"""The analysis stage a status gives on its own, for tests that build notes by hand."""

from __future__ import annotations

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import DesignStatus


def stage_of_status(status: DesignStatus | str) -> AnalysisStage:
    """The stage of a design in *status* with an empty journal and no analysis mark."""
    return AnalysisStage.of(status, (), None)
