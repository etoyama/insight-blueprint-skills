"""Tests of ``tree_io render --theme`` placing the analysis notes under the tree (Epic 28, Story 28.4).

The page is one file: the question tree, then the note of every design of the
theme. Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared._atomic import atomic_write_yaml
from tests.test_tree_render import by_id, parse
from tests.tree_io._support import _add, _design, _rendered, _run_cli
from tests.tree_io.test_render_design import (
    VERDICT_TEXT,
    _entry,
    _figure,
    _write_verdict,
)


def _ids(page: str) -> set[str]:
    return {e.attrs["id"] for e in parse(page).walk() if "id" in e.attrs}


def _hrefs(page: str) -> list[str]:
    return [
        e.attrs["href"]
        for e in parse(page).walk()
        if e.tag == "a" and "href" in e.attrs
    ]


class TestNotesUnderTheTree:
    def test_every_design_of_the_theme_has_a_note_linked_or_not_run_or_not(
        self, tree: Path
    ) -> None:
        _add(tree)
        linked, unlinked = _design(tree), _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", linked, base_dir=tree)
        _write_verdict(tree, linked, VERDICT_TEXT)
        _design(tree, theme_id="FP")

        page = _rendered(tree)

        notes = by_id(parse(page), "design-notes")
        ids = [e.attrs["id"] for e in notes.children if e.tag == "section"]
        assert ids == [f"note-{linked}", f"note-{unlinked}"]
        assert "notebook をまだ実行していない（verdict が無い）。" in page
        assert "FP-H01" not in page

    def test_every_in_page_link_lands_on_an_element_of_the_page(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)

        page = _rendered(tree)

        hrefs = _hrefs(page)
        assert hrefs
        assert all(h.startswith("#") for h in hrefs), hrefs
        assert {h[1:] for h in hrefs} <= _ids(page)

    def test_two_runs_write_the_same_bytes_with_a_verdict_and_a_figure(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        _figure(tree, f"{design_id}_fig01.png")
        _write_verdict(
            tree,
            design_id,
            VERDICT_TEXT.replace(
                '"figures": []',
                f'"figures": [{json.dumps(_entry(f"{design_id}_fig01.png"))}]',
            ),
        )

        first = _rendered(tree)

        assert "data:image/png;base64," in first
        assert _rendered(tree) == first

    def test_a_changed_verdict_changes_the_page(self, tree: Path) -> None:
        design_id = _design(tree)
        _write_verdict(tree, design_id, VERDICT_TEXT)
        before = _rendered(tree)

        _write_verdict(tree, design_id, VERDICT_TEXT.replace("0.00010", "0.00020"))

        after = _rendered(tree)
        assert "<td>0.00020</td>" in after
        assert after != before

    def test_the_page_holds_neither_the_base_dir_nor_a_timestamp_of_generation(
        self, tree: Path
    ) -> None:
        _design(tree)

        page = _rendered(tree)

        assert str(tree.parent) not in page
        assert not re.search(r"generated|生成日時|生成した", page)

    def test_a_broken_verdict_stops_the_whole_page_naming_the_design_and_keeps_the_old_file(
        self, tree: Path
    ) -> None:
        good, broken = _design(tree), _design(tree)
        old = _rendered(tree)
        old_bytes = (tree / "themes" / "LIB_tree.html").read_bytes()
        _write_verdict(tree, broken, "[1, 2]")

        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 1
        assert f"analysis note of '{broken}' cannot be built" in done.stderr
        assert f"{broken}_verdict.json" in done.stderr
        assert good not in done.stderr
        assert (tree / "themes" / "LIB_tree.html").read_bytes() == old_bytes
        assert old

    def test_the_standalone_page_of_each_design_under_the_tree_is_removed(
        self, tree: Path
    ) -> None:
        first, second = _design(tree), _design(tree)
        notes = tree / "notes"
        notes.mkdir()
        for design_id in (first, second, "FP-H01"):
            (notes / f"{design_id}.html").write_text("old", encoding="utf-8")

        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 0, done.stderr
        assert not (notes / f"{first}.html").exists()
        assert not (notes / f"{second}.html").exists()
        assert (notes / "FP-H01.html").read_text("utf-8") == "old"

    def test_a_failed_render_keeps_the_standalone_pages(self, tree: Path) -> None:
        good, broken = _design(tree), _design(tree)
        _write_verdict(tree, broken, "[1, 2]")
        notes = tree / "notes"
        notes.mkdir()
        (notes / f"{good}.html").write_text("old", encoding="utf-8")

        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 1
        assert (notes / f"{good}.html").read_text("utf-8") == "old"

    def test_a_design_is_known_by_its_file_name_in_its_note_too(
        self, tree: Path
    ) -> None:
        _add(tree)
        first = _design(tree)
        copied = dict(design_io.load_design(first, base_dir=tree))
        copied["title"] = "写した分析設計"
        atomic_write_yaml(tree / "designs" / "LIB-H02_hypothesis.yaml", copied)

        page = _rendered(tree)

        assert [
            e.attrs["id"]
            for e in by_id(parse(page), "design-notes").children
            if e.tag == "section"
        ] == [
            "note-LIB-H01",
            "note-LIB-H02",
        ]
        assert "分析ノート LIB-H02 写した分析設計" in page

    def test_a_design_with_a_status_the_schema_does_not_know_names_the_design(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        stored = dict(design_io.load_design(design_id, base_dir=tree))
        stored["status"] = "finished"
        atomic_write_yaml(tree / "designs" / f"{design_id}_hypothesis.yaml", stored)

        with pytest.raises(ValueError, match=f"{design_id}.*finished"):
            tree_io.render("LIB", base_dir=tree)
