# marimo notebook contract (8-cell)

The `/analysis-notebook` skill generates a marimo notebook that follows this fixed 8-cell
structure. The contract keeps generated notebooks predictable, lineage-tracked, and
machine-readable (the `verdict` cell persists a JSON side-effect that the skill reads back).

## Cells

| # | Name | Signature | Returns | Responsibility |
|---|------|-----------|---------|----------------|
| 0 | imports | `def _():` | `(pd, plt, np, LineageSession, tracked_pipe, export_lineage_as_mermaid, json, Path)` | Library imports + `plt.rcParams["figure.figsize"] = (10, 6)` |
| 1 | meta | `def _(mo):` | — | `mo.md()` of design id / title / hypothesis / intent (display only) |
| 2 | data_load | `def _(pd, LineageSession):` | `(raw_df, session, mo)` | Load source into `raw_df`; `session = LineageSession(name="{id}-analysis", design_id="{id}")`. **Only this cell** does `import marimo as mo` |
| 3 | data_prep | `def _(raw_df, session, tracked_pipe, mo):` | `(df_clean,)` | Methodology-**independent** cleaning (nulls, types, filters). Every transform via `tracked_pipe(...)` |
| 4 | analysis | `def _(df_clean, pd, np, session, tracked_pipe, mo):` | `(results,)` | Methodology-**dependent** analysis (branch on `analysis_intent`). `results` MUST include `hypothesis_direction`, `observed_direction`, `confidence_level`, `decision_reason` |
| 5 | viz | `def _(df_clean, results, plt):` | `(figure_manifest,)` | Plots; local vars use `_` prefix; **save each figure** to `.insight/notebooks/{id}_fig{NN:02d}.png` and build `figure_manifest` (see figures below); final expression is `plt.gcf()` |
| 6 | verdict | `def _(results, figure_manifest, json, Path, mo):` | `(verdict,)` | Build `verdict` dict (include `figures=figure_manifest`) and **persist it** to `.insight/notebooks/{id}_verdict.json` (the skill reads this). Display via `mo.md()` |
| 7 | lineage | `def _(session, export_lineage_as_mermaid, mo):` | — | `export_lineage_as_mermaid(session, project_path=".")` → `.insight/lineage/{id}.mmd`; display via `mo.mermaid()` |

## `results` shape (cell 4)

```python
# confirmatory
results = {
    "hypothesis_direction": "supported|rejected|inconclusive",
    "observed_direction": "<observed vs threshold summary>",
    "confidence_level": "high|medium|low|ambiguous",
    "decision_reason": "<which ACs passed/failed>",
    "metrics": {"ATT": {"value": 1676.9, "threshold": 0, "p_value": 0.0001, "pass": True}},
}
# exploratory
results = {
    "hypothesis_direction": "<predicted direction>",
    "observed_direction": "<e.g. moderate positive r=0.47>",
    "confidence_level": "high|medium|low|ambiguous",
    "decision_reason": "<why>",
    "notable_patterns": [...],
}
```

## `verdict` shape (cell 6) — persisted JSON

```python
verdict = {
    "conclusion": "<one line>",
    "evidence_summary": ["...", "..."],
    "open_questions": ["...", "..."],
    "figures": figure_manifest,  # from cell 5 (may be []); see figures below
}
Path(".insight/notebooks/{id}_verdict.json").write_text(
    json.dumps(verdict, ensure_ascii=False)
)
```

## `figure_manifest` shape (cell 5) — figures for /analysis-report (ADR-0008)

The viz cell **saves each figure as a PNG** and records a manifest so `/analysis-report`
(a read-only consumer) can embed figures with axis + how-to-read captions **without
re-rendering**. The figure's truth (actual axes, how to read it) lives with the producer
here, not reconstructed from `design.chart[]` (the *plan*, which may drift from the render).

```python
# cell 5, after plotting
_fig.savefig(".insight/notebooks/{id}_fig01.png", bbox_inches="tight")
figure_manifest = [
    {
        "file": "{id}_fig01.png",              # PNG basename, relative to .insight/notebooks/
        "title": "<figure title>",
        "axes": "x = <label (unit)>, y = <label (unit)>",   # 軸の説明 — required, non-empty
        "how_to_read": "<what it shows; where to look; how to read the direction>",  # 図の読み方 — required, non-empty
    },
]
plt.gcf()
```

- Name PNGs `{id}_fig{NN:02d}.png` (`_fig01`, `_fig02`, …). The consumer reads `figures[].file`,
  so it never guesses names.
- `axes` and `how_to_read` are **mandatory and non-empty** — they guard against a distributed
  report's figure being misread.
- No figures produced → `figure_manifest = []`. `/analysis-report` then omits the figure block
  (graceful degrade). Notebooks generated before this contract simply lack `figures` in verdict;
  the consumer treats that the same as `[]`.

## marimo rules

