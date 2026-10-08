"""
Display titles for the monthly summary.

The family's rule: keep the original title for French, English, Italian and
Spanish films, and use the English title for everything else. OMDb (where
movies.title comes from) only knows English titles; TMDB knows each film's
original title and original language, looked up by IMDb ID.
"""

from typing import Callable, Optional

import requests
from sqlalchemy import text

TMDB_FIND_URL = "https://api.themoviedb.org/3/find/{imdb_id}"
TIMEOUT = 10
ORIGINAL_TITLE_LANGUAGES = {"fr", "en", "it", "es"}

# (original_title, original_language), or None when TMDB has no match
Titles = Optional[tuple[str, str]]


def choose_display_title(original: str, language: str, english: str) -> str:
    """Original title for the languages the family reads, English otherwise."""
    if language in ORIGINAL_TITLE_LANGUAGES:
        return original
    return english


def parse_tmdb_find(data: dict) -> Titles:
    """Extract (original_title, original_language) from a TMDB /find response.

    Films come back in movie_results; TV series (Fleabag, The Bear...) in
    tv_results, whose title field is called original_name.
    """
    for results, title_key in (
        (data.get("movie_results"), "original_title"),
        (data.get("tv_results"), "original_name"),
    ):
        if results and results[0].get(title_key) and results[0].get("original_language"):
            return results[0][title_key], results[0]["original_language"]
    return None


class TmdbAuthError(Exception):
    """TMDB rejected the token: a configuration problem, not a missing film."""


def fetch_tmdb_titles(imdb_id: str, token: str) -> Titles:
    """Look up a film on TMDB by IMDb ID.

    Returns None if the film isn't found or the request fails (retried next
    run). Raises TmdbAuthError on a rejected token, so a bad setup stops the
    run instead of marking every film as not found.
    """
    try:
        response = requests.get(
            TMDB_FIND_URL.format(imdb_id=imdb_id),
            params={"external_source": "imdb_id"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        return None
    if response.status_code in (401, 403):
        raise TmdbAuthError(f"TMDB rejected the token (HTTP {response.status_code})")
    if response.status_code != 200:
        return None
    return parse_tmdb_find(response.json())


def resolve_display_title(imdb_id: str, title: str, fetch: Callable[[str], Titles]) -> Optional[str]:
    """Display title for one film, or None if it can't be resolved yet.

    Films without a real IMDb ID (placeholders such as manual_... from the app
    or csv_... from the import) keep the title the family typed.
    """
    if not imdb_id.startswith("tt"):
        return title
    titles = fetch(imdb_id)
    if titles is None:
        return None
    original, language = titles
    return choose_display_title(original, language, english=title)


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
