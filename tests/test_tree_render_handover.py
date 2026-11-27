"""Tests for the check before a hand-over on the tree page (Epic 35, Story 35.5).

The page lays the designs to hand over side by side (US-2 AC 2), a mark names
the rows whose values differ between them (AC 3), and each design has a
comment box whose comments the page gathers into one text it sends nowhere
(AC 4). Which designs are laid out is the rule's (tests/test_handover.py): the
page lays out the ones it is given. Synthetic data only.
"""

from __future__ import annotations

import re

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import AnalysisDesign
from skills._shared.handover import HandoverDesign, HandoverRow
from skills._shared.tree_words import (
    ASKS_LEAD,
    DIFFERS_WORD,
    GATHER_BUTTON,
    HANDOVER_ROW_WORDS,
    LINKED_NODES,
    NO_CRITERION,
    NOT_WRITTEN,
    handover_heading,
)
from tests._handover import LONG_SQL, confirmation, exploration, handed_tree
from tests._tree_page import (
    Element,
    by_id,
    has_class,
    make_designs,
    page,
    render,
    squash,
    summary,
)


def _summaries() -> dict:
    designs = make_designs()
    for design_id in ("LIB-H05", "LIB-H06"):
        designs[design_id] = summary(
            design_id,
            f"{design_id} の題",
            "in_review",
            None,
            stage=AnalysisStage.before_run,
        )
    return designs


def _handover(*designs: AnalysisDesign) -> list[HandoverDesign]:
    shown = designs or (exploration("LIB-H05"), confirmation("LIB-H06"))
    return [HandoverDesign.of(d) for d in shown]


def _html(*designs: AnalysisDesign) -> str:
    return render(
        tree=handed_tree(), designs=_summaries(), handover=_handover(*designs)
    )


def _page(*designs: AnalysisDesign) -> Element:
    return page(tree=handed_tree(), designs=_summaries(), handover=_handover(*designs))


def _section(root: Element) -> Element:
    return by_id(root, "handover")


def _row(root: Element, row: HandoverRow) -> Element:
    (found,) = [
        e for e in _section(root).walk() if e.attrs.get("data-row") == row.value
    ]
    return found


def _cells(root: Element, row: HandoverRow) -> list[Element]:
    return [c for c in _row(root, row).children if c.tag == "td"]


def _texts(root: Element, row: HandoverRow) -> list[str]:
    return [squash(c.text()) for c in _cells(root, row)]


class TestTheSectionLaysTheDesignsSideBySide:
    """US-2 AC 2: one column a design, the rows in the order the analyst reads them."""

    def test_one_column_a_design_with_its_id_title_and_question(self) -> None:
        heads = [
            squash(e.text())
            for e in _section(_page()).walk()
            if e.tag == "th" and e.attrs.get("scope") == "col"
        ]

        # The question is named as in the analyses that wait for the analyst.
        assert heads == [
            f"LIB-H05 LIB-H05 の題 {LINKED_NODES}: LIB-Q04",
            f"LIB-H06 LIB-H06 の題 {LINKED_NODES}: LIB-Q05",
        ]

    def test_the_heading_counts_the_designs(self) -> None:
        (heading,) = [e for e in _section(_page()).walk() if e.tag == "h2"]

        assert squash(heading.text()) == handover_heading(2)

    def test_the_rows_come_in_the_order_of_the_check(self) -> None:
        rows = [
            e.attrs["data-row"]
            for e in _section(_page()).walk()
            if e.tag == "tr" and "data-row" in e.attrs
        ]

        # The comment of each design comes last, under what it comments on.
        assert rows == [*(r.value for r in HandoverRow), "comment"]

    def test_each_row_is_named_in_the_analysts_word(self) -> None:
        root = _page()

        for row in HandoverRow:
            (head,) = [c for c in _row(root, row).children if c.tag == "th"]
            assert squash(head.text()).startswith(HANDOVER_ROW_WORDS[row])

    def test_what_it_answers_is_the_question_or_the_hypothesis(self) -> None:
        assert _texts(_page(), HandoverRow.statement) == [
            "LIB-H05 の探索の問い",
            "LIB-H06 の検証仮説",
        ]

    def test_the_criterion_of_a_confirmation_and_why_an_exploration_has_none(
        self,
    ) -> None:
        assert _texts(_page(), HandoverRow.criterion) == [
            NO_CRITERION,
            "差が5ポイント以上なら支持、1ポイント以下なら棄却",
        ]

    def test_population_grain_and_denominator_each_on_its_own_row(self) -> None:
        root = _page()

        assert _texts(root, HandoverRow.population) == ["2025年度に予約した本"] * 2
        assert _texts(root, HandoverRow.grain) == ["予約1件"] * 2
        assert _texts(root, HandoverRow.denominator) == ["取り置いた予約の全件"] * 2

    def test_a_design_without_a_scope_says_it_is_not_written(self) -> None:
        root = _page(exploration("LIB-H05", data_scope=None), confirmation("LIB-H06"))

        assert _texts(root, HandoverRow.grain)[0] == NOT_WRITTEN

    def test_the_method_the_primary_metric_and_the_chart(self) -> None:
        root = _page()

        assert _texts(root, HandoverRow.method)[0] == "曜日ごとの集計（pandas）"
        # Only the primary metric: the secondary one is not what is judged.
        assert _texts(root, HandoverRow.metric) == [
            "期限切れ率（割合）",
            "期限切れ率の差",
        ]
        assert _texts(root, HandoverRow.chart)[0] == (
            "曜日ごとの期限切れ率（bar。横: 曜日、縦: 期限切れ率）"
        )

    def test_the_extraction_is_shown_in_full_each_step_apart(self) -> None:
        design = exploration(
            "LIB-H05",
            methodology={
                "method": "集計",
                "steps": [{"description": LONG_SQL}, "df = df.dropna()"],
            },
        )
        (cell, _) = _cells(
            _page(design, confirmation("LIB-H06")), HandoverRow.extraction
        )

        assert [e.text() for e in cell.walk() if e.tag == "pre"] == [
            LONG_SQL,
            "df = df.dropna()",
        ]

    def test_what_a_design_writes_is_escaped(self) -> None:
        design = exploration(
            "LIB-H05",
            methodology={
                "method": "集計",
                "steps": [{"description": "SELECT '</pre><script>x()</script>'"}],
            },
        )
        html = _html(design, confirmation("LIB-H06"))

        assert "<script>x()" not in html
        assert "&lt;/pre&gt;&lt;script&gt;" in html


