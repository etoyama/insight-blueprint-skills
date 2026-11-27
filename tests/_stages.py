"""Stages and journal events built by hand, for tests of the analysis stage."""

from __future__ import annotations

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.journal import JOURNAL_MARKS

ASKS_ANALYST, ANSWERS, STOPPED = JOURNAL_MARKS
ANALYZING = DesignStatus.analyzing


def stage_of_status(status: DesignStatus | str) -> AnalysisStage:
    """The stage of a design in *status* with an empty journal and no analysis mark."""
    return AnalysisStage.of(status, (), None)


def ask_event(event_id: str = "FP-H01-E01") -> dict:
    return {
        "id": event_id,
        "type": "question",
        "content": "分母を変えないと進めない",
        "metadata": {ASKS_ANALYST: True},
    }


def answer_event(question_id: str = "FP-H01-E01", event_id: str = "FP-H01-E02") -> dict:
    return {
        "id": event_id,
        "type": "decide",
        "content": "分母は貸出の数のまま",
        "metadata": {ANSWERS: question_id},
    }


def stop_event(event_id: str = "FP-H01-E09") -> dict:
    return {
        "id": event_id,
        "type": "decide",
        "content": "別の論点を先に見る",
        "metadata": {STOPPED: True},
    }


def journal_event(kind: str, event_id: str = "FP-H01-E05") -> dict:
    return {"id": event_id, "type": kind, "content": "x", "metadata": {}}


MARK = "2026-11-27T10:00:00+09:00"


def event_at(kind: str, created_at: object, event_id: str = "FP-H01-E05") -> dict:
    return {**journal_event(kind, event_id), "created_at": created_at}
