"""Tests for tree_check, the read-only check of cited answers (Epic 18, Story 18.3).

The check exists to stop #105: a number in an answer that no journal record holds.
Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from insight_blueprint.models.tree import QuestionTree
from skills._shared import design_io, tree_check
from skills._shared._atomic import atomic_write_yaml
from skills._shared.tree_check import Violation, find_violations, numbers_in


def values(text: str) -> list[Decimal]:
    return [n.value for n in numbers_in(text)]


def signs(text: str) -> list[str]:
    return [n.sign for n in numbers_in(text)]


class TestNumbersIn:
    def test_a_text_without_digits_has_no_numbers(self) -> None:
        assert numbers_in("取消を除いて比べた") == []

    def test_a_number_keeps_the_token_as_written_and_its_value(self) -> None:
        (found,) = numbers_in("およそ1.90倍")
        assert (found.token, found.value) == ("1.90", Decimal("1.9"))

    def test_numbers_come_in_order_of_appearance(self) -> None:
        assert values("152件と80件") == [Decimal(152), Decimal(80)]

    def test_full_width_forms_equal_the_ascii_forms(self) -> None:
        assert values("３４．６％") == values("34.6%") == [Decimal("34.6")]

    def test_the_token_is_kept_after_normalization(self) -> None:
        assert [n.token for n in numbers_in("１，２３４．５")] == ["1,234.5"]

    def test_a_thousands_separator_is_removed(self) -> None:
        assert values("1,234件") == [Decimal(1234)]

    def test_a_comma_that_is_not_a_thousands_separator_splits_the_number(self) -> None:
        assert values("12,5") == [Decimal(12), Decimal(5)]

    def test_values_compare_by_value_not_by_spelling(self) -> None:
        assert values("1.90") == values("1.9")
        assert values("01") == values("1")

    @pytest.mark.parametrize(
        "text", ["34.6%", "34.6％", "34.6 %", "34.6パーセント", "34.6件"]
    )
    def test_the_unit_is_ignored(self, text: str) -> None:
        assert values(text) == [Decimal("34.6")]

    def test_a_converted_value_is_a_different_number(self) -> None:
        assert values("0.346") != values("34.6")

    def test_a_rounded_value_is_a_different_number(self) -> None:
        assert values("35") != values("34.6")

    @pytest.mark.parametrize(
        "text",
        [
            "-3.2",
            "−3.2",
            "－3.2",
            "‐3.2",
            "–3.2",
            "—3.2",
            "▲3.2",
            "△3.2",
            "▼3.2",
            "▽3.2",
        ],
    )
    def test_a_clear_minus_sign_belongs_to_the_number(self, text: str) -> None:
        (found,) = numbers_in(text)
        assert (found.sign, found.value) == ("-", Decimal("3.2"))

    @pytest.mark.parametrize("text", ["+3.2", "＋3.2"])
    def test_a_clear_plus_sign_belongs_to_the_number(self, text: str) -> None:
        (found,) = numbers_in(text)
        assert (found.sign, found.value) == ("+", Decimal("3.2"))

    def test_a_number_written_without_a_sign_has_none(self) -> None:
        assert signs("3.2ポイント") == [""]

    def test_the_token_keeps_the_sign_as_written(self) -> None:
        assert [n.token for n in numbers_in("前年比▲3.2%")] == ["▲3.2"]

    @pytest.mark.parametrize("text", ["10-20", "10+20", "2026-11-21"])
    def test_a_hyphen_or_plus_right_after_a_digit_is_not_a_sign(
        self, text: str
    ) -> None:
        assert set(signs(text)) == {""}

    @pytest.mark.parametrize("text", ["LIB-H01-E02", "A-3.2", "LIB-3", "Ｑ－3"])
    def test_a_hyphen_right_after_a_letter_of_an_id_is_not_a_sign(
        self, text: str
    ) -> None:
        assert set(signs(text)) == {""}

    def test_a_hyphen_after_a_japanese_word_is_a_sign(self) -> None:
        assert signs("前年比-3.2%") == ["-"]

    @pytest.mark.parametrize(
        ("text", "sign"), [("- 3.2", "-"), ("▲ 3.2", "-"), ("+ 3.2", "+")]
    )
    def test_a_sign_set_apart_by_spaces_still_belongs_to_the_number(
        self, text: str, sign: str
    ) -> None:
        assert signs(text) == [sign]

    def test_a_range_written_with_spaces_reads_as_a_signed_number(self) -> None:
        # Told apart from "10 -20" by nothing a reader could rely on, so it
        # falls on the side of a violation.
        assert signs("10 - 20") == ["", "-"]

    def test_a_wave_dash_is_a_range_never_a_sign(self) -> None:
        assert signs("〜3日") == [""]

    def test_a_number_is_a_whole_token_never_a_substring(self) -> None:
        assert Decimal("1.9") not in values("21.95")
        assert Decimal(5) not in values("152")

    def test_nothing_is_exempt_for_looking_like_an_id_or_a_date(self) -> None:
        assert values("LIB-H01-E02は2026年11月21日") == [
            Decimal(1),
            Decimal(2),
            Decimal(2026),
            Decimal(11),
            Decimal(21),
        ]


ROOT_QUESTION = "取り置き期限を延ばす試行をするか"


def node(node_id: str, parent: str | None = None, **fields: object) -> dict:
    base: dict = {"id": node_id, "question": f"{node_id} の問い"}
    if parent is not None:
        base |= {"parent_question_id": parent, "contribution": "寄与"}
    return base | fields


def answer_of(*statements: dict, round: int = 1) -> dict:
    return {"round": round, "root_revision": 1, "statements": list(statements)}


def claim(text: str, *cites: str) -> dict:
    return {"kind": "claim", "text": text, "cites": list(cites)}


def tree_with(*nodes: dict) -> QuestionTree:
    """LIB-Q01 (root) with LIB-Q02 under it, then whatever *nodes* adds."""
    return QuestionTree.model_validate(
        {
            "theme_id": "LIB",
            "root_revisions": [
                {
                    "revision": 1,
                    "question": ROOT_QUESTION,
                    "aim": {
                        "kind": "business",
                        "decision_maker": "図書館員",
                        "decision": "取り置き期限を延ばす試行を始めるか",
                    },
                }
            ],
            "nodes": [{"id": "LIB-Q01", "question": ROOT_QUESTION}, *nodes],
        }
    )


def checked(statement: dict, events: dict[str, str]) -> list[Violation]:
    """Violations of one answer to LIB-Q02, which links LIB-H01."""
    tree = tree_with(
        node(
            "LIB-Q02", "LIB-Q01", design_ids=["LIB-H01"], answers=[answer_of(statement)]
        )
    )
    return find_violations(tree, events)


class TestFindViolations:
    def test_an_answer_that_only_cites_what_the_journal_holds_is_clean(self) -> None:
        events = {"LIB-H01-E01": "取消を除いた期限切れは34.6%だった"}
        assert checked(claim("期限切れは34.6%だった", "LIB-H01-E01"), events) == []

    def test_a_cite_without_an_event_is_a_missing_event(self) -> None:
        found = checked(claim("取消を除いた", "LIB-H01-E09"), {})
        assert found == [Violation("LIB-Q02", 1, 1, "missing-event", "LIB-H01-E09")]

    def test_a_cite_of_a_design_outside_the_node_is_an_unlinked_design(self) -> None:
        events = {"LIB-H02-E01": "記録"}
        found = checked(claim("記録のとおり", "LIB-H02-E01"), events)
        assert found == [Violation("LIB-Q02", 1, 1, "unlinked-design", "LIB-H02-E01")]

    def test_a_number_that_no_cited_event_holds_is_not_cited(self) -> None:
        events = {"LIB-H01-E01": "期限切れは152件"}
        found = checked(claim("期限切れは153件だった", "LIB-H01-E01"), events)
        assert found == [Violation("LIB-Q02", 1, 1, "number-not-cited", "153")]

    def test_a_number_is_compared_by_value(self) -> None:
        events = {"LIB-H01-E01": "割合は１，２００．０％"}
        assert checked(claim("割合は1200パーセント", "LIB-H01-E01"), events) == []

    def test_a_signed_number_the_record_states_in_words_is_not_cited(self) -> None:
        events = {"LIB-H01-E01": "期限切れは3.2ポイント減った"}
        found = checked(claim("期限切れは−3.2ポイント", "LIB-H01-E01"), events)
        assert [(v.kind, v.text) for v in found] == [("number-not-cited", "−3.2")]

    @pytest.mark.parametrize(
        ("recorded", "written", "token"),
        [
            ("3.2", "△3.2", "△3.2"),
            ("3.2", "- 3.2", "- 3.2"),
            ("A-3.2", "−3.2", "−3.2"),
        ],
    )
    def test_no_spelling_of_a_sign_slips_past_an_unsigned_record(
        self, recorded: str, written: str, token: str
    ) -> None:
        events = {"LIB-H01-E01": f"差は {recorded} ポイント"}
        found = checked(claim(f"差は {written} ポイント", "LIB-H01-E01"), events)
        assert [(v.kind, v.text) for v in found] == [("number-not-cited", token)]

    def test_the_same_sign_in_another_glyph_is_the_same_number(self) -> None:
        events = {"LIB-H01-E01": "前年比 -3.2%"}
        assert checked(claim("前年比▲3.2%", "LIB-H01-E01"), events) == []

    def test_a_recorded_plus_sign_passes_when_written_again(self) -> None:
        events = {"LIB-H01-E01": "前年比 +3.2%"}
        assert checked(claim("前年比+3.2%", "LIB-H01-E01"), events) == []

    @pytest.mark.parametrize(
        ("recorded", "written", "token"),
        [
            ("-3.2", "3.2", "3.2"),
            ("-3.2", "+3.2", "+3.2"),
            ("3.2", "+3.2", "+3.2"),
            ("+3.2", "3.2", "3.2"),
        ],
    )
    def test_a_number_matches_only_with_the_sign_the_record_wrote(
        self, recorded: str, written: str, token: str
    ) -> None:
        events = {"LIB-H01-E01": f"差は {recorded} ポイント"}
        found = checked(claim(f"差は {written} ポイント", "LIB-H01-E01"), events)
        assert [(v.kind, v.text) for v in found] == [("number-not-cited", token)]

    def test_without_any_existing_event_every_number_is_not_cited(self) -> None:
        found = checked(claim("152件だった", "LIB-H01-E09"), {})
        assert [(v.kind, v.text) for v in found] == [
            ("missing-event", "LIB-H01-E09"),
            ("number-not-cited", "152"),
        ]

    def test_a_number_repeated_in_one_statement_is_reported_once(self) -> None:
        events = {"LIB-H01-E01": "記録"}
        found = checked(claim("7件、つまり7.0件", "LIB-H01-E01"), events)
        assert [v.text for v in found] == ["7"]

    def test_a_number_in_a_cite_id_does_not_count_as_cited(self) -> None:
        events = {"LIB-H01-E01": "記録"}
        assert checked(claim("1件", "LIB-H01-E01"), events)[0].text == "1"

    def test_only_the_last_answer_of_a_node_is_checked(self) -> None:
        old = answer_of(claim("999件", "LIB-H01-E09"), round=1)
        new = answer_of(claim("記録のとおり", "LIB-H01-E01"), round=2)
        tree = tree_with(
            node("LIB-Q02", "LIB-Q01", design_ids=["LIB-H01"], answers=[old, new])
        )
        assert find_violations(tree, {"LIB-H01-E01": "記録"}) == []

    def test_the_violation_names_the_round_and_the_statement(self) -> None:
        first = answer_of(claim("記録", "LIB-H01-E01"), round=1)
        second = answer_of(
            claim("記録", "LIB-H01-E01"), claim("9件", "LIB-H01-E01"), round=2
        )
        tree = tree_with(
            node("LIB-Q02", "LIB-Q01", design_ids=["LIB-H01"], answers=[first, second])
        )
        (found,) = find_violations(tree, {"LIB-H01-E01": "記録"})
        assert (found.round, found.statement) == (2, 2)

    def _nested(self, answered: str) -> QuestionTree:
        """Q02 (H01) has the children Q03 (H02) and Q04 (H03); Q03 has Q05 (H04)."""
        answer = answer_of(claim("記録", "LIB-H04-E01"))
        nodes = {
            "LIB-Q02": node("LIB-Q02", "LIB-Q01", design_ids=["LIB-H01"]),
            "LIB-Q03": node("LIB-Q03", "LIB-Q02", design_ids=["LIB-H02"]),
            "LIB-Q04": node("LIB-Q04", "LIB-Q02", design_ids=["LIB-H03"]),
            "LIB-Q05": node("LIB-Q05", "LIB-Q03", design_ids=["LIB-H04"]),
        }
        nodes[answered]["answers"] = [answer]
        return tree_with(*nodes.values())

    def test_a_parent_may_cite_a_design_linked_to_a_grandchild(self) -> None:
        assert find_violations(self._nested("LIB-Q02"), {"LIB-H04-E01": "記録"}) == []

    def test_a_sibling_branch_is_not_a_place_to_cite_from(self) -> None:
        found = find_violations(self._nested("LIB-Q04"), {"LIB-H04-E01": "記録"})
        assert [v.kind for v in found] == ["unlinked-design"]

    def test_a_child_may_not_cite_a_design_linked_only_to_its_parent(self) -> None:
        tree = tree_with(
            node("LIB-Q02", "LIB-Q01", design_ids=["LIB-H01"]),
            node(
                "LIB-Q03",
                "LIB-Q02",
                answers=[answer_of(claim("記録", "LIB-H01-E01"))],
            ),
        )
        found = find_violations(tree, {"LIB-H01-E01": "記録"})
        assert [v.kind for v in found] == ["unlinked-design"]

    def test_violations_are_ordered_by_node_statement_cite_then_number(self) -> None:
        tree = tree_with(
            node(
                "LIB-Q02",
                "LIB-Q01",
                answers=[
                    answer_of(
                        claim("8件と9件", "LIB-H01-E01", "LIB-H02-E01"),
                        claim("5件", "LIB-H01-E01"),
                    )
                ],
            ),
            node(
                "LIB-Q03", "LIB-Q01", answers=[answer_of(claim("記録", "LIB-H01-E02"))]
            ),
        )
        found = find_violations(tree, {"LIB-H02-E01": "記録"})
        assert [(v.node_id, v.statement, v.kind, v.text) for v in found] == [
            ("LIB-Q02", 1, "missing-event", "LIB-H01-E01"),
            ("LIB-Q02", 1, "unlinked-design", "LIB-H01-E01"),
            ("LIB-Q02", 1, "unlinked-design", "LIB-H02-E01"),
            ("LIB-Q02", 1, "number-not-cited", "8"),
            ("LIB-Q02", 1, "number-not-cited", "9"),
            ("LIB-Q02", 2, "missing-event", "LIB-H01-E01"),
            ("LIB-Q02", 2, "unlinked-design", "LIB-H01-E01"),
            ("LIB-Q02", 2, "number-not-cited", "5"),
            ("LIB-Q03", 1, "missing-event", "LIB-H01-E02"),
            ("LIB-Q03", 1, "unlinked-design", "LIB-H01-E02"),
        ]


class TestTheNumberThatWasNeverRecorded:
    """#105: a ratio computed in the answer passed as if the journal held it."""

    EVENTS = {
        "LIB-H01-E01": "期限切れの予約は152件だった",
        "LIB-H01-E02": "取消を除くと80件だった",
    }

    def test_a_ratio_made_from_two_cited_counts_is_stopped(self) -> None:
        text = "期限切れは取消除外後のおよそ1.9倍だった"
        found = checked(claim(text, "LIB-H01-E01", "LIB-H01-E02"), self.EVENTS)
        assert found == [Violation("LIB-Q02", 1, 1, "number-not-cited", "1.9")]

    def test_a_ratio_written_as_a_round_number_is_stopped_too(self) -> None:
        text = "期限切れは取消除外後のおよそ2倍だった"
        found = checked(claim(text, "LIB-H01-E01", "LIB-H01-E02"), self.EVENTS)
        assert [(v.kind, v.text) for v in found] == [("number-not-cited", "2")]

    def test_transcribing_the_recorded_numbers_passes(self) -> None:
        text = "期限切れは152件で、取消を除くと80件だった"
        assert checked(claim(text, "LIB-H01-E01", "LIB-H01-E02"), self.EVENTS) == []

    def test_a_computed_number_passes_once_a_cited_event_records_it(self) -> None:
        events = self.EVENTS | {"LIB-H01-E03": "152 / 80 = 1.9 と計算した"}
        text = "期限切れは取消除外後のおよそ1.9倍だった"
        cites = ("LIB-H01-E01", "LIB-H01-E02", "LIB-H01-E03")
        assert checked(claim(text, *cites), events) == []


