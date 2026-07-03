---
name: analysis-notebook
version: "1.0.0"
description: |
  Generates a marimo notebook from an analysis design's methodology, runs it headlessly,
  and records the results to the Insight Journal. Turns a reviewed/approved design into an
  executed, lineage-tracked analysis. Fills the design→analysis step (successor to the
  removed batch-analysis, now interactive).
  Triggers: "notebook を作って分析", "分析を実行", "ノートブック生成", "run analysis",
  "generate notebook", "分析ノートブック".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-notebook — Analysis Notebook (generate + run + record)

Turns a design's `methodology` into an executable **marimo notebook** (fixed 8-cell
contract), runs it headlessly, and records the findings to the design's Insight Journal.
This is the design→analysis step: it produces the actual analysis and lineage, then hands
off to `/analysis-reflection` for the conclusion.

The full cell contract, marimo rules, execution commands, and verdict→journal mapping live
in **[references/notebook-contract.md](references/notebook-contract.md)** — read it before generating.

## When to Use

- A design is reviewed/approved and you want to run the analysis it specifies
- You need a reproducible, lineage-tracked marimo notebook from the design's methodology

## When NOT to Use

- Concluding the hypothesis from the results (-> /analysis-reflection). This skill records
  observations/evidence/questions, never a conclusion.
- Creating or editing the design (-> /analysis-design)
- Only recording reasoning by hand without running a notebook (-> /analysis-journal)

## Prerequisites

The notebook imports pandas / matplotlib / numpy + `insight_blueprint.lineage`, and is run
with marimo. Check them and offer to install the `notebook` extra if missing:

```bash
uv run python -c "import marimo, pandas, matplotlib, numpy, insight_blueprint.lineage" \
  || uv add "insight-blueprint-lineage[notebook]"
```

Methodology-specific libraries (e.g. scikit-learn, statsmodels) are added per analysis with
`uv add <pkg>`. The source must be registered in the catalog (else -> /catalog-register).

## Workflow

### Step 1: Load the design & check status

1. Identify the design: `$ARGUMENTS`, else `uv run python -m skills._shared.design_io list --status analyzing`.
2. `uv run python -m skills._shared.design_io get --id {design_id}` — read methodology / intent / source.
3. Status: needs `analyzing`. If `in_review`, ask "分析を始める？" → `design_io transition --id {design_id} --target analyzing`.
   (Terminal statuses can't be analyzed.)

### Step 2: Gather source schema

`uv run python -m skills._shared.catalog_io get-schema --id {source_id}` for column names/types
and the connection (CSV path / SQL). If the source is unregistered, stop and suggest /catalog-register.

### Step 3: Generate the notebook

Write `.insight/notebooks/{design_id}.py` following the **8-cell contract** (see references).
Drive cell content from the design:

- cell 1 (meta): `title` / `id` / `hypothesis_statement` / `analysis_intent`
- cell 2 (data_load): source connection → `pd.read_csv(...)` / SQL; init `LineageSession`
- cell 3 (data_prep): methodology-independent cleaning, each step via `tracked_pipe`
- cell 4 (analysis): from `methodology.method` + `methodology.steps` (code patterns) + `analysis_intent`;
  build the `results` dict with the required direction fields
- cell 5 (viz): from `chart[]` (type/description)
- cell 6 (verdict): build `verdict` and persist `.insight/notebooks/{design_id}_verdict.json`
- cell 7 (lineage): `export_lineage_as_mermaid(session, project_path=".")`

### Step 4: Run it headlessly

```bash
uv run marimo export script .insight/notebooks/{design_id}.py -o .insight/notebooks/{design_id}_flat.py
uv run python .insight/notebooks/{design_id}_flat.py
```

This executes the cells, writing `{design_id}_verdict.json` and `.insight/lineage/{design_id}.mmd`.
(Optional viewable report: `uv run marimo export html .insight/notebooks/{design_id}.py -o .insight/notebooks/{design_id}.html`.)

### Step 5: Fix-and-rerun on failure

If execution errors, read the traceback, fix the offending cell in `{design_id}.py`, and
re-run Step 4. Keep it interactive — resolve with the user rather than looping blindly.

### Step 6: Record to the journal

Read `.insight/notebooks/{design_id}_verdict.json` and append `observe` / `evidence` /
`question` events to `.insight/designs/{design_id}_journal.yaml` per the verdict→journal
mapping (references). Preserve existing events; continue ids from the current max; **never emit `conclude`**.

### Step 7: Hand off

- "結論づけは /analysis-reflection {design_id}"
- "lineage 図: `.insight/lineage/{design_id}.mmd`（再出力は /data-lineage）"

## design_io / catalog_io Reference

| Command | Used for |
|---------|----------|
| `design_io list --status analyzing` | Find designs ready to analyze |
| `design_io get --id ID` | Load methodology / intent / source |
| `design_io transition --id ID --target analyzing` | Move an in_review design into analysis |
| `catalog_io get-schema --id SOURCE` | Column schema + connection for data_load |

Journal is appended by writing `.insight/designs/{id}_journal.yaml` directly (same as
/analysis-journal) — there is no journal CLI subcommand.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-design | -> /analysis-notebook | Design ready to analyze: "分析を実行するなら /analysis-notebook {id}" |
| /analysis-review | -> /analysis-notebook | Design approved (analyzing): "分析を実行するなら /analysis-notebook {id}" |
| /analysis-notebook | -> /analysis-journal | Add manual reasoning beyond the auto-recorded events |
| /analysis-notebook | -> /analysis-reflection | Results in: "結論づけは /analysis-reflection {id}" |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Notebook narrative / journal content follows the user's language (usually Japanese).
