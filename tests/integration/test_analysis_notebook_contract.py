"""Integration test for the /analysis-notebook contract mechanics (Epic 07, Epic 30).

Guards the execution path the skill relies on: run the reference notebook, a plain
Python script cut into ``# %% <name>`` cells (ADR-0045), with ``python`` in one step and
assert the verdict JSON side-effect + Mermaid lineage export. The fixture's shape is
checked by the analysis note's own cut (``notebook_cells``), not a second parser. The run is skipped when
the optional `notebook` extra (pandas/matplotlib) is not installed — matching how a minimal install
lacks the analysis-runtime deps.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skills._shared.design_note import CodeCell
from skills._shared.design_note_read import (
    CONTRACT_CELLS,
    DATA_LOAD_CELL,
    notebook_cells,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_notebook.py"
CONTRACT = (
    Path(__file__).parents[2]
    / "skills"
    / "analysis-notebook"
    / "references"
    / "notebook-contract.md"
)


def _run_fixture(tmp_path: Path) -> dict:
    """Run the reference notebook in ``tmp_path`` with one ``python`` command — the
    skill's execution mechanism — and return the verdict side-effect.
    """
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    nb = tmp_path / "SAMPLE.py"
    shutil.copy(FIXTURE, nb)
    run = subprocess.run(
        [sys.executable, str(nb)], cwd=tmp_path, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    return json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))


def _shown_cells() -> tuple[CodeCell, ...]:
    """The fixture's cells as the analysis note cuts them (data_load left out)."""
    cells = notebook_cells(FIXTURE.read_text(encoding="utf-8"))
    assert cells is not None, "the cut found the fixture out of the contract's shape"
    return cells


def _contract_cell_names() -> list[str]:
    table = CONTRACT.read_text(encoding="utf-8").split("## Cells", 1)[1]
    return re.findall(r"^\| `(\w+)` \|", table.split("\n## ", 1)[0], re.M)


class TestTheSampleIsLaidOutAsTheContractSays:
    """US-1 AC 2: the reference notebook is the contract's form, not marimo's."""

    def test_the_cut_knows_the_contract_cells_in_order(self) -> None:
        assert list(CONTRACT_CELLS) == _contract_cell_names()

    def test_the_note_cuts_it_into_the_six_cells_but_data_load(self) -> None:
        assert [c.name for c in _shown_cells()] == [
            name for name in CONTRACT_CELLS if name != DATA_LOAD_CELL
        ]

    def test_each_contract_variable_is_assigned_in_one_cell(self) -> None:
        owners: dict[str, list[str]] = {}
        for cell in _shown_cells():
            for node in ast.walk(ast.parse(cell.source)):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    owners.setdefault(node.id, [])
                    if cell.name not in owners[node.id]:
                        owners[node.id].append(cell.name)
        # The cut lets through only a notebook that binds raw_df in data_load
        # alone and puts nothing but the docstring before the first cell.
        assert "raw_df" not in owners
        assert "session" not in owners
        assert "session = LineageSession(" in FIXTURE.read_text(encoding="utf-8")
        assert owners["df_clean"] == ["data_prep"]
        assert owners["results"] == ["analysis"]
        assert owners["figure_manifest"] == ["viz"]
        assert owners["verdict"] == ["verdict"]

    def test_it_does_not_use_marimo(self) -> None:
        assert "marimo" not in FIXTURE.read_text(encoding="utf-8")


def test_notebook_contract_run_and_sideeffects(tmp_path: Path) -> None:
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
