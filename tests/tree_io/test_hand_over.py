"""Tests of skills/_shared/tree_io.py (Epic 35, Story 35.3): a decision hands over several questions.

A decision names the question to investigate next and the questions handed over
with it (``with_node_ids``). ``position`` and ``progress`` read every one of them
and the stage of each analysis linked there (ADR-0061).
"""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests import _concurrent_writers
from tests.tree_io._support import _add, _design, _finish


@pytest.fixture
def handed_over(tree: Path) -> Path:
    """LIB-Q02 and LIB-Q03 under the root, both named by the start decision."""
    _add(tree, question="期限切れを一貫して数えられるか")
    _add(tree, question="取り置き待ちの人数は何人か")
    tree_io.decide(
        "LIB",
        kind="start",
        node_id="LIB-Q02",
        with_node_ids=["LIB-Q03"],
        reason="互いの結果を待たない",
        base_dir=tree,
    )
    return tree


def _designed(base: Path, node_id: str) -> str:
    design_id = _design(base)
    tree_io.link_design("LIB", node_id, design_id, base_dir=base)
    return design_id


def _running(base: Path, node_id: str) -> str:
    design_id = _designed(base, node_id)
    design_io.transition_status(design_id, "analyzing", base_dir=base)
    return design_id


class TestDecide:
    """US-1 AC 1, AC 2: a decision keeps the questions handed over with it."""

    def test_the_questions_handed_over_are_saved_with_the_decision(
        self, handed_over: Path
    ) -> None:
        saved = tree_io.load_tree("LIB", handed_over)["decisions"][-1]
        assert (saved["node_id"], saved["with_node_ids"]) == ("LIB-Q02", ["LIB-Q03"])

    def test_a_decision_that_hands_over_nothing_is_saved_without_the_key(
        self, tree: Path
    ) -> None:
        _add(tree)
        decided = tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初に", base_dir=tree
        )

        assert "with_node_ids" not in decided
        assert "with_node_ids" not in tree_io.load_tree("LIB", tree)["decisions"][-1]

    def test_a_question_outside_the_tree_is_refused_and_nothing_is_written(
        self, tree: Path
    ) -> None:
        _add(tree)
        with pytest.raises(ValueError, match="LIB-Q09"):
            tree_io.decide(
                "LIB",
                kind="start",
                node_id="LIB-Q02",
                with_node_ids=["LIB-Q09"],
                reason="最初に",
                base_dir=tree,
            )
        assert "decisions" not in tree_io.load_tree("LIB", tree)

    def test_a_saved_tree_without_questions_handed_over_is_written_back_unchanged(
        self, tree: Path
    ) -> None:
        _add(tree)
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初に", base_dir=tree
        )
        before = tree_io.load_tree("LIB", tree)

        # Any write reads the whole tree and writes it back.
        tree_io.link_design("LIB", "LIB-Q02", _design(tree), base_dir=tree)

        after = tree_io.load_tree("LIB", tree)
        assert after["decisions"] == before["decisions"]
        assert "with_node_ids" not in (tree / "themes" / "LIB_tree.yaml").read_text(
            "utf-8"
        )


