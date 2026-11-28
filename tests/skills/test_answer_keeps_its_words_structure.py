"""Structure tests: the theme reflection keeps its words and asks before it writes.

Epic 34, Story 34.8 (US-3 AC 4). The display derives the changes of an answer from
the cites and the exact words of its statements (ADR-0056), so a statement reworded
without a change of meaning reads as "言っていることが変わった". The reflection
therefore sends a statement whose meaning stays exactly as the earlier round wrote
it. Before it writes the answers, it shows the analyst the results that an answer
below rests on and the answer above does not; the analyst decides whether the answer
rests on them, and the answer is written either way. Asking before writing keeps the
reflection to one round. The steps live in SKILL.md prose, so these tests guard the
load-bearing parts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared import tree_io
from skills._shared.tree_changes import AnswerChange, ChangeKind, UncitedBelow
from skills._shared.tree_words import CHANGE_WORDS
from tests.skills._auto import round_item
from tests.skills._markdown import table_row, unwrap
from tests.skills._reflection import reflection_section
from tests.skills.test_next_candidate_structure import _library
from tests.skills.test_theme_reflection_structure import _step

OFFER = "#### Before writing: results no answer above rests on"
NOT_YET = "まだ答えに入れていない分析結果"
DROPPED = "前は答えの根拠にしていて、今は外している分析結果"


def _drafts() -> str:
    return _step("### Step T2: ")


def _offer() -> str:
    return reflection_section(OFFER)


class TestAStatementWhoseMeaningStaysIsSentAsItWas:
    """US-3 AC 4, first half."""

    def test_the_draft_of_an_answered_node_starts_from_its_current_answer(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a node that already has an answer starts from the statements"
            r" of its current answer",
            _drafts(),
        )

    def test_a_statement_whose_meaning_stays_is_sent_character_for_character(
        self,
    ) -> None:
        kept = re.search(
            r"(?i)a statement whose meaning the new results do not change[^.]*"
            r"character for character[^.]*\.",
            _drafts(),
        )
        assert kept, "no rule keeps an unchanged statement as it was written"
        for part in ("`kind`", "`text`", "`cites`"):
            assert part in kept.group(0)

    def test_only_a_statement_the_new_results_change_is_rewritten(self) -> None:
        assert re.search(
            r"(?i)rewrite only the statements the new results change", _drafts()
        )

    def test_the_rule_names_what_the_display_shows_for_a_rewording(self) -> None:
        assert re.search(
            r"differs by one character[^.]*「言っていることが変わった」", _drafts()
        )

    def test_a_kept_statement_is_never_restyled(self) -> None:
        assert re.search(r"(?i)never restyle a number", _drafts())

    def test_a_statement_moves_to_another_kind_only_for_its_meaning_or_a_rule(
        self,
    ) -> None:
        assert re.search(
            r"(?i)move a statement to another `kind` only when its meaning changes"
            r"[^.]*or a rule",
            _drafts(),
        )

    def test_a_statement_no_new_result_bears_on_is_fixed_only_where_it_breaks_a_rule(
        self,
    ) -> None:
        fixed = re.search(
            r"(?i)a statement no new result bears on[^.]*only where it breaks a rule"
            r"[^.]*\.",
            _drafts(),
        )
        assert fixed
        assert "violation" in fixed.group(0)

    def test_a_raised_subject_revision_lets_the_answers_follow_the_new_subject(
        self,
    ) -> None:
        assert re.search(
            r"(?i)when the 主題の版 has gone up since a node's answer[^.]*rewrite",
            _drafts(),
        )

    def test_the_analyst_is_told_what_changed_each_answer(self) -> None:
        assert re.search(
            r"(?i)for a changed node, say what changed it[^.]*new result[^.]*rule",
            _step("### Step T5: "),
        )


class TestResultsNoAnswerAboveRestsOnAreAskedBeforeTheAnswersAreWritten:
    """US-3 AC 4, second half."""

    def test_the_question_is_asked_before_the_first_answer_is_sent(self) -> None:
        write = reflection_section("### Step T3: ")
        assert OFFER in write
        assert write.index(OFFER) < write.index("| tree_io answer")

    def test_the_question_is_asked_once_in_a_reflection(self) -> None:
        offer = unwrap(_offer())
        assert re.search(r"(?i)ask it once", offer)
        assert re.search(r"(?i)do not ask again", offer)

    def test_it_lists_the_results_an_answer_below_rests_on_and_the_parent_does_not(
        self,
    ) -> None:
        assert re.search(
            r"(?i)cited by the answer of a node below[^.]*not by its own draft",
            unwrap(_offer()),
        )

    def test_a_contradicting_result_is_cited_by_rule_and_never_offered(
        self,
    ) -> None:
        assert re.search(
            r"(?i)`contradicts` event[^.]*is cited[^.]*not offered", unwrap(_offer())
        )

    def test_a_result_the_draft_dropped_is_shown_apart_in_the_analysts_words(
        self,
    ) -> None:
        # The results never cited are split again, by the round that first listed
        # them (Epic 36, test_view_and_recommendation_structure).
        assert DROPPED in _offer()

    def test_the_analyst_decides_and_the_answer_is_written_either_way(self) -> None:
        offer = unwrap(_offer())
        assert re.search(r"(?i)the analyst decides", offer)
        assert re.search(r"(?i)written without them", offer)

    def test_the_skill_never_cites_a_result_the_analyst_did_not_confirm(
        self,
    ) -> None:
        assert re.search(
            r"(?i)never cite a result from below that the analyst did not confirm",
            unwrap(_offer()),
        )

    def test_a_heard_answer_is_shown_by_its_own_name(self) -> None:
        offer = _offer()
        assert "`hearing`" in offer
        assert "人に聞いた答え: {content}" in offer

    def test_the_offer_never_says_cite_event_or_node_below(self) -> None:
        # Every Japanese run of the offer is text the analyst reads.
        shown = " ".join(re.findall(r"[぀-ヿ一-鿿「」、。（）]+", _offer()))
        assert "件を根拠に入れて、答えを書いてよいですか。" in shown
        for inner in ("引用", "出来事", "下の論点"):
            assert inner not in shown

    def test_the_presentation_lists_both_kinds_the_analyst_left_out(self) -> None:
        present = reflection_section("### Step T5: ")
        assert f"── {NOT_YET} ──" in present
        assert f"── {DROPPED} ──" in present

    def test_a_chosen_result_whose_statement_was_removed_is_reported(self) -> None:
        assert re.search(
            r"(?i)a result the analyst chose[^.]*Removed statements",
            _step("### Step T5: "),
        )


class TestTheWalkStopsForTheQuestion:
    def test_the_theme_reflection_round_holds_no_rule_of_its_own(self) -> None:
        # The gate row names T3 and T7; the walk does not repeat what T3 asks.
        item = unwrap(round_item("theme reflection"))
        assert NOT_YET not in item
        assert "KEEP gates of the round" in item


CHANGES = "`tree_io changes --theme {theme_id}`"


class TestThePresentationReadsWhatChangedFromTheTree:
    """After writing, Step T5 reads the changes from the tree, not from its drafts.

    `tree_io changes` derives them as the page does (ADR-0056), so what the analyst
    hears in the reflection and what the page shows cannot drift apart.
    """

    def test_the_presentation_runs_the_changes_command(self) -> None:
        assert CHANGES in _step("### Step T5: ")

    def test_it_says_the_lists_come_from_that_output_not_from_the_drafts(
        self,
    ) -> None:
        assert re.search(
            r"(?i)from (the|its) output of `tree_io changes`[^.]*never from the drafts",
            _step("### Step T5: "),
        )

    def test_every_key_it_names_is_in_the_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)
        output = tree_io.changes("LIB", base_dir=insight)
        present = _step("### Step T5: ")
        for key in ("answer_changes", "uncited_below"):
            assert f"`{key}`" in present
            assert key in output
        assert "`evidence`" in present
        assert "evidence" in AnswerChange.model_fields
        assert "`last_cited_round`" in present
        assert "last_cited_round" in UncitedBelow.model_fields

    def test_each_kind_of_change_is_said_as_the_page_says_it(self) -> None:
        present = _step("### Step T5: ")
        for kind in (k for k in ChangeKind if k is not ChangeKind.unchanged):
            assert f"`{kind.value}` {CHANGE_WORDS[kind][0]}" in present

    def test_the_two_headings_split_on_whether_the_node_cited_it_before(
        self,
    ) -> None:
        present = _step("### Step T5: ")
        assert re.search(rf"`last_cited_round` is `null`[^.]*{NOT_YET}", present)
        assert re.search(rf"otherwise[^.]*{DROPPED}", present)

    def test_the_reference_lists_the_changes_command(self) -> None:
        reference = reflection_section("## tree_io / tree_check Reference")
        assert table_row(reference, "`tree_io changes --theme T`")[1]
