"""
Display titles for the monthly summary.

OMDb only gives English titles. The family wants the original title when it is
written in the Latin alphabet, and the French title otherwise (Japanese,
Korean, Cyrillic...). TMDB provides both, looked up by IMDb ID.
"""

import unicodedata
from typing import Callable, Optional

import requests
from sqlalchemy import text

TMDB_FIND_URL = "https://api.themoviedb.org/3/find/{imdb_id}"
TIMEOUT = 10

# (original_title, french_title), or None when TMDB has no match
Titles = Optional[tuple[str, Optional[str]]]


def is_latin(title: str) -> bool:
    """True if every letter in the title is Latin. Accents count as Latin;
    digits and punctuation are ignored."""
    letters = [c for c in title if c.isalpha()]
    return all(unicodedata.name(c, "").startswith("LATIN") for c in letters)


def choose_display_title(original: str, french: Optional[str]) -> str:
    """Original title if readable (Latin alphabet), otherwise the French one."""
    if is_latin(original) or not french:
        return original
    return french


def parse_tmdb_find(data: dict) -> Titles:
    """Extract (original_title, french_title) from a TMDB /find response."""
    results = data.get("movie_results") or []
    if not results or not results[0].get("original_title"):
        return None
    return results[0]["original_title"], results[0].get("title")


def fetch_tmdb_titles(imdb_id: str, token: str) -> Titles:
    """Look up a film on TMDB by IMDb ID. Returns None if not found or on error."""
    try:
        response = requests.get(
            TMDB_FIND_URL.format(imdb_id=imdb_id),
            params={"external_source": "imdb_id", "language": "fr-FR"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    return parse_tmdb_find(response.json())


def resolve_display_title(imdb_id: str, title: str, fetch: Callable[[str], Titles]) -> Optional[str]:
    """Display title for one film, or None if it can't be resolved yet.

    Manually added films (placeholder IDs) keep the title the family typed.
    """
    if imdb_id.startswith("manual_"):
        return title
    titles = fetch(imdb_id)
    if titles is None:
        return None
    return choose_display_title(*titles)


def fill_display_titles(engine, fetch: Callable[[str], Titles], dry_run: bool = False) -> list[dict]:
    """Resolve every film that has no display title yet.

    Unresolved films stay NULL and are retried on the next run.
    Returns one {"title", "display_title"} dict per film examined.
    """
    with engine.connect() as conn:
        movies = conn.execute(
            text("SELECT id, imdb_id, title FROM movies WHERE display_title IS NULL ORDER BY id")
        ).mappings().all()

    results = []
    for movie in movies:
        display_title = resolve_display_title(movie["imdb_id"], movie["title"], fetch)
        results.append({"title": movie["title"], "display_title": display_title})
        if display_title is not None and not dry_run:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE movies SET display_title = :display_title WHERE id = :id"),
                    {"display_title": display_title, "id": movie["id"]},
                )
    return results
