"""Unit tests for the question tree models (Epic 18, Story 18.1).

The models hold every invariant one tree file can decide on its own. Checks
that need another file (does the linked design exist, does the cited event
exist) belong to tree_io and tree_check.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.tree import Progress, QuestionTree
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
        data["nodes"][0]["question"] = "書き換えた根の問い"
        assert "current root revision" in errors_of(data)

    def test_an_unknown_field_is_rejected(self) -> None:
        data = tree_dict()
        data["nodes"][1]["status"] = "analyzed"
        assert "status" in errors_of(data)


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

    def test_a_theme_id_that_differs_from_the_file_name_is_an_error(self) -> None:
        errors = validate_tree(tree_dict(), expected_theme_id="FP")
        assert errors == ["theme_id: 'LIB' does not match the file name (FP_tree.yaml)"]
