# Notebook contract (7 cells)

The `/analysis-notebook` skill generates a plain Python script that follows this fixed 7-cell
structure. The contract keeps generated notebooks predictable, lineage-tracked, and
machine-readable (the `verdict` cell persists a JSON side-effect that the skill reads back).
The script runs from top to bottom with `python` (see "Execution" below).

## File layout

The file opens with a docstring that holds the design's id, title and intent, and what the
design answers: an exploration writes a `- Question:` line with `exploration_question`, and a design
that holds a hypothesis (a confirmation, or an exploration saved before ADR-0048) writes a
`- Hypothesis:` line with `hypothesis_statement`. Never write both lines.
Inside the docstring, write each `\` as `\\` and each `"` as `\"`, so the text cannot end the
docstring early or turn into an escape sequence. Apply the same escape to the title, the question
and the hypothesis.
Only the docstring comes before the first `# %%` line: no import, no assignment, no other statement.

A cell starts at a `# %% <name>` line written at the start of a line, and runs up to the next
`# %%` line (or the end of the file). The notebook has exactly these seven cells, in this order,
each under its own name: the cells of the table below. Write no other `# %%` line, not even a bare
`# %%` or a `# %% [markdown]`; read a second source inside the `data_load` cell, under no line of
its own. The analysis note shows every cell but `data_load` with its name and leaves `data_load`
out, because that cell holds the connection values (ADR-0022, ADR-0045). A notebook whose cells
differ from the seven (one added, missing, renamed or out of order) shows no code at all.

Assign each contract variable only in the cell that makes it (`raw_df`, `session`, `df_clean`,
`results`, `figure_manifest`, `verdict`; see "Assigns" below). Never reassign another cell's
variable; give an intermediate a fresh name instead.
Put every import in the `imports` cell, the source's client library and the methodology-specific
packages included. An import in `data_load` would be hidden from the analysis note with that cell.
The `imports` cell holds imports and settings only.

Write every `connection` value only in the `data_load` cell: a file path, a table name, a project id,
a host, and the client that takes one (`bigquery.Client(project=...)`). The analysis note hides only
that cell, so a `connection` value in any other cell shows there.

```python
# confirmation
"""H01 — 平日夜の予約は週末より多い

- Design ID: H01
- Hypothesis: 平日夜の予約数は週末の予約数を上回る
- Intent: confirmatory
"""

# %% imports
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from insight_blueprint.lineage import LineageSession, export_lineage_as_mermaid, tracked_pipe

plt.rcParams["figure.figsize"] = (10, 6)

# %% data_load
raw_df = pd.read_csv("data/reservations.csv")
session = LineageSession(name="H01-analysis", design_id="H01")

# %% data_prep
...
```

An exploration opens the same way, with the question in place of the hypothesis. The
`# confirmation` or `# exploration` comment above each example only labels the example; a notebook
starts with its docstring.

```python
# exploration
"""H02 — 分館ごとの待ち日数

- Design ID: H02
- Question: 分館ごとに、予約から受け取りまでの日数はどう分布するか
- Intent: exploratory
"""
```

## Cells

| Name | Assigns | Responsibility |
|------|---------|----------------|
| `imports` | `pd, plt, np, LineageSession, tracked_pipe, export_lineage_as_mermaid, json, Path` | Library imports. Call `matplotlib.use("Agg")` before importing `pyplot`, so a run opens no window; then `plt.rcParams["figure.figsize"] = (10, 6)` |
| `data_load` | `raw_df`, `session` | Load source into `raw_df`. Each `{source:ID}` in `methodology.steps` becomes the location in that source's `connection`: a string literal in Python code, a quoted identifier in a SQL query (ADR-0022); an `ID` not in `source_ids` stops the generation; `session = LineageSession(name="{id}-analysis", design_id="{id}")`. The only cell that assigns `raw_df` |
| `data_prep` | `df_clean` | Methodology-**independent** cleaning (nulls, types, filters). Every transform via `tracked_pipe(...)` |
| `analysis` | `results` | Methodology-**dependent** analysis. Build `results` in the shape of the design's form (see "`results` shape" below) |
| `viz` | `figure_manifest` | Plots; **save each figure** to `.insight/notebooks/{id}_fig{NN:02d}.png`, close it, and build `figure_manifest` (see figures below) |
| `verdict` | `verdict` | Build `verdict` dict (include `figures=figure_manifest`) and **persist it** to `.insight/notebooks/{id}_verdict.json` (the skill reads this) |
| `lineage` | — | `export_lineage_as_mermaid(session, project_path=".")` → `.insight/lineage/{id}.mmd` |

