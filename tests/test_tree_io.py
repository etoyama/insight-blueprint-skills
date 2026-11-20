"""Unit tests for skills/_shared/tree_io.py (Epic 18, Story 18.1).

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``. Every
write goes through ``insight_blueprint.validate.validate_tree`` first.
"""

from __future__ import annotations

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


def _design(insight: Path, theme_id: str = "LIB") -> str:
    design = design_io.create_design(
        theme_id=theme_id,
        title="Test",
        hypothesis_statement="X improves Y",
        hypothesis_background="because Z",
        methodology={"method": "OLS"},
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

    def test_a_kind_other_than_start_is_not_written(self, two_nodes: Path) -> None:
        with pytest.raises(ValueError, match="kind"):
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


class TestCli:
    def _run(self, insight: Path, *args: str, payload: dict | None = None):
        return _run_cli(insight, *args, payload=payload)

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
