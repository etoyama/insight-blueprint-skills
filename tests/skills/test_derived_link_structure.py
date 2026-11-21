"""Structure tests for linking a derived design to the question tree (#134).

The Branch Workflow of /analysis-journal creates the derived design, so it is the
step that links it. The link lives in SKILL.md prose: these tests guard that the
shown command runs against the real tree_io, and that the analyst is told the
outcome instead of being asked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills._shown import run_shown_line
from tests.skills.test_skill_structure import _read_skill


def _branch_workflow() -> str:
    return section(_read_skill("analysis-journal"), "### Step 4: ")


def _design(insight: Path, parent_id: str | None = None) -> str:
    return design_io.create_design(
        theme_id="LIB",
        title="Test",
        hypothesis_statement="X improves Y",
        hypothesis_background="because Z",
        methodology={"method": "OLS"},
        parent_id=parent_id,
        base_dir=insight,
    )["id"]


class TestBranchWorkflowLinksTheDerivedDesign:
    def test_the_shown_command_links_the_derived_design_to_its_parents_node(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        tree_io.create_tree(
            theme_id="LIB",
            question="取り置き期限を延ばす試行をするか",
            aim={
                "kind": "business",
                "decision_maker": "図書館員",
                "decision": "取り置き期限を延ばす試行を始めるか",
            },
            base_dir=insight,
        )
        node_id = tree_io.add_node(
            "LIB",
            question="期限切れを一貫して数えられるか",
            parent_question_id="LIB-Q01",
            contribution="予約取消が混ざると、延長で改善しうる件数が変わる",
            base_dir=insight,
        )["id"]
        parent = _design(insight)
        tree_io.link_design("LIB", node_id, parent, base_dir=insight)
        derived = _design(insight, parent_id=parent)

        code = run_shown_line(_branch_workflow(), "link-derived", insight, monkeypatch)

        assert code == 0
        nodes = {
            n["id"]: n for n in tree_io.load_tree("LIB", base_dir=insight)["nodes"]
        }
        assert nodes[node_id]["design_ids"] == [parent, derived]

    def test_the_link_comes_after_the_design_is_created(self) -> None:
        workflow = _branch_workflow()
        assert workflow.index("design_io create") < workflow.index(
            "tree_io link-derived"
        )

    def test_the_analyst_is_told_the_nodes_and_not_asked(self) -> None:
        workflow = unwrap(_branch_workflow())
        assert "`node_ids`" in workflow
        assert "Do not ask which node" in workflow

    def test_an_empty_result_is_not_an_error(self) -> None:
        workflow = unwrap(_branch_workflow())
        assert "empty `node_ids`" in workflow
        assert "/analysis-framing" in workflow

    def test_a_failed_link_does_not_create_the_design_again(self) -> None:
        workflow = unwrap(_branch_workflow())
        assert "non-zero" in workflow
        assert "do not create it again" in workflow

    def test_the_tree_is_written_only_through_this_command(self) -> None:
        workflow = unwrap(_branch_workflow())
        assert "Never run `tree_io link` or `tree_io add-node` here" in workflow

    def test_the_command_reference_lists_the_link(self) -> None:
        reference = section(_read_skill("analysis-journal"), "## tree_io Reference")
        row = table_row(reference, "`tree_io link-derived --theme T --design ID`")
        assert "Branch workflow" in row[1]
