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


def test_notebook_contract_export_run_and_sideeffects(tmp_path: Path) -> None:
    nb = tmp_path / "SAMPLE.py"
    shutil.copy(FIXTURE, nb)
    flat = tmp_path / "SAMPLE_flat.py"

    # 1) marimo export script (no nbformat needed) — the skill's execution mechanism
    export = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "script", str(nb), "-o", str(flat)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert export.returncode == 0, export.stderr
    assert flat.exists()

    # 2) run the flat script; cell side-effects land in cwd
    run = subprocess.run(
        [sys.executable, str(flat)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr

    # 3) verdict JSON side-effect (what the skill reads to build journal events)
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert {"conclusion", "evidence_summary", "open_questions"} <= set(verdict)
    assert isinstance(verdict["evidence_summary"], list)

    # 4) lineage Mermaid export (tracked_pipe recorded the dropna step: 4 -> 3 rows)
    mmd = (tmp_path / "lineage.mmd").read_text(encoding="utf-8")
    assert mmd.startswith("graph LR")
    assert "4 rows" in mmd and "3 rows" in mmd


def test_notebook_contract_figures_manifest(tmp_path: Path) -> None:
    """Epic 10 / ADR-0008: the viz cell saves PNG(s) and the verdict cell records a
    ``figures[]`` manifest so /analysis-report (a read-only consumer) can lay figures out
    with axis + how-to-read captions without re-rendering. The figure's truth lives with
    the producer (notebook), not with design.chart[].
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

    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))

    # figures[] manifest is part of the verdict side-effect (verdict enrich, not a new file)
    assert "figures" in verdict, "verdict must carry a 'figures' manifest (ADR-0008)"
    figures = verdict["figures"]
    assert isinstance(figures, list) and figures, "figures must be a non-empty list"

    required_keys = {"file", "title", "axes", "how_to_read"}
    for fig in figures:
        assert required_keys <= set(fig), (
            f"each figure needs {required_keys}, got {set(fig)}"
        )
        # the producer saved the actual PNG the consumer will embed
        png = tmp_path / fig["file"]
        assert png.exists(), f"figure PNG {fig['file']} was not saved by the viz cell"
        assert fig["axes"].strip(), "axes (軸の説明) must be non-empty"
        assert fig["how_to_read"].strip(), "how_to_read (図の読み方) must be non-empty"
