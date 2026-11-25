"""Structure tests for asking the intent first at the entry (Epic 32 US-1, ADR-0048).

The asking lives in SKILL.md prose, so these tests guard its load-bearing parts:
the intent is asked before anything else of the design, the form it picks decides
whether the analyst writes a question to explore or a hypothesis to confirm, and
`mixed` is never offered. The payloads /analysis-design shows are run against
``design_io``, so a shown payload that the creation check refuses fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insight_blueprint.models.design import AnalysisDesign, DesignForm
from skills._shared import design_io
from tests.docs._changelog import changelog_entry
from tests.skills._auto import design_beat, gate_row
from tests.skills._markdown import bold_item, section, table_row, unwrap
from tests.skills._shown import DESIGN_PIPED, run_shown_design_commands
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

EXPLORATION_FIELDS = ("exploration_question", "exploration_background")
CONFIRMATION_FIELDS = ("hypothesis_statement", "hypothesis_background")


def _design(heading: str) -> str:
    return section(_read_skill("analysis-design"), heading)


def _intent() -> str:
    return unwrap(_design("#### Intent"))


def _lens(name: str) -> str:
    step = section(_read_skill("analysis-review"), "### Step 3: ")
    return unwrap(bold_item(step, name))


class TestAnalysisDesignAsksTheIntentFirst:
    """US-1 AC 1: the intent comes first, and the form decides what is asked next."""

    def test_the_intent_is_asked_before_the_question_or_the_hypothesis(self) -> None:
        step = _design("### Step 2: ")
        first = step.index("#### Intent")
        for field in (*EXPLORATION_FIELDS, *CONFIRMATION_FIELDS):
            assert first < step.index(f"`{field}`"), field

    def test_the_question_to_the_analyst_names_both_intents(self) -> None:
        intent = _intent()
        assert "探索" in intent and "検証" in intent
        assert "`exploratory`" in intent and "`confirmatory`" in intent

    def test_an_exploration_asks_for_the_question_and_its_background(self) -> None:
        intent = _intent()
        for field in EXPLORATION_FIELDS:
            assert f"`{field}`" in intent

    def test_a_confirmation_asks_for_the_hypothesis_and_its_background(self) -> None:
        intent = _intent()
        for field in CONFIRMATION_FIELDS:
            assert f"`{field}`" in intent

    def test_mixed_is_never_offered(self) -> None:
        row = table_row(_design("### Step 2: "), "`analysis_intent`")
        assert all("mixed" not in cell for cell in row[1:])
        assert "Never offer `mixed`" in _intent()

    def test_a_drafted_intent_is_still_asked(self) -> None:
        """The Brief's intent and the default are drafts, never a silent answer."""
        intent = _intent()
        assert "Framing Brief" in intent and "still ask" in intent

    def test_the_field_table_marks_each_form_s_fields(self) -> None:
        step = _design("### Step 2: ")
        for field in EXPLORATION_FIELDS:
            assert "exploration" in table_row(step, f"`{field}`")[1]
        for field in (*CONFIRMATION_FIELDS, "next_action"):
            assert "confirmation" in table_row(step, f"`{field}`")[1]


class TestAnalysisDesignSaysHowToChooseTheIntent:
    """US-1 AC 2: the rule for choosing is written, Yes/No questions included."""

    def test_a_confirmation_needs_a_tentative_answer_and_a_criterion_fixed_now(
        self,
    ) -> None:
        intent = _intent()
        assert "仮の答え" in intent
        assert "基準を今固定できる" in intent

    def test_a_yes_no_question_without_a_criterion_is_an_exploration(self) -> None:
        intent = _intent()
        assert "Yes/No で答えられる論点でも" in intent
        assert "探索" in intent.split("Yes/No で答えられる論点でも", 1)[1]


class TestAChangedIntentChangesItsCriterion:
    """US-1 AC 4: a changed intent rewrites the criterion with the fields of the form."""

    def test_step_3b_rewrites_the_comparison_with_the_intent(self) -> None:
        update = unwrap(_design("### Step 3b: "))
        assert "in_review" in update and "revision_requested" in update
        assert "`metrics` with it" in update
        assert "`comparison`" in update


