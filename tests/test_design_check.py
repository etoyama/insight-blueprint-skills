"""The check of the computation: what the code looks at, the record and its reader.

Epic 36, Story 36.4 (ADR-0070). US-4 AC 1: one result per subject. AC 2: the
code looks at the metrics, the figures and the order of the cells. AC 5: the
check remembers its verdict, and reads as not done once the verdict changed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from insight_blueprint.models.check import CheckResult, CheckSubject, verdict_digest
from insight_blueprint.validate import validate_schema
from skills._shared import design_check, design_io
from skills._shared._atomic import atomic_write_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    REPO_ROOT / "tests" / "integration" / "fixtures" / "sample_notebook.py"
).read_text(encoding="utf-8")
CRITERION = "supported at 2.0 days or more, rejected under 1.0 day"
VERDICT = {
    "conclusion": "the gap is two days",
    "metrics": {
        "wait_days_gap": {"value": 2.1, "support_line": 2.0, "judgment": "supported"},
        "missing_rate": {"value": 0.01, "threshold": 0.05, "pass": True},
    },
    "figures": [{"file": "LIB-H01_fig01.png", "title": "gap"}],
}
READ_BY_THE_AGENT = (
    "population",
    "grain",
    "denominator",
    "extraction",
    "compared_against",
    "criterion",
)


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    (base / "notebooks").mkdir()
    return base


def _confirmation(insight: Path) -> str:
    design_id = design_io.create_design(
        theme_id="LIB",
        title="Holding books longer",
        hypothesis_statement="A longer hold shortens the wait",
        hypothesis_background="Seven days leave many unclaimed",
        methodology={"method": "difference of means"},
        metrics=[
            {"target": "wait_days_gap", "tier": "primary", "comparison": CRITERION},
            {"target": "missing_rate", "tier": "guardrail", "comparison": "under 5%"},
        ],
        chart=[{"intent": "comparison", "type": "bar"}],
        base_dir=insight,
    )["id"]
    design_io.transition_status(design_id, "analyzing", insight)
    return design_id


def _exploration(insight: Path) -> str:
    design_id = design_io.create_design(
        theme_id="LIB",
        title="How long people wait",
        analysis_intent="exploratory",
        exploration_question="How far apart are the branches?",
        exploration_background="Nobody has measured the spread",
        methodology={"method": "describe"},
        metrics=[{"target": "wait_days_gap"}],
        base_dir=insight,
    )["id"]
    design_io.transition_status(design_id, "analyzing", insight)
    return design_id


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _save_result(
    insight: Path,
    design_id: str,
    verdict: dict | None = None,
    notebook: str = NOTEBOOK,
    *,
    not_saved: tuple[str, ...] = (),
) -> Path:
    """Write the notebook, the verdict and each figure it lists but *not_saved*."""
    notebooks = insight / "notebooks"
    (notebooks / f"{design_id}.py").write_text(notebook, encoding="utf-8")
    verdict = VERDICT if verdict is None else verdict
    for figure in verdict.get("figures", []):
        if figure.get("file") and figure["file"] not in not_saved:
            (notebooks / figure["file"]).write_bytes(PNG)
    path = notebooks / f"{design_id}_verdict.json"
    path.write_text(json.dumps(verdict), "utf-8")
    return path


def _payload(*, without: tuple[str, ...] = (), **items: dict) -> dict:
    """What a reader sends after reading ``VERDICT``, the verdict ``_save_result`` writes."""
    return _payload_for(VERDICT, without=without, **items)


def _payload_for(
    verdict: dict, *, without: tuple[str, ...] = (), **items: dict
) -> dict:
    return {
        "checked_by": "check_agent",
        "verdict_digest": verdict_digest(json.dumps(verdict).encode()),
        "items": [
            {"subject": subject, "result": "agrees"} | items.get(subject, {})
            for subject in READ_BY_THE_AGENT
            if subject not in without
        ],
    }


def _code_items(
    insight: Path, verdict: dict, notebook: str | None = NOTEBOOK
) -> dict[CheckSubject, design_check.CheckItem]:
    design_id = _confirmation(insight)
    design = validate_schema(design_io.load_design(design_id, insight))
    # The figures the verdict lists are on file, as a notebook that ran leaves them.
    _save_result(insight, design_id, verdict)
    notebooks = insight / "notebooks"
    items = design_check.code_items(design, verdict, notebook, notebooks)
    return {item.subject: item for item in items}


def _json(reading: design_check.CheckReading) -> dict:
    """The reading as ``design_io checked`` prints it."""
    return design_check.reading_json(reading)


def _record_path(insight: Path, design_id: str) -> Path:
    return insight / "designs" / f"{design_id}_check.yaml"


class TestTheCodeLooksAtTheMetrics:
    """US-4 AC 2: the metrics of the design and of the verdict, by name."""

    def test_the_same_names_agree(self, insight: Path) -> None:
        item = _code_items(insight, VERDICT)[CheckSubject.metrics]
        assert item.result is CheckResult.agrees

    def test_a_metric_of_the_design_missing_from_the_verdict_differs(
        self, insight: Path
    ) -> None:
        metrics = {"wait_days_gap": VERDICT["metrics"]["wait_days_gap"]}
        item = _code_items(insight, VERDICT | {"metrics": metrics})[
            CheckSubject.metrics
        ]
        assert item.result is CheckResult.differs
        assert "missing_rate" in item.note
        assert "wait_days_gap" not in item.note
        assert item.cell == "analysis"

    def test_a_metric_of_the_verdict_the_design_does_not_have_differs(
        self, insight: Path
    ) -> None:
        metrics = VERDICT["metrics"] | {"gap_against_last_year": {"value": 0.3}}
        item = _code_items(insight, VERDICT | {"metrics": metrics})[
            CheckSubject.metrics
        ]
        assert item.result is CheckResult.differs
        assert "gap_against_last_year" in item.note
        assert "missing_rate" not in item.note

    def test_a_renamed_metric_is_named_on_both_sides(self, insight: Path) -> None:
        metrics = {"gap": {"value": 2.1}, "missing_rate": {"value": 0.01}}
        item = _code_items(insight, VERDICT | {"metrics": metrics})[
            CheckSubject.metrics
        ]
        assert "wait_days_gap" in item.note and "「gap」" in item.note

    def test_a_verdict_without_metrics_misses_every_metric(self, insight: Path) -> None:
        verdict = {k: v for k, v in VERDICT.items() if k != "metrics"}
        item = _code_items(insight, verdict)[CheckSubject.metrics]
        assert item.result is CheckResult.differs
        assert "wait_days_gap" in item.note and "missing_rate" in item.note


class TestTheCodeLooksAtTheFigures:
    """US-4 AC 2: as many figures as the design specifies."""

    def test_as_many_figures_as_charts_agree(self, insight: Path) -> None:
        item = _code_items(insight, VERDICT)[CheckSubject.figures]
        assert item.result is CheckResult.agrees

    def test_another_number_of_figures_differs(self, insight: Path) -> None:
        figures = [*VERDICT["figures"], {"file": "LIB-H01_fig02.png"}]
        item = _code_items(insight, VERDICT | {"figures": figures})[
            CheckSubject.figures
        ]
        assert item.result is CheckResult.differs
        assert "2" in item.note and "1" in item.note
        assert item.cell == "viz"

    def test_a_verdict_without_figures_holds_none(self, insight: Path) -> None:
        verdict = {k: v for k, v in VERDICT.items() if k != "figures"}
        item = _code_items(insight, verdict)[CheckSubject.figures]
        assert item.result is CheckResult.differs
        assert "0" in item.note


class TestTheCodeLooksAtTheOrderOfTheCells:
    """US-4 AC 2: the seven cells of the contract, in order."""

    def test_the_cells_of_the_contract_agree(self, insight: Path) -> None:
        item = _code_items(insight, VERDICT)[CheckSubject.cells]
        assert item.result is CheckResult.agrees

    def test_a_notebook_without_one_of_the_cells_differs(self, insight: Path) -> None:
        notebook = NOTEBOOK.replace("# %% viz\n", "")
        item = _code_items(insight, VERDICT, notebook)[CheckSubject.cells]
        assert item.result is CheckResult.differs
        assert "data_load" in item.note
        assert item.cell is None

    def test_without_a_notebook_the_cells_are_not_checkable(
        self, insight: Path
    ) -> None:
        item = _code_items(insight, VERDICT, None)[CheckSubject.cells]
        assert item.result is CheckResult.not_checkable
        assert item.note

    def test_the_code_gives_its_three_subjects_and_no_other(
        self, insight: Path
    ) -> None:
        assert set(_code_items(insight, VERDICT)) == {
            CheckSubject.metrics,
            CheckSubject.figures,
            CheckSubject.cells,
        }


class TestTheCodeReadsTheResultAsTheNoteShowsIt:
    """The check compares the figures and the metrics the analysis note shows."""

    def test_a_figure_whose_file_is_missing_is_not_counted(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        charts = [{"intent": "comparison"}, {"intent": "trend"}]
        design_io.update_design(design_id, {"chart": charts}, insight)
        figures = [{"file": "LIB-H01_fig01.png"}, {"file": "LIB-H01_fig02.png"}]
        verdict = VERDICT | {"figures": figures}
        _save_result(insight, design_id, verdict, not_saved=("LIB-H01_fig02.png",))
        reading = design_check.record_check(design_id, _payload_for(verdict), insight)
        assert [d["subject"] for d in _json(reading)["differences"]] == ["figures"]
        assert "1 枚" in _json(reading)["differences"][0]["note"]

    def test_a_metric_that_is_not_an_object_is_not_counted(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        metrics = VERDICT["metrics"] | {"missing_rate": 0.01}
        verdict = VERDICT | {"metrics": metrics}
        _save_result(insight, design_id, verdict)
        reading = design_check.record_check(design_id, _payload_for(verdict), insight)
        assert [d["subject"] for d in _json(reading)["differences"]] == ["metrics"]
        assert "missing_rate" in _json(reading)["differences"][0]["note"]


class TestCheckWritesTheRecord:
    """US-4 AC 1: one record per design, one result per subject."""

    def test_a_confirmation_gets_all_nine_subjects(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        record = design_io.read_yaml(_record_path(insight, design_id))
        assert [i["subject"] for i in record["items"]] == [
            s.value for s in CheckSubject
        ]
        assert {i["result"] for i in record["items"]} == {"agrees"}
        assert record["design_id"] == design_id
        assert record["checked_by"] == "check_agent"

    def test_an_exploration_holds_no_criterion(self, insight: Path) -> None:
        design_id = _exploration(insight)
        verdict = {"metrics": {"wait_days_gap": {"value": 1.8}}, "figures": []}
        _save_result(insight, design_id, verdict)
        payload = _payload_for(verdict, without=("criterion",))
        design_check.record_check(design_id, payload, insight)
        record = design_io.read_yaml(_record_path(insight, design_id))
        assert "criterion" not in [i["subject"] for i in record["items"]]
        assert len(record["items"]) == 8

    def test_the_differences_come_back(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        metrics = VERDICT["metrics"] | {"gap_against_last_year": {"value": 0.3}}
        verdict = VERDICT | {"metrics": metrics}
        _save_result(insight, design_id, verdict)
        grain = {"result": "differs", "note": "per visit", "cell": "data_prep"}
        reading = design_check.record_check(
            design_id, _payload_for(verdict, grain=grain), insight
        )
        assert _json(reading)["checked"] is True
        assert [d["subject"] for d in _json(reading)["differences"]] == [
            "grain",
            "metrics",
        ]
        assert _json(reading)["differences"][0] == {"subject": "grain"} | grain

    def test_checking_again_replaces_the_record(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        grain = {"result": "differs", "note": "per visit", "cell": "data_prep"}
        design_check.record_check(design_id, _payload(grain=grain), insight)
        reading = design_check.record_check(
            design_id, _payload() | {"checked_by": "same_session"}, insight
        )
        assert _json(reading)["differences"] == []
        assert _json(reading)["checked_by"] == "same_session"

    def test_the_status_and_the_journal_stay_as_they_were(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        before = design_io.load_design(design_id, insight)
        design_check.record_check(design_id, _payload(), insight)
        assert design_io.load_design(design_id, insight) == before
        assert not (insight / "designs" / f"{design_id}_journal.yaml").exists()


class TestCheckRefusesWhatItCannotRecord:
    def _refused(self, insight: Path, design_id: str, payload: dict, match: str):
        with pytest.raises(ValueError, match=match):
            design_check.record_check(design_id, payload, insight)
        assert not _record_path(insight, design_id).exists()

    @pytest.mark.parametrize("subject", ["metrics", "figures", "cells"])
    def test_the_reader_cannot_answer_what_the_code_looks_at(
        self, insight: Path, subject: str
    ) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        payload = _payload()
        payload["items"].append({"subject": subject, "result": "agrees"})
        self._refused(insight, design_id, payload, subject)

    def test_a_subject_the_reader_left_out(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        self._refused(insight, design_id, _payload(without=("grain",)), "grain")

    def test_a_confirmation_without_its_criterion(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        self._refused(insight, design_id, _payload(without=("criterion",)), "criterion")

    def test_an_exploration_with_a_criterion(self, insight: Path) -> None:
        design_id = _exploration(insight)
        verdict = {"metrics": {"wait_days_gap": {}}}
        _save_result(insight, design_id, verdict)
        self._refused(insight, design_id, _payload_for(verdict), "criterion")

    def test_a_difference_without_its_cell(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        grain = {"result": "differs", "note": "per visit"}
        self._refused(insight, design_id, _payload(grain=grain), "cell")

    def test_no_word_on_who_checked(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        payload = {k: v for k, v in _payload().items() if k != "checked_by"}
        self._refused(insight, design_id, payload, "checked_by")

    def test_no_word_on_which_verdict_was_read(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        payload = {k: v for k, v in _payload().items() if k != "verdict_digest"}
        self._refused(insight, design_id, payload, "verdict_digest")

    def test_a_verdict_written_again_while_the_reader_read(self, insight: Path) -> None:
        """What the reader read of one verdict is not recorded for another."""
        design_id = _confirmation(insight)
        path = _save_result(insight, design_id)
        payload = _payload()
        path.write_text(json.dumps(VERDICT | {"conclusion": "rerun"}), "utf-8")
        self._refused(insight, design_id, payload, "changed")

    def test_a_payload_that_is_not_an_object(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        self._refused(insight, design_id, [], "payload")  # type: ignore[arg-type]

    def test_a_design_without_a_verdict(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        self._refused(insight, design_id, _payload(), "verdict")

    def test_a_verdict_that_is_not_json(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id).write_text("{not json", "utf-8")
        self._refused(insight, design_id, _payload(), "JSON")

    def test_a_design_that_does_not_exist(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            design_check.record_check("LIB-H09", _payload(), insight)


class TestTheReaderTellsWhetherTheCheckIsDone:
    """US-4 AC 5: done only for the verdict that is there now."""

    def test_without_a_verdict_there_is_nothing_to_check(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        assert _json(design_check.check_reading(design_id, insight)) == {
            "design_id": design_id,
            "has_verdict": False,
            "verdict_digest": None,
            "checked": False,
            "checked_by": None,
            "items": [],
            "differences": [],
        }

    def test_a_verdict_not_yet_checked(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        reading = design_check.check_reading(design_id, insight)
        assert (
            _json(reading)["has_verdict"] is True and _json(reading)["checked"] is False
        )
        # The name of the verdict a reader is about to read, to send back with its items.
        assert _json(reading)["verdict_digest"] == _payload()["verdict_digest"]

    def test_a_checked_verdict_reads_as_the_command_returned(
        self, insight: Path
    ) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        grain = {"result": "differs", "note": "per visit", "cell": "data_prep"}
        written = design_check.record_check(design_id, _payload(grain=grain), insight)
        reading = design_check.check_reading(design_id, insight)
        assert _json(reading) == _json(written)
        assert _json(reading)["checked"] is True
        assert len(_json(reading)["items"]) == 9

    def test_a_changed_verdict_reads_as_not_checked(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        path = _save_result(insight, design_id)
        grain = {"result": "differs", "note": "per visit", "cell": "data_prep"}
        design_check.record_check(design_id, _payload(grain=grain), insight)
        metrics = VERDICT["metrics"] | {"wait_days_gap": {"value": 0.4}}
        path.write_text(json.dumps(VERDICT | {"metrics": metrics}), "utf-8")
        reading = design_check.check_reading(design_id, insight)
        assert _json(reading)["checked"] is False
        # What was read against another verdict is not shown for this one.
        assert _json(reading)["items"] == [] and _json(reading)["differences"] == []
        assert _json(reading)["checked_by"] is None

    def test_a_verdict_written_again_with_the_same_text_stays_checked(
        self, insight: Path
    ) -> None:
        design_id = _confirmation(insight)
        path = _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        path.write_text(path.read_text("utf-8"), "utf-8")
        assert design_check.check_reading(design_id, insight).checked is True

    def test_checking_the_new_verdict_makes_it_done_again(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        path = _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        again = VERDICT | {"conclusion": "again"}
        path.write_text(json.dumps(again), "utf-8")
        design_check.record_check(design_id, _payload_for(again), insight)
        assert design_check.check_reading(design_id, insight).checked is True

    @pytest.mark.parametrize(
        "record",
        [b"items: nothing\n", b"- a list\n", b"key: [unclosed\n", b"\xff\xfe\x00"],
        ids=["another shape", "not a mapping", "broken YAML", "not UTF-8"],
    )
    def test_a_record_that_does_not_read_is_not_a_check(
        self, insight: Path, record: bytes
    ) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        _record_path(insight, design_id).write_bytes(record)
        assert design_check.check_reading(design_id, insight).checked is False

    def test_a_record_that_is_a_folder_is_not_a_check(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        _record_path(insight, design_id).mkdir()
        assert design_check.check_reading(design_id, insight).checked is False

    def test_the_record_of_another_design_is_not_a_check(self, insight: Path) -> None:
        design_id, other = _confirmation(insight), _confirmation(insight)
        _save_result(insight, design_id)
        _save_result(insight, other)
        design_check.record_check(design_id, _payload(), insight)
        _record_path(insight, other).write_bytes(
            _record_path(insight, design_id).read_bytes()
        )
        assert design_check.check_reading(other, insight).checked is False

    def test_a_design_that_does_not_read_is_not_checked(self, insight: Path) -> None:
        """It does not stop the reading either: a page reads many designs."""
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        design = insight / "designs" / f"{design_id}_hypothesis.yaml"
        design.write_text("key: [unclosed\n", "utf-8")
        assert design_check.check_reading(design_id, insight).checked is False

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file of mode 000")
    def test_a_verdict_that_cannot_be_read_is_not_checked(self, insight: Path) -> None:
        """It does not stop the reading, as a record or a design that does not read."""
        design_id = _confirmation(insight)
        path = _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        path.chmod(0)
        try:
            reading = design_check.check_reading(design_id, insight)
        finally:
            path.chmod(0o644)
        assert reading.checked is False
        assert reading.has_verdict is True and reading.verdict_digest is None

    def test_a_design_changed_after_the_check_reads_as_not_checked(
        self, insight: Path
    ) -> None:
        """ADR-0070 7: a difference of the design before the change is not shown."""
        design_id = _confirmation(insight)
        metrics = VERDICT["metrics"] | {"gap_against_last_year": {"value": 0.3}}
        verdict = VERDICT | {"metrics": metrics}
        _save_result(insight, design_id, verdict)
        design_check.record_check(design_id, _payload_for(verdict), insight)
        held = design_io.load_design(design_id, insight)["metrics"]
        design_io.update_design(
            design_id,
            {
                "metrics": [
                    *held,
                    {"target": "gap_against_last_year", "tier": "secondary"},
                ]
            },
            insight,
        )
        reading = design_check.check_reading(design_id, insight)
        assert (
            _json(reading)["checked"] is False and _json(reading)["differences"] == []
        )
        again = design_check.record_check(design_id, _payload_for(verdict), insight)
        assert _json(again)["checked"] is True and _json(again)["differences"] == []

    def test_another_chart_reads_as_not_checked(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        charts = [{"intent": "comparison"}, {"intent": "trend"}]
        design_io.update_design(design_id, {"chart": charts}, insight)
        assert design_check.check_reading(design_id, insight).checked is False

    def test_a_field_the_check_does_not_read_keeps_the_check(
        self, insight: Path
    ) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        design_io.update_design(
            design_id,
            {"title": "Another title", "referenced_knowledge": {"src": ["K1"]}},
            insight,
        )
        assert design_check.check_reading(design_id, insight).checked is True

    def test_a_write_that_fills_a_default_the_file_left_out_keeps_the_check(
        self, insight: Path
    ) -> None:
        """The design is named as it validates, not as the file spells it."""
        design_id = _confirmation(insight)
        path = insight / "designs" / f"{design_id}_hypothesis.yaml"
        data = design_io.read_yaml(path)
        del data["metrics"][0]["tier"]
        atomic_write_yaml(path, data)
        _save_result(insight, design_id)
        assert design_check.record_check(design_id, _payload(), insight).checked
        design_io.update_design(
            design_id, {"referenced_knowledge": {"src": ["K1"]}}, insight
        )
        assert design_check.check_reading(design_id, insight).checked is True

    def test_a_move_of_the_status_keeps_the_check(self, insight: Path) -> None:
        """A review of the result sends the design to in_review and back."""
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        design_io.transition_status(design_id, "in_review", insight)
        assert design_check.check_reading(design_id, insight).checked is True

    def test_an_id_that_is_not_one_is_refused(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="design_id"):
            design_check.check_reading("../LIB-H01", insight)

    def test_a_linked_verdict_is_not_read(self, insight: Path, tmp_path: Path) -> None:
        design_id = _confirmation(insight)
        elsewhere = tmp_path / "verdict.json"
        elsewhere.write_text(json.dumps(VERDICT), "utf-8")
        (insight / "notebooks" / f"{design_id}_verdict.json").symlink_to(elsewhere)
        assert design_check.check_reading(design_id, insight).has_verdict is False


def _cli(insight: Path, *argv: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "skills._shared.design_io", *argv]
        + ["--base-dir", str(insight)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestTheCommandsOfDesignIo:
    def test_check_writes_the_record_and_prints_the_reading(
        self, insight: Path
    ) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        run = _cli(insight, "check", "--id", design_id, stdin=json.dumps(_payload()))
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout)["checked"] is True
        assert _record_path(insight, design_id).exists()

    def test_checked_reads_it_back_without_stdin(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        design_check.record_check(design_id, _payload(), insight)
        run = _cli(insight, "checked", "--id", design_id)
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout) == _json(
            design_check.check_reading(design_id, insight)
        )

    def test_a_refused_check_writes_nothing(self, insight: Path) -> None:
        design_id = _confirmation(insight)
        _save_result(insight, design_id)
        payload = json.dumps(_payload(without=("grain",)))
        run = _cli(insight, "check", "--id", design_id, stdin=payload)
        assert run.returncode != 0
        assert not _record_path(insight, design_id).exists()
