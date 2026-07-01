---
name: data-lineage
version: "1.1.0"
description: |
  Track data transformation pipeline lineage in analysis notebooks/scripts.
  Wraps pandas pipe chains with tracked_pipe to record row count changes,
  generates Mermaid diagrams for pipeline visualization.
  Triggers: "lineage", "data lineage", "track transformations", "pipeline visualization",
  "リネージ", "変換追跡", "パイプライン可視化", "行数変化を確認".
disable-model-invocation: true
argument-hint: "[design_id] [setup|refactor]"
---

# /data-lineage — Pipeline Lineage Tracker

Track DataFrame transformation pipelines and visualize row count changes
using `insight_blueprint.lineage`.

## When to Use

- Setting up lineage tracking in a new notebook
- Exporting Mermaid diagrams from tracked pipelines
- Refactoring pipelines based on lineage analysis

## When NOT to Use

- Creating or managing analysis designs (-> /analysis-design)
- Recording reasoning steps (-> /analysis-journal)
- Registering data sources (-> /catalog-register)

## Prerequisites Check

### Step 0: Python Package Check (MUST run before Step 1)

1. Run: `python -c "from insight_blueprint.lineage import tracked_pipe; print('OK')"`
2. If output is "OK": proceed to Step 1
3. If ImportError or command fails:
   - Ask the user: "data-lineage の tracked_pipe を使うには insight-blueprint Python パッケージが必要です。`uv add insight-blueprint` を実行しますか？（分析パイプラインの透明性追跡に推奨）"
   - If user approves: run `uv add insight-blueprint`, then re-check import
   - If user declines: inform user that lineage tracking/export is unavailable without the package
   - If install fails: show error, suggest manual install with `pip install insight-blueprint`

> **Note**: All lineage features (`tracked_pipe`, `export_lineage_as_mermaid`) live in the
> `insight_blueprint.lineage` Python package — no MCP server involved.

## Workflow

### Mode A: Setup — `/data-lineage <design_id> setup`

Help the user add `tracked_pipe` to an existing notebook.

**Workflow:**

1. Confirm the target AnalysisDesign (if design_id provided, run
   `uv run python -m skills._shared.design_io get --id {design_id}`; empty `{}` = not found)
2. Locate the target notebook/script (ask the user if unclear)
3. Read the notebook and identify DataFrame transformation steps (`.pipe()`, filter,
   merge, join, dropna, assign, query, etc.)
4. For each transformation, suggest wrapping with `tracked_pipe`:

```python
from insight_blueprint.lineage import LineageSession, tracked_pipe

session = LineageSession(name="<pipeline_name>", design_id="<design_id>")

# Before:
df = df.dropna(subset=["price"])

# After:
df = df.pipe(tracked_pipe(
    lambda df: df.dropna(subset=["price"]),
    reason="price 欠損行を除外",
    session=session,
))
```

5. Add export call at the end of the notebook:

```python
from insight_blueprint.lineage import export_lineage_as_mermaid

export_lineage_as_mermaid(session, project_path=".")
# -> .insight/lineage/<design_id>.mmd
```

6. Suggest running the notebook to verify tracking works.

### Mode B: Export — `/data-lineage <design_id>`

Generate a Mermaid diagram from a tracked session. Default mode when no subcommand given.

**Workflow:**

1. Locate the notebook associated with the design
2. Check if `tracked_pipe` is already used in the code
   - If yes: run the notebook or relevant cells to populate the session,
     then call `export_lineage_as_mermaid`
   - If no: suggest running Mode A first
3. Display the generated Mermaid diagram to the user
4. Confirm the output file location (`.insight/lineage/<design_id>.mmd`)

### Mode C: Refactor — `/data-lineage <design_id> refactor`

Analyze lineage data and suggest pipeline improvements.

**Workflow:**

1. Locate the notebook and its lineage session
2. Run the notebook to get current step records
3. Analyze patterns and report findings:

**Improvement patterns to check:**

| Pattern | Condition | Suggestion |
|---------|-----------|------------|
| No-op step | `delta == 0` | Column add/rename — consider removing from tracked_pipe |
| Consecutive filters | Sequential filters on same column | Merge into single query |
| Large drop | `abs(delta) > 50%` of input rows | Review filter condition for correctness |
| Order optimization | Later step has higher reduction rate | Move high-reduction filters earlier |
| Redundant filter | Step removes 0 rows | Filter condition may be subset of prior step |

4. Present findings with specific code suggestions
5. After refactoring, re-run to verify lineage changes

## Output

- **Mermaid file**: `.insight/lineage/<design_id>.mmd` (or `<session_name>.mmd`)
- **Console**: Step-by-step summary with row counts

## API Reference

```python
from insight_blueprint.lineage import (
    LineageSession,      # Session container (one per pipeline)
    StepRecord,          # Immutable step record (Value Object)
    tracked_pipe,        # Wrapper for .pipe() chain tracking
    export_lineage_as_mermaid,  # Mermaid diagram generator
)
```

## Chaining

| From | To | When |
|------|-----|------|
| /data-lineage | → /analysis-journal | Lineage diagram generated: "リネージ結果を証拠として記録するなら /analysis-journal {id}" |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- The `reason` parameter in `tracked_pipe` may be written in Japanese.
