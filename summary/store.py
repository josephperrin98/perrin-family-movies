"""
Every SQL query the monthly summary needs, behind one small class.

service.run_month only calls these four methods, so tests can pass an
in-memory fake instead of a database (the repository pattern).
"""

import json
from datetime import date
from typing import Optional

from sqlalchemy import text

from summary.facts import RatingRow, month_bounds_utc


class PostgresStore:
    def __init__(self, engine):
        self.engine = engine

    def month_rows(self, year: int, month: int, until: Optional[date] = None) -> list[RatingRow]:
        start, end = month_bounds_utc(year, month, until)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT COALESCE(m.display_title, m.title) AS film, m.year, m.genre AS genres,
                           u.display_name AS who, r.score, r.comment
                    FROM ratings r
                    JOIN movies m ON m.id = r.movie_id
                    JOIN users u ON u.id = r.user_id
                    WHERE r.created_at >= :start AND r.created_at < :end
                    ORDER BY r.created_at
                """),
                {"start": start, "end": end},
            ).mappings().all()
        return [RatingRow(**row) for row in rows]

    def summary_exists(self, year: int, month: int) -> bool:
        with self.engine.connect() as conn:
            found = conn.execute(
                text("SELECT 1 FROM monthly_summaries WHERE month = :month"),
                {"month": date(year, month, 1)},
            ).first()
        return found is not None

    def previous_colour_texts(self, year: int, month: int, limit: int = 3) -> list[str]:
        """The last few texts Claude wrote, newest first, so it avoids repeating jokes."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT colour_text FROM monthly_summaries
                    WHERE month < :month AND colour_text IS NOT NULL
                    ORDER BY month DESC LIMIT :limit
                """),
                {"month": date(year, month, 1), "limit": limit},
            ).all()
        return [r.colour_text for r in rows]

    def save_summary(self, year: int, month: int, tier: str, generation, model: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO monthly_summaries
                        (month, tier, colour_text, full_message, used_fallback, attempts,
                         validation_errors, model, input_tokens, output_tokens)
                    VALUES (:month, :tier, :colour_text, :full_message, :used_fallback, :attempts,
                            CAST(:errors AS JSONB), :model, :input_tokens, :output_tokens)
                """),
                {
                    "month": date(year, month, 1),
                    "tier": tier,
                    "colour_text": generation.colour_text,
                    "full_message": generation.full_message,
                    "used_fallback": generation.used_fallback,
                    "attempts": generation.attempts,
                    "errors": json.dumps(generation.errors, ensure_ascii=False),
                    "model": model,
                    "input_tokens": generation.input_tokens,
                    "output_tokens": generation.output_tokens,
                },
            )
