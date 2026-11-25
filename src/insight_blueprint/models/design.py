"""Pydantic data models for analysis designs."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from insight_blueprint.models.common import now_jst


class DesignStatus(StrEnum):
    """Status of an analysis design."""

    in_review = "in_review"
    revision_requested = "revision_requested"
    analyzing = "analyzing"
    explored = "explored"
    supported = "supported"
    rejected = "rejected"
    inconclusive = "inconclusive"


# The statuses VALID_TRANSITIONS (validate.py) lets nothing follow. The one
# canonical set: premortem, the progress of a node and the walk all read it.
TERMINAL_STATUSES = frozenset(
    {
        DesignStatus.explored,
        DesignStatus.supported,
        DesignStatus.rejected,
        DesignStatus.inconclusive,
    }
)


class AnalysisIntent(StrEnum):
    """Intent of an analysis design.

    ``mixed`` is kept only so saved designs still read; it is read as a
    confirmation and cannot be chosen for a new design (ADR-0048).
    """

    exploratory = "exploratory"
    confirmatory = "confirmatory"
    mixed = "mixed"


class DesignForm(StrEnum):
    """The shape of a design, derived from its intent and fields. Never stored.

    A legacy exploration is an exploratory design that holds a hypothesis, as
    designs did before Epic 32; it is checked and moved like a confirmation
    (ADR-0049).
    """

    exploration = "exploration"
    confirmation = "confirmation"
    legacy_exploration = "legacy_exploration"

    @property
    def judges(self) -> bool:
        """Whether the form holds a hypothesis that a verdict answers.

        An exploration measures and answers its question; a legacy exploration
        holds a hypothesis like a confirmation (ADR-0048, ADR-0049).
        """
        return self is not DesignForm.exploration

    def allows(self, status: DesignStatus) -> bool:
        """Whether a design of this form may take *status*: every status before
        the end, and of the terminal ones only the conclusions of the form."""
        return status not in TERMINAL_STATUSES or status in CONCLUSIONS_OF[self]


_VERDICTS = TERMINAL_STATUSES - {DesignStatus.explored}

CONCLUSIONS_OF: dict[DesignForm, frozenset[DesignStatus]] = {
    form: _VERDICTS if form.judges else frozenset({DesignStatus.explored})
    for form in DesignForm
}


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
    # An exploration holds its question, a confirmation its hypothesis; a field
    # the form does not hold stays None and is not written (ADR-0048).
    exploration_question: str | None = None
    exploration_background: str | None = None
    hypothesis_statement: str | None = None
    hypothesis_background: str | None = None
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

    @model_validator(mode="after")
    def _holds_the_fields_of_its_form(self) -> Self:
        """The fields tell the form, and the form decides what else is held.

        This is the check of reading: it lets a legacy exploration and a mixed
        design through. Refusing them for a new design is validate.py's
        ``validate_creation`` (ADR-0049).
        """
        asks = self.exploration_question is not None
        claims = self.hypothesis_statement is not None
        if asks == claims:
            held = "both" if asks else "neither"
            raise ValueError(
                "a design holds either exploration_question (an exploration) or "
                f"hypothesis_statement (a confirmation), not {held}"
            )
        if not asks:
            self._holds_a_hypothesis()
        elif self.analysis_intent is not AnalysisIntent.exploratory:
            raise ValueError(
                f"exploration_question belongs to an exploratory design, "
                f"not a {self.analysis_intent.value} one"
            )
        else:
            self._holds_a_question()
        return self._ends_as_its_form_does()

    def _ends_as_its_form_does(self) -> Self:
        if not self.form().allows(self.status):
            ends = ", ".join(sorted(s.value for s in CONCLUSIONS_OF[self.form()]))
            raise ValueError(
                f"status: a design of the {self.form().value} form ends as "
                f"{ends}, not {self.status.value}"
            )
        return self

    def _holds_a_question(self) -> None:
        for name in ("exploration_question", "exploration_background"):
            if not (getattr(self, name) or "").strip():
                raise ValueError(f"{name}: an exploration needs it written")
        for name in ("hypothesis_background", "next_action"):
            if getattr(self, name) is not None:
                raise ValueError(
                    f"{name}: an exploration measures and answers its question, "
                    "so it holds no hypothesis and nothing that waits on a verdict"
                )

    def _holds_a_hypothesis(self) -> None:
        if self.hypothesis_background is None:
            raise ValueError("hypothesis_background: a hypothesis needs its background")
        if self.exploration_background is not None:
            raise ValueError(
                "exploration_background: a design with a hypothesis holds no "
                "exploration fields"
            )

    @model_serializer(mode="wrap")
    def _leave_out_the_fields_of_the_other_form(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        data = handler(self)
        for name in _FORM_FIELDS:
            if data.get(name, "") is None:
                del data[name]
        return data

    def form(self) -> DesignForm:
        """The form this design takes (ADR-0048, ADR-0049)."""
        if self.analysis_intent is not AnalysisIntent.exploratory:
            return DesignForm.confirmation
        if self.exploration_question is not None:
            return DesignForm.exploration
        return DesignForm.legacy_exploration


_FORM_FIELDS = (
    "exploration_question",
    "exploration_background",
    "hypothesis_statement",
    "hypothesis_background",
)
