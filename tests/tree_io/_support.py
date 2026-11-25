"""Helpers shared by the tests of skills/_shared/tree_io.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from skills._shared import design_io, tree_io

ROOT_QUESTION = "取り置き期限を延ばす試行をするか"


AIM = {
    "kind": "business",
    "decision_maker": "図書館員",
    "decision": "取り置き期限を延ばす試行を始めるか",
}


def _add(insight: Path, **over: object) -> dict:
    kwargs: dict = {
        "question": "期限切れを一貫して数えられるか",
        "parent_question_id": "LIB-Q01",
        "contribution": "予約取消が混ざると、延長で改善しうる件数が変わる",
        "base_dir": insight,
    }
    kwargs.update(over)
    return tree_io.add_node("LIB", **kwargs)


def _design(insight: Path, theme_id: str = "LIB", parent_id: str | None = None) -> str:
    design = design_io.create_design(
        theme_id=theme_id,
        title="Test",
        hypothesis_statement="X improves Y",
        hypothesis_background="because Z",
        methodology={"method": "OLS"},
        # A confirmation takes a verdict only with its criterion written (ADR-0053).
        metrics=[{"target": "Y", "tier": "primary", "comparison": "Y rises by 5%"}],
        parent_id=parent_id,
        base_dir=insight,
    )
    return design["id"]


def _finish(insight: Path, design_id: str) -> None:
    design_io.transition_status(design_id, "supported", base_dir=insight)


def _derived(insight: Path, parent_id: str) -> str:
    return _design(insight, parent_id=parent_id)


def _linked(insight: Path) -> dict[str, list[str]]:
    nodes = tree_io.load_tree("LIB", base_dir=insight)["nodes"]
    return {n["id"]: n.get("design_ids") or [] for n in nodes}


def _run_cli(insight: Path, *args: str, payload: dict | None = None):
    return subprocess.run(
        [sys.executable, "-m", "skills._shared.tree_io", *args]
        + ["--base-dir", str(insight)],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
    )


def _rendered(insight: Path) -> str:
    return Path(tree_io.render("LIB", base_dir=insight)["path"]).read_text("utf-8")


def _entry(node_id: str, text: str, cite: str = "LIB-H01-E01") -> dict:
    return {
        "node_id": node_id,
        "statements": [{"kind": "claim", "text": text, "cites": [cite]}],
    }
