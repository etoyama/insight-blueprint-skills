"""Fixtures shared by the tests of skills/_shared/tree_io.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.tree_io._support import (
    AIM,
    ROOT_QUESTION,
    _add,
    _design,
)


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    return tmp_path / ".insight"


@pytest.fixture
def tree(insight: Path) -> Path:
    """A base dir that already holds the LIB tree with its root question."""
    tree_io.create_tree(
        theme_id="LIB", question=ROOT_QUESTION, aim=AIM, base_dir=insight
    )
    return insight


@pytest.fixture
def world(tree: Path) -> Path:
    """LIB-Q02 and LIB-Q03 under the root, each with a design and a journal."""
    for node_id in ("LIB-Q02", "LIB-Q03"):
        _add(tree, question=f"{node_id} の問い")
        design_id = _design(tree)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {
                        "id": f"{design_id}-E01",
                        "type": "observe",
                        "content": f"{design_id} は期限切れ152件、取消除外後34.6%",
                    }
                ]
            },
            base_dir=tree,
        )
    return tree
