"""Unit tests for the pure-function validation library (Epic 02).

`validate.py` is the single source of truth for design-document integrity.
It must stay pure (no I/O), so every test here works on plain dicts.
"""

import pytest
from pydantic import ValidationError

from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.validate import (
    VALID_TRANSITIONS,
    validate_design_change,
    validate_schema,
    validate_transition,
)


def make_design(**overrides: object) -> dict:
    """Factory for a minimal valid AnalysisDesign dict. Merge overrides."""
    base: dict = {
        "id": "FP-H01",
        "title": "Test design",
        "hypothesis_statement": "X improves Y",
        "hypothesis_background": "Because Z",
        "status": "in_review",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_transition
# ---------------------------------------------------------------------------


class TestValidateTransition:
    """State-transition guard, moved from reviews._validate_transition."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (current, target)
            for current, targets in VALID_TRANSITIONS.items()
            for target in targets
        ],
    )
    def test_allowed_transitions_pass(
        self, current: DesignStatus, target: DesignStatus
    ) -> None:
        """Every (current -> target) pair listed in VALID_TRANSITIONS is allowed."""
        validate_transition(current, target)  # must not raise

    def test_disallowed_transition_raises(self) -> None:
        """A transition not in the allow-set raises ValueError."""
        with pytest.raises(ValueError, match="Cannot transition from 'analyzing'"):
            validate_transition(DesignStatus.analyzing, DesignStatus.supported)

    def test_terminal_status_has_no_targets(self) -> None:
        """Terminal statuses (supported/rejected/inconclusive) allow no transition."""
        with pytest.raises(ValueError, match="Valid targets: none"):
            validate_transition(DesignStatus.supported, DesignStatus.in_review)

    def test_message_lists_sorted_valid_targets(self) -> None:
        """Error message enumerates the sorted valid targets."""
        with pytest.raises(ValueError) as exc:
            validate_transition(DesignStatus.analyzing, DesignStatus.rejected)
        # analyzing only allows in_review
        assert "in_review" in str(exc.value)


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------


class TestValidateSchema:
    """Pydantic schema validation wrapping AnalysisDesign."""

    def test_valid_dict_returns_model(self) -> None:
        design = validate_schema(make_design())
        assert isinstance(design, AnalysisDesign)
        assert design.id == "FP-H01"
        assert design.status == DesignStatus.in_review

    def test_empty_methodology_method_rejected(self) -> None:
        """Methodology.method has min_length=1; empty string is invalid."""
        with pytest.raises(ValidationError):
            validate_schema(make_design(methodology={"method": ""}))

    def test_valid_methodology_accepted(self) -> None:
        design = validate_schema(make_design(methodology={"method": "OLS"}))
        assert design.methodology is not None
        assert design.methodology.method == "OLS"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_schema(make_design(status="not_a_status"))

    def test_missing_required_field_rejected(self) -> None:
        data = make_design()
        del data["title"]
        with pytest.raises(ValidationError):
            validate_schema(data)

    def test_legacy_metrics_empty_dict_migrates_to_list(self) -> None:
        """Backward compat: metrics={} becomes []."""
        design = validate_schema(make_design(metrics={}))
        assert design.metrics == []

    def test_legacy_metrics_single_dict_migrates_to_list(self) -> None:
        """Backward compat: a single metric dict becomes a one-element list."""
        design = validate_schema(make_design(metrics={"target": "CVR"}))
        assert len(design.metrics) == 1
        assert design.metrics[0].target == "CVR"


# ---------------------------------------------------------------------------
# validate_design_change (hook-facing aggregator)
# ---------------------------------------------------------------------------


class TestValidateDesignChange:
    """Aggregator: schema + (optional) transition. Returns error strings, never raises."""

    def test_new_valid_design_returns_no_errors(self) -> None:
        """current_data=None means new file: schema only, no transition check."""
        assert validate_design_change(make_design(), None) == []

    def test_new_design_with_terminal_status_allowed(self) -> None:
        """New files are schema-only: any initial status is permitted (behaviour unchanged)."""
        assert validate_design_change(make_design(status="supported"), None) == []

    def test_new_design_schema_violation_returns_errors(self) -> None:
        errors = validate_design_change(make_design(methodology={"method": ""}), None)
        assert errors  # non-empty
        assert any("method" in e for e in errors)

    def test_existing_valid_transition_returns_no_errors(self) -> None:
        current = make_design(status="in_review")
        new = make_design(status="analyzing")
        assert validate_design_change(new, current) == []

    def test_existing_invalid_transition_returns_errors(self) -> None:
        current = make_design(status="analyzing")
        new = make_design(status="supported")
        errors = validate_design_change(new, current)
        assert errors
        assert any("transition" in e.lower() for e in errors)

    def test_status_unchanged_skips_transition_check(self) -> None:
        """Body-only edit on a terminal design must not be blocked as a self-transition."""
        current = make_design(status="supported")
        new = make_design(status="supported", title="Edited title")
        assert validate_design_change(new, current) == []

    def test_schema_violation_takes_precedence_over_transition(self) -> None:
        """An invalid new_data reports schema errors even when a transition is involved."""
        current = make_design(status="in_review")
        new = make_design(status="analyzing", methodology={"method": ""})
        errors = validate_design_change(new, current)
        assert errors
