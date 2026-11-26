"""Tests of skills/_shared/tree_io.py (Epic 18): The ``tree_io`` command line.

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skills._shared import tree_io
from tests.tree_io._support import AIM, ROOT_QUESTION, _add, _design, _entry, _run_cli


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
        assert json.loads(progress.stdout)["LIB-Q02"]["progress"] == "investigating"

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

    def _started(self, world: Path) -> Path:
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q02", reason="最初", base_dir=world
        )
        return world / "themes" / "LIB_tree.yaml"

    def test_decide_exits_0_and_prints_the_decision_with_its_cites(
        self, world: Path
    ) -> None:
        self._started(world)

        done = self._run(
            world,
            "decide",
            "--theme",
            "LIB",
            payload={
                "kind": "return",
                "node_id": "LIB-Q03",
                "reason": "期限切れは152件で、数え方は定まった",
                "cites": ["LIB-H01-E01"],
            },
        )

        assert done.returncode == 0, done.stderr
        assert json.loads(done.stdout)["cites"] == ["LIB-H01-E01"]

    def test_decide_exits_3_with_the_violations_and_leaves_the_file_alone(
        self, world: Path
    ) -> None:
        path = self._started(world)
        before = path.read_bytes()

        done = self._run(
            world,
            "decide",
            "--theme",
            "LIB",
            payload={
                "kind": "return",
                "node_id": "LIB-Q03",
                "reason": "期限切れは999件と多い",
                "cites": ["LIB-H01-E01"],
            },
        )

        assert done.returncode == 3, done.stderr
        assert json.loads(done.stdout) == {
            "violations": [
                {"position": 2, "round": 0, "kind": "number-not-cited", "text": "999"}
            ]
        }
        assert path.read_bytes() == before

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