class TestTheShownIntentChangeWorks:
    """US-1 AC 4 (integration): Step 3b's intent change makes an exploration with no criterion."""

    def _change(self) -> str:
        found = [
            m[0]
            for m in DESIGN_PIPED.finditer(_design("### Step 3b: "))
            if '"analysis_intent": "exploratory"' in m["payload"]
        ]
        assert len(found) == 1, "Step 3b shows no single change to an exploration"
        return found[0]

    def test_it_sends_the_metrics_without_a_criterion(self) -> None:
        payload = json.loads(DESIGN_PIPED.match(self._change())["payload"])
        assert "metrics" in payload
        for metric in payload["metrics"]:
            assert "no threshold" in metric["comparison"]

    def test_it_turns_a_confirmation_into_an_exploration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        insight = tmp_path / ".insight"
        (insight / "designs").mkdir(parents=True)
        design_io.create_design(
            theme_id="FP",
            title="t",
            analysis_intent="confirmatory",
            hypothesis_statement="h",
            hypothesis_background="b",
            methodology={"method": "m"},
            metrics=[
                {"target": "d", "tier": "primary", "comparison": "2.0 日以上なら支持"}
            ],
            base_dir=insight,
        )
        [changed] = run_shown_design_commands(
            self._change(), insight, monkeypatch, capsys
        )
        assert AnalysisDesign(**changed).form() is DesignForm.exploration
        assert "支持" not in changed["metrics"][0]["comparison"]


class TestAutopilotAsksTheIntentAtDesignBeatOne:
    """US-1 AC 1: design ① asks the intent first; design ② does not ask it."""

    def test_the_gate_row_of_beat_one_names_the_intent(self) -> None:
        keep = unwrap(gate_row("design ① intent")[1])
        assert "intent" in keep
        assert "question to explore" in keep and "hypothesis" in keep

    def test_the_gate_row_of_beat_two_does_not_ask_the_intent(self) -> None:
        assert "intent" not in gate_row("design ② methodology")[1]

    def test_beat_one_asks_the_intent_before_the_question_or_the_hypothesis(
        self,
    ) -> None:
        beat = design_beat("intent")
        first = beat.index("`analysis_intent`")
        for field in (*EXPLORATION_FIELDS, *CONFIRMATION_FIELDS):
            assert first < beat.index(f"`{field}`"), field
        assert "never `mixed`" in beat

    def test_beat_two_does_not_ask_the_intent(self) -> None:
        assert "analysis_intent" not in design_beat("methodology")


class TestFramingBriefDraftsByIntent:
    """US-1 AC 3: the Brief drafts a question to explore or a hypothesis, never both."""

    def _direction(self) -> str:
        return section(
            section(_read_skill("analysis-framing"), "#### 5b: "), "### 推奨方向"
        )

    def test_it_has_a_line_for_each_draft_and_no_hypothesis_direction(self) -> None:
        direction = self._direction()
        assert "- 探索の問いの案: " in direction
        assert "- 検証仮説の案: " in direction
        assert "仮説の方向性" not in direction

    def test_the_intent_offers_no_mixed(self) -> None:
        line = next(
            line for line in self._direction().splitlines() if "analysis_intent" in line
        )
        assert "mixed" not in line

    def test_the_brief_keeps_only_the_line_of_its_intent(self) -> None:
        brief = unwrap(section(_read_skill("analysis-framing"), "#### 5b: "))
        assert "`exploratory`: keep `探索の問いの案` and drop `検証仮説の案`" in brief
        assert "`confirmatory`: keep `検証仮説の案` and drop `探索の問いの案`" in brief

    def test_analysis_design_maps_each_draft_to_its_field(self) -> None:
        step = _design("### Step 1.5: ")
        assert "`exploration_question`" in table_row(step, "推奨方向.探索の問いの案")[1]
        assert "`hypothesis_statement`" in table_row(step, "推奨方向.検証仮説の案")[1]
        assert "仮説の方向性" not in step


