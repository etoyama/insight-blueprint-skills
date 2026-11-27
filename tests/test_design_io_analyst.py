"""The commands that ask the analyst, record the answer, and stop (ADR-0064 8).

Story 35.2, US-4 AC 5: the marks of a confirmation, its answer and a stop are
written only by these commands of design_io. The stage they lead to is the one
of the State Diagram in docs/design/epic-35-hand-over-questions.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from insight_blueprint.models.analysis_stage import MARKS, AnalysisStage
from skills._shared import design_io

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    return base


ASKS_ANALYST, ANSWERS, STOPPED = MARKS


def _design(insight: Path, status: str = "analyzing") -> str:
    design_id = design_io.create_design(
        theme_id="FP",
        title="Test",
        analysis_intent="exploratory",
        exploration_question="How far apart are the regions?",
        exploration_background="Nobody has measured the spread",
        methodology={"method": "describe"},
        base_dir=insight,
    )["id"]
    if status != "in_review":
        design_io.transition_status(design_id, "analyzing", insight)
    if status == "explored":
        design_io.transition_status(design_id, "explored", insight)
    return design_id


def _stage(insight: Path, design_id: str) -> AnalysisStage:
    return design_io.stage_reading(design_id, insight).stage


def _observe(insight: Path, design_id: str) -> None:
    design_io.append_journal_event(
        design_id, {"type": "observe", "content": "seen"}, insight
    )


class TestAskAnalyst:
    def test_it_writes_a_question_with_the_mark(self, insight: Path) -> None:
        design_id = _design(insight)

        event = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        assert event["type"] == "question"
        assert event["content"] == "分母を変えないと進めない"
        assert event["metadata"] == {ASKS_ANALYST: True}
        assert design_io.journal_events(design_id, insight) == [event]

    def test_a_running_analysis_then_waits_for_the_analyst(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        assert _stage(insight, design_id) is AnalysisStage.awaiting_confirmation

    def test_an_empty_question_is_refused(self, insight: Path) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError, match="empty"):
            design_io.ask_analyst(design_id, "  ", insight)
        assert design_io.journal_events(design_id, insight) == []

    @pytest.mark.parametrize("status", ["in_review", "explored"])
    def test_only_a_running_analysis_asks(self, insight: Path, status: str) -> None:
        design_id = _design(insight, status)

        with pytest.raises(ValueError, match="running"):
            design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

    def test_an_analysis_with_results_does_not_ask(self, insight: Path) -> None:
        design_id = _design(insight)
        _observe(insight, design_id)

        with pytest.raises(ValueError, match="awaiting_reflection"):
            design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

    def test_a_missing_design_is_refused(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            design_io.ask_analyst("FP-H09", "分母を変えないと進めない", insight)


class TestAnswerAnalyst:
    def test_it_writes_a_decision_naming_the_confirmation(self, insight: Path) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        event = design_io.answer_analyst(
            design_id, asked["id"], "分母は貸出の数のまま", insight
        )

        assert event["type"] == "decide"
        assert event["content"] == "分母は貸出の数のまま"
        assert event["metadata"] == {ANSWERS: asked["id"]}

    def test_the_analysis_runs_again_after_the_answer(self, insight: Path) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
        design_io.answer_analyst(design_id, asked["id"], "そのまま", insight)

        assert _stage(insight, design_id) is AnalysisStage.running

    def test_an_answered_confirmation_is_not_answered_twice(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
        design_io.answer_analyst(design_id, asked["id"], "そのまま", insight)

        with pytest.raises(ValueError, match="already answered"):
            design_io.answer_analyst(design_id, asked["id"], "やはり変える", insight)

    def test_an_event_that_is_not_a_confirmation_is_refused(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _observe(insight, design_id)

        with pytest.raises(ValueError, match="not a confirmation"):
            design_io.answer_analyst(design_id, f"{design_id}-E01", "x", insight)

    def test_an_unknown_event_is_refused(self, insight: Path) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError, match="not a confirmation"):
            design_io.answer_analyst(design_id, f"{design_id}-E07", "x", insight)

    def test_an_empty_answer_is_refused(self, insight: Path) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        with pytest.raises(ValueError, match="empty"):
            design_io.answer_analyst(design_id, asked["id"], "", insight)

    def test_a_stopped_analysis_takes_no_answer(self, insight: Path) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match="stopped"):
            design_io.answer_analyst(design_id, asked["id"], "そのまま", insight)


class TestStopAnalysis:
    def test_it_writes_the_reason_with_the_mark(self, insight: Path) -> None:
        design_id = _design(insight)

        event = design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        assert event["type"] == "decide"
        assert event["content"] == "先に別の論点を見る"
        assert event["metadata"] == {STOPPED: True}
        assert _stage(insight, design_id) is AnalysisStage.stopped

    def test_the_status_of_the_design_does_not_change(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        assert design_io.load_design(design_id, insight)["status"] == "analyzing"

    def test_a_design_not_handed_over_can_be_stopped(self, insight: Path) -> None:
        design_id = _design(insight, "in_review")
        design_io.stop_analysis(design_id, "今回は任せない", insight)

        assert _stage(insight, design_id) is AnalysisStage.stopped

    def test_an_analysis_waiting_for_the_analyst_can_be_stopped(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        assert _stage(insight, design_id) is AnalysisStage.stopped

    def test_a_stopped_analysis_is_not_stopped_again(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match="stopped"):
            design_io.stop_analysis(design_id, "もう一度", insight)

    def test_a_finished_analysis_is_not_stopped(self, insight: Path) -> None:
        design_id = _design(insight, "explored")

        with pytest.raises(ValueError, match="finished"):
            design_io.stop_analysis(design_id, "x", insight)

    def test_an_analysis_with_results_waits_for_its_reflection(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _observe(insight, design_id)

        with pytest.raises(ValueError, match="awaiting_reflection"):
            design_io.stop_analysis(design_id, "x", insight)

    def test_an_empty_reason_is_refused(self, insight: Path) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError, match="empty"):
            design_io.stop_analysis(design_id, "", insight)


class TestOnlyTheCommandsWriteTheMarks:
    @pytest.mark.parametrize("mark", [ASKS_ANALYST, ANSWERS, STOPPED])
    def test_appending_an_event_with_a_mark_is_refused(
        self, insight: Path, mark: str
    ) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError, match=mark):
            design_io.append_journal_event(
                design_id,
                {"type": "decide", "content": "x", "metadata": {mark: True}},
                insight,
            )
        assert design_io.journal_events(design_id, insight) == []


def _cli(insight: Path, *args: str, payload: dict | None = None):
    return subprocess.run(
        [sys.executable, "-m", "skills._shared.design_io", *args],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestCommandLine:
    def test_ask_answer_and_stop_run_from_the_command_line(self, insight: Path) -> None:
        design_id = _design(insight)

        asked = _cli(
            insight,
            "ask-analyst",
            "--base-dir",
            str(insight),
            "--id",
            design_id,
            payload={"content": "分母を変えないと進めない"},
        )
        assert asked.returncode == 0, asked.stderr
        question_id = json.loads(asked.stdout)["id"]

        answered = _cli(
            insight,
            "answer-analyst",
            "--base-dir",
            str(insight),
            "--id",
            design_id,
            payload={"answers": question_id, "content": "そのまま"},
        )
        assert answered.returncode == 0, answered.stderr
        assert json.loads(answered.stdout)["metadata"] == {ANSWERS: question_id}

        stopped = _cli(
            insight,
            "stop",
            "--base-dir",
            str(insight),
            "--id",
            design_id,
            payload={"content": "先に別の論点を見る"},
        )
        assert stopped.returncode == 0, stopped.stderr
        assert _stage(insight, design_id) is AnalysisStage.stopped


def test_a_design_without_a_valid_status_is_refused_with_a_reason(
    insight: Path,
) -> None:
    path = insight / "designs" / "FP-H01_hypothesis.yaml"
    path.write_text("id: FP-H01\ntitle: broken\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no valid status"):
        design_io.stop_analysis("FP-H01", "x", insight)


def test_reasoning_journaled_before_the_run_does_not_block_a_confirmation(
    insight: Path,
) -> None:
    """ADR-0061 6.4 as amended: /analysis-journal may run before the analysis."""
    design_id = _design(insight, "in_review")
    design_io.append_journal_event(
        design_id, {"type": "hypothesize", "content": "延ばすと減る"}, insight
    )
    design_io.transition_status(design_id, "analyzing", insight)

    assert _stage(insight, design_id) is AnalysisStage.running
    design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
