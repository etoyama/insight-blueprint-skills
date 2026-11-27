"""Tests for the check before a hand-over on the tree page (Epic 35, Story 35.5).

The page lays the designs to hand over side by side (US-2 AC 2), a mark names
the rows whose values differ between them (AC 3), and each design has a
comment box whose comments the page gathers into one text it sends nowhere
(AC 4). Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import re

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import AnalysisDesign
from skills._shared.handover import (
    COMPARED_ROWS,
    READ_BEFORE_HANDOVER,
    HandoverDesign,
    HandoverRow,
    differing_rows,
    to_hand_over,
)
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
from tests._tree_page import (
    Element,
    build,
    by_id,
    has_class,
    make_designs,
    make_tree,
    page,
    render,
    squash,
    summary,
)

LONG_SQL = (
    "SELECT hold_id, branch_id, ready_on, picked_up_on\n"
    "FROM {source:lib_holds}\n"
    "WHERE ready_on BETWEEN '2025-04-01' AND '2026-03-31'\n"
    "  AND status IN ('picked_up', 'expired')\n"
    "  AND branch_id IN ('central', 'east', 'west', 'north', 'south', 'harbor')\n"
    "-- the last line of a long query is shown too"
)


def _exploration(design_id: str, **over: object) -> AnalysisDesign:
    fields: dict = {
        "id": design_id,
        "theme_id": "LIB",
        "title": f"{design_id} の題",
        "analysis_intent": "exploratory",
        "exploration_question": f"{design_id} の探索の問い",
        "exploration_background": "背景",
        "data_scope": {
            "population": "2025年度に予約した本",
            "grain": "予約1件",
            "denominator": "取り置いた予約の全件",
        },
        "source_ids": ["lib_holds"],
        "methodology": {
            "method": "曜日ごとの集計",
            "package": "pandas",
            "steps": [{"description": LONG_SQL}],
        },
        "metrics": [
            {
                "target": "期限切れ率",
                "tier": "primary",
                "aggregation": "割合",
                "comparison": "曜日ごとに並べる",
            },
            {"target": "待ち日数", "tier": "secondary"},
        ],
        "chart": [
            {
                "intent": "comparison",
                "type": "bar",
                "description": "曜日ごとの期限切れ率",
                "x": "曜日",
                "y": "期限切れ率",
            }
        ],
    }
    fields.update(over)
    return AnalysisDesign.model_validate(fields)


def _confirmation(design_id: str, **over: object) -> AnalysisDesign:
    fields: dict = {
        "analysis_intent": "confirmatory",
        "exploration_question": None,
        "exploration_background": None,
        "hypothesis_statement": f"{design_id} の検証仮説",
        "hypothesis_background": "背景",
        "metrics": [
            {
                "target": "期限切れ率の差",
                "tier": "primary",
                "comparison": "差が5ポイント以上なら支持、1ポイント以下なら棄却",
            }
        ],
    }
    fields.update(over)
    return _exploration(design_id, **fields)


def _handed_tree() -> dict:
    """make_tree, its decision naming LIB-Q04 and LIB-Q05, each with a design to hand over."""
    tree = make_tree()
    tree["nodes"][3]["design_ids"] = ["LIB-H05"]
    tree["nodes"][4]["design_ids"] = ["LIB-H06"]
    tree["decisions"] = [
        {
            "round": 0,
            "kind": "start",
            "node_id": "LIB-Q04",
            "with_node_ids": ["LIB-Q05"],
            "reason": "互いの結果を待たずに調べられる",
        }
    ]
    return tree


def _summaries(
    stages: dict[str, AnalysisStage] | None = None,
) -> dict:
    designs = make_designs()
    for design_id in ("LIB-H05", "LIB-H06"):
        stage = (stages or {}).get(design_id, AnalysisStage.before_run)
        status = "in_review" if stage is AnalysisStage.before_run else "analyzing"
        designs[design_id] = summary(
            design_id, f"{design_id} の題", status, None, stage=stage
        )
    return designs


def _handover(**designs: AnalysisDesign) -> dict[str, HandoverDesign]:
    shown = designs or {
        "LIB-H05": _exploration("LIB-H05"),
        "LIB-H06": _confirmation("LIB-H06"),
    }
    return {d: HandoverDesign.of(design) for d, design in shown.items()}


def _page(
    handover: dict[str, HandoverDesign] | None = None,
    stages: dict[str, AnalysisStage] | None = None,
    tree: dict | None = None,
) -> Element:
    return page(
        tree=tree or _handed_tree(),
        designs=_summaries(stages),
        handover=handover or _handover(),
    )


def _section(root: Element) -> Element:
    return by_id(root, "handover")


def _row(root: Element, row: HandoverRow) -> Element:
    (found,) = [
        e for e in _section(root).walk() if e.attrs.get("data-row") == row.value
    ]
    return found


def _cells(root: Element, row: HandoverRow) -> list[str]:
    return [squash(c.text()) for c in _row(root, row).children if c.tag == "td"]


class TestWhichDesignsAreRead:
    """US-2 AC 2: the designs before their run, on the questions of the last decision."""

    def test_the_designs_on_every_question_the_decision_names_in_its_order(
        self,
    ) -> None:
        tree = build(_handed_tree())
        stages = {d: AnalysisStage.before_run for d in ("LIB-H05", "LIB-H06")}

        assert to_hand_over(tree, stages) == ["LIB-H05", "LIB-H06"]

    def test_a_design_on_a_question_the_decision_does_not_name_is_not_read(
        self,
    ) -> None:
        tree = build(_handed_tree())
        stages = {d: AnalysisStage.before_run for d in ("LIB-H01", "LIB-H05")}

        assert to_hand_over(tree, stages) == ["LIB-H05"]

    @pytest.mark.parametrize(
        "stage", [s for s in AnalysisStage if s not in READ_BEFORE_HANDOVER]
    )
    def test_a_design_past_its_hand_over_is_not_read(
        self, stage: AnalysisStage
    ) -> None:
        tree = build(_handed_tree())

        assert to_hand_over(
            tree, {"LIB-H05": stage, "LIB-H06": AnalysisStage.before_run}
        ) == ["LIB-H06"]

    def test_a_design_on_two_named_questions_is_read_once(self) -> None:
        tree = _handed_tree()
        tree["nodes"][4]["design_ids"] = ["LIB-H05"]

        assert to_hand_over(build(tree), {"LIB-H05": AnalysisStage.before_run}) == [
            "LIB-H05"
        ]

    def test_a_close_hands_nothing_over(self) -> None:
        tree = _handed_tree()
        tree["decisions"].append(
            {"round": 2, "kind": "close", "node_id": "LIB-Q04", "reason": "区切る"}
        )

        assert to_hand_over(build(tree), {"LIB-H05": AnalysisStage.before_run}) == []

    def test_no_decision_hands_nothing_over(self) -> None:
        tree = _handed_tree()
        tree["decisions"] = []

        assert to_hand_over(build(tree), {"LIB-H05": AnalysisStage.before_run}) == []


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
        assert _cells(_page(), HandoverRow.statement) == [
            "LIB-H05 の探索の問い",
            "LIB-H06 の検証仮説",
        ]

    def test_the_criterion_of_a_confirmation_and_none_for_an_exploration(
        self,
    ) -> None:
        assert _cells(_page(), HandoverRow.criterion) == [
            NO_CRITERION,
            "差が5ポイント以上なら支持、1ポイント以下なら棄却",
        ]

    def test_population_grain_and_denominator_each_on_its_own_row(self) -> None:
        root = _page()

        assert _cells(root, HandoverRow.population) == ["2025年度に予約した本"] * 2
        assert _cells(root, HandoverRow.grain) == ["予約1件"] * 2
        assert _cells(root, HandoverRow.denominator) == ["取り置いた予約の全件"] * 2

    def test_a_design_without_a_scope_says_it_is_not_written(self) -> None:
        root = _page(
            _handover(
                **{
                    "LIB-H05": _exploration("LIB-H05", data_scope=None),
                    "LIB-H06": _confirmation("LIB-H06"),
                }
            )
        )

        assert _cells(root, HandoverRow.grain)[0] == NOT_WRITTEN

    def test_the_method_the_primary_metric_and_the_chart(self) -> None:
        root = _page()

        assert _cells(root, HandoverRow.method)[0] == "曜日ごとの集計（pandas）"
        # Only the primary metric: the secondary one is not what is judged.
        assert _cells(root, HandoverRow.metric) == [
            "期限切れ率（割合）",
            "期限切れ率の差",
        ]
        assert _cells(root, HandoverRow.chart)[0] == (
            "曜日ごとの期限切れ率（bar。横: 曜日、縦: 期限切れ率）"
        )

    def test_the_extraction_is_shown_in_full(self) -> None:
        (cell, _) = [
            c for c in _row(_page(), HandoverRow.extraction).children if c.tag == "td"
        ]
        (pre,) = [e for e in cell.walk() if e.tag == "pre"]

        assert pre.text() == LONG_SQL

    def test_every_step_of_the_extraction_is_shown(self) -> None:
        design = _exploration(
            "LIB-H05",
            methodology={
                "method": "集計",
                "steps": [{"description": "SELECT 1"}, "df = df.dropna()"],
            },
        )
        root = _page(
            _handover(**{"LIB-H05": design, "LIB-H06": _confirmation("LIB-H06")})
        )

        (cell, _) = [
            c for c in _row(root, HandoverRow.extraction).children if c.tag == "td"
        ]
        assert [e.text() for e in cell.walk() if e.tag == "pre"] == [
            "SELECT 1",
            "df = df.dropna()",
        ]

    def test_what_a_design_writes_is_escaped(self) -> None:
        design = _exploration(
            "LIB-H05",
            methodology={
                "method": "集計",
                "steps": [{"description": "SELECT '</pre><script>x()</script>'"}],
            },
        )
        html = render(
            tree=_handed_tree(),
            designs=_summaries(),
            handover=_handover(
                **{"LIB-H05": design, "LIB-H06": _confirmation("LIB-H06")}
            ),
        )

        assert "<script>x()" not in html
        assert "&lt;/pre&gt;&lt;script&gt;" in html


class TestTheRowsThatDiffer:
    """US-2 AC 3: the code marks the scope and source rows whose values differ."""

    def test_the_rule_names_only_the_compared_rows_that_differ(self) -> None:
        designs = [
            HandoverDesign.of(_exploration("LIB-H05")),
            HandoverDesign.of(
                _confirmation(
                    "LIB-H06",
                    data_scope={
                        "population": "2025年度に予約した本",
                        "grain": "本1冊",
                        "denominator": "取り置いた予約の全件",
                    },
                    source_ids=["lib_holds", "lib_calendar"],
                )
            ),
        ]

        # The intent, the question and the metric differ too, but are not compared.
        assert differing_rows(designs) == (HandoverRow.grain, HandoverRow.sources)

    def test_one_design_differs_from_nothing(self) -> None:
        assert differing_rows([HandoverDesign.of(_exploration("LIB-H05"))]) == ()

    def test_the_same_sources_in_another_order_do_not_differ(self) -> None:
        designs = [
            HandoverDesign.of(_exploration("LIB-H05", source_ids=["a", "b"])),
            HandoverDesign.of(_exploration("LIB-H06", source_ids=["b", "a"])),
        ]

        assert differing_rows(designs) == ()

    def test_a_scope_written_beside_one_not_written_differs(self) -> None:
        designs = [
            HandoverDesign.of(_exploration("LIB-H05")),
            HandoverDesign.of(_exploration("LIB-H06", data_scope=None)),
        ]

        assert differing_rows(designs) == (
            HandoverRow.population,
            HandoverRow.grain,
            HandoverRow.denominator,
        )

    def test_the_compared_rows_are_the_scope_and_the_sources(self) -> None:
        assert COMPARED_ROWS == (
            HandoverRow.population,
            HandoverRow.grain,
            HandoverRow.denominator,
            HandoverRow.sources,
        )

    def test_the_page_marks_the_rows_the_rule_names(self) -> None:
        root = _page(
            _handover(
                **{
                    "LIB-H05": _exploration("LIB-H05"),
                    "LIB-H06": _confirmation(
                        "LIB-H06",
                        data_scope={
                            "population": "2025年度に予約した本",
                            "grain": "本1冊",
                            "denominator": "取り置いた予約の全件",
                        },
                    ),
                }
            )
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
        html = render(tree=_handed_tree(), designs=_summaries(), handover=_handover())
        (script,) = re.findall(r"<script>(.*?)</script>", html, re.S)

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
        html = render(tree=_handed_tree(), designs=_summaries(), handover=_handover())
        (script,) = re.findall(r"<script>(.*?)</script>", html, re.S)

        assert sends not in script

    def test_the_page_has_no_form_and_loads_nothing(self) -> None:
        root = _page()

        assert not [e for e in root.walk() if e.tag in ("form", "link", "iframe")]
        assert not [
            e for e in root.walk() if {"src", "action", "formaction"} & set(e.attrs)
        ]

    def test_a_page_with_nothing_to_hand_over_has_no_script(self) -> None:
        html = render(designs=make_designs())

        assert "<script" not in html


class TestWhereTheSectionSits:
    """The check is what the analyst does now, so it sits at the top."""

    def test_no_section_without_a_design_to_hand_over(self) -> None:
        root = _page(stages={d: AnalysisStage.running for d in ("LIB-H05", "LIB-H06")})

        assert not [e for e in root.walk() if e.attrs.get("id") == "handover"]

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
        html = render(tree=_handed_tree(), designs=designs, handover=_handover())

        ids = re.findall(r'<section[^>]* id="([a-z-]+)"', html)
        assert ids.index("asks") < ids.index("handover") < ids.index("subject-answer")
        assert ASKS_LEAD in html
