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
    analysis_started,
    valid_targets,
    validate_creation,
    validate_design_change,
    validate_schema,
    validate_transition,
    validate_update,
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
        current = confirmation(status="in_review")
        new = confirmation(status="analyzing")
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


class TestTheHookChecksUpdatesLikeDesignIo:
    """A direct write over a readable design meets validate_update, as design_io does."""

    @pytest.mark.parametrize(
        "intent", ["exploratory", "mixed"], ids=["legacy-exploration", "mixed"]
    )
    def test_a_saved_design_is_rewritten_in_its_form(self, intent: str) -> None:
        current = make_design(analysis_intent=intent, status="analyzing")
        new = {**current, "title": "Edited"}
        assert validate_design_change(new, current) == []

    def test_a_legacy_exploration_is_fixed_to_confirmatory(self) -> None:
        current = make_design(analysis_intent="exploratory", status="supported")
        new = {**current, "analysis_intent": "confirmatory"}
        assert validate_design_change(new, current) == []

    def test_an_analyzing_confirmation_is_not_rewritten_into_an_explored_exploration(
        self,
    ) -> None:
        # analyzing -> explored is a move the new form allows, so the transition
        # check alone (given new_model.form()) lets it through: the refusal of the
        # swap is what stops it.
        current = make_design(status="analyzing")
        errors = validate_design_change(make_exploration(status="explored"), current)
        assert len(errors) == 1
        assert "derive a new design" in errors[0]

    def test_an_analyzing_exploration_does_not_take_a_hypothesis_and_a_verdict(
        self,
    ) -> None:
        current = make_exploration(status="analyzing")
        errors = validate_design_change(make_design(status="supported"), current)
        assert len(errors) == 1
        assert "derive a new design" in errors[0]

    def test_a_new_file_is_still_checked_by_the_schema_only(self) -> None:
        legacy = make_design(analysis_intent="exploratory", status="supported")
        assert validate_design_change(legacy, None) == []

    def test_a_design_broken_on_disk_is_still_not_compared(self) -> None:
        broken = {"id": "FP-H01", "status": "nonsense"}
        new = make_design(analysis_intent="mixed", status="supported")
        assert validate_design_change(new, broken) == []


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

    # --- an update (validate_update: the current design on disk is given) ---

    def test_an_update_checks_the_move_of_its_status(self) -> None:
        current = _model(make_design(status="in_review"))
        new = _model(make_design(status="supported"))
        assert validate_update(new, current) == []
        concluded = _model(make_design(status="supported"))
        errors = validate_update(_model(make_design(status="analyzing")), concluded)
        assert any("Cannot transition" in e for e in errors)

    @pytest.mark.parametrize(
        "status", [DesignStatus.in_review, DesignStatus.revision_requested]
    )
    def test_the_intent_changes_before_the_analysis(self, status: DesignStatus) -> None:
        current = _model(make_design(status=status.value))
        new = _model(make_exploration(status=status.value))
        assert validate_update(new, current) == []

    def test_the_intent_does_not_change_once_analyzing(self) -> None:
        # Past analyzing the pair cannot even be written: a verdict belongs to a
        # hypothesis and explored to a question (the model refuses the record).
        current = _model(make_design(status="analyzing"))
        new = _model(make_exploration(status="analyzing"))
        errors = validate_update(new, current)
        assert any("analysis_intent" in e for e in errors)

    def test_the_intent_does_not_change_to_mixed(self) -> None:
        current = _model(make_design())
        new = _model(make_design(analysis_intent="mixed"))
        assert any("mixed" in e for e in validate_update(new, current))

    def test_an_exploration_does_not_become_a_legacy_exploration(self) -> None:
        current = _model(make_exploration())
        swapped = make_design(analysis_intent="exploratory")
        errors = validate_update(_model(swapped), current)
        assert any("exploration_question" in e for e in errors)

    def test_a_confirmation_does_not_become_a_legacy_exploration(self) -> None:
        current = _model(make_design())
        new = _model(make_design(analysis_intent="exploratory"))
        assert validate_update(new, current)

    @pytest.mark.parametrize("status", [DesignStatus.analyzing, *VERDICTS])
    def test_a_legacy_exploration_is_fixed_to_confirmatory_in_any_status(
        self, status: DesignStatus
    ) -> None:
        current = _model(make_design(analysis_intent="exploratory", status=status))
        new = _model(make_design(analysis_intent="confirmatory", status=status))
        assert validate_update(new, current) == []

    def test_fixing_a_legacy_exploration_keeps_its_hypothesis(self) -> None:
        current = _model(make_design(analysis_intent="exploratory", status="supported"))
        new = _model(
            make_design(
                analysis_intent="confirmatory",
                status="supported",
                hypothesis_statement="A claim written after the result",
            )
        )
        assert any("analysis_intent" in e for e in validate_update(new, current))

    @pytest.mark.parametrize(
        "intent", ["exploratory", "mixed"], ids=["legacy-exploration", "mixed"]
    )
    def test_a_saved_design_is_updated_in_its_form(self, intent: str) -> None:
        current = _model(make_design(analysis_intent=intent, status="analyzing"))
        new = _model(
            make_design(analysis_intent=intent, status="analyzing", title="Edited")
        )
        assert validate_update(new, current) == []


