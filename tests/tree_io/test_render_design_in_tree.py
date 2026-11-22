"""Tests of ``tree_io render --design`` for a theme with a tree (Epic 28, Story 28.4, US-4 AC 4).

The design's note lives in the tree page then, so the command rewrites that page
and says where the note is and which questions link the design. Synthetic data
only (public-library holds, theme LIB).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import tree_io
from skills._shared.design_note import note_anchor
from tests.test_tree_render import by_id, parse
from tests.tree_io._support import _add, _design, _run_cli
from tests.tree_io.test_render_design import VERDICT_TEXT, _write_verdict


def _page(insight: Path) -> Path:
    return insight / "themes" / "LIB_tree.html"


class TestRenderDesignWithATree:
    def test_it_rewrites_the_tree_page_and_returns_path_anchor_and_linked_nodes(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)

        result = tree_io.render_design(design_id, base_dir=tree)

        assert result == {
            "path": str(_page(tree)),
            "anchor": note_anchor(design_id),
            "node_ids": ["LIB-Q02"],
        }
        root = parse(_page(tree).read_text("utf-8"))
        assert by_id(root, note_anchor(design_id)) is not None

    def test_the_linked_nodes_are_listed_in_tree_order_not_in_link_order(
        self, tree: Path
    ) -> None:
        _add(tree)
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q03", design_id, base_dir=tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)

        result = tree_io.render_design(design_id, base_dir=tree)

        assert result["node_ids"] == ["LIB-Q02", "LIB-Q03"]

    def test_a_design_no_question_links_has_an_anchor_and_no_nodes(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)

        result = tree_io.render_design(design_id, base_dir=tree)

        assert result == {
            "path": str(_page(tree)),
            "anchor": note_anchor(design_id),
            "node_ids": [],
        }

    def test_the_page_shows_what_the_notebook_wrote_since_the_last_render(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        tree_io.render("LIB", base_dir=tree)
        _write_verdict(tree, design_id, VERDICT_TEXT)

        tree_io.render_design(design_id, base_dir=tree)

        assert "<td>0.00010</td>" in _page(tree).read_text("utf-8")

    def test_a_standalone_page_left_by_an_earlier_run_is_removed(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        stale = tree / "notes" / f"{design_id}.html"
        stale.parent.mkdir()
        stale.write_text("old", encoding="utf-8")

        tree_io.render_design(design_id, base_dir=tree)

        assert not stale.exists()

    def test_an_unknown_design_is_an_error_and_writes_nothing(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="design 'LIB-H09' not found"):
            tree_io.render_design("LIB-H09", base_dir=tree)

        assert not _page(tree).exists()
        assert not (tree / "notes").exists()

    def test_a_tree_that_exists_but_is_invalid_is_an_error_not_a_fallback(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        path = tree / "themes" / "LIB_tree.yaml"
        path.write_text(path.read_text("utf-8").replace("LIB", "FP"), encoding="utf-8")

        with pytest.raises(ValueError, match="does not match the file name"):
            tree_io.render_design(design_id, base_dir=tree)

        assert not (tree / "notes").exists()

    def test_a_broken_note_of_another_design_stops_it_and_keeps_the_old_page(
        self, tree: Path
    ) -> None:
        design_id, other = _design(tree), _design(tree)
        tree_io.render("LIB", base_dir=tree)
        before = _page(tree).read_bytes()
        _write_verdict(tree, other, "[1, 2]")

        with pytest.raises(ValueError, match=f"analysis note of '{other}'"):
            tree_io.render_design(design_id, base_dir=tree)

        assert _page(tree).read_bytes() == before


class TestRenderDesignWithoutATree:
    def test_it_writes_the_standalone_page_and_returns_only_its_path(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)

        result = tree_io.render_design(design_id, base_dir=insight)

        assert result == {"path": str(insight / "notes" / f"{design_id}.html")}
        assert not (insight / "themes").exists()

    def test_a_design_of_another_theme_than_the_tree_stays_standalone(
        self, tree: Path
    ) -> None:
        design_id = _design(tree, theme_id="FP")

        result = tree_io.render_design(design_id, base_dir=tree)

        assert list(result) == ["path"]
        assert (tree / "notes" / f"{design_id}.html").is_file()
        assert not _page(tree).exists()


class TestRenderDesignCli:
    def test_with_a_tree_it_prints_path_anchor_and_node_ids_and_exits_0(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)

        done = _run_cli(tree, "render", "--design", design_id)

        assert done.returncode == 0, done.stderr
        printed = json.loads(done.stdout)
        assert printed["anchor"] == note_anchor(design_id)
        assert printed["node_ids"] == ["LIB-Q02"]
        assert Path(printed["path"]).resolve() == _page(tree).resolve()

    def test_without_a_tree_it_prints_only_the_path_and_exits_0(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)

        done = _run_cli(insight, "render", "--design", design_id)

        assert done.returncode == 0, done.stderr
        assert list(json.loads(done.stdout)) == ["path"]

    def test_an_unknown_design_exits_1_and_writes_nothing(self, tree: Path) -> None:
        done = _run_cli(tree, "render", "--design", "LIB-H09")

        assert done.returncode == 1
        assert done.stderr.strip() == "tree_io: design 'LIB-H09' not found"
        assert not _page(tree).exists()
