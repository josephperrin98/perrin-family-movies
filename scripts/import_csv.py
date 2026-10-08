"""
Import family movie ratings from CSV into the PostgreSQL database.
Looks up each movie via OMDb API to get IMDb IDs, posters, and ratings.
Users must already exist (the app creates them on first launch); each CSV
contributor is matched to a user by display name, case-insensitively.

Run: DATABASE_URL=... OMDB_API_KEY=... python scripts/import_csv.py path/to/file.csv
"""

import os
import sys
import csv
import re
import time
import requests
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OMDB_URL = "https://www.omdbapi.com/"
OMDB_DELAY = 0.15  # seconds between API calls (respect rate limits)

DATABASE_URL = os.environ.get("DATABASE_URL")
OMDB_API_KEY = os.environ.get("OMDB_API_KEY")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required")
    sys.exit(1)
if not OMDB_API_KEY:
    print("ERROR: OMDB_API_KEY environment variable is required")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# ---------------------------------------------------------------------------
# French/Italian -> English title translations for OMDb lookup
# ---------------------------------------------------------------------------

TITLE_TRANSLATIONS = {
    "8 1/2": "8½",
    "Anatomie d'une chute": "Anatomy of a Fall",
    "Asterix aux Jeux Oympiques": "Asterix at the Olympic Games",
    "Au Poste!": "Keep an Eye Out",
    "C'è ancora domani": "There's Still Tomorrow",
    "Ce qui nous lie": "Back to Burgundy",
    "Chien de la Casse": "Chien de la casse",
    "D'Argent et de Sang": "D'Argent et de Sang",
    "En Attendand Mr Bojangles": "Waiting for Bojangles",
    "Encanto": "Encanto",
    "Je verrai tous vos visages": "All Your Faces",
    "La Grande Bellezza": "The Great Beauty",
    "La nuit du 12": "The Night of the 12th",
    "La ragazza con la valigia": "Girl with a Suitcase",
    "Le goût des autres": "The Taste of Others",
    "Le Livre des solutions": "The Book of Solutions",
    "Le cahier des solutions": "The Book of Solutions",
    "Le Procès Goldman": "The Goldman Case",
    "Le Tour de France": "Tour de France: Unchained",
    "Les choses de la vie": "The Things of Life",
    "Les Misérables": "Les Misérables",
    "Les Rois Mages": "Les rois mages",
    "Mission: Impossible - Dead Reckoning Partie 1": "Mission: Impossible - Dead Reckoning Part One",
    "Mon crime": "My Crime",
    "Old Boy": "Oldboy",
    "Reste un peu": "Reste un peu",
    "Tirailleurs": "Father & Soldier",
    "Une année difficile": "A Difficult Year",
    "Caro diario": "Dear Diary",
    "Amber v Depp: the Case": "Depp vs Heard",
}

# ---------------------------------------------------------------------------
# OMDb helpers
# ---------------------------------------------------------------------------

