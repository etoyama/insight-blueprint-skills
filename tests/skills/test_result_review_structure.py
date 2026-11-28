"""Structure tests for the review of the result (Epic 33, Story 33.5).

A review after the analysis reads the notebook, the verdict and the figures, and
its comments may point at them (ADR-0054). A started confirmation keeps its
hypothesis, its criterion and its intent (ADR-0053), so a revision cannot fix a
comment on them with ``design_io update``. The prose must say both, or the
review checks only the design and the revision sends writes that are refused.
"""

from __future__ import annotations

from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import _read_skill

_RESULT_TARGETS = ("`notebook`", "`verdict`", "`figures`")


def _review(heading: str) -> str:
    return unwrap(section(_read_skill("analysis-review"), heading))


def _revision(heading: str) -> str:
    return unwrap(section(_read_skill("analysis-revision"), heading))


class TestReviewReadsTheResult:
    """US-4 AC 2: /analysis-review reads the result when a verdict exists."""

    def test_step_3_sends_a_design_with_a_verdict_to_the_result_lenses(self) -> None:
        step = _review("### Step 3: ")
        assert "{design_id}_verdict.json`" in step
        assert "Step 3b" in step

    def test_it_says_what_it_reads_before_the_critique(self) -> None:
        step = _review("### Step 3b: ")
        assert "Before the critique, tell the analyst" in step
        for read in (
            "`.insight/notebooks/{design_id}.py`",
            "`.insight/notebooks/{design_id}_verdict.json`",
            "`.insight/notebooks/{design_id}_fig",
        ):
            assert read in step

    def test_the_judgment_is_read_against_the_lines_the_verdict_carries(self) -> None:
        step = _review("### Step 3b: ")
        for name in ("`support_line`", "`reject_line`", "`judgment`", "`comparison`"):
            assert name in step

    def test_it_names_what_the_other_lenses_read(self) -> None:
        """ADR-0071 6: the cells are left to the check of the computation (Story 36.8)."""
        step = _review("### Step 3b: ")
        assert "contradicts the `judgment`" in step
        assert "axis" in step and "how to read" in step
        assert "guardrail" in step and "`pass`" in step

    def test_result_comments_target_the_result(self) -> None:
        step = _review("### Step 3b: ")
        for target in _RESULT_TARGETS:
            assert target in step

    def test_an_exploration_is_read_without_a_criterion(self) -> None:
        """ADR-0050 3: an exploration carries no line and no judgment."""
        step = _review("### Step 3b: ")
        assert "An exploration has no criterion" in step
        assert "the figures and the interpretation lenses only" in step

    def test_a_verdict_without_the_mark_is_said_before_the_batch(self) -> None:
        """ADR-0053 Negative: a design saved without the mark reads as not started."""
        step = _review("### Step 3b: ")
        assert "no `analysis_started_at`" in step
        assert "before the analysis" in step


class TestReviewSendsAMissingCriterionToTheDesign:
    """ADR-0053 4: an approval without a criterion is refused and leaves no batch."""

    def test_step_5_says_what_the_refusal_means_and_where_to_go(self) -> None:
        step = _review("### Step 5: ")
        assert "`comparison`" in step
        assert "a confirmation, a legacy exploration or a `mixed` design" in step
        assert "no batch is recorded" in step
        assert "/analysis-design" in step


class TestRevisionFixesTheResultInTheNotebook:
    """US-4 AC 3: a comment on the result is fixed in the notebook and re-run."""

    def test_a_result_comment_has_no_design_field(self) -> None:
        phase = _revision("### Phase 3: ")
        for target in _RESULT_TARGETS:
            assert target in phase
        assert "no field of the design" in phase

    def test_it_fixes_only_the_cell_the_comment_points_at(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "`.insight/notebooks/{design_id}.py`" in phase
        assert "only the cell the comment points at" in phase

    def test_the_lines_are_copied_again_from_the_comparison(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "copied again from the `comparison`" in phase

    def test_it_re_runs_the_notebook(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "re-run" in phase and "/analysis-notebook" in phase


class TestRevisionDoesNotRewriteWhatTheAnalysisHolds:
    """US-4 AC 3, ADR-0053 3: a held item is answered without design_io update."""

    def test_it_names_the_held_items(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "`analysis_started_at`" in phase
        for held in (
            "`hypothesis_statement`",
            "`target`",
            "`comparison`",
            "`tier`",
            "`analysis_intent`",
        ):
            assert held in phase

    def test_it_does_not_try_the_update(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "do not try `design_io update`" in phase

    def test_a_legacy_exploration_may_still_become_a_confirmation(self) -> None:
        """ADR-0049 6: the one change of intent a started design still takes."""
        phase = _revision("### Phase 3: ")
        assert (
            "legacy exploration may still set `analysis_intent` to `confirmatory`"
            in phase
        )

    def test_it_offers_a_reason_or_a_derived_design(self) -> None:
        phase = _revision("### Phase 3: ")
        assert "wontfix with a reason" in phase
        assert "derive a new design" in phase and "`parent_id`" in phase


class TestReviewRebuildsTheNote:
    """US-4 AC 4: a recorded batch reaches the design note without a manual render.

    The note is a file ``tree_io render`` writes. A review that records a batch and
    stops leaves the note as it was, so the approved comments stay hidden until
    someone renders again (the trial finding G07).
    """

    _RENDER = "`tree_io render --design {design_id}`"

    def test_the_step_after_the_record_renders_the_design(self) -> None:
        assert self._RENDER in _review("### Step 6: ")

    def test_it_renders_after_the_record_and_before_the_hand_off(self) -> None:
        workflow = _review("## Workflow")
        record = workflow.index("### Step 5: Record the review batch")
        render = workflow.index(self._RENDER)
        hand_off = workflow.index("### Step 7: Hand off")
        assert record < render < hand_off

    def test_it_is_not_a_gate_and_shows_a_failure(self) -> None:
        step = _review("### Step 6: ")
        assert "not a gate: ask nothing" in step
        assert "exits non-zero, show its stderr" in step
        assert "the batch of Step 5 stays recorded" in step
