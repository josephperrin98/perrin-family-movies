# Monthly family summary — design

Status: approved in brainstorming, 2026-10-07
Sub-project #1 of Stage 4 (AI agents). Depends on sub-project #0 (display titles).

## Goal

On the 1st of each month, email Joseph a short, funny French summary of the
films the family rated in the previous month, with a one-tap
"Envoyer sur WhatsApp" link so he can review it and forward it to the family
group.

This is a **workflow**, not an agent: code decides every step, and the LLM is
used once, for one job (writing the "colour"). The learning focus is
**grounding** (the model may only talk about facts it was given) and
**evals** (measuring prompt quality instead of guessing).

## Decisions

| Topic | Decision | Rejected alternative, and why |
|---|---|---|
| Which ratings count | `ratings.created_at` in `[1st 00:00, next 1st 00:00)` Europe/Paris | `watch_status.watched_at`: often empty (14 "watched" rows have no date) |
| Who writes what | Code writes every fact and number; Claude writes only the colour | Model writes everything: numbers can't be trusted |
| Output shape | Structured output with one free-text `message` field + self-declared lists | Free text with `{{TOP3}}` markers: fragile to parse and validate |
| Model | `claude-opus-5-5`, configurable via `SUMMARY_MODEL` | Cost is ~$0.22/year on any model; quality and retry rate matter more. Re-check with the eval |
| Provider | Anthropic API directly (API key) | Vertex AI: ~10 setup steps + extra dependencies; a later exercise |
| Comments | Sent to Claude, with first names only | Titles and scores only: loses the family flavour |
| Language | French | — |
| Delivery | Email to Joseph from a dedicated Gmail, containing a `wa.me` link | WhatsApp Cloud API: paid, needs a business number, groups unverified. Unofficial WhatsApp Web libraries: break the ToS |
| Memory | `monthly_summaries` table; last 3 colour texts sent back to Claude | — |
| Prompt changes | Measured with an eval set, one change per commit | Tuning by feel |

## Tiers

| Ratings in the month | Tier | Content |
|---|---|---|
| 0 | `aucun` | A joke + a nudge to log what the family watched. No titles. |
| 1–5 | `leger` | Count, the film(s), who rated, one fun line. |
| 6+ | `complet` | Count and average, contributor ranking, top 3 and bottom 3, favourite genre, plus colour: trend, theme, an anecdote from a comment, a question to start a conversation. |

## Architecture

```
.github/workflows/monthly-summary.yml   cron + manual trigger
scripts/send_monthly_summary.py         thin entry point: env vars -> service
summary/
  facts.py       fetch_month_rows (SQL only) + compute_facts (pure) -> MonthFacts, tier
  render.py      MonthFacts -> French bullets with emojis, email subject, fallback text
  writer.py      the only module that calls Claude; prompt loaded from prompt_fr.txt
  prompt_fr.txt  the system prompt (versioned; tuned with the eval)
  validate.py    automatic rubric checks -> list of errors
  service.py     facts -> writer -> validate -> retry <=2 -> fallback -> email -> store
  delivery.py    wa.me link + email (smtplib)
evals/
  cases/dev/*.json      7 fake months used for tuning
  cases/holdout/*.json  3 fake months, run only at the end
  run_evals.py          runs writer + validate per case, writes a report
  results/              one markdown report per run
```

`service.py` receives the writer and the email sender as arguments
(dependency injection), so every path can be tested without network or cost.

## Data

### Display titles (from sub-project #0)

Facts use `movies.display_title`: the original title when the original
language uses the Latin alphabet, otherwise the French title (from TMDB,
looked up by `imdb_id`). OMDb only provides English titles, and Claude must
never translate titles itself, because that would be an unverifiable fact.

### Month boundaries

`ratings.created_at` is a `TIMESTAMP` without time zone written by the
database in UTC. The month's Paris boundaries are converted to UTC before
querying. Tests cover a month that contains a daylight-saving change.

### Payload sent to Claude (JSON)

```json
{
  "mois": "septembre 2026",
  "palier": "complet",
  "notes": [{"film": "...", "annee": "...", "genres": "Comedy, Romance",
             "qui": "Chloé", "note": 8.5, "commentaire": "..."}],
  "faits": {"nb_notes": 12, "moyenne": 7.4, "genre_favori": "Comedy",
            "meilleurs": [], "pires": [], "classement": []},
  "mois_precedent": {"nb_notes": 4, "moyenne": 8.0},
  "deja_ecrit": ["colour text of the last 3 months"]
}
```

Numbers are given as context, but the colour text must not contain digits.

### Table `monthly_summaries`

Created in `database.py` with the other tables.

| Column | Type | Purpose |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | |
| `month` | `DATE UNIQUE NOT NULL` | 1st of the month; uniqueness prevents a double send |
| `tier` | `TEXT NOT NULL` | `aucun` / `leger` / `complet` |
| `colour_text` | `TEXT` | Claude's text only; null on fallback; anti-repetition memory |
| `full_message` | `TEXT NOT NULL` | exactly what was emailed |
| `used_fallback` | `BOOLEAN NOT NULL` | |
| `attempts` | `INTEGER NOT NULL` | 1–3 |
| `validation_errors` | `JSONB` | errors per failed attempt; source of the failure rate |
| `model` | `TEXT` | |
| `input_tokens`, `output_tokens` | `INTEGER` | tokens, not dollars: prices change |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | |

