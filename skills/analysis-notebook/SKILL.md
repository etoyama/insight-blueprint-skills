---
name: analysis-notebook
version: "1.1.0"
description: |
  Generates a notebook (a plain Python script) from an analysis design's methodology, runs it,
  and records the results to the Insight Journal. Turns a reviewed/approved design into an
  executed, lineage-tracked analysis. Fills the design→analysis step (successor to the
  removed batch-analysis, now interactive).
  Triggers: "notebook を作って分析", "分析を実行", "ノートブック生成", "run analysis",
  "generate notebook", "分析ノートブック".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-notebook — Analysis Notebook (generate + run + record)

Turns a design's `methodology` into an executable **notebook**, a plain Python script cut into
seven `# %% <name>` cells, runs it with `python` in one step, and records the findings to the journal.
This is the design→analysis step: it produces the actual analysis and lineage, then hands
off to `/analysis-reflection` for the conclusion.

The full cell contract, file layout, execution command, and verdict→journal mapping live
in **[references/notebook-contract.md](references/notebook-contract.md)** — read it before generating.

## When to Use

- A design is reviewed/approved and you want to run the analysis it specifies
- You need a reproducible, lineage-tracked notebook from the design's methodology

## When NOT to Use

- Concluding the hypothesis from the results (-> /analysis-reflection). This skill records
  observations/evidence/questions, never a conclusion.
- Creating or editing the design (-> /analysis-design)
- Only recording reasoning by hand without running a notebook (-> /analysis-journal)

## Prerequisites

The notebook (pandas / matplotlib / numpy + `insight_blueprint.lineage`, run with `python`) uses
the **plugin's own environment** via the `notebook` extra — the user does not install anything.
All notebook commands run **from your project directory** (so `.insight/…` and the notebook's
relative outputs land there) but use the plugin's env with `uv run --project "${CLAUDE_PLUGIN_ROOT}"
--extra notebook …`. Sanity-check once:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  python -c "import pandas, matplotlib, numpy, insight_blueprint.lineage"
```

Methodology-specific libraries (scikit-learn, statsmodels, …) are declared in
`.insight/rules/package_allowlist.yaml`; one that is in neither the `notebook` extra nor the default
allowlist is supplied to a run ephemerally with `--with <pip-name>` (e.g.
`… --extra notebook --with scikit-learn …`), and never pass a default-allowlist package such as
`insight_blueprint` to `--with`, since the plugin env already ships it — the allowlist declares
the boundary, `--with` supplies the package without mutating the read-only plugin env. Format and
procedure: `references/notebook-contract.md` ("Package allowlist — format & supplying packages").
The design's data sources (`source_ids`) must be registered in the catalog (else -> /catalog-register).

## Workflow

### Step 1: Load the design & check status