## Lineage calls

Call `LineageSession` and `tracked_pipe` exactly as below. `tracked_pipe` takes the step function
first, then `reason` and `session` as **keyword-only** arguments, and returns a function of one
DataFrame — pass it to `.pipe()`. It never takes the DataFrame itself, and it has no `name`.

```python
# %% data_load
session = LineageSession(name="{id}-analysis", design_id="{id}")

# %% data_prep
# Same shape in the analysis cell; one tracked_pipe per transform.
def drop_nulls(df):
    return df.dropna()

df_clean = raw_df.pipe(tracked_pipe(drop_nulls, reason="drop rows with nulls", session=session))
```

## `results` shape (`analysis` cell)

Choose the shape by the form of the design. Use the exploration shape for every design with the
`exploratory` intent, an old exploration with a hypothesis included; use the confirmation shape for
every other design (`confirmatory`, and a saved `mixed` design or one with no intent, which read as a
confirmation).

```python
# confirmation
results = {
    "hypothesis_direction": "supported|rejected|inconclusive",
    "observed_direction": "<observed vs the lines summary>",
    "confidence_level": "high|medium|low|ambiguous",
    "decision_reason": "<where the value fell against the lines>",
    "metrics": {
        # primary — the two lines of the criterion and the judgment
        "wait_days_gap": {
            "value": 1.4, "support_line": 2.0, "reject_line": 1.0,
            "judgment": "inconclusive", "p_value": 0.0001,
            # optional — see "Optional metric items" below
            "effect_size": {"kind": "cohens_d", "value": 0.42},
            "interval": {"kind": "confidence", "level": 0.95, "lower": 0.9, "upper": 1.9},
            "sample_size": 1200,
        },
        # secondary or guardrail — one threshold and whether it passed
        "missing_rate": {"value": 0.01, "threshold": 0.05, "pass": True},
        # measured per group — the axes in "by", one row per group
        "wait_days_by_branch": {
            "by": ["branch", "weekday"],
            "groups": [
                {"group": ["main", "Mon"], "value": 3.1, "sample_size": 300},
                {
                    "group": ["annex", "Mon"], "value": 4.9,
                    "interval": {"kind": "hdi", "level": 0.95, "lower": 4.1, "upper": 5.8},
                },
            ],
        },
    },
}
```

- In a confirmation, copy the primary metric's `support_line` and `reject_line`, and each other
  metric's `threshold`, from that metric's own `comparison` in the design's `metrics`, where
  `/analysis-design` writes the criterion before the analysis runs; the notebook never makes up a
  line or a threshold
  ([ADR-0050](../../../docs/adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md),
  [ADR-0052](../../../docs/adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md)).
- The primary metric (`tier: primary`) carries the criterion of the judgment. The primary metric
  holds the criterion as `support_line` and `reject_line`, both numbers, and its `judgment`. Write
  at least one of the two lines; a criterion of one line writes only `support_line`.
- `judgment` is `supported`, `rejected` or `inconclusive`. A value between the two lines is
  `inconclusive`. Never say one of the three judgments with `pass`: a `pass` of false cannot tell
  a rejection from no conclusion. `hypothesis_direction` never disagrees with the `judgment` of the
  primary metric.
- The lines keep only the numbers. Which way a line points, and whether the value or an end of its
  interval is held against it, stays in the `comparison`, which the analysis note shows beside the
  table.
- A secondary or guardrail metric holds one `threshold` and whether it passed (`pass`), and no line
  and no `judgment`. Never write a `threshold` or a `pass` in the primary metric. A secondary or
  guardrail metric whose `comparison` states no criterion is reported with its value and no
  `threshold` or `pass`.
