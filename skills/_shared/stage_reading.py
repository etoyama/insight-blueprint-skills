"""The reading of one analysis: its stage and what a reader shows beside it.

``AnalysisStage.of`` decides the stage (ADR-0061 6). This value adds, from the
same design and journal, whether a result is on record, what is asked and why
the analysis was stopped, so that ``design_io stage``, the design note and the
skills read these in one place instead of working them out again.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from insight_blueprint.models.analysis_stage import (
    RECORDS_FROM,
    AnalysisStage,
    open_confirmations,
    result_on_record,
    stops,
)
from insight_blueprint.models.design import DesignStatus


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
