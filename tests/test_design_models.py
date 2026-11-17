"""Unit tests for verification-design model types and validators.

Tests follow TDD Red-Green-Refactor cycle. Tests marked with
'# Red: depends on task 1.4 validators' will fail until validators are added.
"""

import pytest
from pydantic import ValidationError

from insight_blueprint.models.design import (
    AnalysisDesign,
    ChartIntent,
    ChartSpec,
    DecisionContext,
    ExplanatoryVariable,
    Methodology,
    Metric,
    MetricTier,
    VariableRole,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _minimal_design_data(**overrides: object) -> dict:
    """Create minimal valid AnalysisDesign data dict."""
    base: dict = {
        "id": "TEST-H01",
        "title": "Test",
        "hypothesis_statement": "stmt",
        "hypothesis_background": "bg",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# StrEnum member verification
# ---------------------------------------------------------------------------


def test_variable_role_members() -> None:
    """Unit-E01: VariableRole has exactly 5 members."""
    members = set(VariableRole.__members__.keys())
    assert members == {
        "treatment",
        "confounder",
        "covariate",
        "instrumental",
        "mediator",
    }


def test_metric_tier_members() -> None:
    """Unit-E02: MetricTier has exactly 3 members."""
    members = set(MetricTier.__members__.keys())
    assert members == {"primary", "secondary", "guardrail"}


def test_chart_intent_members() -> None:
    """Unit-E03: ChartIntent has exactly 4 members."""
    members = set(ChartIntent.__members__.keys())
    assert members == {"distribution", "correlation", "trend", "comparison"}


# ---------------------------------------------------------------------------
# ExplanatoryVariable tests
# ---------------------------------------------------------------------------


def test_explanatory_variable_role_default_covariate() -> None:
    """Unit-01 (AC-1.1): role-less dict defaults to covariate."""
    data = {
        "name": "x1",
        "description": "desc",
        "data_source": "src",
        "time_points": "2020",
    }
    var = ExplanatoryVariable(**data)
    assert var.role == VariableRole.covariate


def test_explanatory_variable_invalid_role_raises() -> None:
    """Unit-02 (AC-1.2): Invalid role raises ValidationError."""
    with pytest.raises(ValidationError):
        ExplanatoryVariable(name="x1", role="invalid_role")


def test_explanatory_variable_dump_role_as_string() -> None:
    """Unit-03 (AC-1.3): model_dump outputs role as string."""
    var = ExplanatoryVariable(name="x1", role=VariableRole.treatment)
    dumped = var.model_dump(mode="json")
    assert dumped["role"] == "treatment"
    assert isinstance(dumped["role"], str)


@pytest.mark.parametrize("role", list(VariableRole))
def test_explanatory_variable_accepts_all_valid_roles(role: VariableRole) -> None:
    """Unit-E04: All valid VariableRole values are accepted."""
    var = ExplanatoryVariable(name="x1", role=role)
    assert var.role == role


# ---------------------------------------------------------------------------
# Metric tests
# ---------------------------------------------------------------------------


def test_migrate_metrics_single_dict_to_list() -> None:
    """Unit-04 (AC-2.1): Single dict metrics -> [Metric]."""
    # Red: depends on task 1.4 validators
    data = _minimal_design_data(metrics={"target": "crime_rate", "aggregation": "mean"})
    design = AnalysisDesign(**data)
    assert isinstance(design.metrics, list)
    assert len(design.metrics) == 1
    assert design.metrics[0].target == "crime_rate"


def test_migrate_metrics_list_preserved() -> None:
    """Unit-05 (AC-2.2): List metrics preserved as list."""
    metrics_list = [
        {"target": "primary_metric", "tier": "primary"},
        {"target": "guardrail_metric", "tier": "guardrail"},
    ]
    data = _minimal_design_data(metrics=metrics_list)
    design = AnalysisDesign(**data)
    assert len(design.metrics) == 2
    assert design.metrics[0].tier == MetricTier.primary
    assert design.metrics[1].tier == MetricTier.guardrail


def test_migrate_metrics_empty_dict_to_empty_list() -> None:
    """Unit-06 (AC-2.3): Empty dict {} -> empty list []."""
    # Red: depends on task 1.4 validators
    data = _minimal_design_data(metrics={})
    design = AnalysisDesign(**data)
    assert design.metrics == []


def test_metric_tier_default_primary() -> None:
    """Unit-07 (AC-2.4): Metric without tier defaults to primary."""
    metric = Metric(target="some_metric")
    assert metric.tier == MetricTier.primary


def test_migrate_metrics_none_to_empty_list() -> None:
    """Unit-E05: metrics=None -> empty list."""
    # Red: depends on task 1.4 validators
    data = _minimal_design_data(metrics=None)
    design = AnalysisDesign(**data)
    assert design.metrics == []


def test_metric_invalid_tier_raises() -> None:
    """Unit-E06: Invalid tier raises ValidationError."""
    with pytest.raises(ValidationError):
        Metric(target="m1", tier="invalid_tier")


def test_metric_without_target_raises() -> None:
    """Unit-E07: Metric without target raises ValidationError."""
    with pytest.raises(ValidationError):
        Metric(tier="primary")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ChartSpec tests
# ---------------------------------------------------------------------------


def test_chart_spec_infer_intent_scatter_to_correlation() -> None:
    """Unit-08 (AC-3.1): type=scatter -> intent=correlation."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{"type": "scatter", "description": "test"})
    assert spec.intent == ChartIntent.correlation


def test_chart_spec_infer_intent_table_to_comparison() -> None:
    """Unit-09 (AC-3.2): type=table -> intent=comparison."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{"type": "table"})
    assert spec.intent == ChartIntent.comparison


def test_chart_spec_infer_intent_unknown_type_to_distribution() -> None:
    """Unit-10 (AC-3.3): Unknown type -> intent=distribution."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{"type": "unknown_chart"})
    assert spec.intent == ChartIntent.distribution


def test_chart_spec_dump_intent_and_type() -> None:
    """Unit-11 (AC-3.4): model_dump includes both intent and type."""
    spec = ChartSpec(intent=ChartIntent.trend, type="line", description="trend")
    dumped = spec.model_dump(mode="json")
    assert dumped["intent"] == "trend"
    assert dumped["type"] == "line"


@pytest.mark.parametrize(
    "chart_type,expected_intent",
    [
        ("scatter", "correlation"),
        ("heatmap", "correlation"),
        ("bar", "comparison"),
        ("table", "comparison"),
        ("histogram", "distribution"),
        ("box", "distribution"),
        ("line", "trend"),
        ("area", "trend"),
    ],
)
def test_chart_spec_infer_intent_all_mappings(
    chart_type: str, expected_intent: str
) -> None:
    """Unit-E08: All 8 type->intent mappings."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{"type": chart_type})
    assert spec.intent == ChartIntent(expected_intent)


def test_chart_spec_explicit_intent_preserved() -> None:
    """Unit-E09: Explicit intent is not overridden by type inference."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{"intent": "trend", "type": "scatter"})
    assert spec.intent == ChartIntent.trend  # explicit intent wins


def test_chart_spec_no_intent_no_type_defaults_distribution() -> None:
    """Unit-E10: No intent + no type -> distribution."""
    # Red: depends on task 1.4 validators
    spec = ChartSpec(**{})
    assert spec.intent == ChartIntent.distribution


# ---------------------------------------------------------------------------
# Methodology tests
# ---------------------------------------------------------------------------


def test_analysis_design_methodology_default_none() -> None:
    """Unit-12 (AC-4.1): AnalysisDesign without methodology -> None."""
    data = _minimal_design_data()
    design = AnalysisDesign(**data)
    assert design.methodology is None


def test_methodology_from_dict() -> None:
    """Unit-13 (AC-4.2): dict -> Methodology auto-conversion."""
    data = _minimal_design_data(
        methodology={
            "method": "CausalImpact",
            "package": "tfcausalimpact",
            "reason": "causal",
        }
    )
    design = AnalysisDesign(**data)
    assert design.methodology is not None
    assert design.methodology.method == "CausalImpact"
    assert design.methodology.package == "tfcausalimpact"


def test_methodology_empty_method_raises() -> None:
    """Unit-14 (AC-4.3): Empty method raises ValidationError."""
    with pytest.raises(ValidationError):
        Methodology(method="", package="pkg")


def test_methodology_defaults() -> None:
    """Unit-E11: Methodology package and reason default to empty string."""
    m = Methodology(method="OLS")
    assert m.package == ""
    assert m.reason == ""


# ---------------------------------------------------------------------------
# DecisionContext tests (Epic 12 US-2, ADR-0014)
# ---------------------------------------------------------------------------


def test_analysis_design_decision_context_defaults_to_none() -> None:
    """US-2 AC 4: a design without a decision context is still valid."""
    design = AnalysisDesign(**_minimal_design_data())
    assert design.decision_context is None


def test_decision_context_is_built_from_a_dict() -> None:
    """US-2 AC 1: the design carries who decides and what they decide."""
    design = AnalysisDesign(
        **_minimal_design_data(
            decision_context={
                "decision_maker": "マーケティング部長",
                "decision": "来期のクーポン施策を続けるか",
            }
        )
    )
    assert design.decision_context == DecisionContext(
        decision_maker="マーケティング部長",
        decision="来期のクーポン施策を続けるか",
    )


@pytest.mark.parametrize(
    "half",
    [
        {"decision_maker": "マーケティング部長"},
        {"decision": "来期のクーポン施策を続けるか"},
        {"decision_maker": "", "decision": "来期のクーポン施策を続けるか"},
        {"decision_maker": "マーケティング部長", "decision": ""},
        {},
    ],
    ids=[
        "decision missing",
        "decision_maker missing",
        "decision_maker empty",
        "decision empty",
        "both missing",
    ],
)
def test_decision_context_with_only_one_side_is_rejected(half: dict) -> None:
    """US-2 AC 1: a decision context is either absent or has both sides filled."""
    with pytest.raises(ValidationError):
        AnalysisDesign(**_minimal_design_data(decision_context=half))


# ---------------------------------------------------------------------------
# Migration robustness tests
# ---------------------------------------------------------------------------


def test_migrate_metrics_idempotent() -> None:
    """Unit-M01: Metrics migration is idempotent (list -> dump -> re-parse)."""
    data = _minimal_design_data(metrics=[{"target": "y", "tier": "primary"}])
    design1 = AnalysisDesign(**data)
    dumped = design1.model_dump(mode="json")
    design2 = AnalysisDesign(**dumped)
    assert len(design2.metrics) == 1
    assert design2.metrics[0].target == "y"


def test_migrate_metrics_list_with_invalid_element_raises() -> None:
    """Unit-M02: List with invalid element (no target) raises ValidationError."""
    data = _minimal_design_data(metrics=[{"tier": "primary"}])  # no target
    with pytest.raises(ValidationError):
        AnalysisDesign(**data)


def test_analysis_design_update_preserves_other_fields() -> None:
    """Unit-M03: model_copy update preserves other typed fields."""
    data = _minimal_design_data(
        explanatory=[{"name": "x1", "role": "treatment"}],
        metrics=[{"target": "y"}],
        referenced_knowledge={"metrics": ["k1"]},
    )
    design = AnalysisDesign(**data)
    updated = design.model_copy(update={"methodology": Methodology(method="OLS")})
    assert updated.explanatory[0].role == VariableRole.treatment
    assert len(updated.metrics) == 1
    assert updated.referenced_knowledge == {"metrics": ["k1"]}


def test_yaml_roundtrip_metrics_canonical_form() -> None:
    """Unit-M04: Legacy single dict -> dump -> canonical list form."""
    # Red: depends on task 1.4 validators
    data = _minimal_design_data(metrics={"target": "y"})
    design = AnalysisDesign(**data)
    dumped = design.model_dump(mode="json")
    assert isinstance(dumped["metrics"], list)  # canonical form
    assert len(dumped["metrics"]) == 1


# ---------------------------------------------------------------------------
# YAML round-trip tests
# ---------------------------------------------------------------------------


def test_analysis_design_roundtrip_with_typed_fields() -> None:
    """Unit-RT01: Full typed fields round-trip (dump -> re-parse)."""
    data = _minimal_design_data(
        explanatory=[{"name": "x1", "role": "treatment", "data_source": "src1"}],
        metrics=[{"target": "y", "tier": "primary"}],
        chart=[{"intent": "correlation", "type": "scatter", "x": "x1", "y": "y"}],
        methodology={"method": "DID", "package": "statsmodels"},
    )
    design = AnalysisDesign(**data)
    dumped = design.model_dump(mode="json")
    restored = AnalysisDesign(**dumped)
    assert restored.explanatory[0].role == VariableRole.treatment
    assert restored.metrics[0].tier == MetricTier.primary
    assert restored.chart[0].intent == ChartIntent.correlation
    assert restored.methodology.method == "DID"


def test_analysis_design_roundtrip_legacy_format() -> None:
    """Unit-RT02: Legacy format (no role/tier/intent) round-trip."""
    # Red: depends on task 1.4 validators
    data = _minimal_design_data(
        explanatory=[{"name": "x1"}],
        metrics={"target": "y", "aggregation": "mean"},
        chart=[{"type": "scatter", "description": "test"}],
    )
    design = AnalysisDesign(**data)
    assert design.explanatory[0].role == VariableRole.covariate  # default
    assert len(design.metrics) == 1
    assert design.metrics[0].tier == MetricTier.primary  # default
    assert design.chart[0].intent == ChartIntent.correlation  # inferred from scatter

    dumped = design.model_dump(mode="json")
    restored = AnalysisDesign(**dumped)
    assert restored.explanatory[0].role == VariableRole.covariate
    assert restored.metrics[0].tier == MetricTier.primary
    assert restored.chart[0].intent == ChartIntent.correlation


# ---------------------------------------------------------------------------
# Extra field preservation tests (yaml-edit-resilience F1)
# ---------------------------------------------------------------------------


def test_analysis_design_extra_field_preserved_in_model_dump() -> None:
    """Unit-01: AnalysisDesign top-level extra field preserved in model_dump."""
    data = _minimal_design_data(analyst_note="important observation")
    design = AnalysisDesign(**data)
    result = design.model_dump(mode="json")
    assert result["analyst_note"] == "important observation"


def test_metric_extra_field_preserved_in_model_dump() -> None:
    """Unit-02: Metric nested extra field preserved in model_dump."""
    data = _minimal_design_data(
        metrics=[{"target": "revenue", "note": "seasonal adjustment needed"}]
    )
    design = AnalysisDesign(**data)
    result = design.model_dump(mode="json")
    assert result["metrics"][0]["note"] == "seasonal adjustment needed"


def test_chart_spec_extra_field_preserved() -> None:
    """Unit-04: ChartSpec extra field preserved in model_dump."""
    spec = ChartSpec(intent="distribution", type="histogram", color="red")
    result = spec.model_dump(mode="json")
    assert result["color"] == "red"


def test_explanatory_variable_extra_field_preserved() -> None:
    """Unit-05: ExplanatoryVariable extra field preserved in model_dump."""
    var = ExplanatoryVariable(name="age", memo="check outliers")
    result = var.model_dump(mode="json")
    assert result["memo"] == "check outliers"


def test_methodology_extra_field_preserved() -> None:
    """Unit-06: Methodology extra field preserved in model_dump."""
    m = Methodology(method="t-test", package="scipy", ref_paper="doi:xxx")
    result = m.model_dump(mode="json")
    assert result["ref_paper"] == "doi:xxx"


def test_migrate_metrics_preserves_extra_fields() -> None:
    """Unit-12: _migrate_metrics works with extra fields present."""
    data = _minimal_design_data(
        metrics={"target": "x"},
        custom="keep",
    )
    design = AnalysisDesign(**data)
    result = design.model_dump(mode="json")
    assert isinstance(result["metrics"], list)
    assert len(result["metrics"]) == 1
    assert result["metrics"][0]["target"] == "x"
    assert result["custom"] == "keep"


def test_infer_intent_preserves_extra_fields_on_chart() -> None:
    """Unit-13: _infer_intent_from_type works with extra fields present."""
    spec = ChartSpec(**{"type": "scatter", "annotation": "check R\u00b2"})
    result = spec.model_dump(mode="json")
    assert result["intent"] == "correlation"
    assert result["annotation"] == "check R\u00b2"


@pytest.mark.parametrize(
    "model_cls,kwargs",
    [
        (AnalysisDesign, {**_minimal_design_data(), "status": "BOGUS"}),
        (Metric, {"target": "x", "tier": "BOGUS"}),
        (ChartSpec, {"intent": "BOGUS"}),
        (ExplanatoryVariable, {"name": "x", "role": "BOGUS"}),
    ],
    ids=["DesignStatus", "MetricTier", "ChartIntent", "VariableRole"],
)
def test_extra_allow_still_rejects_invalid_enum(model_cls: type, kwargs: dict) -> None:
    """Unit-16: extra='allow' still rejects invalid enum values."""
    with pytest.raises(ValidationError):
        model_cls(**kwargs)
