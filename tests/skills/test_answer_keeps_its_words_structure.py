"""Structure tests: the theme reflection keeps its words and shows what no answer rests on.

Epic 34, Story 34.8 (US-3 AC 4). The display derives the changes of an answer from
the cites and the exact words of its statements (ADR-0056), so a statement reworded
without a change of meaning reads as "言っていることが変わった". The reflection
therefore sends a statement whose meaning stays exactly as the earlier round wrote
it. Before the decision it also shows the analyst the results that an answer above
them does not rest on yet; the analyst decides whether the answer rests on them,
and the answer is written either way. The steps live in SKILL.md prose, so these
tests guard the load-bearing parts.
"""

from __future__ import annotations

import re

from tests.skills._auto import round_item
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import _read_skill

NOT_YET = "まだ答えに入れていない分析結果"
DROPPED = "前は答えの根拠にしていて、今は外している分析結果"


def _skill() -> str:
    return _read_skill("analysis-reflection")


def _step(heading: str) -> str:
    return unwrap(section(_skill(), heading))


def _offer() -> str:
    return section(_skill(), "#### Results no answer above rests on")


class TestAStatementWhoseMeaningStaysIsSentAsItWas:
    """US-3 AC 4, first half."""

    def test_the_draft_of_an_answered_node_starts_from_its_current_answer(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a node that already has an answer[^.]*starts? from the statements"
            r" of its current answer",
            _step("### Step T2: "),
        )

    def test_a_statement_whose_meaning_stays_is_sent_character_for_character(
        self,
    ) -> None:
        step = _step("### Step T2: ")
        kept = re.search(
            r"(?i)a statement whose meaning the new results do not change[^.]*"
            r"character for character[^.]*\.",
            step,
        )
        assert kept, "no rule keeps an unchanged statement as it was written"
        for part in ("`kind`", "`text`", "`cites`"):
            assert part in kept.group(0)

    def test_only_a_statement_the_new_results_change_is_rewritten(self) -> None:
        assert re.search(
            r"(?i)rewrite only the statements? (that )?the new results change",
            _step("### Step T2: "),
        )

    def test_a_rewording_is_named_as_a_change_the_reader_sees(self) -> None:
        # The reason must name what the display does, or the rule reads as style.
        step = _step("### Step T2: ")
        assert "言っていることが変わった" in step

    def test_a_number_or_a_kind_is_not_restyled(self) -> None:
        step = _step("### Step T2: ")
        assert re.search(r"(?i)never restyle a number", step)
        assert re.search(r"(?i)move a statement to another `kind` only when", step)

    def test_a_statement_no_new_result_bears_on_is_fixed_only_where_it_breaks_a_rule(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a statement no new result bears on[^.]*only where it breaks a rule",
            _step("### Step T2: "),
        )

    def test_the_analyst_is_told_what_changed_each_answer(self) -> None:
        present = _step("### Step T5: ")
        assert re.search(
            r"(?i)for a changed node, (also )?say what changed it[^.]*new result"
            r"[^.]*rule",
            present,
        )

    def test_an_answer_with_no_change_is_left_to_unchanged(self) -> None:
        assert re.search(
            r"(?i)when no statement of a node changes[^.]*send (it|them) as (it|they)"
            r" (was|were)",
            _step("### Step T2: "),
        )


class TestResultsNoAnswerAboveRestsOnAreShownBeforeTheDecision:
    """US-3 AC 4, second half."""

    def test_the_offer_comes_before_the_answers_are_written(self) -> None:
        skill = _skill()
        offer = skill.index("#### Results no answer above rests on")
        assert skill.index("### Step T2: ") < offer < skill.index("### Step T3: ")

    def test_nothing_is_written_before_the_analyst_has_answered(self) -> None:
        write = _step("### Step T3: ")
        assert re.search(
            r"(?i)ask the question of \"Results no answer above rests on\"[^.]*first"
            r"[^.]*wait for the analyst's answer\. Send nothing before it",
            write,
        )

    def test_it_lists_the_results_an_answer_below_rests_on_and_the_parent_does_not(
        self,
    ) -> None:
        offer = unwrap(_offer())
        assert re.search(
            r"(?i)cited by the answer of a node below[^.]*(but )?not by (the|its)"
            r" (own )?(draft|answer)",
            offer,
        )

    def test_the_two_kinds_are_shown_apart_in_the_analysts_words(self) -> None:
        offer = _offer()
        assert NOT_YET in offer
        assert DROPPED in offer

    def test_the_analyst_decides_and_the_answer_is_written_either_way(self) -> None:
        offer = unwrap(_offer())
        assert re.search(r"(?i)the analyst decides", offer)
        assert re.search(r"(?i)written without (it|them)", offer)

    def test_the_skill_never_adds_a_result_the_analyst_did_not_choose(
        self,
    ) -> None:
        assert re.search(
            r"(?i)never (add|cite) a result the analyst did not choose",
            unwrap(_offer()),
        )

    def test_a_heard_answer_is_called_by_its_own_name(self) -> None:
        offer = _offer()
        assert "`hearing`" in offer
        assert "人に聞いた答え" in offer

    def test_the_question_to_the_analyst_uses_no_inner_word(self) -> None:
        # Every Japanese run of the offer is text the analyst reads.
        shown = " ".join(re.findall(r"[぀-ヿ一-鿿「」、。（）]+", _offer()))
        assert "根拠にする分析結果はありますか" in shown
        for inner in ("引用", "出来事", "下の論点"):
            assert inner not in shown

    def test_the_presentation_lists_what_the_analyst_left_out(self) -> None:
        present = section(_skill(), "### Step T5: ")
        assert f"── {NOT_YET} ──" in present


class TestTheWalkStopsForTheOffer:
    def test_the_auto_walk_names_the_question_before_the_answers(self) -> None:
        item = unwrap(round_item("theme reflection"))
        assert NOT_YET in item
        assert re.search(r"(?i)before (it writes|writing) the answers", item)
