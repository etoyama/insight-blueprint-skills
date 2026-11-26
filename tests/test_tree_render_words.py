"""Tests for the words a human chose after reading the real pages (Epic 34).

A round is said as the count of reflections (N回目の振り返り), the revision of
the subject only once the subject was revised, in words, and a result is what
an answer says about it, not from it (Decision words-chosen-after-reading-the-real-pages).
Synthetic data only (theme LIB).
"""

from __future__ import annotations

import re

import pytest

from tests.test_tree_render import (
    ROOT_QUESTION,
    by_id,
    make_tree,
    node_text,
    page,
    squash,
)
from tests.test_tree_render_derived import changed_root


def _never_revised() -> dict:
    tree = make_tree()
    tree["root_revisions"] = tree["root_revisions"][1:]
    tree["root_revisions"][0].update(revision=1, reason="")
    for node in tree["nodes"]:
        for answer in node.get("answers", []):
            answer["root_revision"] = 1
    return tree


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


def _text(tree: dict) -> str:
    return squash(by_id(page(tree=tree), "header").text()) + squash(
        by_id(page(tree=tree), "question-tree").text()
    )


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
        root = page(tree=_never_revised())
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
            in (history)
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
