"""The analysis stage of a design: derived from its status and journal, never stored.

ADR-0061 6 fixes the order of the rule, and this module is the one place that
applies it. A reader that shows how far an analysis went calls
``AnalysisStage.of`` instead of reading statuses and events itself.

The marks of a confirmation, of its answer and of a stop are written only by
the commands ADR-0064 8 names, from the events built here. A mark counts only on the kind of
event its builder makes, so reading and writing a mark sit side by side.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NamedTuple

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus
from insight_blueprint.models.journal import DECIDE, HEARING, JOURNAL_MARKS, QUESTION

_ASKS_ANALYST, _ANSWERS, _STOPPED = JOURNAL_MARKS


def confirmation(content: str) -> dict:
    """The fields of a confirmation the analysis asks of the analyst."""
    return {"type": QUESTION, "content": content, "metadata": {_ASKS_ANALYST: True}}


def answer(question_id: str, content: str) -> dict:
    """The fields of the analyst's answer to the confirmation *question_id*."""
    return {"type": DECIDE, "content": content, "metadata": {_ANSWERS: question_id}}


def stop(reason: str) -> dict:
    """The fields of the reason the analysis was stopped."""
    return {"type": DECIDE, "content": reason, "metadata": {_STOPPED: True}}


def _metadata(event: dict) -> dict:
    metadata = event.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def asks_analyst(event: dict) -> bool:
    """Whether *event* is a confirmation the analysis asks of the analyst."""
    return event.get("type") == QUESTION and _metadata(event).get(_ASKS_ANALYST) is True


def answers_of(event: dict) -> str | None:
    """The id of the confirmation *event* answers, or None if it answers none."""
    if event.get("type") != DECIDE:
        return None
    answered = _metadata(event).get(_ANSWERS)
    return answered if isinstance(answered, str) else None


def stops(event: dict) -> bool:
    """Whether *event* is the reason the analysis was stopped."""
    return event.get("type") == DECIDE and _metadata(event).get(_STOPPED) is True


def answered_confirmation_ids(events: Iterable[dict]) -> set[str]:
    """The ids of the confirmations among *events* that an answer names.

    An answer that names an event which is not a confirmation settles nothing.
    """
    events = list(events)
    named = {answers_of(e) for e in events} - {None}
    return {str(e.get("id")) for e in events if asks_analyst(e)} & named


def open_confirmations(events: Iterable[dict]) -> list[dict]:
    """The confirmations among *events* that no answer names yet, in order."""
    events = list(events)
    answered = answered_confirmation_ids(events)
    return [e for e in events if asks_analyst(e) and e.get("id") not in answered]


def _records_a_result(event: dict, started_at: datetime | None) -> bool:
    """Whether *event* is a result of the run that began at *started_at*.

    A hearing, a confirmation, its answer and the reason of a stop are not
    results. Nor is an event written before the analysis mark: /analysis-journal may record reasoning
    before the run (ADR-0061 6.4 as amended). An event whose time cannot be
    compared with the mark counts, as every event did before the amendment.
    """
    if event.get("type") == HEARING:
        return False
    if asks_analyst(event) or answers_of(event) or stops(event):
        return False
    if started_at is None:
        return True
    try:
        return _moment(event.get("created_at")) >= started_at
    except (TypeError, ValueError):
        return True


def records_a_result(events: Iterable[dict], started_at: datetime | str | None) -> bool:
    """Whether *events* hold a result of the run that began at *started_at*.

    The status of the design is not read: a result stays on record while a
    review of it holds the design (ADR-0054).
    """
    start = _mark(started_at)
    return any(_records_a_result(e, start) for e in events)


def _moment(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"not a time: {value!r}")


def _mark(started_at: datetime | str | None) -> datetime | None:
    """The analysis mark as a time; None when there is none or it cannot be read."""
    try:
        return None if started_at is None else _moment(started_at)
    except (TypeError, ValueError):
        return None