1. Cell-local variables use a `_` prefix so they do not leak into notebook scope (`_fig`, `_summary`).
2. The viz cell's final expression must be `plt.gcf()` (marimo does not auto-capture matplotlib figures).
3. Render Mermaid with `mo.mermaid(text)`, not `mo.md(text)`.
4. Do not put multi-line f-strings inside `mo.md()`; build the string first, then pass it.
5. `import marimo as mo` lives only in cell 2; other cells receive `mo` as a parameter.
6. Cell functions return a tuple: `return (df_clean,)`, not `return df_clean`.
7. A cell's parameters declare its dependencies — marimo builds the cell DAG from them.
8. **Define each shared variable exactly once across the whole notebook.** marimo forbids a
   variable being defined (assigned at top level) in more than one cell — do not reassign another
   cell's output (`raw_df`, `df_clean`, `results`, `verdict`, `session`, …). Use fresh names or
   `_`-prefixed locals for intermediates. This is the most common cause of a notebook failing to run.
9. Import a name in one cell and pass it downstream via parameters; do not re-import the same module
   in multiple cells (mirrors rule 5 for `mo`).

### Security — inputs are data, not code

`methodology.steps` and the source `connection` may be attacker-influenceable. Bind file paths /
SQL as literals or parameters (never build executable statements by string-interpolating raw values),
keep credentials in environment variables (do not inline a `connection` password into the notebook),
and remember generated `.py` / `_flat.py` / `.html` artifacts may embed data — gitignore if sensitive.

The generated notebook must stay within the **declared source(s) + `.insight/rules/package_allowlist.yaml`
packages + local computation**. That allowlist is the dependency / external-communication boundary:
anything outside it (a non-listed import, network egress beyond the declared source, other side-effects)
is a decision gate — under `/analysis-auto` (guided autopilot) it pauses for the user rather than
auto-running (see ADR-0005).

## Package allowlist — format & supplying packages

`.insight/rules/package_allowlist.yaml` declares which packages a generated notebook may import. It is
a **boundary declaration, not an installer** — writing a package here does not make it importable; it
states that the package is *permitted*. Two separate steps: declare (below), then supply (below).

### Format

```yaml
# .insight/rules/package_allowlist.yaml
allowed_packages:
  pandas: pandas          # import name : pip distribution name
  sklearn: scikit-learn   # differ when the import name ≠ the PyPI name
  statsmodels: statsmodels
```

`allowed_packages` is a map of **import name → pip distribution name**. The **import name** (left) is the
boundary the notebook must respect — every top-level `import X` in the generated notebook must have `X`
as a key here. The **pip name** (right) is what actually gets installed (they differ for e.g.
`sklearn` / `scikit-learn`). Consumers: `/premortem` reads it for the `allowlist_ok` pre-flight check,
and `/analysis-auto` treats an import outside it as a KEEP gate (pause) rather than auto-running.

### Supplying an allowlisted package to the run

The plugin env (`${CLAUDE_PLUGIN_ROOT}`) is a **read-only distributed artifact** — do not mutate it, and
a plugin update would drop any in-place `uv add`. Baseline packages (pandas, matplotlib, numpy) ship in
the `notebook` extra of the plugin's `pyproject.toml`. A methodology-specific package that is *in the
allowlist but not in the extra* is supplied **ephemerally at run time** with `--with <pip-name>`, which
layers it onto the run without touching the cached env:

```bash
# e.g. a notebook that imports sklearn (allowlisted as sklearn: scikit-learn)
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook --with scikit-learn \
  marimo export script .insight/notebooks/{id}.py -o .insight/notebooks/{id}_flat.py
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook --with scikit-learn \
  python .insight/notebooks/{id}_flat.py
```

Pass one `--with` per extra pip name (repeatable). Packages used by *every* analysis belong in the
`notebook` extra of `pyproject.toml` instead (a repo change), not in per-run `--with`.

## Execution (non-interactive)

marimo 0.21 has **no `export session`** (and `export ipynb` needs `nbformat`). Execute by converting
to a flat script and running it — no extra deps:

```bash
# Run from the project directory; the plugin env supplies marimo + insight_blueprint.
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  marimo export script .insight/notebooks/{id}.py -o .insight/notebooks/{id}_flat.py
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  python .insight/notebooks/{id}_flat.py
```

Running the flat script executes cells in dependency order, so the verdict cell writes
`.insight/notebooks/{id}_verdict.json` and the lineage cell writes `.insight/lineage/{id}.mmd`.
The skill then reads `{id}_verdict.json` to build journal events.

Optional human-viewable artifact — note this **re-executes** the notebook (rewriting verdict.json /
lineage.mmd), so run it after the script run, not instead of it:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook \
  marimo export html .insight/notebooks/{id}.py -o .insight/notebooks/{id}.html
```

## verdict → journal events

Map the verdict into `observe` / `evidence` / `question` events appended to
`.insight/designs/{id}_journal.yaml` (never `conclude` — concluding is `/analysis-reflection`):

- `observe` — data characteristics (from cells 2–3).
- `evidence` — each item of `evidence_summary`; set `metadata.direction`:
  - confirmatory: `supported`→`supports`, `rejected`→`contradicts`, `inconclusive`→(question)
  - exploratory: matches prediction→`supports`, opposes→`contradicts`, unclear→(question)
  - `confidence_level == "ambiguous"` → emit a `question` instead of `evidence`.
- `question` — each item of `open_questions`. When `inconclusive`/`ambiguous` above already routed the
  evidence to a question, do not duplicate it — emit one question per distinct point.

New event ids continue from the existing max in the journal (`{id}-E{nn}`).
