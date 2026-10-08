"""
Fill movies.display_title from TMDB for every film that doesn't have one yet.

Run from the repo root:
    DATABASE_URL=... TMDB_READ_TOKEN=... python -m scripts.fill_display_titles --dry-run
    DATABASE_URL=... TMDB_READ_TOKEN=... python -m scripts.fill_display_titles
"""

import argparse
import os

import database
from summary.titles import TmdbAuthError, fetch_tmdb_titles, fill_display_titles


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print proposals without writing titles (the empty column is still added)")
    args = parser.parse_args()

    token = os.environ.get("TMDB_READ_TOKEN")
    if not token:
        raise SystemExit("TMDB_READ_TOKEN environment variable is required")

    database.init_db()  # adds the display_title column if missing
    try:
        results = fill_display_titles(
            database.get_engine(),
            fetch=lambda imdb_id: fetch_tmdb_titles(imdb_id, token),
            dry_run=args.dry_run,
        )
    except TmdbAuthError as e:
        raise SystemExit(f"{e}. Use the long 'API Read Access Token', not the short API key.")

    for r in results:
        shown = r["display_title"] or "(not found, will retry)"
        marker = "  " if r["display_title"] == r["title"] else "->"
        print(f"{marker} {r['title']}  |  {shown}")

    resolved = sum(1 for r in results if r["display_title"])
    verb = "would update" if args.dry_run else "updated"
    print(f"\n{len(results)} films without a display title, {verb} {resolved}.")


if __name__ == "__main__":
    main()
