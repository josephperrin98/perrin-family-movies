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


# One CSV per table. SELECT * so a new column is backed up without anyone
# remembering to add it; tests/test_backup.py checks no table is missing.
# ratings and watch_status also carry who and which film, for humans reading them.
BACKUP_QUERIES = {
    "users.csv": "SELECT * FROM users ORDER BY id",
    "movies.csv": "SELECT * FROM movies ORDER BY id",
    "ratings.csv": """
        SELECT r.*, u.username, m.title AS movie_title, m.imdb_id
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        JOIN movies m ON r.movie_id = m.id
        ORDER BY r.id
    """,
    "watch_status.csv": """
        SELECT ws.*, u.username, m.title AS movie_title, m.imdb_id
        FROM watch_status ws
        JOIN users u ON ws.user_id = u.id
        JOIN movies m ON ws.movie_id = m.id
        ORDER BY ws.id
    """,
    "monthly_summaries.csv": "SELECT * FROM monthly_summaries ORDER BY month",
}


def create_backup():
    """Create a full backup as a ZIP file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"backup_{timestamp}.zip"

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, query in BACKUP_QUERIES.items():
            zip_file.writestr(filename, export_table_to_csv(filename, query))
        zip_file.writestr("README.txt", f"""Perrin Family Movies Backup
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

One CSV per table: {", ".join(BACKUP_QUERIES)}

To restore: Import CSVs into your PostgreSQL database.
""")

    print(f"✅ Backup created: {zip_filename}")
    with engine.connect() as conn:
        for filename in BACKUP_QUERIES:
            table = filename.removesuffix(".csv")
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
            print(f"   {table}: {count}")

    return zip_filename


if __name__ == "__main__":
    create_backup()


