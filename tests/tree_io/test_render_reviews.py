"""Tests of the review comments on the tree page (Epic 33, Story 33.6, US-4 AC 4, 5).

The batches are written by ``design_io`` as ``/analysis-review`` writes them:
the review that approves the design comes before the analysis, the review of
the result after it. Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared.design_note import note_anchor
from tests._saved_verdicts import table_rows
from tests.test_tree_render import branch_cards, card_text, parse
from tests.tree_io._support import _add, _rendered
from tests.tree_io.test_render_design import VERDICT_TEXT, _write_verdict

_PRIMARY = {
    "target": "期限切れ率の差",
    "tier": "primary",
    "comparison": "差が 0.05 以上で支持、0.01 未満で棄却",
}
_COUNT = "分析を始めた後の review コメント"


def _reviewed(insight: Path) -> str:
    """A design linked to LIB-Q02, approved, analysed, then reviewed on its result."""
    _add(insight)
    design_id = design_io.create_design(
        theme_id="LIB",
        title="取り置き期限の延長",
        hypothesis_statement="延ばすと期限切れが減る",
        hypothesis_background="7日で多い",
        metrics=[_PRIMARY],
        base_dir=insight,
    )["id"]
    tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=insight)
    design_io.append_review_batch(
        design_id,
        "analyzing",
        [{"comment": "比較の向きは合っている"}],
        base_dir=insight,
    )
    _write_verdict(insight, design_id, VERDICT_TEXT)
    design_io.transition_status(design_id, "in_review", base_dir=insight)
    design_io.append_review_batch(
        design_id,
        "revision_requested",
        [
            {
                "comment": "区間が広すぎる",
                "target_section": "verdict",
                "target_content": {"metric": "期限切れ率の差", "upper": 0.5},
            },
            {
                "comment": "図の軸の説明が無い",
                "target_section": "figures",
                "target_content": "fig1.png",
            },
        ],
        base_dir=insight,
    )
    return design_id


def _section(html: str, design_id: str) -> str:
    start = html.index(f'id="{note_anchor(design_id)}-reviews"')
    return html[start : html.index("<section", start)]


def _card(html: str) -> str:
    """The text of the design's card under LIB-Q02."""
    (text,) = [card_text(c) for c in branch_cards(parse(html), "LIB-Q02")]
    return text


class TestReviewsOnTheTreePage:
    def test_the_note_lists_every_batch_newest_first_with_its_comments(
        self, tree: Path
    ) -> None:
        design_id = _reviewed(tree)

        section = _section(_rendered(tree), design_id)

        after = section.index("分析を始めた後の review")
        before = section.index("分析を始める前の review")
        assert after < before
        assert "review の後の状態: 修正待ち（revision_requested）" in section
        assert table_rows(section)[:3] == [
            ["review コメント", "対象", "対象の中身"],
            ["区間が広すぎる", "verdict", '{"metric": "期限切れ率の差", "upper": 0.5}'],
            ["図の軸の説明が無い", "figures", "fig1.png"],
        ]
        assert "比較の向きは合っている" in section[before:]

    def test_the_row_of_the_design_counts_the_comments_after_the_analysis(
        self, tree: Path
    ) -> None:
        _reviewed(tree)

        assert f"{_COUNT}: 2 件" in _card(_rendered(tree))

    def test_a_design_reviewed_only_before_the_analysis_shows_no_count(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = design_io.create_design(
            theme_id="LIB",
            title="取り置き期限の延長",
            hypothesis_statement="延ばすと期限切れが減る",
            hypothesis_background="7日で多い",
            metrics=[_PRIMARY],
            base_dir=tree,
        )["id"]
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)
        design_io.append_review_batch(
            design_id, "analyzing", [{"comment": "よい"}], base_dir=tree
        )

        assert _COUNT not in _card(_rendered(tree))

    @pytest.mark.parametrize(
        "text", ["batches: [unclosed\n", "batches: not a list\n", "- a list\n"]
    )
    def test_a_reviews_file_that_cannot_be_read_leaves_the_page_as_without_one(
        self, tree: Path, text: str
    ) -> None:
        design_id = _reviewed(tree)
        reviews = tree / "designs" / f"{design_id}_reviews.yaml"
        reviews.unlink()
        without = _rendered(tree)

        reviews.write_text(text, encoding="utf-8")

        assert _rendered(tree) == without
