---
name: data-lineage
version: "1.2.0"
description: |
  Re-export and review the data-transformation lineage of a notebook that /analysis-notebook made.
  Re-runs .insight/notebooks/{id}.py in the plugin's env to regenerate the Mermaid diagram of
  row-count changes, and suggests pipeline refactors from it.
  Triggers: "lineage", "data lineage", "track transformations", "pipeline visualization",
  "リネージ", "変換追跡", "パイプライン可視化", "行数変化を確認".
disable-model-invocation: true
argument-hint: "[design_id] [refactor]"
---

# /data-lineage — Pipeline Lineage Tracker

Re-export and review the lineage of the notebook `/analysis-notebook` made for a design.
The lineage is the row count before and after each `tracked_pipe` step, drawn as a Mermaid diagram
by `insight_blueprint.lineage`.

## When to Use

- Regenerating `.insight/lineage/{id}.mmd` after the notebook or its data changed
- Reviewing the notebook's transformation steps for refactors

## When NOT to Use

- The notebook does not exist yet, or was not made by `/analysis-notebook` (-> /analysis-notebook)
- Creating or managing analysis designs (-> /analysis-design)
- Recording reasoning steps (-> /analysis-journal)
- Registering data sources (-> /catalog-register)

## Target

The only target is the notebook `/analysis-notebook` made: `.insight/notebooks/{id}.py`. Its
`data_prep` and `analysis` cells wrap every transform in `tracked_pipe`, and its `lineage` cell
writes `.insight/lineage/{id}.mmd`. The user installs nothing: the notebook runs in the plugin's
own env, like `/analysis-notebook` runs it.

If no design_id is given, list `.insight/notebooks/*.py` and ask the user which one; do not take
`refactor` as an id.

Check the target before any mode, from the project directory, in this order; stop at the first that
fails, so an id with no design never reaches a path or a shell command:

1. `design_io get --id {id}` returns the design (`{}` means there is no such design).
2. `.insight/notebooks/{id}.py` exists.
3. The file uses `tracked_pipe` (for example, `grep -q tracked_pipe .insight/notebooks/{id}.py`).

If any of the three checks fails (no design, no notebook file, or no `tracked_pipe`), or the user
asks for a `setup` subcommand (it was removed in 1.2.0), tell the user that `/data-lineage` only
takes the notebook `/analysis-notebook` made at `.insight/notebooks/{id}.py`, point them to
`/analysis-notebook {id}` (-> /analysis-notebook) to make or regenerate it, and **stop**. Do not add `tracked_pipe` to the file and do not run it.

## Running the notebook

Run from the project directory (so `.insight/…` resolves there) with the same command as
`/analysis-notebook`:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  python .insight/notebooks/{id}.py
```

A package of `.insight/rules/package_allowlist.yaml` that is in neither the `notebook` extra nor
the default allowlist is supplied with `--with <pip-name>`; never pass a default-allowlist package
such as `insight_blueprint` to `--with`, since the plugin env already ships it. Procedure:
`${CLAUDE_PLUGIN_ROOT}/skills/analysis-notebook/references/notebook-contract.md`
("Package allowlist — format & supplying packages").

A run executes every cell. It loads the data again and also rewrites
`.insight/notebooks/{id}_verdict.json` and the figure PNGs, as `/analysis-notebook` Step 4 does.
Tell the user this before the run. The journal events already recorded from the old verdict stay
as they are; to record the new verdict, use `/analysis-notebook {id}`.
If the run fails, show the traceback and hand off to `/analysis-notebook {id}` to fix the notebook.

## Workflow

### Mode B: Export — `/data-lineage <design_id>`

Regenerate the Mermaid diagram. Default mode when no subcommand is given.

**Workflow:**

1. Check the target (see "Target")
2. Run the notebook (see "Running the notebook")
3. Display the generated diagram from `.insight/lineage/{id}.mmd`
4. Confirm the output file location

### Mode C: Refactor — `/data-lineage <design_id> refactor`

Analyze the lineage and suggest pipeline improvements.

**Workflow:**

1. Check the target (see "Target")
2. Run the notebook (see "Running the notebook"). The step records live only in the run, so the
   existing `.mmd` may not match the current code or data. Re-run it to get the current rows.
3. Read `.insight/lineage/{id}.mmd` (each step's `reason`, rows after the step and row delta)
   with the `tracked_pipe` calls in the `data_prep` and `analysis` cells
4. Analyze patterns and report findings:

**Improvement patterns to check:**

| Pattern | Condition | Suggestion |
|---------|-----------|------------|
| No-op step | `delta == 0` | Column add/rename — consider removing from tracked_pipe |
| Consecutive filters | Sequential filters on same column | Merge into single query |
| Large drop | `abs(delta) > 50%` of input rows | Review filter condition for correctness |
| Order optimization | Later step has higher reduction rate | Move high-reduction filters earlier |
| Redundant filter | Step removes 0 rows | Filter condition may be subset of prior step |

5. Present findings with specific code suggestions
6. After the user applies a refactor to the notebook, run it again and compare the new `.mmd`

## Output

- **Mermaid file**: `.insight/lineage/{id}.mmd`

## API Reference

The notebook already imports these (`imports` cell); the skill does not call them directly.

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