def omdb_get_by_title(title, year=None, media_type="movie"):
    """Exact title lookup via OMDb API."""
    params = {"apikey": OMDB_API_KEY, "t": title.strip(), "plot": "short"}
    if media_type:
        params["type"] = media_type
    if year:
        params["y"] = str(year)
    try:
        resp = requests.get(OMDB_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("Response") == "True":
            return data
    except Exception:
        pass
    return None


def omdb_search(title, year=None):
    """Fuzzy search via OMDb API, returns first result."""
    params = {"apikey": OMDB_API_KEY, "s": title.strip()}
    if year:
        params["y"] = str(year)
    try:
        resp = requests.get(OMDB_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("Response") == "True" and data.get("Search"):
            return data["Search"][0]
    except Exception:
        pass
    return None


def lookup_movie(title, year, is_series=False):
    """
    Multi-step OMDb lookup:
    1. Exact match with original title
    2. Exact match with translated English title
    3. Exact match without type filter (catches series listed as movies etc.)
    4. Fuzzy search
    Returns OMDb data dict or None.
    """
    media_type = "series" if is_series else "movie"
    clean_year = _extract_year(year)

    # Step 1: exact match with original title
    result = omdb_get_by_title(title, clean_year, media_type)
    if result:
        return result
    time.sleep(OMDB_DELAY)

    # Step 1b: try without type filter
    result = omdb_get_by_title(title, clean_year, media_type=None)
    if result:
        return result
    time.sleep(OMDB_DELAY)

    # Step 2: translated title
    english_title = TITLE_TRANSLATIONS.get(title)
    if english_title and english_title != title:
        result = omdb_get_by_title(english_title, clean_year, media_type)
        if result:
            return result
        time.sleep(OMDB_DELAY)

        result = omdb_get_by_title(english_title, clean_year, media_type=None)
        if result:
            return result
        time.sleep(OMDB_DELAY)

        # Try translated title without year (sometimes year is off by one)
        if clean_year:
            result = omdb_get_by_title(english_title, None, media_type=None)
            if result:
                return result
            time.sleep(OMDB_DELAY)

    # Step 3: fuzzy search with original title
    search_hit = omdb_search(title, clean_year)
    if search_hit and search_hit.get("imdbID"):
        params = {"apikey": OMDB_API_KEY, "i": search_hit["imdbID"], "plot": "short"}
        try:
            resp = requests.get(OMDB_URL, params=params, timeout=10)
            data = resp.json()
            if data.get("Response") == "True":
                return data
        except Exception:
            pass
        time.sleep(OMDB_DELAY)

    # Step 4: fuzzy search with English title
    if english_title and english_title != title:
        search_hit = omdb_search(english_title, clean_year)
        if search_hit and search_hit.get("imdbID"):
            params = {"apikey": OMDB_API_KEY, "i": search_hit["imdbID"], "plot": "short"}
            try:
                resp = requests.get(OMDB_URL, params=params, timeout=10)
                data = resp.json()
                if data.get("Response") == "True":
                    return data
            except Exception:
                pass
            time.sleep(OMDB_DELAY)

    return None


def _extract_year(raw):
    """Extract a 4-digit year from various formats."""
    if not raw:
        return None
    raw = str(raw).strip()
    m = re.search(r"(19|20)\d{2}", raw)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------

def parse_score(raw):
    """Parse a rating score, return float or None."""
    if not raw:
        return None
    raw = str(raw).strip().replace(",", ".")
    try:
        score = float(raw)
        if 1.0 <= score <= 10.0:
            return score
        return None  # out of range (likely an Excel serial date)
    except ValueError:
        return None


def parse_mom_compatible(raw):
    """Parse mom-compatible flag: returns True, False, or None."""
    if not raw:
        return None
    val = str(raw).strip().lower()
    if val in ("oui", "yes", "absolument", "carrément"):
        return True
    if val.startswith("oui"):
        return True
    if val in ("non", "nope", "no"):
        return False
    return None  # "bof", "maybe", empty, etc.


def parse_watch_date(raw):
    """Best-effort parse of watch date. Returns datetime or None."""
    if not raw:
        return None
    raw = str(raw).strip().lower()
    if raw in ("na", "n/a", "", "0", "boh"):
        return None

    # Try dd/mm/yyyy
    for fmt in ("%d/%m/%Y", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass

    # Handle Excel serial dates (5-digit numbers)
    try:
        serial = int(float(raw))
        if 40000 < serial < 50000:
            from datetime import timedelta
            return datetime(1899, 12, 30) + timedelta(days=serial)
    except (ValueError, OverflowError):
        pass

    # Handle month-year in French ("septembre 2023", "avril 2023")
    FR_MONTHS = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    }
    for month_name, month_num in FR_MONTHS.items():
        if month_name in raw:
            year_match = re.search(r"(20\d{2})", raw)
            if year_match:
                return datetime(int(year_match.group(1)), month_num, 1)

    # Handle "11.2023" style
    m = re.match(r"(\d{1,2})\.(\d{4})", raw)
    if m:
        return datetime(int(m.group(2)), int(m.group(1)), 1)

    return None


def make_placeholder_imdb_id(title, year):
    """Generate a deterministic placeholder IMDb ID for movies not found on OMDb."""
    key = f"{title}_{year}".lower()
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return f"csv_{slug}"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_user_id_map():
    """Return {lowercased display_name: id}, used to match CSV contributors."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, display_name FROM users")).fetchall()
    return {r[1].lower(): r[0] for r in rows}


def upsert_movie(imdb_id, title, year, director, genre, country, actors, plot,
                 poster_url=None, imdb_rating=None):
    """Insert movie or return existing ID."""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM movies WHERE imdb_id = :iid"),
            {"iid": imdb_id}
        ).fetchone()
        if row:
            return row[0]

        result = conn.execute(text("""
            INSERT INTO movies (imdb_id, title, year, poster_url, director, genre,
                                country, actors, plot, imdb_rating)
            VALUES (:imdb_id, :title, :year, :poster, :director, :genre,
                    :country, :actors, :plot, :imdb_rating)
            RETURNING id
        """), {
            "imdb_id": imdb_id, "title": title, "year": year,
            "poster": poster_url, "director": director, "genre": genre,
            "country": country, "actors": actors, "plot": plot,
            "imdb_rating": imdb_rating,
        })
        return result.fetchone()[0]


def upsert_rating(user_id, movie_id, score, comment, mom_compatible):
    """Insert or update a rating."""
    mom_int = None if mom_compatible is None else (1 if mom_compatible else 0)
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, as database.utc_now
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM ratings WHERE user_id = :uid AND movie_id = :mid"),
            {"uid": user_id, "mid": movie_id}
        ).fetchone()
        if existing:
            conn.execute(text("""
                UPDATE ratings SET score = :s, comment = :c,
                       mom_compatible = :mc, updated_at = :now
                WHERE id = :rid
            """), {"s": score, "c": comment, "mc": mom_int, "now": now, "rid": existing[0]})
        else:
            conn.execute(text("""
                INSERT INTO ratings (user_id, movie_id, score, comment, mom_compatible, created_at)
                VALUES (:uid, :mid, :s, :c, :mc, :now)
            """), {"uid": user_id, "mid": movie_id, "s": score, "c": comment,
                   "mc": mom_int, "now": now})


def upsert_watch_status(user_id, movie_id, watched_at=None):
    """Mark a movie as watched."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, as database.utc_now
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO watch_status (user_id, movie_id, status, watched_at, updated_at)
            VALUES (:uid, :mid, 'watched', :wat, :now)
            ON CONFLICT (user_id, movie_id) DO UPDATE SET
                status = 'watched',
                watched_at = COALESCE(EXCLUDED.watched_at, watch_status.watched_at),
                updated_at = EXCLUDED.updated_at
        """), {"uid": user_id, "mid": movie_id, "wat": watched_at, "now": now})


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def read_csv(path):
    """Read the family CSV, returning a list of row dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        all_lines = list(reader)

    # Find the header row (contains "Nom" and "Contributeur")
    header_idx = None
    for i, line in enumerate(all_lines):
        joined = ",".join(line).lower()
        if "contributeur" in joined and "nom" in joined:
            header_idx = i
            break

    if header_idx is None:
        print("ERROR: Could not find header row in CSV")
        sys.exit(1)

    headers = [h.strip().replace("\n", " ") for h in all_lines[header_idx]]
    # Normalize header names for easier access
    col_map = {}
    for i, h in enumerate(headers):
        hl = h.lower()
        if "contributeur" in hl:
            col_map["contributor"] = i
        elif hl == "nom":
            col_map["title"] = i
        elif "réalisateur" in hl or "realisateur" in hl:
            col_map["director"] = i
        elif "acteur" in hl:
            col_map["actors"] = i
        elif hl == "type":
            col_map["type"] = i
        elif hl == "genre":
            col_map["genre"] = i
        elif "année" in hl or "annee" in hl:
            col_map["year"] = i
        elif hl == "pays":
            col_map["country"] = i
        elif "description" in hl:
            col_map["plot"] = i
        elif hl == "notes":
            col_map["comment"] = i
        elif "note" in hl:
            col_map["score"] = i
        elif "date" in hl:
            col_map["watch_date"] = i
        elif "maman" in hl:
            col_map["mom_compatible"] = i
        elif "rang" in hl:
            col_map["rank"] = i

    for data_line in all_lines[header_idx + 1:]:
        if len(data_line) < 5:
            continue
        # Skip empty rows
        if all(not cell.strip() for cell in data_line[:6]):
            continue

        def g(key):
            idx = col_map.get(key)
            if idx is None or idx >= len(data_line):
                return ""
            return data_line[idx].strip()

        title = g("title")
        contributor = g("contributor")
        if not title or not contributor:
            continue

        rows.append({
            "title": title,
            "contributor": contributor,
            "director": g("director"),
            "actors": g("actors"),
            "media_type": g("type"),
            "genre": g("genre"),
            "year": g("year"),
            "country": g("country"),
            "plot": g("plot"),
            "comment": g("comment"),
            "score_raw": g("score"),
            "watch_date_raw": g("watch_date"),
            "mom_compatible_raw": g("mom_compatible"),
        })

    return rows


def main():
    print("=" * 60)
    print("  Family Filmographie - CSV Import")
    print("=" * 60)

    # 1. Read CSV
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_csv.py path/to/file.csv")
        sys.exit(1)
    csv_path = os.path.abspath(sys.argv[1])
    print(f"\n📂 Reading CSV: {csv_path}")
    rows = read_csv(csv_path)
    print(f"   Found {len(rows)} rating entries")

    # 2. Load existing users
    user_map = get_user_id_map()
    print(f"   Users: {list(user_map.keys())}")

    # 3. Group rows by unique movie (title + year)
    movie_groups = {}
    for row in rows:
        key = (row["title"], _extract_year(row["year"]) or row["year"])
        if key not in movie_groups:
            movie_groups[key] = row  # keep first occurrence for movie metadata
        # We don't group ratings here, just need unique movies

    unique_movies = list(movie_groups.keys())
    print(f"\n🎬 Found {len(unique_movies)} unique movies to look up")

    # 4. Look up each unique movie via OMDb
    print("\n🔍 Looking up movies via OMDb API...")
    movie_cache = {}  # (title, year) -> {imdb_id, omdb_data_or_None}

    found_count = 0
    placeholder_count = 0

    for i, (title, year) in enumerate(unique_movies):
        meta = movie_groups[(title, year)]
        is_series = meta["media_type"].lower() in ("série", "serie", "minisérie", "série télévisée")
        
        omdb = lookup_movie(title, year, is_series=is_series)

        if omdb:
            imdb_id = omdb.get("imdbID")
            movie_cache[(title, year)] = {
                "imdb_id": imdb_id,
                "title": omdb.get("Title", title),
                "year": omdb.get("Year", year),
                "director": omdb.get("Director") if omdb.get("Director") != "N/A" else meta["director"],
                "genre": omdb.get("Genre") if omdb.get("Genre") != "N/A" else meta["genre"],
                "country": omdb.get("Country") if omdb.get("Country") != "N/A" else meta["country"],
                "actors": omdb.get("Actors") if omdb.get("Actors") != "N/A" else meta["actors"],
                "plot": omdb.get("Plot") if omdb.get("Plot") != "N/A" else meta["plot"],
                "poster_url": omdb.get("Poster") if omdb.get("Poster") != "N/A" else None,
                "imdb_rating": omdb.get("imdbRating") if omdb.get("imdbRating") != "N/A" else None,
            }
            found_count += 1
            print(f"   ✅ [{i+1}/{len(unique_movies)}] {title} ({year}) -> {imdb_id}")
        else:
            placeholder_id = make_placeholder_imdb_id(title, year)
            movie_cache[(title, year)] = {
                "imdb_id": placeholder_id,
                "title": title,
                "year": year,
                "director": meta["director"],
                "genre": meta["genre"],
                "country": meta["country"],
                "actors": meta["actors"],
                "plot": meta["plot"],
                "poster_url": None,
                "imdb_rating": None,
            }
            placeholder_count += 1
            print(f"   ⚠️  [{i+1}/{len(unique_movies)}] {title} ({year}) -> placeholder: {placeholder_id}")

    print(f"\n   OMDb matched: {found_count} | Placeholders: {placeholder_count}")

    # 5. Insert movies and ratings
    print("\n💾 Inserting movies and ratings into database...")
    ratings_inserted = 0
    ratings_skipped = 0

    for row in rows:
        title = row["title"]
        year = _extract_year(row["year"]) or row["year"]
        key = (title, year)
        cached = movie_cache.get(key)
        if not cached:
            print(f"   ❌ No cache entry for: {title} ({year}) - skipping")
            ratings_skipped += 1
            continue

        # Insert/get movie
        movie_id = upsert_movie(
            imdb_id=cached["imdb_id"],
            title=cached["title"],
            year=cached["year"],
            director=cached["director"],
            genre=cached["genre"],
            country=cached["country"],
            actors=cached["actors"],
            plot=cached["plot"],
            poster_url=cached["poster_url"],
            imdb_rating=cached["imdb_rating"],
        )

        # Resolve user
        contributor = row["contributor"]
        user_id = user_map.get(contributor.lower())
        if not user_id:
            print(f"   ❌ No user named {contributor} - skipping")
            ratings_skipped += 1
            continue

        # Parse score
        score = parse_score(row["score_raw"])
        if score is None:
            print(f"   ⏭️  Skipping rating (no valid score): {contributor} -> {title} (raw: '{row['score_raw']}')")
            ratings_skipped += 1
            continue

        # Parse other fields
        comment = row["comment"] or ""
        mom_compat = parse_mom_compatible(row["mom_compatible_raw"])
        watch_date = parse_watch_date(row["watch_date_raw"])

        # Insert rating
        upsert_rating(user_id, movie_id, score, comment, mom_compat)
        ratings_inserted += 1

        # Set watch status
        upsert_watch_status(user_id, movie_id, watched_at=watch_date)

    # 6. Summary
    print("\n" + "=" * 60)
    print("  Import Complete!")
    print("=" * 60)
    print(f"  Movies in DB (from this import): {found_count + placeholder_count}")
    print(f"    - OMDb matched:  {found_count}")
    print(f"    - Placeholders:  {placeholder_count}")
    print(f"  Ratings inserted:  {ratings_inserted}")
    print(f"  Ratings skipped:   {ratings_skipped}")

    # Final DB counts
    with engine.connect() as conn:
        total_movies = conn.execute(text("SELECT COUNT(*) FROM movies")).fetchone()[0]
        total_ratings = conn.execute(text("SELECT COUNT(*) FROM ratings")).fetchone()[0]
        total_watch = conn.execute(text("SELECT COUNT(*) FROM watch_status")).fetchone()[0]
    print("\n  Total DB counts:")
    print(f"    Movies:       {total_movies}")
    print(f"    Ratings:      {total_ratings}")
    print(f"    Watch Status: {total_watch}")


if __name__ == "__main__":
    main()