def test_explored_is_one_of_the_terminal_statuses() -> None:
    assert DesignStatus.explored in TERMINAL_STATUSES


class TestFormChange:
    """US-2 AC 3: the form changes under the same rule as the intent."""

    def test_a_legacy_exploration_takes_the_new_form_before_the_analysis(self) -> None:
        current = _model(make_design(analysis_intent="exploratory"))
        assert validate_update(_model(make_exploration()), current) == []

    def test_a_legacy_exploration_does_not_drop_its_hypothesis_once_analyzing(
        self,
    ) -> None:
        current = _model(make_design(analysis_intent="exploratory", status="analyzing"))
        new = _model(make_exploration(status="analyzing"))
        assert any("analysis_intent" in e for e in validate_update(new, current))


# ---------------------------------------------------------------------------
# Epic 33 US-3: the analysis mark and what a started confirmation keeps
# ---------------------------------------------------------------------------

MARK = "2026-11-25T10:00:00+09:00"
CRITERION = "supported at 2.0 days or more, rejected under 1.0 day"
STARTED_STATUSES = [DesignStatus.analyzing, *VERDICTS]


def primary(**overrides: object) -> dict:
    return {"target": "lead time", "tier": "primary", "comparison": CRITERION} | (
        overrides
    )


def confirmation(**overrides: object) -> dict:
    """A confirmation that states its criterion, as it must to be analyzed."""
    return make_design(metrics=[primary()]) | overrides


def result_review(**overrides: object) -> dict:
    """A confirmation sent back to in_review after its analysis started."""
    return confirmation(status="in_review", analysis_started_at=MARK) | overrides


def _errors(new: dict, current: dict) -> list[str]:
    return validate_update(_model(new), _model(current))


class TestAnalysisStarted:
    """US-3 AC 1, AC 5: what tells that the analysis of a design has started."""

    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_a_design_before_its_analysis_has_not_started(self, status: str) -> None:
        assert not analysis_started(_model(make_design(status=status)))

    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_the_mark_tells_it_in_any_status(self, status: str) -> None:
        assert analysis_started(_model(result_review(status=status)))

    @pytest.mark.parametrize("status", STARTED_STATUSES)
    def test_a_saved_design_without_the_mark_is_read_by_its_status(
        self, status: DesignStatus
    ) -> None:
        assert analysis_started(_model(make_design(status=status)))

    def test_a_saved_design_without_the_mark_still_reads(self) -> None:
        assert _model(make_design()).analysis_started_at is None

    def test_a_design_without_the_mark_writes_no_mark(self) -> None:
        assert "analysis_started_at" not in _model(make_design()).model_dump()


