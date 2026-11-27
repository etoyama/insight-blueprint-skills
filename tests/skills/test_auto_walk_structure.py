"""Structure tests for the walk of the question tree (Epic 18, Story 18.9).

/analysis-auto is the analyst's single entry: it builds the question tree of a
theme or resumes at the node the latest decision names, and walks one node per
round (US-8, ADR-0026). No Python test can drive the autopilot, so these tests
guard the load-bearing sentences of the SKILL.md files, and run the ``tree_io``
commands they show against the real library.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.skills._auto import round_item as _round_item
from tests.skills._markdown import section, table_row, table_rows, unwrap
from tests.skills._shown import run_shown_commands, run_shown_line
from tests.skills.test_skill_structure import (
    _extract_chaining_edges,
    _read_skill,
    parse_frontmatter,
    split_sections,
)

# The five gates US-8 AC 3 adds, by the first cell of their Gate policy row.
NEW_GATES = (
    "entry: a design without a tree",
    "framing ① root question and aim",
    "framing ② first node",
    "framing ③ root revision",
    "theme reflection",
)

# The rows of gates a delegated skill holds: the row names the gate and the
# step that holds it, and copies none of that step's logic (#143).
OWNED_GATES = {
    "framing ① root question and aim": "`/analysis-framing` 4a",
    "framing ② first node": "`/analysis-framing` 4b",
    "framing ③ root revision": "`/analysis-framing` 4c",
    "framing ④ next node": "`/analysis-framing` 4d",
    "theme reflection": "`/analysis-reflection {theme_id}` T3 + T7",
}

ROUND = [
    "framing brief",
    "design",
    "review",
    "premortem",
    "notebook",
    "journal",
    "reflection",
    "theme reflection",
    "next round",
]


def _auto() -> str:
    return _read_skill("analysis-auto")


def _gates() -> str:
    return split_sections(_auto())["Gate policy"]


def _step(heading: str) -> str:
    return section(_auto(), heading)


def _on_request(about: str) -> str:
    """The bullet under the round that the driver acts on only when the analyst asks."""
    walk = _step("### Step 3:")
    asked = walk[walk.index("only when the analyst asks") :]
    for bullet in re.split(r"^- ", asked, flags=re.MULTILINE)[1:]:
        if about in bullet:
            return unwrap(bullet)
    raise AssertionError(f"no on-request bullet about {about!r}")


def _framing(heading: str) -> str:
    return section(_read_skill("analysis-framing"), heading)


class TestTheThemeIsTheEntry:
    """US-8 AC 1: build the tree, or resume at the node of the latest decision."""

    def test_the_argument_is_a_theme_or_a_design(self) -> None:
        hint = parse_frontmatter(_auto())["argument-hint"]
        assert hint == "[theme_id | design_id]"

    def test_the_position_comes_from_tree_io_and_not_from_reading_the_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        locate = _step("### Step 1:")
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
        assert run_shown_line(locate, "position", insight, monkeypatch) == 0
        assert "never work the position out" in unwrap(locate).lower()

    def test_every_state_of_the_position_has_a_place_to_enter(self) -> None:
        rows = {cells[0] for cells in table_rows(_step("### Step 1:"))}
        for state in (
            "no_tree",
            "no_decision",
            "not_started",
            "in_progress",
            "concluded",
            "closed",
        ):
            assert f"`{state}`" in rows, state

    def test_the_unfinished_designs_are_read_on_every_node_the_decision_names(
        self,
    ) -> None:
        """Epic 35 US-1 AC 3: a decision may hand over several nodes (ADR-0061 5)."""
        rows = {cells[0]: cells[1] for cells in table_rows(_step("### Step 1:"))}
        for state in ("in_progress", "concluded"):
            assert "`node_ids`" in rows[f"`{state}`"], state
        assert "stopped" in rows["`in_progress`"]

    def test_an_analyzing_design_resumes_by_its_events_not_by_its_journal_file(
        self,
    ) -> None:
        # /analysis-design copies a heard answer into the journal before premortem,
        # so a journal file alone does not mean the analysis ran.
        resume = unwrap(_step("### Step 1:"))
        assert "other than `hearing`" in resume
        assert "`analyzing` with a journal" not in resume

    def test_no_tree_goes_to_framing(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert "/analysis-framing" in build
        assert "4a" in build and "4b" in build

    def test_a_research_theme_without_a_question_goes_to_rq_first(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert build.index("/rq-problematization") < build.index("**framing**")
        assert re.search(r"research[^.]*no research question", build)
        assert "RQ Brief" in build

    def test_it_does_not_ask_whether_the_theme_is_research(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert re.search(r"unclear[^.]*do not ask", build)

    def test_a_design_of_a_theme_without_a_tree_is_asked_once(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert "ツリーを作って巡回に入るか" in build
        assert re.search(r"theme that has a tree[^.]*never asked", build)
        assert "not stored" in build

    def test_carrying_one_design_skips_the_tree_steps(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert re.search(r"only this design[^.]*items 2[–-]7", build)

    def test_the_position_is_read_again_once_the_tree_is_built(self) -> None:
        # Review: a design placed in 4b was skipped and its node designed anew.
        build = unwrap(_step("### Step 2:"))
        assert re.search(r"read `tree_io position` again[^.]*its `state`", build)
        item = _round_item("framing brief")
        assert "`not_started`" in item and "`closed`" in item
        assert "Right after Step 2" not in item

    def test_a_position_that_cannot_be_read_stops_the_run(self) -> None:
        locate = unwrap(_step("### Step 1:"))
        assert re.search(r"exits non-zero[^.]*stop", locate)

    def test_a_design_no_node_holds_is_placed_before_it_is_carried(self) -> None:
        locate = unwrap(_step("### Step 1:"))
        assert re.search(
            r"no node of the tree holds it[^.]*Designs no node holds", locate
        )

    def test_never_cd_before_an_io_command(self) -> None:
        locate = unwrap(_step("### Step 1:"))
        assert re.search(r"[Nn]ever `cd`[^.]*`\*_io`", locate)


class TestOneRound:
    """US-8 AC 2: a round runs from the design of a node to the tree decision."""

    def test_the_round_has_its_steps_in_order(self) -> None:
        walk = _step("### Step 3:")
        found = re.findall(r"^\d+\. \*\*(.+?)\*\*", walk, re.MULTILINE)
        assert found == ROUND

    def test_the_theme_reflection_follows_the_reflection(self) -> None:
        item = _round_item("theme reflection")
        assert "/analysis-reflection {theme_id}" in item

    def test_a_later_round_gets_its_framing_brief_from_framing(self) -> None:
        item = _round_item("framing brief")
        assert "/analysis-framing {theme_id}" in item
        assert "`tree_io position`" in item

    def test_the_design_is_linked_to_the_node_of_the_brief(self) -> None:
        item = _round_item("design")
        assert "`node_id`" in item
        assert "unlinked" in item


class TestGates:
    """US-8 AC 3: the analyst is asked at KEEP gates only, and five are new."""

    @pytest.mark.parametrize("step", NEW_GATES)
    def test_the_five_new_gates_are_keep_gates(self, step: str) -> None:
        _, keep, _auto_cell = table_row(_gates(), step)
        assert keep.startswith("**"), keep

    def test_the_entry_gate_asks_whether_to_build_a_tree(self) -> None:
        _, keep, _auto_cell = table_row(_gates(), "entry: a design without a tree")
        assert "whether to build a tree" in keep

    def test_the_rest_of_a_delegated_skill_follows_it_as_written(self) -> None:
        # Thermos on #170: the note must not silence the skill's other questions.
        gates = unwrap(_gates())
        assert "rest of that skill follows it as written" in gates
        assert "runs without asking" not in gates

    @pytest.mark.parametrize("step", OWNED_GATES)
    def test_a_gate_of_a_delegated_skill_points_at_its_step_only(
        self, step: str
    ) -> None:
        _, keep, auto = table_row(_gates(), step)
        assert keep == f"**{OWNED_GATES[step]}**"
        assert auto == "—"

    def test_the_skills_own_gates_are_listed_and_the_driver_adds_no_question(
        self,
    ) -> None:
        for step in ("rq-problematization", "tree-upload"):
            _, keep, _auto_cell = table_row(_gates(), step)
            assert keep.startswith("**"), step
        assert "no question of its own" in table_row(_gates(), "tree-upload")[1]

    def test_the_driver_asks_nothing_outside_the_table(self) -> None:
        assert "Ask the analyst nothing outside the KEEP column" in unwrap(_gates())


class TestTheDecisionSeesTheTree:
    """US-8 AC 4, as Epic 29 left it: the walk writes no report, so the decision sees the tree."""

    def test_the_decision_is_asked_with_the_tree_in_view(self) -> None:
        item = _round_item("theme reflection")
        assert "path of the tree's HTML" in item
        assert "report" not in item
        assert "T7" in item


class TestTheWalkGoesOnUntilTheAnalystStops:
    """US-8 AC 5: rounds repeat until a close or a stop; every skill still stands alone."""

    def test_deepen_and_return_start_the_next_round(self) -> None:
        item = _round_item("next round")
        assert re.search(r"`deepen` or (a )?`return`[^.]*item 1", item)

    def test_the_next_round_starts_without_a_summary_in_between(self) -> None:
        # Manual check, 2026-11-21: after a `return` the driver summarized and stopped.
        item = _round_item("next round")
        assert "in the same turn" in item
        assert re.search(r"[Dd]o not summarize", item)
        assert re.search(r"never tell the analyst to run `/analysis-auto` again", item)

    def test_close_and_stop_end_the_walk(self) -> None:
        item = _round_item("next round")
        assert re.search(r"`close`[^.]*Step 4", item)
        assert re.search(r"stop[^.]*Step 4", item)

    def test_the_summary_says_where_the_next_run_resumes(self) -> None:
        summary = unwrap(_step("### Step 4:"))
        assert "HTML" in summary
        assert "resumes" in summary

    def test_the_tree_is_handed_over_only_when_the_analyst_asks(self) -> None:
        asked = _on_request("hand the tree over")
        assert "/tree-upload {theme_id}" in asked
        assert "do not ask whether to send" in asked.lower()
        assert "Never start it unasked" in asked
        assert "ADR-0016" in asked

    def test_a_changed_root_goes_back_to_framing(self) -> None:
        asked = _on_request("root question or the aim")
        assert "/analysis-framing {theme_id}" in asked
        assert "The root question or the aim" in asked

    def test_the_driver_never_writes_the_tree(self) -> None:
        text = _auto()
        for write in ("create", "add-node", "decide", "answer", "hear", "link"):
            assert f"tree_io {write}" not in text, write

    def test_the_delegated_skills_stay_explicit(self) -> None:
        delegated = unwrap(split_sections(_auto())["Delegated skills"])
        for skill in ("/rq-problematization", "/analysis-framing", "/tree-upload"):
            assert f"`{skill}`" in delegated
        assert "explicit-invocable on its own" in delegated

    @pytest.mark.parametrize(
        "target", ["rq-problematization", "analysis-framing", "tree-upload"]
    )
    def test_the_chaining_points_both_ways(self, target: str) -> None:
        edge = ("analysis-auto", target)
        assert edge in _extract_chaining_edges("analysis-auto")
        assert edge in _extract_chaining_edges(target)


class TestTheDriverReadsTheSkillsItDrives:
    """ADR-0005: the skills stay explicit, so the driver follows their files itself.

    The Skill tool refuses a ``disable-model-invocation`` skill. A driver that
    tries it stops and asks the analyst to type every command (manual check,
    2026-11-21).
    """

    def _how(self) -> str:
        return unwrap(split_sections(_auto())["How the driver runs a skill"])

    def test_it_reads_the_skill_file_instead_of_calling_the_skill_tool(self) -> None:
        how = self._how()
        assert "`${CLAUDE_PLUGIN_ROOT}/skills/{skill-name}/SKILL.md`" in how
        assert "Never search the disk" in how
        assert re.search(r"[Nn]ever call the Skill tool", how)

    def test_it_does_not_hand_the_command_back_to_the_analyst(self) -> None:
        assert re.search(r"never ask the analyst to type", self._how())

    def test_the_run_is_the_explicit_invocation(self) -> None:
        how = self._how()
        assert "disable-model-invocation: true" in how
        assert "ADR-0005" in how

    def test_the_io_commands_are_called_by_name(self) -> None:
        assert re.search(r"on PATH[^.]*by name", self._how())

    def test_variables_in_a_read_file_are_read_as_their_values(self) -> None:
        # A file that is Read is not loaded as a skill: the host fills in neither variable.
        how = self._how()
        assert re.search(r"`CLAUDE_PLUGIN_ROOT`[^.]*plugin root", how)
        assert "before `/skills/`" in how
        assert re.search(r"`ARGUMENTS`[^.]*value you hand", how)
        assert "the shell does not have the variable" in how

    def test_the_driver_names_the_variables_without_writing_them(self) -> None:
        # Written out, the host would replace them in this very sentence.
        text = _auto()
        assert "$ARGUMENTS" not in text
        assert text.count("${CLAUDE_PLUGIN_ROOT}") == 1

    def test_every_driven_skill_has_its_file(self) -> None:
        delegated = split_sections(_auto())["Delegated skills"]
        names = set(re.findall(r"`/([a-z-]+)`", delegated))
        chained = {to for _, to in _extract_chaining_edges("analysis-auto")}
        assert chained <= names
        root = Path(__file__).resolve().parents[2] / "skills"
        for name in names:
            assert (root / name / "SKILL.md").is_file(), name


class TestFramingPlacesExistingDesigns:
    """US-8 AC 1: the analyst decides which node each existing design belongs to."""

    def test_the_gate_asks_where_each_design_belongs(self) -> None:
        gate = unwrap(_framing("#### 4b:"))
        assert re.search(r"designs of this theme[^.]*no node", gate)
        assert re.search(r"which node[^.]*belongs", gate)
        assert re.search(r"[Nn]ever place", gate)

    def test_the_shown_link_ties_an_existing_design_to_its_node(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        design_io.create_design(
            theme_id="LIB",
            title="Test",
            hypothesis_statement="X improves Y",
            hypothesis_background="because Z",
            methodology={"method": "OLS"},
            base_dir=insight,
        )
        writing = _framing("#### 5a:")
        run_shown_commands(writing, insight, monkeypatch)

        assert run_shown_line(writing, "link", insight, monkeypatch) == 0
        linked = tree_io.load_tree("LIB", insight)["nodes"][1]["design_ids"]
        assert linked == ["LIB-H01"]

    def test_a_rerun_places_the_designs_no_node_holds(self) -> None:
        rerun = unwrap(_framing("#### 4c:"))
        assert re.search(r"[Dd]esigns no node holds[^.]*4b", rerun)


class TestFramingTakesTheDecisionAsTheAnswerInsideAuto:
    """Inside the walk, a node decided and not designed since is not asked for twice."""

    def _gate(self) -> str:
        return unwrap(_framing("#### 4d:"))

    def test_the_exception_needs_the_position_it_was_handed(self) -> None:
        # #143: framing keys the exception on its input, not on who called it.
        gate = self._gate()
        assert re.search(r"handed the output of `tree_io position", gate)
        assert "`not_started`" in gate
        assert "/analysis-auto" not in gate

    def test_the_decision_is_the_answer_and_nothing_is_written(self) -> None:
        gate = self._gate()
        assert re.search(r"do not ask again[^.]*write no decision", gate)

    def test_the_exception_covers_only_the_question_about_the_node(self) -> None:
        # Review: skipping all of 4c also skipped placing a design no node holds.
        gate = self._gate()
        assert re.search(r"[Dd]esigns no node holds are still placed", gate)

    def test_the_steps_before_4d_point_at_the_exception(self) -> None:
        # Thermos on #170: 4a and 4c ask before a reader reaches the end of 4d.
        dialogue = unwrap(_framing("### Step 4:").split("#### 4a:")[0])
        assert re.search(r"handed the position[^.]*end of 4d[^.]*4a[^.]*4c", dialogue)

    def test_every_other_case_still_asks(self) -> None:
        gate = self._gate()
        assert re.search(r"any other state[^.]*ask", gate)
        assert re.search(r"not handed the position[^.]*ask", gate)
