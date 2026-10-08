"""
Database module for Perrin Family Movie Ratings App.
PostgreSQL database via SQLAlchemy for Streamlit Cloud deployment.
Tables: users, movies, ratings, watch_status
"""

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from datetime import datetime
from typing import Optional
import os

# Database engine (singleton)
_engine = None


def get_engine():
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        # Try Streamlit secrets first, then environment variable
        try:
            database_url = st.secrets["DATABASE_URL"]
        except Exception:
            database_url = os.environ.get("DATABASE_URL")
        
        if not database_url:
            raise ValueError("DATABASE_URL not found in st.secrets or environment")
        
        # Handle Heroku-style postgres:// URLs (SQLAlchemy requires postgresql://)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        _engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Check connection health
        )
    return _engine


def get_connection():
    """Get a database connection from the pool."""
    return get_engine().connect()


def init_db():
    """Initialize the database with all tables."""
    engine = get_engine()
    
    with engine.begin() as conn:
        # Users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                avatar_emoji TEXT DEFAULT '👤',
                password_hash TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Movies table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                imdb_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                year TEXT,
                poster_url TEXT,
                director TEXT,
                genre TEXT,
                country TEXT,
                actors TEXT,
                plot TEXT,
                imdb_rating TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Ratings table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ratings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                score REAL NOT NULL CHECK (score >= 1.0 AND score <= 10.0),
                comment TEXT,
                mom_compatible INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(user_id, movie_id)
            )
        """))
        
        # Watch status table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS watch_status (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                status TEXT NOT NULL CHECK (status IN ('watched', 'want_to_watch', 'not_interested')),
                watched_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, movie_id)
            )
        """))
        
        # Title shown in the monthly summary (see summary/titles.py), filled from TMDB
        conn.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS display_title TEXT"))

        # One row per monthly summary emailed (see summary/store.py)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS monthly_summaries (
                id SERIAL PRIMARY KEY,
                month DATE UNIQUE NOT NULL,
                tier TEXT NOT NULL,
                colour_text TEXT,
                full_message TEXT NOT NULL,
                used_fallback BOOLEAN NOT NULL,
                attempts INTEGER NOT NULL,
                validation_errors JSONB,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))

        # Create indexes for common queries
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ratings_movie ON ratings(movie_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_watch_status_user ON watch_status(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_watch_status_watched_at ON watch_status(watched_at)"))


def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy row to a dictionary."""
    if row is None:
        return None
    return dict(row._mapping)


def _rows_to_dicts(rows) -> list[dict]:
    """Convert SQLAlchemy rows to a list of dictionaries."""
    return [dict(row._mapping) for row in rows]


# ============== User Functions ==============

def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE id = :id"),
            {"id": user_id}
        )
        row = result.fetchone()
        return _row_to_dict(row)


def create_user_simple(username: str, display_name: str, avatar_emoji: str = "👤") -> int:
    """Create a new user without password and return their ID."""
    with get_engine().begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO users (username, display_name, password_hash, avatar_emoji)
                VALUES (:username, :display_name, '', :avatar_emoji)
                RETURNING id
            """),
            {"username": username, "display_name": display_name, "avatar_emoji": avatar_emoji}
        )
        return result.fetchone()[0]


def get_all_users() -> list[dict]:
    """Get all users."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT id, username, display_name, avatar_emoji FROM users ORDER BY id")
        )
        return _rows_to_dicts(result.fetchall())


# ============== Movie Functions ==============

def get_movie_by_imdb_id(imdb_id: str) -> Optional[dict]:
    """Get movie by IMDb ID."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT * FROM movies WHERE imdb_id = :imdb_id"),
            {"imdb_id": imdb_id}
        )
        row = result.fetchone()
        return _row_to_dict(row)


def get_movie_by_id(movie_id: int) -> Optional[dict]:
    """Get movie by internal ID."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT * FROM movies WHERE id = :id"),
            {"id": movie_id}
        )
        row = result.fetchone()
        return _row_to_dict(row)


def get_or_create_movie(omdb_data: dict) -> int:
    """
    Insert movie from OMDb data or return existing movie ID.
    omdb_data should have keys: imdbID, Title, Year, Poster, Director, Genre, Country, Actors, Plot, imdbRating
    """
    imdb_id = omdb_data.get("imdbID")
    if not imdb_id:
        raise ValueError("Missing imdbID in movie data")
    
    # Check if exists
    existing = get_movie_by_imdb_id(imdb_id)
    if existing:
        return existing["id"]
    
    # Insert new movie
    with get_engine().begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO movies (imdb_id, title, year, poster_url, director, genre, country, actors, plot, imdb_rating)
                VALUES (:imdb_id, :title, :year, :poster_url, :director, :genre, :country, :actors, :plot, :imdb_rating)
                RETURNING id
            """),
            {
                "imdb_id": imdb_id,
                "title": omdb_data.get("Title", "Unknown"),
                "year": omdb_data.get("Year"),
                "poster_url": omdb_data.get("Poster"),
                "director": omdb_data.get("Director"),
                "genre": omdb_data.get("Genre"),
                "country": omdb_data.get("Country"),
                "actors": omdb_data.get("Actors"),
                "plot": omdb_data.get("Plot"),
                "imdb_rating": omdb_data.get("imdbRating")
            }
        )
        return result.fetchone()[0]