class TestTheAnalysisMarkStays:
    """US-3 AC 1: the mark is put on entering the analysis and never leaves."""

    @pytest.mark.parametrize("status", STARTED_STATUSES)
    def test_the_mark_is_put_on_entering_the_analysis(
        self, status: DesignStatus
    ) -> None:
        new = confirmation(status=status, analysis_started_at=MARK)
        assert _errors(new, confirmation()) == []

    def test_the_mark_is_not_put_on_a_design_that_stays_before_its_analysis(
        self,
    ) -> None:
        new = confirmation(status="revision_requested", analysis_started_at=MARK)
        errors = _errors(new, confirmation())
        assert any("analysis_started_at" in e for e in errors)

    @pytest.mark.parametrize("status", ["in_review", "analyzing", "supported"])
    def test_the_mark_is_not_removed(self, status: str) -> None:
        current = result_review(status=status)
        new = confirmation(status=status)
        assert any("analysis_started_at" in e for e in _errors(new, current))

    def test_the_mark_is_not_changed(self) -> None:
        new = result_review(analysis_started_at="2026-11-26T10:00:00+09:00")
        assert any("analysis_started_at" in e for e in _errors(new, result_review()))

    def test_the_mark_stays_through_a_review_of_the_result(self) -> None:
        analyzing = confirmation(status="analyzing", analysis_started_at=MARK)
        assert _errors(result_review(), analyzing) == []
        back = result_review(status="revision_requested")
        assert _errors(back, result_review()) == []

    def test_a_saved_design_does_not_leave_the_analysis_without_the_mark(self) -> None:
        current = confirmation(status="analyzing")
        errors = _errors(confirmation(status="in_review"), current)
        assert any("analysis_started_at" in e for e in errors)

    def test_a_saved_design_leaves_the_analysis_with_the_mark(self) -> None:
        current = confirmation(status="analyzing")
        assert _errors(result_review(), current) == []

    def test_a_saved_design_concludes_without_the_mark(self) -> None:
        current = confirmation(status="analyzing")
        assert _errors(confirmation(status="supported"), current) == []


def _started(intent: str) -> list[dict]:
    """A started design of *intent* in each shape the record can take."""
    return [
        confirmation(analysis_intent=intent, status="analyzing"),
        result_review(analysis_intent=intent),
        result_review(analysis_intent=intent, status="revision_requested"),
        confirmation(analysis_intent=intent, status="supported"),
    ]


JUDGING_AND_STARTED = [
    pytest.param(
        d, id=f"{d['analysis_intent']}-{d['status']}-{'analysis_started_at' in d}"
    )
    for intent in ("confirmatory", "exploratory", "mixed")
    for d in _started(intent)
]


class TestAStartedConfirmationKeepsItsHypothesisAndCriterion:
    """US-3 AC 2: nothing the judgment rests on changes after the analysis starts."""

    @pytest.mark.parametrize("current", JUDGING_AND_STARTED)
    def test_the_hypothesis_does_not_change(self, current: dict) -> None:
        new = current | {"hypothesis_statement": "X improves Y a little"}
        errors = _errors(new, current)
        assert any("hypothesis_statement" in e and "derive" in e for e in errors)

    @pytest.mark.parametrize(
        "metrics",
        [
            [primary(comparison="supported at 0.5 days or more")],
            [primary(target="median lead time")],
            [primary(), primary(target="return rate")],
            [],
            [primary(tier="secondary")],
            [primary(), {"target": "return rate", "tier": "secondary"}]
            + [primary(target="return rate")],
        ],
        ids=["comparison", "target", "added", "removed", "demoted", "promoted-copy"],
    )
    @pytest.mark.parametrize("current", JUDGING_AND_STARTED)
    def test_the_primary_metrics_do_not_change(
        self, current: dict, metrics: list[dict]
    ) -> None:
        errors = _errors(current | {"metrics": metrics}, current)
        assert any("metrics" in e and "derive" in e for e in errors)

    def test_a_secondary_metric_is_not_promoted(self) -> None:
        current = result_review(
            metrics=[primary(), {"target": "return rate", "tier": "secondary"}]
        )
        new = current | {
            "metrics": [primary(), {"target": "return rate", "tier": "primary"}]
        }
        assert any("metrics" in e for e in _errors(new, current))

    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_the_intent_does_not_change_after_a_review_of_the_result(
        self, status: str
    ) -> None:
        current = result_review(status=status)
        new = make_exploration(status=status, analysis_started_at=MARK)
        errors = _errors(new, current)
        assert any("analysis_intent" in e and "derive" in e for e in errors)

    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_a_started_exploration_keeps_its_intent_and_form(self, status: str) -> None:
        current = make_exploration(status=status, analysis_started_at=MARK)
        new = result_review(status=status)
        assert any("analysis_intent" in e for e in _errors(new, current))

    def test_a_started_exploration_may_reword_its_question(self) -> None:
        current = make_exploration(status="in_review", analysis_started_at=MARK)
        new = current | {"exploration_question": "How far apart are the regions now?"}
        assert _errors(new, current) == []

    def test_before_the_analysis_everything_may_change(self) -> None:
        new = confirmation(
            hypothesis_statement="X improves Y a little",
            metrics=[primary(comparison="supported at 0.5 days or more")],
        )
        assert _errors(new, confirmation(status="revision_requested")) == []

    def test_a_started_legacy_exploration_is_still_fixed_to_confirmatory(self) -> None:
        current = result_review(analysis_intent="exploratory")
        new = result_review(analysis_intent="confirmatory")
        assert _errors(new, current) == []


