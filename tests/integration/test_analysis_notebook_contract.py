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

from skills._shared.design_note import (
    CodeCell,
    render_note,
)
from skills._shared.design_note_read import (
    CONTRACT_CELLS,
    DATA_LOAD_CELL,
    load_design_note,
    notebook_cells,
)
from skills._shared.verdict_table import (
    MetricJudgment,
    VerdictMetric,
)
from tests._saved_verdicts import save_design_with_verdict, table_rows

FIXTURE = Path(__file__).parent / "fixtures" / "sample_notebook.py"
EXPLORATION_FIXTURE = (
    Path(__file__).parent / "fixtures" / "sample_exploration_notebook.py"
)
CONTRACT = (
    Path(__file__).parents[2]
    / "skills"
    / "analysis-notebook"
    / "references"
    / "notebook-contract.md"
)


def _run_fixture(tmp_path: Path, fixture: Path = FIXTURE) -> dict:
    """Run a reference notebook in ``tmp_path`` with one ``python`` command — the
    skill's execution mechanism — and return the verdict side-effect.
    """
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    nb = tmp_path / fixture.name
    shutil.copy(fixture, nb)
    run = subprocess.run(
        [sys.executable, str(nb)], cwd=tmp_path, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    return json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))


def _shown_cells(fixture: Path = FIXTURE) -> tuple[CodeCell, ...]:
    """The fixture's cells as the analysis note cuts them (data_load left out)."""
    cells = notebook_cells(fixture.read_text(encoding="utf-8"))
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


def test_verdict_metric_carries_effect_size_interval_and_sample_size(
    tmp_path: Path,
) -> None:
    """Epic 12 / ADR-0013: a metric may carry three optional, self-describing items so
    the analysis note and the report can show how large and how certain an effect is without computing
    anything itself. Epic 33 / ADR-0052: the interval names its kind.
    """
    metric = _run_fixture(tmp_path)["metrics"]["mean_diff"]

    effect_size = metric["effect_size"]
    assert set(effect_size) == {"kind", "value"}
    assert effect_size["kind"].strip(), "an effect size is unreadable without its kind"
    assert isinstance(effect_size["value"], float)

    interval = metric["interval"]
    assert set(interval) == {"kind", "level", "lower", "upper"}
    assert interval["kind"] == "confidence"
    assert 0 < interval["level"] < 1, "level is a proportion (0.95), not a percentage"
    # the interval is the interval of the metric's own value
    assert interval["lower"] <= metric["value"] <= interval["upper"]

    assert isinstance(metric["sample_size"], int)
    assert metric["sample_size"] == 3, "observations the metric used (after data_prep)"


LINES = {"support_line", "reject_line"}
PASS_ITEMS = {"threshold", "pass"}


def _read_back(tmp_path: Path, fixture: Path, intent: str) -> dict[str, VerdictMetric]:
    """The metrics the analysis note reads from the verdict the fixture wrote."""
    _run_fixture(tmp_path, fixture)
    insight = tmp_path / ".insight"
    design_id = save_design_with_verdict(
        insight, intent, (tmp_path / "verdict.json").read_text(encoding="utf-8")
    )
    verdict = load_design_note(design_id, base_dir=insight).verdict
    assert verdict is not None
    return {metric.name: metric for metric in verdict.metrics}


def _note_tables(tmp_path: Path, fixture: Path, intent: str) -> list[list[list[str]]]:
    """The tables under 指標の値 of the note made from the verdict the fixture wrote."""
    _run_fixture(tmp_path, fixture)
    insight = tmp_path / ".insight"
    design_id = save_design_with_verdict(
        insight, intent, (tmp_path / "verdict.json").read_text(encoding="utf-8")
    )
    note = str(render_note(load_design_note(design_id, base_dir=insight)))
    values = note.split("指標の値", 1)[1].split("<h3", 1)[0]
    return [table_rows(t) for t in re.findall(r"<table>.*?</table>", values, re.S)]


class TestTheNoteTabulatesWhatTheSampleWrote:
    """Epic 33 US-1 AC 3, US-2 AC 2, AC 4 (Story 33.2): the sample's verdict, in the note."""

    def test_the_primary_metric_shows_its_lines_and_judgment_beside_the_guardrail(
        self, tmp_path: Path
    ) -> None:
        main, _ = _note_tables(tmp_path, FIXTURE, "confirmatory")

        rows = {row[0]: dict(zip(main[0], row, strict=True)) for row in main[1:]}
        assert set(rows) == {"mean_diff", "null_rate"}
        primary = rows["mean_diff"]
        assert (primary["支持の線"], primary["棄却の線"], primary["判定"]) == (
            "5.0",
            "1.0",
            "支持",
        )
        assert primary["区間"].startswith("信頼区間 水準 0.95: [")
        guardrail = rows["null_rate"]
        assert (guardrail["しきい値"], guardrail["合否"], guardrail["判定"]) == (
            "0.5",
            "✓",
            "—",
        )

    def test_the_groups_come_in_a_table_of_their_own(self, tmp_path: Path) -> None:
        _, grouped = _note_tables(tmp_path, FIXTURE, "confirmatory")

        assert grouped == [["group", "値", "N"], ["A", "11.0", "2"], ["B", "20.0", "1"]]

    def test_the_exploration_measures_without_lines_or_a_judgment(
        self, tmp_path: Path
    ) -> None:
        main, grouped = _note_tables(tmp_path, EXPLORATION_FIXTURE, "exploratory")

        assert main[0] == ["指標", "値", "効果量", "区間", "N"]
        assert grouped[0] == ["branch", "値", "N"]


