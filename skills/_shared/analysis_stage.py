"""The analysis stage of a design: derived from its status and journal, never stored.

ADR-0061 6 fixes the order of the rule, and this module is the one place that
applies it. A reader that shows how far an analysis went calls
``AnalysisStage.of`` instead of reading statuses and events itself.

The marks of a confirmation, of its answer and of a stop are written only by
the commands of ``design_io`` (``ask-analyst``, ``answer-analyst``, ``stop``;
ADR-0064 8), from the events built here. A mark counts only on the kind of
event its builder makes, so reading and writing a mark sit side by side.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus

# The metadata keys of the marks (ADR-0064 8).
MARKS = ("asks_analyst", "answers", "stopped")
_ASKS_ANALYST, _ANSWERS, _STOPPED = MARKS

_QUESTION = "question"
_DECIDE = "decide"
# What /analysis-design copies in before premortem: it does not mean the
# analysis ran (analysis-auto, Step 1).
_HEARING = "hearing"


def confirmation(content: str) -> dict:
    """The fields of a confirmation the analysis asks of the analyst."""
    return {"type": _QUESTION, "content": content, "metadata": {_ASKS_ANALYST: True}}


def answer(question_id: str, content: str) -> dict:
    """The fields of the analyst's answer to the confirmation *question_id*."""
    return {"type": _DECIDE, "content": content, "metadata": {_ANSWERS: question_id}}


def stop(reason: str) -> dict:
    """The fields of the reason the analysis was stopped."""
    return {"type": _DECIDE, "content": reason, "metadata": {_STOPPED: True}}


def _metadata(event: dict) -> dict:
    metadata = event.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def asks_analyst(event: dict) -> bool:
    """Whether *event* is a confirmation the analysis asks of the analyst."""
    return (
        event.get("type") == _QUESTION and _metadata(event).get(_ASKS_ANALYST) is True
    )


def answers_of(event: dict) -> str | None:
    """The id of the confirmation *event* answers, or None if it answers none."""
    if event.get("type") != _DECIDE:
        return None
    answered = _metadata(event).get(_ANSWERS)
    return answered if isinstance(answered, str) else None


def stops(event: dict) -> bool:
    """Whether *event* is the reason the analysis was stopped."""
    return event.get("type") == _DECIDE and _metadata(event).get(_STOPPED) is True


def open_confirmations(events: Iterable[dict]) -> list[dict]:
    """The confirmations among *events* that no answer names yet, in order."""
    events = list(events)
    answered = {answers_of(e) for e in events} - {None}
    return [e for e in events if asks_analyst(e) and e.get("id") not in answered]


def _records_a_result(event: dict) -> bool:
    return not (
        event.get("type") == _HEARING or asks_analyst(event) or answers_of(event)
    )


class AnalysisStage(StrEnum):
    """Where one analysis stands (ADR-0061 6). Never stored."""

    before_run = "before_run"
    running = "running"
    awaiting_confirmation = "awaiting_confirmation"
    stopped = "stopped"
    awaiting_reflection = "awaiting_reflection"
    finished = "finished"

    @classmethod
    def of(cls, status: DesignStatus | str, events: Iterable[dict]) -> AnalysisStage:
        """The stage of a design in *status* whose journal holds *events*.

        The first line that holds decides, in the order of ADR-0061 6. A status
        read from a file as text is read as its ``DesignStatus``.
        """
        status = DesignStatus(status)
        events = list(events)
        if status in TERMINAL_STATUSES:
            return cls.finished
        if any(stops(e) for e in events):
            return cls.stopped
        if open_confirmations(events):
            return cls.awaiting_confirmation
        if status is not DesignStatus.analyzing:
            return cls.before_run
        if any(_records_a_result(e) for e in events):
            return cls.awaiting_reflection
        return cls.running


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
