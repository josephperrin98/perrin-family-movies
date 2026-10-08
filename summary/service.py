"""
Monthly summary orchestration: facts -> Claude -> checks -> retry -> email -> store.

The writer, the email sender and the store are passed in (dependency
injection), so every path, including failures, is tested without network,
database or cost.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from summary.facts import MonthFacts, compute_facts, month_before
from summary.render import assemble, fallback_colour, period_label, render_facts, subject, title
from summary.validate import validate
from summary.writer import WriterError, WriterResult, build_payload

MAX_ATTEMPTS = 3  # first try + 2 retries
API_ERROR = "API indisponible : "

Writer = Callable[[dict, Optional[tuple[str, list[str]]]], WriterResult]


@dataclass
class Generation:
    colour_text: Optional[str]  # None when the fallback was used
    full_message: str
    used_fallback: bool
    attempts: int
    errors: list[list[str]] = field(default_factory=list)  # one list per failed attempt
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class RunOutcome:
    status: str  # "already_sent" | "dry_run" | "sent"
    subject: str
    generation: Optional[Generation] = None


def generate_message(facts: MonthFacts, previous_texts: list[str], write: Writer) -> Generation:
    payload = build_payload(facts, previous_texts)
    facts_text = render_facts(facts)
    title_line = title(facts.year, facts.month, facts.until)
    errors_log: list[list[str]] = []
    tokens_in = tokens_out = 0
    feedback = None
    attempts = 0

    for attempts in range(1, MAX_ATTEMPTS + 1):
        try:
            result = write(payload, feedback)
        except WriterError as e:
            errors_log.append([f"{API_ERROR}{e}"])
            break
        tokens_in += result.input_tokens
        tokens_out += result.output_tokens
        if result.colour is None:
            errors_log.append(["Réponse inexploitable (refus ou sortie incomplète)."])
            continue
        errors = validate(result.colour, facts, previous_texts)
        if not errors:
            message = result.colour.message
            return Generation(message, assemble(title_line, message, facts_text), False, attempts,
                              errors_log, tokens_in, tokens_out)
        errors_log.append(errors)
        feedback = (result.colour.message, errors)

    fallback = fallback_colour(facts.tier, period_label(facts.year, facts.month, facts.until))
    return Generation(None, assemble(title_line, fallback, facts_text), True, attempts,
                      errors_log, tokens_in, tokens_out)


def loggable_errors(errors: list[list[str]], public: bool) -> list[str]:
    """One log line per failed attempt.

    Public logs (the repo is public) keep API errors, which say nothing about
    the family, and reduce validation errors, which quote names and drafts,
    to a count.
    """
    lines = []
    for i, attempt in enumerate(errors, 1):
        if public and not all(e.startswith(API_ERROR) for e in attempt):
            lines.append(f"attempt {i}: {len(attempt)} validation errors (hidden in public logs)")
        else:
            lines.append(f"attempt {i} errors: {attempt}")
    return lines


def run_month(store, year: int, month: int, write: Writer, send: Callable[[str, str], None],
              model: str, dry_run: bool = False, until: Optional[date] = None) -> RunOutcome:
    """Build the month's summary and email it once.

    Order matters: email first, then record. If the email fails, nothing is
    recorded and the next run tries again; the reverse order could mark as
    sent a summary that never left.
    """
    email_subject = subject(year, month, until)
    if not dry_run and store.summary_exists(year, month):
        return RunOutcome("already_sent", email_subject)

    facts = compute_facts(year, month, store.month_rows(year, month, until),
                          store.month_rows(*month_before(year, month)), until=until,
                          family=store.family_names())
    generation = generate_message(facts, store.previous_colour_texts(year, month), write)
    if dry_run:
        return RunOutcome("dry_run", email_subject, generation)

    send(email_subject, generation.full_message)
    store.save_summary(year, month, facts.tier, generation, model)
    return RunOutcome("sent", email_subject, generation)
