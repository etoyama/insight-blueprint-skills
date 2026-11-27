"""Which marks an event holds: one reading for the commands and the hook (ADR-0064 8, ADR-0067)."""

from __future__ import annotations

import pytest

from insight_blueprint.models.journal import JOURNAL_MARKS, marks_held

ASKS_ANALYST, ANSWERS, STOPPED = JOURNAL_MARKS


class TestMarksHeld:
    @pytest.mark.parametrize("mark", JOURNAL_MARKS)
    def test_a_mark_counts_on_any_type_of_event(self, mark: str) -> None:
        assert marks_held({"type": "observe", "metadata": {mark: False}}) == [mark]

    def test_the_marks_come_in_the_order_of_the_list(self) -> None:
        event = {"metadata": {STOPPED: True, ASKS_ANALYST: True}}
        assert marks_held(event) == [ASKS_ANALYST, STOPPED]

    def test_other_metadata_is_no_mark(self) -> None:
        assert marks_held({"metadata": {"direction": "supports"}}) == []

    @pytest.mark.parametrize(
        "event", [{}, {"metadata": None}, {"metadata": "stopped"}, "stopped", None]
    )
    def test_an_event_without_a_mapping_of_metadata_holds_none(
        self, event: object
    ) -> None:
        assert marks_held(event) == []
