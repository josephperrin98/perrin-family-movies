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