- If the design has no primary metric, or its `comparison` states no criterion, stop rather than
  choosing one: a design that began its analysis cannot take a criterion any more, so suggest
  deriving a new design with /analysis-design (`parent_id`)
  ([ADR-0053](../../../docs/adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)).
- A metric measured per group holds the names of its axes in `by` and one row per group in
  `groups`. Each row holds as many names in `group` as `by` has axes, its `value`, and any of the
  optional items and a `p_value`. A row holds no `judgment`, no line, no `threshold` and no `pass`:
  a group is measured, and the metric as a whole is judged elsewhere. A metric holds either one
  `value` or `groups`, never both. Never write a group into the name of a metric
  (`wait_days[annex|Mon]`): the analysis note and the report lay the rows out by their axes.

```python
# exploration
results = {
    "observed_direction": "<e.g. moderate positive r=0.47>",
    "confidence_level": "high|medium|low|ambiguous",
    "notable_patterns": [...],
    "metrics": {
        "wait_days_gap": {
            "value": 1.8, "p_value": 0.03,
            # optional — see "Optional metric items" below
            "effect_size": {"kind": "cohens_d", "value": 0.35},
            "interval": {"kind": "confidence", "level": 0.95, "lower": 0.4, "upper": 3.2},
            "sample_size": 840,
        }
    },
}
```

- An exploration answers its question by measuring, so it holds no expectation and judges
  nothing: its `results` have no `hypothesis_direction` and no `decision_reason`, and its metrics
  have no line, no `judgment`, no `threshold` and no `pass`. Put every value it measured in
  `metrics`; a metric measured per group holds `by` and `groups` as in a confirmation.
- An exploration may write a p-value but never a pass or fail, and never calls a value
  significant against a cut-off of its own.

## `verdict` shape (`verdict` cell) — persisted JSON

```python
verdict = {
    "conclusion": "<one line>",
    "evidence_summary": ["...", "..."],
    "open_questions": ["...", "..."],
    "metrics": results.get("metrics", {}),  # both forms: the note and the report tabulate them
    "figures": figure_manifest,  # from the viz cell (may be []); see figures below
}
Path(".insight/notebooks/{id}_verdict.json").write_text(
    json.dumps(verdict, ensure_ascii=False)
)
```

The verdict keeps `metrics` in both forms, so the analysis note and the report lay out what an
exploration measured as well as what a confirmation judged. A verdict saved before these rules may
lack `metrics`, carry a `threshold` and a `pass` in an exploration or in a primary metric, or hold
none of the lines, the `judgment`, the `interval` and the `groups`; the consumers read it as
written.

## Optional metric items (`analysis` cell) — effect size, interval, sample size (ADR-0013, ADR-0052)

Each entry of `results["metrics"]`, and each row of its `groups`, may carry three **optional**
items, so a reader of the report can tell how large and how certain an effect is, not only how it
was judged. The notebook (the producer) computes them; the analysis note and the report
(`tree_io render` and `tree_io report`, read-only consumers) only lay them out and never
compute a missing one ([ADR-0013](../../../docs/adr/0013-verdict-metric-optional-items.md)).

| Key | Shape | Meaning |
|---|---|---|
| `effect_size` | `{"kind": str, "value": float}` | Standardized size of the effect. `kind` names the measure (`cohens_d`, `r`, `odds_ratio`, …) — an open string, because the measure depends on the method |
| `interval` | `{"kind": str, "level": float, "lower": float, "upper": float}` | Interval of **this metric's `value`** (not of the effect size). `kind` names the interval (`confidence`, `hdi`, `eti`, …) — an open string, because the interval depends on the method. `level` is a proportion (`0.95`), `lower <= value <= upper` |
| `sample_size` | `int` | Number of observations the metric was computed from (after data_prep) |

- **Each item is independent and optional.** Some methods define no effect size or no interval —
  then leave that key out. Never write `null`, `0`, or a placeholder for an item you cannot compute.
