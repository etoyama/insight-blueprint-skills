"""Structure tests for the decision context in the skills' prose (Epic 12 US-2, ADR-0014).

The asking and the reviewing live in SKILL.md prose, not Python, so these tests guard
the load-bearing parts: /analysis-design asks for the decision context together with the
hypothesis and lets the analyst skip it, the guided autopilot confirms it at the
hypothesis beat, and /analysis-review reads it against the hypothesis.
"""

from __future__ import annotations

import re

from skills._shared import design_io
from tests.skills._markdown import section, table_row
from tests.skills.test_skill_structure import _read_skill


class TestAnalysisDesignAsksForTheDecisionContext:
    """US-2 AC 2: asked at the hypothesis step; the analyst may go on without it."""

    def test_field_table_lists_it_as_optional(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 2: ")
        row = table_row(step, "`decision_context`")
        assert row[1] == "No"
        assert "decision_maker" in row[3] and "decision" in row[3]

    def test_it_is_asked_together_with_the_hypothesis(self) -> None:
        asking = section(_read_skill("analysis-design"), "#### Decision context")
        assert "hypothesis_statement" in asking
        assert "decision_maker" in asking and "`decision`" in asking

    def test_the_analyst_may_skip_it(self) -> None:
        asking = section(_read_skill("analysis-design"), "#### Decision context")
        assert "skip" in asking.lower()
        # A skipped context is left out, never written half-filled or as a placeholder.
        assert "omit" in asking.lower()

    def test_create_payload_shows_the_field(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 3: ")
        assert '"decision_context": {"decision_maker":' in step

    def test_design_io_reference_lists_the_field(self) -> None:
        reference = section(_read_skill("analysis-design"), "## design_io Reference")
        assert "decision_context?" in table_row(reference, "`create`")[2]

    def test_typed_field_reference_says_both_sides_are_required(self) -> None:
        reference = section(
            _read_skill("analysis-design"), "## Typed Field Values Reference"
        )
        for field in ("decision_context.decision_maker", "decision_context.decision"):
            assert "non-empty" in table_row(reference, f"`{field}`")[2]

    def test_schema_error_is_listed(self) -> None:
        errors = section(_read_skill("analysis-design"), "## Error Handling")
        assert "decision_context" in errors


class TestAutopilotConfirmsItAtTheHypothesisBeat:
    """US-2 AC 2: the guided autopilot shows it at design beat 1, not as a new gate."""

    def test_gate_policy_row_names_the_decision_context(self) -> None:
        row = table_row(_read_skill("analysis-auto"), "design ① intent")
        assert "decision context" in row[1]

    def test_hypothesis_beat_presents_the_field_and_allows_skipping(self) -> None:
        text = _read_skill("analysis-auto")
        beat = re.search(
            r"^\s+1\. \*\*intent\*\*.*?(?=^\s+2\. \*\*)", text, re.M | re.S
        )
        assert beat, "intent beat not found"
        assert "decision_context" in beat.group(0)
        assert "skip" in beat.group(0).lower()

    def test_there_are_still_four_design_beats(self) -> None:
        assert "four ordered confirmation beats" in _read_skill("analysis-auto")


class TestAnalysisReviewReadsTheDecisionContext:
    """US-2 AC 3: the review reads it and checks that it fits the hypothesis."""

    def test_allowed_sections_match_design_io(self) -> None:
        step = section(_read_skill("analysis-review"), "### Step 3: ")
        listed = step[step.index("allowed set:") : step.index("Suggested lenses")]
        assert set(re.findall(r"`(\w+)`", listed)) == design_io.ALLOWED_TARGET_SECTIONS

    def test_has_a_lens_that_checks_it_against_the_hypothesis(self) -> None:
        step = section(_read_skill("analysis-review"), "### Step 3: ")
        lens = re.search(
            r"^- \*\*decision_context\*\*.*?(?=^- \*\*|^\S)", step, re.M | re.S
        )
        assert lens, "decision_context lens not found"
        assert "hypothesis" in lens.group(0)

    def test_an_absent_decision_context_is_not_a_finding(self) -> None:
        step = section(_read_skill("analysis-review"), "### Step 3: ")
        lens = re.search(
            r"^- \*\*decision_context\*\*.*?(?=^- \*\*|^\S)", step, re.M | re.S
        )
        assert lens, "decision_context lens not found"
        assert "optional" in lens.group(0)
