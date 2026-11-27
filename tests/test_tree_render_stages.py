"""Tests for the analysis stages on the tree page (Epic 35, Story 35.4).

The page words each linked design by its analysis stage (US-3 AC 2), lifts the
analyses that wait for the analyst's confirmation to the top (AC 3), folds a
node whose designs were all stopped into its own progress word (AC 4), and
names every question a decision hands over (AC 5). Synthetic data only.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.tree import Progress, TreeDecisionKind
from skills._shared._html import BASE_CSS
from skills._shared.tree_words import (
    ASKS_LEAD,
    DECISION_LABELS,
    PROGRESS_WORDS,
    STAGE_WORDS,
    STOP_REASON,
    WHAT_IS_ASKED,
    asks_heading,
    when_decided,
)
from tests._tree_page import (
    T0,
    Element,
    branch_cards,
    by_id,
    card_text,
    has_class,
    make_designs,
    make_tree,
    node_card,
    page,
    render,
    squash,
    summary,
)

STOPPED_WHY = "通知の時刻が記録されていなかった"
ASKED = "予約の記録が2025年10月より前に無い。対象を変えてよいか"


def _stage_spans(root: Element) -> list[Element]:
    return [e for e in root.walk() if has_class(e, "stage")]


def _staged(stage: AnalysisStage, **over: object) -> dict:
    """make_designs with LIB-H01 (linked to LIB-Q02) at *stage*."""
    designs = make_designs()
    status = {
        AnalysisStage.before_run: "in_review",
        AnalysisStage.finished: "supported",
    }.get(stage, "analyzing")
    designs["LIB-H01"] = summary(
        "LIB-H01", "取消を除く数え方", status, None, stage=stage, **over
    )
    return designs


class TestEachDesignSaysItsStage:
    """US-3 AC 2: the stage in words and in colour, the words carrying the meaning."""

    @pytest.mark.parametrize("stage", list(AnalysisStage))
    def test_the_card_says_the_stage_in_its_word(self, stage: AnalysisStage) -> None:
        root = page(designs=_staged(stage))

        (card,) = branch_cards(root, "LIB-Q02")
        (span,) = [e for e in card.walk() if has_class(e, "stage")]
        assert squash(span.text()) == STAGE_WORDS[stage][0]
        assert has_class(span, f"stage-{stage.value}")

    def test_a_short_row_under_a_second_node_says_the_stage_too(self) -> None:
        tree = make_tree()
        tree["nodes"][4]["design_ids"] = ["LIB-H01"]

        root = page(tree=tree, designs=_staged(AnalysisStage.running))

        (row,) = branch_cards(root, "LIB-Q05")
        assert STAGE_WORDS[AnalysisStage.running][0] in card_text(row)

    @pytest.mark.parametrize(
        ("stage", "status_word"),
        [
            (AnalysisStage.before_run, "レビュー中"),
            (AnalysisStage.finished, "検証仮説の判定: 支持"),
        ],
    )
    def test_a_stage_the_status_adds_to_keeps_the_status_word(
        self, stage: AnalysisStage, status_word: str
    ) -> None:
        (card,) = branch_cards(page(designs=_staged(stage)), "LIB-Q02")

        assert status_word in card_text(card)

    @pytest.mark.parametrize(
        "stage",
        [
            AnalysisStage.running,
            AnalysisStage.awaiting_confirmation,
            AnalysisStage.stopped,
            AnalysisStage.awaiting_reflection,
        ],
    )
    def test_a_stage_of_a_design_still_analyzing_hides_the_status_word(
        self, stage: AnalysisStage
    ) -> None:
        """A stopped analysis keeps the status analyzing: the card says only 止めた."""
        (card,) = branch_cards(page(designs=_staged(stage)), "LIB-Q02")

        assert "分析中" not in card_text(card)

    def test_a_stopped_design_says_why_it_was_stopped(self) -> None:
        designs = _staged(AnalysisStage.stopped, stop_reason=STOPPED_WHY)

        (card,) = branch_cards(page(designs=designs), "LIB-Q02")

        assert f"{STOP_REASON}: {STOPPED_WHY}" in card_text(card)

    def test_a_design_waiting_for_the_analyst_says_what_it_asks(self) -> None:
        designs = _staged(AnalysisStage.awaiting_confirmation, asks=(ASKED,))

        (card,) = branch_cards(page(designs=designs), "LIB-Q02")

        assert f"{WHAT_IS_ASKED}: {ASKED}" in card_text(card)

    def test_a_running_design_carries_neither_a_reason_nor_a_question(self) -> None:
        (card,) = branch_cards(page(designs=_staged(AnalysisStage.running)), "LIB-Q02")

        assert STOP_REASON not in card_text(card)
        assert WHAT_IS_ASKED not in card_text(card)

    @pytest.mark.parametrize("stage", list(AnalysisStage))
    def test_every_stage_has_its_colour_in_light_and_dark(
        self, stage: AnalysisStage
    ) -> None:
        css = render(designs=_staged(stage))
        (rule,) = re.findall(rf"\.stage-{stage.value} \{{[^}}]*\}}", css)
        (variable,) = re.findall(r"var\((--[a-z-]+)\)", rule)

        assert BASE_CSS.count(f"{variable}:") == 2

    def test_stopped_has_a_shape_besides_its_grey(self) -> None:
        # The grey of stopped is near the grey of not started (35.5, the real
        # page): stopped adds a dashed frame and stripes, not another colour.
        css = render(designs=_staged(AnalysisStage.stopped))
        (frame,) = re.findall(r"\.progress-stopped \{[^}]*\}", css)
        (stage,) = re.findall(r"\.stage-stopped \{[^}]*\}", css)
        (before,) = re.findall(r"\.stage-before_run \{[^}]*\}", css)

        assert "border-left-style: dashed" in frame
        assert "repeating-linear-gradient" in stage
        assert "repeating-linear-gradient" not in before
        assert re.findall(r"var\((--[a-z-]+)\)", stage) == ["--stopped"]

    def test_the_legend_explains_each_stage_and_that_the_colour_only_adds(
        self,
    ) -> None:
        legend = squash(by_id(page(), "legend").text())

        for word, meaning in STAGE_WORDS.values():
            assert f"{word}: {meaning}" in legend
        assert "分析の段階" in legend


def _asking(*asks: str) -> dict:
    return _staged(AnalysisStage.awaiting_confirmation, asks=asks)


class TestTheAnalysesWaitingForTheAnalystLeadThePage:
    """US-3 AC 3: lifted to the top, and absent when none waits."""

    def test_no_section_when_nothing_waits(self) -> None:
        root = page()

        assert not [e for e in root.walk() if e.attrs.get("id") == "asks"]

    def test_the_section_comes_right_after_the_header(self) -> None:
        body = next(e for e in page(designs=_asking(ASKED)).walk() if e.tag == "body")

        order = [e.attrs.get("id") for e in body.children if e.attrs.get("id")]
        assert order[:3] == ["header", "asks", "subject-answer"]

    def test_it_names_each_waiting_design_its_question_and_where_it_is(
        self,
    ) -> None:
        second = "期間を短くしてよいか"
        root = page(designs=_asking(ASKED, second))

        asks = by_id(root, "asks")
        text = squash(asks.text())
        assert text.startswith(f"{asks_heading(1)} {ASKS_LEAD}")
        assert "LIB-H01 取消を除く数え方" in text
        assert f"{WHAT_IS_ASKED}: {ASKED}" in text
        assert f"{WHAT_IS_ASKED}: {second}" in text
        hrefs = [e.attrs["href"] for e in asks.walk() if e.tag == "a"]
        assert "#design-LIB-H01" in hrefs
        assert "#LIB-Q02" in hrefs

    def test_it_counts_the_designs_that_wait(self) -> None:
        designs = _asking(ASKED)
        designs["LIB-H02"] = summary(
            "LIB-H02",
            "通知の遅れを測る",
            "analyzing",
            "LIB-H01",
            stage=AnalysisStage.awaiting_confirmation,
            asks=("通知の日をどう数えるか",),
        )

        text = squash(by_id(page(designs=designs), "asks").text())

        assert text.startswith(asks_heading(2))
        assert text.index("LIB-H01") < text.index("LIB-H02")

    def test_a_waiting_design_linked_to_no_question_is_still_listed(self) -> None:
        designs = make_designs()
        designs["LIB-H04"] = summary(
            "LIB-H04",
            "貸出の季節差",
            "analyzing",
            "LIB-H99",
            stage=AnalysisStage.awaiting_confirmation,
            asks=(ASKED,),
        )

        text = squash(by_id(page(designs=designs), "asks").text())

        assert "LIB-H04 貸出の季節差" in text

    def test_the_heading_and_the_lead_say_who_does_what(self) -> None:
        assert asks_heading(1) == "あなたの確認待ち（1件）"
        assert "あなた" in ASKS_LEAD
        assert "エージェント" in ASKS_LEAD


class TestAQuestionWhoseDesignsWereAllStopped:
    """US-3 AC 4: 止めた on the card and in the counts, with its own colour."""

    def _page(self, *stages: AnalysisStage) -> Element:
        tree = make_tree()
        tree["nodes"][2]["design_ids"] = [
            f"LIB-H0{n}" for n in range(5, 5 + len(stages))
        ]
        designs = make_designs()
        for n, stage in enumerate(stages, start=5):
            status = "supported" if stage is AnalysisStage.finished else "analyzing"
            designs[f"LIB-H0{n}"] = summary(
                f"LIB-H0{n}", "t", status, None, T0, stage=stage
            )
        return page(tree=tree, designs=designs)

    def test_all_stopped_reads_as_stopped(self) -> None:
        root = self._page(AnalysisStage.stopped, AnalysisStage.stopped)

        card = node_card(root, "LIB-Q03")
        assert f"進捗: {PROGRESS_WORDS[Progress.stopped][0]}" in squash(card.text())
        assert has_class(card, "progress-stopped")
        assert "--stopped:" in BASE_CSS
        assert ".progress-stopped {" in render()

    def test_a_stopped_design_beside_a_finished_one_is_not_counted(self) -> None:
        root = self._page(AnalysisStage.stopped, AnalysisStage.finished)

        assert has_class(node_card(root, "LIB-Q03"), "progress-analyzed")

    def test_the_counts_count_a_stopped_question(self) -> None:
        root = self._page(AnalysisStage.stopped)

        counts = squash(by_id(root, "counts").text())
        assert f"{PROGRESS_WORDS[Progress.stopped][0]} 1" in counts


class TestStoppedCardsComeLast:
    """A stopped analysis is never resumed, so its card follows the finished ones."""

    def test_unfinished_then_finished_then_stopped(self) -> None:
        tree = make_tree()
        tree["nodes"][2]["design_ids"] = ["LIB-H05", "LIB-H06", "LIB-H07"]
        designs = make_designs()
        day = timedelta(days=1)
        designs["LIB-H05"] = summary(
            "LIB-H05", "t", "analyzing", None, T0 + day, stage=AnalysisStage.stopped
        )
        designs["LIB-H06"] = summary(
            "LIB-H06", "t", "supported", None, T0, stage=AnalysisStage.finished
        )
        designs["LIB-H07"] = summary(
            "LIB-H07", "t", "analyzing", None, T0 - day, stage=AnalysisStage.running
        )

        cards = branch_cards(page(tree=tree, designs=designs), "LIB-Q03")

        shown = [next(i for i in designs if i in card_text(c)) for c in cards]
        assert shown == ["LIB-H07", "LIB-H06", "LIB-H05"]


RETURN = DECISION_LABELS[TreeDecisionKind.return_]


def _handing_over() -> dict:
    tree = make_tree()
    tree["decisions"].append(
        {
            "round": 2,
            "kind": "return",
            "node_id": "LIB-Q03",
            "with_node_ids": ["LIB-Q05"],
            "reason": "互いの結果を待たない",
        }
    )
    return tree


class TestEveryQuestionADecisionNames:
    """US-3 AC 5: the next question and the list of decisions name them all."""

    def test_the_next_question_names_each_question_and_what_it_asks(self) -> None:
        section = by_id(page(tree=_handing_over()), "next-question")

        assert squash(section.text()).startswith(
            f"次に調べる論点 {RETURN}（{when_decided(2)}）: "
            "LIB-Q03 通知は期限の何日前に届くか、LIB-Q05 延長で予約は減るか 理由:"
        )
        hrefs = [a.attrs["href"] for a in section.walk() if a.tag == "a"]
        assert hrefs[:2] == ["#LIB-Q03", "#LIB-Q05"]

    def test_the_list_of_decisions_links_each_question(self) -> None:
        decisions = by_id(page(tree=_handing_over()), "decisions")
        (last,) = [li for li in decisions.walk() if li.tag == "li"][-1:]

        assert squash(last.text()).startswith(
            f"{RETURN}（{when_decided(2)}）: LIB-Q03、LIB-Q05 互いの結果を待たない"
        )
        hrefs = [a.attrs["href"] for a in last.walk() if a.tag == "a"]
        assert hrefs == ["#LIB-Q03", "#LIB-Q05"]


class TestTheDerivationSaysTheStageToo:
    """The derivation names each design's state as its card does."""

    def test_a_stopped_design_reads_as_stopped_in_the_derivation(self) -> None:
        designs = _staged(AnalysisStage.stopped, stop_reason=STOPPED_WHY)

        row = squash(by_id(page(designs=designs), "design-LIB-H01").text())

        assert STAGE_WORDS[AnalysisStage.stopped][0] in row
        assert "分析中" not in row

    def test_a_finished_design_keeps_its_verdict_in_the_derivation(self) -> None:
        row = squash(by_id(page(), "design-LIB-H01").text())

        assert STAGE_WORDS[AnalysisStage.finished][0] in row
        assert "検証仮説の判定: 支持" in row
