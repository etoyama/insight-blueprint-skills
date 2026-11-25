"""SAMPLE — reference notebook of the 7-cell contract (Epic 07, Epic 30)

- Design ID: SAMPLE
- Hypothesis: group B has a higher mean value than group A
- Criterion: a difference of 5.0 or more supports it, one under 1.0 rejects it
- Intent: confirmatory

Self-contained (builds its own DataFrame, no external source) so the contract's
mechanics — top-to-bottom run, tracked_pipe lineage, verdict JSON side-effect, Mermaid
export — can be regression-tested with one ``python`` run. Writes ``verdict.json`` and
``lineage.mmd`` relative to the current working directory.

See skills/analysis-notebook/references/notebook-contract.md.
"""

# %% imports
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 — the backend is chosen before pyplot loads
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from insight_blueprint.lineage import (  # noqa: E402
    LineageSession,
    export_lineage_as_mermaid,
    tracked_pipe,
)

plt.rcParams["figure.figsize"] = (10, 6)

# %% data_load
raw_df = pd.DataFrame(
    {"group": ["A", "A", "B", "B"], "value": [10.0, 12.0, 20.0, None]}
)
session = LineageSession(name="SAMPLE-analysis", design_id="SAMPLE")

# %% data_prep
df_clean = raw_df.pipe(
    tracked_pipe(
        lambda d: d.dropna(subset=["value"]),
        reason="drop null value",
        session=session,
    )
)

# %% analysis
means = df_clean.groupby("group")["value"].mean()
# Optional metric items (Epic 12 / ADR-0013): the producer computes how large and how
# certain the effect is, so the analysis note and the report only lay the numbers out.
a = df_clean.loc[df_clean["group"] == "A", "value"]
b = df_clean.loc[df_clean["group"] == "B", "value"]
diff = float(b.mean() - a.mean())
n = len(a) + len(b)
squared_deviations = ((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()
pooled_sd = float(np.sqrt(squared_deviations / (n - 2)))
# Normal approximation keeps the fixture free of scipy (not in the notebook extra).
half_width = 1.96 * pooled_sd * float(np.sqrt(1 / len(a) + 1 / len(b)))
# The lines come from the criterion the design fixed before the run (ADR-0052);
# between them the notebook draws no conclusion.
support_line = 5.0
reject_line = 1.0
if diff >= support_line:
    judgment = "supported"
elif diff < reject_line:
    judgment = "rejected"
else:
    judgment = "inconclusive"
null_rate = float(raw_df["value"].isna().mean())
results = {
    "hypothesis_direction": judgment,
    "observed_direction": f"A={means.get('A')} B={means.get('B')}",
    "confidence_level": "medium",
    "decision_reason": f"the difference {diff} against the lines 5.0 and 1.0",
    "metrics": {
        "mean_diff": {
            "value": diff,
            "support_line": support_line,
            "reject_line": reject_line,
            "judgment": judgment,
            "effect_size": {"kind": "cohens_d", "value": diff / pooled_sd},
            "interval": {
                "kind": "confidence",
                "level": 0.95,
                "lower": diff - half_width,
                "upper": diff + half_width,
            },
            "sample_size": n,
        },
        # A guardrail passes or fails against one threshold; it is not judged.
        "null_rate": {"value": null_rate, "threshold": 0.5, "pass": null_rate <= 0.5},
        "mean_by_group": {
            "by": ["group"],
            "groups": [
                {"group": [name], "value": float(mean), "sample_size": int(size)}
                for name, mean, size in zip(
                    means.index,
                    means,
                    df_clean.groupby("group")["value"].size(),
                    strict=True,
                )
            ],
        },
    },
}

# %% viz
# Epic 10 / ADR-0008: save the figure as a PNG and describe it in a figure_manifest so
# the analysis note and the report can embed it with axis + how-to-read captions without
# re-rendering. The producer owns the figure's truth.
fig, ax = plt.subplots()
df_clean.groupby("group")["value"].mean().plot.bar(ax=ax)
ax.set_xlabel("group")
ax.set_ylabel("mean value")
fig.savefig("SAMPLE_fig01.png", bbox_inches="tight")
plt.close(fig)
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

# %% verdict
verdict = {
    "conclusion": f"observed {results['observed_direction']}",
    "evidence_summary": ["B mean > A mean"],
    "open_questions": ["small sample?"],
    "metrics": results.get("metrics", {}),
    "figures": figure_manifest,
}
Path("verdict.json").write_text(json.dumps(verdict, ensure_ascii=False))

# %% lineage
export_lineage_as_mermaid(session, output_path="lineage.mmd")
