"""Tests of skills/_shared/tree_io.py (Epic 18): ``render``: the generated view of the tree.

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared._atomic import atomic_write_yaml
from tests.test_tree_render import by_id, parse
from tests.tree_io._support import (
    ROOT_QUESTION,
    _add,
    _design,
    _rendered,
    _run_cli,
)


def _tree_text(insight: Path) -> str:
    """The text of the question tree alone: the notes below it list whole journals."""
    page = (insight / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
    return by_id(parse(page), "question-tree").text()


class TestRender:
    def _answered(self, insight: Path) -> str:
        """LIB-Q02 linked to a design and answered with a citation; returns the design id."""
        _add(insight)
        design_id = _design(insight)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=insight)
        stored = tree_io.load_tree("LIB", base_dir=insight)
        stored["nodes"][1]["answers"] = [
            {
                "round": 1,
                "root_revision": 1,
                "statements": [
                    {
                        "kind": "claim",
                        "text": "取消を除くと期限切れは 346 件",
                        "cites": [f"{design_id}-E01"],
                    }
                ],
            }
        ]
        atomic_write_yaml(insight / "themes" / "LIB_tree.yaml", stored)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {
                        "id": f"{design_id}-E01",
                        "type": "evidence",
                        "content": "期限切れは取消除外で 346 件",
                        "metadata": {"direction": "supports"},
                    }
                ]
            },
            base_dir=insight,
        )
        return design_id

    def test_writes_the_html_next_to_the_tree_and_returns_its_path(
        self, tree: Path
    ) -> None:
        result = tree_io.render("LIB", base_dir=tree)

        path = tree / "themes" / "LIB_tree.html"
        assert result == {"path": str(path)}
        text = path.read_text(encoding="utf-8")
        assert ROOT_QUESTION in text
        assert "<script" not in text

    def test_a_saved_tree_keeps_its_keys_and_is_shown_in_the_analysts_words(
        self, tree: Path
    ) -> None:
        """Epic 34 US-5 AC 3: the words change on the page, not in the YAML."""
        self._answered(tree)
        saved = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")

        tree_io.render("LIB", base_dir=tree)

        page = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        shown = by_id(parse(page), "header").text() + _tree_text(tree)
        assert "主題: " in shown
        assert "これまでわかっていること" in shown
        after = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")
        assert after == saved
        assert "root_revisions:" in after
        assert "kind: claim" in after

    def test_a_stale_answer_that_no_longer_matches_the_record_is_marked(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {"id": f"{design_id}-E01", "type": "evidence", "content": "x"}
                ]
            },
            base_dir=tree,
        )

        shown = _rendered(tree)

        assert 'class="mark">記録と合わない答え' in shown
        assert "number-not-cited" in shown
        stored = tree_io.load_tree("LIB", tree)["nodes"][1]["answers"]
        assert len(stored) == 1  # the answer is marked on the page, never withdrawn

    def test_a_cited_journal_that_is_not_a_mapping_stops_render_naming_the_file(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)
        journal = tree / "designs" / f"{design_id}_journal.yaml"
        journal.write_text(f"- id: {design_id}-E01\n", encoding="utf-8")

        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 1
        assert f"{design_id}_journal.yaml is not a mapping" in done.stderr
        assert not (tree / "themes" / "LIB_tree.html").exists()

    def test_an_answer_that_matches_the_record_carries_no_mark(
        self, tree: Path
    ) -> None:
        self._answered(tree)

        shown = _rendered(tree)

        assert "取消を除くと期限切れは 346 件" in shown
        assert "check-notice" not in shown
        assert 'class="mark">記録と合わない答え' not in shown

    def test_a_check_that_cannot_run_still_writes_a_page_that_says_so(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)
        event = {"id": f"{design_id}-E01", "type": "evidence", "content": "346 件"}
        design_io.write_journal(design_id, {"events": [event, event]}, base_dir=tree)

        shown = _rendered(tree)

        assert 'id="check-notice"' in shown
        assert "appears twice" in shown
        assert "取消を除くと期限切れは 346 件" in shown

    def test_rendering_twice_gives_identical_bytes(self, tree: Path) -> None:
        self._answered(tree)
        tree_io.render("LIB", base_dir=tree)
        first = (tree / "themes" / "LIB_tree.html").read_bytes()

        tree_io.render("LIB", base_dir=tree)

        assert (tree / "themes" / "LIB_tree.html").read_bytes() == first

    def test_shows_the_cited_event_and_the_design_of_the_theme(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)

        tree_io.render("LIB", base_dir=tree)

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        assert "期限切れは取消除外で 346 件" in text
        assert "direction: supports" in text
        assert f'id="design-{design_id}"' in text

    def test_a_tree_without_answers_or_designs_renders(self, tree: Path) -> None:
        tree_io.render("LIB", base_dir=tree)

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        assert "まだ答えていない" in text

    def test_designs_of_another_theme_are_not_shown(self, tree: Path) -> None:
        other = _design(tree, theme_id="FP")

        tree_io.render("LIB", base_dir=tree)

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        assert other not in text

    def test_an_event_counts_only_in_the_journal_its_id_names(self, tree: Path) -> None:
        design_id = self._answered(tree)
        other = _design(tree)
        design_io.write_journal(
            other,
            {
                "events": [
                    {
                        "id": f"{design_id}-E01",
                        "type": "evidence",
                        "content": "別の journal に書いた同じ id",
                    }
                ]
            },
            base_dir=tree,
        )
        design_io.write_journal(design_id, {"events": []}, base_dir=tree)

        tree_io.render("LIB", base_dir=tree)

        text = _tree_text(tree)
        assert "別の journal に書いた同じ id" not in text
        assert "journal に見つからない出来事" in text

    def test_an_event_id_written_twice_keeps_the_first(self, tree: Path) -> None:
        design_id = self._answered(tree)
        event = {"id": f"{design_id}-E01", "type": "evidence", "content": "二つ目"}
        journal = design_io.load_journal(design_id, base_dir=tree)
        journal["events"].append(event)
        design_io.write_journal(design_id, journal, base_dir=tree)

        tree_io.render("LIB", base_dir=tree)

        text = _tree_text(tree)
        assert "期限切れは取消除外で 346 件" in text
        assert "二つ目" not in text

    def test_a_non_text_content_is_shown_as_text(self, tree: Path) -> None:
        design_id = self._answered(tree)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {"id": f"{design_id}-E01", "type": "observe", "content": 34.6}
                ]
            },
            base_dir=tree,
        )

        tree_io.render("LIB", base_dir=tree)

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        assert "34.6" in text

    def test_a_linked_design_that_disappeared_is_an_error_and_nothing_is_written(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)
        (tree / "designs" / f"{design_id}_hypothesis.yaml").unlink()

        with pytest.raises(ValueError, match=design_id):
            tree_io.render("LIB", base_dir=tree)
        assert not (tree / "themes" / "LIB_tree.html").exists()

    def test_a_missing_tree_is_an_error(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="has no question tree"):
            tree_io.render("LIB", base_dir=insight)

    @pytest.mark.parametrize("theme_id", ["../evil", "lib", ""])
    def test_an_invalid_theme_id_is_an_error(
        self, insight: Path, theme_id: str
    ) -> None:
        with pytest.raises(ValueError, match="theme_id"):
            tree_io.render(theme_id, base_dir=insight)

    def test_a_tree_file_that_names_another_theme_is_an_error(self, tree: Path) -> None:
        path = tree / "themes" / "LIB_tree.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("LIB", "FP"))

        with pytest.raises(ValueError, match="does not match the file name"):
            tree_io.render("LIB", base_dir=tree)
        assert not (tree / "themes" / "LIB_tree.html").exists()

    def test_the_cli_prints_the_path_and_exits_0(self, tree: Path) -> None:
        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 0, done.stderr
        assert json.loads(done.stdout) == {
            "path": str(tree / "themes" / "LIB_tree.html")
        }

    def test_the_cli_exits_1_with_a_message_when_it_cannot_render(
        self, insight: Path
    ) -> None:
        done = _run_cli(insight, "render", "--theme", "LIB")

        assert done.returncode == 1
        assert "has no question tree" in done.stderr

    def test_a_design_is_known_by_its_file_name_not_by_the_id_inside(
        self, tree: Path
    ) -> None:
        """A copied design file still carries the id of the one it was copied from."""
        _add(tree)
        first = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", first, base_dir=tree)
        copied = dict(design_io.load_design(first, base_dir=tree))
        copied |= {"title": "写した分析設計", "status": "supported"}
        atomic_write_yaml(tree / "designs" / "LIB-H02_hypothesis.yaml", copied)

        page = _rendered(tree)

        assert tree_io.progress("LIB", base_dir=tree)["LIB-Q02"] == "investigating"
        assert "検証中 1" in page
        assert "分析済み 0" in page
        assert "写した分析設計" in page

    def test_a_design_without_an_id_inside_stops_the_page_naming_the_design(
        self, tree: Path
    ) -> None:
        """Spec change (Epic 28 US-4 AC 1): every design needs a note, and a note needs a valid design."""
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)
        stored = dict(design_io.load_design(design_id, base_dir=tree))
        del stored["id"]
        atomic_write_yaml(tree / "designs" / f"{design_id}_hypothesis.yaml", stored)

        with pytest.raises(ValueError, match=f"analysis note of '{design_id}'"):
            tree_io.render("LIB", base_dir=tree)
        assert not (tree / "themes" / "LIB_tree.html").exists()

    def test_a_linked_design_with_an_unknown_status_names_the_design(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)
        stored = dict(design_io.load_design(design_id, base_dir=tree))
        stored["status"] = "finished"
        atomic_write_yaml(tree / "designs" / f"{design_id}_hypothesis.yaml", stored)

        with pytest.raises(ValueError, match=f"{design_id}.*finished"):
            tree_io.render("LIB", base_dir=tree)

    def test_a_broken_design_of_another_theme_does_not_stop_the_page(
        self, tree: Path
    ) -> None:
        broken = tree / "designs" / "FP-H01_hypothesis.yaml"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("title: [unclosed\n", encoding="utf-8")

        assert "論点ツリー LIB" in _rendered(tree)

    def test_the_cli_exits_1_with_a_message_when_a_journal_cannot_be_read(
        self, tree: Path
    ) -> None:
        design_id = self._answered(tree)
        journal = tree / "designs" / f"{design_id}_journal.yaml"
        journal.write_text("events: [unclosed\n", encoding="utf-8")

        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr
