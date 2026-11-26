"""Unit tests for the question tree models (Epic 18, Story 18.1).

The models hold every invariant one tree file can decide on its own. Checks
that need another file (does the linked design exist, does the cited event
exist) belong to tree_io and tree_check.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.tree import (
    NextCandidate,
    Progress,
    QuestionTree,
    StatementKind,
)
from insight_blueprint.validate import validate_tree

ROOT_QUESTION = "取り置き期限を延ばす試行をするか"


def tree_dict() -> dict:
    """The synthetic scenario (public library holds), right after framing."""
    return {
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
        "nodes": [
            {"id": "LIB-Q01", "question": ROOT_QUESTION},
            {
                "id": "LIB-Q02",
                "question": "期限切れを一貫して数えられるか",
                "parent_question_id": "LIB-Q01",
                "contribution": "予約取消が混ざると、延長で改善しうる件数が変わる",
            },
        ],
        "decisions": [
            {
                "round": 0,
                "kind": "start",
                "node_id": "LIB-Q02",
                "reason": "取消が混ざると延長で改善しうる件数が変わるため",
            }
        ],
    }


def errors_of(data: dict) -> str:
    with pytest.raises(ValidationError) as exc:
        QuestionTree.model_validate(data)
    return str(exc.value)


class TestQuestionTree:
    def test_the_synthetic_scenario_is_valid(self) -> None:
        tree = QuestionTree.model_validate(tree_dict())
        assert tree.root().id == "LIB-Q01"
        assert tree.current_revision().revision == 1

    def test_theme_id_must_be_an_upper_case_identifier(self) -> None:
        data = tree_dict()
        data["theme_id"] = "lib"
        assert "theme_id" in errors_of(data)

    def test_a_tree_without_a_root_revision_is_rejected(self) -> None:
        data = tree_dict()
        data["root_revisions"] = []
        assert "root_revisions" in errors_of(data)

    def test_a_tree_without_a_root_question_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"] = [data["nodes"][1]]
        assert "exactly one root question" in errors_of(data)

    def test_a_second_root_question_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"].append({"id": "LIB-Q03", "question": "別の根"})
        assert "exactly one root question" in errors_of(data)

    def test_a_parent_outside_the_tree_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["parent_question_id"] = "LIB-Q09"
        assert "LIB-Q09" in errors_of(data)

    def test_a_cycle_of_parents_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["parent_question_id"] = "LIB-Q03"
        data["nodes"].append(
            {
                "id": "LIB-Q03",
                "question": "循環する論点",
                "parent_question_id": "LIB-Q02",
                "contribution": "循環",
            }
        )
        assert "cycle" in errors_of(data)

    def test_a_duplicated_node_id_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"].append(copy.deepcopy(data["nodes"][1]))
        assert "duplicated" in errors_of(data)

    def test_a_node_id_of_another_theme_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["id"] = "FP-Q02"
        assert "LIB-Q{nn}" in errors_of(data)

    def test_root_revisions_must_count_up_from_one(self) -> None:
        data = tree_dict()
        second = copy.deepcopy(data["root_revisions"][0])
        second |= {"revision": 3, "reason": "到達点が変わった"}
        data["root_revisions"].append(second)
        assert "count up from 1" in errors_of(data)

    def test_the_root_question_must_match_the_current_revision(self) -> None:
        data = tree_dict()
        data["nodes"][0]["question"] = "書き換えた主題"
        assert "current root revision" in errors_of(data)

    def test_an_unknown_field_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["status"] = "analyzed"
        assert "status" in errors_of(data)


class TestTreeDecision:
    def test_a_tree_without_decisions_is_valid(self) -> None:
        data = tree_dict()
        del data["decisions"]
        assert QuestionTree.model_validate(data).decisions == []

    def test_a_start_decision_keeps_its_node_and_reason(self) -> None:
        decision = QuestionTree.model_validate(tree_dict()).decisions[0]
        assert decision.node_id == "LIB-Q02"
        assert decision.reason == "取消が混ざると延長で改善しうる件数が変わるため"

    def test_a_decision_on_a_node_outside_the_tree_is_rejected(self) -> None:
        data = tree_dict()
        data["decisions"][0]["node_id"] = "LIB-Q09"
        assert "LIB-Q09" in errors_of(data)

    def test_a_start_decision_belongs_to_round_zero(self) -> None:
        data = tree_dict()
        data["decisions"][0]["round"] = 1
        assert "round 0" in errors_of(data)

    def test_a_decision_needs_a_reason(self) -> None:
        data = tree_dict()
        data["decisions"][0]["reason"] = ""
        assert "reason" in errors_of(data)

    def test_a_kind_outside_the_four_is_rejected(self) -> None:
        data = tree_dict()
        data["decisions"][0]["kind"] = "abandon"
        assert "kind" in errors_of(data)

    def test_the_first_decision_must_be_a_start(self) -> None:
        data = tree_dict()
        data["decisions"][0]["kind"] = "close"
        assert "first decision must be a start" in errors_of(data)

    def test_an_unknown_field_of_a_decision_is_rejected(self) -> None:
        data = tree_dict()
        data["decisions"][0]["status"] = "done"
        assert "status" in errors_of(data)

    def test_a_second_start_decision_is_rejected(self) -> None:
        data = tree_dict()
        data["decisions"].append({**data["decisions"][0], "node_id": "LIB-Q01"})
        assert "at most one start" in errors_of(data)

    def test_a_tree_without_decisions_dumps_no_decisions_key(self) -> None:
        data = tree_dict()
        del data["decisions"]
        dumped = QuestionTree.model_validate(data).model_dump(exclude_defaults=True)
        assert "decisions" not in dumped


def branching_tree(*decisions: dict) -> dict:
    """Q01 root; Q02 and Q04 under it; Q03 under Q02; decided to start at Q02."""
    data = tree_dict()
    data["nodes"] += [
        {
            "id": "LIB-Q03",
            "question": "通知は期限の何日前に届くか",
            "parent_question_id": "LIB-Q02",
            "contribution": "通知の遅れが期限切れに混ざる",
        },
        {
            "id": "LIB-Q04",
            "question": "取り置き待ちの人数は何人か",
            "parent_question_id": "LIB-Q01",
            "contribution": "延長で待ち時間が伸びる人数が決まる",
        },
    ]
    data["nodes"][1]["answers"] = [
        {
            "round": 1,
            "root_revision": 1,
            "statements": [
                {"kind": "claim", "text": "取消を除く", "cites": ["LIB-H01-E01"]}
            ],
        }
    ]
    data["decisions"] += list(decisions)
    return data


def decision(kind: str, node_id: str, round: int = 1) -> dict:
    return {"round": round, "kind": kind, "node_id": node_id, "reason": "理由"}


class TestDecisionKinds:
    def test_deepen_stays_on_the_node_or_goes_below_it(self) -> None:
        tree = QuestionTree.model_validate(
            branching_tree(decision("deepen", "LIB-Q02"), decision("deepen", "LIB-Q03"))
        )
        assert tree.decisions[-1].node_id == "LIB-Q03"

    def test_deepen_to_a_node_outside_the_branch_is_rejected(self) -> None:
        data = branching_tree(decision("deepen", "LIB-Q04"))
        assert "deepen goes to LIB-Q02 or below" in errors_of(data)

    def test_return_goes_to_a_node_outside_the_current_branch(self) -> None:
        tree = QuestionTree.model_validate(
            branching_tree(decision("return", "LIB-Q04"))
        )
        assert tree.decisions[-1].node_id == "LIB-Q04"

    def test_return_to_the_same_node_or_below_it_is_rejected(self) -> None:
        for target in ("LIB-Q02", "LIB-Q03"):
            data = branching_tree(decision("return", target))
            assert "return leaves LIB-Q02" in errors_of(data)

    def test_return_to_the_parent_is_outside_the_branch(self) -> None:
        tree = QuestionTree.model_validate(
            branching_tree(decision("return", "LIB-Q01"))
        )
        assert tree.decisions[-1].node_id == "LIB-Q01"

    def test_close_stops_at_the_node_it_was_investigating(self) -> None:
        tree = QuestionTree.model_validate(branching_tree(decision("close", "LIB-Q02")))
        assert tree.decisions[-1].node_id == "LIB-Q02"

    def test_close_on_another_node_is_rejected(self) -> None:
        data = branching_tree(decision("close", "LIB-Q04"))
        assert "close stops at LIB-Q02" in errors_of(data)

    def test_a_decision_round_cannot_pass_the_last_reflection_round(self) -> None:
        data = branching_tree(decision("deepen", "LIB-Q02", round=2))
        assert "past the last reflection round 1" in errors_of(data)

    def test_decision_rounds_never_decrease(self) -> None:
        data = branching_tree(
            decision("deepen", "LIB-Q02", round=1),
            decision("deepen", "LIB-Q02", round=0),
        )
        assert "rounds must not decrease" in errors_of(data)


class TestUntouchedNodes:
    def test_a_node_with_no_design_below_it_is_a_next_candidate(self) -> None:
        data = branching_tree()
        data["nodes"][2]["design_ids"] = ["LIB-H01"]
        tree = QuestionTree.model_validate(data)
        assert [n.id for n in tree.untouched_nodes()] == ["LIB-Q04"]

    def test_a_node_whose_descendant_has_a_design_is_touched(self) -> None:
        data = branching_tree()
        data["nodes"][2]["design_ids"] = ["LIB-H01"]
        ids = [n.id for n in QuestionTree.model_validate(data).untouched_nodes()]
        assert "LIB-Q02" not in ids and "LIB-Q01" not in ids

    def test_the_root_is_never_a_candidate(self) -> None:
        tree = QuestionTree.model_validate(tree_dict())
        assert [n.id for n in tree.untouched_nodes()] == ["LIB-Q02"]

    def test_untouched_nodes_come_in_tree_order(self) -> None:
        tree = QuestionTree.model_validate(branching_tree())
        assert [n.id for n in tree.untouched_nodes()] == [
            "LIB-Q02",
            "LIB-Q03",
            "LIB-Q04",
        ]


class TestNextCandidate:
    ASK = "予約取消は、窓口でどれくらい起きますか"

    def test_an_ask_alone_is_a_valid_note(self) -> None:
        assert NextCandidate(ask=self.ASK).answer == ""

    def test_known_alone_is_a_valid_note(self) -> None:
        assert NextCandidate(known="カタログに取消フラグがある").ask == ""

    def test_a_note_with_nothing_in_it_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one of"):
            NextCandidate()

    def test_changes_if_needs_the_ask(self) -> None:
        with pytest.raises(ValidationError, match="changes_if needs the ask"):
            NextCandidate(known="x", changes_if="延長の可否")

    def test_an_answer_needs_who_and_when(self) -> None:
        with pytest.raises(ValidationError, match="set together"):
            NextCandidate(ask=self.ASK, answer="月に十数件")

    def test_who_and_when_without_an_answer_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="set together"):
            NextCandidate(ask=self.ASK, answered_by="窓口の職員")

    def test_an_answer_needs_the_ask_it_answers(self) -> None:
        with pytest.raises(ValidationError, match="answer needs the ask"):
            NextCandidate(
                known="x",
                answer="月に十数件",
                answered_by="窓口の職員",
                answered_at="2026-11-21",
            )

    def test_a_heard_answer_keeps_who_and_the_date(self) -> None:
        note = NextCandidate(
            ask=self.ASK,
            answer="月に十数件",
            answered_by="窓口の職員",
            answered_at="2026-11-21",
        )
        assert (note.answered_by, note.answered_at.isoformat()) == (
            "窓口の職員",
            "2026-11-21",
        )

    def test_a_node_keeps_its_note_through_a_dump_and_a_load(self) -> None:
        data = tree_dict()
        data["nodes"][1]["next_candidate"] = {
            "ask": self.ASK,
            "answer": "月に十数件",
            "answered_by": "窓口の職員",
            "answered_at": "2026-11-21",
        }
        tree = QuestionTree.model_validate(data)
        dumped = tree.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        assert QuestionTree.model_validate(dumped) == tree
        assert dumped["nodes"][1]["next_candidate"]["answered_at"] == "2026-11-21"


def statement(**overrides: object) -> dict:
    return {
        "kind": "claim",
        "text": "状態の履歴から取消を除き、期限を迎えた予約同士を比べられた",
        "cites": ["LIB-H01-E01"],
    } | overrides


def answer(**overrides: object) -> dict:
    return {"round": 1, "root_revision": 1, "statements": [statement()]} | overrides


def tree_with_answers(*answers: dict) -> dict:
    data = tree_dict()
    data["nodes"][1]["answers"] = list(answers)
    return data


class TestAnswer:
    def test_a_node_with_a_cited_answer_is_valid(self) -> None:
        tree = QuestionTree.model_validate(tree_with_answers(answer()))
        stated = tree.nodes[1].answers[0].statements[0]
        assert stated.kind is StatementKind.claim
        assert stated.cites == ["LIB-H01-E01"]

    def test_a_tree_without_answers_dumps_no_answers_key(self) -> None:
        dumped = QuestionTree.model_validate(tree_dict()).model_dump(
            exclude_defaults=True
        )
        assert "answers" not in dumped["nodes"][1]

    def test_the_shape_in_the_design_doc_is_valid(self) -> None:
        text = """
