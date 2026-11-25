"""Unit tests for the pure-function validation library (Epic 02).

`validate.py` is the single source of truth for design-document integrity.
It must stay pure (no I/O), so every test here works on plain dicts.
"""

import pytest
from pydantic import ValidationError

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    DesignForm,
    DesignStatus,
)
from insight_blueprint.validate import (
    VALID_TRANSITIONS,
    valid_targets,
    validate_creation,
    validate_design_change,
    validate_schema,
    validate_transition,
)

CONFIRMATION = DesignForm.confirmation
VERDICTS = [DesignStatus.supported, DesignStatus.rejected, DesignStatus.inconclusive]


def make_exploration(**overrides: object) -> dict:
    """Factory for a minimal exploratory design as Epic 32 writes it."""
    base: dict = {
        "id": "FP-H01",
        "title": "Test design",
        "analysis_intent": "exploratory",
        "exploration_question": "How far apart are the regions?",
        "exploration_background": "Nobody has measured the spread",
        "status": "in_review",
    }
    base.update(overrides)
    return base


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
        """Every pair in VALID_TRANSITIONS is allowed for a form that may end there."""
        form = (
            DesignForm.exploration
            if target is DesignStatus.explored
            else DesignForm.confirmation
        )
        validate_transition(current, target, form)  # must not raise

    def test_disallowed_transition_raises(self) -> None:
        """A transition not in the allow-set raises ValueError."""
        with pytest.raises(ValueError, match="Cannot transition from 'analyzing'"):
            validate_transition(
                DesignStatus.analyzing, DesignStatus.revision_requested, CONFIRMATION
            )

    @pytest.mark.parametrize(
        "conclusion",
        [DesignStatus.supported, DesignStatus.rejected, DesignStatus.inconclusive],
    )
    def test_analyzing_reaches_each_conclusion_directly(
        self, conclusion: DesignStatus
    ) -> None:
        """A reflection closes an analyzed design without a review in between (ADR-0029)."""
        validate_transition(DesignStatus.analyzing, conclusion, CONFIRMATION)

    def test_analyzing_can_still_go_back_to_in_review(self) -> None:
        """Reviewing the result after the analysis stays available, as an option."""
        validate_transition(
            DesignStatus.analyzing, DesignStatus.in_review, CONFIRMATION
        )

    def test_terminal_status_has_no_targets(self) -> None:
        """Terminal statuses (supported/rejected/inconclusive) allow no transition."""
        with pytest.raises(ValueError, match="Valid targets: none"):
            validate_transition(
                DesignStatus.supported, DesignStatus.in_review, CONFIRMATION
            )

    def test_message_lists_sorted_valid_targets(self) -> None:
        """Error message enumerates the sorted valid targets."""
        with pytest.raises(ValueError) as exc:
            validate_transition(
                DesignStatus.analyzing, DesignStatus.revision_requested, CONFIRMATION
            )
        assert str(exc.value).endswith(
            "Valid targets: in_review, inconclusive, rejected, supported"
        )


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

    def test_design_without_decision_context_is_accepted(self) -> None:
        """Epic 12 US-2 AC 4: designs written before the field existed still pass."""
        assert validate_schema(make_design()).decision_context is None

    def test_valid_decision_context_accepted(self) -> None:
        design = validate_schema(
            make_design(
                decision_context={
                    "decision_maker": "事業責任者",
                    "decision": "値上げを実施するか",
                }
            )
        )
        assert design.decision_context is not None
        assert design.decision_context.decision_maker == "事業責任者"
        assert design.decision_context.decision == "値上げを実施するか"

    def test_decision_context_missing_one_side_rejected(self) -> None:
        """Epic 12 US-2 AC 1: who decides and what they decide come as a pair."""
        with pytest.raises(ValidationError):
            validate_schema(
                make_design(decision_context={"decision_maker": "事業責任者"})
            )

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

    def test_half_filled_decision_context_names_the_missing_side(self) -> None:
        """The hook message must point at the field the analyst has to fill."""
        errors = validate_design_change(
            make_design(decision_context={"decision": "値上げを実施するか"}), None
        )
        assert any("decision_context.decision_maker" in e for e in errors)

    def test_existing_valid_transition_returns_no_errors(self) -> None:
        current = make_design(status="in_review")
        new = make_design(status="analyzing")
        assert validate_design_change(new, current) == []

    def test_existing_invalid_transition_returns_errors(self) -> None:
        current = make_design(status="analyzing")
        new = make_design(status="revision_requested")
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


