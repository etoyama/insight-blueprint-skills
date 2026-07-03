---
name: premortem
description: |
  Report-only pre-flight cost/risk evaluation for analysis designs.
  Before expensive data access, evaluates each design (source registered? BigQuery
  location ok? methodology packages allowed? estimated rows?) and prints a risk
  table (HARD_BLOCK / HIGH / MEDIUM / LOW / SKIP). Issues no token and writes nothing.
  Triggers: "premortem", "事前チェック", "実行前チェック", "リスク判定",
  "pre-flight check", "run premortem".
disable-model-invocation: true
argument-hint: "[--design <id>]"
---

# /premortem -- Pre-flight Risk Evaluation (report-only)

Standalone skill that evaluates analysis designs against a deterministic, static
risk decision tree (HARD_BLOCK / HIGH / MEDIUM / LOW / SKIP) and prints a report.
It does **not** issue tokens, gate execution, or write to disk — it advises.

## When to Use

- Before expensive data access, to see the cost/risk of the designs you're about to run
- To check risk levels of designs without executing them

## When NOT to Use

- Creating or editing designs (-> /analysis-design)
- Reviewing completed results (-> /analysis-reflection)

## Workflow

1. **Collect design data** (Claude Code responsibility):
   - `design_io list` to enumerate designs
     (use `--design <id>` to scope to one).
   - For each design: `design_io get --id <id>`, then build `source_checks_map` from
     `catalog_io get-schema --id <source_id>` / `catalog_io search --query <source_id>`
     and `.insight/rules/package_allowlist.yaml` (source registered? location ok?
     packages allowed? estimated rows?).
   - Pipe `{ "designs": [...], "source_checks_map": {...} }` as JSON to cli.py stdin.

2. **Evaluate** (pure static decision engine):
   ```bash
   echo '{ "designs": [...], "source_checks_map": {...} }' | premortem   # reads stdin, prints table
   ```
   `premortem` (on PATH via the plugin) reads the JSON payload on stdin, prints one line per
   design (id / intent / est_rows / strategy / risk / reasons), and exits 2 if any design is
   HARD_BLOCK/HIGH, else 0.

3. **Present** the risk table to the user and advise on next steps (e.g. fix
   HARD_BLOCK designs, reconsider HIGH ones before running). No token, no gating.

## Risk Levels (static)

| Level | Trigger | Suggested action |
|-------|---------|------------------|
| `HARD_BLOCK` | Unregistered source, allowlist violation, or BigQuery location mismatch | Don't run this design; fix it (`/analysis-design`) first |
| `HIGH` | `estimated_rows` > `static_rows_high`, or a source check errored (location/allowlist `null`) | Reconsider before expensive access |
| `MEDIUM` | `estimated_rows` > `static_rows_medium` | Proceed with awareness |
| `LOW` | Small/unknown row count, all checks pass | Happy path |
| `SKIP` | Terminal status (`supported` / `rejected` / `inconclusive`) | Not evaluated |

Thresholds live in `.insight/config.yaml` under `premortem.*`
(`static_rows_high`, `static_rows_medium`; see `.insight/config.example.yaml`).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No HARD_BLOCK / HIGH design |
| 2 | At least one HARD_BLOCK / HIGH design (warning signal) |
| 1 | Bad input (e.g. `--design` id not in payload) |

## Language Rules

- Respond to users in Japanese
- Code, IDs, tool names, and YAML fields stay in English