# ============== Rating Functions ==============

def add_rating(user_id: int, movie_id: int, score: float, comment: str = "", mom_compatible: Optional[bool] = None) -> int:
    """Add or update a rating. Returns rating ID."""
    now = datetime.now()
    # Convert bool to int for storage (None stays None)
    mom_compat_int = None if mom_compatible is None else (1 if mom_compatible else 0)
    
    with get_engine().begin() as conn:
        # Check if rating exists
        result = conn.execute(
            text("SELECT id FROM ratings WHERE user_id = :user_id AND movie_id = :movie_id"),
            {"user_id": user_id, "movie_id": movie_id}
        )
        existing = result.fetchone()
        
        if existing:
            # Update existing rating
            conn.execute(
                text("""
                    UPDATE ratings 
                    SET score = :score, comment = :comment, mom_compatible = :mom_compatible, updated_at = :updated_at
                    WHERE id = :id
                """),
                {"score": score, "comment": comment, "mom_compatible": mom_compat_int, 
                 "updated_at": now, "id": existing[0]}
            )
            return existing[0]
        else:
            # Insert new rating
            result = conn.execute(
                text("""
                    INSERT INTO ratings (user_id, movie_id, score, comment, mom_compatible, created_at)
                    VALUES (:user_id, :movie_id, :score, :comment, :mom_compatible, :created_at)
                    RETURNING id
                """),
                {"user_id": user_id, "movie_id": movie_id, "score": score, 
                 "comment": comment, "mom_compatible": mom_compat_int, "created_at": now}
            )
            return result.fetchone()[0]


def get_user_rating(user_id: int, movie_id: int) -> Optional[dict]:
    """Get a user's rating for a specific movie."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT * FROM ratings WHERE user_id = :user_id AND movie_id = :movie_id"),
            {"user_id": user_id, "movie_id": movie_id}
        )
        row = result.fetchone()
        if row:
            data = _row_to_dict(row)
            # Convert mom_compatible int to bool
            if data.get("mom_compatible") is not None:
                data["mom_compatible"] = bool(data["mom_compatible"])
            return data
        return None


def get_movie_mom_compatible_status(movie_id: int) -> dict:
    """
    Get the mom-compatible consensus for a movie.
    Returns: {"yes": count, "no": count, "status": "compatible"|"not_compatible"|"mixed"|"unknown"}
    """
    with get_connection() as conn:
        result = conn.execute(
            text("""
                SELECT mom_compatible, COUNT(*) as count
                FROM ratings
                WHERE movie_id = :movie_id AND mom_compatible IS NOT NULL
                GROUP BY mom_compatible
            """),
            {"movie_id": movie_id}
        )
        rows = result.fetchall()
    
    yes_count = 0
    no_count = 0
    for row in rows:
        row_dict = _row_to_dict(row)
        if row_dict["mom_compatible"] == 1:
            yes_count = row_dict["count"]
        elif row_dict["mom_compatible"] == 0:
            no_count = row_dict["count"]
    
    total = yes_count + no_count
    if total == 0:
        status = "unknown"
    elif no_count == 0:
        status = "compatible"
    elif yes_count == 0:
        status = "not_compatible"
    else:
        status = "mixed"
    
    return {"yes": yes_count, "no": no_count, "status": status}


def get_movie_ratings(movie_id: int) -> list[dict]:
    """Get all ratings for a movie with user info."""
    with get_connection() as conn:
        result = conn.execute(
            text("""
                SELECT r.*, u.display_name, u.avatar_emoji
                FROM ratings r
                JOIN users u ON r.user_id = u.id
                WHERE r.movie_id = :movie_id
                ORDER BY r.created_at DESC
            """),
            {"movie_id": movie_id}
        )
        return _rows_to_dicts(result.fetchall())


def get_user_ratings(user_id: int) -> list[dict]:
    """Get all ratings by a user with movie info."""
    with get_connection() as conn:
        result = conn.execute(
            text("""
                SELECT r.*, m.title, m.year, m.poster_url, m.imdb_id
                FROM ratings r
                JOIN movies m ON r.movie_id = m.id
                WHERE r.user_id = :user_id
                ORDER BY r.created_at DESC
            """),
            {"user_id": user_id}
        )
        return _rows_to_dicts(result.fetchall())


# ============== Watch Status Functions ==============

def set_watch_status(user_id: int, movie_id: int, status: str):
    """Set or update watch status for a movie."""
    if status not in ('watched', 'want_to_watch', 'not_interested'):
        raise ValueError(f"Invalid status: {status}")
    
    now = datetime.now()
    watched_at = now if status == 'watched' else None
    
    with get_engine().begin() as conn:
        # Use PostgreSQL's INSERT ... ON CONFLICT
        conn.execute(
            text("""
                INSERT INTO watch_status (user_id, movie_id, status, watched_at, updated_at)
                VALUES (:user_id, :movie_id, :status, :watched_at, :updated_at)
                ON CONFLICT (user_id, movie_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    watched_at = CASE WHEN EXCLUDED.status = 'watched' THEN :watched_at ELSE watch_status.watched_at END,
                    updated_at = EXCLUDED.updated_at
            """),
            {"user_id": user_id, "movie_id": movie_id, "status": status, 
             "watched_at": watched_at, "updated_at": now}
        )


def get_watch_status(user_id: int, movie_id: int) -> Optional[dict]:
    """Get watch status for a specific user and movie."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT * FROM watch_status WHERE user_id = :user_id AND movie_id = :movie_id"),
            {"user_id": user_id, "movie_id": movie_id}
        )
        row = result.fetchone()
        return _row_to_dict(row)


