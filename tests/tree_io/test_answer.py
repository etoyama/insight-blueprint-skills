"""Tests of skills/_shared/tree_io.py (Epic 18): ``answer``: one reflection round, checked before it is saved.

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared import design_io, tree_check, tree_io
from skills._shared._atomic import atomic_write_yaml
from tests.tree_io._support import _add, _design, _entry


class TestAnswer:
    """``answer`` is the one write path for answers: checked first, then appended."""

    @staticmethod
    def _answers_of(base: Path, node_id: str) -> list[dict]:
        stored = tree_io.load_tree("LIB", base_dir=base)
        return next(n for n in stored["nodes"] if n["id"] == node_id).get("answers", [])

    def test_the_first_answer_is_round_1_under_the_current_root_revision(
        self, world: Path
    ) -> None:
        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )

        assert result == {
            "round": 1,
            "root_revision": 1,
            "written": [
                {"node_id": "LIB-Q02", "previous_round": None, "restated": False}
            ],
            "unchanged": [],
            "violations": [],
        }
        (stored,) = self._answers_of(world, "LIB-Q02")
        assert (stored["round"], stored["root_revision"]) == (1, 1)
        assert stored["created_at"]
        assert stored["statements"][0]["text"] == "期限切れは152件"

    def test_a_second_call_is_round_2_and_names_the_answer_it_replaces(
        self, world: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )

        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "取消除外後は34.6%")], base_dir=world
        )

        assert result["round"] == 2
        assert result["written"] == [
            {"node_id": "LIB-Q02", "previous_round": 1, "restated": False}
        ]
        assert [a["round"] for a in self._answers_of(world, "LIB-Q02")] == [1, 2]

    def test_one_call_gives_every_node_it_answers_the_same_round(
        self, world: Path
    ) -> None:
        result = tree_io.answer(
            "LIB",
            answers=[
                _entry("LIB-Q02", "期限切れは152件"),
                _entry("LIB-Q03", "取消除外後は34.6%", "LIB-H02-E01"),
            ],
            base_dir=world,
        )

        assert result["round"] == 1
        assert [w["node_id"] for w in result["written"]] == ["LIB-Q02", "LIB-Q03"]
        assert self._answers_of(world, "LIB-Q03")[0]["round"] == 1

    def test_a_node_skipped_in_round_2_and_answered_in_round_3_has_rounds_1_and_3(
        self, world: Path
    ) -> None:
        both = [
            _entry("LIB-Q02", "期限切れは152件"),
            _entry("LIB-Q03", "取消除外後は34.6%", "LIB-H02-E01"),
        ]
        tree_io.answer("LIB", answers=both, base_dir=world)
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "取消除外後は34.6%")], base_dir=world
        )

        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q03", "期限切れは152件", "LIB-H02-E01")],
            base_dir=world,
        )

        assert result["round"] == 3
        assert result["written"] == [
            {"node_id": "LIB-Q03", "previous_round": 1, "restated": False}
        ]
        assert [a["round"] for a in self._answers_of(world, "LIB-Q03")] == [1, 3]

    def test_an_answer_with_the_same_statements_is_not_written_again(
        self, world: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )

        result = tree_io.answer(
            "LIB",
            answers=[
                _entry("LIB-Q02", "期限切れは152件"),
                _entry("LIB-Q03", "取消除外後は34.6%", "LIB-H02-E01"),
            ],
            base_dir=world,
        )

        assert result["round"] == 2
        assert result["unchanged"] == ["LIB-Q02"]
        assert [w["node_id"] for w in result["written"]] == ["LIB-Q03"]
        assert len(self._answers_of(world, "LIB-Q02")) == 1

    def test_a_call_with_nothing_to_write_leaves_the_file_and_the_round_alone(
        self, world: Path
    ) -> None:
        entry = _entry("LIB-Q02", "期限切れは152件")
        tree_io.answer("LIB", answers=[entry], base_dir=world)
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        again = tree_io.answer("LIB", answers=[entry], base_dir=world)
        empty = tree_io.answer("LIB", answers=[], base_dir=world)

        assert path.read_bytes() == before
        assert again == empty | {"unchanged": ["LIB-Q02"]}
        assert (empty["round"], empty["written"], empty["unchanged"]) == (1, [], [])

    def test_the_same_statements_are_written_again_after_the_root_revision_moved(
        self, world: Path
    ) -> None:
        entry = _entry("LIB-Q02", "期限切れは152件")
        tree_io.answer("LIB", answers=[entry], base_dir=world)
        tree_io.revise_root(
            "LIB", question="延長の対象を絞るか", bump=True, reason="到達点が変わった",
            base_dir=world,
        )  # fmt: skip

        result = tree_io.answer("LIB", answers=[entry], base_dir=world)

        assert result["root_revision"] == 2
        assert result["written"] == [
            {"node_id": "LIB-Q02", "previous_round": 1, "restated": True}
        ]
        assert [a["root_revision"] for a in self._answers_of(world, "LIB-Q02")] == [
            1,
            2,
        ]

    def test_a_number_no_cited_event_holds_is_reported_and_nothing_is_written(
        self, world: Path
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは999件")], base_dir=world
        )

        assert path.read_bytes() == before
        assert (result["round"], result["written"]) == (0, [])
        assert result["violations"] == [
            {
                "node_id": "LIB-Q02",
                "round": 1,
                "statement": 1,
                "kind": "number-not-cited",
                "text": "999",
                "fix": tree_check.NUMBER_FIX,
            }
        ]

    def test_a_number_not_cited_says_how_to_fix_it(self, world: Path) -> None:
        # Epic 35, US-6 AC 4: cite the event that records it, or take it out.
        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは999件")], base_dir=world
        )

        fix = result["violations"][0]["fix"]
        assert "cite the event that records it" in fix
        assert "take the number out" in fix

    def test_an_answer_may_name_its_node_and_the_round(self, world: Path) -> None:
        # Epic 35, US-6 AC 1, AC 2: the answer being written is round 1.
        text = "1回目の振り返りで、LIB-Q02 の期限切れは152件"
        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", text)], base_dir=world
        )

        assert (result["violations"], result["round"]) == ([], 1)

    def test_the_statement_position_in_a_violation_is_one_based(
        self, world: Path
    ) -> None:
        entry = _entry("LIB-Q02", "期限切れは152件")
        entry["statements"].append(
            {"kind": "claim", "text": "割合は77%", "cites": ["LIB-H01-E01"]}
        )

        result = tree_io.answer("LIB", answers=[entry], base_dir=world)

        assert [v["statement"] for v in result["violations"]] == [2]

    def test_one_bad_node_blocks_the_good_node_in_the_same_call(
        self, world: Path
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        result = tree_io.answer(
            "LIB",
            answers=[
                _entry("LIB-Q02", "期限切れは152件"),
                _entry("LIB-Q03", "期限切れは999件", "LIB-H02-E01"),
            ],
            base_dir=world,
        )

        assert path.read_bytes() == before
        assert [v["node_id"] for v in result["violations"]] == ["LIB-Q03"]
        assert result["written"] == []

    def test_a_parent_may_cite_an_event_of_a_design_linked_below_it(
        self, world: Path
    ) -> None:
        _add(world, question="孫の問い", parent_question_id="LIB-Q02")
        grandchild_design = _design(world)
        tree_io.link_design("LIB", "LIB-Q04", grandchild_design, base_dir=world)
        design_io.write_journal(
            grandchild_design,
            {"events": [{"id": f"{grandchild_design}-E01", "content": "取消は12件"}]},
            base_dir=world,
        )

        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q02", "取消は12件", f"{grandchild_design}-E01")],
            base_dir=world,
        )

        assert result["violations"] == []
        assert result["written"] == [
            {"node_id": "LIB-Q02", "previous_round": None, "restated": False}
        ]

    def test_citing_a_design_linked_only_to_a_sibling_branch_writes_nothing(
        self, world: Path
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q02", "期限切れ152件", "LIB-H02-E01")],
            base_dir=world,
        )

        assert path.read_bytes() == before
        assert [(v["kind"], v["text"]) for v in result["violations"]] == [
            ("unlinked-design", "LIB-H02-E01")
        ]

    def test_a_stored_violation_in_a_node_not_written_does_not_block_the_call(
        self, world: Path
    ) -> None:
        stored = tree_io.load_tree("LIB", base_dir=world)
        stale = _entry("LIB-Q03", "期限切れは999件", "LIB-H02-E01")
        next(n for n in stored["nodes"] if n["id"] == "LIB-Q03")["answers"] = [
            {"round": 1, "root_revision": 1, "statements": stale["statements"]}
        ]
        atomic_write_yaml(world / "themes" / "LIB_tree.yaml", stored)

        result = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )

        assert result["violations"] == []
        assert result["round"] == 2

    def test_a_node_that_is_not_in_the_tree_is_rejected(self, world: Path) -> None:
        with pytest.raises(ValueError, match="LIB-Q09"):
            tree_io.answer("LIB", answers=[_entry("LIB-Q09", "152件")], base_dir=world)

    def test_a_node_answered_twice_in_one_call_is_rejected_and_nothing_is_written(
        self, world: Path
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()
        entry = _entry("LIB-Q02", "期限切れは152件")

        with pytest.raises(ValueError, match="only once"):
            tree_io.answer("LIB", answers=[entry, entry], base_dir=world)

        assert path.read_bytes() == before

    def test_a_theme_without_a_tree_is_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="no question tree"):
            tree_io.answer("LIB", answers=[], base_dir=insight)

    @pytest.mark.parametrize("answers", [["LIB-Q02"], {"node_id": "LIB-Q02"}])
    def test_an_entry_that_is_not_an_object_is_rejected(
        self, world: Path, answers: object
    ) -> None:
        with pytest.raises(ValueError):
            tree_io.answer("LIB", answers=answers, base_dir=world)  # type: ignore[arg-type]

    def test_an_entry_without_a_node_id_is_rejected_for_that_reason(
        self, world: Path
    ) -> None:
        statements = _entry("LIB-Q02", "期限切れは152件")["statements"]
        nameless = {"statements": statements}

        with pytest.raises(ValueError, match="node_id"):
            tree_io.answer("LIB", answers=[nameless, nameless], base_dir=world)

    @pytest.mark.parametrize("extra", ["round", "root_revision", "created_at"])
    def test_an_entry_cannot_set_what_tree_io_sets(
        self, world: Path, extra: str
    ) -> None:
        entry = _entry("LIB-Q02", "期限切れは152件") | {extra: 7}

        with pytest.raises(ValueError, match=extra):
            tree_io.answer("LIB", answers=[entry], base_dir=world)

    def test_the_order_of_the_keys_does_not_make_an_answer_changed(
        self, world: Path
    ) -> None:
        entry = _entry("LIB-Q02", "期限切れは152件")
        tree_io.answer("LIB", answers=[entry], base_dir=world)
        reordered = {
            "statements": [
                dict(reversed(list(s.items()))) for s in entry["statements"]
            ],
            "node_id": "LIB-Q02",
        }

        result = tree_io.answer("LIB", answers=[reordered], base_dir=world)

        assert result["unchanged"] == ["LIB-Q02"]

    @pytest.mark.parametrize(
        "statements",
        [
            [],
            [{"kind": "claim", "text": "期限切れは152件", "cites": []}],
            [{"kind": "claim", "text": "期限切れは152件"}],
        ],
    )
    def test_statements_without_a_cite_are_rejected_and_nothing_is_written(
        self, world: Path, statements: list[dict]
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        with pytest.raises(ValueError):
            tree_io.answer(
                "LIB",
                answers=[{"node_id": "LIB-Q02", "statements": statements}],
                base_dir=world,
            )

        assert path.read_bytes() == before


class TestDecideAfterTheStart:
    """deepen, return and close are taken at the round of the answers in view."""

    @pytest.fixture
    def started(self, world: Path) -> Path:
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初", base_dir=world
        )
        return world

    def _decide(self, base: Path, kind: str, node_id: str) -> dict:
        return tree_io.decide(
            "LIB", kind=kind, node_id=node_id, reason="答えを見て", base_dir=base
        )

    def test_a_decision_after_a_reflection_carries_that_round(
        self, started: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=started
        )
        decision = self._decide(started, "deepen", "LIB-Q02")
        assert (decision["kind"], decision["round"]) == ("deepen", 1)

    def test_decisions_do_not_move_the_round_of_the_next_answers(
        self, started: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=started
        )
        self._decide(started, "return", "LIB-Q03")
        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q03", "取消後は34.6%", "LIB-H02-E01")],
            base_dir=started,
        )
        assert result["round"] == 2

    def test_return_records_the_node_to_investigate_next(self, started: Path) -> None:
        self._decide(started, "return", "LIB-Q03")
        stored = tree_io.load_tree("LIB", started)["decisions"]
        assert [(d["kind"], d["node_id"]) for d in stored] == [
            ("start", "LIB-Q02"),
            ("return", "LIB-Q03"),
        ]

    def test_close_stops_at_the_node_investigated(self, started: Path) -> None:
        assert self._decide(started, "close", "LIB-Q02")["kind"] == "close"

    def test_a_deepen_outside_the_branch_is_not_written(self, started: Path) -> None:
        with pytest.raises(ValueError, match="deepen goes to LIB-Q02"):
            self._decide(started, "deepen", "LIB-Q03")
        assert len(tree_io.load_tree("LIB", started)["decisions"]) == 1

    def test_a_round_in_the_payload_is_refused(self, started: Path) -> None:
        with pytest.raises(TypeError):
            tree_io.decide(
                "LIB",
                kind="deepen",
                node_id="LIB-Q02",
                reason="x",
                round=5,  # type: ignore[call-arg]
                base_dir=started,
            )


VIEW = "延長は試す価値がある。\n  期限切れの多くは通知の遅れで説明できそうだ"


def _view(node_id: str, text: str = VIEW, cite: str = "LIB-H01-E01") -> dict:
    entry = _entry(node_id, text, cite)
    entry["statements"][0]["analyst_view"] = True
    return entry


class TestTheAnalystsView:
    """A statement marked as the analyst's view is written like any other (ADR-0068)."""

    @staticmethod
    def _statements_of(base: Path, node_id: str) -> list[list[dict]]:
        stored = tree_io.load_tree("LIB", base_dir=base)
        node = next(n for n in stored["nodes"] if n["id"] == node_id)
        return [a["statements"] for a in node.get("answers", [])]

    def test_a_marked_statement_is_stored_word_for_word_with_its_mark(
        self, world: Path
    ) -> None:
        result = tree_io.answer("LIB", answers=[_view("LIB-Q01")], base_dir=world)

        assert result["violations"] == []
        ((stored,),) = self._statements_of(world, "LIB-Q01")
        assert stored == {
            "kind": "claim",
            "text": VIEW,
            "cites": ["LIB-H01-E01"],
            "analyst_view": True,
        }

    def test_an_unmarked_statement_is_stored_without_the_mark(
        self, world: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )

        ((stored,),) = self._statements_of(world, "LIB-Q02")
        assert "analyst_view" not in stored

    def test_a_marked_statement_with_a_number_no_cited_event_records_is_refused(
        self, world: Path
    ) -> None:
        result = tree_io.answer(
            "LIB", answers=[_view("LIB-Q01", "期限切れは999件だと見る")], base_dir=world
        )

        (violation,) = result["violations"]
        assert violation["node_id"] == "LIB-Q01"
        assert result["written"] == []
        assert self._statements_of(world, "LIB-Q01") == []

    def test_a_marked_statement_citing_an_event_that_does_not_exist_is_refused(
        self, world: Path
    ) -> None:
        result = tree_io.answer(
            "LIB", answers=[_view("LIB-Q01", cite="LIB-H01-E99")], base_dir=world
        )

        assert result["violations"]
        assert self._statements_of(world, "LIB-Q01") == []

    def test_a_marked_statement_without_a_cite_is_an_error(self, world: Path) -> None:
        uncited = _view("LIB-Q01")
        uncited["statements"][0]["cites"] = []

        with pytest.raises(ValueError, match="cites"):
            tree_io.answer("LIB", answers=[uncited], base_dir=world)

    def test_the_same_words_with_the_mark_added_are_a_new_answer(
        self, world: Path
    ) -> None:
        tree_io.answer("LIB", answers=[_entry("LIB-Q01", VIEW)], base_dir=world)

        result = tree_io.answer("LIB", answers=[_view("LIB-Q01")], base_dir=world)

        assert result["written"] == [
            {"node_id": "LIB-Q01", "previous_round": 1, "restated": False}
        ]
        before, after = self._statements_of(world, "LIB-Q01")
        assert "analyst_view" not in before[0]
        assert after[0]["analyst_view"] is True

    def test_a_marked_statement_sent_again_as_it_is_writes_nothing(
        self, world: Path
    ) -> None:
        tree_io.answer("LIB", answers=[_view("LIB-Q01")], base_dir=world)

        result = tree_io.answer("LIB", answers=[_view("LIB-Q01")], base_dir=world)

        assert (result["written"], result["unchanged"]) == ([], ["LIB-Q01"])

    def test_a_tree_saved_before_the_mark_existed_reads_and_takes_a_marked_answer(
        self, world: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q01", "期限切れは152件")], base_dir=world
        )
        saved = (world / "themes" / "LIB_tree.yaml").read_text("utf-8")
        assert "analyst_view" not in saved

        tree_io.answer("LIB", answers=[_view("LIB-Q01")], base_dir=world)

        first, second = self._statements_of(world, "LIB-Q01")
        assert first == [
            {"kind": "claim", "text": "期限切れは152件", "cites": ["LIB-H01-E01"]}
        ]
        assert second[0]["analyst_view"] is True
        assert tree_check.check_theme("LIB", base_dir=world) == []