class TestPosition:
    """US-1 AC 3: the position reads every question the last decision named."""

    def test_one_finished_analysis_beside_a_running_one_is_still_in_progress(
        self, handed_over: Path
    ) -> None:
        finished = _designed(handed_over, "LIB-Q02")
        _finish(handed_over, finished)
        running = _running(handed_over, "LIB-Q03")

        position = tree_io.position("LIB", base_dir=handed_over)

        assert position["state"] == "in_progress"
        assert position["design_ids"] == [running]
        assert position["node_ids"] == ["LIB-Q02", "LIB-Q03"]
        assert position["nodes"] == [
            {
                "node_id": "LIB-Q02",
                "designs": [{"design_id": finished, "stage": "finished"}],
            },
            {
                "node_id": "LIB-Q03",
                "designs": [{"design_id": running, "stage": "running"}],
            },
        ]

    def test_every_analysis_finished_on_every_question_is_concluded(
        self, handed_over: Path
    ) -> None:
        first = _designed(handed_over, "LIB-Q02")
        second = _designed(handed_over, "LIB-Q03")
        _finish(handed_over, first)
        _finish(handed_over, second)

        position = tree_io.position("LIB", base_dir=handed_over)
        assert (position["state"], position["design_ids"]) == (
            "concluded",
            [first, second],
        )

    def test_a_stopped_analysis_does_not_hold_the_walk(self, handed_over: Path) -> None:
        finished = _designed(handed_over, "LIB-Q02")
        _finish(handed_over, finished)
        stopped = _running(handed_over, "LIB-Q03")
        design_io.stop_analysis(stopped, "分母が合わない", base_dir=handed_over)

        position = tree_io.position("LIB", base_dir=handed_over)

        assert (position["state"], position["design_ids"]) == (
            "concluded",
            [finished, stopped],
        )
        assert position["nodes"][1]["designs"] == [
            {"design_id": stopped, "stage": "stopped"}
        ]

    def test_a_question_handed_over_without_a_design_keeps_the_walk_open(
        self, handed_over: Path
    ) -> None:
        """A question left without a design is not dropped (Decisions, 35.3)."""
        finished = _designed(handed_over, "LIB-Q02")
        _finish(handed_over, finished)

        position = tree_io.position("LIB", base_dir=handed_over)

        assert (position["state"], position["design_ids"]) == ("not_started", [])
        assert position["undesigned_node_ids"] == ["LIB-Q03"]

    def test_every_question_with_a_design_since_the_decision_has_none_undesigned(
        self, handed_over: Path
    ) -> None:
        _finish(handed_over, _designed(handed_over, "LIB-Q02"))
        _finish(handed_over, _designed(handed_over, "LIB-Q03"))

        assert (
            tree_io.position("LIB", base_dir=handed_over)["undesigned_node_ids"] == []
        )

    def test_a_question_without_a_design_lists_none(self, handed_over: Path) -> None:
        running = _running(handed_over, "LIB-Q02")

        position = tree_io.position("LIB", base_dir=handed_over)

        assert position["design_ids"] == [running]
        assert position["nodes"][1] == {"node_id": "LIB-Q03", "designs": []}

    def test_a_design_on_two_named_questions_is_named_once(
        self, handed_over: Path
    ) -> None:
        running = _running(handed_over, "LIB-Q02")
        tree_io.link_design("LIB", "LIB-Q03", running, base_dir=handed_over)

        assert tree_io.position("LIB", base_dir=handed_over)["design_ids"] == [running]

    def test_a_decision_that_hands_over_nothing_names_its_own_question(
        self, tree: Path
    ) -> None:
        _add(tree)
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初に", base_dir=tree
        )

        position = tree_io.position("LIB", base_dir=tree)
        assert (position["node_id"], position["node_ids"]) == ("LIB-Q02", ["LIB-Q02"])
        assert position["nodes"] == [{"node_id": "LIB-Q02", "designs": []}]


class TestProgress:
    """US-3 AC 4: tree_io progress folds the stage of every analysis on a question."""

    def test_a_question_whose_every_analysis_was_stopped_is_stopped(
        self, handed_over: Path
    ) -> None:
        stopped = _designed(handed_over, "LIB-Q02")
        design_io.stop_analysis(stopped, "任せない", base_dir=handed_over)

        progress = tree_io.progress("LIB", base_dir=handed_over)

        assert progress["LIB-Q02"]["progress"] == "stopped"
        assert progress["LIB-Q02"]["designs"] == [
            {"design_id": stopped, "stage": "stopped"}
        ]
        assert progress["LIB-Q01"]["below"] == {"stopped": 1, "not_started": 1}

    def test_a_stopped_analysis_beside_a_finished_one_is_analyzed(
        self, handed_over: Path
    ) -> None:
        _finish(handed_over, _designed(handed_over, "LIB-Q02"))
        stopped = _designed(handed_over, "LIB-Q02")
        design_io.stop_analysis(stopped, "任せない", base_dir=handed_over)

        assert tree_io.progress("LIB", base_dir=handed_over)["LIB-Q02"]["progress"] == (
            "analyzed"
        )


ROUNDS = 10


class TestConcurrentWrites:
    """US-5 AC 1 (tree_io): two processes linking at once both keep their links."""

    def test_two_processes_linking_at_once_keep_every_link(self, tree: Path) -> None:
        _add(tree)
        designs = [_design(tree) for _ in range(2 * ROUNDS)]
        start_at = time.time() + 2.0
        context = multiprocessing.get_context("spawn")
        with context.Pool(2) as pool:
            runs = [
                pool.apply_async(
                    _concurrent_writers.link_designs,
                    (str(tree), "LIB-Q02", half, start_at),
                )
                for half in (designs[0::2], designs[1::2])
            ]
            for run in runs:
                run.get(timeout=60)

        node = tree_io.load_tree("LIB", tree)["nodes"][1]
        assert sorted(node["design_ids"]) == sorted(designs)

    def test_two_processes_copying_one_hearing_at_once_write_it_once(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _designed(tree, "LIB-Q02")
        tree_io.candidate("LIB", "LIB-Q02", ask="取消はどれくらいか", base_dir=tree)
        tree_io.hear(
            "LIB",
            "LIB-Q02",
            answer="月に十数件",
            answered_by="窓口の職員",
            answered_at="2026-11-21",
            base_dir=tree,
        )
        start_at = time.time() + 2.0
        context = multiprocessing.get_context("spawn")
        with context.Pool(2) as pool:
            runs = [
                pool.apply_async(
                    _concurrent_writers.copy_hearings,
                    (str(tree), "LIB-Q02", design_id, ROUNDS, start_at),
                )
                for _ in range(2)
            ]
            copied = [c for run in runs for c in run.get(timeout=60)]

        assert copied.count(True) == 1
        events = design_io.journal_events(design_id, tree)
        assert [e["type"] for e in events] == ["hearing"]
