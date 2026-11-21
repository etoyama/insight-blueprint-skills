"""Unit tests for skills/_shared/tree_io.py (Epic 18, Story 18.1).

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``. Every
write goes through ``insight_blueprint.validate.validate_tree`` first.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared._atomic import atomic_write_yaml

ROOT_QUESTION = "取り置き期限を延ばす試行をするか"
AIM = {
    "kind": "business",
    "decision_maker": "図書館員",
    "decision": "取り置き期限を延ばす試行を始めるか",
}


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    return tmp_path / ".insight"


@pytest.fixture
def tree(insight: Path) -> Path:
    """A base dir that already holds the LIB tree with its root question."""
    tree_io.create_tree(
        theme_id="LIB", question=ROOT_QUESTION, aim=AIM, base_dir=insight
    )
    return insight


def _add(insight: Path, **over: object) -> dict:
    kwargs: dict = {
        "question": "期限切れを一貫して数えられるか",
        "parent_question_id": "LIB-Q01",
        "contribution": "予約取消が混ざると、延長で改善しうる件数が変わる",
        "base_dir": insight,
    }
    kwargs.update(over)
    return tree_io.add_node("LIB", **kwargs)


def _design(insight: Path, theme_id: str = "LIB", parent_id: str | None = None) -> str:
    design = design_io.create_design(
        theme_id=theme_id,
        title="Test",
        hypothesis_statement="X improves Y",
        hypothesis_background="because Z",
        methodology={"method": "OLS"},
        parent_id=parent_id,
        base_dir=insight,
    )
    return design["id"]


def _finish(insight: Path, design_id: str) -> None:
    design_io.transition_status(design_id, "supported", base_dir=insight)


class TestCreateTree:
    def test_writes_the_root_question_and_the_first_root_revision(
        self, insight: Path
    ) -> None:
        created = tree_io.create_tree(
            theme_id="LIB", question=ROOT_QUESTION, aim=AIM, base_dir=insight
        )

        assert (insight / "themes" / "LIB_tree.yaml").exists()
        assert tree_io.load_tree("LIB", base_dir=insight) == created
        assert created["nodes"] == [{"id": "LIB-Q01", "question": ROOT_QUESTION}]
        revision = created["root_revisions"][0]
        assert (revision["revision"], revision["question"]) == (1, ROOT_QUESTION)
        assert revision["aim"] == AIM
        assert revision["created_at"]

    def test_a_theme_has_only_one_tree(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="already exists"):
            tree_io.create_tree(
                theme_id="LIB", question="別の問い", aim=AIM, base_dir=tree
            )

    def test_an_invalid_tree_is_not_written(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="decision_maker and decision"):
            tree_io.create_tree(
                theme_id="LIB",
                question=ROOT_QUESTION,
                aim={"kind": "business"},
                base_dir=insight,
            )
        assert not (insight / "themes" / "LIB_tree.yaml").exists()

    @pytest.mark.parametrize("theme_id", ["../evil", "lib", "", "A/B"])
    def test_a_theme_id_that_could_leave_the_directory_is_rejected(
        self, insight: Path, theme_id: str
    ) -> None:
        with pytest.raises(ValueError, match="theme_id"):
            tree_io.create_tree(
                theme_id=theme_id, question=ROOT_QUESTION, aim=AIM, base_dir=insight
            )

    def test_a_missing_tree_loads_as_empty(self, insight: Path) -> None:
        assert tree_io.load_tree("LIB", base_dir=insight) == {}


class TestAddNode:
    def test_adds_a_child_with_the_next_id(self, tree: Path) -> None:
        first = _add(tree)
        second = _add(tree, question="通知は期限の何日前に届くか")

        assert (first["id"], second["id"]) == ("LIB-Q02", "LIB-Q03")
        assert first["parent_question_id"] == "LIB-Q01"
        assert "origin_event_id" not in first
        stored = tree_io.load_tree("LIB", base_dir=tree)["nodes"]
        assert [n["id"] for n in stored] == ["LIB-Q01", "LIB-Q02", "LIB-Q03"]

    def test_a_second_root_question_cannot_be_added(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="exactly one root question"):
            _add(tree, parent_question_id=None)

    def test_a_child_without_a_contribution_is_not_written(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="contribution"):
            _add(tree, contribution="")
        assert len(tree_io.load_tree("LIB", base_dir=tree)["nodes"]) == 1

    def test_a_file_that_names_another_theme_is_not_written_elsewhere(
        self, tree: Path
    ) -> None:
        path = tree / "themes" / "LIB_tree.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("LIB", "FP"), encoding="utf-8")

        with pytest.raises(ValueError, match="does not match the file name"):
            tree_io.add_node(
                "LIB",
                question="q",
                parent_question_id="FP-Q01",
                contribution="c",
                base_dir=tree,
            )
        assert not (tree / "themes" / "FP_tree.yaml").exists()

    def test_a_tree_must_exist_first(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="no question tree"):
            _add(insight)


class TestPromoteJournalQuestion:
    """US-2 AC 2: a journal ``question`` becomes a node that keeps its origin."""

    def _journal(self, insight: Path, design_id: str) -> None:
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {"id": f"{design_id}-E01", "type": "observe", "content": "o"},
                    {"id": f"{design_id}-E02", "type": "question", "content": "q"},
                ]
            },
            base_dir=insight,
        )

    def test_the_promoted_node_keeps_the_event_id(self, tree: Path) -> None:
        design_id = _design(tree)
        self._journal(tree, design_id)

        node = _add(tree, origin_event_id=f"{design_id}-E02")

        assert node["origin_event_id"] == "LIB-H01-E02"

    def test_an_event_that_is_not_a_question_cannot_be_promoted(
        self, tree: Path
    ) -> None:
        design_id = _design(tree)
        self._journal(tree, design_id)

        with pytest.raises(ValueError, match="not a question"):
            _add(tree, origin_event_id=f"{design_id}-E01")

    def test_an_event_that_does_not_exist_cannot_be_promoted(self, tree: Path) -> None:
        design_id = _design(tree)
        self._journal(tree, design_id)

        with pytest.raises(ValueError, match="not found"):
            _add(tree, origin_event_id=f"{design_id}-E09")


class TestLinkDesign:
    def test_links_a_design_to_a_node(self, tree: Path) -> None:
        node_id = _add(tree)["id"]
        design_id = _design(tree)

        node = tree_io.link_design("LIB", node_id, design_id, base_dir=tree)

        assert node["design_ids"] == [design_id]

    def test_linking_twice_keeps_one_link(self, tree: Path) -> None:
        node_id = _add(tree)["id"]
        design_id = _design(tree)

        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        node = tree_io.link_design("LIB", node_id, design_id, base_dir=tree)

        assert node["design_ids"] == [design_id]

    def test_one_design_can_be_linked_to_several_nodes(self, tree: Path) -> None:
        """US-2 AC 3."""
        first = _add(tree)["id"]
        second = _add(tree, question="通知は期限の何日前に届くか")["id"]
        design_id = _design(tree)

        tree_io.link_design("LIB", first, design_id, base_dir=tree)
        tree_io.link_design("LIB", second, design_id, base_dir=tree)

        nodes = {n["id"]: n for n in tree_io.load_tree("LIB", base_dir=tree)["nodes"]}
        assert nodes[first]["design_ids"] == nodes[second]["design_ids"] == [design_id]

    def test_a_design_that_does_not_exist_cannot_be_linked(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="design 'LIB-H09' not found"):
            tree_io.link_design("LIB", "LIB-Q01", "LIB-H09", base_dir=tree)

    def test_a_design_of_another_theme_cannot_be_linked(self, tree: Path) -> None:
        other = _design(tree, theme_id="FP")
        with pytest.raises(ValueError, match="belongs to theme 'FP'"):
            tree_io.link_design("LIB", "LIB-Q01", other, base_dir=tree)

    def test_a_node_that_does_not_exist_cannot_be_linked(self, tree: Path) -> None:
        design_id = _design(tree)
        with pytest.raises(ValueError, match="node 'LIB-Q09' not found"):
            tree_io.link_design("LIB", "LIB-Q09", design_id, base_dir=tree)


def _derived(insight: Path, parent_id: str) -> str:
    return _design(insight, parent_id=parent_id)


def _linked(insight: Path) -> dict[str, list[str]]:
    nodes = tree_io.load_tree("LIB", base_dir=insight)["nodes"]
    return {n["id"]: n.get("design_ids") or [] for n in nodes}


class TestLinkDerivedDesign:
    """#134: a derived design answers the questions its parent answers."""

    def test_links_the_derived_design_to_the_node_of_its_parent(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        derived = _derived(tree, parent)

        result = tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert result == {
            "design_id": derived,
            "parent_id": parent,
            "node_ids": [node_id],
        }
        assert _linked(tree)[node_id] == [parent, derived]

    def test_links_it_to_every_node_of_its_parent(self, tree: Path) -> None:
        first = _add(tree)["id"]
        second = _add(tree, question="通知は期限の何日前に届くか")["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", first, parent, base_dir=tree)
        tree_io.link_design("LIB", second, parent, base_dir=tree)
        derived = _derived(tree, parent)

        result = tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert result["node_ids"] == [first, second]
        linked = _linked(tree)
        assert linked[first] == linked[second] == [parent, derived]

    def test_a_node_without_the_parent_is_left_alone(self, tree: Path) -> None:
        with_parent = _add(tree)["id"]
        other = _add(tree, question="通知は期限の何日前に届くか")["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", with_parent, parent, base_dir=tree)
        tree_io.link_design("LIB", other, _design(tree), base_dir=tree)
        derived = _derived(tree, parent)

        tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert derived not in _linked(tree)[other]

    def test_linking_twice_keeps_one_link(self, tree: Path) -> None:
        node_id = _add(tree)["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        derived = _derived(tree, parent)

        tree_io.link_derived_design("LIB", derived, base_dir=tree)
        result = tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert result["node_ids"] == [node_id]
        assert _linked(tree)[node_id] == [parent, derived]

    def test_a_parent_on_no_node_links_nothing(self, tree: Path) -> None:
        _add(tree)
        derived = _derived(tree, _design(tree))
        before = tree_io.load_tree("LIB", base_dir=tree)

        result = tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert result["node_ids"] == []
        assert tree_io.load_tree("LIB", base_dir=tree) == before

    def test_a_theme_without_a_tree_links_nothing(self, insight: Path) -> None:
        derived = _derived(insight, _design(insight))

        result = tree_io.link_derived_design("LIB", derived, base_dir=insight)

        assert result["node_ids"] == []
        assert tree_io.load_tree("LIB", base_dir=insight) == {}

    def test_a_design_without_a_parent_is_refused(self, tree: Path) -> None:
        design_id = _design(tree)
        with pytest.raises(ValueError, match=f"design '{design_id}' has no parent_id"):
            tree_io.link_derived_design("LIB", design_id, base_dir=tree)

    def test_a_design_that_does_not_exist_is_refused(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="design 'LIB-H09' not found"):
            tree_io.link_derived_design("LIB", "LIB-H09", base_dir=tree)

    def test_a_design_of_another_theme_is_refused(self, tree: Path) -> None:
        parent = _design(tree, theme_id="FP")
        other = _design(tree, theme_id="FP", parent_id=parent)
        with pytest.raises(ValueError, match="belongs to theme 'FP'"):
            tree_io.link_derived_design("LIB", other, base_dir=tree)

    def test_a_tree_named_for_another_theme_is_refused_with_nothing_to_write(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        derived = _derived(tree, parent)
        tree_io.link_derived_design("LIB", derived, base_dir=tree)
        path = tree / "themes" / "LIB_tree.yaml"
        path.write_text(
            path.read_text("utf-8").replace("theme_id: LIB", "theme_id: FP"), "utf-8"
        )

        with pytest.raises(ValueError, match="FP"):
            tree_io.link_derived_design("LIB", derived, base_dir=tree)

    def test_the_cli_exits_1_without_a_traceback_on_a_tree_written_by_hand(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        derived = _derived(tree, parent)
        path = tree / "themes" / "LIB_tree.yaml"
        text = path.read_text("utf-8")
        assert f"design_ids:\n  - {parent}" in text
        path.write_text(
            text.replace(f"design_ids:\n  - {parent}", f"design_ids: {parent}"),
            "utf-8",
        )

        done = _run_cli(tree, "link-derived", "--theme", "LIB", "--design", derived)

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr

    def test_the_derived_design_shows_in_the_progress_and_the_position(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        tree_io.decide(
            "LIB", kind="start", node_id=node_id, reason="first", base_dir=tree
        )
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        _finish(tree, parent)
        derived = _derived(tree, parent)
        assert tree_io.progress("LIB", base_dir=tree)[node_id] == "analyzed"

        tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert tree_io.progress("LIB", base_dir=tree)[node_id] == "investigating"
        where = tree_io.position("LIB", base_dir=tree)
        assert (where["state"], where["design_ids"]) == ("in_progress", [derived])

    def test_the_cli_prints_the_nodes_it_linked(self, tree: Path) -> None:
        node_id = _add(tree)["id"]
        parent = _design(tree)
        tree_io.link_design("LIB", node_id, parent, base_dir=tree)
        derived = _derived(tree, parent)

        done = _run_cli(tree, "link-derived", "--theme", "LIB", "--design", derived)

        assert done.returncode == 0, done.stderr
        assert json.loads(done.stdout)["node_ids"] == [node_id]

    def test_the_cli_exits_1_with_a_message_without_a_design(self, tree: Path) -> None:
        done = _run_cli(tree, "link-derived", "--theme", "LIB")

        assert done.returncode == 1
        assert done.stderr.strip() == "tree_io: --design is required for link-derived"


class TestReviseRoot:
    """US-1 AC 5: the root changes only here, and a bump keeps the version and reason."""

    def test_a_bump_appends_a_revision_with_its_reason(self, tree: Path) -> None:
        revised = tree_io.revise_root(
            "LIB",
            question="延長の対象を新着本に絞るか",
            bump=True,
            reason="全館での試行は予算が付かなかった",
            base_dir=tree,
        )

        first, second = revised["root_revisions"]
        assert first["question"] == ROOT_QUESTION
        assert (second["revision"], second["question"], second["reason"]) == (
            2,
            "延長の対象を新着本に絞るか",
            "全館での試行は予算が付かなかった",
        )
        assert second["aim"] == AIM
        assert revised["nodes"][0]["question"] == "延長の対象を新着本に絞るか"

    def test_a_bump_without_a_reason_is_not_written(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="reason"):
            tree_io.revise_root("LIB", question="別の問い", bump=True, base_dir=tree)
        stored = tree_io.load_tree("LIB", base_dir=tree)
        assert len(stored["root_revisions"]) == 1
        assert stored["nodes"][0]["question"] == ROOT_QUESTION

    def test_a_rewording_without_a_bump_keeps_the_revision_number(
        self, tree: Path
    ) -> None:
        revised = tree_io.revise_root(
            "LIB", question="取り置き期限の延長を試すか", bump=False, base_dir=tree
        )

        assert [r["revision"] for r in revised["root_revisions"]] == [1]
        assert revised["root_revisions"][0]["question"] == "取り置き期限の延長を試すか"
        assert revised["nodes"][0]["question"] == "取り置き期限の延長を試すか"

    def test_the_aim_alone_can_change(self, tree: Path) -> None:
        aim = {**AIM, "decision_maker": "館長"}

        revised = tree_io.revise_root(
            "LIB", aim=aim, bump=True, reason="決める人が替わった", base_dir=tree
        )

        assert revised["root_revisions"][1]["aim"] == aim
        assert revised["root_revisions"][1]["question"] == ROOT_QUESTION

    def test_a_bump_must_be_a_boolean(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="bump must be true or false"):
            tree_io.revise_root(
                "LIB", question="別の問い", bump="false", reason="x", base_dir=tree
            )

    def test_a_reason_without_a_bump_is_rejected(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="only with a bump"):
            tree_io.revise_root(
                "LIB", question="別の問い", bump=False, reason="x", base_dir=tree
            )

    def test_a_revision_needs_a_new_question_or_aim(self, tree: Path) -> None:
        with pytest.raises(ValueError, match="question or aim"):
            tree_io.revise_root("LIB", bump=True, reason="x", base_dir=tree)


class TestDecide:
    REASON = "取消が混ざると延長で改善しうる件数が変わるため"

    def _decide(self, insight: Path, **over: object) -> dict:
        kwargs: dict = {
            "kind": "start",
            "node_id": "LIB-Q02",
            "reason": self.REASON,
            "base_dir": insight,
        }
        kwargs.update(over)
        return tree_io.decide("LIB", **kwargs)

    @pytest.fixture
    def two_nodes(self, tree: Path) -> Path:
        _add(tree)
        return tree

    def test_records_the_first_question_and_why(self, two_nodes: Path) -> None:
        decision = self._decide(two_nodes)
        assert decision["kind"] == "start"
        assert decision["node_id"] == "LIB-Q02"
        assert decision["reason"] == self.REASON
        assert decision["round"] == 0
        assert decision["created_at"]
        assert tree_io.load_tree("LIB", two_nodes)["decisions"] == [decision]

    def test_a_second_start_decision_is_not_written(self, two_nodes: Path) -> None:
        first = self._decide(two_nodes)
        with pytest.raises(ValueError, match="at most one start"):
            self._decide(two_nodes, node_id="LIB-Q01", reason="根から見直す")
        assert tree_io.load_tree("LIB", two_nodes)["decisions"] == [first]

    def test_a_node_that_does_not_exist_is_not_written(self, two_nodes: Path) -> None:
        with pytest.raises(ValueError, match="LIB-Q09"):
            self._decide(two_nodes, node_id="LIB-Q09")
        assert "decisions" not in tree_io.load_tree("LIB", two_nodes)

    def test_an_empty_reason_is_not_written(self, two_nodes: Path) -> None:
        with pytest.raises(ValueError, match="reason"):
            self._decide(two_nodes, reason="")
        assert "decisions" not in tree_io.load_tree("LIB", two_nodes)

    def test_a_first_decision_other_than_start_is_not_written(
        self, two_nodes: Path
    ) -> None:
        with pytest.raises(ValueError, match="must be a start"):
            self._decide(two_nodes, kind="close")
        assert "decisions" not in tree_io.load_tree("LIB", two_nodes)

    def test_a_tree_must_exist_first(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="has no question tree"):
            self._decide(insight)


class TestProgress:
    """US-2 AC 1: progress comes from the linked designs and is never stored."""

    def test_follows_the_linked_designs(self, tree: Path) -> None:
        untouched = _add(tree)["id"]
        open_node = _add(tree, question="通知は期限の何日前に届くか")["id"]
        done_node = _add(tree, question="期限切れは曜日で偏るか")["id"]
        open_design, done_design = _design(tree), _design(tree)
        _finish(tree, done_design)
        tree_io.link_design("LIB", open_node, open_design, base_dir=tree)
        tree_io.link_design("LIB", open_node, done_design, base_dir=tree)
        tree_io.link_design("LIB", done_node, done_design, base_dir=tree)

        assert tree_io.progress("LIB", base_dir=tree) == {
            "LIB-Q01": "not_started",
            untouched: "not_started",
            open_node: "investigating",
            done_node: "analyzed",
        }

    def test_changes_when_the_design_reaches_a_terminal_status(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        design_id = _design(tree)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        before = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")

        _finish(tree, design_id)

        assert tree_io.progress("LIB", base_dir=tree)[node_id] == "analyzed"
        after = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")
        assert after == before

    def test_a_linked_design_that_disappeared_is_an_error(self, tree: Path) -> None:
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q01", design_id, base_dir=tree)
        (tree / "designs" / f"{design_id}_hypothesis.yaml").unlink()

        with pytest.raises(ValueError, match=f"design '{design_id}' not found"):
            tree_io.progress("LIB", base_dir=tree)


def _run_cli(insight: Path, *args: str, payload: dict | None = None):
    return subprocess.run(
        [sys.executable, "-m", "skills._shared.tree_io", *args]
        + ["--base-dir", str(insight)],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
    )


def _rendered(insight: Path) -> str:
    return Path(tree_io.render("LIB", base_dir=insight)["path"]).read_text("utf-8")


class TestPosition:
    """US-8 AC 1: where a run resumes comes from the last decision and its designs."""

    @pytest.fixture
    def started(self, tree: Path) -> Path:
        """LIB-Q02 under the root, named by the start decision."""
        _add(tree)
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初に", base_dir=tree
        )
        return tree

    @staticmethod
    def _designed(base: Path, node_id: str = "LIB-Q02") -> str:
        design_id = _design(base)
        tree_io.link_design("LIB", node_id, design_id, base_dir=base)
        return design_id

    def test_a_theme_without_a_tree_has_no_tree(self, insight: Path) -> None:
        assert tree_io.position("LIB", base_dir=insight) == {"state": "no_tree"}

    def test_a_tree_without_a_decision_has_no_decision(self, tree: Path) -> None:
        assert tree_io.position("LIB", base_dir=tree) == {"state": "no_decision"}

    def test_a_decided_node_without_a_design_is_not_started(
        self, started: Path
    ) -> None:
        position = tree_io.position("LIB", base_dir=started)

        assert position["state"] == "not_started"
        assert position["node_id"] == "LIB-Q02"
        assert position["design_ids"] == []
        assert position["decision"]["kind"] == "start"

    def test_an_unfinished_design_on_the_node_is_in_progress(
        self, started: Path
    ) -> None:
        design_id = self._designed(started)

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == (
            "in_progress",
            [design_id],
        )

    def test_a_design_made_and_finished_after_the_decision_is_concluded(
        self, started: Path
    ) -> None:
        design_id = self._designed(started)
        _finish(started, design_id)

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == ("concluded", [design_id])

    def test_deciding_to_deepen_the_same_node_makes_it_not_started_again(
        self, started: Path
    ) -> None:
        _finish(started, self._designed(started))
        tree_io.decide(
            "LIB", kind="deepen", node_id="LIB-Q02", reason="もう一本", base_dir=started
        )

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == ("not_started", [])

    def test_an_unfinished_design_older_than_the_decision_is_still_in_progress(
        self, started: Path
    ) -> None:
        design_id = self._designed(started)
        tree_io.decide(
            "LIB",
            kind="deepen",
            node_id="LIB-Q02",
            reason="仮説を直す",
            base_dir=started,
        )

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == (
            "in_progress",
            [design_id],
        )

    def test_in_progress_names_only_the_unfinished_designs(self, started: Path) -> None:
        _finish(started, self._designed(started))
        unfinished = self._designed(started)

        assert tree_io.position("LIB", base_dir=started)["design_ids"] == [unfinished]

    def test_a_design_on_another_node_does_not_count(self, started: Path) -> None:
        _add(started, question="別の論点")
        self._designed(started, "LIB-Q03")

        assert tree_io.position("LIB", base_dir=started)["state"] == "not_started"

    def test_a_close_is_closed_at_its_node(self, started: Path) -> None:
        _finish(started, self._designed(started))
        tree_io.decide(
            "LIB", kind="close", node_id="LIB-Q02", reason="ここまで", base_dir=started
        )

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["node_id"]) == ("closed", "LIB-Q02")

    def _closed(self, base: Path) -> None:
        tree_io.decide(
            "LIB", kind="close", node_id="LIB-Q02", reason="ここまで", base_dir=base
        )

    def test_a_design_made_after_the_close_resumes_the_node(
        self, started: Path
    ) -> None:
        _finish(started, self._designed(started))
        self._closed(started)
        resumed = self._designed(started)

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == ("in_progress", [resumed])

    def test_a_design_made_and_finished_after_the_close_is_concluded(
        self, started: Path
    ) -> None:
        self._closed(started)
        resumed = self._designed(started)
        _finish(started, resumed)

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == ("concluded", [resumed])

    def test_an_unfinished_design_left_behind_by_the_close_stays_closed(
        self, started: Path
    ) -> None:
        self._designed(started)
        self._closed(started)

        assert tree_io.position("LIB", base_dir=started)["state"] == "closed"

    @pytest.mark.parametrize("created_at", ["2026-11-21T10:00:00", "not a time", None])
    def test_a_design_whose_time_cannot_be_compared_is_an_error(
        self, started: Path, created_at: str | None
    ) -> None:
        design_id = self._designed(started)
        _finish(started, design_id)
        path = started / "designs" / f"{design_id}_hypothesis.yaml"
        saved = design_io.read_yaml(path)
        saved["created_at"] = created_at
        atomic_write_yaml(path, saved)

        with pytest.raises(ValueError, match=f"{design_id}.*created_at"):
            tree_io.position("LIB", base_dir=started)

    def test_the_states_are_the_ones_the_driver_enters_by(self) -> None:
        assert {state.value for state in tree_io.WalkState} == {
            "no_tree",
            "no_decision",
            "not_started",
            "in_progress",
            "concluded",
            "closed",
        }

    def test_a_decision_without_a_time_counts_every_finished_design_as_later(
        self, started: Path
    ) -> None:
        design_id = self._designed(started)
        _finish(started, design_id)
        saved = tree_io.load_tree("LIB", started)
        del saved["decisions"][0]["created_at"]
        atomic_write_yaml(started / "themes" / "LIB_tree.yaml", saved)

        position = tree_io.position("LIB", base_dir=started)
        assert (position["state"], position["design_ids"]) == ("concluded", [design_id])

    def test_it_writes_nothing(self, started: Path) -> None:
        self._designed(started)
        path = started / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        tree_io.position("LIB", base_dir=started)
        assert path.read_bytes() == before

    def test_the_cli_prints_the_position(
        self, started: Path, capsys: pytest.CaptureFixture
    ) -> None:
        code = tree_io._main(["position", "--theme", "LIB", "--base-dir", str(started)])

        assert code == 0
        assert json.loads(capsys.readouterr().out)["state"] == "not_started"

    def test_the_cli_says_where_it_looked_when_there_is_no_tree(
        self, insight: Path, capsys: pytest.CaptureFixture
    ) -> None:
        code = tree_io._main(["position", "--theme", "LIB", "--base-dir", str(insight)])

        captured = capsys.readouterr()
        assert code == 0
        assert json.loads(captured.out) == {"state": "no_tree"}
        assert str((insight / "themes" / "LIB_tree.yaml").resolve()) in captured.err


@pytest.fixture
def world(tree: Path) -> Path:
    """LIB-Q02 and LIB-Q03 under the root, each with a design and a journal."""
    for node_id in ("LIB-Q02", "LIB-Q03"):
        _add(tree, question=f"{node_id} の問い")
        design_id = _design(tree)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        design_io.write_journal(
            design_id,
            {
                "events": [
                    {
                        "id": f"{design_id}-E01",
                        "type": "observe",
                        "content": f"{design_id} は期限切れ152件、取消除外後34.6%",
                    }
                ]
            },
            base_dir=tree,
        )
    return tree


def _entry(node_id: str, text: str, cite: str = "LIB-H01-E01") -> dict:
    return {
        "node_id": node_id,
        "statements": [{"kind": "claim", "text": text, "cites": [cite]}],
    }


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
            }
        ]

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


class TestNextCandidates:
    ASK = "予約取消は、窓口でどれくらい起きますか"

    def _note(self, base: Path, node_id: str = "LIB-Q03", **over: str) -> dict:
        kwargs = {"ask": self.ASK, "changes_if": "取消が多ければ延長を見送る"} | over
        return tree_io.candidate("LIB", node_id, base_dir=base, **kwargs)

    def test_a_node_with_no_design_is_listed_with_its_question(
        self, world: Path
    ) -> None:
        _add(world, question="通知は期限の何日前に届くか")
        listed = tree_io.candidates("LIB", base_dir=world)
        assert [c["id"] for c in listed] == ["LIB-Q04"]
        assert listed[0]["question"] == "通知は期限の何日前に届くか"
        assert "next_candidate" not in listed[0]

    def test_a_node_with_a_linked_design_is_not_listed(self, world: Path) -> None:
        assert tree_io.candidates("LIB", base_dir=world) == []

    def test_notes_are_listed_with_the_node(self, world: Path) -> None:
        _add(world, question="通知は期限の何日前に届くか")
        self._note(world, "LIB-Q04")
        listed = tree_io.candidates("LIB", base_dir=world)
        assert listed[0]["next_candidate"] == {
            "ask": self.ASK,
            "changes_if": "取消が多ければ延長を見送る",
        }

    def test_the_notes_of_a_node_are_stored_on_it(self, world: Path) -> None:
        node = self._note(world, known="カタログに取消フラグがある")
        assert node["next_candidate"]["known"] == "カタログに取消フラグがある"
        stored = tree_io.load_tree("LIB", world)["nodes"][2]
        assert stored["next_candidate"] == node["next_candidate"]

    def test_noting_again_replaces_the_notes(self, world: Path) -> None:
        self._note(world)
        node = self._note(world, changes_if="")
        assert "changes_if" not in node["next_candidate"]

    def test_notes_with_nothing_in_them_are_not_written(self, world: Path) -> None:
        with pytest.raises(ValueError, match="at least one of"):
            self._note(world, ask="", changes_if="")
        assert "next_candidate" not in tree_io.load_tree("LIB", world)["nodes"][2]

    def test_a_node_outside_the_tree_is_refused(self, world: Path) -> None:
        with pytest.raises(ValueError, match="LIB-Q09"):
            self._note(world, "LIB-Q09")


class TestHear:
    ASK = "予約取消は、窓口でどれくらい起きますか"
    HEARD = {
        "answer": "月に十数件で、ほとんどが電話での取消",
        "answered_by": "窓口の職員",
        "answered_at": "2026-11-21",
    }

    @pytest.fixture
    def asked(self, world: Path) -> Path:
        tree_io.candidate(
            "LIB", "LIB-Q03", ask=self.ASK, changes_if="件数次第", base_dir=world
        )
        return world

    def test_the_answer_is_kept_with_who_and_when(self, asked: Path) -> None:
        node = tree_io.hear("LIB", "LIB-Q03", base_dir=asked, **self.HEARD)
        assert node["next_candidate"] | {} == {
            "ask": self.ASK,
            "changes_if": "件数次第",
            **self.HEARD,
        }
        stored = tree_io.load_tree("LIB", asked)["nodes"][2]["next_candidate"]
        assert str(stored["answered_at"]) == "2026-11-21"

    def test_a_listed_candidate_shows_the_answer_heard(self, asked: Path) -> None:
        _add(asked, question="通知は期限の何日前に届くか")
        tree_io.candidate("LIB", "LIB-Q04", ask="通知の担当は", base_dir=asked)
        tree_io.hear("LIB", "LIB-Q04", base_dir=asked, **self.HEARD)
        heard = tree_io.candidates("LIB", base_dir=asked)[0]["next_candidate"]
        assert heard["answered_by"] == "窓口の職員"

    def test_hearing_again_replaces_the_answer(self, asked: Path) -> None:
        tree_io.hear("LIB", "LIB-Q03", base_dir=asked, **self.HEARD)
        node = tree_io.hear(
            "LIB", "LIB-Q03", base_dir=asked, **self.HEARD | {"answer": "月に数件"}
        )
        assert node["next_candidate"]["answer"] == "月に数件"

    def test_a_node_without_an_ask_cannot_be_answered(self, world: Path) -> None:
        with pytest.raises(ValueError, match="no ask to answer"):
            tree_io.hear("LIB", "LIB-Q03", base_dir=world, **self.HEARD)

    def test_an_answer_without_who_is_not_written(self, asked: Path) -> None:
        with pytest.raises(ValueError, match="set together"):
            tree_io.hear(
                "LIB", "LIB-Q03", base_dir=asked, **self.HEARD | {"answered_by": ""}
            )
        note = tree_io.load_tree("LIB", asked)["nodes"][2]["next_candidate"]
        assert "answer" not in note

    def test_a_date_that_is_not_a_date_is_not_written(self, asked: Path) -> None:
        with pytest.raises(ValueError, match="answered_at"):
            tree_io.hear(
                "LIB", "LIB-Q03", base_dir=asked, **self.HEARD | {"answered_at": "昨日"}
            )

    def test_the_ask_cannot_change_once_it_is_answered(self, asked: Path) -> None:
        tree_io.hear("LIB", "LIB-Q03", base_dir=asked, **self.HEARD)
        with pytest.raises(ValueError, match="the ask cannot change"):
            tree_io.candidate("LIB", "LIB-Q03", ask="別の問い", base_dir=asked)

    def test_the_other_notes_can_change_after_the_answer_and_keep_it(
        self, asked: Path
    ) -> None:
        tree_io.hear("LIB", "LIB-Q03", base_dir=asked, **self.HEARD)
        node = tree_io.candidate(
            "LIB", "LIB-Q03", ask=self.ASK, known="追記", base_dir=asked
        )
        assert node["next_candidate"]["answer"] == self.HEARD["answer"]
        assert node["next_candidate"]["known"] == "追記"


class TestCopyHearing:
    ASK = "予約取消は、窓口でどれくらい起きますか"
    ANSWER = "月に十数件で、ほとんどが電話での取消"

    @pytest.fixture
    def heard(self, world: Path) -> Path:
        tree_io.candidate("LIB", "LIB-Q03", ask=self.ASK, base_dir=world)
        tree_io.hear(
            "LIB",
            "LIB-Q03",
            answer=self.ANSWER,
            answered_by="窓口の職員",
            answered_at="2026-11-21",
            base_dir=world,
        )
        return world

    @staticmethod
    def _design_of(base: Path) -> str:
        return tree_io.load_tree("LIB", base)["nodes"][2]["design_ids"][0]

    def test_the_answer_lands_in_the_journal_as_a_hearing_event(
        self, heard: Path
    ) -> None:
        design_id = self._design_of(heard)
        result = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)

        assert result["copied"] is True
        event = result["event"]
        assert event["id"] == f"{design_id}-E02"
        assert (event["type"], event["content"]) == ("hearing", self.ANSWER)
        assert event["metadata"] == {
            "node_id": "LIB-Q03",
            "ask": self.ASK,
            "answered_by": "窓口の職員",
            "answered_at": "2026-11-21",
        }
        events = design_io.load_journal(design_id, base_dir=heard)["events"]
        assert [e["id"] for e in events] == [f"{design_id}-E01", f"{design_id}-E02"]
        assert events[1]["content"] == self.ANSWER

    def test_copying_twice_writes_one_event(self, heard: Path) -> None:
        design_id = self._design_of(heard)
        tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        again = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)

        assert again["copied"] is False
        assert "already" in again["reason"]
        events = design_io.load_journal(design_id, base_dir=heard)["events"]
        assert len(events) == 2

    def test_a_changed_answer_is_copied_as_a_new_event(self, heard: Path) -> None:
        design_id = self._design_of(heard)
        tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        tree_io.hear(
            "LIB",
            "LIB-Q03",
            answer="月に数件",
            answered_by="窓口の職員",
            answered_at="2026-11-22",
            base_dir=heard,
        )
        tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        events = design_io.load_journal(design_id, base_dir=heard)["events"]
        assert [e["id"][-3:] for e in events] == ["E01", "E02", "E03"]

    def test_a_journal_that_does_not_exist_is_created_with_its_header(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)
        tree_io.candidate("LIB", "LIB-Q02", ask=self.ASK, base_dir=tree)
        tree_io.hear(
            "LIB",
            "LIB-Q02",
            answer=self.ANSWER,
            answered_by="窓口の職員",
            answered_at="2026-11-21",
            base_dir=tree,
        )
        tree_io.copy_hearing("LIB", "LIB-Q02", design_id, base_dir=tree)

        journal = design_io.load_journal(design_id, base_dir=tree)
        assert journal["metadata"]["design_id"] == design_id
        assert journal["metadata"]["created_at"] and journal["metadata"]["updated_at"]
        assert [e["id"] for e in journal["events"]] == [f"{design_id}-E01"]

    def test_a_node_without_an_answer_copies_nothing_and_is_not_an_error(
        self, world: Path
    ) -> None:
        design_id = self._design_of(world)
        result = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=world)
        assert result["copied"] is False
        assert "no answer" in result["reason"]

    def test_a_design_not_linked_to_the_node_is_refused(self, heard: Path) -> None:
        other = _design(heard)
        with pytest.raises(ValueError, match="not linked"):
            tree_io.copy_hearing("LIB", "LIB-Q03", other, base_dir=heard)

    @pytest.mark.parametrize("status", ["supported", "rejected", "inconclusive"])
    def test_a_finished_design_is_refused_and_its_journal_is_left_as_it_is(
        self, heard: Path, status: str
    ) -> None:
        design_id = self._design_of(heard)
        design_io.transition_status(design_id, status, base_dir=heard)
        before = self._journal_path(heard).read_bytes()

        with pytest.raises(ValueError, match=f"{design_id} is {status}"):
            tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        assert self._journal_path(heard).read_bytes() == before

    def test_the_refusal_says_where_the_answer_goes_instead(self, heard: Path) -> None:
        design_id = self._design_of(heard)
        _finish(heard, design_id)

        with pytest.raises(ValueError, match="next design"):
            tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)

    def test_an_answer_copied_before_the_design_finished_is_not_an_error(
        self, heard: Path
    ) -> None:
        design_id = self._design_of(heard)
        tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        _finish(heard, design_id)

        again = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        assert again["copied"] is False
        assert "already" in again["reason"]

    def test_a_finished_design_with_no_answer_to_copy_is_not_an_error(
        self, world: Path
    ) -> None:
        design_id = self._design_of(world)
        _finish(world, design_id)

        result = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=world)
        assert result["copied"] is False

    def _journal_path(self, heard: Path) -> Path:
        return heard / "designs" / f"{self._design_of(heard)}_journal.yaml"

    def test_a_journal_whose_top_level_is_a_list_is_refused_and_left_as_it_is(
        self, heard: Path
    ) -> None:
        path = self._journal_path(heard)
        path.write_text("- id: X-E01\n  type: observe\n", encoding="utf-8")
        before = path.read_bytes()

        with pytest.raises(ValueError, match=path.name):
            tree_io.copy_hearing(
                "LIB", "LIB-Q03", self._design_of(heard), base_dir=heard
            )
        assert path.read_bytes() == before

    @pytest.mark.parametrize("events", ["{a: 1}", "hello"])
    def test_events_that_are_not_a_list_are_refused_and_left_as_they_are(
        self, heard: Path, events: str
    ) -> None:
        path = self._journal_path(heard)
        path.write_text(f"events: {events}\n", encoding="utf-8")
        before = path.read_bytes()

        with pytest.raises(ValueError, match="events"):
            tree_io.copy_hearing(
                "LIB", "LIB-Q03", self._design_of(heard), base_dir=heard
            )
        assert path.read_bytes() == before

    def test_the_cli_exits_1_with_a_message_when_the_events_are_not_a_list(
        self,
        heard: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        path = self._journal_path(heard)
        path.write_text("events: hello\n", encoding="utf-8")
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))

        code = tree_io._main(
            [
                "copy-hearing",
                "--theme",
                "LIB",
                "--node",
                "LIB-Q03",
                "--design",
                self._design_of(heard),
                "--base-dir",
                str(heard),
            ]
        )

        assert code == 1
        err = capsys.readouterr().err
        assert err.startswith("tree_io: ")
        assert "Traceback" not in err

    def test_events_that_are_not_mappings_are_skipped_and_the_hearing_is_appended(
        self, heard: Path
    ) -> None:
        design_id = self._design_of(heard)
        path = self._journal_path(heard)
        path.write_text(
            "events:\n"
            "  - just text\n"
            f"  - id: {design_id}-E01\n"
            "    type: hearing\n"
            f"    content: {self.ANSWER}\n"
            "    metadata: not a mapping\n",
            encoding="utf-8",
        )

        result = tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)

        assert result["copied"] is True
        assert result["event"]["id"] == f"{design_id}-E02"
        events = design_io.load_journal(design_id, base_dir=heard)["events"]
        assert len(events) == 3

    def test_a_copied_hearing_can_back_an_answer_as_a_journal_event(
        self, heard: Path
    ) -> None:
        design_id = self._design_of(heard)
        tree_io.copy_hearing("LIB", "LIB-Q03", design_id, base_dir=heard)
        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q03", "取消は月に十数件", f"{design_id}-E02")],
            base_dir=heard,
        )
        assert result["violations"] == []


