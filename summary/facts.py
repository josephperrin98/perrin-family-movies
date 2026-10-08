"""
Facts for the monthly summary: plain Python, no database, no AI.

Everything the family reads as a number comes from here, so it can be tested
exhaustively and never invented by the model.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean
from typing import Optional
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

# The family's shared film culture: Claude may quote these in any month
FAMILY_CLASSICS = [
    "OSS 117",
    "Astérix & Obélix : Mission Cléopâtre",
    "Le Prénom",
    "La grande bellezza",
    "Notte prima degli esami",
]


@dataclass(frozen=True)
class RatingRow:
    film: str
    year: Optional[str]
    genres: Optional[str]
    who: str
    score: float
    comment: Optional[str]


@dataclass(frozen=True)
class FilmScore:
    film: str
    average: float
    raters: int


@dataclass
class MonthFacts:
    year: int
    month: int
    tier: str
    rows: list[RatingRow]
    count: int
    average: Optional[float]
    favourite_genre: Optional[str]
    best: list[FilmScore]
    worst: list[FilmScore]
    ranking: list[tuple[str, int]]
    previous_count: int
    previous_average: Optional[float]
    until: Optional[date] = None  # set when the period runs past the month's end

    @property
    def films(self) -> set[str]:
        return {r.film for r in self.rows}

    @property
    def people(self) -> set[str]:
        return {r.who for r in self.rows}


def month_before(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def paris_midnight_utc(day: date) -> datetime:
    """Midnight in Paris on that day, as a naive UTC datetime, because
    ratings.created_at is a TIMESTAMP without time zone written in UTC."""
    moment = datetime(day.year, day.month, day.day, tzinfo=PARIS)
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def month_bounds_utc(year: int, month: int, until: Optional[date] = None) -> tuple[datetime, datetime]:
    """[1st 00:00, next 1st 00:00) in Paris time, or [1st 00:00, until 00:00)."""
    end = until or date(year + month // 12, month % 12 + 1, 1)
    return paris_midnight_utc(date(year, month, 1)), paris_midnight_utc(end)


def tier_for(count: int) -> str:
    if count == 0:
        return "aucun"
    if count <= 5:
        return "leger"
    return "complet"


def round1(value: float) -> float:
    """Round to one decimal, halves up (6.25 -> 6.3), as people expect.
    Python's round() rounds halves to even and gives 6.2."""
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _average(rows: list[RatingRow]) -> Optional[float]:
    return round1(mean(r.score for r in rows)) if rows else None


def _film_scores(rows: list[RatingRow]) -> list[FilmScore]:
    by_film: dict[str, list[float]] = {}
    for r in rows:
        by_film.setdefault(r.film, []).append(r.score)
    return [FilmScore(film, round1(mean(s)), len(s)) for film, s in by_film.items()]


def _favourite_genre(rows: list[RatingRow]) -> Optional[str]:
    genres = Counter(g.strip() for r in rows if r.genres for g in r.genres.split(","))
    if not genres:
        return None
    top = max(genres.values())
    return min(g for g, n in genres.items() if n == top)


def compute_facts(year: int, month: int, rows: list[RatingRow], previous_rows: list[RatingRow],
                  until: Optional[date] = None) -> MonthFacts:
    scores = _film_scores(rows)
    best = sorted(scores, key=lambda s: (-s.average, s.film))[:3]
    worst = sorted((s for s in scores if s not in best), key=lambda s: (s.average, s.film))[:3]
    ranking = sorted(Counter(r.who for r in rows).items(), key=lambda kv: (-kv[1], kv[0]))
    return MonthFacts(
        year=year,
        month=month,
        tier=tier_for(len(rows)),
        rows=rows,
        count=len(rows),
        average=_average(rows),
        favourite_genre=_favourite_genre(rows),
        best=best,
        worst=worst,
        ranking=ranking,
        previous_count=len(previous_rows),
        previous_average=_average(previous_rows),
        until=until,
    )
