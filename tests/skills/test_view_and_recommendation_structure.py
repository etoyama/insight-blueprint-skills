"""Structure tests: the theme reflection asks the view first and recommends the evidence.

Epic 36, Story 36.3 (US-1 AC 1 and AC 4, US-2 AC 2 to AC 4). Before the answer of the
subject is written, the analyst is asked how the results of the round bear on it, in
their own words (ADR-0068). The results the answers above do not rest on are then
split by the code into the ones new to the list and the ones shown in an earlier
round; the agent recommends from the new ones with a reason, and the earlier ones
are a count (ADR-0069). An answer rests on a result from below only after the analyst
confirmed it. The steps live in prose, so these tests guard the load-bearing parts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from insight_blueprint.models.tree import AnswerStatement
from skills._shared import tree_io
from skills._shared.tree_changes import UncitedBelow
from tests import _wide_tree
from tests.skills._auto import gate_row, round_item
from tests.skills._markdown import table_row, unwrap
from tests.skills._reflection import reflection_section

VIEW = "#### Before writing: the analyst's view of the subject"
OFFER = "#### Before writing: results no answer above rests on"
SEND = "#### Send the answers"

RECOMMENDED = "根拠に入れることを勧める分析結果"
NOT_RECOMMENDED = "勧めなかった、この回の分析結果"
SHOWN_BEFORE = "前の回までに見せて、答えに入れなかった分析結果"
YOUR_VIEW = "あなたの見立て"
WITH_ANSWERS = "tree_io changes --theme {theme_id} --with-answers < {file}"


def _write() -> str:
    return reflection_section("### Step T3: ")


def _view() -> str:
    return reflection_section(VIEW)


def _offer() -> str:
    return reflection_section(OFFER)


def _send() -> str:
    return reflection_section(SEND)


def _drafts() -> str:
    return unwrap(reflection_section("### Step T2: "))


def _present() -> str:
    return reflection_section("### Step T5: ")


def _shown(prose: str) -> str:
    """Every Japanese run of a section: the text the analyst reads."""
    return " ".join(re.findall(r"[぀-ヿ一-鿿「」、。（）・]+", prose))


class TestTheViewOfTheSubjectIsAskedBeforeItsAnswerIsWritten:
    """US-1 AC 1."""

    def test_the_view_is_asked_before_the_results_and_before_the_answers(self) -> None:
        write = _write()
        assert write.index(VIEW) < write.index(OFFER) < write.index(SEND)

    def test_it_is_asked_about_the_root_only(self) -> None:
        view = unwrap(_view())
        assert re.search(r"(?i)only about the root", view)
        assert re.search(r"(?i)never ask it about another node", view)

    def test_the_question_asks_how_the_results_bear_on_the_subject(self) -> None:
        shown = _shown(_view())
        assert "この回の結果は、主題の答えにどう効きますか。" in shown
        assert "いまの答えを支える・いまの答えを変える・まだ言えない" in shown
        assert "あなたの言葉で書いてください。" in shown

    def test_the_analyst_may_start_from_the_draft_of_the_agent(self) -> None:
        assert "見立てを書かずに、エージェントの下書きから始めることもできます。" in (
            _shown(_view())
        )
        assert re.search(
            r"(?i)when the analyst starts from the draft[^.]*no statement carries"
            r" `analyst_view`",
            unwrap(_view()),
        )

    def test_the_question_shows_the_conclusions_and_the_current_answer(self) -> None:
        view = _view()
        assert "あなたの結論: 「{content}」" in view
        assert "`conclude`" in view
        assert "いまの答え（{round}回目の振り返り）" in view

    def test_a_subject_without_an_answer_is_asked_what_can_be_said(self) -> None:
        assert re.search(
            r"(?i)when the root has no answer yet[^.]*leave out", unwrap(_view())
        )
        assert "この回の結果から、主題についていま何が言えますか。" in _shown(_view())

    def test_it_is_asked_once_and_only_when_a_result_is_new(self) -> None:
        view = unwrap(_view())
        assert re.search(r"(?i)ask it once", view)
        assert re.search(
            r"(?i)when no journal event[^.]*since the current answer of the root"
            r"[^.]*do not ask",
            view,
        )

    def test_the_question_never_says_cite_event_or_node_below(self) -> None:
        shown = _shown(_view())
        for inner in ("引用", "出来事", "下の論点", "分析者の見立て"):
            assert inner not in shown

    def test_the_view_becomes_one_statement_in_the_analysts_words(self) -> None:
        view = unwrap(_view())
        kept = re.search(
            r"(?i)the view becomes one statement[^.]*exactly as the analyst wrote it"
            r"[^.]*\.",
            view,
        )
        assert kept
        assert '`"analyst_view": true`' in kept.group(0)
        assert re.search(r"(?i)never reword, shorten, split or merge it", view)

    def test_the_statement_it_shows_is_one_the_tree_accepts(self) -> None:
        shown = re.search(r'\{"kind": [^\n]*"analyst_view": true\}', _view())
        assert shown, "no statement with the mark is shown"
        statement = AnswerStatement.model_validate(json.loads(shown.group(0)))
        assert statement.analyst_view is True

    def test_the_agent_places_the_view_and_the_analyst_confirms_the_place(
        self,
    ) -> None:
        assert (
            "置く所: {これまでわかっていること | 注意すべきこと | まだ決められないこと}"
            in (_offer())
        )


class TestTheAgentNeverRewordsTheAnalystsView:
    """US-1 AC 4."""

    def test_a_later_round_sends_it_character_for_character(self) -> None:
        kept = re.search(
            r"(?i)a statement with `analyst_view` is sent character for character"
            r"[^.]*\.",
            _drafts(),
        )
        assert kept
        assert "every later round" in kept.group(0)

    def test_no_rule_of_the_draft_lets_the_agent_change_it(self) -> None:
        assert re.search(
            r"(?i)where a rule of this step, a new result or a new 主題 would change"
            r" it, ask the analyst",
            _drafts(),
        )
        assert re.search(
            r"(?i)changes only when the analyst says how it now reads", _drafts()
        )

    def test_a_violation_of_it_is_asked_and_never_rewritten(self) -> None:
        send = unwrap(_send())
        asked = re.search(
            r"(?i)a statement with `analyst_view` that violates is never rewritten"
            r" and never removed by you[^.]*\.",
            send,
        )
        assert asked
        assert re.search(r"(?i)show the analyst the violation[^.]*ask", send)

    def test_the_presentation_marks_the_statement_as_the_analysts(self) -> None:
        assert f"[これまでわかっていること]（{YOUR_VIEW}）{{text}}" in _present()
        assert re.search(r"`analyst_view`[^.]*（あなたの見立て）", unwrap(_present()))


class TestTheResultsAreSplitByTheCodeAndRecommendedByTheAgent:
    """US-2 AC 2."""

    def test_the_list_is_read_from_the_command_and_never_made_by_hand(self) -> None:
        offer = _offer()
        assert WITH_ANSWERS in offer
        assert re.search(r"(?i)never build the list by hand", unwrap(offer))

    def test_the_command_it_shows_splits_the_wide_tree(self, tmp_path: Path) -> None:
        # The keys the step names are the ones the command returns.
        base = tmp_path / ".insight"
        _wide_tree.build(base)
        _wide_tree.add_round_2_events(base)
        listed = tree_io.changes(
            _wide_tree.THEME, answers=_wide_tree.round_2_drafts(base), base_dir=base
        )["uncited_below"][_wide_tree.ROOT]
        offer = _offer()
        for key in ("uncited_below", "shown_before", "last_cited_round"):
            assert f"`{key}`" in offer
        assert "shown_before" in UncitedBelow.model_fields
        by_content = [e for e in listed if not e["shown_before"]]
        assert len(by_content) == _wide_tree.NEW_IN_ROUND_2
        assert len(listed) - len(by_content) == _wide_tree.LISTED_BEFORE

    def test_the_drafts_above_do_not_cite_a_result_from_below_yet(self) -> None:
        assert re.search(
            r"(?i)the draft of the root and of a node with nodes below it does not"
            r" yet cite[^.]*\.",
            _drafts(),
        )

    def test_the_statements_of_the_output_are_never_shown(self) -> None:
        assert re.search(
            r"(?i)`statements`[^.]*not checked[^.]*never show", unwrap(_offer())
        )

    def test_a_new_result_is_recommended_or_not_with_a_reason(self) -> None:
        offer = unwrap(_offer())
        assert re.search(
            r"(?i)`shown_before` is `false`[^.]*recommend[^.]*or not", offer
        )
        assert re.search(r"(?i)one line[^.]*reason", offer)
        for words in (RECOMMENDED, NOT_RECOMMENDED):
            assert words in _offer()

    def test_the_reason_is_said_and_never_recorded(self) -> None:
        assert re.search(
            r"(?i)the reason is said here only[^.]*never write it into a statement",
            unwrap(_offer()),
        )

    def test_a_result_shown_before_is_a_count(self) -> None:
        offer = _offer()
        assert re.search(
            r"(?i)`shown_before` is `true`[^.]*count[^.]*not by its content",
            unwrap(offer),
        )
        assert f"{SHOWN_BEFORE}: {{N}}件（言ってもらえれば全部出す）" in offer

    def test_the_analyst_can_have_them_all_listed(self) -> None:
        assert re.search(
            r"(?i)when the analyst asks for them, list every one by its content",
            unwrap(_offer()),
        )

    def test_a_result_is_written_out_once_and_named_by_its_number_after(
        self,
    ) -> None:
        assert re.search(
            r"(?i)number[^.]*once[^.]*block of another node names it by that number",
            unwrap(_offer()),
        )

    def test_the_parts_of_the_question_are_listed_in_order(self) -> None:
        offer = _offer()
        parts = re.findall(r"^(\d)\. \*\*([^*]+)\*\*", offer, re.MULTILINE)
        assert [name for _, name in parts] == [
            "The view",
            "Recommended",
            "Not recommended",
            "Shown before",
            "Dropped",
            "Overstated",
            "The question",
        ]

    def test_the_question_asks_to_write_with_the_recommended_results(self) -> None:
        shown = _shown(_offer())
        assert "件を根拠に入れて、答えを書いてよいですか。" in shown
        assert (
            "外す番号、足す番号、見立ての言い直し、前の答えの文の扱いがあれば、"
            "あわせて書いてください。" in shown.replace(" ", "")
        )

    def test_the_block_never_says_cite_event_or_node_below(self) -> None:
        shown = _shown(_offer())
        for inner in ("引用", "出来事", "下の論点", "推奨"):
            assert inner not in shown


class TestAResultShownBeforeCanBeRaised:
    """US-2 AC 3."""

    def test_it_is_raised_only_when_a_result_of_this_round_changes_it(self) -> None:
        raised = re.search(
            r"(?i)raise a result shown before[^.]*only when a result of this round"
            r" changes what it means[^.]*\.",
            unwrap(_offer()),
        )
        assert raised

    def test_its_reason_names_the_new_result_and_it_says_it_was_shown(self) -> None:
        offer = unwrap(_offer())
        assert re.search(r"(?i)its reason names the result of this round", offer)
        assert "（前の回にも見せた）" in _offer()


class TestAnAnswerRestsOnlyOnWhatTheAnalystConfirmed:
    """US-2 AC 4."""

    def test_taking_the_recommendation_as_it_stands_confirms_it(self) -> None:
        assert re.search(
            r"(?i)taking the recommendation as it stands confirms it", unwrap(_offer())
        )

    def test_a_result_the_analyst_did_not_confirm_is_never_cited(self) -> None:
        assert re.search(
            r"(?i)never cite a result from below that the analyst did not confirm",
            unwrap(_offer()),
        )

    def test_the_agent_waits_for_the_reply(self) -> None:
        assert re.search(r"(?i)wait for the answer", unwrap(_offer()))


class TestThePresentationSplitsTheLeftOutResultsTheSameWay:
    """The chat after writing splits as the question did (the same `shown_before`)."""

    def test_a_result_shown_before_is_a_count_after_writing_too(self) -> None:
        present = _present()
        assert f"── {SHOWN_BEFORE} ──" in present
        assert re.search(r"(?i)`shown_before` is `true`[^.]*count", unwrap(present))

    def test_the_count_after_writing_is_the_one_the_question_showed(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / ".insight"
        _wide_tree.build_through_round_2(base)
        left = tree_io.changes(_wide_tree.THEME, base_dir=base)["uncited_below"][
            _wide_tree.ROOT
        ]
        before = [e for e in left if e["shown_before"]]
        assert len(before) == _wide_tree.LISTED_BEFORE
        assert len(left) - len(before) == (
            _wide_tree.NEW_IN_ROUND_2 - _wide_tree.CHOSEN
        )

    def test_the_reference_lists_the_command_with_the_answers(self) -> None:
        reference = reflection_section("## tree_io / tree_check Reference")
        assert table_row(
            reference, "`tree_io changes --theme T --with-answers` (stdin JSON)"
        )[1]


class TestTheWalkCountsTheViewInsideTheGateOfTheReflection:
    def test_the_gate_row_still_names_the_two_steps(self) -> None:
        row = gate_row("theme reflection")
        assert row[1] == "**`/analysis-reflection {theme_id}` T3 + T7**"

    def test_the_row_copies_nothing_of_what_the_step_asks(self) -> None:
        assert gate_row("theme reflection")[2] == "—"

    def test_all_that_the_step_asks_is_one_gate_and_the_driver_adds_none(
        self,
    ) -> None:
        item = round_item("theme reflection")
        assert re.search(
            r"(?i)everything T3 asks before it writes the answers belongs to that one"
            r" gate, however many replies it takes",
            item,
        )
        assert re.search(r"(?i)the driver adds no question of its own", item)
        for copied in ("見立て", "勧め"):
            assert copied not in item


class TestTheEdgesTheReviewFound:
    """Paths an agent would have had to guess (review of Story 36.3)."""

    def test_a_node_without_a_statement_yet_is_left_out_of_the_file(
        self, tmp_path: Path
    ) -> None:
        assert re.search(
            r"(?i)leave out of the file a node whose draft has no statement yet",
            unwrap(_offer()),
        )
        # The command lists the results below a node the file leaves out.
        base = tmp_path / ".insight"
        _wide_tree.build(base)
        _wide_tree.add_round_2_events(base)
        below = [
            a
            for a in _wide_tree.round_2_drafts(base)
            if a["node_id"] != _wide_tree.ROOT
        ]
        listed = tree_io.changes(_wide_tree.THEME, answers=below, base_dir=base)[
            "uncited_below"
        ][_wide_tree.ROOT]
        assert sum(not e["shown_before"] for e in listed) == _wide_tree.NEW_IN_ROUND_2

    def test_the_command_says_when_it_could_not_read_the_file(self) -> None:
        assert re.search(
            r"(?i)exit code 1[^.]*nothing is listed[^.]*stderr", unwrap(_offer())
        )

    def test_a_contradicting_result_is_cited_without_being_confirmed(self) -> None:
        assert re.search(
            r"(?i)never cite a result from below that the analyst did not confirm,"
            r" other than a `contradicts` event",
            unwrap(_offer()),
        )

    def test_a_kept_statement_keeps_the_results_it_already_cites(self) -> None:
        assert re.search(
            r"(?i)does not yet cite[^.]*that its current answer does not cite",
            _drafts(),
        )

    def test_an_earlier_view_stays_beside_a_new_one_unless_the_analyst_replaces_it(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a view of an earlier round stays beside the new one[^.]*unless the"
            r" analyst says the new one replaces it",
            unwrap(_view()),
        )
        assert "前の回までのあなたの見立て" in _offer()

    def test_an_earlier_view_that_needs_asking_keeps_the_question(self) -> None:
        assert re.search(
            r"(?i)skip the question[^.]*only when[^.]*no statement with"
            r" `analyst_view` needs asking about",
            unwrap(_offer()),
        )

    def test_the_view_shows_the_results_it_rests_on_before_it_is_written(
        self,
    ) -> None:
        assert "根拠: {the numbers of the results it rests on}" in _offer()

    def test_a_first_answer_lists_every_design_with_a_result(self) -> None:
        assert re.search(
            r"(?i)when the root has no answer yet[^.]*every design whose journal"
            r" holds an event",
            unwrap(_view()),
        )

    def test_no_sentence_for_the_analyst_says_read_for_the_view(self) -> None:
        # 読む is kept for reading the analysis note (docs/UBIQUITOUS_LANGUAGE.md).
        for shown in (_shown(_view()), _shown(_offer())):
            assert "読" not in shown
