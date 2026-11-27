"""The analysis stage is derived, never stored (ADR-0061 6, Story 35.2, US-3 AC 1).

One rule, in the order of ADR-0061: the first line that holds decides.
"""

from __future__ import annotations

import pytest

from insight_blueprint.models.analysis_stage import (
    MARKS,
    AnalysisStage,
    answer,
    answers_of,
    asks_analyst,
    confirmation,
    stop,
    stops,
)
from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus

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


def _of(status, events, started_at=None) -> AnalysisStage:
    """The stage of a record without the analysis mark, unless one is given."""
    return AnalysisStage.of(status, events, started_at)


class TestOrderOfTheRule:
    @pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
    def test_a_terminal_status_is_finished_even_with_a_stop_mark(
        self, status: DesignStatus
    ) -> None:
        assert _of(status, [_stop()]) is AnalysisStage.finished

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested, ANALYZING]
    )
    def test_a_stop_mark_is_stopped_before_the_end(self, status: DesignStatus) -> None:
        assert _of(status, [_stop()]) is AnalysisStage.stopped

    def test_a_stop_mark_wins_over_an_open_confirmation(self) -> None:
        stage = _of(ANALYZING, [_ask(), _stop()])
        assert stage is AnalysisStage.stopped

    def test_a_confirmation_without_an_answer_waits_for_the_analyst(self) -> None:
        stage = _of(ANALYZING, [_ask()])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_an_open_confirmation_wins_over_recorded_results(self) -> None:
        stage = _of(ANALYZING, [_event("observe"), _ask("FP-H01-E06")])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_an_answered_confirmation_runs_again(self) -> None:
        stage = _of(ANALYZING, [_ask(), _answer()])
        assert stage is AnalysisStage.running

    def test_one_open_confirmation_among_answered_ones_still_waits(self) -> None:
        events = [_ask(), _answer(), _ask("FP-H01-E03")]
        assert _of(ANALYZING, events) is AnalysisStage.awaiting_confirmation

    @pytest.mark.parametrize(
        "kind", ["observe", "evidence", "question", "decide", "conclude", "reflect"]
    )
    def test_an_analyzing_design_with_a_result_waits_for_its_reflection(
        self, kind: str
    ) -> None:
        stage = _of(ANALYZING, [_event(kind)])
        assert stage is AnalysisStage.awaiting_reflection

    def test_an_analyzing_design_with_only_a_hearing_is_running(self) -> None:
        stage = _of(ANALYZING, [_event("hearing")])
        assert stage is AnalysisStage.running

    def test_an_analyzing_design_without_events_is_running(self) -> None:
        assert _of(ANALYZING, []) is AnalysisStage.running

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested]
    )
    def test_a_design_before_analysis_is_before_run(self, status: DesignStatus) -> None:
        stage = _of(status, [_event("observe")])
        assert stage is AnalysisStage.before_run


class TestMarksCountOnlyOnTheirEvents:
    """A mark counts on the event its command writes, nowhere else (ADR-0064 8)."""

    def test_a_decide_event_that_asks_is_not_a_confirmation(self) -> None:
        event = {**_answer(), "metadata": {ASKS_ANALYST: True}}
        stage = _of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection

    def test_a_question_event_with_a_stop_mark_does_not_stop(self) -> None:
        event = {**_event("question"), "metadata": {STOPPED: True}}
        stage = _of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection

    def test_an_answer_naming_another_event_leaves_the_confirmation_open(
        self,
    ) -> None:
        stage = _of(ANALYZING, [_ask(), _answer("FP-H01-E07")])
        assert stage is AnalysisStage.awaiting_confirmation

    def test_a_hand_edited_metadata_that_is_not_a_mapping_is_no_mark(self) -> None:
        event = {**_event("decide"), "metadata": "stopped"}
        stage = _of(ANALYZING, [event])
        assert stage is AnalysisStage.awaiting_reflection


def test_a_status_read_from_a_file_as_text_is_read_as_its_status() -> None:
    assert _of("analyzing", []) is AnalysisStage.running


class TestTheBuildersMakeWhatTheReadersRead:
    def test_a_built_confirmation_is_a_confirmation(self) -> None:
        assert asks_analyst(confirmation("分母を変えないと進めない"))

    def test_a_built_answer_names_its_confirmation(self) -> None:
        assert answers_of(answer("FP-H01-E01", "そのまま")) == "FP-H01-E01"

    def test_a_built_stop_stops(self) -> None:
        assert stops(stop("先に別の論点を見る"))


MARK = "2026-11-27T10:00:00+09:00"


def _at(kind: str, created_at: object, event_id: str = "FP-H01-E05") -> dict:
    return {**_event(kind, event_id), "created_at": created_at}


class TestOnlyEventsAfterTheMarkAreResults:
    """ADR-0061 6.4 as amended: a journal written before the run is not a result."""

    def test_reasoning_written_before_the_run_leaves_the_analysis_running(
        self,
    ) -> None:
        events = [_at("hypothesize", "2026-11-27T09:00:00+09:00")]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.running

    def test_an_observation_written_by_hand_before_the_run_is_not_a_result(
        self,
    ) -> None:
        events = [_at("observe", "2026-11-27T09:30:00+09:00")]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.running

    @pytest.mark.parametrize("kind", ["observe", "evidence", "question"])
    def test_an_event_written_after_the_mark_is_a_result(self, kind: str) -> None:
        events = [_at(kind, "2026-11-27T11:00:00+09:00")]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.awaiting_reflection

    def test_an_event_at_the_moment_of_the_mark_is_a_result(self) -> None:
        events = [_at("observe", MARK)]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.awaiting_reflection

    @pytest.mark.parametrize(
        "created_at", [None, "yesterday", "2026-11-27T11:00:00"], ids=str
    )
    def test_an_event_whose_time_cannot_be_compared_is_a_result(
        self, created_at: object
    ) -> None:
        events = [_at("hypothesize", created_at)]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.awaiting_reflection

    def test_the_mark_may_be_a_datetime(self) -> None:
        from datetime import datetime

        events = [_at("hypothesize", "2026-11-27T09:00:00+09:00")]
        started = datetime.fromisoformat(MARK)
        assert _of(ANALYZING, events, started) is AnalysisStage.running

    def test_a_record_without_the_mark_reads_every_event(self) -> None:
        events = [_at("hypothesize", "2026-11-27T09:00:00+09:00")]
        assert _of(ANALYZING, events, None) is AnalysisStage.awaiting_reflection

    def test_a_confirmation_before_the_mark_still_waits(self) -> None:
        events = [{**_ask(), "created_at": "2026-11-27T09:00:00+09:00"}]
        assert _of(ANALYZING, events, MARK) is AnalysisStage.awaiting_confirmation

    def test_a_mark_that_cannot_be_read_reads_every_event(self) -> None:
        events = [_at("hypothesize", "2026-11-27T09:00:00+09:00")]
        assert _of(ANALYZING, events, "soon") is AnalysisStage.awaiting_reflection
