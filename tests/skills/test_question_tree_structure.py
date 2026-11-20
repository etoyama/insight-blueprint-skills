"""Structure tests for the question tree in the skills' prose (Epic 18 US-1, Story 18.2).

/analysis-framing creates the tree and /analysis-design links the design to its
node. Both live in SKILL.md prose, so these tests guard the load-bearing parts:
which tree_io commands the skills call, that the payloads they show are accepted
by the real tree_io, where the analyst is asked, and what the Framing Brief carries.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill

_PIPED = re.compile(r"echo '(?P<payload>\{.*?\})' \| tree_io (?P<args>[^\n]+)", re.S)
_COMMAND = re.compile(r"(?<![\w/])tree_io ([a-z][a-z-]*)")


def _framing(heading: str) -> str:
    return section(_read_skill("analysis-framing"), heading)


def _run_shown_commands(
    prose: str, insight: Path, monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    """Run every ``echo '<json>' | tree_io ...`` shown in *prose* against *insight*."""
    ran: list[str] = []
    for shown in _PIPED.finditer(prose):
        args = shown["args"].split()
        monkeypatch.setattr("sys.stdin", io.StringIO(shown["payload"]))
        assert tree_io._main([*args, "--base-dir", str(insight)]) == 0, shown[0]
        ran.append(args[0])
    return ran


class TestFramingSettlesTheRootQuestionAndTheAim:
    """US-1 AC 1, AC 4: the root question and the aim are the analyst's call."""

    def test_the_analyst_decides_the_root_question_and_the_aim(self) -> None:
        step = unwrap(_framing("#### 4a: "))
        assert "root question" in step and "aim" in step
        assert "KEEP" in step

    def test_a_business_aim_is_who_decides_what(self) -> None:
        step = _framing("#### 4a: ")
        assert "`decision_maker`" in step and "`decision`" in step

    def test_a_research_aim_is_the_audience_and_the_claim_scope(self) -> None:
        step = _framing("#### 4a: ")
        assert "`audience`" in step and "`claim_scope`" in step

    def test_the_audience_is_asked_when_the_rq_brief_has_none(self) -> None:
        step = unwrap(_framing("#### 4a: "))
        asked = re.search(r"[^.]*RQ Brief[^.]*audience[^.]*\.", step)
        assert asked, "no sentence ties the RQ Brief to the audience"
        assert "ask" in asked.group(0).lower()

    def test_the_aim_is_never_filled_with_a_placeholder(self) -> None:
        assert "placeholder" in unwrap(_framing("#### 4a: "))

    def test_the_theme_id_is_settled_before_the_tree_is_written(self) -> None:
        step = _framing("#### 4a: ")
        assert "`theme_id`" in step
        assert "tree_io get --theme" in step


class TestFramingLaysOutTheFirstLevel:
    """US-1 AC 1, AC 2: first-level nodes with a contribution; one is chosen first."""

    def test_each_node_has_a_question_and_a_contribution(self) -> None:
        step = unwrap(_framing("#### 4b: "))
        assert "first-level" in step
        assert "question" in step and "contribution" in step

    def test_the_analyst_chooses_the_first_node_with_a_reason(self) -> None:
        step = unwrap(_framing("#### 4b: "))
        assert "KEEP" in step
        assert "reason" in step

    def test_the_second_level_may_stay_empty(self) -> None:
        assert "second level" in unwrap(_framing("#### 4b: "))

    def test_no_hypothesis_statement_is_written(self) -> None:
        assert "hypothesis_statement" in _framing("### Step 4: ")


class TestFramingWritesTheTreeThroughTreeIo:
    """US-1 AC 1, AC 2: create, add-node and decide, with payloads tree_io accepts."""

    def test_the_shown_commands_build_a_tree_with_a_start_decision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"

        ran = _run_shown_commands(_framing("#### 5a: "), insight, monkeypatch)

        assert ran == ["create", "add-node", "decide"]
        tree = tree_io.load_tree("LIB", base_dir=insight)
        root, first = tree["nodes"]
        assert root["question"] == tree["root_revisions"][0]["question"]
        assert first["parent_question_id"] == root["id"]
        assert first["contribution"]
        (decision,) = tree["decisions"]
        assert (decision["kind"], decision["node_id"]) == ("start", first["id"])
        assert decision["reason"]

    def test_the_file_is_never_written_by_hand(self) -> None:
        step = unwrap(_framing("#### 5a: "))
        assert "_tree.yaml" in step
        by_hand = re.search(r"Never [^`]*`[^`]*_tree\.yaml`[^.]*\.", step)
        assert by_hand, "no sentence forbids writing the tree file by hand"
        assert "Write" in by_hand.group(0) and "Edit" in by_hand.group(0)

    def test_a_failed_command_stops_the_brief(self) -> None:
        assert "non-zero" in unwrap(_framing("#### 5a: "))


