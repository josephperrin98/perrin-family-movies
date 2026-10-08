# Monthly Family Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Email Joseph a short, funny French summary of the family's monthly film ratings, with a one-tap WhatsApp link — sent by hand for September 2026 today, then automatically on the 1st of each month.

**Architecture:** A GitHub Actions cron runs `scripts/send_monthly_summary.py`. Pure-Python modules compute the facts and render the factual bullets; one module (`writer.py`) asks Claude for the "colour" text through structured output; `validate.py` checks it, with up to two retries and an AI-free fallback. A `Store` class wraps every SQL query so the orchestration can be tested with an in-memory fake.

**Tech Stack:** Python 3.11, SQLAlchemy Core + psycopg 3 (existing), `anthropic` 1.12.1 (new, brings `pydantic`), standard library for everything else (`zoneinfo`, `difflib`, `smtplib`, `email`, `urllib.parse`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-10-07-monthly-summary-design.md`

## Global Constraints

- Ratings count for a month when `ratings.created_at` is in `[1st 00:00, next 1st 00:00)` Europe/Paris; `created_at` is a naive UTC `TIMESTAMP`.
- Titles in facts: `COALESCE(movies.display_title, movies.title)`. Claude never translates titles.
- Code writes every number; the colour text must contain no digits outside «…».
- Tiers: 0 ratings → `aucun`, 1–5 → `leger`, 6+ → `complet`.
- Colour length (characters): `aucun` 80–400, `leger` 150–500, `complet` 300–900.
- Similarity limit against each of the last 3 colour texts: `difflib.SequenceMatcher` ratio < 0.6.
- Max 3 attempts (1 + 2 retries), then the AI-free fallback.
- Model from env `SUMMARY_MODEL`, default `claude-opus-5-5`; `output_config={"effort": "medium"}`.
- Email subject: `Résumé Perrin-rama: Sept'26` (abbreviations Janv, Févr, Mars, Avr, Mai, Juin, Juil, Août, Sept, Oct, Nov, Déc).
- Cron `17 12 1 * *`.
- The repo is public: workflow logs must never contain family names, titles or comments (`PUBLIC_LOGS=true`).
- Dependencies pinned to exact versions. Tests use `unittest`, need no network or database, run with `.venv/bin/python -m unittest`.
- Conventional Commits, one feature per commit, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Commits need `ussh` first (global Uber pre-commit hook); never bypass it.

## Decisions taken while planning

- **`summary/store.py` (new, not in the spec's module list):** all SQL in one class. `service.run_month` receives a store object, so tests pass an in-memory fake. This is the *repository pattern*.
- **Server-side refusal fallback not used.** The Claude API offers a `fallbacks` parameter that re-runs a refused request on another model. We don't need it: a refusal already lands in our own deterministic fallback, and family film comments are very unlikely to trigger one.
- **The eval measures the first attempt only (no retries).** Retries hide prompt weaknesses; the first-attempt pass rate is the honest quality metric.
- **Similarity test:** the spec mentioned ratios of 0.59 and 0.61; crafting exact ratios is brittle, so the tests use a near-copy (fails) and a different text (passes) instead.

## Amendment: the first send covers September + early October

September 2026 has no ratings, so the first email covers 1 September up to
the day of sending. This adds one optional value, `until` (a `date`,
exclusive end at Paris midnight, later than the month's end), threaded through:

- `facts.paris_midnight_utc(d: date) -> datetime`; `month_bounds_utc` uses it.
- `MonthFacts.until: Optional[date] = None`; `compute_facts(..., until=None)`.
- `PostgresStore.month_rows(year, month, until=None)`.
- `render.period_label(year, month, until=None)` → `"septembre 2026"` or
  `"septembre et début octobre 2026"`; `subject(year, month, until=None)` →
  `"Résumé Perrin-rama: Sept'26"` or `"Résumé Perrin-rama: Sept-Oct'26"`;
  `fallback_colour(tier, label)` takes the label instead of year/month.
- `service.run_month(..., until=None)`; script flag `--until YYYY-MM-DD`.
- The database row is still keyed by the starting month (2026-09-01).

Known trade-off: the 1 November run summarises all of October, so the
ratings from 1–8 October appear twice. Accepted: it's four ratings, and
a period-overlap rule isn't worth its complexity.

## File map

| File | Responsibility |
|---|---|
| `requirements.txt` | + `anthropic`, `pydantic` pins |
| `database.py` | + `monthly_summaries` table in `init_db()` |
| `summary/facts.py` | dataclasses, month boundaries, tiers, `compute_facts` (pure) |
| `summary/store.py` | `PostgresStore`: month rows, summary exists, previous texts, save |
| `summary/render.py` | month labels, subject, French factual bullets, fallback sentences |
| `summary/validate.py` | automatic rubric → list of error strings |
| `summary/prompt_fr.txt` | system prompt (tuned in Task 10) |
| `summary/writer.py` | `Colour` schema, payload, the only Claude call |
| `summary/service.py` | `generate_message` (retry/fallback), `run_month` (orchestration) |
| `summary/delivery.py` | wa.me link, email building and sending |
| `scripts/send_monthly_summary.py` | thin CLI entry point |
| `evals/run_evals.py`, `evals/cases/{dev,holdout}/*.json` | eval harness and fake months |
| `.github/workflows/monthly-summary.yml` | cron + manual trigger |
| `tests/test_summary_*.py` | unit tests |

---

### Task 1: Dependency and `monthly_summaries` table

**Files:**
- Modify: `requirements.txt`
- Modify: `database.py` (inside `init_db()`, after the `display_title` ALTER)
- Modify: `tests/test_dependencies.py`

**Interfaces:**
- Produces: table `monthly_summaries` (columns per spec); importable `anthropic` and `pydantic`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_dependencies.py`:

```python
class TestSummaryDependencies(unittest.TestCase):
    def test_anthropic_sdk_is_v1(self):
        import anthropic
        self.assertTrue(anthropic.__version__.startswith("1."))
```

- [ ] **Step 2: Run it, expect FAIL** — `.venv/bin/python -m unittest tests.test_dependencies -v` → `ModuleNotFoundError: No module named 'anthropic'`.

- [ ] **Step 3: Install and pin.** Run `.venv/bin/pip install anthropic==1.12.1`, then `.venv/bin/pip show pydantic | grep Version` and add both lines to `requirements.txt` (pydantic at the exact version shown, because `writer.py` imports it directly):

```
anthropic==1.12.1
pydantic==<version from pip show>
```

- [ ] **Step 4: Add the table** in `database.py`, right after the `display_title` line:

```python
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
```

- [ ] **Step 5: Run all tests, expect PASS** — `.venv/bin/python -m unittest`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt database.py tests/test_dependencies.py
git commit -m "feat(backend): add anthropic SDK and monthly_summaries table"
```

---

### Task 2: Facts (pure computation)

**Files:**
- Create: `summary/facts.py`
- Test: `tests/test_summary_facts.py`

**Interfaces:**
- Produces:
  - `PARIS: ZoneInfo`
  - `RatingRow(film: str, year: Optional[str], genres: Optional[str], who: str, score: float, comment: Optional[str])` (frozen dataclass)
  - `FilmScore(film: str, average: float, raters: int)` (frozen dataclass)
  - `MonthFacts(year, month, tier, rows, count, average, favourite_genre, best, worst, ranking, previous_count, previous_average)` with properties `films: set[str]`, `people: set[str]`
  - `month_before(year: int, month: int) -> tuple[int, int]`
  - `month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]` (naive UTC)
  - `tier_for(count: int) -> str`
  - `compute_facts(year, month, rows, previous_rows) -> MonthFacts`

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_facts.py`:

```python
import unittest
from datetime import datetime

from summary.facts import RatingRow, compute_facts, month_before, month_bounds_utc, tier_for


def row(film, who, score, genres="Drama", comment=None):
    return RatingRow(film=film, year="2020", genres=genres, who=who, score=score, comment=comment)


class TestMonths(unittest.TestCase):
    def test_month_before(self):
        self.assertEqual(month_before(2026, 10), (2026, 9))
        self.assertEqual(month_before(2027, 1), (2026, 12))

    def test_summer_month_bounds(self):
        # Paris is UTC+2 in summer
        self.assertEqual(
            month_bounds_utc(2026, 9),
            (datetime(2026, 8, 31, 22, 0), datetime(2026, 9, 30, 22, 0)),
        )

    def test_month_with_daylight_saving_change(self):
        # Clocks go back on 25 Oct 2026: the month ends at UTC+1
        self.assertEqual(
            month_bounds_utc(2026, 10),
            (datetime(2026, 9, 30, 22, 0), datetime(2026, 10, 31, 23, 0)),
        )

    def test_december_rolls_into_next_year(self):
        self.assertEqual(month_bounds_utc(2026, 12)[1], datetime(2026, 12, 31, 23, 0))


class TestTiers(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(tier_for(0), "aucun")
        self.assertEqual(tier_for(1), "leger")
        self.assertEqual(tier_for(5), "leger")
        self.assertEqual(tier_for(6), "complet")


class TestComputeFacts(unittest.TestCase):
    def test_empty_month(self):
        facts = compute_facts(2026, 9, [], [row("A", "Bob", 8)])
        self.assertEqual(facts.tier, "aucun")
        self.assertEqual(facts.count, 0)
        self.assertIsNone(facts.average)
        self.assertEqual(facts.best, [])
        self.assertEqual(facts.previous_count, 1)

    def test_counts_average_and_ranking(self):
        rows = [row("A", "Bob", 8), row("B", "Bob", 6), row("A", "Alice", 9)]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual(facts.count, 3)
        self.assertEqual(facts.average, 7.7)
        self.assertEqual(facts.ranking, [("Bob", 2), ("Alice", 1)])
        self.assertEqual(facts.films, {"A", "B"})
        self.assertEqual(facts.people, {"Bob", "Alice"})

    def test_best_and_worst_use_film_averages_and_never_overlap(self):
        rows = [row(f, "Bob", s) for f, s in [("A", 9), ("B", 8), ("C", 7), ("D", 4)]]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual([s.film for s in facts.best], ["A", "B", "C"])
        self.assertEqual([s.film for s in facts.worst], ["D"])

    def test_ties_are_broken_by_title(self):
        rows = [row("Zorro", "Bob", 8), row("Amélie", "Bob", 8)]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual([s.film for s in facts.best], ["Amélie", "Zorro"])

    def test_favourite_genre_splits_multi_genre_strings(self):
        rows = [row("A", "Bob", 8, "Comedy, Romance"), row("B", "Bob", 7, "Comedy"), row("C", "Bob", 7, "Drama")]
        self.assertEqual(compute_facts(2026, 9, rows, []).favourite_genre, "Comedy")

    def test_no_genres(self):
        self.assertIsNone(compute_facts(2026, 9, [row("A", "Bob", 8, None)], []).favourite_genre)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_facts` → `ModuleNotFoundError: No module named 'summary.facts'`.

- [ ] **Step 3: Implement** — `summary/facts.py`:

```python
"""
Facts for the monthly summary: plain Python, no database, no AI.

Everything the family reads as a number comes from here, so it can be tested
exhaustively and never invented by the model.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Optional
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


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


def month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """[1st 00:00, next 1st 00:00) in Paris time, as naive UTC datetimes,
    because ratings.created_at is a TIMESTAMP without time zone written in UTC."""
    start = datetime(year, month, 1, tzinfo=PARIS)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=PARIS)
    return _naive_utc(start), _naive_utc(end)


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def tier_for(count: int) -> str:
    if count == 0:
        return "aucun"
    if count <= 5:
        return "leger"
    return "complet"


def _average(rows: list[RatingRow]) -> Optional[float]:
    return round(mean(r.score for r in rows), 1) if rows else None


def _film_scores(rows: list[RatingRow]) -> list[FilmScore]:
    by_film: dict[str, list[float]] = {}
    for r in rows:
        by_film.setdefault(r.film, []).append(r.score)
    return [FilmScore(film, round(mean(s), 1), len(s)) for film, s in by_film.items()]


def _favourite_genre(rows: list[RatingRow]) -> Optional[str]:
    genres = Counter(g.strip() for r in rows if r.genres for g in r.genres.split(","))
    if not genres:
        return None
    top = max(genres.values())
    return min(g for g, n in genres.items() if n == top)


def compute_facts(year: int, month: int, rows: list[RatingRow], previous_rows: list[RatingRow]) -> MonthFacts:
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
    )
```

- [ ] **Step 4: Run, expect PASS** — `.venv/bin/python -m unittest tests.test_summary_facts -v`.

- [ ] **Step 5: Commit**

```bash
git add summary/facts.py tests/test_summary_facts.py
git commit -m "feat(backend): compute monthly summary facts"
```

---

### Task 3: Store (all SQL for the summary)

**Files:**
- Create: `summary/store.py`
- Test: none automated (needs a database); verified by a read-only query in Step 3.

**Interfaces:**
- Consumes: `RatingRow`, `month_bounds_utc` (Task 2); table from Task 1.
- Produces: `PostgresStore(engine)` with
  - `month_rows(year, month) -> list[RatingRow]`
  - `summary_exists(year, month) -> bool`
  - `previous_colour_texts(year, month, limit=3) -> list[str]` (newest first)
  - `save_summary(year, month, tier, generation, model) -> None` where `generation` has `colour_text, full_message, used_fallback, attempts, errors, input_tokens, output_tokens` (Task 7)

- [ ] **Step 1: Implement** — `summary/store.py`:

```python
"""
Every SQL query the monthly summary needs, behind one small class.

service.run_month only calls these four methods, so tests can pass an
in-memory fake instead of a database (the repository pattern).
"""

import json
from datetime import date

from sqlalchemy import text

from summary.facts import RatingRow, month_bounds_utc


class PostgresStore:
    def __init__(self, engine):
        self.engine = engine

    def month_rows(self, year: int, month: int) -> list[RatingRow]:
        start, end = month_bounds_utc(year, month)
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
```

- [ ] **Step 2: Create the table** (adds `monthly_summaries`, idempotent): `.venv/bin/python -c "import database; database.init_db()"`

- [ ] **Step 3: Verify read-only against Neon** — expect 0 rows for September, 4+ for October, and `False`/`[]` for the new table:

```bash
.venv/bin/python -c "
import database
from summary.store import PostgresStore
s = PostgresStore(database.get_engine())
print(len(s.month_rows(2026, 9)), len(s.month_rows(2026, 10)))
print(s.summary_exists(2026, 9), s.previous_colour_texts(2026, 9))
"
```

- [ ] **Step 4: Commit**

```bash
git add summary/store.py
git commit -m "feat(backend): add summary store for ratings and sent summaries"
```

---

### Task 4: Render (French bullets, subject, fallback)

**Files:**
- Create: `summary/render.py`
- Test: `tests/test_summary_render.py`

**Interfaces:**
- Consumes: `MonthFacts`, `FilmScore`, `RatingRow`, `compute_facts` (Task 2)
- Produces:
  - `month_label(year, month) -> str` e.g. `"septembre 2026"`
  - `subject(year, month) -> str` e.g. `"Résumé Perrin-rama: Sept'26"`
  - `render_facts(facts: MonthFacts) -> str` (empty string for `aucun`)
  - `fallback_colour(tier: str, year: int, month: int) -> str`
  - `assemble(colour: str, facts_text: str) -> str`

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_render.py`:

```python
import unittest

from summary.facts import RatingRow, compute_facts
from summary.render import (
    MONTH_ABBR, assemble, fallback_colour, month_label, render_facts, subject,
)


def row(film, who, score, genres="Comedy"):
    return RatingRow(film=film, year="2020", genres=genres, who=who, score=score, comment=None)


class TestLabels(unittest.TestCase):
    def test_subject(self):
        self.assertEqual(subject(2026, 9), "Résumé Perrin-rama: Sept'26")
        self.assertEqual(subject(2027, 1), "Résumé Perrin-rama: Janv'27")

    def test_twelve_abbreviations(self):
        self.assertEqual(
            MONTH_ABBR,
            ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"],
        )

    def test_month_label(self):
        self.assertEqual(month_label(2026, 8), "août 2026")


class TestRenderFacts(unittest.TestCase):
    def test_empty_month_has_no_bullets(self):
        self.assertEqual(render_facts(compute_facts(2026, 9, [], [])), "")

    def test_light_month_lists_each_rating(self):
        text = render_facts(compute_facts(2026, 9, [row("Le Daim", "Chloé", 8.5)], []))
        self.assertIn("1 note", text)
        self.assertIn("«Le Daim» — Chloé 8,5", text)

    def test_full_month(self):
        rows = [row(f"Film {c}", who, s) for c, who, s in [
            ("A", "Bob", 9), ("B", "Bob", 8), ("C", "Alice", 7.5),
            ("D", "Alice", 6), ("E", "Chloé", 4), ("F", "Bob", 3),
        ]]
        text = render_facts(compute_facts(2026, 9, rows, []))
        self.assertIn("6 notes · moyenne 6,3/10", text)
        self.assertIn("Bob (3)", text)
        self.assertIn("🥇 «Film A» — 9,0", text)
        self.assertIn("«Film F» — 3,0", text)
        self.assertIn("Comédie", text)  # genres are translated


class TestFallbackAndAssemble(unittest.TestCase):
    def test_fallback_exists_for_every_tier(self):
        for tier in ("aucun", "leger", "complet"):
            self.assertIn("septembre", fallback_colour(tier, 2026, 9))

    def test_assemble_skips_empty_parts(self):
        self.assertEqual(assemble("Salut 🎬", ""), "Salut 🎬")
        self.assertEqual(assemble("Salut", "• x"), "Salut\n\n• x")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_render` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `summary/render.py`:

```python
"""
Everything in the summary that is written by code, not by Claude: the
factual bullets, the email subject, and the AI-free fallback sentences.
"""

from summary.facts import MonthFacts

MONTH_NAMES = ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MONTH_ABBR = ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin",
              "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]
MEDALS = ["🥇", "🥈", "🥉"]

# OMDb's genre list, in French
GENRES_FR = {
    "Action": "Action", "Adventure": "Aventure", "Animation": "Animation",
    "Biography": "Biopic", "Comedy": "Comédie", "Crime": "Policier",
    "Documentary": "Documentaire", "Drama": "Drame", "Family": "Famille",
    "Fantasy": "Fantastique", "Film-Noir": "Film noir", "History": "Histoire",
    "Horror": "Horreur", "Music": "Musique", "Musical": "Comédie musicale",
    "Mystery": "Mystère", "Romance": "Romance", "Sci-Fi": "Science-fiction",
    "Short": "Court métrage", "Sport": "Sport", "Thriller": "Thriller",
    "War": "Guerre", "Western": "Western",
}


def month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month - 1]} {year}"


def subject(year: int, month: int) -> str:
    return f"Résumé Perrin-rama: {MONTH_ABBR[month - 1]}'{year % 100:02d}"


def fr_number(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _notes(count: int) -> str:
    return f"{count} note" if count == 1 else f"{count} notes"


def render_facts(facts: MonthFacts) -> str:
    if facts.tier == "aucun":
        return ""
    lines = [f"🎬 {_notes(facts.count)} · moyenne {fr_number(facts.average)}/10"]
    if facts.tier == "leger":
        lines += [f"• «{r.film}» — {r.who} {fr_number(r.score)}" for r in facts.rows]
        return "\n".join(lines)

    lines.append("🏆 Les plus assidus : " + ", ".join(f"{who} ({n})" for who, n in facts.ranking))
    lines.append("\n👍 Top 3")
    lines += [f"{MEDALS[i]} «{s.film}» — {fr_number(s.average)}" for i, s in enumerate(facts.best)]
    if facts.worst:
        lines.append("\n👎 Flop")
        lines += [f"• «{s.film}» — {fr_number(s.average)}" for s in facts.worst]
    if facts.favourite_genre:
        genre = GENRES_FR.get(facts.favourite_genre, facts.favourite_genre)
        lines.append(f"\n🎭 Genre du mois : {genre}")
    return "\n".join(lines)


def fallback_colour(tier: str, year: int, month: int) -> str:
    label = month_label(year, month)
    if tier == "aucun":
        return f"🎬 Aucun film noté en {label} ! Vous avez regardé quoi ? Notez-les dans l'appli 🍿"
    if tier == "leger":
        return f"🍿 Petit mois cinéma en {label}. Qui a un film à recommander ?"
    return f"🎬 Gros mois cinéma en {label} ! Voici le bilan. Et vous, votre coup de cœur ?"


def assemble(colour: str, facts_text: str) -> str:
    return "\n\n".join(part for part in (colour, facts_text) if part)
```

- [ ] **Step 4: Run, expect PASS** — `.venv/bin/python -m unittest tests.test_summary_render -v`.

- [ ] **Step 5: Commit**

```bash
git add summary/render.py tests/test_summary_render.py
git commit -m "feat(backend): render summary bullets, subject and fallback"
```

---

### Task 5: Validation (the automatic rubric)

**Files:**
- Create: `summary/validate.py`
- Test: `tests/test_summary_validate.py`

**Interfaces:**
- Consumes: `MonthFacts`, `compute_facts`, `RatingRow` (Task 2). A "colour" is any object with `message: str`, `titles_mentioned: list[str]`, `names_mentioned: list[str]` (the pydantic `Colour` from Task 6 satisfies it; tests use a dataclass so this task doesn't depend on Task 6).
- Produces: `validate(colour, facts, previous_texts: list[str]) -> list[str]` (French error messages, empty if valid); `quoted_titles(text) -> list[str]`; constants `LENGTH`, `SIMILARITY_LIMIT`.

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_validate.py`:

```python
import unittest
from dataclasses import dataclass, field

from summary.facts import RatingRow, compute_facts
from summary.validate import quoted_titles, validate


@dataclass
class FakeColour:
    message: str
    titles_mentioned: list = field(default_factory=list)
    names_mentioned: list = field(default_factory=list)


def light_month():
    rows = [RatingRow("Blade Runner 2049", "2017", "Sci-Fi", "Chloé", 8.5, "Trop long"),
            RatingRow("Le Daim", "2019", "Comedy", "Bob", 6.0, None)]
    return compute_facts(2026, 9, rows, [])


GOOD = ("Ce mois-ci, Chloé a plongé dans «Blade Runner 2049» pendant que Bob "
        "se battait avec «Le Daim» et son blouson 🧥. Spoiler : personne n'a compris "
        "la fin. Qui ose le revoir avec lui ?")


class TestQuotedTitles(unittest.TestCase):
    def test_extracts_titles_and_trims_spaces(self):
        self.assertEqual(quoted_titles("Vu « Le Daim » et «Tenet»"), ["Le Daim", "Tenet"])


class TestValidate(unittest.TestCase):
    def check(self, message, titles=None, names=None, facts=None, previous=()):
        colour = FakeColour(message, titles if titles is not None else quoted_titles(message), names or [])
        return validate(colour, facts or light_month(), list(previous))

    def test_good_message_passes(self):
        self.assertEqual(self.check(GOOD, names=["Chloé", "Bob"]), [])

    def test_unknown_title_fails(self):
        errors = self.check(GOOD.replace("«Le Daim»", "«Le Cerf»"))
        self.assertTrue(any("Le Cerf" in e for e in errors))

    def test_titles_compared_case_insensitively(self):
        self.assertEqual(self.check(GOOD.replace("«Le Daim»", "«le daim»")), [])

    def test_unknown_name_fails(self):
        errors = self.check(GOOD, names=["Chloé", "Mamie"])
        self.assertTrue(any("Mamie" in e for e in errors))

    def test_self_declared_titles_must_match_text(self):
        errors = self.check(GOOD, titles=["Blade Runner 2049"])
        self.assertTrue(any("titles_mentioned" in e for e in errors))

    def test_digits_inside_titles_are_allowed_but_not_outside(self):
        errors = self.check(GOOD.replace("Ce mois-ci", "Avec 2 films"))
        self.assertTrue(any("chiffre" in e for e in errors))

    def test_length_range(self):
        errors = self.check("Trop court 🎬 ?")
        self.assertTrue(any("Longueur" in e for e in errors))

    def test_needs_emoji_and_question(self):
        errors = self.check(GOOD.replace("🧥", "").replace("?", "."))
        self.assertTrue(any("emoji" in e for e in errors))
        self.assertTrue(any("question" in e for e in errors))

    def test_near_copy_of_previous_summary_fails(self):
        errors = self.check(GOOD, previous=[GOOD.replace("Bob", "Bobby")])
        self.assertTrue(any("précédent" in e for e in errors))

    def test_different_previous_summary_passes(self):
        other = "Rien à voir : un mois de comédies musicales et de pop-corn brûlé 🍿, qui chante ?"
        self.assertEqual(self.check(GOOD, previous=[other]), [])

    def test_empty_month_must_not_quote_titles(self):
        empty = compute_facts(2026, 9, [], [])
        message = "Septembre sans film ? La télé a fait grève 📺 ! Racontez-nous ce que vous avez regardé, même «Tenet»."
        errors = self.check(message, facts=empty)
        self.assertTrue(any("Aucun film" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_validate` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `summary/validate.py`:

```python
"""
Automatic checks on Claude's colour text (the code half of the rubric).

Used twice: in production before anything is emailed, and offline by the
eval harness to score prompt versions. Errors are written in French because
they are sent back to Claude when it gets a second attempt.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from summary.facts import MonthFacts

LENGTH = {"aucun": (80, 400), "leger": (150, 500), "complet": (300, 900)}
SIMILARITY_LIMIT = 0.6
QUOTED = re.compile(r"«\s*(.+?)\s*»")


def quoted_titles(text: str) -> list[str]:
    return QUOTED.findall(text)


def has_emoji(text: str) -> bool:
    return any(unicodedata.category(c) == "So" for c in text)


def validate(colour, facts: MonthFacts, previous_texts: list[str]) -> list[str]:
    errors = []
    message = colour.message
    quoted = quoted_titles(message)
    known_titles = {t.lower() for t in facts.films}

    if facts.tier == "aucun" and quoted:
        errors.append("Aucun film ce mois-ci : ne cite aucun titre entre « ».")
    for title in quoted:
        if title.lower() not in known_titles:
            errors.append(f"Titre inconnu : «{title}». Recopie exactement un titre des données.")
    if {t.lower() for t in colour.titles_mentioned} != {t.lower() for t in quoted}:
        errors.append("titles_mentioned doit lister exactement les titres écrits entre « ».")
    for name in colour.names_mentioned:
        if name not in facts.people:
            errors.append(f"Prénom inconnu : {name}. Cite uniquement les personnes des données.")

    if re.search(r"\d", QUOTED.sub("", message)):
        errors.append("N'écris aucun chiffre en dehors des titres : les chiffres sont déjà dans le résumé.")
    low, high = LENGTH[facts.tier]
    if not low <= len(message) <= high:
        errors.append(f"Longueur {len(message)} caractères : vise entre {low} et {high}.")
    if not has_emoji(message):
        errors.append("Ajoute au moins un emoji.")
    if "?" not in message:
        errors.append("Termine par une question qui donne envie d'en parler.")

    for previous in previous_texts:
        if SequenceMatcher(None, message, previous).ratio() >= SIMILARITY_LIMIT:
            errors.append("Trop proche d'un résumé précédent : change d'angle et de blagues.")
            break
    return errors
```

- [ ] **Step 4: Run, expect PASS** — `.venv/bin/python -m unittest tests.test_summary_validate -v`. If `test_good_message_passes` fails on length, `GOOD` is outside 150–500: adjust the test sentence, not the limits.

- [ ] **Step 5: Commit**

```bash
git add summary/validate.py tests/test_summary_validate.py
git commit -m "feat(backend): validate summary colour text against the rubric"
```

---

### Task 6: Writer (the only Claude call) and the prompt

**Files:**
- Create: `summary/prompt_fr.txt`
- Create: `summary/writer.py`
- Test: `tests/test_summary_writer.py`

**Interfaces:**
- Consumes: `MonthFacts` (Task 2), `month_label` (Task 4)
- Produces:
  - `Colour(BaseModel)`: `message: str`, `titles_mentioned: list[str]`, `names_mentioned: list[str]`
  - `WriterResult(colour: Optional[Colour], input_tokens: int, output_tokens: int)`
  - `WriterError(Exception)`
  - `build_payload(facts, previous_texts) -> dict`
  - `build_user_content(payload, feedback: Optional[tuple[str, list[str]]]) -> str`
  - `write_colour(client, model, payload, feedback=None) -> WriterResult`

- [ ] **Step 1: Write the prompt** — `summary/prompt_fr.txt` (version 1; Task 10 tunes it):

```
Tu écris le petit mot d'ouverture du résumé cinéma mensuel de la famille Perrin, envoyé dans leur groupe WhatsApp.

Tu reçois en JSON les notes du mois. Les chiffres, classements, top et flop sont déjà affichés sous ton texte par ailleurs : ton rôle est d'apporter de la chaleur, de l'humour et une envie d'en parler.

Règles strictes :
- N'écris aucun chiffre (ni note, ni nombre de films, ni année), sauf s'il fait partie d'un titre.
- Ne parle que des films, des personnes et des commentaires fournis. N'invente aucun fait.
- Écris chaque titre entre « », recopié exactement comme dans le champ "film", sans le traduire.
- Utilise uniquement les prénoms du champ "qui".
- Mets quelques emojis.
- Termine par une question qui donne envie de répondre dans le groupe.
- Ne réutilise ni les blagues ni les tournures des textes de "deja_ecrit".

Selon le "palier" :
- "aucun" : aucun film noté ce mois-ci. Une blague bienveillante et une relance pour qu'ils notent ce qu'ils ont regardé. Ne cite aucun titre. Entre 80 et 400 caractères.
- "leger" : quelques notes. Un texte court et complice. Entre 150 et 500 caractères.
- "complet" : un vrai mois cinéma. Une tendance, un thème, une anecdote tirée d'un commentaire. Entre 300 et 900 caractères.

Remplis aussi "titles_mentioned" (les titres que tu as écrits entre « ») et "names_mentioned" (les prénoms que tu as cités).
```

- [ ] **Step 2: Write the failing tests** — `tests/test_summary_writer.py`. The Claude client is a `mock.Mock`, so no network and no cost:

```python
import json
import unittest
from unittest import mock

import anthropic
import httpx2 as httpx

from summary.facts import RatingRow, compute_facts
from summary.writer import Colour, WriterError, build_payload, build_user_content, write_colour


def facts():
    rows = [RatingRow("Le Daim", "2019", "Comedy", "Bob", 6.0, "Le blouson !")]
    return compute_facts(2026, 9, rows, [])


def fake_response(colour, stop_reason="end_turn"):
    usage = mock.Mock(input_tokens=1200, output_tokens=300)
    return mock.Mock(parsed_output=colour, stop_reason=stop_reason, usage=usage)


class TestPayload(unittest.TestCase):
    def test_payload_shape(self):
        payload = build_payload(facts(), ["texte d'août"])
        self.assertEqual(payload["mois"], "septembre 2026")
        self.assertEqual(payload["palier"], "leger")
        self.assertEqual(payload["notes"][0]["qui"], "Bob")
        self.assertEqual(payload["notes"][0]["commentaire"], "Le blouson !")
        self.assertEqual(payload["deja_ecrit"], ["texte d'août"])

    def test_feedback_is_appended(self):
        content = build_user_content({"mois": "septembre 2026"}, ("brouillon", ["Ajoute au moins un emoji."]))
        self.assertIn('"mois": "septembre 2026"', content)
        self.assertIn("brouillon", content)
        self.assertIn("- Ajoute au moins un emoji.", content)

    def test_payload_is_sent_as_readable_json(self):
        content = build_user_content(build_payload(facts(), []), None)
        self.assertEqual(json.loads(content)["notes"][0]["film"], "Le Daim")


class TestWriteColour(unittest.TestCase):
    def test_returns_parsed_colour_and_tokens(self):
        colour = Colour(message="Salut 🎬 ?", titles_mentioned=[], names_mentioned=[])
        client = mock.Mock()
        client.messages.parse.return_value = fake_response(colour)
        result = write_colour(client, "claude-opus-5-5", {"mois": "x"})
        self.assertEqual(result.colour, colour)
        self.assertEqual((result.input_tokens, result.output_tokens), (1200, 300))
        kwargs = client.messages.parse.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertIs(kwargs["output_format"], Colour)
        self.assertEqual(kwargs["output_config"], {"effort": "medium"})

    def test_refusal_gives_no_colour(self):
        client = mock.Mock()
        client.messages.parse.return_value = fake_response(None, stop_reason="refusal")
        self.assertIsNone(write_colour(client, "m", {}).colour)

    def test_api_error_becomes_writer_error(self):
        client = mock.Mock()
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        client.messages.parse.side_effect = anthropic.APIConnectionError(request=request)
        with self.assertRaises(WriterError):
            write_colour(client, "m", {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_writer` → `ModuleNotFoundError: No module named 'summary.writer'`. (If instead `import httpx2` fails, the installed SDK uses `httpx`: change that import to `import httpx`.)

- [ ] **Step 4: Implement** — `summary/writer.py`:

```python
"""
The only module that talks to Claude.

Claude writes the "colour" (the funny opening text) as structured output: a
free-text message plus the titles and names it says it used, so validate.py
can check them. Everything factual is written by code elsewhere.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic
import pydantic
from pydantic import BaseModel

from summary.facts import MonthFacts
from summary.render import month_label

PROMPT_PATH = Path(__file__).with_name("prompt_fr.txt")
MAX_TOKENS = 8000  # a ceiling, not a cost: thinking tokens count toward it


class Colour(BaseModel):
    message: str
    titles_mentioned: list[str]
    names_mentioned: list[str]


@dataclass
class WriterResult:
    colour: Optional[Colour]  # None when the model refused or the output was unusable
    input_tokens: int
    output_tokens: int


class WriterError(Exception):
    """The API couldn't be reached, even after the SDK's own retries."""


def build_payload(facts: MonthFacts, previous_texts: list[str]) -> dict:
    return {
        "mois": month_label(facts.year, facts.month),
        "palier": facts.tier,
        "notes": [
            {"film": r.film, "annee": r.year, "genres": r.genres,
             "qui": r.who, "note": r.score, "commentaire": r.comment}
            for r in facts.rows
        ],
        "faits": {
            "nb_notes": facts.count,
            "moyenne": facts.average,
            "genre_favori": facts.favourite_genre,
            "meilleurs": [s.film for s in facts.best],
            "pires": [s.film for s in facts.worst],
            "classement": [{"qui": who, "nb_notes": n} for who, n in facts.ranking],
        },
        "mois_precedent": {"nb_notes": facts.previous_count, "moyenne": facts.previous_average},
        "deja_ecrit": previous_texts,
    }


def build_user_content(payload: dict, feedback: Optional[tuple[str, list[str]]]) -> str:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if feedback:
        draft, errors = feedback
        content += (
            "\n\nTon brouillon précédent :\n" + draft
            + "\n\nCorrige exactement ceci :\n" + "\n".join(f"- {e}" for e in errors)
        )
    return content


def write_colour(client, model: str, payload: dict,
                 feedback: Optional[tuple[str, list[str]]] = None) -> WriterResult:
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=PROMPT_PATH.read_text(encoding="utf-8"),
            messages=[{"role": "user", "content": build_user_content(payload, feedback)}],
            output_format=Colour,
            output_config={"effort": "medium"},
        )
    except anthropic.APIError as e:
        raise WriterError(str(e)) from e
    except pydantic.ValidationError:
        # Output cut off or malformed: count it as an unusable attempt
        return WriterResult(None, 0, 0)
    colour = None if response.stop_reason == "refusal" else response.parsed_output
    return WriterResult(colour, response.usage.input_tokens, response.usage.output_tokens)
```

- [ ] **Step 5: Run, expect PASS** — `.venv/bin/python -m unittest tests.test_summary_writer -v`.

- [ ] **Step 6: Commit**

```bash
git add summary/prompt_fr.txt summary/writer.py tests/test_summary_writer.py
git commit -m "feat(backend): ask Claude for the summary colour text"
```

---

### Task 7: Service — retry, fallback and orchestration

**Files:**
- Create: `summary/service.py`
- Test: `tests/test_summary_service.py`

**Interfaces:**
- Consumes: `compute_facts`, `month_before` (Task 2); store methods (Task 3); `render_facts`, `fallback_colour`, `assemble`, `subject` (Task 4); `validate` (Task 5); `build_payload`, `WriterResult`, `WriterError` (Task 6).
- Produces:
  - `Generation(colour_text, full_message, used_fallback, attempts, errors, input_tokens, output_tokens)`
  - `RunOutcome(status: str, subject: str, generation: Optional[Generation])`, status in `"already_sent" | "dry_run" | "sent"`
  - `generate_message(facts, previous_texts, write) -> Generation` where `write(payload, feedback) -> WriterResult`
  - `run_month(store, year, month, write, send, model, dry_run=False) -> RunOutcome` where `send(subject, message) -> None`
  - `MAX_ATTEMPTS = 3`

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_service.py`:

```python
import unittest

from summary.delivery import MAX_MESSAGE_CHARS
from summary.facts import RatingRow, compute_facts
from summary.service import MAX_ATTEMPTS, generate_message, run_month
from summary.writer import Colour, WriterError, WriterResult

GOOD = ("Ce mois-ci, Chloé a plongé dans «Le Daim» et en est ressortie avec "
        "une soudaine envie de blouson en daim 🧥. Le reste de la famille jure qu'il "
        "n'en portera jamais. Qui l'accompagne au prochain ?")
BAD = "Trop court ?"


def facts():
    return compute_facts(2026, 9, [RatingRow("Le Daim", "2019", "Comedy", "Chloé", 8.0, None)], [])


def writer(*messages):
    """Fake writer returning the given messages in order; records the feedback it got."""
    calls = []

    def write(payload, feedback):
        calls.append(feedback)
        message = messages[len(calls) - 1]
        if isinstance(message, Exception):
            raise message
        colour = None if message is None else Colour(
            message=message, titles_mentioned=["Le Daim"] if "«" in message else [], names_mentioned=[])
        return WriterResult(colour, 1000, 200)

    write.calls = calls
    return write


class TestGenerateMessage(unittest.TestCase):
    def test_first_attempt_passes(self):
        result = generate_message(facts(), [], writer(GOOD))
        self.assertFalse(result.used_fallback)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.colour_text, GOOD)
        self.assertTrue(result.full_message.startswith(GOOD))
        self.assertIn("«Le Daim» — Chloé 8,0", result.full_message)

    def test_retry_sends_draft_and_errors_back(self):
        write = writer(BAD, GOOD)
        result = generate_message(facts(), [], write)
        self.assertEqual(result.attempts, 2)
        self.assertIsNone(write.calls[0])
        draft, errors = write.calls[1]
        self.assertEqual(draft, BAD)
        self.assertTrue(errors)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual((result.input_tokens, result.output_tokens), (2000, 400))

    def test_three_failures_fall_back(self):
        result = generate_message(facts(), [], writer(BAD, BAD, BAD))
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.attempts, MAX_ATTEMPTS)
        self.assertIsNone(result.colour_text)
        self.assertIn("septembre 2026", result.full_message)
        self.assertEqual(len(result.errors), 3)

    def test_refusal_counts_as_a_failed_attempt(self):
        result = generate_message(facts(), [], writer(None, GOOD))
        self.assertEqual(result.attempts, 2)
        self.assertFalse(result.used_fallback)

    def test_api_error_falls_back_immediately(self):
        result = generate_message(facts(), [], writer(WriterError("down")))
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.attempts, 1)

    def test_biggest_message_fits_in_a_whatsapp_link(self):
        rows = [RatingRow(f"Un titre de film assez long numéro {i}", "2020", "Comedy, Drama",
                          f"Personne{i % 6}", 5 + i % 5, None) for i in range(30)]
        big = compute_facts(2026, 9, rows, [])
        colour = "x" * 900
        result = generate_message(big, [], lambda payload, feedback: WriterResult(
            Colour(message=colour, titles_mentioned=[], names_mentioned=[]), 0, 0))
        self.assertLessEqual(len(result.full_message), MAX_MESSAGE_CHARS)


class FakeStore:
    def __init__(self, rows=(), sent=False):
        self.rows, self.sent, self.saved = list(rows), sent, []

    def month_rows(self, year, month):
        return self.rows if (year, month) == (2026, 9) else []

    def summary_exists(self, year, month):
        return self.sent

    def previous_colour_texts(self, year, month, limit=3):
        return []

    def save_summary(self, year, month, tier, generation, model):
        self.saved.append((year, month, tier, model))


class TestRunMonth(unittest.TestCase):
    def setUp(self):
        self.emails = []
        self.send = lambda subject, message: self.emails.append((subject, message))
        self.rows = [RatingRow("Le Daim", "2019", "Comedy", "Chloé", 8.0, None)]

    def test_sends_then_saves(self):
        store = FakeStore(self.rows)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "claude-opus-5-5")
        self.assertEqual(outcome.status, "sent")
        self.assertEqual(self.emails[0][0], "Résumé Perrin-rama: Sept'26")
        self.assertEqual(store.saved, [(2026, 9, "leger", "claude-opus-5-5")])

    def test_already_sent_month_does_nothing(self):
        store = FakeStore(self.rows, sent=True)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "m")
        self.assertEqual(outcome.status, "already_sent")
        self.assertEqual((self.emails, store.saved), ([], []))

    def test_dry_run_neither_sends_nor_saves(self):
        store = FakeStore(self.rows, sent=True)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "m", dry_run=True)
        self.assertEqual(outcome.status, "dry_run")
        self.assertEqual((self.emails, store.saved), ([], []))

    def test_failed_email_saves_nothing(self):
        store = FakeStore(self.rows)

        def broken_send(subject, message):
            raise OSError("SMTP down")

        with self.assertRaises(OSError):
            run_month(store, 2026, 9, writer(GOOD), broken_send, "m")
        self.assertEqual(store.saved, [])


if __name__ == "__main__":
    unittest.main()
```

Note: this test imports `MAX_MESSAGE_CHARS` from `summary.delivery`; create that constant now so this task stands alone: `summary/delivery.py` containing only `MAX_MESSAGE_CHARS = 1500  # checked on a phone during the first live send` (Task 8 adds the rest).

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_service` → `ModuleNotFoundError: No module named 'summary.service'`.

- [ ] **Step 3: Implement** — `summary/service.py`:

```python
"""
Monthly summary orchestration: facts -> Claude -> checks -> retry -> email -> store.

The writer, the email sender and the store are passed in (dependency
injection), so every path, including failures, is tested without network,
database or cost.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from summary.facts import MonthFacts, compute_facts, month_before
from summary.render import assemble, fallback_colour, render_facts, subject
from summary.validate import validate
from summary.writer import WriterError, WriterResult, build_payload

MAX_ATTEMPTS = 3  # first try + 2 retries

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
    errors_log: list[list[str]] = []
    tokens_in = tokens_out = 0
    feedback = None
    attempts = 0

    for attempts in range(1, MAX_ATTEMPTS + 1):
        try:
            result = write(payload, feedback)
        except WriterError as e:
            errors_log.append([f"API indisponible : {e}"])
            break
        tokens_in += result.input_tokens
        tokens_out += result.output_tokens
        if result.colour is None:
            errors_log.append(["Réponse inexploitable (refus ou sortie incomplète)."])
            continue
        errors = validate(result.colour, facts, previous_texts)
        if not errors:
            message = result.colour.message
            return Generation(message, assemble(message, facts_text), False, attempts,
                              errors_log, tokens_in, tokens_out)
        errors_log.append(errors)
        feedback = (result.colour.message, errors)

    fallback = fallback_colour(facts.tier, facts.year, facts.month)
    return Generation(None, assemble(fallback, facts_text), True, attempts,
                      errors_log, tokens_in, tokens_out)


def run_month(store, year: int, month: int, write: Writer,
              send: Callable[[str, str], None], model: str, dry_run: bool = False) -> RunOutcome:
    """Build the month's summary and email it once.

    Order matters: email first, then record. If the email fails, nothing is
    recorded and the next run tries again; the reverse order could mark as
    sent a summary that never left.
    """
    email_subject = subject(year, month)
    if not dry_run and store.summary_exists(year, month):
        return RunOutcome("already_sent", email_subject)

    facts = compute_facts(year, month, store.month_rows(year, month),
                          store.month_rows(*month_before(year, month)))
    generation = generate_message(facts, store.previous_colour_texts(year, month), write)
    if dry_run:
        return RunOutcome("dry_run", email_subject, generation)

    send(email_subject, generation.full_message)
    store.save_summary(year, month, facts.tier, generation, model)
    return RunOutcome("sent", email_subject, generation)
```

- [ ] **Step 4: Run, expect PASS** — `.venv/bin/python -m unittest tests.test_summary_service -v`. If `test_biggest_message_fits_in_a_whatsapp_link` fails, the `complet` bullets are too long: shorten `render_facts`, don't raise the limit.

- [ ] **Step 5: Commit**

```bash
git add summary/service.py summary/delivery.py tests/test_summary_service.py
git commit -m "feat(backend): orchestrate summary with retries and fallback"
```

---

### Task 8: Delivery — WhatsApp link and email

**Files:**
- Modify: `summary/delivery.py` (keeps `MAX_MESSAGE_CHARS` from Task 7)
- Test: `tests/test_summary_delivery.py`

**Interfaces:**
- Produces: `whatsapp_link(message) -> str`, `build_email(sender, to, subject, message) -> EmailMessage`, `send_email(msg, user, password) -> None`

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_delivery.py`:

```python
import unittest
from unittest import mock
from urllib.parse import unquote

from summary.delivery import build_email, send_email, whatsapp_link

MESSAGE = "Salut la famille 🎬 !\n«Le Daim» & co… Qui vient ? 50% de chances"


class TestWhatsappLink(unittest.TestCase):
    def test_round_trip(self):
        link = whatsapp_link(MESSAGE)
        self.assertTrue(link.startswith("https://wa.me/?text="))
        self.assertEqual(unquote(link.removeprefix("https://wa.me/?text=")), MESSAGE)

    def test_special_characters_are_encoded(self):
        link = whatsapp_link(MESSAGE)
        for raw in (" ", "&", "\n", "%"):
            self.assertNotIn(raw, link.removeprefix("https://"))


class TestEmail(unittest.TestCase):
    def test_email_has_text_and_html_with_link(self):
        msg = build_email("bot@gmail.com", "me@hotmail.fr", "Résumé Perrin-rama: Sept'26", MESSAGE)
        self.assertEqual(msg["Subject"], "Résumé Perrin-rama: Sept'26")
        self.assertEqual(msg["To"], "me@hotmail.fr")
        plain = msg.get_body(("plain",)).get_content()
        html = msg.get_body(("html",)).get_content()
        self.assertIn("Salut la famille", plain)
        self.assertIn("Envoyer sur WhatsApp", html)
        self.assertIn("&amp;", html)  # message text is HTML-escaped

    def test_send_uses_gmail_over_ssl(self):
        msg = build_email("bot@gmail.com", "me@hotmail.fr", "s", "m")
        with mock.patch("summary.delivery.smtplib.SMTP_SSL") as smtp:
            send_email(msg, "bot@gmail.com", "app-password")
        smtp.assert_called_once_with("smtp.gmail.com", 465, timeout=30)
        server = smtp.return_value.__enter__.return_value
        server.login.assert_called_once_with("bot@gmail.com", "app-password")
        server.send_message.assert_called_once_with(msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_delivery` → `ImportError: cannot import name 'build_email'`.

- [ ] **Step 3: Implement** — replace `summary/delivery.py` with:

```python
"""
Delivery: an email to Joseph with a one-tap "send to WhatsApp" link.

WhatsApp has no free API for posting to a family group, so a person reviews
the message and forwards it: wa.me opens WhatsApp with the text pre-filled.
"""

import html
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

WA_URL = "https://wa.me/?text="
MAX_MESSAGE_CHARS = 1500  # checked on a phone during the first live send
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465


def whatsapp_link(message: str) -> str:
    return WA_URL + quote(message, safe="")


def build_email(sender: str, to: str, subject: str, message: str) -> EmailMessage:
    link = whatsapp_link(message)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(f"{message}\n\n---\nEnvoyer sur WhatsApp : {link}\n")
    msg.add_alternative(
        f"""<p style="white-space: pre-wrap; font-family: sans-serif;">{html.escape(message)}</p>
<p><a href="{html.escape(link)}" style="display: inline-block; padding: 12px 20px;
background: #25D366; color: white; border-radius: 8px; text-decoration: none;
font-family: sans-serif; font-weight: bold;">Envoyer sur WhatsApp</a></p>""",
        subtype="html",
    )
    return msg


def send_email(msg: EmailMessage, user: str, password: str) -> None:
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(user, password)
        server.send_message(msg)
```

- [ ] **Step 4: Run all tests, expect PASS** — `.venv/bin/python -m unittest`.

- [ ] **Step 5: Commit**

```bash
git add summary/delivery.py tests/test_summary_delivery.py
git commit -m "feat(backend): email the summary with a WhatsApp share link"
```

---

### Task 9: Entry-point script

**Files:**
- Create: `scripts/send_monthly_summary.py`
- Test: `tests/test_summary_script.py` (argument parsing only)

**Interfaces:**
- Consumes: everything above; `fill_display_titles`, `fetch_tmdb_titles`, `TmdbAuthError` from `summary/titles.py`.
- Produces: `python -m scripts.send_monthly_summary [--month YYYY-MM] [--dry-run]`; `parse_month(value) -> tuple[int, int]`; `target_month(arg, now) -> tuple[int, int]`.
- Env: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SUMMARY_MODEL` (optional), `TMDB_READ_TOKEN` (optional), and when not a dry run `SMTP_USER`, `SMTP_APP_PASSWORD`, `SUMMARY_TO`; `PUBLIC_LOGS=true` hides the message and errors.

- [ ] **Step 1: Write the failing tests** — `tests/test_summary_script.py`:

```python
import os
import unittest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts.send_monthly_summary import parse_month, target_month  # noqa: E402


class TestMonthArguments(unittest.TestCase):
    def test_parse_month(self):
        self.assertEqual(parse_month("2026-09"), (2026, 9))

    def test_invalid_month(self):
        with self.assertRaises(ValueError):
            parse_month("2026-13")

    def test_default_is_previous_month(self):
        self.assertEqual(target_month(None, datetime(2026, 11, 1, 12, 17)), (2026, 10))
        self.assertEqual(target_month(None, datetime(2027, 1, 1)), (2026, 12))

    def test_explicit_month_wins(self):
        self.assertEqual(target_month("2026-09", datetime(2026, 11, 1)), (2026, 9))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m unittest tests.test_summary_script` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `scripts/send_monthly_summary.py`:

```python
"""
Build the monthly family summary and email it.

Run from the repo root:
    python -m scripts.send_monthly_summary --dry-run          # previous month, print only
    python -m scripts.send_monthly_summary --month 2026-09    # a given month, send for real
"""

import argparse
import os
from datetime import datetime
from typing import Optional

import anthropic

import database
from summary.delivery import build_email, send_email
from summary.facts import PARIS, month_before
from summary.service import run_month
from summary.store import PostgresStore
from summary.titles import TmdbAuthError, fetch_tmdb_titles, fill_display_titles
from summary.writer import write_colour

DEFAULT_MODEL = "claude-opus-5-5"


def parse_month(value: str) -> tuple[int, int]:
    year, month = (int(part) for part in value.split("-"))
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month: {value}")
    return year, month


def target_month(arg: Optional[str], now: datetime) -> tuple[int, int]:
    return parse_month(arg) if arg else month_before(now.year, now.month)


def require_env(names: list[str]) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--month", help="YYYY-MM (default: previous month)")
    parser.add_argument("--dry-run", action="store_true", help="generate and print only: no email, no database write")
    args = parser.parse_args()

    require_env(["ANTHROPIC_API_KEY"] + ([] if args.dry_run else ["SMTP_USER", "SMTP_APP_PASSWORD", "SUMMARY_TO"]))
    year, month = target_month(args.month, datetime.now(PARIS))
    model = os.environ.get("SUMMARY_MODEL", DEFAULT_MODEL)
    public_logs = os.environ.get("PUBLIC_LOGS") == "true"

    database.init_db()
    engine = database.get_engine()

    # Titles are a nice-to-have: a TMDB problem must not block the summary
    token = os.environ.get("TMDB_READ_TOKEN")
    if token:
        try:
            fill_display_titles(engine, fetch=lambda imdb_id: fetch_tmdb_titles(imdb_id, token))
        except TmdbAuthError as e:
            print(f"Warning: {e}; using existing titles.")

    client = anthropic.Anthropic()

    def write(payload, feedback):
        return write_colour(client, model, payload, feedback)

    def send(subject, message):
        user = os.environ["SMTP_USER"]
        send_email(build_email(user, os.environ["SUMMARY_TO"], subject, message),
                   user, os.environ["SMTP_APP_PASSWORD"])

    outcome = run_month(PostgresStore(engine), year, month, write, send, model, dry_run=args.dry_run)

    print(f"{outcome.subject}: {outcome.status}")
    g = outcome.generation
    if g is None:
        return
    print(f"attempts={g.attempts} fallback={g.used_fallback} chars={len(g.full_message)} "
          f"tokens_in={g.input_tokens} tokens_out={g.output_tokens}")
    # Workflow logs on a public repo are public: never print family data there
    if not public_logs:
        for i, errors in enumerate(g.errors, 1):
            print(f"attempt {i} errors: {errors}")
        print("\n" + g.full_message)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests, expect PASS** — `.venv/bin/python -m unittest`, then `uvx -q pyflakes summary scripts tests`.

- [ ] **Step 5: Commit**

```bash
git add scripts/send_monthly_summary.py tests/test_summary_script.py
git commit -m "feat(scripts): add monthly summary entry point"
```

---

### Task 10: Eval harness and fake months

**Files:**
- Create: `evals/__init__.py` (empty), `evals/run_evals.py`, `evals/README.md`
- Create: `evals/cases/dev/01_empty_month.json` … `07_repeat_history.json`, `evals/cases/holdout/08_…` … `10_…`
- Modify: `.gitignore` (nothing: `evals/results/` **is** committed, as the experiment log)

**Interfaces:**
- Consumes: `RatingRow`, `compute_facts` (Task 2), `build_payload`, `write_colour` (Task 6), `validate` (Task 5).
- Produces: `python -m evals.run_evals --set dev|holdout --label v1 [--model ...]` → `evals/results/<date>-<set>-<label>.md` and a printed pass rate and cost.

Case format (rows use the `RatingRow` field names):

```json
{
  "description": "what this case tests",
  "year": 2026, "month": 5,
  "rows": [{"film": "...", "year": "2019", "genres": "Comedy", "who": "Bob", "score": 6.0, "comment": "..."}],
  "previous_rows": [],
  "previous_texts": []
}
```

- [ ] **Step 1: Write the harness** — `evals/run_evals.py`:

```python
"""
Run the summary prompt on fake months and write a report for human review.

Measures the FIRST attempt only (no retries): retries hide prompt weaknesses.
Costs real money (one Claude call per case); needs ANTHROPIC_API_KEY.

    python -m evals.run_evals --set dev --label v1
    python -m evals.run_evals --set holdout --label v4-final
"""

import argparse
import json
from datetime import date
from pathlib import Path

import anthropic

from summary.facts import RatingRow, compute_facts
from summary.validate import validate
from summary.writer import build_payload, write_colour

ROOT = Path(__file__).parent
PRICES_PER_MTOK = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}


def load_case(path: Path):
    case = json.loads(path.read_text(encoding="utf-8"))
    facts = compute_facts(
        case["year"], case["month"],
        [RatingRow(**r) for r in case["rows"]],
        [RatingRow(**r) for r in case.get("previous_rows", [])],
    )
    return case, facts


def main():
    parser = argparse.ArgumentParser(description="Run the summary eval set")
    parser.add_argument("--set", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--label", required=True, help="prompt version, e.g. v1")
    parser.add_argument("--model", default="claude-opus-5-5")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    results, tokens_in, tokens_out = [], 0, 0
    for path in sorted((ROOT / "cases" / args.set).glob("*.json")):
        case, facts = load_case(path)
        previous = case.get("previous_texts", [])
        result = write_colour(client, args.model, build_payload(facts, previous))
        tokens_in += result.input_tokens
        tokens_out += result.output_tokens
        errors = validate(result.colour, facts, previous) if result.colour else ["no usable output"]
        message = result.colour.message if result.colour else ""
        results.append((path.stem, case["description"], facts.tier, message, errors))
        print(f"{'PASS' if not errors else 'FAIL'}  {path.stem}")

    passed = sum(1 for r in results if not r[4])
    price_in, price_out = PRICES_PER_MTOK.get(args.model, (0, 0))
    cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000

    lines = [f"# Eval {args.set} — {args.label}", "",
             f"Model: `{args.model}` · automatic checks: {passed}/{len(results)} · "
             f"tokens {tokens_in} in / {tokens_out} out · ≈ ${cost:.2f}", "",
             "| Case | Tier | Checks | Chars | Humour /5 | Tone /5 |", "|---|---|---|---|---|---|"]
    lines += [f"| {name} | {tier} | {'✅' if not errors else '❌'} | {len(message)} |  |  |"
              for name, _, tier, message, errors in results]
    for name, description, tier, message, errors in results:
        lines += ["", f"## {name} ({tier})", f"_{description}_", "", "```", message, "```"]
        lines += [f"- ❌ {e}" for e in errors] or ["- ✅ all automatic checks pass"]
        lines += ["", "Humour: _/5 · Tone: _/5 · Notes:"]

    out = ROOT / "results" / f"{date.today()}-{args.set}-{args.label}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} pass · ≈ ${cost:.2f} · report: {out.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the dev cases** (fake family: Alice, Bob, Chloé, Daniel — never real data):

`evals/cases/dev/01_empty_month.json`
```json
{"description": "No ratings: a joke and a nudge, no titles", "year": 2026, "month": 9,
 "rows": [], "previous_rows": [{"film": "Tenet", "year": "2020", "genres": "Action, Sci-Fi", "who": "Bob", "score": 7.0, "comment": "J'ai rien compris"}],
 "previous_texts": []}
```

`evals/cases/dev/02_one_film.json`
```json
{"description": "A single rating, light tier", "year": 2026, "month": 6, "rows": [
  {"film": "Le Daim", "year": "2019", "genres": "Comedy, Horror", "who": "Bob", "score": 6.5, "comment": "Le blouson a plus de charisme que moi"}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/dev/03_big_month.json`
```json
{"description": "Full tier, 10 ratings, comments to quote", "year": 2026, "month": 1, "rows": [
  {"film": "The Godfather", "year": "1972", "genres": "Crime, Drama", "who": "Daniel", "score": 9.5, "comment": "Chef-d'œuvre absolu"},
  {"film": "The Godfather Part II", "year": "1974", "genres": "Crime, Drama", "who": "Daniel", "score": 9.0, "comment": "Encore mieux ?"},
  {"film": "The Godfather Part III", "year": "1990", "genres": "Crime, Drama", "who": "Daniel", "score": 6.0, "comment": "On aurait dû s'arrêter à deux"},
  {"film": "Encanto", "year": "2021", "genres": "Animation, Comedy, Family", "who": "Chloé", "score": 8.0, "comment": "On ne parle pas de Bruno"},
  {"film": "Encanto", "year": "2021", "genres": "Animation, Comedy, Family", "who": "Alice", "score": 7.0, "comment": "La chanson est restée trois jours"},
  {"film": "La La Land", "year": "2016", "genres": "Comedy, Drama, Music", "who": "Alice", "score": 8.5, "comment": "J'ai pleuré à la fin"},
  {"film": "Whiplash", "year": "2014", "genres": "Drama, Music", "who": "Bob", "score": 9.0, "comment": "Not quite my tempo"},
  {"film": "Mean Girls", "year": "2004", "genres": "Comedy", "who": "Chloé", "score": 7.5, "comment": "Le mercredi on s'habille en rose"},
  {"film": "Napoleon", "year": "2023", "genres": "Action, Biography, Drama", "who": "Bob", "score": 4.0, "comment": "Trois heures pour ça"},
  {"film": "Les Misérables", "year": "2019", "genres": "Crime, Drama, Thriller", "who": "Alice", "score": 8.0, "comment": null}],
 "previous_rows": [{"film": "Tenet", "year": "2020", "genres": "Action", "who": "Bob", "score": 7.0, "comment": null}],
 "previous_texts": []}
```

`evals/cases/dev/04_tie_for_best.json`
```json
{"description": "Full tier where two films tie for best", "year": 2026, "month": 3, "rows": [
  {"film": "Anatomie d'une chute", "year": "2023", "genres": "Crime, Drama", "who": "Alice", "score": 9.0, "comment": "Le chien mérite la Palme"},
  {"film": "Shutter Island", "year": "2010", "genres": "Mystery, Thriller", "who": "Bob", "score": 9.0, "comment": "Fin à revoir deux fois"},
  {"film": "The Menu", "year": "2022", "genres": "Comedy, Horror", "who": "Chloé", "score": 7.0, "comment": "Plus jamais de cheeseburger"},
  {"film": "Gladiator II", "year": "2024", "genres": "Action, Drama", "who": "Bob", "score": 5.0, "comment": "Des requins au Colisée ?"},
  {"film": "Podium", "year": "2004", "genres": "Comedy, Music", "who": "Daniel", "score": 7.5, "comment": "Bernard Frédéric forever"},
  {"film": "Top Gun: Maverick", "year": "2022", "genres": "Action, Drama", "who": "Daniel", "score": 8.0, "comment": null}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/dev/05_titles_with_digits.json`
```json
{"description": "Titles containing digits: digits inside «» are allowed", "year": 2026, "month": 4, "rows": [
  {"film": "Blade Runner 2049", "year": "2017", "genres": "Action, Drama, Sci-Fi", "who": "Bob", "score": 8.0, "comment": "Long mais beau"},
  {"film": "8½", "year": "1963", "genres": "Drama", "who": "Daniel", "score": 7.0, "comment": "Je n'ai pas tout suivi"},
  {"film": "F1", "year": "2025", "genres": "Action, Drama, Sport", "who": "Chloé", "score": 6.5, "comment": "Brad Pitt ne vieillit pas"}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/dev/06_translation_trap.json`
```json
{"description": "English titles Claude may be tempted to translate into French", "year": 2026, "month": 2, "rows": [
  {"film": "The Lives of Others", "year": "2006", "genres": "Drama, Thriller", "who": "Alice", "score": 9.0, "comment": "Glaçant"},
  {"film": "Parasite", "year": "2019", "genres": "Drama, Thriller", "who": "Bob", "score": 8.5, "comment": "La scène de la pluie"},
  {"film": "Sentimental Value", "year": "2025", "genres": "Drama", "who": "Chloé", "score": 7.0, "comment": null},
  {"film": "Spirited Away", "year": "2001", "genres": "Animation, Family, Fantasy", "who": "Daniel", "score": 8.0, "comment": "Sans-Visage me hante"}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/dev/07_repeat_history.json`
```json
{"description": "History contains a joke that must not come back", "year": 2026, "month": 7, "rows": [
  {"film": "Le Daim", "year": "2019", "genres": "Comedy", "who": "Alice", "score": 7.0, "comment": "Encore ce blouson"},
  {"film": "Les rois mages", "year": "2001", "genres": "Comedy", "who": "Bob", "score": 6.0, "comment": null}],
 "previous_rows": [],
 "previous_texts": ["🧥 Ce mois-ci, le vrai héros c'est le blouson en daim : il a volé la vedette à tout le monde ! Bob et Alice se disputent déjà la taille. Qui ose le porter au prochain repas de famille ?"]}
```

- [ ] **Step 3: Write the holdout cases** (do **not** read their reports until the final run):

`evals/cases/holdout/08_quiet_summer.json`
```json
{"description": "Light tier, one person did all the rating", "year": 2026, "month": 8, "rows": [
  {"film": "Mamma Mia!", "year": "2008", "genres": "Comedy, Musical, Romance", "who": "Alice", "score": 8.0, "comment": "En boucle tout l'été"},
  {"film": "Jaws", "year": "1975", "genres": "Adventure, Thriller", "who": "Alice", "score": 7.5, "comment": "Plus jamais de baignade"},
  {"film": "Grease", "year": "1978", "genres": "Musical, Romance", "who": "Alice", "score": 6.0, "comment": null}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/holdout/09_family_feud.json`
```json
{"description": "Full tier, the family strongly disagrees about the same film", "year": 2026, "month": 11, "rows": [
  {"film": "Barbie", "year": "2023", "genres": "Adventure, Comedy, Fantasy", "who": "Chloé", "score": 9.0, "comment": "Iconique"},
  {"film": "Barbie", "year": "2023", "genres": "Adventure, Comedy, Fantasy", "who": "Bob", "score": 3.0, "comment": "Je suis Ken et je souffre"},
  {"film": "Oppenheimer", "year": "2023", "genres": "Biography, Drama, History", "who": "Bob", "score": 9.0, "comment": "Le son de l'explosion"},
  {"film": "Oppenheimer", "year": "2023", "genres": "Biography, Drama, History", "who": "Chloé", "score": 5.0, "comment": "Trois heures de réunions"},
  {"film": "Amélie", "year": "2001", "genres": "Comedy, Romance", "who": "Alice", "score": 8.0, "comment": null},
  {"film": "Intouchables", "year": "2011", "genres": "Biography, Comedy, Drama", "who": "Daniel", "score": 8.5, "comment": "Boogie Wonderland"}],
 "previous_rows": [], "previous_texts": []}
```

`evals/cases/holdout/10_empty_after_big.json`
```json
{"description": "Empty month right after a big one, with history", "year": 2026, "month": 12, "rows": [],
 "previous_rows": [
  {"film": "Barbie", "year": "2023", "genres": "Comedy", "who": "Chloé", "score": 9.0, "comment": null},
  {"film": "Oppenheimer", "year": "2023", "genres": "Drama", "who": "Bob", "score": 9.0, "comment": null}],
 "previous_texts": ["🎬 Novembre a coupé la famille en deux : team rose contre team bombe atomique ! Bob souffre en Ken, Chloé bâille devant les physiciens. Qui tranche le débat au prochain dîner ?"]}
```

- [ ] **Step 4: Write `evals/README.md`**:

```markdown
# Summary evals

Fake months (no real family data) used to tune `summary/prompt_fr.txt`.

1. `python -m evals.run_evals --set dev --label vN` (≈ $0.30, needs `ANTHROPIC_API_KEY`)
2. Read `results/<date>-dev-vN.md`, fill in the humour and tone scores.
3. Change **one** thing in the prompt; commit with the scores in the message.
4. Stop when the dev set passes every automatic check twice in a row and
   the human scores stop improving.
5. Run `--set holdout` once. A drop means the prompt fits the examples
   rather than the task.

Only the first attempt is measured: production retries would hide a weak prompt.
```

- [ ] **Step 5: Sanity-check loading without calling the API**:

```bash
.venv/bin/python -c "
from pathlib import Path
from evals.run_evals import load_case
for p in sorted(Path('evals/cases').glob('*/*.json')):
    print(p.name, load_case(p)[1].tier)
"
```
Expected: 10 lines; tiers `aucun, leger, complet, complet, leger, leger, leger, leger, complet, aucun`.

- [ ] **Step 6: Commit**

```bash
git add evals
git commit -m "feat(evals): add eval harness and fake months"
```

---

### Task 11: Eval round with Joseph (manual, time-boxed)

**Prerequisite (Joseph):** console.anthropic.com → add credit → create a dedicated API key → set a monthly spend limit (e.g. $5). In the terminal: `read -s ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY`.

- [ ] **Step 1: Baseline** — `.venv/bin/python -m evals.run_evals --set dev --label v1`. Commit the report: `git add evals/results && git commit -m "chore(eval): prompt v1 baseline (dev X/7)"`.
- [ ] **Step 2: Joseph reads and scores** the report (≈ 10 min): humour /5, tone /5, notes.
- [ ] **Step 3: One change per round** to `summary/prompt_fr.txt`, rerun with `--label v2`, commit prompt + report together: `chore(eval): prompt v2, <the change> (dev X/7, humour Y/5)`.
- [ ] **Step 4: Stop** at 7/7 twice in a row with a stable human score, **or after 4 rounds** (time box for today).
- [ ] **Step 5: Holdout once** — `--set holdout --label vN-final`, commit the report. If it drops noticeably, note it in the README section (Task 13) rather than tuning on it.

---

### Task 12: First real send — September 2026

**Prerequisites (Joseph):** a dedicated Gmail with 2-step verification and an app password (Google Account → Security → App passwords).

- [ ] **Step 1: Local dry run on real data** (prints the message locally, sends nothing):

```bash
.venv/bin/python -m scripts.send_monthly_summary --month 2026-09 --dry-run
```
Expected: `Résumé Perrin-rama: Sept'26: dry_run`, tier `aucun` (September has no ratings), `fallback=False`.

- [ ] **Step 2: Live send to Joseph** — in the same terminal:

```bash
read -s SMTP_APP_PASSWORD && export SMTP_APP_PASSWORD
export SMTP_USER=<dedicated gmail address> SUMMARY_TO=<joseph's address>
.venv/bin/python -m scripts.send_monthly_summary --month 2026-09
```
Expected: `sent`; a row in `monthly_summaries` for 2026-09-01.

- [ ] **Step 3: Phone check** — open the email on the phone, tap "Envoyer sur WhatsApp", confirm the full text (emojis, line breaks) appears in WhatsApp, send it to the family group. If the text is cut, lower `MAX_MESSAGE_CHARS` and the `complet` length range, then rerun the tests.

- [ ] **Step 4: Idempotency check** — rerun the Step 2 command: expected `already_sent`, no second email.

---

### Task 13: Automation for 1 November

**Files:**
- Create: `.github/workflows/monthly-summary.yml`

- [ ] **Step 1: Write the workflow**:

```yaml
name: Monthly Summary

on:
  schedule:
    # 1st of each month, 12:17 UTC (08:17 New York in summer, 07:17 in winter).
    # Off the hour because GitHub delays jobs scheduled exactly on the hour.
    - cron: '17 12 1 * *'
  workflow_dispatch:
    inputs:
      month:
        description: 'Month to summarise (YYYY-MM). Empty = previous month'
        required: false
        default: ''
      dry_run:
        description: 'Generate only: no email, no database write'
        type: boolean
        default: true

jobs:
  summary:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Build and send the summary
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TMDB_READ_TOKEN: ${{ secrets.TMDB_READ_TOKEN }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_APP_PASSWORD: ${{ secrets.SMTP_APP_PASSWORD }}
          SUMMARY_TO: ${{ secrets.SUMMARY_TO }}
          SUMMARY_MODEL: claude-opus-5-5
          # This repo is public, so its logs are too: the script then prints
          # only counts, never names, titles or comments.
          PUBLIC_LOGS: 'true'
          # Inputs go through env, not straight into the shell command,
          # so a crafted value can't inject shell code.
          MONTH: ${{ inputs.month }}
          DRY_RUN: ${{ inputs.dry_run }}
        run: |
          args=()
          if [ -n "$MONTH" ]; then args+=(--month "$MONTH"); fi
          if [ "$DRY_RUN" = "true" ]; then args+=(--dry-run); fi
          python -m scripts.send_monthly_summary "${args[@]}"
```

On the scheduled run, `inputs.*` are empty, so it summarises the previous month and sends for real.

- [ ] **Step 2: Add secrets (Joseph)** — `gh secret set ANTHROPIC_API_KEY`, `gh secret set SMTP_USER`, `gh secret set SMTP_APP_PASSWORD`, `gh secret set SUMMARY_TO` (each prompts for the value; nothing lands in shell history). `DATABASE_URL` and `TMDB_READ_TOKEN` already exist.

- [ ] **Step 3: Commit and push** (after `ussh`):

```bash
git add .github/workflows/monthly-summary.yml
git commit -m "feat(ci): schedule the monthly summary"
git push origin main
```

- [ ] **Step 4: Test on GitHub** — `gh workflow run monthly-summary.yml -f month=2026-10 -f dry_run=true`, then `gh run watch`. Expected: success, log shows `dry_run`, counts only, **no** names or titles.

---

### Task 14: Interview-ready polish

**Files:**
- Modify: `README.md` (features, architecture diagram, new "Monthly summary" section, keys table, layout, roadmap)
- Modify: `CONTEXT.local.md` (local only)

- [ ] **Step 1: README** — add:
  - Architecture mermaid: an edge `GH2[GitHub Actions<br/>monthly cron] -->|facts| Claude[Anthropic API]` and `GH2 -->|email + wa.me link| Gmail`.
  - Keys table rows: `ANTHROPIC_API_KEY`, `SMTP_USER` / `SMTP_APP_PASSWORD` (dedicated Gmail app password), `SUMMARY_TO`.
  - Project layout: `summary/`, `evals/`.
  - Section **"Monthly summary: an LLM in a box"** (≈ 15 lines): code writes the facts, Claude only the colour; structured output plus automatic checks; retry with the errors, then an AI-free fallback; memory of the last three summaries; eval set with dev/holdout split and the results history in `evals/results/`; public-log hygiene; cost per month from `monthly_summaries` tokens. Link the spec and the plan.
  - Roadmap: recommendations agent next, then logging past viewings.
- [ ] **Step 2: Full check** — `.venv/bin/python -m unittest -v` and `uvx -q pyflakes summary scripts tests evals`, then push and confirm the Tests workflow passes.
- [ ] **Step 3: Commit** — `docs: document the monthly summary`.
- [ ] **Step 4: `CONTEXT.local.md`** — what shipped, secrets added, next items (data cleanup of duplicates and episodes, `display_title` in the app, recommendations agent, GitHub Support purge follow-up).
