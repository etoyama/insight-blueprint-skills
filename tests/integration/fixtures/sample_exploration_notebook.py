"""EXPLORE — reference notebook of an exploration (Epic 32)

- Design ID: EXPLORE
- Question: how are \"wait days\" spread across branches?
- Intent: exploratory

Self-contained like sample_notebook.py. An exploration answers its question by measuring:
its results hold no predicted direction and its metrics no threshold or pass, while the
verdict still keeps every measured value (ADR-0050). The quote in the question is escaped
as the contract's "File layout" says, so it cannot end the docstring.

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
    {
        "branch": ["main", "main", "main", "annex", "annex", "annex"],
        "wait_days": [2.0, 3.0, 4.0, 4.0, 6.0, None],
    }
)
session = LineageSession(name="EXPLORE-analysis", design_id="EXPLORE")

# %% data_prep
df_clean = raw_df.pipe(
    tracked_pipe(
        lambda d: d.dropna(subset=["wait_days"]),
        reason="drop null wait_days",
        session=session,
    )
)

# %% analysis
main_days = df_clean.loc[df_clean["branch"] == "main", "wait_days"]
annex_days = df_clean.loc[df_clean["branch"] == "annex", "wait_days"]
gap = float(annex_days.mean() - main_days.mean())
n = len(main_days) + len(annex_days)
squared_deviations = ((main_days - main_days.mean()) ** 2).sum() + (
    (annex_days - annex_days.mean()) ** 2
).sum()
pooled_sd = float(np.sqrt(squared_deviations / (n - 2)))
half_width = 1.96 * pooled_sd * float(np.sqrt(1 / len(main_days) + 1 / len(annex_days)))
# No threshold and no pass: an exploration measures and leaves the judging to a
# confirmation whose criterion is fixed before it runs.
results = {
    "observed_direction": f"annex waits {gap:.1f} days longer on average",
    "confidence_level": "low",
    "notable_patterns": ["annex has the widest spread"],
    "metrics": {
        "wait_days_gap": {
            "value": gap,
            "effect_size": {"kind": "cohens_d", "value": gap / pooled_sd},
            "confidence_interval": {
                "level": 0.95,
                "lower": gap - half_width,
                "upper": gap + half_width,
            },
            "sample_size": n,
        }
    },
}

# %% viz
fig, ax = plt.subplots()
df_clean.boxplot(column="wait_days", by="branch", ax=ax)
ax.set_xlabel("branch")
ax.set_ylabel("wait days")
fig.savefig("EXPLORE_fig01.png", bbox_inches="tight")
plt.close(fig)
figure_manifest = [
    {
        "file": "EXPLORE_fig01.png",
        "title": "Wait days by branch",
        "axes": "x = branch (category), y = wait days (days)",
        "how_to_read": (
            "Each box is a branch's spread of wait days; the line in a box is its median. "
            "Compare the boxes to see where waits are longer and wider."
        ),
    }
]

# %% verdict
verdict = {
    "conclusion": results["observed_direction"],
    "evidence_summary": ["annex mean wait days exceed main by the measured gap"],
    "open_questions": ["does the gap hold with more than a few rows?"],
    "metrics": results.get("metrics", {}),
    "figures": figure_manifest,
}
Path("verdict.json").write_text(json.dumps(verdict, ensure_ascii=False))

# %% lineage
export_lineage_as_mermaid(session, output_path="lineage.mmd")
