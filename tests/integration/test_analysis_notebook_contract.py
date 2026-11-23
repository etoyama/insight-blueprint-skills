"""Integration test for the /analysis-notebook 8-cell contract mechanics (Epic 07).

Guards the execution path the skill relies on: convert the reference notebook to a flat
script (`marimo export script`), run it, and assert the verdict JSON side-effect + Mermaid
lineage export. Skipped when the optional `notebook` extra (marimo/pandas/matplotlib) is
not installed — matching how a minimal install lacks the analysis-runtime deps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("marimo")
pytest.importorskip("pandas")
pytest.importorskip("matplotlib")

FIXTURE = Path(__file__).parent / "fixtures" / "sample_notebook.py"


def _run_fixture(tmp_path: Path) -> dict:
    """Export the reference notebook to a flat script (no nbformat needed), run it in
    ``tmp_path`` — the skill's execution mechanism — and return the verdict side-effect.
    """
    nb = tmp_path / "SAMPLE.py"
    shutil.copy(FIXTURE, nb)
    flat = tmp_path / "SAMPLE_flat.py"
    export = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "script", str(nb), "-o", str(flat)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert export.returncode == 0, export.stderr
    run = subprocess.run(
        [sys.executable, str(flat)], cwd=tmp_path, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    return json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))


def test_notebook_contract_export_run_and_sideeffects(tmp_path: Path) -> None:
    # verdict JSON side-effect (what the skill reads to build journal events)
    verdict = _run_fixture(tmp_path)
    assert {"conclusion", "evidence_summary", "open_questions"} <= set(verdict)
    assert isinstance(verdict["evidence_summary"], list)
    # a confirmatory verdict persists its metrics so the analysis note and the report can build the
    # Results numbers table (metrics live in results/cell4; verdict must carry them —
    # a consumer reading verdict.metrics would otherwise get an empty table)
    assert "metrics" in verdict, "confirmatory verdict must persist results metrics"
    assert verdict["metrics"], (
        "metrics should be non-empty for the confirmatory fixture"
    )

    # lineage Mermaid export (tracked_pipe recorded the dropna step: 4 -> 3 rows)
    mmd = (tmp_path / "lineage.mmd").read_text(encoding="utf-8")
    assert mmd.startswith("graph LR")
    assert "4 rows" in mmd and "3 rows" in mmd


def test_notebook_contract_figures_manifest(tmp_path: Path) -> None:
    """Epic 10 / ADR-0008: the viz cell saves PNG(s) and the verdict cell records a
    ``figures[]`` manifest so the analysis note and the report (read-only consumers) can lay figures out
    with axis + how-to-read captions without re-rendering. The figure's truth lives with
    the producer (notebook), not with design.chart[].
    """
    verdict = _run_fixture(tmp_path)

    # figures[] manifest is part of the verdict side-effect (verdict enrich, not a new file)
    assert "figures" in verdict, "verdict must carry a 'figures' manifest (ADR-0008)"
    figures = verdict["figures"]
    assert isinstance(figures, list) and figures, "figures must be a non-empty list"

    required_keys = {"file", "title", "axes", "how_to_read"}
    for fig in figures:
        assert required_keys <= set(fig), (
            f"each figure needs {required_keys}, got {set(fig)}"
        )
        # file must be a bare basename (no traversal) — it rides into a distributable report
        assert (
            "/" not in fig["file"]
            and "\\" not in fig["file"]
            and ".." not in fig["file"]
        ), f"figure file must be a bare basename, got {fig['file']!r}"
        # the producer saved the actual (non-empty) PNG the consumer will embed
        png = tmp_path / fig["file"]
        assert png.exists(), f"figure PNG {fig['file']} was not saved by the viz cell"
        assert png.stat().st_size > 0, f"figure PNG {fig['file']} is empty"
        assert fig["title"].strip(), "title must be non-empty"
        assert fig["axes"].strip(), "axes (軸の説明) must be non-empty"
        assert fig["how_to_read"].strip(), "how_to_read (図の読み方) must be non-empty"


def test_verdict_metric_carries_effect_size_confidence_interval_and_sample_size(
    tmp_path: Path,
) -> None:
    """Epic 12 / ADR-0013: a metric may carry three optional, self-describing items so
    the analysis note and the report can show how large and how certain an effect is without computing
    anything itself.
    """
    metric = _run_fixture(tmp_path)["metrics"]["mean_diff"]

    effect_size = metric["effect_size"]
    assert set(effect_size) == {"kind", "value"}
    assert effect_size["kind"].strip(), "an effect size is unreadable without its kind"
    assert isinstance(effect_size["value"], float)

    interval = metric["confidence_interval"]
    assert set(interval) == {"level", "lower", "upper"}
    assert 0 < interval["level"] < 1, "level is a proportion (0.95), not a percentage"
    # the interval is the interval of the metric's own value
    assert interval["lower"] <= metric["value"] <= interval["upper"]

    assert isinstance(metric["sample_size"], int)
    assert metric["sample_size"] == 3, "observations the metric used (after data_prep)"


def test_verdict_metric_keeps_the_existing_keys(tmp_path: Path) -> None:
    """The three items are additions: the pre-ADR-0013 keys stay as they were."""
    metric = _run_fixture(tmp_path)["metrics"]["mean_diff"]
    assert {"value", "threshold", "pass"} <= set(metric)
