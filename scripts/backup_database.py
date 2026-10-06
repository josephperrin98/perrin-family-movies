"""
Database backup script for Perrin Family Movies.
Exports all tables to CSV files.
Run manually or via GitHub Actions.
"""

import os
import csv
import io
import zipfile
from datetime import datetime
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Handle Heroku-style postgres:// URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)


def export_table_to_csv(table_name: str, query: str) -> str:
    """Export a table to CSV format."""
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()
        columns = result.keys()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def create_backup():
    """Create a full backup as a ZIP file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export each table
    tables = {
        "users.csv": "SELECT id, username, display_name, avatar_emoji, created_at FROM users ORDER BY id",
        "movies.csv": "SELECT id, imdb_id, title, year, poster_url, director, genre, country, plot, imdb_rating, added_at FROM movies ORDER BY id",
        "ratings.csv": """
            SELECT r.id, r.user_id, u.username, r.movie_id, m.title, m.imdb_id,
                   r.score, r.comment, r.mom_compatible, r.created_at, r.updated_at
            FROM ratings r
            JOIN users u ON r.user_id = u.id
            JOIN movies m ON r.movie_id = m.id
            ORDER BY r.id
        """,
        "watch_status.csv": """
            SELECT ws.id, ws.user_id, u.username, ws.movie_id, m.title, m.imdb_id,
                   ws.status, ws.watched_at, ws.updated_at
            FROM watch_status ws
            JOIN users u ON ws.user_id = u.id
            JOIN movies m ON ws.movie_id = m.id
            ORDER BY ws.id
        """
    }
    
    # Create ZIP file
    zip_filename = f"backup_{timestamp}.zip"
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, query in tables.items():
            csv_data = export_table_to_csv(filename, query)
            zip_file.writestr(filename, csv_data)
        
        # Add README
        readme = f"""Perrin Family Movies Backup
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Contents:
- users.csv: All family members
- movies.csv: All movies in the database  
- ratings.csv: All ratings with user and movie info
- watch_status.csv: Watch status records (watchlist, etc.)

To restore: Import CSVs into your PostgreSQL database.
"""
        zip_file.writestr("README.txt", readme)
    
    print(f"✅ Backup created: {zip_filename}")
    
    # Print summary
    with engine.connect() as conn:
        users = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
        movies = conn.execute(text("SELECT COUNT(*) FROM movies")).fetchone()[0]
        ratings = conn.execute(text("SELECT COUNT(*) FROM ratings")).fetchone()[0]
        watch = conn.execute(text("SELECT COUNT(*) FROM watch_status")).fetchone()[0]
    
    print(f"   Users: {users}")
    print(f"   Movies: {movies}")
    print(f"   Ratings: {ratings}")
    print(f"   Watch Status: {watch}")
    
    return zip_filename


if __name__ == "__main__":
    create_backup()


