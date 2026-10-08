"""
Everything in the summary that is written by code, not by Claude: the
factual bullets, the email subject, and the AI-free fallback sentences.
"""

from datetime import date
from typing import Optional

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


def _runs_into_next_month(year: int, month: int, until: Optional[date]) -> bool:
    return until is not None and until > date(year + month // 12, month % 12 + 1, 1)


def period_label(year: int, month: int, until: Optional[date] = None) -> str:
    """"septembre 2026", or "septembre et début octobre 2026" for a longer period."""
    if not _runs_into_next_month(year, month, until):
        return f"{MONTH_NAMES[month - 1]} {year}"
    if until.year == year:
        return f"{MONTH_NAMES[month - 1]} et début {MONTH_NAMES[until.month - 1]} {year}"
    return f"{MONTH_NAMES[month - 1]} {year} et début {MONTH_NAMES[until.month - 1]} {until.year}"


def subject(year: int, month: int, until: Optional[date] = None) -> str:
    months = MONTH_ABBR[month - 1]
    if _runs_into_next_month(year, month, until):
        months += "-" + MONTH_ABBR[until.month - 1]
    return f"Résumé Perrin-rama: {months}'{year % 100:02d}"


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


def fallback_colour(tier: str, label: str) -> str:
    if tier == "aucun":
        return f"🎬 Aucun film noté en {label} ! Vous avez regardé quoi ? Notez-les dans l'appli 🍿"
    if tier == "leger":
        return f"🍿 Petit mois cinéma en {label}. Qui a un film à recommander ?"
    return f"🎬 Gros mois cinéma en {label} ! Voici le bilan. Et vous, votre coup de cœur ?"


def assemble(colour: str, facts_text: str) -> str:
    return "\n\n".join(part for part in (colour, facts_text) if part)