- **An item is all-or-nothing.** `effect_size` without `kind`, or `interval` without `kind` or
  without `level`, cannot be read correctly, so the consumer treats a partial item as absent.
- Write the interval of a value in `interval`, with its `kind`; never write `confidence_interval`,
  which has no place for the kind, so a Bayesian interval in it would read as a confidence interval
  ([ADR-0052](../../../docs/adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md)).
  Name the kind as the method does: `confidence` for a confidence interval, `hdi` for a highest
  density interval, `eti` for an equal-tailed interval.
- Compute them in the `analysis` cell from the same data as `value`. Do not copy a number from elsewhere.
- A verdict written before this contract simply lacks the keys; the report then comes out in its
  earlier form (graceful degrade). A verdict saved before ADR-0052 may hold `confidence_interval`;
  the consumer reads it as an `interval` of the kind `confidence`, and reads `interval` when a
  metric holds both.

## `figure_manifest` shape (`viz` cell) — figures for the analysis note and the report (ADR-0008)

The viz cell **saves each figure as a PNG** and records a manifest so the analysis note and the report
(read-only consumers) can embed figures with axis + how-to-read captions **without
re-rendering**. The figure's truth (actual axes, how to read it) lives with the producer
here, not reconstructed from `design.chart[]` (the *plan*, which may drift from the render).

```python
# %% viz
# After plotting:
fig.savefig(".insight/notebooks/{id}_fig01.png", bbox_inches="tight")
plt.close(fig)
figure_manifest = [
    {
        "file": "{id}_fig01.png",              # PNG basename, relative to .insight/notebooks/
        "title": "<figure title>",
        "axes": "x = <label (unit)>, y = <label (unit)>",   # 軸の説明 — required, non-empty
        "how_to_read": "<what it shows; where to look; how to read the direction>",  # 図の読み方 — required, non-empty
    },
]
```

