"""Reference marimo notebook following the 8-cell contract (Epic 07).

Self-contained (builds its own DataFrame, no external source) so the contract's
mechanics — cell DAG, tracked_pipe lineage, verdict JSON side-effect, Mermaid export —
can be regression-tested via `marimo export script` + execution. Writes `verdict.json`
and `lineage.mmd` relative to the current working directory.

See skills/analysis-notebook/references/notebook-contract.md.
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import pathlib

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from insight_blueprint.lineage import (
        LineageSession,
        export_lineage_as_mermaid,
        tracked_pipe,
    )

    plt.rcParams["figure.figsize"] = (10, 6)
    return (
        LineageSession,
        export_lineage_as_mermaid,
        json,
        np,
        pathlib,
        pd,
        plt,
        tracked_pipe,
    )


@app.cell
def _(LineageSession, pd):
    import marimo as mo

    raw_df = pd.DataFrame(
        {"group": ["A", "A", "B", "B"], "value": [10.0, 12.0, 20.0, None]}
    )
    session = LineageSession(name="SAMPLE-analysis", design_id="SAMPLE")
    mo.md(f"loaded {len(raw_df)} rows")
    return mo, raw_df, session


@app.cell
def _(mo):
    mo.md("# SAMPLE\n- Design ID: SAMPLE\n- Intent: confirmatory")
    return


@app.cell
def _(mo, raw_df, session, tracked_pipe):
    df_clean = raw_df.pipe(
        tracked_pipe(
            lambda d: d.dropna(subset=["value"]),
            reason="drop null value",
            session=session,
        )
    )
    mo.md(f"prep {len(raw_df)}->{len(df_clean)}")
    return (df_clean,)


@app.cell
def _(df_clean, mo):
    _means = df_clean.groupby("group")["value"].mean()
    results = {
        "hypothesis_direction": "A<B",
        "observed_direction": f"A={_means.get('A')} B={_means.get('B')}",
        "confidence_level": "medium",
        "decision_reason": "group means differ",
    }
    mo.md("analysis done")
    return (results,)


@app.cell
def _(df_clean, plt):
    # viz cell (Epic 10 / ADR-0008): save the figure as a PNG and describe it in a
    # figure_manifest so /analysis-report can embed it with axis + how-to-read captions
    # without re-rendering. The producer owns the figure's truth.
    _fig, _ax = plt.subplots()
    df_clean.groupby("group")["value"].mean().plot.bar(ax=_ax)
    _ax.set_xlabel("group")
    _ax.set_ylabel("mean value")
    _fig.savefig("SAMPLE_fig01.png", bbox_inches="tight")
    figure_manifest = [
        {
            "file": "SAMPLE_fig01.png",
            "title": "Mean value by group",
            "axes": "x = group (category), y = mean value",
            "how_to_read": (
                "Each bar is a group's mean value; a taller bar means a higher mean. "
                "Compare A vs B heights to read the direction."
            ),
        }
    ]
    plt.gcf()
    return (figure_manifest,)


@app.cell
def _(figure_manifest, json, mo, pathlib, results):
    verdict = {
        "conclusion": f"observed {results['observed_direction']}",
        "evidence_summary": ["B mean > A mean"],
        "open_questions": ["small sample?"],
        "figures": figure_manifest,
    }
    pathlib.Path("verdict.json").write_text(json.dumps(verdict, ensure_ascii=False))
    mo.md("verdict written")
    return (verdict,)


@app.cell
def _(export_lineage_as_mermaid, session):
    export_lineage_as_mermaid(session, output_path="lineage.mmd")
    return


if __name__ == "__main__":
    app.run()
