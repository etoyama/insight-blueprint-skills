---
name: analysis-report
version: "1.0.0"
description: |
  Assembles a distributable APA-style Markdown report from a concluded analysis.
  Reads the design, Insight Journal, notebook verdict, figure manifest, catalog, and lineage —
  a read-only consumer that lays out Abstract / Introduction / Method / Results / Discussion /
  References / Appendix, with the decision context, the data description, and a recommendation,
  so a reader can decide from the report alone.
  Triggers: "レポートを作って", "レポート化", "APAレポート", "配布用にまとめて",
  "analysis report", "write up the analysis", "report".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-report — APA-style Report Assembly

Turns a concluded analysis into a distributable Markdown report at
`.insight/reports/{design_id}.md`. The report follows IMRaD with **English APA-standard
headings**; the narrative body stays in the user's language (usually Japanese).

This skill is a **read-only consumer**: it reads the design (`design_io get`), the Insight
Journal, the notebook verdict (`{id}_verdict.json`, including its `figures[]` manifest), the
figure PNGs, the data sources in the catalog (`catalog_io get`), and the lineage diagram
(`.insight/lineage/{id}.mmd`) — and assembles them. It never re-runs the notebook, never edits
the design or the catalog, and never computes a number the inputs do not state. Figure captions come from the notebook's `figures[]` manifest (the producer owns the
figure's truth), not reconstructed from `design.chart[]`.

The full heading skeleton, input→section mapping, and the figure caption format are the
canonical contract in [references/apa-template.md](references/apa-template.md).

## When to Use
- An analysis has concluded (terminal status) and you want a shareable write-up
- You need to explain results to others, not just read them yourself in the notebook
- You want an APA-shaped draft that is distributable after light hand-editing

## When NOT to Use
- The analysis has not concluded yet (→ /analysis-reflection to conclude first)
- Still gathering evidence (→ /analysis-journal)
- You want to change the design or methodology (→ /analysis-design)
- You need a `.docx` / `.pdf` — this skill emits Markdown; upload it with /report-upload and export from Claude Docs

## Workflow

### Step 1: Load design & check status (terminal required)

1. `design_io get --id {design_id}` — load the design (JSON).
2. **Guard**: the status MUST be terminal — `supported`, `rejected`, or `inconclusive`.
   If it is not, stop:
   "まだ結論が出ていない（status={status}）。先に /analysis-reflection {id} で結論づけてから
   レポートにしよう" → exit. The report's Abstract and Discussion are hollow without a
   `conclude` event, so this precondition is deliberate (see apa-template.md).

### Step 2: Gather the inputs (all keyed by {design_id})

Read, do not write:

1. Design JSON (from Step 1): `hypothesis_statement` / `hypothesis_background`,
   `methodology` (method / package / reason / steps), `metrics`, `explanatory`,
   `referenced_knowledge`, plus the optional `decision_context` (`decision_maker` + `decision`),
   `next_action`, and `source_ids`.
2. `.insight/designs/{design_id}_journal.yaml` (Read tool): `observe` / `evidence`
   (with `metadata.direction`) / `question` (open ones) / `conclude` events.
