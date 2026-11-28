"""Structure tests: the skills speak the analyst's words for the tree (Epic 34, Story 34.1).

US-5 AC 1, AC 2: the sentences a skill shows the analyst call the root question
主題, an answer to an older revision 見直す前の主題への答え, a reflection round
N回目の振り返り, and the kinds of statement by the words the analyst chose
(ADR-0055). A revision of the subject is said in words, by how many times it
was revised, and not at all while it never was: the analyst never reads 版
(Decision words-chosen-after-reading-the-real-pages). The YAML keys and
``tree_io revise-root`` keep the word root (US-5 AC 3).
"""

from __future__ import annotations

import pytest

from tests.skills._reflection import reflection_section
from tests.skills._skill_text import skill_text
from tests.skills.test_skill_structure import _read_skill

WORDS_RULE = (
    "call the root question 主題, an answer to an earlier root revision"
    " 見直す前の主題への答え, and reflection round N N回目の振り返り. Never show the"
    " word 版 or the number of a root revision: say how many times the 主題 was"
    " revised (主題を1回見直した), and nothing of it while it was never revised"
)


@pytest.mark.parametrize("skill", ["analysis-framing", "analysis-reflection"])
def test_a_skill_that_talks_about_the_tree_names_the_analysts_words(
    skill: str,
) -> None:
    assert WORDS_RULE in " ".join(skill_text(skill).split())


def test_the_theme_reflection_never_shows_a_round_as_a_bare_number() -> None:
    present = reflection_section("### Step T5: ")
    ask = reflection_section("### Step T3: ")

    for text in (present, ask):
        assert "回 {" not in text
    assert "{previous_round}回目の振り返りから変わった" in present
    assert "（{round}回目の振り返りの答えまで根拠にしていた）" in ask


class TestTheThemeReflectionShowsTheAnalystsWords:
    def _present(self) -> str:
        return reflection_section("### Step T5: ")

    def test_the_answers_are_headed_by_the_subject_and_its_revision(self) -> None:
        present = self._present()

        assert "{round}回目の振り返り{。主題を{n}回見直した}" in present
        assert "主題の版" not in present
        assert "主題: {root question}" in present

    def test_each_statement_is_tagged_with_the_word_of_its_kind(self) -> None:
        present = self._present()

        for word in (
            "これまでわかっていること",
            "注意すべきこと",
            "まだ決められないこと",
        ):
            assert f"[{word}] {{text}}" in present

    def test_an_answer_to_an_older_revision_is_marked_in_the_analysts_words(
        self,
    ) -> None:
        present = self._present()

        assert '"見直す前の主題への答え"' in present
        assert "主題を見直し、同じ文で書き直した" in present

    def test_a_theme_without_a_tree_is_sent_to_decide_its_subject(self) -> None:
        load = reflection_section("### Step T1: ")

        assert "主題と論点を決めよう" in load


def test_the_report_without_an_answer_names_the_subject_and_its_revision() -> None:
    assert '`no_root_answer`: "今の主題への答えがまだない。' in _read_skill(
        "report-export"
    )


def test_the_report_warns_that_it_carries_the_subject() -> None:
    assert "レポートには主題、答え、到達点" in _read_skill("report-export")


def test_the_upload_says_the_page_carries_the_subject_and_its_aim() -> None:
    assert "論点ツリー（主題と到達点、" in _read_skill("tree-upload")
