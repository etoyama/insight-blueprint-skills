"""Pydantic data models for analysis designs."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from insight_blueprint.models.common import now_jst


class DesignStatus(StrEnum):
    """Status of an analysis design."""

    in_review = "in_review"
    revision_requested = "revision_requested"
    analyzing = "analyzing"
    supported = "supported"
    rejected = "rejected"
    inconclusive = "inconclusive"


class AnalysisIntent(StrEnum):
    """Intent of an analysis design: exploratory, confirmatory, or mixed."""

    exploratory = "exploratory"
    confirmatory = "confirmatory"
    mixed = "mixed"


class VariableRole(StrEnum):
    """Causal role of an explanatory variable."""

    treatment = "treatment"
    confounder = "confounder"
    covariate = "covariate"
    instrumental = "instrumental"
    mediator = "mediator"


class MetricTier(StrEnum):
    """Priority tier of a verification metric."""

    primary = "primary"
    secondary = "secondary"
    guardrail = "guardrail"


class ChartIntent(StrEnum):
    """Analysis intent of a chart specification."""

    distribution = "distribution"
    correlation = "correlation"
    trend = "trend"
    comparison = "comparison"


class ExplanatoryVariable(BaseModel):
    """Schema for an explanatory variable with causal role."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    role: VariableRole = VariableRole.covariate
    data_source: str = ""
    time_points: str = ""


class Metric(BaseModel):
    """Schema for a verification metric with priority tier."""

    model_config = ConfigDict(extra="allow")

    target: str
    tier: MetricTier = MetricTier.primary
    data_source: dict = Field(default_factory=dict)
    grouping: list = Field(default_factory=list)
    filter: str = ""
    aggregation: str = ""
    comparison: str = ""


class ChartSpec(BaseModel):
    """Schema for a chart specification with analysis intent."""

    model_config = ConfigDict(extra="allow")

    intent: ChartIntent
    type: str = ""
    description: str = ""
    x: str = ""
    y: str = ""

    @model_validator(mode="before")
    @classmethod
    def _infer_intent_from_type(cls, data: Any) -> Any:
        """Backward compat: infer intent from type when intent is missing."""
        if isinstance(data, dict) and "intent" not in data:
            chart_type = data.get("type", "")
            type_to_intent = {
                "scatter": "correlation",
                "heatmap": "correlation",
                "bar": "comparison",
                "table": "comparison",
                "histogram": "distribution",
                "box": "distribution",
                "line": "trend",
                "area": "trend",
            }
            data["intent"] = type_to_intent.get(chart_type, "distribution")
        return data


class Methodology(BaseModel):
    """Schema for analysis methodology and package."""

    model_config = ConfigDict(extra="allow")

    method: str = Field(min_length=1)
    package: str = ""
    reason: str = ""


class DecisionContext(BaseModel):
    """Who decides what on the strength of this analysis (ADR-0014).

    Both sides are required so a design never carries a decision without its
    decision maker, or the other way round.
    """

    model_config = ConfigDict(extra="allow")

    decision_maker: str = Field(min_length=1)
    decision: str = Field(min_length=1)


class AnalysisDesign(BaseModel):
    """Analysis design document for hypothesis-driven EDA."""

    model_config = ConfigDict(extra="allow")

    id: str
    theme_id: str = "DEFAULT"
    title: str
    hypothesis_statement: str
    hypothesis_background: str
    status: DesignStatus = DesignStatus.in_review
    analysis_intent: AnalysisIntent = AnalysisIntent.confirmatory
    parent_id: str | None = None
    metrics: list[Metric] = Field(default_factory=list)
    explanatory: list[ExplanatoryVariable] = Field(default_factory=list)
    chart: list[ChartSpec] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    next_action: dict | None = None
    referenced_knowledge: dict[str, list[str]] = Field(default_factory=dict)
    methodology: Methodology | None = None
    decision_context: DecisionContext | None = None
    created_at: datetime = Field(default_factory=now_jst)
    updated_at: datetime = Field(default_factory=now_jst)

    @model_validator(mode="before")
    @classmethod
    def _migrate_metrics(cls, data: Any) -> Any:
        """Convert legacy metrics formats to list[Metric]."""
        if isinstance(data, dict) and "metrics" in data:
            m = data["metrics"]
            if m is None:
                data["metrics"] = []
            elif isinstance(m, dict):
                if not m:  # empty dict {}
                    data["metrics"] = []
                elif "target" in m:  # single metric dict
                    data["metrics"] = [m]
                # else: unexpected dict structure -> let Pydantic validate
        return data
