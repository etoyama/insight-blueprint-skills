"""Tests of ``tree_io render --design`` (Epic 28, Story 28.1): the analysis note page.

The note is built from the files of one design: its YAML, its journal, the
catalog, and the verdict and figures the notebook wrote. Synthetic data only
(public-library holds, theme LIB).
"""

from __future__ import annotations

import base64
import json
import re
import struct
import zlib
from pathlib import Path

import pytest

from skills._shared import catalog_io, design_io
from skills._shared.design_note_read import render_design_note
from tests.tree_io._support import _design, _run_cli

CONNECTION_PATH = "/Users/secret-analyst/data/reservations.csv"
# Written by hand: json.dumps would drop the trailing zeros the notebook wrote.
VERDICT_TEXT = """{
  "conclusion": "期限切れは減った",
  "metrics": {
    "期限切れ率の差": {
      "value": 0.00010,
      "threshold": 0.050,
      "p": 1e-05,
      "pass": true,
      "effect_size": {"kind": "cohens_d", "value": 0.30},
      "confidence_interval": {"level": 0.95, "lower": 0.10, "upper": 0.50},
      "sample_size": 1520
    }
  },
  "figures": []
}"""


def _png(color: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"\x00" + bytes([color, color, color])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _write_verdict(insight: Path, design_id: str, verdict: dict | str) -> None:
    notebooks = insight / "notebooks"
    notebooks.mkdir(parents=True, exist_ok=True)
    text = (
        verdict if isinstance(verdict, str) else json.dumps(verdict, ensure_ascii=False)
    )
    (notebooks / f"{design_id}_verdict.json").write_text(text, encoding="utf-8")


def _figure(insight: Path, name: str, color: int = 10) -> bytes:
    notebooks = insight / "notebooks"
    notebooks.mkdir(parents=True, exist_ok=True)
    png = _png(color)
    (notebooks / name).write_bytes(png)
    return png


def _entry(file: str, title: str = "取り置き日数別") -> dict:
    return {
        "file": file,
        "title": title,
        "axes": "x = 日数, y = 期限切れ率",
        "how_to_read": "右下がりなら延長が効いている",
    }


def _note_html(insight: Path, design_id: str = "LIB-H01") -> str:
    path = Path(render_design_note(design_id, base_dir=insight)["path"])
    return path.read_text("utf-8")


def _embedded(png: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(png).decode()}"


class TestRenderDesignNote:
    def test_writes_a_standalone_page_for_a_theme_without_a_tree(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)

        result = render_design_note(design_id, base_dir=insight)

        path = insight / "notes" / f"{design_id}.html"
        assert result == {"path": str(path)}
        text = path.read_text("utf-8")
        assert text.startswith("<!doctype html>")
        assert f"分析ノート {design_id}" in text

    def test_writes_the_same_standalone_page_for_a_theme_with_a_tree(
        self, world: Path
    ) -> None:
        design_id = "LIB-H01"

        result = render_design_note(design_id, base_dir=world)

        assert result == {"path": str(world / "notes" / f"{design_id}.html")}
        assert (world / "notes" / f"{design_id}.html").is_file()

    def test_an_unknown_design_is_an_error_and_writes_nothing(
        self, insight: Path
    ) -> None:
        with pytest.raises(ValueError, match="design 'LIB-H09' not found"):
            render_design_note("LIB-H09", base_dir=insight)

        assert not (insight / "notes").exists()

    def test_a_verdict_that_is_not_an_object_is_an_error_naming_the_file(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _write_verdict(insight, design_id, "[1, 2]")

        with pytest.raises(ValueError, match=f"{design_id}_verdict.json"):
            render_design_note(design_id, base_dir=insight)

        assert not (insight / "notes").exists()

    def test_a_design_whose_notebook_has_not_run_still_renders(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)

        html = _note_html(insight, design_id)

        assert "notebook をまだ実行していない（verdict が無い）。" in html
        assert "notebook の結果（verdict）: まだ無い" in html

    def test_journal_events_and_verdict_numbers_appear_as_written(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {
                        "id": f"{design_id}-E01",
                        "type": "observe",
                        "content": "期限切れは152件",
                        "created_at": "2026-11-02T10:00:00+09:00",
                    },
                    {
                        "id": f"{design_id}-E02",
                        "type": "evidence",
                        "content": "取消除外後は34.6%",
                        "metadata": {"direction": "supports"},
                        "created_at": "2026-11-03T10:00:00+09:00",
                    },
                ]
            },
            base_dir=insight,
        )
        _write_verdict(insight, design_id, VERDICT_TEXT)

        html = _note_html(insight, design_id)

        assert "期限切れは152件" in html
        assert "仮説を支持する証拠" in html
        assert "取消除外後は34.6%" in html
        assert "2026-11-03T10:00:00+09:00" in html
        for cell in ("0.00010", "0.050", "1e-05", "1520", "✓"):
            assert f"<td>{cell}</td>" in html
        assert "<td>0.30（cohens_d）</td>" in html
        assert "<td>水準 0.95: [0.10, 0.50]</td>" in html

    def test_a_partial_effect_size_or_interval_is_left_out(self, insight: Path) -> None:
        design_id = _design(insight)
        verdict = {
            "metrics": {
                "m": {
                    "value": 1,
                    "effect_size": {"value": 0.3},
                    "confidence_interval": {"level": 0.95, "lower": 0.1},
                }
            }
        }
        _write_verdict(insight, design_id, verdict)

        html = _note_html(insight, design_id)

        assert "（" not in html.split("指標の値")[1]
        assert "水準" not in html

    def test_a_verdict_without_a_metrics_object_has_no_metric_values(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _write_verdict(insight, design_id, {"conclusion": "x", "metrics": "none"})

        html = _note_html(insight, design_id)

        assert "verdict に指標の値は無い。" in html
        assert "notebook の結果（verdict）: あり" in html

    def test_a_metric_entry_that_is_not_an_object_is_skipped(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _write_verdict(
            insight, design_id, {"metrics": {"bad": 3, "good": {"value": 0.5}}}
        )

        html = _note_html(insight, design_id)

        assert "<td>good</td>" in html
        assert "<td>bad</td>" not in html


class TestFigures:
    def test_figures_are_embedded_in_manifest_order_with_captions(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        first = _figure(insight, f"{design_id}_fig01.png", 10)
        second = _figure(insight, f"{design_id}_fig02.png", 200)
        _write_verdict(
            insight,
            design_id,
            {
                "figures": [
                    _entry(f"{design_id}_fig02.png", "二つ目を先に載せる"),
                    _entry(f"{design_id}_fig01.png", "一つ目を後に載せる"),
                ]
            },
        )

        html = _note_html(insight, design_id)

        assert html.index(_embedded(second)) < html.index(_embedded(first))
        assert html.index("二つ目を先に載せる") < html.index("一つ目を後に載せる")
        assert "軸の説明: x = 日数, y = 期限切れ率" in html
        assert "図の読み方: 右下がりなら延長が効いている" in html

    @pytest.mark.parametrize(
        "file",
        [
            "sub/fig.png",
            "../outside.png",
            "..",
            "a..b.png",
            "fig 01.png",
            "missing.png",
            "",
        ],
    )
    def test_a_figure_that_is_not_a_bare_existing_file_is_left_out(
        self, insight: Path, file: str
    ) -> None:
        design_id = _design(insight)
        (insight / "outside.png").write_bytes(_png(5))
        (insight / "notebooks").mkdir(parents=True)
        (insight / "notebooks" / "sub").mkdir()
        (insight / "notebooks" / "sub" / "fig.png").write_bytes(_png(6))
        valid = _figure(insight, f"{design_id}_fig01.png", 77)
        _write_verdict(
            insight,
            design_id,
            {
                "figures": [
                    _entry(file, "不正な図"),
                    _entry(f"{design_id}_fig01.png", "正しい図"),
                ]
            },
        )

        html = _note_html(insight, design_id)

        assert "正しい図" in html
        assert _embedded(valid) in html
        assert "不正な図" not in html
        assert html.count("<img") == 1

    def test_a_directory_named_like_a_figure_is_left_out(self, insight: Path) -> None:
        design_id = _design(insight)
        (insight / "notebooks" / "fig01.png").mkdir(parents=True)
        _write_verdict(insight, design_id, {"figures": [_entry("fig01.png")]})

        html = _note_html(insight, design_id)

        assert "<img" not in html
        assert "図はまだ無い。" in html

    def test_a_file_that_is_not_a_png_is_left_out(self, insight: Path) -> None:
        """A manifest could name the notebook itself, which holds connection values."""
        design_id = _design(insight)
        notebooks = insight / "notebooks"
        notebooks.mkdir(parents=True)
        (notebooks / "LIB-H01.py").write_text("path = 'secret-warehouse'", "utf-8")
        (notebooks / "renamed.png").write_text("path = 'secret-warehouse'", "utf-8")
        _write_verdict(
            insight,
            design_id,
            {"figures": [_entry("LIB-H01.py"), _entry("renamed.png")]},
        )

        html = _note_html(insight, design_id)

        assert "<img" not in html
        assert "図はまだ無い。" in html

    def test_a_link_to_a_file_outside_notebooks_is_left_out(
        self, insight: Path, tmp_path: Path
    ) -> None:
        design_id = _design(insight)
        outside = tmp_path / "outside.png"
        outside.write_bytes(_png(10))
        notebooks = insight / "notebooks"
        notebooks.mkdir(parents=True)
        (notebooks / "fig01.png").symlink_to(outside)
        _write_verdict(insight, design_id, {"figures": [_entry("fig01.png")]})

        assert "<img" not in _note_html(insight, design_id)

    def test_a_figures_entry_that_is_not_an_object_is_skipped(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _write_verdict(insight, design_id, {"figures": ["fig01.png", 3]})

        assert "図はまだ無い。" in _note_html(insight, design_id)


class TestWhatTheNoteKeepsOut:
    def test_it_shows_the_source_name_but_neither_its_connection_nor_any_absolute_path(
        self, insight: Path
    ) -> None:
        catalog_io.create_source(
            id="reservations",
            name="予約台帳",
            type="csv",
            description="予約の一覧",
            connection={"path": CONNECTION_PATH},
            base_dir=insight,
        )
        design = design_io.create_design(
            theme_id="LIB",
            title="Test",
            hypothesis_statement="X",
            hypothesis_background="Y",
            source_ids=["reservations"],
            base_dir=insight,
        )
        _figure(insight, f"{design['id']}_fig01.png")
        _write_verdict(
            insight, design["id"], {"figures": [_entry(f"{design['id']}_fig01.png")]}
        )

        html = _note_html(insight, design["id"])

        assert "予約台帳" in html
        assert "予約の一覧" in html
        assert CONNECTION_PATH not in html
        assert "secret-analyst" not in html
        assert str(insight.parent) not in html

    def test_two_runs_write_the_same_bytes(self, insight: Path) -> None:
        design_id = _design(insight)
        _figure(insight, f"{design_id}_fig01.png")
        _write_verdict(
            insight,
            design_id,
            VERDICT_TEXT.replace(
                '"figures": []',
                f'"figures": [{json.dumps(_entry(f"{design_id}_fig01.png"))}]',
            ),
        )

        first = _note_html(insight, design_id)
        second = _note_html(insight, design_id)

        assert first == second

    def test_the_page_has_no_script_and_loads_nothing_from_outside(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        _figure(insight, f"{design_id}_fig01.png")
        _write_verdict(
            insight, design_id, {"figures": [_entry(f"{design_id}_fig01.png")]}
        )

        html = _note_html(insight, design_id)

        assert "<script" not in html
        assert not re.search(r"https?://", html)


class TestRenderDesignCli:
    def test_render_design_prints_the_path_and_exits_0(self, insight: Path) -> None:
        design_id = _design(insight)

        done = _run_cli(insight, "render", "--design", design_id)

        assert done.returncode == 0, done.stderr
        path = Path(json.loads(done.stdout)["path"])
        assert path.resolve() == (insight / "notes" / f"{design_id}.html").resolve()
        assert (insight / "notes" / f"{design_id}.html").is_file()

    def test_an_unknown_design_exits_1_with_a_message_and_writes_nothing(
        self, insight: Path
    ) -> None:
        done = _run_cli(insight, "render", "--design", "LIB-H09")

        assert done.returncode == 1
        assert done.stderr.strip() == "tree_io: design 'LIB-H09' not found"
        assert not (insight / "notes").exists()

    def test_render_theme_still_writes_the_tree_page(self, tree: Path) -> None:
        done = _run_cli(tree, "render", "--theme", "LIB")

        assert done.returncode == 0, done.stderr
        assert (tree / "themes" / "LIB_tree.html").is_file()
        assert not (tree / "notes").exists()

    @pytest.mark.parametrize(
        "args",
        [("--theme", "LIB", "--design", "LIB-H01"), ()],
        ids=["both", "neither"],
    )
    def test_render_needs_exactly_one_of_theme_and_design(
        self, tree: Path, args: tuple[str, ...]
    ) -> None:
        _design(tree)

        done = _run_cli(tree, "render", *args)

        assert done.returncode == 1
        assert "exactly one of --theme and --design" in done.stderr
        assert not (tree / "notes").exists()
        assert not (tree / "themes" / "LIB_tree.html").exists()

    def test_other_commands_still_require_theme(self, tree: Path) -> None:
        done = _run_cli(tree, "progress")

        assert done.returncode == 1
        assert "--theme is required for progress" in done.stderr