def get_user_watchlist(user_id: int) -> list[dict]:
    """Get movies user wants to watch."""
    with get_connection() as conn:
        result = conn.execute(
            text("""
                SELECT m.*, ws.updated_at as added_to_watchlist
                FROM watch_status ws
                JOIN movies m ON ws.movie_id = m.id
                WHERE ws.user_id = :user_id AND ws.status = 'want_to_watch'
                ORDER BY ws.updated_at DESC
            """),
            {"user_id": user_id}
        )
        return _rows_to_dicts(result.fetchall())


def add_to_watchlist(user_id: int, movie_id: int):
    """Add a movie to user's watchlist."""
    set_watch_status(user_id, movie_id, 'want_to_watch')


def remove_from_watchlist(user_id: int, movie_id: int):
    """Remove a movie from user's watchlist."""
    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM watch_status WHERE user_id = :user_id AND movie_id = :movie_id"),
            {"user_id": user_id, "movie_id": movie_id}
        )


def is_in_watchlist(user_id: int, movie_id: int) -> bool:
    """Check if a movie is in user's watchlist."""
    status = get_watch_status(user_id, movie_id)
    return status is not None and status.get("status") == "want_to_watch"


# ============== Feed & Rankings Functions ==============

def get_latest_watched(limit: int = 20) -> list[dict]:
    """Get the latest watched movies across all users (for the feed)."""
    with get_connection() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    r.score, r.comment, r.created_at,
                    m.id as movie_id, m.imdb_id, m.title, m.year, m.poster_url, m.genre,
                    u.id as user_id, u.display_name, u.avatar_emoji
                FROM ratings r
                JOIN movies m ON r.movie_id = m.id
                JOIN users u ON r.user_id = u.id
                ORDER BY r.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        return _rows_to_dicts(result.fetchall())


def get_family_top100(genre: Optional[str] = None, country: Optional[str] = None, limit: int = 100) -> list[dict]:
    """
    Get family top movies ranked by NORMALIZED average rating.
    Uses Z-score normalization to account for harsh vs generous raters.
    Optionally filter by genre and/or country.
    """
    with get_connection() as conn:
        # Step 1: Calculate each user's rating statistics
        result = conn.execute(text("""
            SELECT user_id, AVG(score) as avg, STDDEV(score) as std
            FROM ratings
            GROUP BY user_id
        """))
        user_stats = {}
        for row in result.fetchall():
            row_dict = _row_to_dict(row)
            std = row_dict["std"] if row_dict["std"] and row_dict["std"] > 0.5 else 0.5
            user_stats[row_dict["user_id"]] = {"avg": row_dict["avg"], "std": std}
        
        # Step 2: Get all ratings with movie info
        query = """
            SELECT r.user_id, r.score, r.movie_id,
                   m.id, m.imdb_id, m.title, m.year, m.poster_url, m.director, 
                   m.genre, m.country, m.imdb_rating
            FROM ratings r
            JOIN movies m ON r.movie_id = m.id
            WHERE 1=1
        """
        params = {}
        
        if genre:
            query += " AND m.genre ILIKE :genre"
            params["genre"] = f"%{genre}%"
        
        if country:
            query += " AND m.country ILIKE :country"
            params["country"] = f"%{country}%"
        
        result = conn.execute(text(query), params)
        ratings = result.fetchall()
    
    # Step 3: Calculate normalized scores for each rating
    movie_scores = {}  # movie_id -> {movie_data, normalized_scores[], raw_scores[]}
    
    for row in ratings:
        row_dict = _row_to_dict(row)
        movie_id = row_dict["movie_id"]
        user_id = row_dict["user_id"]
        raw_score = row_dict["score"]
        
        # Get user stats
        stats = user_stats.get(user_id, {"avg": 7.0, "std": 1.5})
        
        # Z-score normalization: (score - mean) / std
        z_score = (raw_score - stats["avg"]) / stats["std"]
        
        # Convert Z-score back to 1-10 scale (assuming mean=7, std=1.5 as "neutral")
        normalized_score = 7.0 + (z_score * 1.5)
        normalized_score = max(1.0, min(10.0, normalized_score))  # Clamp to 1-10
        
        if movie_id not in movie_scores:
            movie_scores[movie_id] = {
                "id": row_dict["id"],
                "imdb_id": row_dict["imdb_id"],
                "title": row_dict["title"],
                "year": row_dict["year"],
                "poster_url": row_dict["poster_url"],
                "director": row_dict["director"],
                "genre": row_dict["genre"],
                "country": row_dict["country"],
                "imdb_rating": row_dict["imdb_rating"],
                "normalized_scores": [],
                "raw_scores": []
            }
        
        movie_scores[movie_id]["normalized_scores"].append(normalized_score)
        movie_scores[movie_id]["raw_scores"].append(raw_score)
    
    # Step 4: Calculate final normalized average for each movie
    results = []
    for movie_id, data in movie_scores.items():
        normalized_avg = sum(data["normalized_scores"]) / len(data["normalized_scores"])
        raw_avg = sum(data["raw_scores"]) / len(data["raw_scores"])
        
        results.append({
            "id": data["id"],
            "imdb_id": data["imdb_id"],
            "title": data["title"],
            "year": data["year"],
            "poster_url": data["poster_url"],
            "director": data["director"],
            "genre": data["genre"],
            "country": data["country"],
            "imdb_rating": data["imdb_rating"],
            "avg_rating": round(normalized_avg, 1),
            "raw_avg_rating": round(raw_avg, 1),
            "num_ratings": len(data["raw_scores"])
        })
    
    # Sort by normalized average rating, then by number of ratings
    results.sort(key=lambda x: (-x["avg_rating"], -x["num_ratings"]))
    
    return results[:limit]


def get_all_genres() -> list[str]:
    """Get all distinct genres from rated movies."""
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT m.genre 
            FROM movies m
            JOIN ratings r ON m.id = r.movie_id
            WHERE m.genre IS NOT NULL AND m.genre != ''
        """))
        rows = result.fetchall()
    
    # Parse comma-separated genres into unique list
    genres = set()
    for row in rows:
        row_dict = _row_to_dict(row)
        for genre in row_dict["genre"].split(","):
            genre = genre.strip()
            if genre:
                genres.add(genre)
    return sorted(genres)


def get_all_countries() -> list[str]:
    """Get all distinct countries from rated movies."""
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT m.country 
            FROM movies m
            JOIN ratings r ON m.id = r.movie_id
            WHERE m.country IS NOT NULL AND m.country != ''
        """))
        rows = result.fetchall()
    
    # Parse comma-separated countries into unique list
    countries = set()
    for row in rows:
        row_dict = _row_to_dict(row)
        for country in row_dict["country"].split(","):
            country = country.strip()
            if country:
                countries.add(country)
    return sorted(countries)


# ============== Stats Functions ==============

def get_user_stats(user_id: int) -> dict:
    """Get statistics for a user."""
    with get_connection() as conn:
        # Total movies rated
        result = conn.execute(
            text("SELECT COUNT(*) as count FROM ratings WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        total_rated = result.fetchone()[0]
        
        # Average rating
        result = conn.execute(
            text("SELECT AVG(score) as avg FROM ratings WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        avg_row = result.fetchone()
        avg_rating = avg_row[0] if avg_row[0] else 0
        
        # Favorite genres (most rated)
        result = conn.execute(
            text("""
                SELECT m.genre, COUNT(*) as count
                FROM ratings r
                JOIN movies m ON r.movie_id = m.id
                WHERE r.user_id = :user_id AND m.genre IS NOT NULL
                GROUP BY m.genre
                ORDER BY count DESC
                LIMIT 3
            """),
            {"user_id": user_id}
        )
        top_genres = [_row_to_dict(row)["genre"] for row in result.fetchall()]
    
    return {
        "total_rated": total_rated,
        "avg_rating": round(avg_rating, 1),
        "top_genres": top_genres
    }