def write_tree(base: Path, tree: QuestionTree) -> Path:
    path = base / "themes" / "LIB_tree.yaml"
    atomic_write_yaml(
        path, tree.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    )
    return path


def write_journal(base: Path, design_id: str, *events: tuple[int, object]) -> None:
    design_io.write_journal(
        design_id,
        {
            "events": [
                {"id": f"{design_id}-E{n:02d}", "type": "observe", "content": content}
                for n, content in events
            ]
        },
        base_dir=base,
    )


def answered_tree(text: str, *cites: str) -> QuestionTree:
    return tree_with(
        node(
            "LIB-Q02",
            "LIB-Q01",
            design_ids=["LIB-H01"],
            answers=[answer_of(claim(text, *cites))],
        )
    )


def snapshot(base: Path) -> dict[str, bytes | None]:
    return {
        str(p.relative_to(base)): p.read_bytes() if p.is_file() else None
        for p in sorted(base.rglob("*"))
    }


class TestCheckTheme:
    def test_it_reads_the_journal_of_each_cited_design(self, tmp_path: Path) -> None:
        write_tree(tmp_path, answered_tree("期限切れは152件", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, "期限切れは152件"))

        assert tree_check.check_theme("LIB", tmp_path) == []

    def test_a_journal_file_that_does_not_exist_makes_the_cite_missing(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, answered_tree("記録", "LIB-H01-E01"))

        found = tree_check.check_theme("LIB", tmp_path)

        assert [v.kind for v in found] == ["missing-event"]

    def test_an_event_without_content_holds_no_numbers(self, tmp_path: Path) -> None:
        write_tree(tmp_path, answered_tree("3件", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, None))

        found = tree_check.check_theme("LIB", tmp_path)

        assert [(v.kind, v.text) for v in found] == [("number-not-cited", "3")]

    def test_content_written_as_a_bare_number_is_read_as_its_text(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, answered_tree("割合は34.6%", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, 34.6))

        assert tree_check.check_theme("LIB", tmp_path) == []

    def test_an_event_filed_in_the_journal_of_another_design_is_missing(
        self, tmp_path: Path
    ) -> None:
        tree = tree_with(
            node(
                "LIB-Q02",
                "LIB-Q01",
                design_ids=["LIB-H01", "LIB-H02"],
                answers=[answer_of(claim("999件", "LIB-H01-E01", "LIB-H02-E05"))],
            )
        )
        write_tree(tmp_path, tree)
        design_io.write_journal(
            "LIB-H01",
            {
                "events": [
                    {"id": "LIB-H01-E01", "content": "記録"},
                    {"id": "LIB-H02-E05", "content": "999件"},
                ]
            },
            base_dir=tmp_path,
        )

        found = tree_check.check_theme("LIB", tmp_path)

        assert [(v.kind, v.text) for v in found] == [
            ("missing-event", "LIB-H02-E05"),
            ("number-not-cited", "999"),
        ]

    def test_an_event_whose_id_is_not_text_is_skipped(self, tmp_path: Path) -> None:
        write_tree(tmp_path, answered_tree("記録", "LIB-H01-E01"))
        design_io.write_journal(
            "LIB-H01", {"events": [{"id": ["x"], "content": "記録"}]}, base_dir=tmp_path
        )

        found = tree_check.check_theme("LIB", tmp_path)

        assert [v.kind for v in found] == ["missing-event"]

    def test_a_cited_id_that_two_events_share_cannot_be_checked(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, answered_tree("152件", "LIB-H01-E01"))
        design_io.write_journal(
            "LIB-H01",
            {
                "events": [
                    {"id": "LIB-H01-E01", "content": "152件"},
                    {"id": "LIB-H01-E01", "content": "80件"},
                ]
            },
            base_dir=tmp_path,
        )

        with pytest.raises(ValueError, match="LIB-H01-E01"):
            tree_check.check_theme("LIB", tmp_path)

    def test_a_tree_that_names_another_theme_cannot_be_checked(
        self, tmp_path: Path
    ) -> None:
        data = answered_tree("記録", "LIB-H01-E01").model_dump(
            mode="json", exclude_none=True, exclude_defaults=True
        )
        other = json.loads(json.dumps(data).replace("LIB", "FP"))
        atomic_write_yaml(tmp_path / "themes" / "LIB_tree.yaml", other)

        with pytest.raises(ValueError, match="does not match"):
            tree_check.check_theme("LIB", tmp_path)

    def test_a_journal_without_an_event_list_has_no_events(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, answered_tree("記録", "LIB-H01-E01"))
        design_io.write_journal("LIB-H01", {"events": "none"}, base_dir=tmp_path)

        found = tree_check.check_theme("LIB", tmp_path)

        assert [v.kind for v in found] == ["missing-event"]

    def test_it_writes_nothing(self, tmp_path: Path) -> None:
        write_tree(tmp_path, answered_tree("152件", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, "記録"))
        before = snapshot(tmp_path)

        tree_check.check_theme("LIB", tmp_path)

        assert snapshot(tmp_path) == before

    def test_it_creates_no_designs_directory_when_none_exists(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, answered_tree("記録", "LIB-H01-E01"))

        tree_check.check_theme("LIB", tmp_path)

        assert not (tmp_path / "designs").exists()


