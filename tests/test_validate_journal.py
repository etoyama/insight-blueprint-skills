"""The marks of a journal are written only by design_io (ADR-0067, Story 35.2, US-4 AC 5).

A journal has no schema: skills write its events by hand. The pre-write hook
checks one thing of it, that a write by the Write or Edit tool leaves the
events with a mark exactly as they were. design_io writes the marks from
Python, which the hook never sees.
"""

from __future__ import annotations

import pytest

from insight_blueprint.models.journal import JOURNAL_MARKS
from insight_blueprint.validate import validate_journal_change

ASKS_ANALYST, ANSWERS, STOPPED = JOURNAL_MARKS


def _event(event_id: str, kind: str = "observe", **metadata: object) -> dict:
    return {
        "id": event_id,
        "type": kind,
        "content": "x",
        "metadata": metadata,
        "created_at": "2026-11-27T11:00:00+09:00",
    }


def _journal(*events: dict) -> dict:
    return {"metadata": {"design_id": "FP-H01"}, "events": list(events)}


ASKED = _event("FP-H01-E01", "question", **{ASKS_ANALYST: True})
STOP = _event("FP-H01-E02", "decide", **{STOPPED: True})


class TestEventsWithoutMarksAreFree:
    def test_a_new_journal_without_marks_is_allowed(self) -> None:
        assert validate_journal_change(_journal(_event("FP-H01-E01")), None) == []

    def test_appending_an_event_without_a_mark_is_allowed(self) -> None:
        before = _journal(_event("FP-H01-E01"))
        after = _journal(_event("FP-H01-E01"), _event("FP-H01-E02", "evidence"))
        assert validate_journal_change(after, before) == []

    def test_appending_after_the_marks_of_the_commands_is_allowed(self) -> None:
        before = _journal(ASKED, STOP)
        after = _journal(ASKED, STOP, _event("FP-H01-E03"))
        assert validate_journal_change(after, before) == []

    def test_editing_an_event_without_a_mark_is_allowed(self) -> None:
        before = _journal(ASKED, _event("FP-H01-E02"))
        after = _journal(ASKED, {**_event("FP-H01-E02"), "content": "直した"})
        assert validate_journal_change(after, before) == []


class TestTheMarksStayAsTheCommandsWroteThem:
    @pytest.mark.parametrize("mark", JOURNAL_MARKS)
    def test_adding_an_event_with_a_mark_is_refused(self, mark: str) -> None:
        before = _journal(_event("FP-H01-E01"))
        after = _journal(_event("FP-H01-E01"), _event("FP-H01-E02", **{mark: True}))
        (error,) = validate_journal_change(after, before)
        assert "design_io" in error

    def test_a_new_journal_with_a_mark_is_refused(self) -> None:
        assert validate_journal_change(_journal(ASKED), None)

    def test_removing_a_stop_is_refused(self) -> None:
        assert validate_journal_change(_journal(ASKED), _journal(ASKED, STOP))

    def test_rewriting_a_confirmation_is_refused(self) -> None:
        after = _journal({**ASKED, "content": "別の文"}, STOP)
        assert validate_journal_change(after, _journal(ASKED, STOP))

    def test_giving_a_mark_to_an_event_that_had_none_is_refused(self) -> None:
        before = _journal(_event("FP-H01-E01", "decide"))
        after = _journal(_event("FP-H01-E01", "decide", **{STOPPED: True}))
        assert validate_journal_change(after, before)

    def test_reordering_the_keys_of_a_marked_event_is_allowed(self) -> None:
        reordered = dict(reversed(list(ASKED.items())))
        assert validate_journal_change(_journal(reordered), _journal(ASKED)) == []


class TestAJournalThatIsNotAJournal:
    def test_events_that_are_not_a_list_are_refused(self) -> None:
        assert validate_journal_change({"events": {"a": 1}}, None)

    def test_an_unreadable_journal_on_disk_is_read_as_holding_no_marks(self) -> None:
        assert validate_journal_change(_journal(_event("FP-H01-E01")), None) == []