class TestTheSampleJudgesItsPrimaryMetricByTwoLines:
    """Epic 33 US-1 AC 1, AC 2 (ADR-0052): lines and a judgment, or a threshold and a pass."""

    def test_the_primary_metric_holds_its_lines_and_its_judgment(
        self, tmp_path: Path
    ) -> None:
        metric = _run_fixture(tmp_path)["metrics"]["mean_diff"]
        assert LINES <= set(metric)
        assert metric["judgment"] in {"supported", "rejected", "inconclusive"}
        assert not PASS_ITEMS & set(metric)

    def test_the_guardrail_metric_holds_a_threshold_and_a_pass(
        self, tmp_path: Path
    ) -> None:
        metric = _run_fixture(tmp_path)["metrics"]["null_rate"]
        assert PASS_ITEMS <= set(metric)
        assert not (LINES | {"judgment"}) & set(metric)

    def test_the_overall_direction_is_the_judgment_of_the_primary_metric(
        self,
    ) -> None:
        """The contract: hypothesis_direction never disagrees with the judgment."""
        (analysis,) = [c for c in _shown_cells() if c.name == "analysis"]
        assert '"hypothesis_direction": judgment,' in analysis.source
        assert '"judgment": judgment,' in analysis.source

    def test_the_note_reads_the_lines_and_the_judgment_back(
        self, tmp_path: Path
    ) -> None:
        metrics = _read_back(tmp_path, FIXTURE, "confirmatory")

        primary = metrics["mean_diff"]
        assert (primary.support_line, primary.reject_line) == ("5.0", "1.0")
        assert primary.value == "9.0"
        assert primary.judgment is MetricJudgment.supported
        assert (primary.threshold, primary.passed) == (None, None)
        assert primary.interval is not None
        assert (primary.interval.kind, primary.interval.level) == ("confidence", "0.95")

        guardrail = metrics["null_rate"]
        assert (guardrail.value, guardrail.threshold) == ("0.25", "0.5")
        assert guardrail.passed is True
        assert guardrail.judgment is None

    def test_the_note_reads_the_rows_of_the_groups_back(self, tmp_path: Path) -> None:
        grouped = _read_back(tmp_path, FIXTURE, "confirmatory")["mean_by_group"]

        assert grouped.by == ("group",)
        assert grouped.value is None
        assert [(row.group, row.value, row.sample_size) for row in grouped.groups] == [
            (("A",), "11.0", "2"),
            (("B",), "20.0", "1"),
        ]


def _docstring(fixture: Path) -> list[str]:
    docstring = ast.get_docstring(ast.parse(fixture.read_text(encoding="utf-8")))
    assert docstring is not None
    return docstring.splitlines()


def _results_keys(fixture: Path) -> set[str]:
    """The keys of the ``results`` dict the analysis cell assigns."""
    (analysis,) = [c for c in _shown_cells(fixture) if c.name == "analysis"]
    for node in ast.walk(ast.parse(analysis.source)):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Dict)
            and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["results"]
        ):
            return {ast.literal_eval(k) for k in node.value.keys if k is not None}
    raise AssertionError("the analysis cell assigns no results dict")


class TestTheExplorationSampleKeepsWhatItMeasured:
    """Epic 32 US-3 AC 1, AC 4: an exploration runs without a prediction or a pass."""

    def test_the_note_cuts_it_into_the_six_cells_but_data_load(self) -> None:
        assert [c.name for c in _shown_cells(EXPLORATION_FIXTURE)] == [
            name for name in CONTRACT_CELLS if name != DATA_LOAD_CELL
        ]

    def test_its_results_hold_no_prediction(self) -> None:
        keys = _results_keys(EXPLORATION_FIXTURE)
        assert "metrics" in keys
        assert not keys & {"hypothesis_direction", "decision_reason"}

    def test_its_verdict_keeps_the_measured_values(self, tmp_path: Path) -> None:
        metrics = _run_fixture(tmp_path, EXPLORATION_FIXTURE)["metrics"]
        assert metrics
        for metric in metrics.values():
            assert not (PASS_ITEMS | LINES | {"judgment"}) & set(metric)
        assert isinstance(metrics["wait_days_gap"]["value"], float)

    def test_the_note_reads_its_interval_and_its_groups_back(
        self, tmp_path: Path
    ) -> None:
        metrics = _read_back(tmp_path, EXPLORATION_FIXTURE, "exploratory")

        gap = metrics["wait_days_gap"]
        assert gap.interval is not None
        assert gap.interval.kind == "confidence"
        assert (gap.support_line, gap.reject_line, gap.judgment) == (None, None, None)

        by_branch = metrics["wait_days_by_branch"]
        assert by_branch.by == ("branch",)
        assert [row.group for row in by_branch.groups] == [("annex",), ("main",)]
        assert all(row.value is not None for row in by_branch.groups)

    def test_its_docstring_states_the_question(self) -> None:
        lines = _docstring(EXPLORATION_FIXTURE)
        assert "- Intent: exploratory" in lines
        assert any(line.startswith("- Question: ") for line in lines)
        assert not any(line.startswith("- Hypothesis: ") for line in lines)

    def test_its_docstring_escapes_the_quote_in_the_question(self) -> None:
        """The file writes the quote escaped, and Python reads it back as the question."""
        source = EXPLORATION_FIXTURE.read_text(encoding="utf-8")
        assert '- Question: how are \\"wait days\\" spread across branches?' in source
        assert '- Question: how are "wait days" spread across branches?' in (
            _docstring(EXPLORATION_FIXTURE)
        )

    def test_the_confirmation_docstring_states_the_hypothesis(self) -> None:
        lines = _docstring(FIXTURE)
        assert any(line.startswith("- Hypothesis: ") for line in lines)
        assert not any(line.startswith("- Question: ") for line in lines)
