"""
Automatic checks on Claude's colour text (the code half of the rubric).

Used twice: in production before anything is emailed, and offline by the
eval harness to score prompt versions. Errors are written in French because
they are sent back to Claude when it gets a second attempt.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from summary.facts import FAMILY_CLASSICS, MonthFacts

LENGTH = {"aucun": (80, 400), "leger": (150, 500), "complet": (250, 600)}
MAX_PEOPLE_NAMED = 2
SIMILARITY_LIMIT = 0.6
QUOTED = re.compile(r"«\s*(.+?)\s*»")


def quoted_titles(text: str) -> list[str]:
    return QUOTED.findall(text)


def has_emoji(text: str) -> bool:
    # "So" = Unicode category "Symbol, other", where emojis live
    return any(unicodedata.category(c) == "So" for c in text)


def validate(colour, facts: MonthFacts, previous_texts: list[str]) -> list[str]:
    errors = []
    message = colour.message
    quoted = quoted_titles(message)
    known_titles = {t.lower() for t in facts.films | set(FAMILY_CLASSICS)}

    for title in quoted:
        if title.lower() not in known_titles:
            errors.append(f"Titre inconnu : «{title}». Recopie exactement un titre de 'notes' ou de 'classiques_famille'.")
    if {t.lower() for t in colour.titles_mentioned} != {t.lower() for t in quoted}:
        errors.append("titles_mentioned doit lister exactement les titres écrits entre « ».")
    # Names are found in the text itself, not only in what the model says it did
    family = set(facts.family) | facts.people
    named = {n for n in family if re.search(rf"\b{re.escape(n)}\b", message)}
    for name in sorted(named | set(colour.names_mentioned)):
        if name not in facts.people:
            errors.append(f"Ne cite pas {name} : cite uniquement les personnes qui ont noté un film.")
    if len(named) > MAX_PEOPLE_NAMED:
        errors.append(f"Trop de personnes citées ({', '.join(sorted(named))}) : "
                      f"parle d'au plus {MAX_PEOPLE_NAMED} personnes.")

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
