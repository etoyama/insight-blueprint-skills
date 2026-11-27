"""The reading of one analysis: its stage and what goes with it, read once (Epic 35)."""

from __future__ import annotations

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import DesignStatus
from skills._shared.stage_reading import Ask, StageReading
from tests._stages import (
    ANALYZING,
    MARK,
    answer_event,
    ask_event,
    event_at,
    journal_event,
    stop_event,
)


class TestStageReading:
    """One value holds the stage and what goes with it, so no reader works these out again."""

    def test_it_holds_the_stage_of_the_rule(self) -> None:
        reading = StageReading.of(ANALYZING, [ask_event()], None)
        assert reading.stage is AnalysisStage.awaiting_confirmation

    def test_an_analysis_waiting_for_the_analyst_holds_what_it_asks(self) -> None:
        reading = StageReading.of(
            ANALYZING, [ask_event(), ask_event("FP-H01-E03")], None
        )
        assert reading.asks == (
            Ask("FP-H01-E01", "分母を変えないと進めない"),
            Ask("FP-H01-E03", "分母を変えないと進めない"),
        )

    def test_an_answered_confirmation_is_not_asked(self) -> None:
        reading = StageReading.of(ANALYZING, [ask_event(), answer_event()], None)
        assert reading.asks == ()

    def test_a_stopped_analysis_holds_the_reason_and_asks_nothing(self) -> None:
        reading = StageReading.of(ANALYZING, [ask_event(), stop_event()], None)
        assert reading.stop_reason == "別の論点を先に見る"
        assert reading.asks == ()

    def test_a_finished_analysis_that_once_stopped_has_no_reason(self) -> None:
        reading = StageReading.of(DesignStatus.explored, [stop_event()], None)
        assert reading.stop_reason is None

    def test_a_reason_written_as_a_number_is_read_as_text(self) -> None:
        reading = StageReading.of(ANALYZING, [{**stop_event(), "content": 34.6}], None)
        assert reading.stop_reason == "34.6"

    def test_a_result_is_on_record_whatever_the_stage(self) -> None:
        events = [event_at("observe", "2026-11-27T11:00:00+09:00"), stop_event()]
        reading = StageReading.of(ANALYZING, events, MARK)
        assert reading.stage is AnalysisStage.stopped
        assert reading.result_on_record is True

    def test_reasoning_on_a_design_never_run_is_no_result(self) -> None:
        reading = StageReading.of(
            DesignStatus.in_review, [journal_event("hypothesize")], None
        )
        assert reading.result_on_record is False

    def test_a_design_stopped_before_its_run_has_no_result(self) -> None:
        events = [journal_event("hypothesize"), stop_event()]
        reading = StageReading.of(DesignStatus.in_review, events, None)
        assert reading.result_on_record is False

    @pytest.mark.parametrize(
        ("status", "events", "takes"),
        [
            (ANALYZING, [], True),
            (ANALYZING, [journal_event("observe")], True),
            (ANALYZING, [ask_event()], False),
            (ANALYZING, [stop_event()], False),
            (
                DesignStatus.in_review,
                [event_at("observe", "2026-11-27T11:00:00+09:00")],
                False,
            ),
            (DesignStatus.in_review, [], False),
            (DesignStatus.explored, [journal_event("observe")], False),
        ],
        ids=[
            "running",
            "awaiting_reflection",
            "asking",
            "stopped",
            "under_review",
            "before_run",
            "finished",
        ],
    )
    def test_only_an_analysis_under_way_takes_a_result(
        self, status: DesignStatus, events: list[dict], takes: bool
    ) -> None:
        assert StageReading.of(status, events, MARK).takes_a_result is takes