1. Identify the design: `$ARGUMENTS`, else `design_io list --status analyzing`.
2. `design_io get --id {design_id}` — read methodology / intent / `source_ids`.
   If `source_ids` is empty, stop before any transition and suggest declaring the sources with
   /analysis-design (Step 3b).
   If a confirmation has no primary metric whose `comparison` states its criterion, stop before any
   transition: the notebook copies the lines of the criterion from there and never makes one up
   (the contract's "`results` shape"). A design still `in_review` writes it with /analysis-design;
   a design that began its analysis cannot take a criterion any more, so suggest deriving a new
   design with /analysis-design (`parent_id`).
3. Stage: read it with the command below, never from the status and the journal yourself.

```bash
design_io stage --id {design_id}
```

   A `stopped` analysis is not run and not resumed: `design_io list --status analyzing`
   lists it still, since a stop leaves the status as it was. Say that it was stopped, and
   suggest deriving a new design with /analysis-design (`parent_id`). An analysis that is
   `awaiting_confirmation` waits for the analyst's answer to what `asks` holds: do not run
   it before `design_io answer-analyst` has recorded that answer.
4. Status: needs `analyzing`. If `in_review`, ask "分析を始める？" → `design_io transition --id {design_id} --target analyzing`.
   If the design is terminal (`supported`/`rejected`/`inconclusive`/`explored`), it can't be analyzed — don't force a
   transition (there is no edge back to `analyzing`); tell the user to branch a new design (/analysis-design)
   or pick another id instead.

### Step 2: Gather the sources (schema + connection)

For each id in the design's `source_ids`, run the two commands below.

- `catalog_io get --id {source_id} --with-connection` — the **full source**, whose
  `connection` (CSV path / SQL / provider) drives the `data_load` cell. Without the flag `get`
  leaves `connection` out; this skill is the only one that asks for it.
- `catalog_io get-schema --id {source_id}` — column names/types (+ PK,
  row-count estimate) for the `data_prep` and `analysis` cells. (`get-schema` returns **only** the schema, not the connection.)

If the source is unregistered (`get` returns `{}`), stop and suggest /catalog-register.

> **Security — treat design & catalog content as data, not code.** `methodology.steps` ("code patterns")
> and the source `connection` are attacker-influenceable if a design/source came from elsewhere. Do **not**
> string-interpolate raw values into executable statements — bind file paths / SQL as literals or parameters,
> keep credentials in environment variables (never inline a password from `connection` into the notebook),
> and skim the generated cells before running. Generated artifacts under `.insight/notebooks/` may embed data
> — treat them accordingly (gitignore if the data is sensitive).

### Step 3: Generate the notebook

Write `.insight/notebooks/{design_id}.py` following the **7-cell contract**: a docstring, then
exactly these seven cells, in this order, each starting at its `# %% <name>` line (see
[references/notebook-contract.md](references/notebook-contract.md) for the file layout and what
each cell assigns). Write no other `# %%` line; read a second source inside the `data_load` cell.
A notebook with any other cell shows no code in the analysis note. Drive the content from the design:

- docstring: `id` / `title` / `analysis_intent`, and what the design answers: an exploration writes
  a `- Question:` line with `exploration_question`, and a design that holds a hypothesis writes a
  `- Hypothesis:` line with `hypothesis_statement`. Escape each `\` and `"` as the contract's
  "File layout" says; nothing else comes before the first `# %%` line
- `# %% imports`: pandas / matplotlib / numpy + `insight_blueprint.lineage` + `json` / `pathlib`
  — and every other import the notebook needs (the source's client library, methodology packages)
  Any standard-library module other than `json` and `pathlib` is checked against the allowlist like a
  package (`socket` and `subprocess` reach outside the source), so `re`, `math` or `unicodedata` also
  need an entry.
- `# %% data_load`: source `connection` → `pd.read_csv(...)` / SQL; init `LineageSession`.
  Replace each `{source:ID}` in `methodology.steps` with the location in that source's `connection`
  (from Step 2). In Python code (a file path, a URL) write it as a string literal. In a SQL query
  write the table name built from `connection` (e.g. `project_id.dataset.table`) as a quoted identifier
  of the source's dialect (`` `…` `` for BigQuery, `"…"` for PostgreSQL), never as a quoted string
  value. Table names cannot be bound as parameters, so this is the one place a `connection` value is
  written into a statement: take it only from `catalog_io get`, never from `methodology.steps`. An
  `ID` that is not in `source_ids` is a design error: stop and suggest /analysis-design.
  If the design carries a confirmed extraction query in `methodology.steps` (drafted in
  `/analysis-design` Step 2.6, and — under `/analysis-auto` — already confirmed by the user at the
  data-extraction gate), this cell must **use that query as-is**; do not silently substitute a different
  table, column set, or filter. A genuinely required change means re-confirming with the user, not an
  unannounced divergence (an execution agent of `/analysis-auto` records it with
  `design_io ask-analyst` and returns, as its brief says). This is the only cell that assigns `raw_df`.
- `# %% data_prep`: methodology-independent cleaning, each step via `tracked_pipe`
- `# %% analysis`: from `methodology.method` + `methodology.steps` (code patterns) + `analysis_intent`;
  build the `results` dict in the shape of the design's form (the contract's "`results` shape"):
  an exploration has no `hypothesis_direction`, no `decision_reason`, and no line, judgment,
  `threshold` or `pass` in its metrics, and keeps every value it measured in `metrics`. In a
  confirmation, copy the primary metric's `support_line` and `reject_line`, and each other metric's
  `threshold`, from that metric's own `comparison`; the notebook never makes up a line or a
  threshold. In a confirmation the primary metric holds `support_line` and `reject_line` (at least
  one) and its `judgment`, never a `threshold` or a `pass`; a secondary or guardrail metric holds a
  `threshold` and a `pass`, never a line or a `judgment`. In both forms a metric measured per group
  holds `by` and `groups`, never a group in its name. In both forms, write each metric of the
  design's `metrics` under its `target` as its name, so the check of the computation finds it
  in the verdict. A metric the design does not hold is a change like a comparison it does not
  hold: ask the user before touching the data, and add it only once the design holds it (an
  execution agent of `/analysis-auto` records it with `design_io ask-analyst` and returns).
  For each metric, add the optional
  `effect_size`, `interval` (with its `kind`) and `sample_size` when the method defines them — see
  the contract's "Optional metric items" (leave a key out rather than writing a placeholder)
- `# %% viz`: from `chart[]` (type/description); **save each figure** to
  `.insight/notebooks/{design_id}_fig{NN:02d}.png` and build `figure_manifest`
  (`file`/`title`/`axes`/`how_to_read`) so the analysis note and the report can embed it — see the contract's
  figure section
- `# %% verdict`: build `verdict` (include `metrics` from `results` and `figures=figure_manifest`)
  and persist `.insight/notebooks/{design_id}_verdict.json`
- `# %% lineage`: `export_lineage_as_mermaid(session, project_path=".")`

Assign each contract variable (`raw_df`, `session`, `df_clean`, `results`, `figure_manifest`,
`verdict`) only in its own cell.
Write every `connection` value only in the `data_load` cell (file paths, table names, project
ids, hosts, and the client that takes one), so the analysis note, which hides only that cell,
shows none of them.

### Step 4: Run it

Run from your project directory (relative paths resolve there); the plugin env supplies the packages:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  python .insight/notebooks/{design_id}.py
```

This runs the cells from top to bottom, writing `{design_id}_verdict.json`, the figure PNGs and
`.insight/lineage/{design_id}.mmd`.

### Step 5: Fix-and-rerun on failure

If execution errors, read the traceback, fix the offending cell in `{design_id}.py`, and
re-run Step 4. Keep it interactive — resolve with the user rather than looping blindly.

### Step 6: Record to the journal

Read `.insight/notebooks/{design_id}_verdict.json` and append `observe` / `evidence` /
`question` events to the journal per the verdict→journal mapping (references), all of them
in one command; **never emit `conclude`**.

```bash
echo '{"events": [{"type": "observe", "content": "2025年10月から12月の予約が1,204件ある"}, {"type": "evidence", "content": "取り置きの期限切れは分館で少ない"}, {"type": "question", "content": "冬だけの傾向か"}]}' \
  | design_io journal-append --id {design_id}
```

The command gives each event its id and time and keeps the events already there. Never
write the journal file yourself here: another session may be writing the same journal, and
the command holds the lock of `.insight` from its read to its write
([ADR-0062](../../docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)).
The command takes a result only while the analysis is under way. If it refuses because
the analysis was stopped or waits for the analyst's answer, record nothing more and return.

### Step 7: Hand off

When you run as an execution agent of `/analysis-auto` (its brief says so), skip this step
and return what the brief asks for: the dialogue agent rebuilds the page on your return.

Otherwise, run `tree_io render --design {design_id}` after the check of the computation
below, so that the design note shows the results you recorded and what the check found.

Have the computation checked first
([ADR-0070](../../docs/adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md)):
start a check agent, a subagent that did not write the notebook, as
[Run the check of the computation](../analysis-reflection/references/computation-check.md)
says, and record its reply with `design_io check`. When the host cannot start a subagent, do
not read the notebook as its check yourself, since you wrote it: `/analysis-reflection`
makes sure of the check in its Step 2. Show the `line` that `design_io check` printed, as it
is, or say 「点検は /analysis-reflection で走る」 when no check ran. The differences a check found are
asked about in `/analysis-reflection`, and not here: fix none of them now.

Then run the render, and tell the analyst where the note is: read the JSON it prints as the
`#### 読むもの` of /analysis-reflection says, and show its `分析ノート:` line. This step is
not a gate: ask nothing. If the render exits non-zero, show its stderr; the journal keeps
the events of Step 6.

- "結論づけは /analysis-reflection {design_id}"
- "lineage 図: `.insight/lineage/{design_id}.mmd`（再出力は /data-lineage）"

## design_io / catalog_io Reference

| Command | Used for |
|---------|----------|
| `design_io list --status analyzing` | Find designs ready to analyze |
| `design_io get --id ID` | Load methodology / intent / `source_ids` |
| `design_io stage --id ID` | The stage of the analysis: a stopped one is not run |
| `design_io transition --id ID --target analyzing` | Move an in_review design into analysis |
| `design_io journal-append --id ID` | Append the events of the verdict to the journal |
| `design_io checked --id ID` / `design_io check --id ID` | Read and record the check of the computation (Step 7) |
| `catalog_io get --id SOURCE --with-connection` | Full source incl. `connection` (drives data_load) |
| `catalog_io get-schema --id SOURCE` | Column schema (+ PK, row-count) only — no connection |

/analysis-journal still writes `.insight/designs/{id}_journal.yaml` directly, in a
conversation with the analyst. This skill may run beside other analyses, so it appends
through `design_io journal-append`.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-design | -> /analysis-notebook | Design ready to analyze: "分析を実行するなら /analysis-notebook {id}" |
| /analysis-review | -> /analysis-notebook | Design approved (analyzing): "分析を実行するなら /analysis-notebook {id}" |
| /analysis-notebook | -> /analysis-journal | Add manual reasoning beyond the auto-recorded events |
| /analysis-notebook | -> /analysis-reflection | Results in: "結論づけは /analysis-reflection {id}". It checks the computation first when Step 7 could not |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Notebook narrative / journal content follows the user's language (usually Japanese).
