"""Structure tests for the next candidates and the tree decision (Epic 18, Story 18.5).

After the current answers, /analysis-reflection shows the untouched nodes as next
candidates, keeps what the analyst heard from a person, and records the decision
the analyst takes (US-3 AC 4, AC 5). /analysis-framing asks which node to design
next on a rerun, and /analysis-design copies a heard answer into the journal as a
``hearing`` event. The steps live in SKILL.md prose, so these tests guard the
load-bearing parts: the commands the skills show are accepted by the real
tree_io, and the analyst is asked where the Story says so.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills._shown import run_shown_commands, run_shown_line
from tests.skills.test_skill_structure import _read_skill


def _reflection(heading: str) -> str:
    return section(_read_skill("analysis-reflection"), heading)


def _framing(heading: str) -> str:
    return section(_read_skill("analysis-framing"), heading)


def _library(insight: Path) -> None:
    """LIB-Q02 is started (LIB-H01) and holds the start decision; LIB-Q03 is untouched."""
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
    for question, contribution in (
        ("期限切れを一貫して数えられるか", "予約取消が混ざると、件数が変わる"),
        ("通知は期限に間に合っているか", "通知が遅いなら、延長より通知を直す"),
    ):
        tree_io.add_node(
            "LIB",
            question=question,
            parent_question_id="LIB-Q01",
            contribution=contribution,
            base_dir=insight,
        )
    tree_io.decide(
        "LIB", kind="start", node_id="LIB-Q02", reason="最初に数え方", base_dir=insight
    )
    design = design_io.create_design(
        theme_id="LIB",
        title="Test",
        hypothesis_statement="X improves Y",
        hypothesis_background="because Z",
        methodology={"method": "OLS"},
        base_dir=insight,
    )
    tree_io.link_design("LIB", "LIB-Q02", design["id"], base_dir=insight)


def _node(insight: Path, node_id: str) -> dict:
    nodes = tree_io.load_tree("LIB", base_dir=insight)["nodes"]
    return next(n for n in nodes if n["id"] == node_id)


class TestReflectionShowsTheNextCandidates:
    """US-3 AC 4: untouched nodes, with an ask, what its answer changes, what is known."""

    def test_the_candidates_come_from_tree_io(self) -> None:
        step = unwrap(_reflection("### Step T6: "))
        assert "`tree_io candidates --theme {theme_id}`" in step
        assert "no design" in step

    @pytest.mark.parametrize("note", ["ask", "changes_if", "known"])
    def test_each_note_is_explained(self, note: str) -> None:
        assert table_row(_reflection("### Step T6: "), f"`{note}`")

    def test_the_shown_command_writes_the_notes_of_an_untouched_node(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)

        ran = run_shown_commands(_reflection("### Step T6: "), insight, monkeypatch)

        assert ran == ["candidate"]
        notes = _node(insight, "LIB-Q03")["next_candidate"]
        assert notes["ask"] and notes["changes_if"] and notes["known"]

    def test_data_sources_are_read_without_their_connection(self) -> None:
        step = unwrap(_reflection("### Step T6: "))
        assert "`catalog_io list`" in step
        assert "ADR-0022" in step
        kept_out = re.search(r"Never write[^.]*`connection`[^.]*\.", step)
        assert kept_out, "no sentence keeps connection values out of the tree"

    def test_a_note_states_only_what_was_read(self) -> None:
        step = unwrap(_reflection("### Step T6: "))
        assert re.search(r"(?i)never[^.]*`known`[^.]*did not read", step)

    def test_a_node_needs_no_ask(self) -> None:
        assert "needs no note" in unwrap(_reflection("### Step T6: "))


class TestReflectionKeepsWhatTheAnalystHeard:
    """US-3 AC 4: the answer stays on the candidate with who answered and when."""

    def test_the_shown_command_keeps_the_answer_with_who_and_when(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)
        run_shown_commands(_reflection("### Step T6: "), insight, monkeypatch)

        ran = run_shown_commands(_reflection("### Step T7: "), insight, monkeypatch)

        assert ran[0] == "hear"
        notes = _node(insight, "LIB-Q03")["next_candidate"]
        assert notes["answer"] and notes["answered_by"] and notes["answered_at"]

    def test_who_and_when_are_never_filled_in_by_the_skill(self) -> None:
        step = unwrap(_reflection("### Step T7: "))
        assert re.search(r"(?i)never fill[^.]*`answered_by`[^.]*`answered_at`", step)

    def test_the_answer_is_kept_in_the_analysts_words(self) -> None:
        assert "in the analyst's words" in unwrap(_reflection("### Step T7: "))

    def test_a_heard_answer_cannot_be_cited_before_it_is_in_a_journal(self) -> None:
        step = unwrap(_reflection("### Step T7: "))
        assert "`hearing`" in step
        assert re.search(r"cannot be cited[^.]*until", step)


class TestReflectionRecordsTheDecision:
    """US-3 AC 5: deepen, return or close, with the analyst's reason."""

    def test_the_decision_is_a_keep_gate(self) -> None:
        assert "KEEP gate" in _reflection("### Step T7: ")

    @pytest.mark.parametrize(
        ("kind", "word"),
        [("deepen", "深める"), ("return", "親に戻る"), ("close", "区切る")],
    )
    def test_each_kind_is_explained(self, kind: str, word: str) -> None:
        assert word in table_row(_reflection("### Step T7: "), f"`{kind}`")[1]

    def test_the_shown_command_records_the_decision_at_the_last_round(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)
        run_shown_commands(_reflection("### Step T6: "), insight, monkeypatch)

        ran = run_shown_commands(_reflection("### Step T7: "), insight, monkeypatch)

        assert ran == ["hear", "decide"]
        decision = tree_io.load_tree("LIB", base_dir=insight)["decisions"][-1]
        assert (decision["kind"], decision["node_id"]) == ("return", "LIB-Q03")
        assert decision["reason"]
        assert decision["round"] == 0  # no reflection round has been written yet

    def test_the_skill_never_decides_for_the_analyst(self) -> None:
        step = unwrap(_reflection("### Step T7: "))
        assert re.search(
            r"(?i)never choose[^.]*kind[^.]*node[^.]*reason[^.]*yourself", step
        )

    def test_the_skill_never_sets_the_round(self) -> None:
        assert re.search(
            r"(?i)never send[^.]*`round`", unwrap(_reflection("### Step T7: "))
        )

    def test_a_decision_cannot_be_taken_back(self) -> None:
        step = unwrap(_reflection("### Step T7: "))
        assert "append-only" in step
        assert "read the decision back" in step

    def test_a_tree_without_a_start_is_sent_to_framing(self) -> None:
        step = unwrap(_reflection("### Step T7: "))
        missing = re.search(r"[^.]*no decision[^.]*\.", step)
        assert missing, "no sentence covers a tree without a start decision"
        assert "/analysis-framing" in missing.group(0)

    def test_the_analyst_may_leave_the_decision_open(self) -> None:
        assert "write nothing" in unwrap(_reflection("### Step T7: "))

    def test_the_html_is_rendered_again_after_the_decision(self) -> None:
        assert "`tree_io render --theme {theme_id}`" in unwrap(
            _reflection("### Step T7: ")
        )


