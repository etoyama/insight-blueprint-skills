"""Tests of skills/_shared/tree_io.py (Epic 18): The walk: ``position``, the next candidates, hearing, and copying a hearing.

tree_io is the only writer of ``.insight/themes/{theme_id}_tree.yaml``.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from skills._shared._atomic import atomic_write_yaml
from tests.tree_io._support import _add, _design, _entry, _finish


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

    def test_an_exploration_ended_as_explored_is_concluded(self, started: Path) -> None:
        """Epic 32 US-2 AC 5: explored is a terminal status for the walk."""
        design_id = design_io.create_design(
            theme_id="LIB",
            title="Test",
            analysis_intent="exploratory",
            exploration_question="How many loans expire each month?",
            exploration_background="Nobody has counted them",
            base_dir=started,
        )["id"]
        tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=started)
        design_io.transition_status(design_id, "explored", base_dir=started)

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
