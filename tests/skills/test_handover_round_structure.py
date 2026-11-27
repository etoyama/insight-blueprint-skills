"""Structure tests for what follows the hand-over of a round of several nodes (Epic 35, Story 35.7).

After the designs are handed over, the dialogue agent rebuilds the page on every
return, asks the analyst what an analysis cannot go on without, stops one
analysis when the analyst says so, and asks how the finished analyses end, once
for all of them (US-4, US-5 AC 3). The commands the skills show are run against
the synthetic theme whose designs stand at every stage.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.handoff_trial import build, load_scenario
from skills._shared import design_io
from tests.skills._auto import (
    auto,
    gate_row,
    handover_item,
    handover_item_text,
    handover_part,
    round_item,
)
from tests.skills._markdown import section, table_row, table_rows, unwrap
from tests.skills._shown import (
    run_shown_design_commands,
    run_shown_design_line,
    run_shown_line,
)
from tests.skills.test_skill_structure import _read_skill

WAITING, RUNNING = "LIB-H04", "LIB-H05"
STOPPING = "#### Stopping an analysis"
BRIEF = "#### The brief of an execution agent"


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    """The synthetic theme: LIB-H04 waits for the analyst and LIB-H05 runs."""
    build(load_scenario("lib-stages"), tmp_path)
    return tmp_path


def _stage(insight: Path, design_id: str) -> str:
    return design_io.stage_reading(design_id, insight).stage.value


def _brief_line(label: str) -> str:
    """The bullet of the brief that starts with *label*."""
    for bullet in re.split(r"^- ", handover_part(BRIEF), flags=re.MULTILINE)[1:]:
        if bullet.startswith(label):
            return unwrap(bullet)
    raise AssertionError(f"the brief has no line starting with {label!r}")


def _notebook(heading: str) -> str:
    return section(_read_skill("analysis-notebook"), heading)


class TestThePageIsRebuiltOnEveryReturn:
    """US-5 AC 3 (ADR-0062 3)."""

    def test_the_dialogue_agent_rebuilds_the_page_each_time_an_agent_returns(
        self, staged: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        item = handover_item_text("return")
        assert run_shown_line(item, "render", staged, monkeypatch) == 0
        assert run_shown_line(item, "position", staged, monkeypatch) == 0
        assert re.search(
            r"[Ee]ach time[^.]*returned[^.]*without waiting for the others",
            unwrap(item),
        )

    def test_the_return_says_where_a_design_goes_by_its_stage(self) -> None:
        item = handover_item("return")
        assert re.search(r"`awaiting_confirmation`[^.]*\*\*confirmation\*\*", item)
        assert re.search(r"`awaiting_reflection`[^.]*\*\*endings\*\*", item)

    def test_an_execution_agent_skips_the_render_of_the_notebook_skill(self) -> None:
        step = unwrap(_notebook("### Step 7"))
        assert re.search(r"execution agent[^.]*skip this step", step)
        assert re.search(r"dialogue agent[^.]*rebuilds the page", step)

    def test_a_notebook_started_on_its_own_still_renders(self) -> None:
        step = unwrap(_notebook("### Step 7"))
        assert re.search(r"[Oo]therwise[^.]*`tree_io render --design", step)

    def test_the_brief_keeps_the_agent_from_the_page(self) -> None:
        never = _brief_line("What it never runs")
        assert re.search(r"Never `tree_io render`[^.]*dialogue agent rebuilds", never)


class TestAnAnalysisAsksBeforeChangingWhatWasRead:
    """US-4 AC 1 to AC 3 (ADR-0064 1 to 3)."""

    def test_the_brief_names_what_the_analyst_read(self) -> None:
        stops = _brief_line("Where it stops")
        for read in (
            "population",
            "grain",
            "denominator",
            "extraction",
            "source",
            "primary metric",
            "criterion",
        ):
            assert read in stops, read
        assert re.search(r"before it touches the data", stops)
        assert "`design_io ask-analyst`" in stops
        assert re.search(r"never asks the analyst[^.]*itself", stops)

    def test_the_command_the_brief_shows_makes_the_analysis_wait(
        self,
        staged: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (asked,) = run_shown_design_commands(
            handover_part(BRIEF), staged, monkeypatch, capsys
        )

        assert _stage(staged, RUNNING) == "awaiting_confirmation"
        assert design_io.stage_report(RUNNING, staged)["asks"] == [
            {"id": asked["id"], "content": asked["content"]}
        ]

    def test_the_other_stops_of_the_brief_are_not_confirmations(self) -> None:
        """A package or a side effect changes nothing the analyst read (ADR-0064 5)."""
        stops = _brief_line("Where it stops")
        assert re.search(r"package outside the allowlist[^.]*side effect", stops)

    def test_the_agent_returns_the_id_of_what_it_asked(self) -> None:
        assert "`id` of the confirmation" in _brief_line("What it returns")

    def test_the_confirmation_is_a_keep_gate(self) -> None:
        _, keep, _ = gate_row("confirmation after handing over")
        assert keep.startswith("**")
        assert "Step 3H" in keep

    def test_only_the_asking_analysis_waits(self) -> None:
        item = handover_item("confirmation")
        assert re.search(r"[Oo]nly that analysis waits", item)
        assert re.search(r"never[^.]*(stop|hold)[^.]*other execution agent", item)

    def test_the_shown_command_reads_what_is_asked(
        self, staged: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        item = handover_item_text("confirmation")
        assert run_shown_design_line(item, "stage", staged) == 0
        assert '"asks"' in capsys.readouterr().out
        assert "`asks`" in item
        assert re.search(r"[Nn]ever read[^.]*journal yourself", unwrap(item))

    def test_the_shown_command_records_the_answer_and_the_analysis_runs_again(
        self,
        staged: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        item = handover_item_text("confirmation")
        (answered,) = run_shown_design_commands(item, staged, monkeypatch, capsys)

        assert answered["metadata"] == {"answers": f"{WAITING}-E01"}
        assert _stage(staged, WAITING) == "running"
        assert re.search(r"answer[^.]*analyst's words", unwrap(item))

    def test_a_changed_design_is_shown_and_premortem_runs_again(self) -> None:
        """AC 3: the extraction may have changed, so the cost is looked at again."""
        item = handover_item("confirmation")
        assert "`design_io update`" in item
        assert re.search(r"before and after", item)
        assert re.search(r"back to \*\*premortem\*\*", item)
        premortem = handover_item("premortem")
        assert re.search(r"confirmation[^.]*answered", premortem)

    def test_a_change_a_started_confirmation_cannot_take_ends_in_a_stop(self) -> None:
        item = handover_item("confirmation")
        assert re.search(r"`update`[^.]*refuses[^.]*stop[^.]*derive", item)

    def test_a_round_of_one_node_goes_through_the_same_item(self) -> None:
        rows = {c[0]: c[-1] for c in table_rows(section(auto(), "### Step 1:"))}
        assert "**confirmation**" in rows["`awaiting_confirmation`"]
        assert "Step 3H" in rows["`awaiting_confirmation`"]

    def test_premortem_is_run_again_on_a_design_already_in_its_analysis(self) -> None:
        skill = unwrap(_read_skill("premortem"))
        assert re.search(r"`analyzing`[^.]*evaluated again", skill)
        assert re.search(r"`design_io stage[^.]*`stopped`[^.]*leave it out", skill)


class TestAResultUnderReviewIsNotRunAgain:
    """A review of the result holds the design in_review, with its result on record (ADR-0054)."""

    def test_only_a_design_before_its_run_is_moved_into_the_analysis(self) -> None:
        item = handover_item("premortem")
        assert re.search(
            r"`awaiting_reflection`[^.]*review of its result[^.]*never moved into the analysis",
            item,
        )
        assert re.search(r"never moved into the analysis[^.]*\*\*endings\*\*", item)


class TestOneAnalysisIsStopped:
    """US-4 AC 4 (ADR-0064 6, 7)."""

    def test_the_shown_command_stops_a_running_analysis_for_good(
        self,
        staged: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        shown = handover_part(STOPPING).replace("LIB-H05", RUNNING)
        run_shown_design_commands(shown, staged, monkeypatch, capsys)

        assert _stage(staged, RUNNING) == "stopped"
        with pytest.raises(ValueError, match="is stopped"):
            design_io.transition_status(RUNNING, "explored", staged)
        assert _stage(staged, RUNNING) == "stopped"

    def test_the_stop_is_shown_in_one_place(self) -> None:
        assert auto().count("| design_io stop") == 1
        assert "| design_io stop" in handover_part(STOPPING)
        check = handover_item("check before handing over")
        assert re.search(r"stopped[^.]*Stopping an analysis", check)

    def test_only_the_named_analysis_stops(self) -> None:
        part = unwrap(handover_part(STOPPING))
        assert re.search(r"only the one[^.]*name", part)
        assert re.search(r"others go on", part)
        assert re.search(r"reason[^.]*analyst's words", part)

    def test_a_stopped_analysis_is_derived_and_never_resumed(self) -> None:
        part = unwrap(handover_part(STOPPING))
        assert re.search(r"not resumed", part)
        assert re.search(r"derive[^.]*`parent_id`", part)
        assert re.search(r"[Nn]ever delete the design or unlink it", part)
        assert re.search(r"`design_io transition`[^.]*refuses", part)

    def test_an_analysis_with_its_result_on_record_is_ended_and_not_stopped(
        self,
    ) -> None:
        part = unwrap(handover_part(STOPPING))
        assert re.search(r"`awaiting_reflection`[^.]*\*\*endings\*\*", part)

    def test_the_agent_of_a_stopped_analysis_records_nothing_more(self) -> None:
        part = unwrap(handover_part(STOPPING))
        assert re.search(r"`design_io journal-append`[^.]*refuses", part)

    def test_the_analyst_may_ask_for_it_anywhere_in_the_walk(self) -> None:
        walk = section(auto(), "### Step 3:")
        asked = unwrap(walk[walk.index("only when the analyst asks") :])
        assert re.search(r"stop an analysis[^.]*Stopping an analysis", asked)

    def test_the_notebook_skill_does_not_pick_up_a_stopped_analysis(
        self, staged: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        step = _notebook("### Step 1")
        assert (
            run_shown_design_line(
                step.replace("{design_id}", "LIB-H06"), "stage", staged
            )
            == 0
        )
        assert '"stage": "stopped"' in capsys.readouterr().out
        assert re.search(r"`stopped` analysis is not run", unwrap(step))
        assert re.search(r"stopped[^.]*deriving a new design", unwrap(step))
        assert re.search(r"`awaiting_confirmation`[^.]*answer", unwrap(step))


class TestTheResultsGoInThroughDesignIo:
    """Decision of the Story: the journal of a run is written under the write lock."""

    def test_the_notebook_records_with_the_command(
        self,
        staged: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        step = _notebook("### Step 6").replace("{design_id}", RUNNING)
        written = run_shown_design_commands(step, staged, monkeypatch, capsys)

        assert [e["type"] for e in written[0]] == ["observe", "evidence", "question"]
        assert _stage(staged, RUNNING) == "awaiting_reflection"

    def test_the_file_is_not_written_by_hand(self) -> None:
        step = unwrap(_notebook("### Step 6"))
        assert re.search(r"[Nn]ever write the journal file", step)
        assert "**never emit `conclude`**" in step
        reference = _read_skill("analysis-notebook")
        assert table_row(
            section(reference, "## design_io / catalog_io Reference"),
            "`design_io journal-append --id ID`",
        )

    def test_a_refused_result_ends_the_run(self) -> None:
        step = unwrap(_notebook("### Step 6"))
        assert re.search(r"refuses[^.]*stopped[^.]*return", step)

    def test_the_brief_names_the_command_among_what_the_agent_writes(self) -> None:
        writes = _brief_line("What it writes")
        assert "`design_io journal-append`" in writes
        assert "`design_io ask-analyst`" in writes


class TestTheEndingsAreAskedTogether:
    """The human's decision of 2026-11-27: one question for the designs that came back."""

    def test_the_endings_are_a_keep_gate_asked_once(self) -> None:
        _, keep, _ = gate_row("endings")
        assert keep.startswith("**")
        assert "Step 3H" in keep
        item = handover_item("endings")
        assert re.search(r"asked once for all", item)

    def test_they_are_asked_when_nothing_is_running_or_waiting(self) -> None:
        item = handover_item("endings")
        assert re.search(
            r"no execution agent is at work[^.]*no analysis waits for a confirmation",
            item,
        )

    def test_the_questions_are_those_of_the_reflection_as_it_words_them(self) -> None:
        item = handover_item("endings")
        assert re.search(r"`/analysis-reflection \{design_id\}`[^.]*Step 2", item)
        assert re.search(r"three questions[^.]*Step 3[^.]*as that step words", item)
        assert "この分析設計をどう終えるか" in item
        assert re.search(r"[Aa]dd no question of your own", item)

    def test_a_design_the_reply_does_not_cover_is_not_ended(self) -> None:
        item = handover_item("endings")
        assert re.search(r"[Nn]ever end a design[^.]*did not", item)

    def test_the_designs_end_one_after_another_before_the_theme_reflection(
        self,
    ) -> None:
        item = handover_item("endings")
        assert re.search(r"Step 4[^.]*one design after another", item)
        assert re.search(r"`tree_io render --theme[^.]*\*\*theme reflection\*\*", item)

    def test_the_reflection_of_a_round_of_one_node_stays_as_it_was(self) -> None:
        assert "pause at its third question" in round_item("reflection")


class TestTheReflectionReadsTheStage:
    """A reader of whether the analysis ran follows the one rule (ADR-0061 6)."""

    def _step(self) -> str:
        return section(_read_skill("analysis-reflection"), "### Step 1")

    def test_whether_a_result_is_on_record_comes_from_design_io(
        self, staged: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        step = self._step()
        assert (
            run_shown_design_line(
                step.replace("{design_id}", "LIB-H03"), "stage", staged
            )
            == 0
        )
        assert '"result_on_record": true' in capsys.readouterr().out
        assert re.search(r"`result_on_record`[^.]*false", unwrap(step))
        assert re.search(r"[Nn]ever work[^.]*out[^.]*journal", unwrap(step))

    def test_a_stopped_analysis_is_not_reflected_on(self) -> None:
        step = unwrap(self._step())
        assert re.search(r"`stopped`[^.]*no result to reflect on", step)
        assert re.search(r"deriving a new design", step)