class TestFramingAsksBeforeTheRootChanges:
    """US-1 AC 5: on a rerun, the analyst decides whether the root revision goes up."""

    def test_an_existing_tree_is_shown_instead_of_created_again(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert "already" in rerun
        assert "tree_io create" not in rerun

    def test_the_shown_revision_is_accepted_by_tree_io(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _run_shown_commands(_framing("#### 5a: "), insight, monkeypatch)

        ran = _run_shown_commands(_framing("#### 4c: "), insight, monkeypatch)

        assert ran == ["revise-root"]
        revisions = tree_io.load_tree("LIB", base_dir=insight)["root_revisions"]
        assert [r["revision"] for r in revisions] == [1, 2]
        assert revisions[-1]["reason"]

    def test_the_analyst_is_asked_whether_to_raise_the_revision(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert "KEEP" in rerun
        assert "old" in rerun and "new" in rerun

    def test_the_skill_never_picks_the_bump_itself(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert re.search(r"(?i)never[^.]*`bump`[^.]*yourself", rerun)

    def test_a_change_of_meaning_always_raises_the_revision(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        kept = re.search(r"`\"bump\": false`[^.]*\.", rerun)
        assert kept, "no sentence says when bump may be false"
        assert "only" in kept.group(0) and "rewording" in kept.group(0)
        assert "earlier answers" in rerun


class TestFramingBriefNamesTheNode:
    """US-1 AC 3: the Framing Brief carries the theme and the first node."""

    def test_recommended_direction_has_the_theme_and_the_node(self) -> None:
        direction = section(_framing("#### 5b: "), "### 推奨方向")
        assert "- theme_id: " in direction
        assert "- node_id: " in direction

    def test_the_node_id_is_the_one_tree_io_returned(self) -> None:
        brief = unwrap(_framing("#### 5b: "))
        assert "tree_io add-node" in brief or "5a" in brief
        assert "{theme_id}-Q{nn}" in brief


class TestDesignLinksItselfToTheNode:
    """US-1 AC 3: /analysis-design links the design it created to the Brief's node."""

    def test_the_brief_mapping_reads_the_node_id(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 1.5: ")
        assert "tree_io link" in table_row(step, "推奨方向.node_id")[2]

    def test_the_shown_link_is_accepted_by_tree_io(
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
        design_io.create_design(
            theme_id="FP",
            title="Test",
            hypothesis_statement="X improves Y",
            hypothesis_background="because Z",
            methodology={"method": "OLS"},
            base_dir=insight,
        )
        linking = section(_read_skill("analysis-design"), "#### Link the design")
        shown = re.search(r"^tree_io (link [^\n]+)$", linking, re.M)
        assert shown, "no tree_io link command is shown"
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        code = tree_io._main([*shown.group(1).split(), "--base-dir", str(insight)])

        assert code == 0
        nodes = {n["id"]: n for n in tree_io.load_tree("FP", base_dir=insight)["nodes"]}
        assert nodes["FP-Q02"]["design_ids"] == ["FP-H01"]

    def test_the_link_comes_after_the_design_is_created(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 3: ")
        assert step.index("design_io create") < step.index("#### Link the design")

    def test_a_brief_without_a_node_creates_the_design_unlinked(self) -> None:
        linking = unwrap(
            section(_read_skill("analysis-design"), "#### Link the design")
        )
        assert re.search(r"no `node_id`[^.]*skip", linking)

    def test_a_changed_theme_is_not_linked_to_the_node(self) -> None:
        linking = unwrap(
            section(_read_skill("analysis-design"), "#### Link the design")
        )
        assert "another theme" in linking

    def test_the_design_never_creates_a_node(self) -> None:
        linking = unwrap(
            section(_read_skill("analysis-design"), "#### Link the design")
        )
        assert re.search(r"(?i)never[^.]*`tree_io add-node`", linking)

    def test_the_linked_node_is_shown_at_the_end(self) -> None:
        assert "node" in section(_read_skill("analysis-design"), "### Step 4: ")


class TestSkillsCallOnlyCommandsTreeIoHas:
    """A command a skill names must exist, or the step fails at the analyst's desk."""

    @pytest.mark.parametrize("skill", ["analysis-framing", "analysis-design"])
    def test_every_named_command_exists(self, skill: str) -> None:
        source = Path(tree_io.__file__).read_text(encoding="utf-8")
        choices = re.search(r"choices=\[(.*?)\]", source, re.S)
        assert choices
        known = set(json.loads(f"[{choices.group(1).rstrip().rstrip(',')}]"))

        named = set(_COMMAND.findall(_read_skill(skill)))

        assert named, f"{skill} names no tree_io command"
        assert named <= known
