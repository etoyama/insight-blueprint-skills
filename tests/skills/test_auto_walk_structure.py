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
from tests.skills._markdown import section, table_row, table_rows, unwrap
from tests.skills._shown import run_shown_commands, run_shown_line
from tests.skills.test_skill_structure import (
    _extract_chaining_edges,
    _read_skill,
    parse_frontmatter,
    split_sections,
)

# The five gates US-8 AC 3 adds, by the first cell of their Gate policy row.
NEW_GATES = {
    "entry: a design without a tree": "whether to build a tree",
    "framing ① root question and aim": "root question",
    "framing ② first node": "first node to investigate",
    "framing ③ root revision": "root revision",
    "theme reflection": "tree decision",
}

ROUND = [
    "framing brief",
    "design",
    "review",
    "premortem",
    "notebook",
    "journal",
    "reflection",
    "report",
    "upload",
    "theme reflection",
    "next round",
]


def _auto() -> str:
    return _read_skill("analysis-auto")


def _gates() -> str:
    return split_sections(_auto())["Gate policy"]


def _step(heading: str) -> str:
    return section(_auto(), heading)


def _round_item(name: str) -> str:
    """The numbered item ``N. **name**`` of the round, up to the next item or heading."""
    found = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,4}} |\Z)",
        _step("### Step 3:"),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"the round has no '{name}' item"
    return unwrap(found.group(0))


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
        assert "ツリーを作って巡回に入るか、この分析設計だけを流すか" in build
        assert re.search(r"theme that has a tree[^.]*never asked", build)
        assert "not stored" in build

    def test_carrying_one_design_skips_the_tree_steps(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert re.search(r"only this design[^.]*items 2[–-]9", build)

    def test_framing_places_the_designs_that_already_exist(self) -> None:
        build = unwrap(_step("### Step 2:"))
        assert re.search(r"existing designs[^.]*4b", build)

    def test_never_cd_before_an_io_command(self) -> None:
        locate = unwrap(_step("### Step 1:"))
        assert re.search(r"[Nn]ever `cd`[^.]*`\*_io`", locate)


class TestOneRound:
    """US-8 AC 2: a round runs from the design of a node to the tree decision."""

    def test_the_round_has_its_steps_in_order(self) -> None:
        walk = _step("### Step 3:")
        found = re.findall(r"^\d+\. \*\*(.+?)\*\*", walk, re.MULTILINE)
        assert found == ROUND

    def test_the_theme_reflection_follows_the_report_and_the_upload(self) -> None:
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
        assert NEW_GATES[step] in keep

    def test_the_text_names_the_five(self) -> None:
        gates = unwrap(_gates())
        assert "Five gates are new with the question tree" in gates

    def test_the_framing_gates_point_at_their_steps(self) -> None:
        for step, where in (
            ("framing ① root question and aim", "4a"),
            ("framing ② first node", "4b"),
            ("framing ③ root revision", "4c"),
            ("framing ④ next node", "4d"),
        ):
            assert where in table_row(_gates(), step)[1], step

    def test_the_decided_node_is_not_asked_again(self) -> None:
        _, keep, auto = table_row(_gates(), "framing ④ next node")
        assert "`closed`" in keep
        assert "`not_started`" in auto

    def test_the_skills_own_gates_are_listed_and_the_driver_adds_no_question(
        self,
    ) -> None:
        for step in ("rq-problematization", "tree-upload"):
            _, keep, _auto_cell = table_row(_gates(), step)
            assert keep.startswith("**"), step
        assert "no question of its own" in table_row(_gates(), "tree-upload")[1]

    def test_the_driver_asks_nothing_outside_the_table(self) -> None:
        assert "Ask the analyst nothing outside the KEEP column" in unwrap(_gates())


class TestTheReportIsWrittenWithoutAsking:
    """US-8 AC 4: a concluded design gets its report unasked; the decision sees both paths."""

    def test_the_report_gate_moved_to_auto(self) -> None:
        _, keep, auto = table_row(_gates(), "report")
        assert keep == "—"
        assert "/analysis-report" in auto
        assert "terminal status" in auto

    def test_the_report_item_does_not_ask(self) -> None:
        item = _round_item("report")
        assert "without asking" in item
        assert "offer" not in item.lower()

    def test_a_round_without_a_conclusion_writes_no_report(self) -> None:
        item = _round_item("report")
        assert re.search(r"not in a terminal status[^.]*no report", item)

    def test_the_decision_is_asked_with_both_paths(self) -> None:
        item = _round_item("theme reflection")
        assert re.search(r"report's path[^.]*HTML", item)
        assert "T7" in item

    def test_the_driver_never_decides_for_the_analyst(self) -> None:
        item = _round_item("theme reflection")
        assert re.search(r"[Nn]ever choose[^.]*kind", item)


class TestTheWalkGoesOnUntilTheAnalystStops:
    """US-8 AC 5: rounds repeat until a close or a stop; every skill still stands alone."""

    def test_deepen_and_return_start_the_next_round(self) -> None:
        item = _round_item("next round")
        assert re.search(r"`deepen` or (a )?`return`[^.]*item 1", item)

    def test_close_and_stop_end_the_walk(self) -> None:
        item = _round_item("next round")
        assert re.search(r"`close`[^.]*Step 4", item)
        assert re.search(r"stop[^.]*Step 4", item)

    def test_the_summary_says_where_the_next_run_resumes(self) -> None:
        summary = unwrap(_step("### Step 4:"))
        assert "HTML" in summary
        assert "resumes" in summary

    def test_the_tree_is_handed_over_only_when_the_analyst_asks(self) -> None:
        walk = unwrap(_step("### Step 3:"))
        asked = walk[walk.index("/tree-upload {theme_id}") - 300 :]
        assert "asks" in asked
        assert "do not ask whether to send" in asked.lower()
        assert "ADR-0016" in asked

    def test_a_changed_root_goes_back_to_framing(self) -> None:
        walk = unwrap(_step("### Step 3:"))
        assert re.search(r"root question or the aim[^.]*/analysis-framing", walk)

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

    def test_the_exception_needs_the_position_from_the_driver(self) -> None:
        gate = self._gate()
        assert "/analysis-auto" in gate
        assert "`tree_io position --theme {theme_id}`" in gate
        assert "`not_started`" in gate

    def test_the_decision_is_the_answer_and_nothing_is_written(self) -> None:
        gate = self._gate()
        assert re.search(r"do not ask again[^.]*write no decision", gate)

    def test_every_other_case_still_asks(self) -> None:
        gate = self._gate()
        assert re.search(r"any other state[^.]*ask", gate)
        assert re.search(r"started on its own[^.]*ask", gate)
