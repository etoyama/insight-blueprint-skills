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
| 5 | viz | `def _(df_clean, results, plt):` | — | Plots; local vars use `_` prefix; final expression is `plt.gcf()` |
| 6 | verdict | `def _(results, json, Path, mo):` | `(verdict,)` | Build `verdict` dict and **persist it** to `.insight/notebooks/{id}_verdict.json` (the skill reads this). Display via `mo.md()` |
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
}
Path(".insight/notebooks/{id}_verdict.json").write_text(
    json.dumps(verdict, ensure_ascii=False)
)
```

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

## Execution (non-interactive)

marimo 0.21 has **no `export session`** (and `export ipynb` needs `nbformat`). Execute by converting
to a flat script and running it — no extra deps:

```bash
uv run marimo export script .insight/notebooks/{id}.py -o .insight/notebooks/{id}_flat.py
uv run python .insight/notebooks/{id}_flat.py
```

Running the flat script executes cells in dependency order, so the verdict cell writes
`.insight/notebooks/{id}_verdict.json` and the lineage cell writes `.insight/lineage/{id}.mmd`.
The skill then reads `{id}_verdict.json` to build journal events.

Optional human-viewable artifact — note this **re-executes** the notebook (rewriting verdict.json /
lineage.mmd), so run it after the script run, not instead of it:

```bash
uv run marimo export html .insight/notebooks/{id}.py -o .insight/notebooks/{id}.html
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