class TestCli:
    def _run(self, insight: Path, *args: str, payload: dict | None = None):
        return _run_cli(insight, *args, payload=payload)

    def test_get_says_where_it_looked_when_the_theme_has_no_tree(
        self, insight: Path
    ) -> None:
        missing = self._run(insight, "get", "--theme", "LIB")

        assert missing.returncode == 0
        assert json.loads(missing.stdout) == {}
        looked = str(insight.resolve() / "themes" / "LIB_tree.yaml")
        assert missing.stderr.strip() == f"tree_io: no tree at {looked}"

    @pytest.mark.parametrize(
        ("command", "payload"),
        [
            ("progress", None),
            ("add-node", {"question": "q", "parent_question_id": "LIB-Q01"}),
        ],
    )
    def test_a_tree_that_fails_its_schema_is_an_error_not_a_crash(
        self, insight: Path, command: str, payload: dict | None
    ) -> None:
        (insight / "themes").mkdir(parents=True)
        (insight / "themes" / "LIB_tree.yaml").write_text(
            "theme_id: LIB\n", encoding="utf-8"
        )

        done = self._run(insight, command, "--theme", "LIB", payload=payload)

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr

    def test_get_is_silent_when_the_tree_is_there(self, insight: Path) -> None:
        self._run(
            insight,
            "create",
            payload={"theme_id": "LIB", "question": ROOT_QUESTION, "aim": AIM},
        )

        found = self._run(insight, "get", "--theme", "LIB")

        assert json.loads(found.stdout)["theme_id"] == "LIB"
        assert found.stderr == ""

    def test_create_add_link_and_progress_round_trip(self, insight: Path) -> None:
        created = self._run(
            insight,
            "create",
            payload={"theme_id": "LIB", "question": ROOT_QUESTION, "aim": AIM},
        )
        assert created.returncode == 0, created.stderr

        added = self._run(
            insight,
            "add-node",
            "--theme",
            "LIB",
            payload={
                "question": "期限切れを一貫して数えられるか",
                "parent_question_id": "LIB-Q01",
                "contribution": "件数が変わる",
            },
        )
        assert json.loads(added.stdout)["id"] == "LIB-Q02"

        design_id = _design(insight)
        linked = self._run(
            insight,
            "link",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q02",
            "--design",
            design_id,
        )
        assert json.loads(linked.stdout)["design_ids"] == [design_id]

        progress = self._run(insight, "progress", "--theme", "LIB")
        assert json.loads(progress.stdout)["LIB-Q02"] == "investigating"

        got = self._run(insight, "get", "--theme", "LIB")
        assert json.loads(got.stdout)["theme_id"] == "LIB"

    def test_revise_root_reads_the_bump_from_the_payload(self, tree: Path) -> None:
        revised = self._run(
            tree,
            "revise-root",
            "--theme",
            "LIB",
            payload={
                "question": "別の問い",
                "bump": True,
                "reason": "到達点が変わった",
            },
        )
        assert revised.returncode == 0, revised.stderr
        assert len(json.loads(revised.stdout)["root_revisions"]) == 2

    def test_decide_reads_the_decision_from_the_payload(self, tree: Path) -> None:
        _add(tree)
        decided = self._run(
            tree,
            "decide",
            "--theme",
            "LIB",
            payload={"kind": "start", "node_id": "LIB-Q02", "reason": "件数が変わる"},
        )
        assert decided.returncode == 0, decided.stderr
        assert json.loads(decided.stdout)["node_id"] == "LIB-Q02"
        got = self._run(tree, "get", "--theme", "LIB")
        assert len(json.loads(got.stdout)["decisions"]) == 1

    def test_the_next_candidate_commands_round_trip_through_the_cli(
        self, world: Path
    ) -> None:
        design_id = tree_io.load_tree("LIB", world)["nodes"][2]["design_ids"][0]
        noted = self._run(
            world,
            "candidate",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q03",
            payload={"ask": "取消は月に何件か", "changes_if": "件数次第"},
        )
        assert noted.returncode == 0, noted.stderr
        assert json.loads(noted.stdout)["next_candidate"]["ask"] == "取消は月に何件か"

        heard = self._run(
            world,
            "hear",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q03",
            payload={
                "answer": "月に十数件",
                "answered_by": "窓口の職員",
                "answered_at": "2026-11-21",
            },
        )
        assert heard.returncode == 0, heard.stderr

        copied = self._run(
            world,
            "copy-hearing",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q03",
            "--design",
            design_id,
        )
        assert copied.returncode == 0, copied.stderr
        assert json.loads(copied.stdout)["event"]["type"] == "hearing"

        again = self._run(
            world,
            "copy-hearing",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q03",
            "--design",
            design_id,
        )
        assert (again.returncode, json.loads(again.stdout)["copied"]) == (0, False)

        listed = self._run(world, "candidates", "--theme", "LIB")
        assert json.loads(listed.stdout) == []

    def test_hear_on_a_node_without_an_ask_exits_1_with_the_message(
        self, world: Path
    ) -> None:
        done = self._run(
            world,
            "hear",
            "--theme",
            "LIB",
            "--node",
            "LIB-Q03",
            payload={
                "answer": "x",
                "answered_by": "y",
                "answered_at": "2026-11-21",
            },
        )
        assert done.returncode == 1
        assert "no ask to answer" in done.stderr
        assert done.stdout == ""

    def test_a_node_command_without_its_node_says_so(self, world: Path) -> None:
        done = self._run(world, "hear", "--theme", "LIB", payload={})
        assert done.returncode == 1
        assert "--node is required" in done.stderr

    def test_decide_with_a_round_exits_1(self, world: Path) -> None:
        done = self._run(
            world,
            "decide",
            "--theme",
            "LIB",
            payload={
                "kind": "start",
                "node_id": "LIB-Q02",
                "reason": "x",
                "round": 0,
            },
        )
        assert done.returncode == 1
        assert "round" in done.stderr

    def test_a_command_without_its_theme_says_so(self, tree: Path) -> None:
        missing = self._run(tree, "progress")
        assert missing.returncode != 0
        assert "--theme is required" in missing.stderr

    def test_a_rejected_write_exits_with_an_error(self, tree: Path) -> None:
        rejected = self._run(
            tree,
            "add-node",
            "--theme",
            "LIB",
            payload={"question": "寄与の無い論点", "parent_question_id": "LIB-Q01"},
        )
        assert rejected.returncode != 0
        assert "contribution" in rejected.stderr

    def test_answer_exits_0_and_prints_the_round_written(self, world: Path) -> None:
        done = self._run(
            world,
            "answer",
            "--theme",
            "LIB",
            payload={"answers": [_entry("LIB-Q02", "期限切れは152件")]},
        )

        assert done.returncode == 0, done.stderr
        out = json.loads(done.stdout)
        assert (out["round"], out["violations"]) == (1, [])
        assert out["written"] == [
            {"node_id": "LIB-Q02", "previous_round": None, "restated": False}
        ]

    def test_answer_exits_3_with_the_violations_and_leaves_the_file_alone(
        self, world: Path
    ) -> None:
        path = world / "themes" / "LIB_tree.yaml"
        before = path.read_bytes()

        done = self._run(
            world,
            "answer",
            "--theme",
            "LIB",
            payload={"answers": [_entry("LIB-Q02", "期限切れは999件")]},
        )

        assert done.returncode == 3, done.stderr
        out = json.loads(done.stdout)
        assert [v["kind"] for v in out["violations"]] == ["number-not-cited"]
        assert (out["round"], out["written"]) == (0, [])
        assert path.read_bytes() == before

    def test_a_payload_that_is_not_json_exits_1_without_a_traceback(
        self, world: Path
    ) -> None:
        done = subprocess.run(
            [sys.executable, "-m", "skills._shared.tree_io", "answer", "--theme", "LIB"]
            + ["--base-dir", str(world)],
            input="{answers:",
            capture_output=True,
            text=True,
        )

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr

    def test_a_journal_that_cannot_be_read_exits_1_without_a_traceback(
        self, world: Path
    ) -> None:
        journal = world / "designs" / "LIB-H01_journal.yaml"
        journal.unlink()
        journal.mkdir()

        done = self._run(
            world,
            "answer",
            "--theme",
            "LIB",
            payload={"answers": [_entry("LIB-Q02", "期限切れは152件")]},
        )

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr

    def test_answer_exits_1_for_a_node_that_is_not_in_the_tree(
        self, world: Path
    ) -> None:
        done = self._run(
            world,
            "answer",
            "--theme",
            "LIB",
            payload={"answers": [_entry("LIB-Q09", "152件")]},
        )

        assert done.returncode == 1
        assert "LIB-Q09" in done.stderr
        assert done.stdout == ""


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

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
        assert "別の journal に書いた同じ id" not in text
        assert "journal に見つからない出来事" in text

    def test_an_event_id_written_twice_keeps_the_first(self, tree: Path) -> None:
        design_id = self._answered(tree)
        event = {"id": f"{design_id}-E01", "type": "evidence", "content": "二つ目"}
        journal = design_io.load_journal(design_id, base_dir=tree)
        journal["events"].append(event)
        design_io.write_journal(design_id, journal, base_dir=tree)

        tree_io.render("LIB", base_dir=tree)

        text = (tree / "themes" / "LIB_tree.html").read_text(encoding="utf-8")
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

    def test_a_linked_design_without_an_id_inside_is_still_shown(
        self, tree: Path
    ) -> None:
        _add(tree)
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=tree)
        stored = dict(design_io.load_design(design_id, base_dir=tree))
        del stored["id"]
        stored["title"] = "id の無い分析設計"
        atomic_write_yaml(tree / "designs" / f"{design_id}_hypothesis.yaml", stored)

        assert "id の無い分析設計" in _rendered(tree)

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
