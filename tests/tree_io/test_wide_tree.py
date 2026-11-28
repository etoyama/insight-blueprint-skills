"""The answer commands over a tree as wide as a real theme (Epic 36, ADR-0068, ADR-0069).

The trees of the other tests list one or two results; here the subject leaves
out about forty, so what was listed the round before is told apart at scale.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from skills._shared import design_io, tree_check, tree_io
from tests import _wide_tree as wide


@pytest.fixture
def after_round_1(insight: Path) -> Path:
    wide.build(insight)
    return insight


def _listed(found: dict, node_id: str = wide.ROOT) -> dict[str, bool]:
    return {u["event_id"]: u["shown_before"] for u in found["uncited_below"][node_id]}


def _type_of(base: Path, event_id: str) -> str:
    design_id = event_id.rsplit("-", 1)[0]
    return next(
        e["type"]
        for e in design_io.journal_events(design_id, base)
        if e["id"] == event_id
    )


class TestTheListBeforeRoundTwoIsWritten:
    def test_the_tree_has_seven_nodes(self, after_round_1: Path) -> None:
        assert len(tree_io.load_tree(wide.THEME, base_dir=after_round_1)["nodes"]) == 7

    def test_the_subject_lists_what_round_1_left_out_and_what_is_new(
        self, after_round_1: Path
    ) -> None:
        new_events = wide.add_round_2_events(after_round_1)

        found = tree_io.changes(
            wide.THEME,
            answers=wide.round_2_drafts(after_round_1),
            base_dir=after_round_1,
        )

        listed = _listed(found)
        assert Counter(listed.values()) == {
            True: wide.LISTED_BEFORE,
            False: wide.NEW_IN_ROUND_2,
        }
        assert {e for e, before in listed.items() if not before} == set(new_events)

    def test_the_new_results_are_of_every_kind(self, after_round_1: Path) -> None:
        new_events = wide.add_round_2_events(after_round_1)

        kinds = Counter(_type_of(after_round_1, e) for e in new_events)

        assert set(kinds) == {"question", "evidence", "observe", "conclude"}

    def test_a_node_in_between_lists_what_its_own_branch_left_out(
        self, after_round_1: Path
    ) -> None:
        wide.add_round_2_events(after_round_1)

        found = tree_io.changes(
            wide.THEME,
            answers=wide.round_2_drafts(after_round_1),
            base_dir=after_round_1,
        )

        listed = _listed(found, "GYM-Q03")
        assert all(e.startswith(("GYM-H03", "GYM-H04")) for e in listed)
        # GYM-Q05 got its first answer in round 2, so none of GYM-H04 was listed before.
        assert not any(b for e, b in listed.items() if e.startswith("GYM-H04"))
        assert any(listed.values())

    def test_asking_writes_nothing(self, after_round_1: Path) -> None:
        wide.add_round_2_events(after_round_1)
        path = after_round_1 / "themes" / f"{wide.THEME}_tree.yaml"
        before = path.read_bytes()

        tree_io.changes(
            wide.THEME,
            answers=wide.round_2_drafts(after_round_1),
            base_dir=after_round_1,
        )

        assert path.read_bytes() == before


class TestAfterTheAnalystChose:
    @pytest.fixture
    def after_round_2(self, insight: Path) -> Path:
        wide.build_through_round_2(insight)
        return insight

    def test_what_the_analyst_did_not_take_stays_listed(
        self, after_round_2: Path
    ) -> None:
        listed = _listed(tree_io.changes(wide.THEME, base_dir=after_round_2))

        assert Counter(listed.values()) == {
            True: wide.LISTED_BEFORE,
            False: wide.NEW_IN_ROUND_2 - wide.CHOSEN,
        }

    def test_the_analysts_view_is_kept_word_for_word_across_two_designs(
        self, after_round_2: Path
    ) -> None:
        tree = tree_io.load_tree(wide.THEME, base_dir=after_round_2)
        root = next(n for n in tree["nodes"] if n["id"] == wide.ROOT)

        (view,) = [
            s for s in root["answers"][-1]["statements"] if s.get("analyst_view")
        ]

        assert view["text"] == wide.ANALYST_VIEW
        assert {c.rsplit("-", 1)[0] for c in view["cites"]} == {"GYM-H01", "GYM-H04"}

    def test_the_tree_passes_its_check(self, after_round_2: Path) -> None:
        assert tree_check.check_theme(wide.THEME, base_dir=after_round_2) == []

    def test_the_page_of_the_tree_still_shows_the_marked_statement(
        self, after_round_2: Path
    ) -> None:
        page = Path(tree_io.render(wide.THEME, base_dir=after_round_2)["path"])

        assert wide.ANALYST_VIEW.splitlines()[0] in page.read_text("utf-8")

    def test_the_note_of_a_cited_design_still_renders(
        self, after_round_2: Path
    ) -> None:
        note = tree_io.render_design("GYM-H01", base_dir=after_round_2)

        assert Path(note["path"]).read_text("utf-8")
