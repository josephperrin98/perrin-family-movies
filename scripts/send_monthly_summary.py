"""
Build the monthly family summary and email it.

Run from the repo root:
    python -m scripts.send_monthly_summary --dry-run          # previous month, print only
    python -m scripts.send_monthly_summary --month 2026-09    # a given month, send for real
    python -m scripts.send_monthly_summary --month 2026-09 --until 2026-10-09   # longer period
"""

import argparse
import os
from datetime import date, datetime
from typing import Optional

import anthropic

import database
from summary.delivery import build_email, send_email
from summary.facts import PARIS, month_before
from summary.service import loggable_errors, run_month
from summary.store import PostgresStore
from summary.titles import TmdbAuthError, fetch_tmdb_titles, fill_display_titles
from summary.writer import write_colour

DEFAULT_MODEL = "claude-opus-5-5"


def parse_month(value: str) -> tuple[int, int]:
    year, month = (int(part) for part in value.split("-"))
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month: {value}")
    return year, month


def target_month(arg: Optional[str], now: datetime) -> tuple[int, int]:
    return parse_month(arg) if arg else month_before(now.year, now.month)


def require_env(names: list[str]) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--month", help="YYYY-MM (default: previous month)")
    parser.add_argument("--until", type=date.fromisoformat,
                        help="YYYY-MM-DD: extend the period up to this day (excluded)")
    parser.add_argument("--dry-run", action="store_true",
                        help="generate and print only: no email, no database write")
    args = parser.parse_args()

    require_env(["ANTHROPIC_API_KEY"] + ([] if args.dry_run else ["SMTP_USER", "SMTP_APP_PASSWORD", "SUMMARY_TO"]))
    year, month = target_month(args.month, datetime.now(PARIS))
    model = os.environ.get("SUMMARY_MODEL", DEFAULT_MODEL)
    public_logs = os.environ.get("PUBLIC_LOGS") == "true"

    database.init_db()
    engine = database.get_engine()

    # Titles are a nice-to-have: a TMDB problem must not block the summary
    token = os.environ.get("TMDB_READ_TOKEN")
    if token:
        try:
            fill_display_titles(engine, fetch=lambda imdb_id: fetch_tmdb_titles(imdb_id, token))
        except TmdbAuthError as e:
            print(f"Warning: {e}; using existing titles.")

    client = anthropic.Anthropic()

    def write(payload, feedback):
        return write_colour(client, model, payload, feedback)

    def send(subject, message):
        user = os.environ["SMTP_USER"]
        send_email(build_email(user, os.environ["SUMMARY_TO"], subject, message),
                   user, os.environ["SMTP_APP_PASSWORD"])

    outcome = run_month(PostgresStore(engine), year, month, write, send, model,
                        dry_run=args.dry_run, until=args.until)

    print(f"{outcome.subject}: {outcome.status}")
    g = outcome.generation
    if g is None:
        return
    print(f"attempts={g.attempts} fallback={g.used_fallback} chars={len(g.full_message)} "
          f"tokens_in={g.input_tokens} tokens_out={g.output_tokens}")
    for line in loggable_errors(g.errors, public_logs):
        print(line)
    # Workflow logs on a public repo are public: never print family data there
    if not public_logs:
        print("\n" + g.full_message)


if __name__ == "__main__":
    main()