class TestFramingAsksWhichNodeComesNext:
    """Story 18.5: a rerun never names a node the analyst has not just chosen."""

    def test_the_next_node_is_a_keep_gate(self) -> None:
        assert "KEEP gate" in _framing("#### 4d: ")

    def test_the_brief_waits_for_the_analysts_choice(self) -> None:
        step = unwrap(_framing("#### 4d: "))
        assert re.search(
            r"(?i)do not output the Framing Brief[^.]*until the analyst", step
        )

    def test_the_node_of_the_latest_decision_is_offered_with_its_progress(self) -> None:
        step = unwrap(_framing("#### 4d: "))
        assert "latest decision" in step
        assert "`tree_io progress --theme {theme_id}`" in step
        assert "`tree_io candidates --theme {theme_id}`" in step

    def test_a_node_that_already_has_a_design_is_confirmed(self) -> None:
        step = unwrap(_framing("#### 4d: "))
        linked = re.search(r"[^.]*already has a design[^.]*\.", step)
        assert linked, "no sentence covers a node that already has a design"
        assert "another design" in linked.group(0)

    def test_the_shown_command_records_the_change_of_node(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)

        ran = run_shown_commands(_framing("#### 4d: "), insight, monkeypatch)

        assert ran == ["decide"]
        decision = tree_io.load_tree("LIB", base_dir=insight)["decisions"][-1]
        assert (decision["kind"], decision["node_id"]) == ("return", "LIB-Q03")

    def test_the_same_node_writes_no_decision(self) -> None:
        step = unwrap(_framing("#### 4d: "))
        assert re.search(r"same node[^.]*no decision", step)

    def test_a_close_is_never_written_by_framing(self) -> None:
        step = unwrap(_framing("#### 4d: "))
        assert re.search(r"(?i)never[^.]*`close`", step)

    def test_the_rerun_points_at_the_gate(self) -> None:
        assert "4d" in unwrap(_framing("#### 4c: "))

    def test_a_tree_with_a_decision_gets_no_second_start(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert re.search(r"already has a decision[^.]*never[^.]*`start`", rerun)


class TestDesignCopiesWhatTheAnalystHeard:
    """US-3 AC 4: when a design is made on the node, the answer goes to its journal."""

    def _copying(self) -> str:
        return section(_read_skill("analysis-design"), "#### Copy what the analyst")

    def test_the_shown_command_copies_the_answer_as_a_hearing_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        tree_io.create_tree(
            theme_id="FP",
            question="来期もクーポン施策を続けるか",
            aim={
                "kind": "business",
                "decision_maker": "マーケティング部長",
                "decision": "来期もクーポン施策を続けるか",
            },
            base_dir=insight,
        )
        tree_io.add_node(
            "FP",
            question="クーポンは新規の購入を増やしたか",
            parent_question_id="FP-Q01",
            contribution="増やしていなければ、続ける理由が1つ消える",
            base_dir=insight,
        )
        tree_io.candidate(
            "FP", "FP-Q02", ask="配布の対象は途中で変わりましたか", base_dir=insight
        )
        tree_io.hear(
            "FP",
            "FP-Q02",
            answer="7月から新規の会員だけに配っている",
            answered_by="販促の担当者",
            answered_at="2026-11-20",
            base_dir=insight,
        )
        design_io.create_design(
            theme_id="FP",
            title="Test",
            hypothesis_statement="X improves Y",
            hypothesis_background="because Z",
            methodology={"method": "OLS"},
            base_dir=insight,
        )
        tree_io.link_design("FP", "FP-Q02", "FP-H01", base_dir=insight)
        code = run_shown_line(self._copying(), "copy-hearing", insight, monkeypatch)

        assert code == 0
        (event,) = design_io.load_journal("FP-H01", insight)["events"]
        assert event["type"] == "hearing"
        assert event["content"] == "7月から新規の会員だけに配っている"
        assert event["metadata"]["answered_by"] == "販促の担当者"

    def test_a_finished_design_keeps_its_journal_and_the_answer_waits(self) -> None:
        copying = unwrap(self._copying())
        assert re.search(r"finished[^.]*refus", copying)
        assert re.search(r"next design[^.]*`copy-hearing`", copying)
        assert re.search(r"[Nn]ever[^.]*reopen", copying)

    def test_the_copy_comes_after_the_link(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 3: ")
        assert step.index("#### Link the design") < step.index(
            "#### Copy what the analyst"
        )

    def test_the_copy_runs_after_every_link(self) -> None:
        copying = unwrap(self._copying())
        assert "every time" in copying
        assert '`"copied": false`' in copying

    def test_the_answer_is_never_retyped(self) -> None:
        assert re.search(r"(?i)never[^.]*retype", unwrap(self._copying()))


class TestJournalKnowsTheHearingEvent:
    """ADR-0028: what a person answered is its own kind of journal event."""

    def test_the_convention_lists_hearing_with_who_and_when(self) -> None:
        convention = section(
            _read_skill("analysis-journal"), "## InsightType Convention"
        )
        row = table_row(convention, "`hearing`")
        assert "answered_by" in row[2] and "answered_at" in row[2]

    def test_a_hearing_event_is_not_an_observation_of_data(self) -> None:
        skill = unwrap(_read_skill("analysis-journal"))
        assert re.search(r"`hearing`[^.]*not[^.]*`observe`", skill)

    def test_the_summary_counts_hearing_events(self) -> None:
        assert "{hearing}hear" in _read_skill("analysis-journal")

    def test_the_phase_is_inferred_for_a_hearing_event(self) -> None:
        phases = section(_read_skill("analysis-journal"), "## Phase Inference")
        assert "`hearing`" in phases


class TestAnEmptyGetIsCheckedAgainstTheProject:
    """Story 18.5: `{}` also comes back when tree_io looked in another directory."""

    @pytest.mark.parametrize(
        ("skill", "heading"),
        [
            ("analysis-reflection", "### Step T1: "),
            ("analysis-framing", "#### 4a: "),
        ],
    )
    def test_the_path_on_stderr_is_compared_with_the_project(
        self, skill: str, heading: str
    ) -> None:
        step = unwrap(section(_read_skill(skill), heading))
        assert "`tree_io: no tree at {path}`" in step
        assert re.search(r"(?i)never `cd`[^.]*before", step)
        assert "this project's `.insight`" in step
