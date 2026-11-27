"""Tests of skills/_shared/tree_io.py (Epic 35, Story 35.4): ``render`` reads the stages from the records.

The stage, the reason a design was stopped and what a confirmation asks come
from the design and its journal as ``design_io`` wrote them, and the page,
``progress`` and ``position`` say the same of the same question (US-3 AC 4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.tree import Progress
from skills._shared import design_io, tree_io
from skills._shared.tree_words import (
    PROGRESS_WORDS,
    STAGE_WORDS,
    STOP_REASON,
    WHAT_IS_ASKED,
    asks_heading,
)
from tests._tree_page import (
    Element,
    branch_cards,
    by_id,
    card_text,
    node_card,
    parse,
    squash,
)
from tests.tree_io._support import _add, _design, _rendered

ASKED = "予約の記録が2025年10月より前に無い。対象を変えてよいか"
WHY = "通知の時刻が記録されていなかった"


@pytest.fixture
def staged(tree: Path) -> Path:
    """LIB-Q02 waits for the analyst, LIB-Q03 was stopped, LIB-Q04 is running.

    A start decision hands over all three.
    """
    for question in ("予約者の待ち", "曜日ごとの通知時刻", "開館日数"):
        _add(tree, question=question)
    tree_io.decide(
        "LIB",
        kind="start",
        node_id="LIB-Q02",
        with_node_ids=["LIB-Q03", "LIB-Q04"],
        reason="互いの結果を待たない",
        base_dir=tree,
    )
    for node_id in ("LIB-Q02", "LIB-Q03", "LIB-Q04"):
        design_id = _design(tree)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        design_io.transition_status(design_id, "analyzing", base_dir=tree)
    design_io.ask_analyst("LIB-H01", ASKED, base_dir=tree)
    design_io.stop_analysis("LIB-H02", WHY, base_dir=tree)
    return tree


def _page(base: Path) -> Element:
    return parse(_rendered(base))


def test_each_card_says_the_stage_read_from_the_journal(staged: Path) -> None:
    root = _page(staged)

    for node_id, stage in (
        ("LIB-Q02", AnalysisStage.awaiting_confirmation),
        ("LIB-Q03", AnalysisStage.stopped),
        ("LIB-Q04", AnalysisStage.running),
    ):
        (card,) = branch_cards(root, node_id)
        assert STAGE_WORDS[stage][0] in card_text(card)


def test_the_stopped_card_quotes_the_reason_the_stop_wrote(staged: Path) -> None:
    (card,) = branch_cards(_page(staged), "LIB-Q03")

    assert f"{STOP_REASON}: {WHY}" in card_text(card)


def test_the_confirmation_leads_the_page_until_it_is_answered(staged: Path) -> None:
    asks = squash(by_id(_page(staged), "asks").text())
    assert asks.startswith(asks_heading(1))
    assert f"{WHAT_IS_ASKED}: {ASKED}" in asks

    (question,) = [
        e
        for e in design_io.journal_events("LIB-H01", staged)
        if e["type"] == "question"
    ]
    design_io.answer_analyst(
        "LIB-H01", question["id"], "対象を変えてよい", base_dir=staged
    )

    root = _page(staged)
    assert not [e for e in root.walk() if e.attrs.get("id") == "asks"]
    (card,) = branch_cards(root, "LIB-Q02")
    assert WHAT_IS_ASKED not in card_text(card)


def test_the_page_progress_and_position_agree_on_each_question(staged: Path) -> None:
    root = _page(staged)
    progress = tree_io.progress("LIB", base_dir=staged)
    position = tree_io.position("LIB", base_dir=staged)
    stages = {
        d["design_id"]: d["stage"] for n in position["nodes"] for d in n["designs"]
    }

    for node_id in ("LIB-Q02", "LIB-Q03", "LIB-Q04"):
        word = PROGRESS_WORDS[Progress(progress[node_id]["progress"])][0]
        assert f"進捗: {word}" in squash(node_card(root, node_id).text())
        for design in progress[node_id]["designs"]:
            assert stages[design["design_id"]] == design["stage"]
            (card,) = branch_cards(root, node_id)
            assert STAGE_WORDS[AnalysisStage(design["stage"])][0] in card_text(card)
    assert progress["LIB-Q03"]["progress"] == Progress.stopped


def test_the_next_question_names_every_question_handed_over(staged: Path) -> None:
    shown = squash(by_id(_page(staged), "next-question").text())

    assert "LIB-Q02 予約者の待ち、LIB-Q03 曜日ごとの通知時刻、LIB-Q04 開館日数" in shown