class AnalysisStage(StrEnum):
    """Where one analysis stands (ADR-0061 6). Never stored."""

    before_run = "before_run"
    running = "running"
    awaiting_confirmation = "awaiting_confirmation"
    stopped = "stopped"
    awaiting_reflection = "awaiting_reflection"
    finished = "finished"

    @classmethod
    def of(
        cls,
        status: DesignStatus | str,
        events: Iterable[dict],
        started_at: datetime | str | None,
    ) -> AnalysisStage:
        """The stage of a design in *status* whose journal holds *events*.

        *started_at* is the design's analysis mark (``analysis_started_at``);
        None for a record saved without one, whose events are all read. The
        first line that holds decides, in the order of ADR-0061 6. A status or
        a mark read from a file as text is read as what it says.
        """
        status = DesignStatus(status)
        events = list(events)
        if status in TERMINAL_STATUSES:
            return cls.finished
        if any(stops(e) for e in events):
            return cls.stopped
        if open_confirmations(events):
            return cls.awaiting_confirmation
        # A review of the result takes the design back from analyzing, and the
        # result stays on record (ADR-0054); one taken back without a result is
        # read before its run, to be handed over again.
        if result_on_record(status, events, started_at):
            return cls.awaiting_reflection
        if status is DesignStatus.analyzing:
            return cls.running
        return cls.before_run


def result_on_record(
    status: DesignStatus, events: list[dict], started_at: datetime | str | None
) -> bool:
    """Whether a run of a design in *status* left a result among *events*.

    A design that never entered its analysis has none, whatever reasoning its
    journal holds. The stage is not read: a result stays on record while a
    review of it holds the design (ADR-0054), and a stopped analysis may have one.
    """
    entered = (
        status is DesignStatus.analyzing
        or status in TERMINAL_STATUSES
        or started_at is not None
    )
    return entered and records_a_result(events, started_at)


# The stages a confirmation and a stop may be written from (the State Diagram
# of docs/design/epic-35-hand-over-questions.md). Only a running analysis asks:
# one before its run is read before it is handed over, and one with results has
# touched the data already (ADR-0064 1). One with results waits for its
# reflection, which ends it instead of a stop.
ASKS_FROM = frozenset({AnalysisStage.running})
STOPS_FROM = frozenset(
    {
        AnalysisStage.before_run,
        AnalysisStage.running,
        AnalysisStage.awaiting_confirmation,
    }
)

# The stages a result is recorded from: a run writes its results while the
# analysis is under way, and a second run adds to those of the first. One that
# waits for the analyst asked before it touched the data, so it has none to
# record; a stopped or a finished one keeps the record it ended on. A design a
# review of its result holds is awaiting_reflection but not analyzing: its run
# is over, so a writer checks the status as well.
RECORDS_FROM = frozenset({AnalysisStage.running, AnalysisStage.awaiting_reflection})

# The stages that are over: a finished analysis has its end, and a stopped one is
# never resumed (ADR-0064). Neither holds the walk, and a node whose analyses are
# all over is analyzed unless every one of them was stopped (ADR-0061 7).
SETTLED = frozenset({AnalysisStage.finished, AnalysisStage.stopped})


class Ask(NamedTuple):
    """A confirmation no answer names yet: the id an answer names, and what it asks."""

    id: str
    content: str


def _text(value: object) -> str:
    # A hand-written "content: 34.6" loads as a float, not as text.
    return "" if value is None else str(value)


@dataclass(frozen=True)
class StageReading:
    """The stage of one analysis and what a reader shows beside it. Never stored.

    Read once from the design and its journal, so no reader works out again
    whether a result is on record, what is asked or why it was stopped.
    ``asks`` is empty unless the analysis waits for the analyst, and
    ``stop_reason`` is None unless it was stopped: a finished analysis that
    once asked or stopped carries neither.
    """

    stage: AnalysisStage
    status: DesignStatus
    result_on_record: bool  # analysis_stage.result_on_record
    asks: tuple[Ask, ...]
    stop_reason: str | None

    @classmethod
    def of(
        cls,
        status: DesignStatus | str,
        events: Iterable[dict],
        started_at: datetime | str | None,
    ) -> StageReading:
        """The reading of a design in *status*, as ``AnalysisStage.of`` takes it."""
        status = DesignStatus(status)
        events = list(events)
        stage = AnalysisStage.of(status, events, started_at)
        waits = stage is AnalysisStage.awaiting_confirmation
        stopped = stage is AnalysisStage.stopped
        return cls(
            stage=stage,
            status=status,
            result_on_record=result_on_record(status, events, started_at),
            asks=tuple(
                Ask(str(e.get("id")), _text(e.get("content")))
                for e in open_confirmations(events)
            )
            if waits
            else (),
            stop_reason=next(
                (_text(e.get("content")) for e in events if stops(e)), None
            )
            if stopped
            else None,
        )

    @property
    def takes_a_result(self) -> bool:
        """Whether a run may record a result now: only while it is under way."""
        return self.stage in RECORDS_FROM and self.status is DesignStatus.analyzing
