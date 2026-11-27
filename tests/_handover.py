"""Designs and a tree the tests of the check before a hand-over share (Epic 35, Story 35.5).

Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

from insight_blueprint.models.design import AnalysisDesign
from tests._tree_page import make_tree

LONG_SQL = (
    "SELECT hold_id, branch_id, ready_on, picked_up_on\n"
    "FROM {source:lib_holds}\n"
    "WHERE ready_on BETWEEN '2025-04-01' AND '2026-03-31'\n"
    "  AND status IN ('picked_up', 'expired')\n"
    "  AND branch_id IN ('central', 'east', 'west', 'north', 'south', 'harbor')\n"
    "-- the last line of a long query is shown too"
)


def exploration(design_id: str, **over: object) -> AnalysisDesign:
    """An exploration that writes every row of the check."""
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


def confirmation(design_id: str, **over: object) -> AnalysisDesign:
    """A confirmation with its criterion, otherwise as ``exploration``."""
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
    return exploration(design_id, **fields)


def handed_tree() -> dict:
    """make_tree, its decision naming LIB-Q04 and LIB-Q05, linked to LIB-H05 and LIB-H06."""
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
