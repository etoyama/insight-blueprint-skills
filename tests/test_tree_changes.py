"""Tests for tree_changes: what an answer changed since the answer before it (Epic 34).

The change is derived from the cites of two answers and never stored (ADR-0056).
Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import copy

from insight_blueprint.models.tree import AnswerStatement, QuestionTree, StatementKind
from insight_blueprint.validate import validate_tree_schema
from skills._shared.tree_changes import (
    AnswerChange,
    ChangeKind,
    CitedAbove,
    EvidenceChange,
    UncitedBelow,
    answer_changes,
    cited_above,
    uncited_below,
)

AIM = {
    "kind": "business",
    "decision_maker": "図書館員",
    "decision": "取り置き期限を延ばす試行を始めるか",
}

E1, E2, E3 = "LIB-H01-E01", "LIB-H01-E02", "LIB-H01-E03"


def said(kind: str, text: str, *cites: str) -> dict:
    return {"kind": kind, "text": text, "cites": list(cites)}


def answer(round: int, *statements: dict) -> dict:
    return {"round": round, "root_revision": 1, "statements": list(statements)}


def tree_of(*answers: dict, others: tuple[dict, ...] = ()) -> QuestionTree:
    """A tree whose root holds *answers*; *others* are answers of LIB-Q02."""
    return validate_tree_schema(
        copy.deepcopy(
            {
                "theme_id": "LIB",
                "root_revisions": [
                    {"revision": 1, "question": "試行をするか", "aim": AIM}
                ],
                "nodes": [
                    {
                        "id": "LIB-Q01",
                        "question": "試行をするか",
                        "answers": list(answers),
                    },
                    {
                        "id": "LIB-Q02",
                        "question": "数えられるか",
                        "parent_question_id": "LIB-Q01",
                        "contribution": "件数が変わる",
                        "design_ids": ["LIB-H01"],
                        "answers": list(others),
                    },
                ],
            }
        )
    )


def change_of(*answers: dict) -> AnswerChange:
    return answer_changes(tree_of(*answers))["LIB-Q01"]


def kinds(change: AnswerChange) -> dict[str, ChangeKind]:
    return {e.event_id: e.kind for e in change.evidence}


def row(change: AnswerChange, event_id: str) -> EvidenceChange:
    (found,) = [e for e in change.evidence if e.event_id == event_id]
    return found


def texts(statements: tuple) -> list[str]:
    return [s.text for s in statements]


class TestWhichAnswersAreCompared:
    def test_a_node_without_an_answer_has_no_change(self) -> None:
        assert answer_changes(tree_of()) == {}

    def test_a_node_answered_once_has_no_change(self) -> None:
        assert answer_changes(tree_of(answer(1, said("claim", "346 件", E1)))) == {}

    def test_the_last_answer_is_compared_with_the_one_before_it(self) -> None:
        change = change_of(
            answer(1, said("claim", "最初の文", E1)),
            answer(2, said("claim", "2回目の文", E2)),
            answer(4, said("claim", "3回目の文", E3)),
        )

        assert (change.node_id, change.previous_round, change.round) == (
            "LIB-Q01",
            2,
            4,
        )
        assert kinds(change) == {E3: ChangeKind.newly_cited, E2: ChangeKind.dropped}

    def test_each_node_with_two_answers_has_its_own_change(self) -> None:
        tree = tree_of(
            answer(1, said("claim", "346 件", E1)),
            others=(
                answer(1, said("claim", "数えられる", E1)),
                answer(
                    2, said("claim", "数えられる", E1), said("weakening", "1館", E2)
                ),
            ),
        )

        changes = answer_changes(tree)

        assert list(changes) == ["LIB-Q02"]
        assert kinds(changes["LIB-Q02"]) == {
            E1: ChangeKind.unchanged,
            E2: ChangeKind.newly_cited,
        }


class TestHowAnEventChanged:
    def test_an_event_only_the_last_answer_cites_is_newly_cited(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("claim", "346 件", E1), said("weakening", "1館だけ", E2)),
        )

        found = row(change, E2)
        assert found.kind is ChangeKind.newly_cited
        assert found.before == ()
        assert texts(found.after) == ["1館だけ"]

    def test_an_event_only_the_answer_before_cites_is_dropped(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1), said("weakening", "1館だけ", E2)),
            answer(2, said("claim", "346 件", E1)),
        )

        found = row(change, E2)
        assert found.kind is ChangeKind.dropped
        assert texts(found.before) == ["1館だけ"]
        assert found.after == ()

    def test_an_event_cited_by_another_text_is_reworded(self) -> None:
        change = change_of(
            answer(1, said("claim", "期限切れは 346 件", E1)),
            answer(2, said("claim", "期限切れは 346 件で、延長の余地がある", E1)),
        )

        found = row(change, E1)
        assert found.kind is ChangeKind.reworded
        assert texts(found.before) == ["期限切れは 346 件"]
        assert texts(found.after) == ["期限切れは 346 件で、延長の余地がある"]

    def test_the_same_text_under_another_kind_is_reworded(self) -> None:
        change = change_of(
            answer(1, said("claim", "期限切れは 346 件", E1)),
            answer(2, said("weakening", "期限切れは 346 件", E1)),
        )

        found = row(change, E1)
        assert found.kind is ChangeKind.reworded
        assert found.before[0].kind is StatementKind.claim
        assert found.after[0].kind is StatementKind.weakening

    def test_an_event_a_second_statement_now_cites_is_reworded(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("claim", "346 件", E1), said("undetermined", "保留", E1)),
        )

        found = row(change, E1)
        assert found.kind is ChangeKind.reworded
        assert texts(found.before) == ["346 件"]
        assert texts(found.after) == ["346 件", "保留"]

    def test_an_event_cited_by_the_same_statements_is_unchanged(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1), said("weakening", "1館だけ", E2)),
            answer(2, said("claim", "346 件", E1), said("weakening", "1館のみ", E2)),
        )

        assert kinds(change) == {E1: ChangeKind.unchanged, E2: ChangeKind.reworded}

    def test_the_order_of_the_statements_does_not_make_a_change(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1), said("weakening", "1館だけ", E1)),
            answer(2, said("weakening", "1館だけ", E1), said("claim", "346 件", E1)),
        )

        assert kinds(change) == {E1: ChangeKind.unchanged}

    def test_the_other_cites_of_a_statement_do_not_reword_an_event(self) -> None:
        # E1 backs the same sentence in both rounds; that the sentence now
        # also cites E2 is a change of E2, not of E1.
        change = change_of(
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("claim", "346 件", E1, E2)),
        )

        assert kinds(change) == {E1: ChangeKind.unchanged, E2: ChangeKind.newly_cited}


class TestOneRowPerEvent:
    def test_two_events_changed_in_one_round_are_two_rows(self) -> None:
        change = change_of(
            answer(
                1, said("claim", "相関は 0.41", E1), said("claim", "0.30 上がった", E2)
            ),
            answer(
                2,
                said("weakening", "相関 0.41 は負荷で説明できる", E1, E3),
                said("claim", "0.30 上がった", E2),
                said("undetermined", "どちらを優先するかは保留", E2),
            ),
        )

        assert kinds(change) == {
            E1: ChangeKind.reworded,
            E3: ChangeKind.newly_cited,
            E2: ChangeKind.reworded,
        }

    def test_an_event_cited_twice_by_one_statement_is_one_row(self) -> None:
        change = change_of(
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("claim", "346 件", E1, E1)),
        )

        assert [e.event_id for e in change.evidence] == [E1]
        assert texts(row(change, E1).after) == ["346 件"]

    def test_the_rows_follow_the_last_answer_then_the_dropped_events(self) -> None:
        change = change_of(
            answer(1, said("claim", "a", E3), said("claim", "b", E1)),
            answer(2, said("claim", "c", E2), said("claim", "b", E1)),
        )

        assert [e.event_id for e in change.evidence] == [E2, E1, E3]


class TestDerivedNotStored:
    def test_the_same_tree_gives_the_same_changes(self) -> None:
        answers = (
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("weakening", "1館だけ", E2)),
        )

        assert answer_changes(tree_of(*answers)) == answer_changes(tree_of(*answers))

    def test_deriving_leaves_the_tree_as_it_was(self) -> None:
        tree = tree_of(
            answer(1, said("claim", "346 件", E1)),
            answer(2, said("weakening", "1館だけ", E2)),
        )
        before = tree.model_dump()

        answer_changes(tree)

        assert tree.model_dump() == before


# --- What the answers below a node cite and its own answer does not (ADR-0056) ---

F1, F2 = "LIB-H02-E01", "LIB-H02-E02"


def three_levels(
    root: tuple[dict, ...] = (),
    q02: tuple[dict, ...] = (),
    q03: tuple[dict, ...] = (),
    q04: tuple[dict, ...] = (),
) -> QuestionTree:
    """LIB-Q01 over LIB-Q02 (LIB-H01) over LIB-Q03 (LIB-H02); LIB-Q04 is a leaf."""

    def node(node_id: str, parent: str, design: str, answers: tuple) -> dict:
        return {
            "id": node_id,
            "question": f"{node_id} の問い",
            "parent_question_id": parent,
            "contribution": "件数が変わる",
            "design_ids": [design],
            "answers": list(answers),
        }

    return validate_tree_schema(
        copy.deepcopy(
            {
                "theme_id": "LIB",
                "root_revisions": [
                    {"revision": 1, "question": "試行をするか", "aim": AIM}
                ],
                "nodes": [
                    {
                        "id": "LIB-Q01",
                        "question": "試行をするか",
                        "answers": list(root),
                    },
                    node("LIB-Q02", "LIB-Q01", "LIB-H01", q02),
                    node("LIB-Q03", "LIB-Q02", "LIB-H02", q03),
                    node("LIB-Q04", "LIB-Q01", "LIB-H03", q04),
                ],
            }
        )
    )


def ids_of(found: tuple) -> list[str]:
    return [u.event_id for u in found]


class TestWhatTheAnswersBelowCite:
    def test_an_event_the_answer_below_cites_and_the_node_does_not_is_listed(
        self,
    ) -> None:
        tree = three_levels(
            root=(answer(2, said("claim", "延ばす", E1)),),
            q02=(
                answer(2, said("claim", "数えられる", E1), said("claim", "減る", E2)),
            ),
        )

        (found,) = uncited_below(tree)["LIB-Q01"]

        assert found == UncitedBelow(
            event_id=E2,
            node_id="LIB-Q02",
            round=2,
            statements=(
                AnswerStatement(kind=StatementKind.claim, text="減る", cites=[E2]),
            ),
            last_cited_round=None,
            cited_instead=(),
        )

    def test_a_node_whose_answer_cites_everything_below_lists_nothing(self) -> None:
        tree = three_levels(
            root=(answer(1, said("claim", "延ばす", E1)),),
            q02=(answer(1, said("claim", "数えられる", E1)),),
        )

        assert "LIB-Q01" not in uncited_below(tree)

    def test_a_node_without_an_answer_lists_every_event_cited_below(self) -> None:
        tree = three_levels(
            q02=(
                answer(1, said("claim", "数えられる", E1), said("claim", "減る", E2)),
            ),
        )

        assert ids_of(uncited_below(tree)["LIB-Q01"]) == [E1, E2]

    def test_only_the_current_answer_below_counts(self) -> None:
        tree = three_levels(
            root=(answer(2, said("claim", "延ばす", E1)),),
            q02=(
                answer(1, said("claim", "減る", E2)),
                answer(2, said("claim", "数えられる", E1)),
            ),
        )

        assert "LIB-Q01" not in uncited_below(tree)

    def test_events_cited_further_below_are_listed_too(self) -> None:
        tree = three_levels(
            root=(answer(1, said("claim", "延ばす", E1)),),
            q02=(answer(1, said("claim", "数えられる", E1)),),
            q03=(answer(1, said("claim", "金曜が多い", F1)),),
        )

        found = uncited_below(tree)

        assert ids_of(found["LIB-Q01"]) == [F1]
        assert ids_of(found["LIB-Q02"]) == [F1]
        assert found["LIB-Q01"][0].node_id == "LIB-Q03"

    def test_an_event_cited_at_two_levels_below_comes_from_the_nearer_answer(
        self,
    ) -> None:
        tree = three_levels(
            q02=(answer(1, said("claim", "金曜に集まる", F1)),),
            q03=(answer(1, said("claim", "金曜が多い", F1)),),
        )

        (found,) = uncited_below(tree)["LIB-Q01"]

        assert found.node_id == "LIB-Q02"
        assert texts(found.statements) == ["金曜に集まる"]

    def test_the_listed_events_follow_the_nodes_then_their_statements(self) -> None:
        tree = three_levels(
            q02=(answer(1, said("claim", "減る", E2), said("claim", "数える", E1)),),
            q03=(answer(1, said("claim", "金曜", F2)),),
            q04=(answer(1, said("claim", "別館", "LIB-H03-E01")),),
        )

        assert ids_of(uncited_below(tree)["LIB-Q01"]) == [
            E2,
            E1,
            F2,
            "LIB-H03-E01",
        ]

    def test_a_node_with_nothing_below_has_no_entry(self) -> None:
        tree = three_levels(q04=(answer(1, said("claim", "別館", "LIB-H03-E01")),))

        assert "LIB-Q04" not in uncited_below(tree)


class TestAnEventTheNodeCitedBefore:
    def test_an_event_cited_before_has_the_last_round_that_cited_it(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "相関がある", E1)),
                answer(2, said("claim", "同じ人で上がる", F1)),
                answer(3, said("claim", "同じ人で上がる", F1)),
            ),
            q02=(answer(1, said("claim", "相関は 0.41", E1)),),
            q03=(answer(2, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = uncited_below(tree)["LIB-Q01"]

        assert found.event_id == E1
        assert found.last_cited_round == 1
        assert found.cited_instead == (F1,)

    def test_the_last_round_is_the_latest_that_cited_it(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "相関", E1)),
                answer(2, said("claim", "外す", E2)),
                answer(3, said("claim", "相関", E1), said("claim", "外す", E2)),
                answer(4, said("claim", "外す", E2), said("claim", "金曜", F1)),
            ),
            q02=(
                answer(1, said("claim", "相関は 0.41", E1), said("claim", "減る", E2)),
            ),
            q03=(answer(1, said("claim", "金曜", F1)),),
        )

        (found,) = uncited_below(tree)["LIB-Q01"]

        assert found.last_cited_round == 3
        assert found.cited_instead == (F1,)

    def test_nothing_cited_instead_is_an_empty_tuple(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "相関", E1), said("claim", "減る", E2)),
                answer(2, said("claim", "減る", E2)),
            ),
            q02=(
                answer(1, said("claim", "相関は 0.41", E1), said("claim", "減る", E2)),
            ),
        )

        (found,) = uncited_below(tree)["LIB-Q01"]

        assert found.last_cited_round == 1
        assert found.cited_instead == ()

    def test_deriving_gives_the_same_values_and_leaves_the_tree(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "相関", E1)),
                answer(2, said("claim", "減る", E2)),
            ),
            q02=(
                answer(1, said("claim", "相関は 0.41", E1), said("claim", "減る", E2)),
            ),
        )
        before = tree.model_dump()

        assert uncited_below(tree) == uncited_below(tree)
        assert tree.model_dump() == before


# --- How the answers above a node cite what its own answer cites (ADR-0056) ---


def above_of(tree: QuestionTree, node_id: str) -> list[tuple[str, str]]:
    return [(a.event_id, a.node_id) for a in cited_above(tree)[node_id]]


class TestWhereTheAnswersAboveCiteIt:
    def test_an_event_the_parent_also_cites_is_listed_with_its_answer(self) -> None:
        tree = three_levels(
            q02=(answer(2, said("claim", "上がる", F1), said("claim", "数える", E1)),),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found == CitedAbove(
            event_id=F1,
            node_id="LIB-Q02",
            round=2,
            statements=(
                AnswerStatement(kind=StatementKind.claim, text="上がる", cites=[F1]),
            ),
            reworded_in=None,
        )

    def test_an_answer_further_above_is_listed_after_the_nearer_one(self) -> None:
        tree = three_levels(
            root=(answer(1, said("weakening", "1館だけ", F1)),),
            q02=(answer(1, said("claim", "上がる", F1)),),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        assert above_of(tree, "LIB-Q03") == [(F1, "LIB-Q02"), (F1, "LIB-Q01")]

    def test_the_subject_is_listed_when_the_parent_does_not_cite_it(self) -> None:
        tree = three_levels(
            root=(answer(1, said("weakening", "1館だけ", F1)),),
            q02=(answer(1, said("claim", "数える", E1)),),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        assert above_of(tree, "LIB-Q03") == [(F1, "LIB-Q01")]

    def test_only_the_current_answer_above_counts(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "上がる", F1)),
                answer(2, said("claim", "数える", E1)),
            ),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        assert "LIB-Q03" not in cited_above(tree)

    def test_a_node_without_an_answer_has_no_entry(self) -> None:
        tree = three_levels(q02=(answer(1, said("claim", "上がる", F1)),))

        assert "LIB-Q03" not in cited_above(tree)

    def test_the_entries_follow_the_cites_of_the_node(self) -> None:
        tree = three_levels(
            root=(answer(1, said("claim", "金曜", F2), said("claim", "上がる", F1)),),
            q03=(
                answer(1, said("claim", "0.30", F1), said("claim", "金曜が多い", F2)),
            ),
        )

        assert above_of(tree, "LIB-Q03") == [(F1, "LIB-Q01"), (F2, "LIB-Q01")]


class TestTheRoundTheAnswerAboveChangedIt:
    def test_a_later_answer_above_that_says_something_else_is_its_round(
        self,
    ) -> None:
        tree = three_levels(
            root=(
                answer(2, said("claim", "上がった", F1)),
                answer(3, said("undetermined", "分けられない", F1)),
            ),
            q03=(answer(2, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.round == 3
        assert found.reworded_in == 3

    def test_the_first_round_that_changed_it_is_kept_after_more_rewriting(
        self,
    ) -> None:
        tree = three_levels(
            root=(
                answer(2, said("claim", "上がった", F1)),
                answer(3, said("undetermined", "分けられない", F1)),
                answer(
                    4,
                    said("undetermined", "分けられない", F1),
                    said("claim", "数える", E1),
                ),
            ),
            q03=(answer(2, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.round == 4
        assert found.reworded_in == 3

    def test_an_answer_above_in_the_same_round_did_not_change_it(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "上がった", F1)),
                answer(3, said("undetermined", "分けられない", F1)),
            ),
            q03=(answer(3, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.reworded_in is None

    def test_an_answer_above_that_says_the_same_later_did_not_change_it(
        self,
    ) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "上がった", F1)),
                answer(2, said("claim", "上がった", F1), said("claim", "数える", E1)),
            ),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.reworded_in is None

    def test_an_answer_above_that_first_cites_it_later_did_not_change_it(
        self,
    ) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "数える", E1)),
                answer(2, said("claim", "上がった", F1)),
            ),
            q03=(answer(1, said("claim", "0.30 上がる", F1)),),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.reworded_in is None

    def test_a_change_before_the_answer_of_the_node_is_not_after_it(self) -> None:
        tree = three_levels(
            root=(
                answer(1, said("claim", "上がった", F1)),
                answer(2, said("undetermined", "分けられない", F1)),
            ),
            q03=(
                answer(1, said("claim", "0.30", F1)),
                answer(3, said("claim", "0.30 上がる", F1)),
            ),
        )

        (found,) = cited_above(tree)["LIB-Q03"]

        assert found.reworded_in is None