class TestCheckTree:
    def test_it_checks_a_tree_that_is_not_on_disk(self, tmp_path: Path) -> None:
        write_journal(tmp_path, "LIB-H01", (1, "期限切れは152件"))

        found = tree_check.check_tree(
            answered_tree("期限切れは999件", "LIB-H01-E01"), tmp_path
        )

        assert [(v.kind, v.text) for v in found] == [("number-not-cited", "999")]


def run_main(
    capsys: pytest.CaptureFixture[str], base: Path, theme: str = "LIB"
) -> tuple[int, str, str]:
    code = tree_check._main(["--theme", theme, "--base-dir", str(base)])
    out = capsys.readouterr()
    return code, out.out, out.err


class TestMain:
    def test_it_exits_0_and_prints_no_violations_for_a_clean_tree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, answered_tree("152件", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, "152件"))

        code, out, _ = run_main(capsys, tmp_path)

        assert code == 0
        assert json.loads(out) == {
            "tree": str(tmp_path / "themes" / "LIB_tree.yaml"),
            "violations": [],
        }

    def test_it_exits_1_and_prints_each_violation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, answered_tree("153件", "LIB-H01-E01"))
        write_journal(tmp_path, "LIB-H01", (1, "152件"))

        code, out, _ = run_main(capsys, tmp_path)

        assert code == 1
        assert json.loads(out)["violations"] == [
            {
                "node_id": "LIB-Q02",
                "round": 1,
                "statement": 1,
                "kind": "number-not-cited",
                "text": "153",
            }
        ]

    def test_it_keeps_non_ascii_text_unescaped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        base = tmp_path / "図書館"
        write_tree(base, answered_tree("記録", "LIB-H01-E01"))
        write_journal(base, "LIB-H01", (1, "記録"))

        _, out, _ = run_main(capsys, base)

        assert "図書館" in out

    @pytest.mark.parametrize("theme", ["lib", "../LIB", "LIB X"])
    def test_it_exits_2_for_a_theme_id_that_is_not_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], theme: str
    ) -> None:
        code, out, err = run_main(capsys, tmp_path, theme)

        assert (code, out) == (2, "")
        assert err.startswith("tree_check: ")

    def test_it_exits_2_when_the_theme_has_no_tree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, err = run_main(capsys, tmp_path)

        assert (code, out) == (2, "")
        assert "no question tree" in err

    def test_it_exits_2_for_a_tree_that_fails_the_schema(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        atomic_write_yaml(tmp_path / "themes" / "LIB_tree.yaml", {"theme_id": "LIB"})

        code, out, err = run_main(capsys, tmp_path)

        assert (code, out) == (2, "")
        assert err.startswith("tree_check: ")

    def test_it_exits_2_for_yaml_that_cannot_be_read(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "themes" / "LIB_tree.yaml"
        path.parent.mkdir()
        path.write_text("nodes: [unclosed", encoding="utf-8")

        code, out, err = run_main(capsys, tmp_path)

        assert (code, out) == (2, "")
        assert err.startswith("tree_check: ")

    def test_it_exits_2_not_1_when_the_check_fails_in_a_way_nobody_foresaw(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def broken(*_: object) -> list[Violation]:
            raise RuntimeError("boom")

        monkeypatch.setattr(tree_check, "check_theme", broken)

        code, out, err = run_main(capsys, tmp_path)

        assert (code, out) == (2, "")
        assert err.startswith("tree_check: ")

    def test_it_requires_a_theme(self) -> None:
        with pytest.raises(SystemExit) as exc:
            tree_check._main([])
        assert exc.value.code == 2

    def test_it_creates_nothing_when_the_base_dir_is_empty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_main(capsys, tmp_path)

        assert list(tmp_path.iterdir()) == []
