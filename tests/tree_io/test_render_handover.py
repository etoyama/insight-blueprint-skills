"""Tests of skills/_shared/tree_io.py (Epic 35, Story 35.5): the check before a hand-over.

``render`` lays out the designs as ``design_io`` saved them (US-2 AC 2) and
marks the rows that differ (AC 3). ``handover`` gives the same designs and the
same rows to the driver, which sums them up in the chat (ADR-0063 5): the rule
is the page's, so the two cannot disagree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared.handover import HandoverRow
from skills._shared.tree_words import DIFFERS_WORD, HANDOVER_ROW_WORDS
from tests._tree_page import Element, by_id, has_class, parse, squash
from tests.tree_io._support import _add, _rendered, _run_cli

SQL = (
    "SELECT hold_id, ready_on, picked_up_on\n"
    "FROM {source:lib_holds}\n"
    "WHERE ready_on >= '2025-04-01'"
)


def _exploration(base: Path, question: str, grain: str) -> str:
    return design_io.create_design(
        theme_id="LIB",
        title=question,
        analysis_intent="exploratory",
        exploration_question=question,
        exploration_background="背景",
        methodology={"method": "集計", "steps": [{"description": SQL}]},
        data_scope={
            "population": "2025年度に予約した本",
            "grain": grain,
            "denominator": "取り置いた予約の全件",
        },
        source_ids=["lib_holds"],
        base_dir=base,
    )["id"]


@pytest.fixture
def handed(tree: Path) -> Path:
    """A start decision names LIB-Q02 and LIB-Q03, each with a design not yet run.

    The two count by another grain.
    """
    for question in ("予約者の待ち", "曜日ごとの通知時刻"):
        _add(tree, question=question)
    tree_io.decide(
        "LIB",
        kind="start",
        node_id="LIB-Q02",
        with_node_ids=["LIB-Q03"],
        reason="互いの結果を待たない",
        base_dir=tree,
    )
    for node_id, grain in (("LIB-Q02", "予約1件"), ("LIB-Q03", "本1冊")):
        design_id = _exploration(tree, f"{node_id} の探索の問い", grain)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
    return tree


def _row(root: Element, row: HandoverRow) -> Element:
    (found,) = [
        e for e in by_id(root, "handover").walk() if e.attrs.get("data-row") == row
    ]
    return found


def test_the_page_lays_out_the_saved_designs_side_by_side(handed: Path) -> None:
    root = parse(_rendered(handed))

    cells = [
        squash(c.text())
        for c in _row(root, HandoverRow.statement).children
        if c.tag == "td"
    ]
    assert cells == ["LIB-Q02 の探索の問い", "LIB-Q03 の探索の問い"]
    (pre, _) = [e for e in _row(root, HandoverRow.extraction).walk() if e.tag == "pre"]
    assert pre.text() == SQL


def test_the_page_marks_the_grain_the_two_count_by(handed: Path) -> None:
    root = parse(_rendered(handed))

    grain = _row(root, HandoverRow.grain)
    assert has_class(grain, "differs")
    assert DIFFERS_WORD in squash(grain.text())
    assert not has_class(_row(root, HandoverRow.population), "differs")


def test_handover_names_the_designs_and_the_rows_that_differ(handed: Path) -> None:
    assert tree_io.handover("LIB", base_dir=handed) == {
        "design_ids": ["LIB-H01", "LIB-H02"],
        "differing": [
            {
                "row": "grain",
                "label": HANDOVER_ROW_WORDS[HandoverRow.grain],
                "values": {"LIB-H01": "予約1件", "LIB-H02": "本1冊"},
            }
        ],
        "no_data_scope": [],
    }


def test_handover_names_the_designs_that_state_no_data_scope(handed: Path) -> None:
    """US-7 AC 2: such a design is not read before a hand-over until it states one."""
    bare = design_io.create_design(
        theme_id="LIB",
        title="範囲を書いていない",
        analysis_intent="exploratory",
        exploration_question="通知は何曜日に多いか",
        exploration_background="背景",
        methodology={"method": "集計"},
        base_dir=handed,
    )["id"]
    tree_io.link_design("LIB", "LIB-Q03", bare, base_dir=handed)

    assert tree_io.handover("LIB", base_dir=handed)["no_data_scope"] == [bare]


def test_handover_runs_from_the_command_line(handed: Path) -> None:
    result = _run_cli(handed, "handover", "--theme", "LIB")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["design_ids"] == ["LIB-H01", "LIB-H02"]


def test_once_handed_over_nothing_is_read_before_it(handed: Path) -> None:
    for design_id in ("LIB-H01", "LIB-H02"):
        design_io.transition_status(design_id, "analyzing", base_dir=handed)

    assert tree_io.handover("LIB", base_dir=handed) == {
        "design_ids": [],
        "differing": [],
        "no_data_scope": [],
    }
    assert 'id="handover"' not in _rendered(handed)