def test_terminal_statuses_are_the_ones_nothing_follows() -> None:
    from insight_blueprint.models.design import TERMINAL_STATUSES

    assert TERMINAL_STATUSES == {s for s, t in VALID_TRANSITIONS.items() if not t}


# ---------------------------------------------------------------------------
# Epic 32, Story 32.1: the end of a design follows its form (ADR-0048, ADR-0049)
# ---------------------------------------------------------------------------

_BEFORE_A_CONCLUSION = [
    DesignStatus.in_review,
    DesignStatus.revision_requested,
    DesignStatus.analyzing,
]


class TestConclusionFollowsTheForm:
    """US-2 AC 2: an exploration ends only as explored, the others only on a verdict."""

    @pytest.mark.parametrize("current", _BEFORE_A_CONCLUSION)
    def test_an_exploration_concludes_as_explored(self, current: DesignStatus) -> None:
        validate_transition(current, DesignStatus.explored, DesignForm.exploration)

    @pytest.mark.parametrize("current", _BEFORE_A_CONCLUSION)
    @pytest.mark.parametrize("verdict", VERDICTS)
    def test_an_exploration_takes_no_verdict(
        self, current: DesignStatus, verdict: DesignStatus
    ) -> None:
        with pytest.raises(ValueError, match="Cannot transition"):
            validate_transition(current, verdict, DesignForm.exploration)

    @pytest.mark.parametrize(
        "form", [DesignForm.confirmation, DesignForm.legacy_exploration]
    )
    @pytest.mark.parametrize("current", _BEFORE_A_CONCLUSION)
    def test_a_confirmation_and_a_legacy_exploration_do_not_end_as_explored(
        self, form: DesignForm, current: DesignStatus
    ) -> None:
        with pytest.raises(ValueError, match="Cannot transition"):
            validate_transition(current, DesignStatus.explored, form)

    @pytest.mark.parametrize("verdict", VERDICTS)
    def test_a_legacy_exploration_concludes_on_a_verdict(
        self, verdict: DesignStatus
    ) -> None:
        validate_transition(
            DesignStatus.analyzing, verdict, DesignForm.legacy_exploration
        )

    def test_the_message_lists_only_the_targets_of_the_form(self) -> None:
        with pytest.raises(ValueError) as exc:
            validate_transition(
                DesignStatus.analyzing, DesignStatus.supported, DesignForm.exploration
            )
        assert str(exc.value).endswith("Valid targets: explored, in_review")

    def test_explored_is_followed_by_nothing(self) -> None:
        assert valid_targets(DesignStatus.explored, DesignForm.exploration) == set()

    def test_the_hook_refuses_a_verdict_on_an_exploration(self) -> None:
        current = make_exploration(status="analyzing")
        errors = validate_design_change(make_exploration(status="supported"), current)
        assert any("ends as explored" in e for e in errors)

    def test_the_hook_lets_an_exploration_end_as_explored(self) -> None:
        current = make_exploration(status="analyzing")
        new = make_exploration(status="explored")
        assert validate_design_change(new, current) == []


class TestSavedDesignsStillRead:
    """US-2 AC 4: saved designs pass the read check, and move as before."""

    @pytest.fixture(
        params=[
            {"analysis_intent": "exploratory"},
            {"analysis_intent": "mixed"},
            {},
        ],
        ids=["legacy-exploration", "mixed", "no-intent"],
    )
    def saved(self, request: pytest.FixtureRequest) -> dict:
        data = make_design(status="analyzing", **request.param)
        if not request.param:
            assert "analysis_intent" not in data
        return data

    def test_a_saved_design_passes_the_read_check(self, saved: dict) -> None:
        assert validate_design_change(saved, None) == []

    @pytest.mark.parametrize("verdict", VERDICTS)
    def test_a_saved_design_concludes_on_a_verdict(
        self, saved: dict, verdict: DesignStatus
    ) -> None:
        assert validate_design_change({**saved, "status": verdict.value}, saved) == []

    def test_a_saved_design_does_not_end_as_explored(self, saved: dict) -> None:
        errors = validate_design_change({**saved, "status": "explored"}, saved)
        assert any("not explored" in e for e in errors)


def _model(data: dict) -> AnalysisDesign:
    return validate_schema(data)


