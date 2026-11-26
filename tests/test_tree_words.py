"""Tests for the words a question tree shows the analyst (Epic 34, #273).

The tests of the page and of the report name a reflection round, the subject,
the marks and the headings through ``tree_words`` and check where they are
shown. This module alone spells those words, so one of them that changes is
changed here. A sentence only one section says is still spelled by the test of
that section.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from insight_blueprint.models.tree import Progress
from skills._shared import tree_words
from skills._shared.tree_words import Mark
from tests._tree_page import (
    OLD_QUESTION,
    ROOT_QUESTION,
    by_id,
    changed_root,
    make_tree,
    mark_word,
    never_revised,
    node_text,
    page,
    squash,
)


def _revised_twice() -> dict:
    """make_tree with a third revision of the subject: LIB-Q02 answers revision 2."""
    tree = make_tree()
    tree["root_revisions"].append(
        {
            "revision": 3,
            "question": "取り置き期限を延ばす試行を今年度に始めるか",
            "aim": tree["root_revisions"][1]["aim"],
            "reason": "始める時期も決めることになった",
        }
    )
    tree["nodes"][0]["question"] = tree["root_revisions"][-1]["question"]
    return tree


class TestRoundsAreCountedReflections:
    @pytest.mark.parametrize("tree", [make_tree(), changed_root()])
    def test_no_round_is_shown_as_a_bare_number(self, tree: dict) -> None:
        root = page(tree=tree)
        shown = squash(" ".join(e.text() for e in root.walk() if e.tag == "body"))

        assert not re.search(r"回 \d", shown)
        assert "回 N" not in shown


class TestTheSubjectNamesItsRevisionsOnlyOnceRevised:
    """US-5 AC 1 as chosen after reading the pages: no 版 and no number of it."""

    def test_a_subject_never_revised_says_nothing_of_revisions(self) -> None:
        root = page(tree=never_revised())
        shown = squash(" ".join(e.text() for e in root.walk() if e.tag == "body"))

        assert "見直した" not in squash(by_id(root, "header").text())
        assert "見直す前の主題への答え" not in by_id(root, "question-tree").text()
        assert "主題の版" not in shown

    def test_a_revised_subject_says_how_many_times_and_links_its_history(
        self,
    ) -> None:
        header = by_id(page(), "header")

        assert "主題を1回見直した" in squash(header.text())
        assert any(
            e.tag == "a" and e.attrs.get("href") == "#root-history"
            for e in header.walk()
        )

    def test_no_page_shows_the_word_for_a_revision(self) -> None:
        for tree in (make_tree(), _revised_twice(), changed_root()):
            root = page(tree=tree)
            shown = " ".join(e.text() for e in root.walk() if e.tag == "body")
            assert "版" not in shown

    def test_after_two_revisions_an_old_answer_says_before_which(self) -> None:
        root = page(tree=_revised_twice())

        assert "主題を2回見直した" in squash(by_id(root, "header").text())
        assert "1回目の見直しの前の主題への答え" in node_text(root, "LIB-Q05")
        assert "2回目の見直しの前の主題への答え" in node_text(root, "LIB-Q02")

    def test_the_history_names_each_subject_by_the_revisions_before_it(
        self,
    ) -> None:
        history = squash(by_id(page(tree=_revised_twice()), "root-history").text())

        assert f"1回目の見直しの後の主題: {ROOT_QUESTION}" in history
        assert (
            "2回目の見直しの後の主題: 取り置き期限を延ばす試行を今年度に始めるか"
            in history
        )
        assert "理由: 始める時期も決めることになった" in history


class TestTheMarksReadAsTheHeadingOfTheAnswer:
    """Chosen after reading the pages: こと makes the mark head the statements
    below it, not read as "changed after N reflections"."""

    def test_the_mark_at_the_top_and_on_the_card_say_what_changed(self) -> None:
        root = page(tree=changed_root())

        assert "2回目の振り返りで変わったこと" in squash(
            by_id(root, "subject-answer").text()
        )
        assert "2回目の振り返りで変わったこと" in node_text(root, "LIB-Q02")


class TestTheWordsShownToTheAnalyst:
    """Epic 34 US-5 AC 1, AC 2: the page speaks the analyst's words, not the code's."""

    def test_the_header_calls_the_root_question_the_subject(self) -> None:
        header = squash(by_id(page(), "header").text())

        assert f"主題: {ROOT_QUESTION}" in header

    def test_the_history_lists_each_revision_of_the_subject(self) -> None:
        history = squash(by_id(page(), "root-history").text())

        assert history.startswith("主題を見直した履歴")
        assert f"最初の主題: {OLD_QUESTION}" in history
        assert f"1回目の見直しの後の主題: {ROOT_QUESTION}" in history

    def test_the_round_of_an_answer_is_said_as_the_count_of_reflections(
        self,
    ) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert "1回目の振り返り" in shown
        assert "版" not in shown

    @pytest.mark.parametrize(
        "entry",
        [
            "これまでわかっていること: 根拠にした分析結果から言えること。",
            "まだ決められないこと: 分析をしても、分析結果からは決められないこと。",
            "注意すべきこと: これまでわかっていることを弱める分析結果や、"
            "言える範囲を狭める条件。",
            "見直す前の主題への答え: 主題か到達点を見直す前の主題に対して書いた答え。",
        ],
    )
    def test_the_legend_explains_each_word_in_the_analysts_words(
        self, entry: str
    ) -> None:
        assert entry in squash(by_id(page(), "legend").text())


class TestEachPhrasingIsSpelledOnce:
    """What ``tree_words`` says, word for word."""

    @pytest.mark.parametrize(
        ("said", "expected"),
        [
            (tree_words.SUBJECT, "主題"),
            (tree_words.reflection(2), "2回目の振り返り"),
            (tree_words.CHANGES_HEADING, "前の振り返りから変わったこと"),
            (
                tree_words.changes_title(1, 2),
                "前の振り返りから変わったこと（1回目 → 2回目の振り返り）",
            ),
            (
                tree_words.left_as_written(3, 2),
                "最新の振り返りは3回目で、2回目より後の振り返りでは、"
                "この答えを書き直していない。",
            ),
            (tree_words.when_decided(0), "振り返りの前"),
            (tree_words.when_decided(2), "2回目の振り返りの後"),
            (tree_words.whose_answer(True), "主題への"),
            (tree_words.whose_answer(False), "この論点の"),
            (tree_words.revision_name(1), "最初の主題"),
            (tree_words.revision_name(3), "2回目の見直しの後の主題"),
            (mark_word(Mark.changed, 2), "2回目の振り返りで変わったこと"),
            (mark_word(Mark.first, 2), "2回目の振り返りで初めて答えたこと"),
            (mark_word(Mark.before_root_change), "見直す前の主題への答え"),
            (mark_word(Mark.violating), "記録と合わない答え"),
            (tree_words.HEARD_WORD, "（人に聞いた答えによる）"),
            (tree_words.OPEN_EVIDENCE, "根拠を開く"),
            (tree_words.OPEN_NOTE, "分析ノートを開く"),
            (tree_words.BACK_TO_TREE, "論点ツリーへ戻る"),
            (
                # The furthest first, with all three words.
                tree_words.below_text(
                    True,
                    Counter(
                        {
                            Progress.not_started: 2,
                            Progress.investigating: 1,
                            Progress.analyzed: 1,
                        }
                    ),
                ),
                "主題の下に置いた論点 4 つ: 分析済み 1、検証中 1、未着手 2",
            ),
            (
                tree_words.below_text(
                    True,
                    Counter({Progress.analyzed: 1, Progress.not_started: 2}),
                ),
                "主題の下に置いた論点 3 つ: 分析済み 1、未着手 2",
            ),
            (
                tree_words.below_text(False, Counter({Progress.investigating: 1})),
                "この論点の下に置いた論点 1 つ: 検証中 1",
            ),
        ],
    )
    def test_a_phrasing_reads_as_the_analyst_chose_it(
        self, said: str, expected: str
    ) -> None:
        assert said == expected

    @pytest.mark.parametrize(
        ("table", "words"),
        [
            (tree_words.PROGRESS_WORDS, ["未着手", "検証中", "分析済み"]),
            (
                tree_words.KIND_WORDS,
                ["これまでわかっていること", "まだ決められないこと", "注意すべきこと"],
            ),
            (
                tree_words.CHANGE_WORDS,
                [
                    "新しく根拠にした",
                    "根拠から外した",
                    "言っていることが変わった",
                    "変わっていない",
                ],
            ),
        ],
    )
    def test_a_table_holds_the_words_in_the_order_of_its_kinds(
        self, table: dict, words: list[str]
    ) -> None:
        assert [word for word, _ in table.values()] == words