theme_id: LIB
root_revisions:
  - revision: 1
    question: 取り置き期限を延ばす試行をするか
    aim: {kind: business, decision_maker: 図書館員, decision: 取り置き期限を延ばす試行を始めるか}
nodes:
  - {id: LIB-Q01, question: 取り置き期限を延ばす試行をするか}
  - id: LIB-Q02
    question: 期限切れを一貫して数えられるか
    parent_question_id: LIB-Q01
    contribution: 予約取消が混ざると、延長で改善しうる件数が変わる
    design_ids: [LIB-H01]
    answers:
      - round: 1
        root_revision: 1
        statements:
          - {kind: claim, text: 状態の履歴から取消を除き、期限を迎えた予約同士を比べられた, cites: [LIB-H01-E01]}
decisions:
  - {round: 0, kind: start, node_id: LIB-Q02, reason: 取消が混ざると延長で改善しうる件数が変わるため}
"""
        assert validate_tree(YAML(typ="safe").load(text)) == []

    @pytest.mark.parametrize("kind", ["undetermined", "weakening"])
    def test_a_statement_can_say_it_is_undetermined_or_weakening(
        self, kind: str
    ) -> None:
        data = tree_with_answers(answer(statements=[statement(kind=kind)]))
        assert validate_tree(data) == []

    def test_a_statement_kind_outside_the_three_is_rejected(self) -> None:
        data = tree_with_answers(answer(statements=[statement(kind="guess")]))
        assert "kind" in errors_of(data)

    def test_a_statement_without_a_cite_is_rejected(self) -> None:
        data = tree_with_answers(answer(statements=[statement(cites=[])]))
        assert "cites" in errors_of(data)

    def test_a_cite_that_is_not_an_event_id_is_rejected(self) -> None:
        data = tree_with_answers(answer(statements=[statement(cites=["LIB-H01"])]))
        assert "LIB-H01" in errors_of(data)

    def test_a_cite_of_another_theme_is_rejected(self) -> None:
        data = tree_with_answers(answer(statements=[statement(cites=["FP-H01-E01"])]))
        assert "FP-H01-E01" in errors_of(data)

    def test_a_statement_needs_text(self) -> None:
        data = tree_with_answers(answer(statements=[statement(text="")]))
        assert "text" in errors_of(data)

    def test_an_answer_needs_a_statement(self) -> None:
        assert "statements" in errors_of(tree_with_answers(answer(statements=[])))

    @pytest.mark.parametrize("field", ["round", "root_revision"])
    def test_round_and_root_revision_start_at_one(self, field: str) -> None:
        assert field in errors_of(tree_with_answers(answer(**{field: 0})))

    def test_rounds_increase_within_a_node(self) -> None:
        data = tree_with_answers(answer(round=1), answer(round=2))
        assert validate_tree(data) == []

    def test_a_round_that_does_not_increase_is_rejected(self) -> None:
        data = tree_with_answers(answer(round=2), answer(round=2))
        assert "round" in errors_of(data)

    def test_an_answer_to_a_root_revision_that_does_not_exist_yet_is_rejected(
        self,
    ) -> None:
        data = tree_with_answers(answer(root_revision=2))
        assert "root_revision" in errors_of(data)

    def test_an_answer_to_an_earlier_root_revision_is_valid(self) -> None:
        data = tree_with_answers(answer(root_revision=1))
        second = copy.deepcopy(data["root_revisions"][0])
        second |= {"revision": 2, "question": "延長の対象を絞るか", "reason": "x"}
        data["root_revisions"].append(second)
        data["nodes"][0]["question"] = "延長の対象を絞るか"
        assert validate_tree(data) == []

    def test_an_unknown_field_of_an_answer_is_rejected(self) -> None:
        data = tree_with_answers(answer(confidence="high"))
        assert "confidence" in errors_of(data)


class TestCurrentRound:
    def test_it_is_0_while_no_node_has_an_answer(self) -> None:
        assert QuestionTree.model_validate(tree_dict()).current_round() == 0

    def test_it_is_the_highest_round_across_the_nodes(self) -> None:
        data = tree_with_answers(answer(round=1), answer(round=3))
        data["nodes"][0]["answers"] = [answer(round=2)]
        assert QuestionTree.model_validate(data).current_round() == 3


class TestRootRevision:
    def test_a_later_revision_needs_a_reason(self) -> None:
        data = tree_dict()
        second = copy.deepcopy(data["root_revisions"][0])
        second["revision"] = 2
        data["root_revisions"].append(second)
        assert "reason" in errors_of(data)

    def test_a_later_revision_with_a_reason_becomes_the_current_one(self) -> None:
        data = tree_dict()
        second = copy.deepcopy(data["root_revisions"][0])
        second |= {"revision": 2, "question": "延長の対象を絞るか", "reason": "x"}
        data["root_revisions"].append(second)
        data["nodes"][0]["question"] = "延長の対象を絞るか"
        assert QuestionTree.model_validate(data).current_revision().revision == 2


class TestAim:
    def test_a_business_aim_needs_who_decides_what(self) -> None:
        data = tree_dict()
        del data["root_revisions"][0]["aim"]["decision"]
        assert "decision_maker and decision" in errors_of(data)

    def test_a_research_aim_needs_the_audience_and_the_claim_scope(self) -> None:
        data = tree_dict()
        data["root_revisions"][0]["aim"] = {"kind": "research", "audience": "司書"}
        assert "audience and claim_scope" in errors_of(data)

    def test_a_research_aim_with_both_is_valid(self) -> None:
        data = tree_dict()
        data["root_revisions"][0]["aim"] = {
            "kind": "research",
            "audience": "図書館情報学の研究者",
            "claim_scope": "公共図書館1館の予約本",
        }
        QuestionTree.model_validate(data)


class TestQuestionNode:
    def test_a_child_needs_a_contribution(self) -> None:
        data = tree_dict()
        del data["nodes"][1]["contribution"]
        assert "contribution" in errors_of(data)

    def test_an_origin_must_look_like_a_journal_event_id(self) -> None:
        data = tree_dict()
        data["nodes"][1]["origin_event_id"] = "LIB-H02"
        assert "origin_event_id" in errors_of(data)

    def test_a_promoted_node_keeps_its_origin(self) -> None:
        data = tree_dict()
        data["nodes"][1]["origin_event_id"] = "LIB-H02-E03"
        tree = QuestionTree.model_validate(data)
        assert tree.nodes[1].origin_event_id == "LIB-H02-E03"

    def test_one_design_can_be_linked_to_several_nodes(self) -> None:
        data = tree_dict()
        data["nodes"][0]["design_ids"] = ["LIB-H01"]
        data["nodes"][1]["design_ids"] = ["LIB-H01"]
        QuestionTree.model_validate(data)

    @pytest.mark.parametrize("design_id", ["FP-H01", "../../etc/passwd", "LIB-Q01"])
    def test_a_linked_design_must_be_a_design_id_of_the_theme(
        self, design_id: str
    ) -> None:
        data = tree_dict()
        data["nodes"][1]["design_ids"] = [design_id]
        assert "LIB-H{nn}" in errors_of(data)

    def test_an_origin_in_another_theme_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["origin_event_id"] = "FP-H01-E01"
        assert "LIB-H{nn}-E{nn}" in errors_of(data)

    def test_the_same_design_twice_on_one_node_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["design_ids"] = ["LIB-H01", "LIB-H01"]
        assert "design_ids" in errors_of(data)


class TestProgress:
    """US-2 AC 1: progress is derived from the linked designs, never stored."""

    def test_no_design_means_not_started(self) -> None:
        assert Progress.of([]) is Progress.not_started

    @pytest.mark.parametrize(
        "status",
        [
            DesignStatus.in_review,
            DesignStatus.revision_requested,
            DesignStatus.analyzing,
        ],
    )
    def test_one_open_design_means_investigating(self, status: DesignStatus) -> None:
        assert Progress.of([DesignStatus.supported, status]) is Progress.investigating

    def test_only_terminal_designs_mean_analyzed(self) -> None:
        statuses = [
            DesignStatus.supported,
            DesignStatus.rejected,
            DesignStatus.inconclusive,
        ]
        assert Progress.of(statuses) is Progress.analyzed

    def test_progress_is_not_a_field_of_the_tree(self) -> None:
        data = tree_dict()
        data["nodes"][1]["progress"] = "analyzed"
        assert "progress" in errors_of(data)


class TestValidateTree:
    """validate.py is the one place the hook and tree_io ask about the shape."""

    def test_a_valid_tree_has_no_errors(self) -> None:
        assert validate_tree(tree_dict()) == []

    def test_errors_come_back_as_readable_lines(self) -> None:
        data = tree_dict()
        del data["nodes"][1]["contribution"]
        errors = validate_tree(data)
        assert len(errors) == 1
        assert "contribution" in errors[0]

    def _with_second_revision(self) -> dict:
        data = tree_dict()
        second = copy.deepcopy(data["root_revisions"][0])
        second |= {"revision": 2, "question": "延長の対象を絞るか", "reason": "x"}
        data["root_revisions"].append(second)
        data["nodes"][0]["question"] = "延長の対象を絞るか"
        return data

    def test_appending_a_root_revision_is_allowed(self) -> None:
        assert validate_tree(self._with_second_revision(), current=tree_dict()) == []

    def test_rewording_the_current_root_revision_is_allowed(self) -> None:
        new = self._with_second_revision()
        new["root_revisions"][1]["question"] = new["nodes"][0]["question"] = "絞るか"
        assert validate_tree(new, current=self._with_second_revision()) == []

    def test_dropping_a_root_revision_is_an_error(self) -> None:
        errors = validate_tree(tree_dict(), current=self._with_second_revision())
        assert errors == ["root_revisions: a root revision cannot be removed (2 -> 1)"]

    def test_rewriting_an_earlier_root_revision_is_an_error(self) -> None:
        new = self._with_second_revision()
        new["root_revisions"][0]["question"] = "書き換えた過去の問い"
        errors = validate_tree(new, current=self._with_second_revision())
        assert errors == ["root_revisions: revision 1 is history and cannot change"]

    def test_rewriting_the_current_revision_while_appending_is_an_error(self) -> None:
        new = self._with_second_revision()
        new["root_revisions"][0]["question"] = "書き換えた過去の問い"
        errors = validate_tree(new, current=tree_dict())
        assert errors == ["root_revisions: revision 1 is history and cannot change"]

    def _without_decisions(self) -> dict:
        data = tree_dict()
        del data["decisions"]
        return data

    def test_appending_a_decision_is_allowed(self) -> None:
        assert validate_tree(tree_dict(), current=self._without_decisions()) == []

    def test_dropping_every_decision_is_an_error(self) -> None:
        errors = validate_tree(self._without_decisions(), current=tree_dict())
        assert errors == ["decisions: a decision cannot be removed (1 -> 0)"]

    def test_rewriting_a_decision_is_an_error(self) -> None:
        new = tree_dict()
        new["decisions"][0]["reason"] = "後から書き換えた理由"
        errors = validate_tree(new, current=tree_dict())
        assert errors == ["decisions: decision 1 is history and cannot change"]

    def _answered(self, *rounds: int) -> dict:
        return tree_with_answers(*(answer(round=r) for r in rounds))

    def test_appending_an_answer_is_allowed(self) -> None:
        assert validate_tree(self._answered(1, 2), current=self._answered(1)) == []

    def test_adding_the_first_answer_to_a_node_is_allowed(self) -> None:
        assert validate_tree(self._answered(1), current=tree_dict()) == []

    def test_dropping_an_answer_is_an_error(self) -> None:
        errors = validate_tree(tree_dict(), current=self._answered(1))
        assert errors == ["LIB-Q02.answers: an answer cannot be removed (1 -> 0)"]

    def test_dropping_a_node_that_had_answers_is_an_error(self) -> None:
        new = self._without_decisions()
        del new["nodes"][1]
        on_disk = self._answered(1)
        del on_disk["decisions"]
        errors = validate_tree(new, current=on_disk)
        assert errors == ["LIB-Q02.answers: an answer cannot be removed (1 -> 0)"]

    def test_rewriting_an_answer_is_an_error(self) -> None:
        new = self._answered(1)
        new["nodes"][1]["answers"][0]["statements"][0]["text"] = "書き換えた"
        errors = validate_tree(new, current=self._answered(1))
        assert errors == [
            "LIB-Q02.answers: the answer of round 1 is history and cannot change"
        ]

    def test_rewriting_an_answer_while_appending_is_an_error(self) -> None:
        new = self._answered(1, 2)
        new["nodes"][1]["answers"][0]["statements"][0]["kind"] = "weakening"
        errors = validate_tree(new, current=self._answered(1))
        assert errors == [
            "LIB-Q02.answers: the answer of round 1 is history and cannot change"
        ]

    def test_a_rewritten_answer_is_named_by_its_round_not_its_position(self) -> None:
        new = self._answered(1, 3)
        new["nodes"][1]["answers"][1]["statements"][0]["text"] = "書き換えた"
        errors = validate_tree(new, current=self._answered(1, 3))
        assert errors == [
            "LIB-Q02.answers: the answer of round 3 is history and cannot change"
        ]

    def test_a_broken_file_on_disk_does_not_block_its_repair(self) -> None:
        assert validate_tree(tree_dict(), current={"theme_id": "LIB"}) == []

    def test_a_theme_id_that_differs_from_the_file_name_is_an_error(self) -> None:
        errors = validate_tree(tree_dict(), expected_theme_id="FP")
        assert errors == ["theme_id: 'LIB' does not match the file name (FP_tree.yaml)"]