class TestValidateCreation:
    """US-2 AC 1, AC 3: the check of the create path writes only the new forms."""

    def test_a_new_exploration_passes(self) -> None:
        assert validate_creation(_model(make_exploration())) == []

    def test_a_new_confirmation_passes(self) -> None:
        assert validate_creation(_model(make_design())) == []

    def test_a_new_mixed_design_is_refused(self) -> None:
        errors = validate_creation(_model(make_design(analysis_intent="mixed")))
        assert any("mixed" in e for e in errors)

    def test_a_new_exploration_with_a_hypothesis_is_refused(self) -> None:
        legacy = _model(make_design(analysis_intent="exploratory"))
        errors = validate_creation(legacy)
        assert any("exploration_question" in e for e in errors)

    @pytest.mark.parametrize("field", ["hypothesis_statement", "hypothesis_background"])
    def test_a_new_confirmation_needs_a_written_hypothesis(self, field: str) -> None:
        errors = validate_creation(_model(make_design(**{field: " "})))
        assert any(field in e for e in errors)

    # --- an update (the current design on disk is given) ---

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested]
    )
    def test_the_intent_changes_before_the_analysis(self, status: DesignStatus) -> None:
        current = _model(make_design(status=status.value))
        new = _model(make_exploration(status=status.value))
        assert validate_creation(new, current) == []

    def test_the_intent_does_not_change_once_analyzing(self) -> None:
        # Past analyzing the pair cannot even be written: a verdict belongs to a
        # hypothesis and explored to a question (the model refuses the record).
        current = _model(make_design(status="analyzing"))
        new = _model(make_exploration(status="analyzing"))
        errors = validate_creation(new, current)
        assert any("analysis_intent" in e for e in errors)

    def test_the_intent_does_not_change_to_mixed(self) -> None:
        current = _model(make_design())
        new = _model(make_design(analysis_intent="mixed"))
        assert any("mixed" in e for e in validate_creation(new, current))

    def test_an_exploration_does_not_become_a_legacy_exploration(self) -> None:
        current = _model(make_exploration())
        swapped = make_design(analysis_intent="exploratory")
        errors = validate_creation(_model(swapped), current)
        assert any("exploration_question" in e for e in errors)

    def test_a_confirmation_does_not_become_a_legacy_exploration(self) -> None:
        current = _model(make_design())
        new = _model(make_design(analysis_intent="exploratory"))
        assert validate_creation(new, current)

    @pytest.mark.parametrize("status", [DesignStatus.analyzing, *VERDICTS])
    def test_a_legacy_exploration_is_fixed_to_confirmatory_in_any_status(
        self, status: DesignStatus
    ) -> None:
        current = _model(make_design(analysis_intent="exploratory", status=status))
        new = _model(make_design(analysis_intent="confirmatory", status=status))
        assert validate_creation(new, current) == []

    def test_fixing_a_legacy_exploration_keeps_its_hypothesis(self) -> None:
        current = _model(make_design(analysis_intent="exploratory", status="supported"))
        new = _model(
            make_design(
                analysis_intent="confirmatory",
                status="supported",
                hypothesis_statement="A claim written after the result",
            )
        )
        assert any("analysis_intent" in e for e in validate_creation(new, current))

    @pytest.mark.parametrize(
        "intent", ["exploratory", "mixed"], ids=["legacy-exploration", "mixed"]
    )
    def test_a_saved_design_is_updated_in_its_form(self, intent: str) -> None:
        current = _model(make_design(analysis_intent=intent, status="analyzing"))
        new = _model(
            make_design(analysis_intent=intent, status="analyzing", title="Edited")
        )
        assert validate_creation(new, current) == []


def test_explored_is_one_of_the_terminal_statuses() -> None:
    assert DesignStatus.explored in TERMINAL_STATUSES


class TestFormChange:
    """US-2 AC 3: the form changes under the same rule as the intent."""

    def test_a_legacy_exploration_takes_the_new_form_before_the_analysis(self) -> None:
        current = _model(make_design(analysis_intent="exploratory"))
        assert validate_creation(_model(make_exploration()), current) == []

    def test_a_legacy_exploration_does_not_drop_its_hypothesis_once_analyzing(
        self,
    ) -> None:
        current = _model(make_design(analysis_intent="exploratory", status="analyzing"))
        new = _model(make_exploration(status="analyzing"))
        assert any("analysis_intent" in e for e in validate_creation(new, current))
