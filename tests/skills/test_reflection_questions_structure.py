"""Structure tests for the questions of a design reflection (Epic 32 US-6, #211).

The reflection on one design asks three questions in order. The analyst asked back
twice when they were numbered Q1-Q3: what the second covers, and how the third
differs from the first. These tests guard the parts that answer that before the
analyst has to ask: each heading is the question, the scope and the meaning of the
verdict come first, and an exploration is never asked for a verdict. The transitions
the end of each form shows are run against ``design_io``, so a shown target that the
form refuses fails here.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from skills._shared import design_io
from tests.docs._changelog import changelog_entry
from tests.skills._auto import gate_row, round_item
from tests.skills._markdown import bold_item, section, table_row, table_rows, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

WHAT_THE_RESULTS_SAY = "#### 結果から何が言えるか"
OPEN_QUESTIONS = "#### まだ答えの出ていない問いで、判定は変わるか"
HOW_TO_END = "#### この分析設計をどう終えるか"


def _skill() -> str:
    return _read_skill("analysis-reflection")


def _step(heading: str) -> str:
    return section(_skill(), heading)


def _beat(heading: str) -> str:
    return unwrap(section(_skill(), heading))


def _part(beat: str, label: str) -> str:
    """The bullet ``- **label**`` of a step or a beat."""
    return unwrap(bold_item(section(_skill(), beat), label))


class TestTheHeadingsAreTheQuestions:
    """US-6 AC 1: the three beats are headed by the question they ask."""

    def test_step_3_has_the_three_beats_in_order(self) -> None:
        step = _step("### Step 3:")
        at = [step.find(h) for h in (WHAT_THE_RESULTS_SAY, OPEN_QUESTIONS, HOW_TO_END)]
        assert -1 not in at, at
        assert at == sorted(at)

    def test_an_exploration_reads_the_second_heading_with_answer(self) -> None:
        assert "まだ答えの出ていない問いで、答えは変わるか" in unwrap(
            _step("### Step 3:")
        )

    def test_no_beat_is_numbered_q1_to_q3(self) -> None:
        for heading in ("### Step 2:", "### Step 3:", "### Step 4:", "### Step 5:"):
            assert not re.search(r"\bQ[1-3]\b", _step(heading)), heading


class TestAConfirmationShowsWhatEachAnswerChanges:
    """US-6 AC 2: the criterion, the scope and the usual end come before each question."""

    def test_the_first_beat_shows_the_criterion_of_the_primary_metric_first(
        self,
    ) -> None:
        part = _part(WHAT_THE_RESULTS_SAY, "Confirmation")
        assert "`comparison`" in part and "`tier: primary`" in part
        assert part.find("`comparison`") < part.find("「")

    def test_a_confirmation_without_a_criterion_is_not_given_one(self) -> None:
        part = _part(WHAT_THE_RESULTS_SAY, "Confirmation")
        assert "分析の前に固定した基準は無い" in part
        assert "Never write a criterion yourself" in part

    def test_an_exploration_is_shown_no_verdict_for_an_open_question(self) -> None:
        beat = _beat(OPEN_QUESTIONS)
        assert "For an exploration, write 答え for 判定" in beat
        assert "never `supported`, `rejected` or `inconclusive`" in beat

    def test_the_second_beat_says_its_scope_before_it_asks(self) -> None:
        beat = _beat(OPEN_QUESTIONS)
        assert "`question` events of this design's journal" in beat
        assert "`resolves`" in beat
        assert "not the questions of the theme or of the root question" in beat

    def test_the_second_beat_says_what_the_verdict_is(self) -> None:
        beat = _beat(OPEN_QUESTIONS)
        assert "判定" in beat
        assert "`supported`, `rejected` or `inconclusive`" in beat

    def test_each_open_question_shows_how_its_answer_changes_the_verdict(
        self,
    ) -> None:
        beat = _beat(OPEN_QUESTIONS)
        assert "答えが" in beat and "なら判定は" in beat
        assert "For each open question" in beat

    def test_the_third_beat_first_says_it_usually_follows_the_first(self) -> None:
        beat = _beat(HOW_TO_END)
        said = "ふつうは1つ目の答えのとおりに終える。変わるのは、2つ目で『ある』と答えたときだけ"
        assert said in beat
        assert beat.find(said) < beat.find("Confirmation")


class TestAnExplorationIsNotAskedForAVerdict:
    """US-6 AC 3: an exploration answers its question and ends as `explored`."""

    def test_the_first_beat_asks_for_the_answer_to_the_question(self) -> None:
        part = _part(WHAT_THE_RESULTS_SAY, "Exploration")
        assert "{exploration_question}" in part
        assert "no verdict" in part

    def test_an_answer_with_no_measured_value_is_asked_again_with_the_values(
        self,
    ) -> None:
        """Trial F12: 「特になし」 became the conclusion, and the values stayed in the evidence."""
        part = _part(WHAT_THE_RESULTS_SAY, "Exploration")
        assert "states no measured value" in part
        assert "`evidence` events" in part
        assert part.find("states no measured value") < part.find("`evidence` events")

    def test_the_answer_asked_again_is_kept_in_the_analysts_words(self) -> None:
        part = _part(WHAT_THE_RESULTS_SAY, "Exploration")
        assert "Keep the analyst's words" in part

    def test_the_third_beat_offers_only_to_end_or_to_look_further(self) -> None:
        part = _part(HOW_TO_END, "Exploration")
        options = re.findall(r"「([^」]+)」", part)
        assert options == ["探索を終える", "調べ足す"]
        for verdict in ("supported", "rejected", "inconclusive"):
            assert verdict not in part

    def test_ending_an_exploration_moves_it_to_explored(self) -> None:
        assert "`design_io transition --id {design_id} --target explored`" in _part(
            "### Step 4:", "Exploration"
        )


class TestAnExplorationCanLeaveATentativeAnswer:
    """US-6 AC 4: the next answer to confirm is kept, and the analyst may skip it."""

    def test_the_end_asks_for_a_tentative_answer_and_can_be_skipped(self) -> None:
        part = _part("### Step 4:", "Exploration")
        assert "次に確かめたい仮の答え" in part
        assert "飛ばしてよい" in part

    def test_the_tentative_answer_is_a_hypothesize_event(self) -> None:
        assert "`hypothesize`" in _part("### Step 4:", "Exploration")

    def test_a_confirmation_is_derived_through_analysis_design(self) -> None:
        part = _part("### Step 4:", "Exploration")
        assert "/analysis-design" in part
        assert "`parent_id`" in part

    def test_the_derived_confirmation_is_linked_and_recorded_like_step_5(
        self,
    ) -> None:
        part = _part("### Step 4:", "Exploration")
        assert "Step 5 items 3 and 4" in part
        assert "`branch`" in part

    def test_the_tentative_answer_is_kept_before_the_design_ends(self) -> None:
        part = _part("### Step 4:", "Exploration")
        assert part.find("`hypothesize`") < part.find("--target explored")


class TestAnAnswerThatChangesNoVerdictGoesToTheTheme:
    """US-6 AC 5: an open question that changes no verdict goes to the theme reflection.

    The beat says only that the question is kept and where it is written. The analyst
    has the question in front of them, so the beat gives it no name of its own: a name
    such as 注意すべきこと would clash with the two kinds it is written as (Epic 34,
    the human's choice in the PM session, 2026-11-26).
    """

    def test_such_a_question_is_kept_and_written_in_the_theme_reflection(
        self,
    ) -> None:
        beat = _beat(OPEN_QUESTIONS)
        assert "/analysis-reflection {theme_id}" in beat
        assert "この問いは捨てない" in beat
        assert "まだ決められないこと か 注意すべきこと として書く" in beat

    def test_the_question_gets_no_other_name(self) -> None:
        beat = _beat(OPEN_QUESTIONS)
        for name in ("主題への答えで注意すべきこと", "残る問い", "留保"):
            assert name not in beat
        assert not re.search(r"(?i)it is a (caution|reservation)", beat)

    def test_no_text_for_the_analyst_uses_hibiku(self) -> None:
        assert "響" not in _skill()
        assert "響" not in _read_skill("analysis-auto")


class TestALegacyExplorationReadsItsUndirectedEvidence:
    """Deferred (32.4): a legacy exploration chooses a verdict from evidence with no direction."""

    def test_step_2_lists_the_evidence_without_a_direction(self) -> None:
        assert "Without a direction" in _step("### Step 2:")

    def test_the_analyst_reads_it_against_the_hypothesis(self) -> None:
        part = _part(WHAT_THE_RESULTS_SAY, "Legacy exploration")
        assert "`direction`" in part
        assert "Never give it a direction yourself" in part
        assert "分析の前に固定した基準は無い" in part


class TestARefinementIsADerivedDesign:
    """d12 B (2026-11-25): a corrected hypothesis is a new design, not a rewrite."""

    def test_step_5_derives_a_design_through_analysis_design(self) -> None:
        step = unwrap(_step("### Step 5:"))
        assert "/analysis-design" in step and "`parent_id`" in step
        assert "`tree_io link-derived" in step
        assert "`branch`" in step
        assert "`forked_from: {design_id}`" in step

    def test_step_5_never_rewrites_the_hypothesis(self) -> None:
        step = unwrap(_step("### Step 5:"))
        assert "Never rewrite" in step and "ADR-0053" in step
        assert "design_io update" not in step

    def test_the_reference_has_no_update_command(self) -> None:
        reference = section(_skill(), "## design_io Reference")
        assert "`update" not in reference


def _make(
    insight: Path,
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Create a design from *payload* and move it to `analyzing`; return its id."""
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    capsys.readouterr()
    assert design_io._main(["create", "--base-dir", str(insight)]) == 0
    design_id = json.loads(capsys.readouterr().out)["id"]
    args = ["transition", "--id", design_id, "--target", "analyzing"]
    assert design_io._main([*args, "--base-dir", str(insight)]) == 0
    return design_id


EXPLORATION = (
    '{"title": "t", "analysis_intent": "exploratory",'
    ' "exploration_question": "q", "exploration_background": "b",'
    ' "methodology": {"method": "m"}}'
)
CONFIRMATION = (
    '{"title": "t", "analysis_intent": "confirmatory",'
    ' "hypothesis_statement": "h", "hypothesis_background": "b",'
    ' "metrics": [{"target": "m", "tier": "primary", "comparison": "c"}],'
    ' "methodology": {"method": "m"}}'
)


def _shown_targets(part: str) -> list[str]:
    return re.findall(r"design_io transition --id \{design_id\} --target (\w+)", part)


class TestTheShownTransitionsRun:
    """Integration: each form ends at the targets its part of Step 4 shows."""

    def test_an_exploration_reaches_explored_and_no_verdict(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        targets = _shown_targets(_part("### Step 4:", "Exploration"))
        assert targets == ["explored"]
        insight = tmp_path / ".insight"
        design_id = _make(insight, EXPLORATION, monkeypatch, capsys)
        for verdict in ("supported", "rejected", "inconclusive"):
            args = ["transition", "--id", design_id, "--target", verdict]
            with pytest.raises(ValueError, match="Valid targets: explored"):
                design_io._main([*args, "--base-dir", str(insight)])
        args = ["transition", "--id", design_id, "--target", targets[0]]
        assert design_io._main([*args, "--base-dir", str(insight)]) == 0

    @pytest.mark.parametrize("verdict", ["supported", "rejected", "inconclusive"])
    def test_a_confirmation_reaches_each_shown_verdict(
        self,
        verdict: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        targets = _shown_targets(_part("### Step 4:", "Confirmation"))
        assert targets == ["supported", "rejected", "inconclusive"]
        insight = tmp_path / ".insight"
        design_id = _make(insight, CONFIRMATION, monkeypatch, capsys)
        args = ["transition", "--id", design_id, "--target", verdict]
        assert design_io._main([*args, "--base-dir", str(insight)]) == 0


class TestAutoPausesAtTheEndOfEachForm:
    """US-6 AC 3: /analysis-auto pauses where the reflection asks, by form."""

    def test_the_gate_row_names_both_ends(self) -> None:
        keep = gate_row("reflection")[1]
        assert "この分析設計をどう終えるか" in keep
        assert "`explored`" in keep and "never a verdict" in keep

    def test_the_round_item_pauses_at_the_third_question(self) -> None:
        item = round_item("reflection")
        assert "この分析設計をどう終えるか" in item
        assert "conclude/refine/branch" not in item


class TestFramingSpeaksOfAQuestionOrAHypothesis:
    """Deferred (32.3): framing's description and its row from reflection name both forms."""

    def test_the_description_names_both_forms(self) -> None:
        head = _read_skill("analysis-framing").split("---", 2)[1]
        assert "question to explore" in head and "hypothesis to confirm" in head

    def test_the_row_from_reflection_names_both_forms(self) -> None:
        chaining = section(_read_skill("analysis-framing"), "## Chaining")
        when = table_row(chaining, "/analysis-reflection")[2]
        assert "探索の問い" in when and "検証仮説" in when
        assert "新仮説" not in when

    def test_reflection_rows_name_both_forms(self) -> None:
        chaining = section(_skill(), "## Chaining")
        rows = [
            cells
            for cells in table_rows(chaining)
            if cells[0] == "/analysis-reflection"
        ]
        assert len(rows) >= 5, "the Chaining table lost the rows from reflection"
        for cells in rows:
            assert "New hypothesis" not in cells[2]
            assert "Derived hypothesis" not in cells[2]


class TestChangelogSaysTheQuestionsChanged:
    """Completion: the release notes say what the analyst sees at the reflection."""

    def test_the_entry_names_the_headings_and_the_derived_design(self) -> None:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        entry = unwrap(changelog_entry(changelog, "`/analysis-reflection` asks"))
        assert "結果から何が言えるか" in entry
        assert "`explored`" in entry
        assert "derived design" in entry

    def test_the_entry_says_the_review_comes_before_the_conclusion(self) -> None:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        phrase = "asks whether to have the result reviewed before it records `conclude`"
        assert "#217" in unwrap(changelog_entry(changelog, phrase))

    def test_the_entry_says_an_answer_without_a_value_is_asked_again(self) -> None:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        phrase = "shows the measured values and asks again"
        assert "#217" in unwrap(changelog_entry(changelog, phrase))