class TestAConfirmationFixesItsCriterionInTheDesign:
    """US-1 AC 4: design ② writes the criterion in the primary metric's comparison."""

    def test_analysis_design_writes_it_in_the_primary_comparison(self) -> None:
        criterion = unwrap(_design("#### Criterion"))
        assert "`primary`" in criterion and "`comparison`" in criterion
        assert "confirm" in criterion

    def test_an_exploration_writes_no_criterion(self) -> None:
        criterion = unwrap(_design("#### Criterion"))
        assert "exploration" in criterion.split("`comparison`", 1)[1]
        assert "no threshold" in criterion

    def test_autopilot_beat_two_confirms_it(self) -> None:
        beat = design_beat("methodology")
        assert "`comparison`" in beat and "criterion" in beat
        assert "confirm" in gate_row("design ② methodology")[1]
        assert "criterion" in gate_row("design ② methodology")[1]


class TestAnalysisReviewLooksByIntent:
    """US-1 AC 5: the lenses split by intent; the decision context fits both."""

    def test_an_exploration_is_read_against_its_node_and_for_slipped_in_guesses(
        self,
    ) -> None:
        lens = _lens("exploration_question")
        assert "narrower than the question node" in lens
        assert "what is measured" in lens
        assert "guess" in lens and "criterion" in lens

    def test_a_confirmation_is_read_for_falsifiability_and_a_written_criterion(
        self,
    ) -> None:
        lens = _lens("hypothesis_statement")
        assert "falsifiable" in lens
        assert "`comparison`" in lens and "criterion" in lens

    def test_the_supported_rejected_lens_applies_to_a_confirmation_only(self) -> None:
        lens = _lens("decision_context")
        before, after = lens.split("`supported`", 1)
        assert "confirmation" in before.rsplit(".", 1)[-1]
        assert "exploration" in lens

    def test_the_review_can_target_the_exploration_fields(self) -> None:
        for field in EXPLORATION_FIELDS:
            assert field in design_io.ALLOWED_TARGET_SECTIONS


class TestShownPayloadsCreateTheirForm:
    """US-1 AC 1 (integration): the payloads of Step 3 make the two forms."""

    def test_step_3_shows_one_payload_per_form(self) -> None:
        payloads = [
            m["payload"] for m in DESIGN_PIPED.finditer(_design("### Step 3: "))
        ]
        assert len(payloads) == 2
        exploration, confirmation = payloads
        assert '"analysis_intent": "exploratory"' in exploration
        assert '"analysis_intent": "confirmatory"' in confirmation
        for field in (*CONFIRMATION_FIELDS, "next_action"):
            assert field not in exploration

    def test_each_shown_payload_is_created_in_its_form(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        insight = tmp_path / ".insight"
        (insight / "designs").mkdir(parents=True)
        created = run_shown_design_commands(
            _design("### Step 3: "), insight, monkeypatch, capsys
        )
        forms = [AnalysisDesign(**design).form() for design in created]
        assert forms == [DesignForm.exploration, DesignForm.confirmation]


class TestRqProblematizationNamesBothEnds:
    """Scope: the hand-off from a reflection names a verdict and an exploration."""

    def test_the_row_from_reflection_names_both_forms(self) -> None:
        chaining = section(_read_skill("rq-problematization"), "## Chaining")
        when = table_row(chaining, "/analysis-reflection")[2]
        assert "検証仮説" in when and "探索" in when
        assert "仮説が棄却/不確定" not in when


class TestChangelogSaysTheIntentIsAskedFirst:
    """Completion: the release notes tell the analyst what changes at the entry."""

    def test_the_entry_names_the_skills_and_the_two_forms(self) -> None:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        entry = unwrap(changelog_entry(changelog, "ask the intent first"))
        assert "`/analysis-design`" in entry and "`/analysis-auto`" in entry
        assert "`exploration_question`" in entry and "`hypothesis_statement`" in entry
        assert "`comparison`" in entry
