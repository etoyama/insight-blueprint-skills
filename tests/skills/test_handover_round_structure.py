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

from insight_blueprint.models.analysis_stage import SETTLED, AnalysisStage
from scripts.handoff_trial import build, load_scenario
from skills._shared import design_io, tree_io
from skills._shared.tree_words import HANDOVER_HEADING, STAGE_WORDS
from tests.skills._auto import (
    auto,
    auto_gates,
    auto_step,
    framing_section,
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

# Step 3H, the round of a decision that names several nodes (Epic 35, Story 35.6).
HANDOVER = [
    "briefs",
    "designs",
    "check before handing over",
    "premortem",
    "hand over",
    "return",
    "confirmation",
    "endings",
]

WAITING, RUNNING = "LIB-H04", "LIB-H05"
AWAITING_MARK = STAGE_WORDS[AnalysisStage.awaiting_reflection][0]
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
            "what a result is compared against",
            "criterion",
        ):
            assert read in stops, read
        # Real-data finding 8: an agent added a comparison the design did not have.
        assert re.search(r"adds? or changes? what a result is compared against", stops)
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

    def auto_step(self) -> str:
        return section(_read_skill("analysis-reflection"), "### Step 1")

    def test_whether_a_result_is_on_record_comes_from_design_io(
        self, staged: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        step = self.auto_step()
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
        step = unwrap(self.auto_step())
        assert re.search(r"`stopped`[^.]*no result to reflect on", step)
        assert re.search(r"deriving a new design", step)


@pytest.fixture
def handed(tmp_path: Path) -> Path:
    """The synthetic theme whose last decision names three nodes, each with a design not yet run."""
    build(load_scenario("lib-handover"), tmp_path)
    return tmp_path


def _stages(insight: Path) -> dict[str, str]:
    nodes = tree_io.position("LIB", base_dir=insight)["nodes"]
    return {d["design_id"]: d["stage"] for node in nodes for d in node["designs"]}


class TestSeveralNodesGoThroughOneCheck:
    """Epic 35, Story 35.6: a decision that names several nodes is handed over together."""

    def _handover(self) -> str:
        return auto_step("### Step 3H:")

    def test_a_round_of_several_nodes_enters_the_hand_overauto_step(self) -> None:
        locate = unwrap(auto_step("### Step 1:"))
        assert re.search(r"more than one node[^.]*`node_ids`[^.]*Step 3H", locate)
        assert re.search(r"[Ss]tep 3H[^.]*several nodes", round_item("next round"))

    def test_every_item_names_the_designs_it_acts_on(self) -> None:
        """A resumed run goes through the items in order; each skips what it has nothing for."""
        heads = dict(
            re.findall(r"^\d+\. \*\*(.+?)\*\* \((.+?)\):", self._handover(), re.M)
        )
        assert list(heads) == HANDOVER
        named = " ".join(heads.values())
        for stage in set(AnalysisStage) - SETTLED:
            assert f"`{stage.value}`" in named, stage
        assert "`undesigned_node_ids`" in heads["briefs"]
        assert re.search(r"skipped when there are none", unwrap(self._handover()))

    def test_the_step_has_its_items_in_order(self) -> None:
        found = re.findall(r"^\d+\. \*\*(.+?)\*\*", self._handover(), re.MULTILINE)
        assert found == HANDOVER

    def test_the_check_is_a_keep_gate_asked_once_for_all_the_designs(self) -> None:
        _, keep, auto = table_row(auto_gates(), "check before handing over")
        assert keep.startswith("**")
        assert "Step 3H" in keep
        assert "`in_review`" in auto

    def test_every_node_without_a_design_gets_its_brief(self) -> None:
        """Decision 1 of the Story: all of them go into the one check."""
        item = handover_item("briefs")
        assert "`undesigned_node_ids`" in item
        assert "/analysis-framing {theme_id}" in item
        assert re.search(r"every node", item)

    def test_the_designs_are_saved_and_linked_before_the_check(self) -> None:
        """US-2 AC 1 (ADR-0063 1)."""
        item = handover_item("designs")
        assert "/analysis-design" in item
        assert "`in_review`" in item
        assert re.search(r"[Nn]o premortem[^.]*no data", item)
        assert re.search(r"one after another[^.]*never[^.]*parallel", item)
        assert re.search(r"four[^.]*beats[^.]*not asked", item)

    def test_a_design_handed_over_states_its_data_scope(self) -> None:
        """US-7 AC 2 (ADR-0066 3)."""
        assert "`data_scope`" in handover_item("designs")
        check = handover_item("check before handing over")
        assert re.search(r"`no_data_scope`[^.]*not empty[^.]*do not ask", check)

    def test_the_shown_commands_build_the_page_and_name_the_differing_rows(
        self, handed: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US-2 AC 1, ADR-0063 5: the path of the page and the rows the code marked."""
        check = self._handover()
        assert run_shown_line(check, "render", handed, monkeypatch) == 0
        assert run_shown_line(check, "handover", handed, monkeypatch) == 0
        item = handover_item("check before handing over")
        for name in ("`path`", "`differing`", "`label`", "`values`"):
            assert name in item, name
        assert re.search(r"[Nn]ever compare the values yourself", item)
        assert "分析を任せる前の確認" in item

    def test_the_shown_commands_record_a_comment_and_stop_a_design(
        self,
        handed: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """US-2 AC 5: a comment becomes a review comment of its design; one design is stopped."""
        check = handover_item_text("check before handing over")
        run_shown_design_commands(check, handed, monkeypatch, capsys)
        assert run_shown_design_line(check, "transition", handed) == 0
        # The item points at the one place that shows how an analysis is stopped.
        stopping = handover_part("#### Stopping an analysis")
        run_shown_design_commands(stopping, handed, monkeypatch, capsys)

        commented, stopped = "LIB-H03", "LIB-H05"
        batches = design_io.list_review_batches(commented, base_dir=handed)
        assert [c["comment"] for b in batches for c in b["comments"]] == [
            "粒度を本1冊にそろえてほしい"
        ]
        assert (
            design_io.load_design(commented, base_dir=handed)["status"] == "in_review"
        )
        assert _stages(handed)[stopped] == "stopped"
        assert tree_io.handover("LIB", base_dir=handed)["design_ids"] == [
            "LIB-H04",
            commented,
        ]

    def test_a_comment_and_a_stop_keep_the_analysts_words(self) -> None:
        item = handover_item("check before handing over")
        assert "分析を任せる前の確認へのコメント" in item
        assert re.search(r"comment[^.]*analyst's words", item)
        assert re.search(r"reason[^.]*analyst's words", item)
        assert re.search(r"ask(s)? (the check )?again", item)

    def test_premortem_runs_only_after_the_check(self) -> None:
        item = handover_item("premortem")
        assert "/premortem" in item
        assert "--target analyzing" in item
        assert re.search(r"`HARD_BLOCK`/`HIGH`[^.]*stop", item)

    def test_a_refused_move_into_the_analysis_goes_back_to_the_check(self) -> None:
        # Review: a confirmation without its criterion is refused, and the item said nothing.
        item = handover_item("premortem")
        assert re.search(
            r"exits non-zero[^.]*stderr[^.]*back to \*\*check before handing over\*\*",
            item,
        )

    def test_each_design_goes_to_its_own_execution_agent(self) -> None:
        item = handover_item("hand over")
        assert re.search(r"one execution agent[^.]*each design", item)
        assert "same message" in item

    def test_only_the_dialogue_agent_writes_the_shared_records(self) -> None:
        """US-5 AC 2 (ADR-0062 1, 2)."""
        step = unwrap(self._handover())
        assert re.search(
            r"dialogue agent[^.]*alone writes[^.]*tree[^.]*designs[^.]*HTML", step
        )
        brief = unwrap(
            section(self._handover(), "#### The brief of an execution agent")
        )
        assert re.search(r"only[^.]*notebook[^.]*verdict[^.]*journal", brief)
        assert re.search(r"[Nn]ever[^.]*`tree_io render`", brief)
        assert re.search(r"[Nn]ever[^.]*`design_io`", brief)
        assert re.search(r"never asks the analyst", brief)
        assert "ADR-0062" in step

    def test_a_running_analysis_no_agent_holds_is_handed_over_again(self) -> None:
        """Decision 3 of the Story: an execution agent does not outlive its conversation."""
        item = handover_item("premortem")
        assert re.search(r"did not start[^.]*in this conversation", item)
        assert re.search(r"hand it over again[^.]*tell the analyst", item)

    def test_an_agent_that_returned_without_a_result_is_not_started_again_unasked(
        self,
    ) -> None:
        item = handover_item("return")
        assert re.search(
            r"`running`[^.]*without a result\. Tell the analyst[^.]*only if they ask",
            item,
        )

    def test_a_round_whose_designs_all_stopped_still_gets_its_theme_reflection(
        self,
    ) -> None:
        item = handover_item("check before handing over")
        assert re.search(r"every design[^.]*stopped[^.]*\*\*theme reflection\*\*", item)


class TestTheAnalystMayChooseSeveralNodes:
    """US-1 AC 5: several nodes in one decision, none of which waits for another."""

    def _rule(self) -> str:
        return unwrap(
            framing_section("#### 4d:").split("**Several nodes in one decision.**")[1]
        )

    def test_the_rest_of_the_chosen_nodes_go_into_with_node_ids(self) -> None:
        assert '`"with_node_ids"`' in self._rule()

    def test_a_node_that_waits_for_another_is_left_out_and_the_analyst_is_told(
        self,
    ) -> None:
        rule = self._rule()
        assert "needs a result of another chosen node" in rule
        assert re.search(r"[Ll]eave it out of the decision", rule)
        assert re.search(r"tell the analyst which result", rule)
        assert re.search(r"write it nowhere", rule)

    def test_a_close_takes_no_other_node(self) -> None:
        assert re.search(r"`close`[^.]*none", self._rule())

    def test_the_first_choice_and_the_reflection_point_at_the_same_rule(self) -> None:
        for prose in (
            framing_section("#### 4b:"),
            section(_read_skill("analysis-reflection"), "### Step T7:"),
        ):
            assert "Several nodes in one decision" in unwrap(prose)

    def test_a_run_handed_the_position_takes_every_node_without_a_design(self) -> None:
        gate = unwrap(framing_section("#### 4d:"))
        assert re.search(r"`undesigned_node_ids`[^.]*as the answer", gate)
        assert re.search(r"Brief[^.]*each of them", gate)

    def test_a_round_resumed_halfway_still_gets_its_remaining_briefs(self) -> None:
        # Review: once one design is saved the state is in_progress, and the gate asked again.
        gate = unwrap(framing_section("#### 4d:"))
        assert re.search(
            r"`not_started`, or `in_progress` with `undesigned_node_ids` not empty",
            gate,
        )

    def test_the_gate_shows_every_node_the_decision_names(self) -> None:
        assert "`node_ids`" in unwrap(framing_section("#### 4d:"))
        step = unwrap(section(_read_skill("analysis-reflection"), "### Step T7:"))
        assert "`node_ids`" in step


class TestARoundWithoutAResult:
    """Decision 2 of the Story: every analysis of the round was stopped."""

    def _load(self) -> str:
        return unwrap(section(_read_skill("analysis-reflection"), "### Step T1:"))

    def test_the_reflection_reads_the_position(self) -> None:
        load = section(_read_skill("analysis-reflection"), "### Step T1:")
        assert re.search(r"tree_io position --theme", load)
        reference = section(
            _read_skill("analysis-reflection"), "## tree_io / tree_check"
        )
        assert table_row(reference, "`tree_io position --theme T`")

    def test_no_answer_is_written_and_the_analyst_is_asked_to_leave_them(self) -> None:
        load = self._load()
        assert re.search(r"every[^.]*`stopped`[^.]*no result", load)
        assert re.search(r"write no answer", load)
        assert "止めた理由" in load
        assert re.search(r"Step T6", load)


def _plan() -> str:
    """Item 4 of Step 1, where the analyst is told the plan of the round."""
    locate = auto_step("### Step 1:")
    return unwrap(locate[locate.index("4. Tell the analyst the plan") :])


def _in_order(text: str, words: list[str]) -> list[int]:
    at, found = 0, []
    for word in words:
        at = text.find(word, at)
        found.append(at)
    return found


class TestTheAnalystIsShownTheWay:
    """Real-data findings 4, 6, 7, 11 and 12 of Epic 35: the analyst lost the way."""

    def test_the_plan_of_a_round_of_several_nodes_names_its_steps_in_order(
        self,
    ) -> None:
        plan = _plan()
        several = plan[plan.index("A round of several nodes") :]
        steps = ["まとめて書", HANDOVER_HEADING, "並べて走らせ", "確認", "終わり方"]
        assert -1 not in _in_order(several, steps), steps

    def test_the_plan_of_several_nodes_is_told_once_the_nodes_are_chosen(
        self,
    ) -> None:
        plan = _plan()
        assert re.search(r"`closed`[^.]*not chosen", plan)
        assert re.search(
            r"[Rr]ight after the analyst chooses several nodes[^.]*4d", plan
        )
        assert re.search(r"Step 1, item 4", round_item("framing brief"))

    def test_the_page_stands_on_a_line_of_its_own_right_before_the_question(
        self,
    ) -> None:
        item = handover_item("check before handing over")
        assert re.search(
            r"`path`[^.]*line of its own[^.]*right before the question", item
        )
        assert "`open {path}`" in item

    def test_the_question_says_to_read_the_page_first(self) -> None:
        item = handover_item("check before handing over")
        assert f"先にページの「{HANDOVER_HEADING}」を開いて読んでから答える" in item

    def test_the_summary_of_differing_is_written_in_the_question(self) -> None:
        item = handover_item("check before handing over")
        assert re.search(r"summary of `differing`[^.]*in the question itself", item)

    def test_the_endings_name_the_notes_by_the_mark_on_the_page(self) -> None:
        item = handover_item("endings")
        assert f"「{AWAITING_MARK}」" in item
        assert re.search(r"page[^.]*as \*\*check before handing over\*\* does", item)


class TestTheReviewOfTheResultIsExplained:
    """Real-data finding 12 of Epic 35: what a review of the result does, and a suggestion."""

    def _ask(self) -> str:
        return unwrap(section(_read_skill("analysis-reflection"), "### Step 4:"))

    def test_the_reflection_says_what_the_review_does_before_asking(self) -> None:
        step = self._ask()
        assert (
            "Claude が notebook・verdict・図・分析設計を批評し、コメントを残す" in step
        )
        assert "結論の記録はレビューの後になる" in step
        assert "以後はレビューできない" in step

    def test_the_guide_suggests_by_the_form_and_the_analyst_decides(self) -> None:
        step = self._ask()
        guide = step[step.index("**The guide to a review of the result.**") :]
        assert re.search(r"confirmation[^.]*verdict[^.]*suggest taking", guide)
        assert re.search(r"exploration[^.]*usually[^.]*not", guide)
        assert re.search(r"added[^.]*the design does not have", guide)
        assert re.search(r"adds up[^.]*within the data", guide)
        assert re.search(r"[Tt]he analyst decides", guide)

    def test_the_endings_read_the_guide_and_do_not_copy_it(self) -> None:
        item = handover_item("endings")
        assert re.search(
            r"guide to a review of the result[^.]*`/analysis-reflection`", item
        )
        assert "批評し、コメントを残す" not in auto()


class TestAnAnswerChangesEveryFieldItTouches:
    """Real-data finding 9 of Epic 35: an old definition stayed in an explanatory variable."""

    def test_every_field_that_writes_the_same_definition_is_changed(self) -> None:
        item = handover_item("confirmation")
        assert re.search(r"[Ll]ist every field the answer touches", item)
        for field in (
            "`methodology.steps`",
            "`explanatory`",
            "`data_scope`",
            "`metrics`",
        ):
            assert field in item, field

    def test_the_fields_are_changed_before_premortem_runs_again(self) -> None:
        item = handover_item("confirmation")
        assert item.index("List every field the answer touches") < item.index(
            "back to **premortem**"
        )
        assert re.search(
            r"every field[^.]*changed[^.]*before[^.]*\*\*premortem\*\*", item
        )
