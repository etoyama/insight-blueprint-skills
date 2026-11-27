"""The analysis stage of a design: derived from its status and journal, never stored.

ADR-0061 6 fixes the order of the rule, and this module is the one place that
applies it. A reader that shows how far an analysis went calls
``AnalysisStage.of`` instead of reading statuses and events itself.

The marks of a confirmation, of its answer and of a stop are written only by
the commands of ``design_io`` (``ask-analyst``, ``answer-analyst``, ``stop``;
ADR-0064 8). A mark counts only on the kind of event its command writes.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus

# The metadata keys the commands of design_io write (ADR-0064 8).
ASKS_ANALYST = "asks_analyst"
ANSWERS = "answers"
STOPPED = "stopped"
MARKS = (ASKS_ANALYST, ANSWERS, STOPPED)

QUESTION = "question"
DECIDE = "decide"
# What /analysis-design copies in before premortem: it does not mean the
# analysis ran (analysis-auto, Step 1).
HEARING = "hearing"


def _metadata(event: dict) -> dict:
    metadata = event.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def asks_analyst(event: dict) -> bool:
    """Whether *event* is a confirmation the analysis asks of the analyst."""
    return event.get("type") == QUESTION and _metadata(event).get(ASKS_ANALYST) is True


def answered_id(event: dict) -> str | None:
    """The id of the confirmation *event* answers, or None if it answers none."""
    if event.get("type") != DECIDE:
        return None
    answered = _metadata(event).get(ANSWERS)
    return answered if isinstance(answered, str) else None


def stops(event: dict) -> bool:
    """Whether *event* is the reason the analysis was stopped."""
    return event.get("type") == DECIDE and _metadata(event).get(STOPPED) is True


def open_confirmations(events: Iterable[dict]) -> list[dict]:
    """The confirmations among *events* that no answer names yet, in order."""
    events = list(events)
    answered = {answered_id(e) for e in events} - {None}
    return [e for e in events if asks_analyst(e) and e.get("id") not in answered]


def _records_a_result(event: dict) -> bool:
    return not (
        event.get("type") == HEARING or asks_analyst(event) or answered_id(event)
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
    def of(cls, status: DesignStatus, events: Iterable[dict]) -> AnalysisStage:
        """The stage of a design in *status* whose journal holds *events*.

        The first line that holds decides, in the order of ADR-0061 6.
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
