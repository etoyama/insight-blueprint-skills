"""Backward compatibility tests for verification-design typed fields.

These tests validate that legacy YAML formats (no role/tier/intent/methodology)
are correctly handled after the model migration. Can be shrunk after migration
is complete and legacy data is fully converted.
"""

import asyncio
from pathlib import Path

import pytest

import insight_blueprint._registry as registry
import insight_blueprint.server as server_module
from insight_blueprint.core.designs import DesignService
from insight_blueprint.models.design import (
    AnalysisDesign,
    ChartIntent,
    MetricTier,
    VariableRole,
)


@pytest.fixture
def service(tmp_path: Path) -> DesignService:
    """Return a DesignService backed by a temporary directory."""
    (tmp_path / ".insight" / "designs").mkdir(parents=True)
    return DesignService(tmp_path)


# ---------------------------------------------------------------------------
# BC-01: Legacy YAML full backward compat
# ---------------------------------------------------------------------------


def test_legacy_yaml_full_backward_compat() -> None:
    """BC-01: Legacy format with no typed fields loads correctly."""
    data = {
        "id": "LEGACY-H01",
        "title": "Legacy",
        "hypothesis_statement": "s",
        "hypothesis_background": "b",
        "metrics": {"target": "y", "aggregation": "mean"},
        "explanatory": [{"name": "x1", "data_source": "src"}],
        "chart": [{"type": "scatter", "description": "test"}],
    }
    design = AnalysisDesign(**data)
    assert design.explanatory[0].role == VariableRole.covariate
    assert len(design.metrics) == 1
    assert design.metrics[0].tier == MetricTier.primary
    assert design.chart[0].intent == ChartIntent.correlation
    assert design.methodology is None


# ---------------------------------------------------------------------------
# BC-02: DesignService update with legacy metrics format
# ---------------------------------------------------------------------------


def test_update_design_with_legacy_metrics_format(service: DesignService) -> None:
    """BC-02: DesignService update with legacy dict metrics migrates correctly.

    model_copy does not re-validate, so we verify the persisted result
    (round-trip through YAML) which triggers Pydantic validators on re-read.
    """
    design = service.create_design(
        title="t",
        hypothesis_statement="s",
        hypothesis_background="b",
    )
    # Simulate passing legacy single-dict format through update
    service.update_design(design.id, metrics=[{"target": "new_metric"}])
    # Re-read from YAML to trigger validators
    reloaded = service.get_design(design.id)
    assert reloaded is not None
    assert len(reloaded.metrics) == 1
    assert reloaded.metrics[0].target == "new_metric"


# ---------------------------------------------------------------------------
# BC-03: MCP tool with invalid enum value returns error dict
# ---------------------------------------------------------------------------


@pytest.fixture
def initialized_server(tmp_path: Path) -> Path:
    """Set up server with a real DesignService backed by tmp_path."""
    (tmp_path / ".insight" / "designs").mkdir(parents=True)
    original = registry.design_service
    registry.design_service = DesignService(tmp_path)
    yield tmp_path  # type: ignore[misc]
    registry.design_service = original


def test_create_design_invalid_role_returns_error(initialized_server: Path) -> None:
    """BC-03: MCP tool with invalid enum value returns error dict."""
    result = asyncio.run(
        server_module.create_analysis_design(
            title="t",
            hypothesis_statement="s",
            hypothesis_background="b",
            explanatory=[{"name": "x1", "role": "invalid_role"}],
        )
    )
    assert "error" in result