- Name PNGs `{id}_fig{NN:02d}.png` (`_fig01`, `_fig02`, …). The consumer reads `figures[].file`,
  so it never guesses names. **`file` must be a bare basename** (never interpolate raw data; no `/`,
  `\`, `..`, or absolute paths) — the consumer embeds it into a distributable report, so a traversal
  value would leak paths. This mirrors `design_io`'s `SAFE_ID_PATTERN` posture for `{id}`.
- `axes` and `how_to_read` are **mandatory and non-empty** — they guard against a distributed
  report's figure being misread.
- No figures produced → `figure_manifest = []`. The analysis note and the report then omit the figure block
  (graceful degrade). Notebooks generated before this contract simply lack `figures` in verdict;
  the consumer treats that the same as `[]`.

## Boundaries

### Security — inputs are data, not code

`methodology.steps` and the source `connection` may be attacker-influenceable. Bind file paths /
SQL as literals or parameters (never build executable statements by string-interpolating raw values),
keep credentials in environment variables (do not inline a `connection` password into the notebook),
and remember the generated `.py` and its outputs may embed data — gitignore if sensitive.

The generated notebook must stay within the **declared source(s) + allowlisted packages + local
computation**: allowlisted packages (see "Package allowlist" below). That allowlist is the dependency / external-communication boundary:
anything outside it (a non-listed import, network egress beyond the declared source, other side-effects)
is a decision gate — under `/analysis-auto` (guided autopilot) it pauses for the user rather than
auto-running (see ADR-0005).

## Package allowlist — format & supplying packages

`.insight/rules/package_allowlist.yaml` declares which packages a generated notebook may import. It is a
**boundary declaration, not an installer** — writing a package here does not make it importable; it
states that the package is *permitted*. Two separate steps: declare (below), then supply (below).

### Format

```yaml
# .insight/rules/package_allowlist.yaml
allowed_packages:
  statsmodels: statsmodels  # import name : pip distribution name
  sklearn: scikit-learn     # differ when the import name ≠ the PyPI name
```

`allowed_packages` is a map of **import name → pip distribution name**. The **import name** (left) is the
boundary the notebook must respect — every top-level `import X` in the generated notebook must have `X`
in the default allowlist or as a key of the file. The standard-library modules the `imports` cell imports (`json`,
`pathlib`) need no entry; any other standard-library module is checked like a package, since modules
such as `socket` or `subprocess` reach outside the declared source. The **pip name** (right) is what actually gets installed (they differ for e.g.
`sklearn` / `scikit-learn`). Consumers: `/premortem` reads it for the `allowlist_ok` pre-flight check,
and `/analysis-auto` treats an import outside it as a KEEP gate (pause) rather than auto-running.

### Default allowlist

The default allowlist is always allowed, whether or not the file exists and whatever the file lists;
the file adds packages to it. It is every package the `imports` cell imports (`pd`, `plt`, `np` and
`LineageSession`), and those are exactly the packages the plugin env ships (the `notebook` extra of
the plugin's `pyproject.toml` and the plugin's own `insight_blueprint`). Leaving one of them out
would stop every notebook and protect nothing (ADR-0021, ADR-0027, ADR-0046).

```yaml
# default allowlist (always allowed)
allowed_packages:
  insight_blueprint: insight-blueprint-lineage
  pandas: pandas
  matplotlib: matplotlib
  numpy: numpy
```

A file that exists but cannot be read (invalid YAML, no `allowed_packages`) is an error, not a
fallback to the default. An empty `allowed_packages` is readable and adds nothing. To allow one more
package, list only that package in the file.

### Supplying an allowlisted package to the run

The plugin env (`${CLAUDE_PLUGIN_ROOT}`) is a **read-only distributed artifact** — do not mutate it, and
a plugin update would drop any in-place `uv add`. The packages of the default allowlist above already
ship in the plugin env, so never pass a default-allowlist package such as `insight_blueprint` to `--with`
(`--with insight-blueprint-lineage` would layer a published copy over the plugin's own source). A
methodology-specific package of the file that is in neither the `notebook` extra nor the default allowlist
is supplied **ephemerally at run time** with `--with <pip-name>`, which layers it onto the run without
touching the cached env:

```bash
# e.g. a notebook that imports sklearn (allowlisted as sklearn: scikit-learn)
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook --with scikit-learn \
  python .insight/notebooks/{id}.py
```

Pass one `--with` per extra pip name (repeatable). Packages used by *every* analysis belong in the
`notebook` extra of `pyproject.toml` instead (a repo change), not in per-run `--with`.

## Execution (non-interactive)

The notebook is a plain script, so one command runs it from top to bottom:

```bash
# Run from the project directory; the plugin env supplies pandas, matplotlib, numpy and insight_blueprint.
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  python .insight/notebooks/{id}.py
```

The run executes the cells in file order, so the verdict cell writes
`.insight/notebooks/{id}_verdict.json` and the lineage cell writes `.insight/lineage/{id}.mmd`.
The skill then reads `{id}_verdict.json` to build journal events. When the run stops, the
traceback names the line; fix the cell that holds it and run the same command again.

## verdict → journal events

Map the verdict into `observe` / `evidence` / `question` events appended to
`.insight/designs/{id}_journal.yaml` (never `conclude` — concluding is `/analysis-reflection`):

- `observe` — data characteristics (from the `data_load` and `data_prep` cells).
- `evidence` — each item of `evidence_summary`. `metadata.direction` is the lean against the
  design's `hypothesis_statement`, and only a design of the confirmation form sets it (an
  exploration never does, an old exploration with a hypothesis included):
  - confirmation: `supported`→`supports`, `rejected`→`contradicts`, `inconclusive`→(question)
  - exploration: leave `metadata.direction` out of every evidence event. An exploration has no
    hypothesis for the evidence to lean against; a guess formed along the way is a `hypothesize`
    event of `/analysis-journal`
  - `confidence_level == "ambiguous"` → emit a `question` instead of `evidence`, in both forms.
- `question` — each item of `open_questions`. When `inconclusive`/`ambiguous` above already routed the
  evidence to a question, do not duplicate it — emit one question per distinct point.

Append them with `design_io journal-append --id {id}` (SKILL.md, Step 6): it continues the
event ids from the existing max in the journal (`{id}-E{nn}`) and sets each `created_at`.
