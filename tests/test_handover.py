"""Tests of the rule of the check before a hand-over (Epic 35, Story 35.5).

Which designs the analyst reads before the hand-over (US-2 AC 2), what each
row holds, and which rows differ between them (AC 3). The page and
``tree_io handover`` both read this rule. Synthetic data only.
"""

from __future__ import annotations

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from skills._shared.handover import (
    READ_BEFORE_HANDOVER,
    Absent,
    ChartPlan,
    HandoverDesign,
    HandoverRow,
    differing_rows,
    to_hand_over,
)
from tests._handover import LONG_SQL, confirmation, exploration, handed_tree
from tests._tree_page import build

BEFORE = AnalysisStage.before_run


class TestWhichDesignsAreRead:
    """US-2 AC 2: the designs before their run, on the questions of the last decision."""

    def test_the_designs_on_every_question_the_decision_names_in_its_order(
        self,
    ) -> None:
        stages = {"LIB-H05": BEFORE, "LIB-H06": BEFORE}

        assert to_hand_over(build(handed_tree()), stages) == ["LIB-H05", "LIB-H06"]

    def test_a_design_on_a_question_the_decision_does_not_name_is_not_read(
        self,
    ) -> None:
        stages = {"LIB-H01": BEFORE, "LIB-H05": BEFORE}

        assert to_hand_over(build(handed_tree()), stages) == ["LIB-H05"]

    @pytest.mark.parametrize(
        "stage", [s for s in AnalysisStage if s not in READ_BEFORE_HANDOVER]
    )
    def test_a_design_past_its_hand_over_is_not_read(
        self, stage: AnalysisStage
    ) -> None:
        stages = {"LIB-H05": stage, "LIB-H06": BEFORE}

        assert to_hand_over(build(handed_tree()), stages) == ["LIB-H06"]

    def test_a_design_on_two_named_questions_is_read_once(self) -> None:
        tree = handed_tree()
        tree["nodes"][4]["design_ids"] = ["LIB-H05"]

        assert to_hand_over(build(tree), {"LIB-H05": BEFORE}) == ["LIB-H05"]

    def test_a_close_hands_nothing_over(self) -> None:
        tree = handed_tree()
        tree["decisions"].append(
            {"round": 2, "kind": "close", "node_id": "LIB-Q04", "reason": "区切る"}
        )

        assert to_hand_over(build(tree), {"LIB-H05": BEFORE}) == []

    def test_no_decision_hands_nothing_over(self) -> None:
        tree = handed_tree()
        tree["decisions"] = []

        assert to_hand_over(build(tree), {"LIB-H05": BEFORE}) == []


class TestWhatEachRowHolds:
    """US-2 AC 2: each row holds what the design writes, or why it holds nothing."""

    def test_an_exploration_has_no_criterion_and_a_confirmation_has_its_own(
        self,
    ) -> None:
        explored = HandoverDesign.of(exploration("LIB-H05"))
        confirmed = HandoverDesign.of(confirmation("LIB-H06"))

        assert explored.values[HandoverRow.criterion] is Absent.not_judged
        assert confirmed.values[HandoverRow.criterion] == (
            "差が5ポイント以上なら支持、1ポイント以下なら棄却"
        )

    def test_a_confirmation_without_its_criterion_does_not_write_it(self) -> None:
        design = confirmation(
            "LIB-H06", metrics=[{"target": "期限切れ率の差", "tier": "primary"}]
        )

        assert HandoverDesign.of(design).values[HandoverRow.criterion] is (
            Absent.not_written
        )

    def test_a_design_without_a_scope_does_not_write_it(self) -> None:
        values = HandoverDesign.of(exploration("LIB-H05", data_scope=None)).values

        assert {values[r] for r in (HandoverRow.population, HandoverRow.grain)} == {
            Absent.not_written
        }

    def test_the_extraction_holds_each_step_in_full(self) -> None:
        design = exploration(
            "LIB-H05",
            methodology={
                "method": "集計",
                "steps": [{"description": LONG_SQL}, "df = df.dropna()"],
            },
        )

        assert HandoverDesign.of(design).values[HandoverRow.extraction] == (
            LONG_SQL,
            "df = df.dropna()",
        )

    def test_a_query_written_as_one_text_is_still_read(self) -> None:
        design = exploration(
            "LIB-H05", methodology={"method": "集計", "steps": "SELECT 1"}
        )

        assert HandoverDesign.of(design).values[HandoverRow.extraction] == ("SELECT 1",)

    def test_a_chart_holds_what_it_shows_its_kind_and_axes(self) -> None:
        values = HandoverDesign.of(exploration("LIB-H05")).values

        assert values[HandoverRow.chart] == (
            ChartPlan("曜日ごとの期限切れ率", "bar", "曜日", "期限切れ率"),
        )


class TestTheRowsThatDiffer:
    """US-2 AC 3: the scope and source rows whose values differ."""

    def test_only_the_scope_and_source_rows_are_compared(self) -> None:
        designs = [
            HandoverDesign.of(exploration("LIB-H05")),
            HandoverDesign.of(
                confirmation(
                    "LIB-H06",
                    data_scope={
                        "population": "2025年度に予約した本",
                        "grain": "本1冊",
                        "denominator": "取り置いた予約の全件",
                    },
                    source_ids=["lib_holds", "lib_calendar"],
                    methodology={"method": "差の検定"},
                )
            ),
        ]

        # The intent, the question, the method and the metric differ too.
        assert differing_rows(designs) == (HandoverRow.grain, HandoverRow.sources)

    def test_one_design_differs_from_nothing(self) -> None:
        assert differing_rows([HandoverDesign.of(exploration("LIB-H05"))]) == ()

    def test_the_same_sources_in_another_order_do_not_differ(self) -> None:
        designs = [
            HandoverDesign.of(exploration("LIB-H05", source_ids=["a", "b"])),
            HandoverDesign.of(exploration("LIB-H06", source_ids=["b", "a"])),
        ]

        assert differing_rows(designs) == ()

    def test_a_scope_written_beside_one_not_written_differs(self) -> None:
        designs = [
            HandoverDesign.of(exploration("LIB-H05")),
            HandoverDesign.of(exploration("LIB-H06", data_scope=None)),
        ]

        assert differing_rows(designs) == (
            HandoverRow.population,
            HandoverRow.grain,
            HandoverRow.denominator,
        )