class TestTheRowsThatDiffer:
    """US-2 AC 3: the page marks the rows the rule names, in a word."""

    def test_the_page_marks_the_rows_the_rule_names(self) -> None:
        root = _page(
            exploration("LIB-H05"),
            confirmation(
                "LIB-H06",
                data_scope={
                    "population": "2025年度に予約した本",
                    "grain": "本1冊",
                    "denominator": "取り置いた予約の全件",
                },
            ),
        )

        marked = [
            r.value
            for r in HandoverRow
            if has_class(_row(root, r), "differs")
            and DIFFERS_WORD in squash(_row(root, r).text())
        ]
        assert marked == [HandoverRow.grain.value]


class TestTheComments:
    """US-2 AC 4: a comment box a design, gathered into one text, sent nowhere."""

    def test_each_design_has_a_comment_box_named_by_its_id(self) -> None:
        boxes = [e for e in _section(_page()).walk() if e.tag == "textarea"]

        assert [b.attrs.get("data-design-id") for b in boxes] == [
            "LIB-H05",
            "LIB-H06",
            None,  # the gathered text
        ]

    def test_the_button_and_the_box_of_the_gathered_text(self) -> None:
        section = _section(_page())
        (button,) = [e for e in section.walk() if e.tag == "button"]
        gathered = by_id(section, "handover-gathered")

        assert squash(button.text()) == GATHER_BUTTON
        assert button.attrs.get("type") == "button"
        assert gathered.tag == "textarea"
        assert "readonly" in gathered.attrs
        # The script holds no word: the page gives it the head and the empty case.
        assert gathered.attrs.get("data-head")
        assert gathered.attrs.get("data-none")

    def test_the_script_gathers_each_comment_after_its_design_id(self) -> None:
        (script,) = re.findall(r"<script>(.*?)</script>", _html(), re.S)

        assert "data-design-id" in script
        assert "designId" in script
        assert not re.search(r"[^\x00-\x7f]", script)

    @pytest.mark.parametrize(
        "sends",
        [
            "fetch(",
            "XMLHttpRequest",
            "sendBeacon",
            "WebSocket",
            "EventSource",
            "import(",
            ".submit(",
            "location",
            "window.open",
            "postMessage",
        ],
    )
    def test_the_page_sends_nothing(self, sends: str) -> None:
        (script,) = re.findall(r"<script>(.*?)</script>", _html(), re.S)

        assert sends not in script

    def test_the_page_has_no_form_and_loads_nothing(self) -> None:
        root = _page()

        assert not [e for e in root.walk() if e.tag in ("form", "link", "iframe")]
        assert not [
            e for e in root.walk() if {"src", "action", "formaction"} & set(e.attrs)
        ]

    def test_a_page_with_nothing_to_hand_over_has_no_section_and_no_script(
        self,
    ) -> None:
        html = render(tree=handed_tree(), designs=_summaries(), handover=[])

        assert 'id="handover"' not in html
        assert "<script" not in html


class TestWhereTheSectionSits:
    """The check is what the analyst does now, so it sits at the top."""

    def test_after_the_asks_and_before_the_answer_to_the_subject(self) -> None:
        designs = _summaries()
        designs["LIB-H02"] = summary(
            "LIB-H02",
            "通知の遅れを測る",
            "analyzing",
            "LIB-H01",
            stage=AnalysisStage.awaiting_confirmation,
            asks=("対象を変えてよいか",),
        )
        html = render(tree=handed_tree(), designs=designs, handover=_handover())

        ids = re.findall(r'<section[^>]* id="([a-z-]+)"', html)
        assert ids.index("asks") < ids.index("handover") < ids.index("subject-answer")
        assert ASKS_LEAD in html
