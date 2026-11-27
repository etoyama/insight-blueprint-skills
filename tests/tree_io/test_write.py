"""Tests of skills/_shared/tree_io.py (Epic 18): Writes that change the tree: create, add, link, revise, decide, and progress.

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.tree_io._support import (
    AIM,
    ROOT_QUESTION,
    _add,
    _derived,
    _design,
    _entry,
    _finish,
    _linked,
    _run_cli,
)


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
        assert tree_io.progress("LIB", base_dir=tree)[node_id]["progress"] == "analyzed"

        tree_io.link_derived_design("LIB", derived, base_dir=tree)

        assert (
            tree_io.progress("LIB", base_dir=tree)[node_id]["progress"]
            == "investigating"
        )
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


class TestDecideWithCites:
    """Epic 34, US-4 AC 1, AC 2 (ADR-0058): a decision that cites is checked first."""

    REASON = "期限切れは152件で、数え方は定まった"

    @pytest.fixture
    def started(self, world: Path) -> Path:
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初", base_dir=world
        )
        return world

    def _go_to_q03(self, base: Path, *cites: str, reason: str = REASON) -> dict:
        return tree_io.decide(
            "LIB",
            kind="return",
            node_id="LIB-Q03",
            reason=reason,
            cites=list(cites),
            base_dir=base,
        )

    def _decisions(self, base: Path) -> list[dict]:
        return tree_io.load_tree("LIB", base)["decisions"]

    def test_the_cites_are_written_with_the_decision(self, started: Path) -> None:
        decision = self._go_to_q03(started, "LIB-H01-E01")

        assert decision["cites"] == ["LIB-H01-E01"]
        assert self._decisions(started)[-1] == decision

    def test_a_decision_without_cites_writes_no_cites_key(self, started: Path) -> None:
        decision = self._go_to_q03(started)

        assert "cites" not in decision
        assert "cites" not in self._decisions(started)[-1]

    def test_an_event_of_another_branch_than_the_next_node_can_be_cited(
        self, started: Path
    ) -> None:
        # LIB-H01 is on LIB-Q02; the decision goes to LIB-Q03.
        assert "violations" not in self._go_to_q03(started, "LIB-H01-E01")

    @pytest.mark.parametrize(
        ("cite", "reason", "violation"),
        [
            ("LIB-H01-E09", "数え方は定まった", ("missing-event", "LIB-H01-E09")),
            ("LIB-H01-E01", "期限切れは153件と多い", ("number-not-cited", "153")),
        ],
    )
    def test_a_violation_is_returned_and_nothing_is_written(
        self, started: Path, cite: str, reason: str, violation: tuple[str, str]
    ) -> None:
        before = self._decisions(started)

        result = self._go_to_q03(started, cite, reason=reason)

        assert [(v["kind"], v["text"]) for v in result["violations"]] == [violation]
        assert result["violations"][0]["position"] == 2
        assert self._decisions(started) == before

    def test_an_event_of_a_design_on_no_node_is_not_written(
        self, started: Path
    ) -> None:
        loose = _design(started)
        design_io.write_journal(
            loose,
            {
                "events": [
                    {"id": f"{loose}-E01", "type": "observe", "content": "無関係"}
                ]
            },
            base_dir=started,
        )

        result = self._go_to_q03(started, f"{loose}-E01", reason="数え方は定まった")

        assert [v["kind"] for v in result["violations"]] == ["unlinked-design"]
        assert len(self._decisions(started)) == 1

    def test_a_cite_that_is_not_an_event_id_never_reaches_a_journal_path(
        self, started: Path
    ) -> None:
        with pytest.raises(ValueError, match=r"must be LIB-H\{nn\}-E\{nn\}"):
            self._go_to_q03(started, "../../etc/passwd-E01")
        assert len(self._decisions(started)) == 1

    def test_an_earlier_decision_that_no_longer_holds_does_not_stop_a_new_one(
        self, started: Path
    ) -> None:
        self._go_to_q03(started, "LIB-H01-E01")
        design_io.write_journal("LIB-H01", {"events": []}, base_dir=started)

        decision = tree_io.decide(
            "LIB", kind="return", node_id="LIB-Q02", reason="戻る", base_dir=started
        )

        assert decision["node_id"] == "LIB-Q02"
        assert len(self._decisions(started)) == 3

    def test_a_broken_journal_under_an_earlier_decision_does_not_stop_a_new_one(
        self, started: Path
    ) -> None:
        self._go_to_q03(started, "LIB-H01-E01")
        twice = {"id": "LIB-H01-E01", "type": "observe", "content": "152件"}
        design_io.write_journal("LIB-H01", {"events": [twice, twice]}, base_dir=started)

        decision = tree_io.decide(
            "LIB", kind="return", node_id="LIB-Q02", reason="戻る", base_dir=started
        )

        assert decision["node_id"] == "LIB-Q02"

    def test_a_decision_without_cites_reads_no_journal(self, started: Path) -> None:
        (started / "designs" / "LIB-H01_journal.yaml").write_text("events: [", "utf-8")

        assert self._go_to_q03(started)["node_id"] == "LIB-Q03"

    def test_the_same_event_cited_twice_is_not_written(self, started: Path) -> None:
        with pytest.raises(ValueError, match="cites the same event twice"):
            self._go_to_q03(started, "LIB-H01-E01", "LIB-H01-E01")
        assert len(self._decisions(started)) == 1

    def test_an_answer_still_cannot_cite_the_other_branch(self, started: Path) -> None:
        # US-2 AC 3: the wider reach of a decision is not the reach of an answer.
        result = tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q03", "記録がある", cite="LIB-H01-E01")],
            base_dir=started,
        )

        assert [v["kind"] for v in result["violations"]] == ["unlinked-design"]
        assert result["written"] == []


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
            # The subject has designs only below it: no word, the counts below it.
            "LIB-Q01": {
                "progress": None,
                "designs": [],
                "below": {"analyzed": 1, "investigating": 1, "not_started": 1},
            },
            untouched: {"progress": "not_started", "designs": [], "below": {}},
            open_node: {
                "progress": "investigating",
                "designs": [
                    {"design_id": open_design, "stage": "before_run"},
                    {"design_id": done_design, "stage": "finished"},
                ],
                "below": {},
            },
            done_node: {
                "progress": "analyzed",
                "designs": [{"design_id": done_design, "stage": "finished"}],
                "below": {},
            },
        }

    def test_a_question_with_no_design_on_it_or_below_it_is_not_started(
        self, tree: Path
    ) -> None:
        parent = _add(tree)["id"]
        child = _add(tree, parent_question_id=parent)["id"]

        progress = tree_io.progress("LIB", base_dir=tree)

        assert progress[parent] == {
            "progress": "not_started",
            "designs": [],
            "below": {"not_started": 1},
        }
        assert progress[child] == {
            "progress": "not_started",
            "designs": [],
            "below": {},
        }
        assert progress["LIB-Q01"] == {
            "progress": "not_started",
            "designs": [],
            "below": {"not_started": 2},
        }

    def test_changes_when_the_design_reaches_a_terminal_status(
        self, tree: Path
    ) -> None:
        node_id = _add(tree)["id"]
        design_id = _design(tree)
        tree_io.link_design("LIB", node_id, design_id, base_dir=tree)
        before = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")

        _finish(tree, design_id)

        assert tree_io.progress("LIB", base_dir=tree)[node_id]["progress"] == "analyzed"
        after = (tree / "themes" / "LIB_tree.yaml").read_text(encoding="utf-8")
        assert after == before

    def test_a_linked_design_that_disappeared_is_an_error(self, tree: Path) -> None:
        design_id = _design(tree)
        tree_io.link_design("LIB", "LIB-Q01", design_id, base_dir=tree)
        (tree / "designs" / f"{design_id}_hypothesis.yaml").unlink()

        with pytest.raises(ValueError, match=f"design '{design_id}' not found"):
            tree_io.progress("LIB", base_dir=tree)
