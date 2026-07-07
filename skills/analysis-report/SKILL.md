---
name: analysis-report
version: "1.0.0"
description: |
  Assembles a distributable APA-style Markdown report from a concluded analysis.
  Reads the design, Insight Journal, notebook verdict, and figure manifest — a read-only
  consumer that lays out Abstract / Introduction / Method / Results / Discussion / References
  so results can be explained to others with only light hand-editing.
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
Journal, the notebook verdict (`{id}_verdict.json`, including its `figures[]` manifest), and
the figure PNGs — and assembles them. It never re-runs the notebook and never edits the
design. Figure captions come from the notebook's `figures[]` manifest (the producer owns the
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
- You need a `.docx` / `.pdf` — this skill emits Markdown; convert it downstream yourself

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
   `referenced_knowledge`.
2. `.insight/designs/{design_id}_journal.yaml` (Read tool): `observe` / `evidence`
   (with `metadata.direction`) / `question` (open ones) / `conclude` events.
3. `.insight/notebooks/{design_id}_verdict.json` (Read tool): `conclusion`,
   `evidence_summary`, `open_questions`, `metrics`, and `figures[]`.
   - If the file or `figures` is absent (analysis predates the figure contract), treat it
     as `figures = []` and **graceful degrade**: omit the figure block, add one line noting
     figures were not produced (re-run /analysis-notebook to include them).

### Step 3: Assemble the report

Build the Markdown per [references/apa-template.md](references/apa-template.md) — English APA
headings, narrative in the user's language:

- **Abstract** — the conclusion in a few sentences (from the `conclude` event + verdict).
- **Introduction** — `hypothesis_statement` + `hypothesis_background`.
- **Method** — `methodology` (method / package / reason / steps) + `metrics` + `explanatory`.
- **Results** — `observe`/`evidence` narrative + a numbers table from `verdict.metrics`
  + **Figures**: for each `figures[]` entry, embed the PNG and its **Axes（軸の説明）** and
  **How to read（図の読み方）** caption verbatim from the manifest. Both are mandatory.
- **Discussion → Limitations / Future Directions** — `conclude` limits + open `question`s.
- **References** — `referenced_knowledge` if any; omit the section entirely when empty.

### Step 4: Write and hand off

1. Write the assembled Markdown to `.insight/reports/{design_id}.md`
   (create `.insight/reports/` if missing). This is the only file this skill writes.
2. Show the path and note: "配布用レポートを生成した。わずかな手直しで配布できる。
   `.docx`/PDF 化は別途変換を"。

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details + read the status for the terminal-status guard |

This skill uses `design_io` read-only. It does not `update` or `transition` the design.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-reflection | → /analysis-report | Conclusion reached (terminal status); build a distributable report |
| /analysis-auto | → /analysis-report | autopilot reached the conclusion; offer the report at the end (KEEP gate) |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Report **headings are English (APA standard)**; the narrative body follows the user's
  language (usually Japanese).
