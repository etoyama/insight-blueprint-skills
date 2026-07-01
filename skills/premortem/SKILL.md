---
name: premortem
description: |
  Pre-flight risk evaluation and approval token issuance for batch analysis designs.
  Evaluates queued designs against history-based extrapolation and static thresholds,
  then issues an approval token for /batch-analysis --approved-by.
  Triggers: "premortem", "事前チェック", "batch の承認", "リスク判定",
  "pre-flight check", "run premortem".
  Chains to: /batch-analysis --approved-by TOKEN
  evaluate-only (write-prohibition contract, AC-1.5).
disable-model-invocation: true
argument-hint: "[--queued | --design <id> | --all] [--yes] [--mode manual|review|auto]"
---

# /premortem -- Pre-flight Risk Evaluation

Standalone skill that scans queued (or specified) analysis designs, runs a
deterministic risk decision tree (HARD_BLOCK / HIGH / MEDIUM / LOW / SKIP),
and issues an approval token consumed by `/batch-analysis --approved-by TOKEN`.

## When to Use

- Before launching `/batch-analysis` to validate the queue
- When you want to check risk levels of designs without executing them
- As an automated gate in review / auto mode dispatched by the launcher

## When NOT to Use

- Creating or editing designs (-> /analysis-design)
- Executing batch analysis (-> /batch-analysis)
- Reviewing completed results (-> /analysis-reflection)

## Workflow

1. **Parse arguments** -- Claude Code invokes `skills/premortem/cli.py` via
   Python subprocess. The CLI expects design data as JSON on stdin (Claude Code
   gathers it via `design_io` / `catalog_io` and pipes the result).

2. **Collect design data** (Claude Code responsibility, before invoking cli.py):
   - `uv run python -m skills._shared.design_io list` and filter
     `next_action.type == "batch_execute"` (or use `--design <id>` / `--all` to select differently)
   - For each design: `design_io get --id <id>`, then build `source_checks_map` from
     `catalog_io get-schema --id <source_id>` and `catalog_io search --query <source_id>`
     (source registered? location/allowlist/rows)
   - Pipe the JSON payload to cli.py stdin

   > Note: the `batch_execute` selection is a remnant of batch-analysis (removed in E3.5);
   > premortem's self-standing redefinition is E5. cli.py itself is unchanged.

3. **Risk evaluation** (cli.py, pure decision engine):
   - For each design: `history_query.query()` + `risk_evaluator.evaluate()`
   - Render 1-line-per-design table to stdout
   - Apply mode logic (manual/review/auto) to decide approved vs skipped

4. **Interactive gate** (manual mode or review+HIGH):
   - Display `[s]kip / [e]dit / [a]bort / [c]ontinue` per HIGH design
   - HARD_BLOCK: `[c]ontinue` is NOT offered

5. **Token issuance**:
   - `token_manager.issue()` writes `.insight/premortem/{TIMESTAMP}.yaml`
   - stdout final line: `Launch with: /batch-analysis --approved-by {token_id}`

## Risk Levels

Every design is classified into one of five levels. The level determines
what the operator (or automation) should do next.

| Level | Trigger | Operator Action |
|-------|---------|-----------------|
| `HARD_BLOCK` | Unregistered source, allowlist violation, or BigQuery location mismatch. | Batch MUST NOT run this design. The `[c]ontinue` option is withheld; use `[s]kip`, `[e]dit` (fix the design), or `[a]bort` (stop the whole batch). |
| `HIGH` | History median × buffer exceeds `time_high_min` **or** `estimated_rows` exceeds `static_rows_high` **or** success rate over `history_min_samples` samples drops below `success_rate_high_threshold`. | manual mode: operator prompt (s/e/a/c). review mode: batch STOPS (exit 2). auto mode: batch RUNS with a `WARNING: HIGH risk executed without human approval` line appended to `summary.md`. |
| `MEDIUM` | Extrapolated time between `time_medium_min` and `time_high_min`. | Proceeds automatically in every mode. Logged for visibility. |
| `LOW` | Nothing above triggered, history is healthy. | Proceeds automatically. The happy path. |
| `SKIP` | Terminal status (`supported` / `rejected` / `inconclusive`) or `next_action` cleared. | Recorded as skipped with `skip_reason=terminal_status`; never enters the batch queue. |

Thresholds live in `.insight/config.yaml` under `premortem.*` (see
`.insight/config.example.yaml`). Change them there, not in code.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Token issued successfully, batch may proceed |
| 2 | review mode + HIGH detected, batch should stop |
| 1 | Unexpected error (config invalid, I/O failure, etc.) |

## Writing Contract (AC-1.5)

During `/premortem` execution, the following paths are NEVER written to:

- `notebook.py` / marimo session JSON
- `.insight/designs/*.yaml` / `.insight/designs/*_journal.yaml`
- `.insight/runs/*/*/manifest.yaml` / `.insight/runs/*/run.yaml`
- `.insight/catalog/**`

Only `.insight/premortem/` receives writes (approval token).

## Language Rules

- Respond to users in Japanese
- Code, IDs, tool names, and YAML fields stay in English
