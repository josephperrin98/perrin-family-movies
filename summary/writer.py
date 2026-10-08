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
from summary.render import period_label

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
        "mois": period_label(facts.year, facts.month, facts.until),
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
