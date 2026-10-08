"""
Run the summary prompt on fake months and write a report for human review.

Measures the FIRST attempt only (no retries): retries hide prompt weaknesses.
Costs real money (one Claude call per case); needs ANTHROPIC_API_KEY.

    python -m evals.run_evals --set dev --label v1
    python -m evals.run_evals --set holdout --label v4-final
"""

import argparse
import json
import os
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

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set in this terminal. "
                         "Run: read -s ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY")
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