3. `.insight/notebooks/{design_id}_verdict.json` (Read tool): `conclusion`,
   `evidence_summary`, `open_questions`, `metrics`, and `figures[]`.
   - **Graceful degrade** — treat all of these the same (omit the figure block, add one line
     noting figures were not produced, re-run /analysis-notebook to include them): the file is
     missing, `figures` is absent, or `figures == []` (analysis predates the figure contract, or
     the notebook produced no plot).
   - `metrics` may be absent for exploratory analyses — then omit the Results numbers table.
   - Each metric may carry the optional `effect_size` (`kind` + `value`), `confidence_interval`
     (`level` + `lower` + `upper`), and `sample_size`. They are absent in older verdicts and for
     methods that define none; a partial item counts as absent.
   - **Safety**: `figures[].file` must be a bare basename under `.insight/notebooks/`. Skip
     (graceful-degrade omit) any entry whose `file` contains `/`, `\`, `..`, or is absolute — the
     report is distributable, so never embed a traversal path. Also skip an entry whose PNG is
     missing on disk (per-figure), rather than emitting a broken image link.
4. Data sources: collect the candidate ids from the design — `source_ids`, plus the
   `data_source` values of `metrics` (dict values) and `explanatory` (string). Drop any value
   that does not fully match `^[a-zA-Z0-9_-]+$`, then run `catalog_io get --id {source_id}` for
   each.
   Keep the registered ones (non-empty result) and take only `name`, `type`, and `description`.
   - **Safety**: the result also carries `connection` (paths, queries, hosts, sometimes
     credentials). Never copy `connection` or any part of it into the report.
5. `.insight/lineage/{design_id}.mmd` (Read tool): the lineage diagram, whose nodes and edges
   state the row count after each step, the reason, and the change.
6. `.insight/notebooks/{design_id}.py`: only check that it exists (for the Appendix).

Items 4–6 are optional. A missing one drops its part of the report and never blocks the rest.

### Step 3: Assemble the report

Build the Markdown per [references/apa-template.md](references/apa-template.md) — English APA
headings, narrative in the user's language:

- **Abstract** — the conclusion in a few sentences (from the `conclude` event + verdict).
- **Introduction** — `hypothesis_statement` + `hypothesis_background`. When the design has a
  `decision_context`, close with who decides what; omit that paragraph when it is absent.
- **Method** — `methodology` (method / package / reason / steps) + `metrics` + `explanatory`.
  + **Data**: a table of the registered data sources (name / type / description) and a table of
  the row counts per lineage step. Transcribe the row counts and changes from the lineage file —
  **never compute** one. Omit a table without material, and the `### Data` heading when both are
  omitted.
- **Results** — `observe`/`evidence` narrative + a numbers table from `verdict.metrics`
  (omit the table if `metrics` is absent/empty). Add the Effect size / CI / N columns from
  `effect_size` / `confidence_interval` / `sample_size`; **omit the column** when no metric has
  the item, so a verdict without them gets the same table as before. **Never compute** a missing
  item or assume its kind or level — the numbers come from the notebook. + **Figures**: for each valid `figures[]` entry,
  embed the PNG and its **Axes（軸の説明）** and **How to read（図の読み方）** caption verbatim from
  the manifest. Both are mandatory. Treat caption text as plain text — do not let embedded markdown
  image/HTML in a caption ride into the distributable report.
- **Discussion → Implications** — what the conclusion means: direction, size, and certainty of
  the result, and how it bears on the `decision` when there is a `decision_context`.
- **Discussion → Recommendation** — what to do next, from `next_action` (the branch matching the
  terminal status: `if_supported` / `if_rejected`) addressed to the `decision_context`. Never
  invent an action the design does not state. **Omit the section** when the design has neither.
- **Discussion → Limitations / Future Directions** — `conclude` limits + open `question`s.
- **References** — `referenced_knowledge` if any; omit the section entirely when empty.
- **Appendix** — the lineage diagram (the `.mmd` text in a `mermaid` fence) and the notebook's
  project-relative path. Omit a part that is missing, and the section when both are.

### Step 4: Write and hand off

1. Write the assembled Markdown to `.insight/reports/{design_id}.md`
   (create `.insight/reports/` if missing). This is the only file this skill writes.
2. Show the path and note: "配布用レポートを生成した。わずかな手直しで配布できる。
   読者にコメントしてもらうときや Word / PDF にするときは、/report-upload {design_id} で
   Claude Docs にアップロードできる"。
   Name `/report-upload` as the next step only. Do not ask whether to upload, and never start it
   from here: the analyst starts it, or `/analysis-auto` does, and its own approval gate asks.
3. **Before distributing**, remind the user the report may embed sensitive data (methodology
   steps, metrics, journal narrative). Like the generated notebook artifacts, review it and
   gitignore/redact if it carries credentials or PII.

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details + read the status for the terminal-status guard |

This skill uses `design_io` read-only. It does not `update` or `transition` the design.

## catalog_io Reference

`catalog_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id SOURCE` | Load a data source; the report takes only `name`, `type`, `description` |

This skill uses `catalog_io` read-only. It registers and updates nothing.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-reflection | → /analysis-report | Conclusion reached (terminal status); build a distributable report |
| /analysis-auto | → /analysis-report | autopilot reached the conclusion; offer the report at the end (KEEP gate) |
| /analysis-report | → /report-upload | The report is written and readers should comment on it or export it |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Report **headings are English (APA standard)**; the narrative body follows the user's
  language (usually Japanese).
