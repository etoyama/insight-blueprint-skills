"""The analysis stage is derived, never stored (ADR-0061 6, Story 35.2, US-3 AC 1).

One rule, in the order of ADR-0061: the first line that holds decides.
"""

from __future__ import annotations

import pytest

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus
from skills._shared.analysis_stage import (
    MARKS,
    AnalysisStage,
    answer,
    answers_of,
    asks_analyst,
    confirmation,
    stop,
    stops,
)

ASKS_ANALYST, ANSWERS, STOPPED = MARKS


def _ask(event_id: str = "FP-H01-E01") -> dict:
    return {
        "id": event_id,
        "type": "question",
        "content": "分母を変えないと進めない",
        "metadata": {ASKS_ANALYST: True},
    }


def _answer(question_id: str = "FP-H01-E01", event_id: str = "FP-H01-E02") -> dict:
    return {
        "id": event_id,
        "type": "decide",
        "content": "分母は貸出の数のまま",
        "metadata": {ANSWERS: question_id},
    }


def _stop(event_id: str = "FP-H01-E09") -> dict:
    return {
        "id": event_id,
        "type": "decide",
        "content": "別の論点を先に見る",
        "metadata": {STOPPED: True},
    }


def _event(kind: str, event_id: str = "FP-H01-E05") -> dict:
    return {"id": event_id, "type": kind, "content": "x", "metadata": {}}


ANALYZING = DesignStatus.analyzing


class TestOrderOfTheRule:
    @pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
    def test_a_terminal_status_is_finished_even_with_a_stop_mark(
        self, status: DesignStatus
    ) -> None:
        assert AnalysisStage.of(status, [_stop()]) is AnalysisStage.finished

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested, ANALYZING]
    )
    def test_a_stop_mark_is_stopped_before_the_end(self, status: DesignStatus) -> None:
        assert AnalysisStage.of(status, [_stop()]) is AnalysisStage.stopped

    def test_a_stop_mark_wins_over_an_open_confirmation(self) -> None:
        stage = AnalysisStage.of(ANALYZING, [_ask(), _stop()])
        assert stage is AnalysisStage.stopped

    def test_a_confirmation_without_an_answer_waits_for_the_analyst(self) -> None:
        stage = AnalysisStage.of(ANALYZING, [_ask()])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_an_open_confirmation_wins_over_recorded_results(self) -> None:
        stage = AnalysisStage.of(ANALYZING, [_event("observe"), _ask("FP-H01-E06")])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_an_answered_confirmation_runs_again(self) -> None:
        stage = AnalysisStage.of(ANALYZING, [_ask(), _answer()])
        assert stage is AnalysisStage.running

    def test_one_open_confirmation_among_answered_ones_still_waits(self) -> None:
        events = [_ask(), _answer(), _ask("FP-H01-E03")]
        assert (
            AnalysisStage.of(ANALYZING, events) is AnalysisStage.awaiting_confirmation
        )

    @pytest.mark.parametrize(
        "kind", ["observe", "evidence", "question", "decide", "conclude", "reflect"]
    )
    def test_an_analyzing_design_with_a_result_waits_for_its_reflection(
        self, kind: str
    ) -> None:
        stage = AnalysisStage.of(ANALYZING, [_event(kind)])
        assert stage is AnalysisStage.awaiting_reflection

    def test_an_analyzing_design_with_only_a_hearing_is_running(self) -> None:
        stage = AnalysisStage.of(ANALYZING, [_event("hearing")])
        assert stage is AnalysisStage.running

    def test_an_analyzing_design_without_events_is_running(self) -> None:
        assert AnalysisStage.of(ANALYZING, []) is AnalysisStage.running

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested]
    )
    def test_a_design_before_analysis_is_before_run(self, status: DesignStatus) -> None:
        stage = AnalysisStage.of(status, [_event("observe")])
        assert stage is AnalysisStage.before_run


class TestMarksCountOnlyOnTheirEvents:
    """A mark counts on the event its command writes, nowhere else (ADR-0064 8)."""

    def test_a_decide_event_that_asks_is_not_a_confirmation(self) -> None:
        event = {**_answer(), "metadata": {ASKS_ANALYST: True}}
        stage = AnalysisStage.of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection

    def test_a_question_event_with_a_stop_mark_does_not_stop(self) -> None:
        event = {**_event("question"), "metadata": {STOPPED: True}}
        stage = AnalysisStage.of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection

    def test_an_answer_naming_another_event_leaves_the_confirmation_open(
        self,
    ) -> None:
        stage = AnalysisStage.of(ANALYZING, [_ask(), _answer("FP-H01-E07")])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_a_hand_edited_metadata_that_is_not_a_mapping_is_no_mark(self) -> None:
        event = {**_event("decide"), "metadata": "stopped"}
        stage = AnalysisStage.of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection


def test_a_status_read_from_a_file_as_text_is_read_as_its_status() -> None:
    assert AnalysisStage.of("analyzing", []) is AnalysisStage.running


class TestTheBuildersMakeWhatTheReadersRead:
    def test_a_built_confirmation_is_a_confirmation(self) -> None:
        assert asks_analyst(confirmation("分母を変えないと進めない"))

    def test_a_built_answer_names_its_confirmation(self) -> None:
        assert answers_of(answer("FP-H01-E01", "そのまま")) == "FP-H01-E01"

    def test_a_built_stop_stops(self) -> None:
        assert stops(stop("先に別の論点を見る"))