Order: check the month is absent -> generate -> send email -> insert. A failed
email records nothing, so the next run retries.

## The Claude call

```python
class Colour(BaseModel):
    message: str
    titles_mentioned: list[str]
    names_mentioned: list[str]

response = client.messages.parse(
    model=SUMMARY_MODEL,
    max_tokens=2000,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    output_format=Colour,
    output_config={"effort": "medium"},
)
```

- The schema guarantees shape; `validate.py` checks content.
- Thinking cannot be disabled on Opus 5.5; depth is set with `effort`
  (`medium`, explicit; the eval may test `low`).
- Token usage is read from `response.usage` and stored.

### Prompt outline (French, starting point for the eval)

Write the intro and conclusion of the Perrin family's monthly film summary.
Numbers and rankings are already written elsewhere: write no digits. Only
mention the films, people and comments provided. Put every title in
«guillemets», exactly as written in the data. Warm, funny, a few emojis. End
with a question that makes people want to talk. Don't reuse jokes from
`deja_ecrit`. Adapt to the tier.

## Validation (`validate.py`)

1. Every «…» title is one of the month's titles (case-insensitive).
2. Every `names_mentioned` is the first name of someone who rated that month.
3. `titles_mentioned` matches the «…» extracted from the text.
4. No digits outside «…» (so «Blade Runner 2049» passes).
5. Length within the tier's range (starting values: `aucun` 80–400,
   `leger` 150–500, `complet` 300–900 characters; tuned in the eval).
6. At least one emoji and one `?`.
7. `difflib.SequenceMatcher` ratio < 0.6 against each previous colour text.
8. Tier `aucun`: no «…» at all.

Language, humour and tone are judged by a human during the eval.

## Retry and fallback

- On validation errors: a new standalone request with the payload, the
  rejected draft and the error list ("Corrige exactement ceci : …"). It does
  not replay the conversation, which avoids carrying thinking blocks between
  turns.
- At most 2 retries (3 attempts). Then fall back to the factual bullets plus a
  fixed AI-free sentence for the tier, with `used_fallback = true`.
- API errors: the SDK retries twice; if it still fails, same fallback.
  The family always gets a summary.

## Delivery

- Subject: `Résumé Perrin-rama: Sept'26` (abbreviations Janv, Févr, Mars, Avr,
  Mai, Juin, Juil, Août, Sept, Oct, Nov, Déc).
- Body: the full message to proofread, then a link
  `https://wa.me/?text=<url-encoded message>` labelled "Envoyer sur WhatsApp".
- Sent with `smtplib` from a dedicated Gmail account using an app password.
- The message stays under ~1,500 characters; the real `wa.me` limit is checked
  on a phone during the first live test.

## Workflow

- Cron `17 12 1 * *` (08:17 New York in summer, 07:17 in winter; off the hour
  because GitHub delays jobs scheduled on the hour).
- `workflow_dispatch` inputs: `month` (e.g. `2026-09`) and `dry_run` (print to
  the log; no email, no insert).
- Secrets: `DATABASE_URL` (existing), `ANTHROPIC_API_KEY`, `SMTP_USER`,
  `SMTP_APP_PASSWORD`, `SUMMARY_TO` (kept secret so the address isn't public).
- `SUMMARY_MODEL` is a plain env value in the workflow.
- New pinned dependency: `anthropic` (brings `pydantic`).
- If the run crashes, GitHub's failed-workflow email is the alert.
- Anthropic console: a dedicated API key and a monthly spend limit.

## Testing

Unit tests (`unittest`, no network, in CI):

- `facts`: tier boundaries 0/1/5/6; Paris->UTC boundaries including a DST
  month; fewer than 3 films; ties; multi-genre strings.
- `render`: each tier; subject format; all 12 abbreviations; fallback text.
- `validate`: every check both passing and failing; digits inside «…»; a
  translated title is rejected; similarity just under and just over 0.6.
- `service` (fake writer and sender): pass first try; pass on retry; three
  failures -> fallback; API error -> fallback; month already stored -> no send.
- `delivery`: `wa.me` link decodes back to the identical message; length limit.

## Eval

Run manually by Joseph with a local API key (never in CI: costs money).

1. `run_evals.py --set dev` runs the 7 dev cases (empty month, one film, big
   month, tie, title with digits, non-Latin original title, history containing
   a joke that must not return).
2. The report lists each message, the automatic check results, total tokens
   and cost, and a blank human score (1–5) for humour and tone.
3. Joseph scores the outputs; one prompt change per round; one commit per
   round, with the dev pass rate and average score in the message.
4. Stop when the dev set passes every automatic check on two consecutive runs
   and the human score has plateaued.
5. Run `--set holdout` once. A drop means the prompt was tuned to the
   examples rather than the task.
6. Optionally compare `claude-sonnet-5-5` on the same cases, and keep the
   cheaper model if quality is tied.

Estimated cost: about $0.60 per dev run, about $3 for the whole tuning.

## Out of scope

- Sending to WhatsApp automatically.
- An LLM judge for humour (10 cases are better judged by a human).
- Vertex AI / Google Cloud (possible later exercise; only `writer.py` changes).
- Sub-projects #2 (recommendations) and #3 (logging past viewings).
