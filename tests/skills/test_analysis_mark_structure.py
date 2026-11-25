"""Structure tests for the analysis mark in the prose (Epic 33, Story 33.4).

``validate_update`` holds the hypothesis, the criterion and the intent of a
design whose analysis has started, and lets a judging design into ``analyzing``
only with its criterion written (ADR-0053). The prose that tells a model what it
may still change must say the same, or a skill sends a write that is refused.
"""

from __future__ import annotations

from pathlib import Path

from tests.docs._changelog import changelog_entry
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import _read_skill

REPO_ROOT = Path(__file__).resolve().parents[2]


def _design(heading: str) -> str:
    return unwrap(section(_read_skill("analysis-design"), heading))


class TestStatusFlowTellsWhatAStartedDesignKeeps:
    """US-3 AC 1, AC 2, AC 4: the Status Flow of /analysis-design."""

    def test_it_names_the_mark_and_when_it_is_written(self) -> None:
        flow = _design("### Status Flow")
        assert "`analysis_started_at`" in flow
        assert "first enters `analyzing` or a terminal status" in flow
        assert "stays when the design goes back to `in_review`" in flow

    def test_it_names_what_a_started_confirmation_keeps(self) -> None:
        flow = _design("### Status Flow")
        for held in ("`hypothesis_statement`", "`target`", "`comparison`", "`tier`"):
            assert held in flow
        assert "`analysis_intent`" in flow
        assert "derive a new design" in flow and "`parent_id`" in flow

    def test_it_names_what_is_still_edited(self) -> None:
        flow = _design("### Status Flow")
        assert "`hypothesis_background`" in flow
        assert "can still be edited" in flow

    def test_it_asks_for_the_criterion_before_analyzing(self) -> None:
        flow = _design("### Status Flow")
        assert "enters `analyzing`, `supported` or `rejected` only when" in flow
        assert "`primary` metric" in flow and "non-empty `comparison`" in flow


class TestIntentChangeFollowsTheMark:
    """US-3 AC 2: the intent changes before the analysis starts, not by status."""

    def test_step_2_gives_the_boundary(self) -> None:
        step = unwrap(section(_read_skill("analysis-design"), "### Step 2:"))
        assert "only before the analysis starts" in step

    def test_step_3b_gives_the_boundary_and_the_way_out(self) -> None:
        step = unwrap(section(_read_skill("analysis-design"), "### Step 3b:"))
        assert "only before the analysis starts" in step
        assert "`analysis_started_at`" in step
        assert "derive a new design" in step


class TestReflectionSaysTheRewriteIsRefused:
    """US-3 AC 2: Step 5 of /analysis-reflection sends a changed hypothesis to a derived design."""

    def test_step_5_says_design_io_refuses_the_rewrite(self) -> None:
        step = unwrap(section(_read_skill("analysis-reflection"), "### Step 5:"))
        assert "`design_io` refuses" in step
        assert "ADR-0053" in step
        for held in ("hypothesis", "criterion", "intent"):
            assert held in step


class TestArchitectureNamesTheChecksOfAStartedDesign:
    """US-3 AC 5: the validation library's entry tells what validate_update holds."""

    def test_the_validation_library_names_the_mark_and_the_checks(self) -> None:
        text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        entry = next(
            line
            for line in text.split("\n- ")
            if line.startswith("**Validation library")
        )
        assert "`analysis_started_at`" in entry
        assert "adr/0053-" in entry
        assert "検証仮説" in entry and "`comparison`" in entry
        assert "`analysis_started`" in entry


class TestChangelogTellsWhatIsNowRefused:
    """A write that used to pass is refused, so the notes say it and the way out."""

    def test_the_notes_name_the_refusals_and_the_derived_design(self) -> None:
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        notes = unwrap(changelog_entry(changelog, "`analysis_started_at`"))
        assert "`hypothesis_statement`" in notes
        assert "`comparison`" in notes
        assert "derive a new design" in notes
        assert "ADR-0053" in notes and "#244" in notes


class TestAVerdictNeedsItsCriterion:
    """d9 C: a hypothesis is not supported or rejected without a criterion on record."""

    def test_the_review_tells_both_ways_out_of_a_refused_verdict(self) -> None:
        step = unwrap(section(_read_skill("analysis-review"), "### Step 5:"))
        assert "`--status supported` or `--status rejected`" in step
        assert "is refused" in step and "no batch is recorded" in step
        assert "/analysis-design {design_id}" in step
        assert "`--status inconclusive`" in step

    def test_the_scope_names_the_condition_of_a_direct_verdict(self) -> None:
        scope = unwrap(section(_read_skill("analysis-review"), "## Scope"))
        assert "`supported` and `rejected` need the criterion" in scope
        assert "`inconclusive` does not" in scope

    def test_the_status_flow_names_it(self) -> None:
        flow = _design("### Status Flow")
        assert "enters `analyzing`, `supported` or `rejected` only when" in flow
        assert "`inconclusive` is open without a criterion" in flow

    def test_the_architecture_names_it(self) -> None:
        text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        entry = next(
            line
            for line in text.split("\n- ")
            if line.startswith("**Validation library")
        )
        assert "`analyzing` か `supported`・`rejected` に入る書き込み" in entry
        assert "`inconclusive` には入れる" in entry

    def test_the_changelog_names_it(self) -> None:
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        notes = unwrap(changelog_entry(changelog, "`analysis_started_at`"))
        assert (
            "a write that concludes such a design as `supported` or `rejected`" in notes
        )
        assert "close it as `inconclusive`" in notes

    def test_the_reflection_does_not_write_a_criterion_to_pass_the_refusal(
        self,
    ) -> None:
        step = unwrap(section(_read_skill("analysis-reflection"), "### Step 4:"))
        assert "is refused `supported` and `rejected`" in step
        assert "before recording `conclude`" in step
        assert "do not write a criterion now" in step
        assert "`inconclusive`" in step and "Step 5" in step