class TestAStartedConfirmationStillTakesOtherChanges:
    """US-3 AC 3: only what the judgment rests on is held."""

    @pytest.mark.parametrize(
        "changes",
        [
            {"hypothesis_background": "Because Z, as the 2025 survey shows"},
            {
                "metrics": [
                    primary(),
                    {"target": "return rate", "tier": "secondary"},
                    {"target": "cost", "tier": "guardrail", "comparison": "< 5%"},
                ]
            },
            {"metrics": [primary(aggregation="median", filter="region == 'east'")]},
            {"explanatory": [{"name": "region", "role": "confounder"}]},
            {"chart": [{"intent": "trend", "type": "line"}]},
            {"methodology": {"method": "difference in means"}},
            {"decision_context": {"decision_maker": "ops lead", "decision": "roll"}},
            {"next_action": {"if_supported": "roll out"}},
            {"title": "Edited"},
        ],
        ids=[
            "background",
            "secondary-and-guardrail",
            "other-fields-of-the-primary",
            "explanatory",
            "chart",
            "methodology",
            "decision-context",
            "next-action",
            "title",
        ],
    )
    @pytest.mark.parametrize("current", JUDGING_AND_STARTED)
    def test_a_field_outside_the_judgment_changes(
        self, current: dict, changes: dict
    ) -> None:
        assert _errors(current | changes, current) == []

    def test_the_primary_metrics_may_be_reordered(self) -> None:
        both = [primary(), primary(target="return rate")]
        current = result_review(metrics=both)
        assert _errors(current | {"metrics": both[::-1]}, current) == []


class TestEnteringTheAnalysisNeedsACriterion:
    """US-3 AC 4: a judging design is analyzed only with its criterion written."""

    @pytest.mark.parametrize("intent", ["confirmatory", "exploratory", "mixed"])
    @pytest.mark.parametrize(
        "metrics",
        [
            [],
            [{"target": "return rate", "tier": "secondary", "comparison": "< 5%"}],
            [primary(comparison="")],
            [primary(comparison="  ")],
            [primary(), primary(target="return rate", comparison="")],
        ],
        ids=["no-metric", "no-primary", "empty", "blank", "one-of-two-empty"],
    )
    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_a_judging_design_without_a_criterion_is_not_analyzed(
        self, intent: str, metrics: list[dict], status: str
    ) -> None:
        current = make_design(analysis_intent=intent, metrics=metrics, status=status)
        new = current | {"status": "analyzing", "analysis_started_at": MARK}
        errors = _errors(new, current)
        assert any("comparison" in e and "primary" in e for e in errors)

    def test_a_judging_design_with_a_criterion_is_analyzed(self) -> None:
        new = confirmation(status="analyzing", analysis_started_at=MARK)
        assert _errors(new, confirmation()) == []

    def test_the_words_of_the_criterion_are_not_read(self) -> None:
        current = make_design(metrics=[primary(comparison="see the review")])
        new = current | {"status": "analyzing", "analysis_started_at": MARK}
        assert _errors(new, current) == []

    def test_an_exploration_is_analyzed_without_a_criterion(self) -> None:
        new = make_exploration(status="analyzing", analysis_started_at=MARK)
        assert _errors(new, make_exploration()) == []

    def test_a_saved_design_without_a_criterion_returns_from_a_review_of_its_result(
        self,
    ) -> None:
        # Its criterion can no longer be written, so asking for it would leave
        # the design with no way back to analyzing.
        current = make_design(status="in_review", analysis_started_at=MARK)
        assert _errors(current | {"status": "analyzing"}, current) == []

    def test_a_saved_design_without_a_criterion_is_still_updated(self) -> None:
        current = make_design(status="analyzing")
        assert _errors(current | {"title": "Edited"}, current) == []
