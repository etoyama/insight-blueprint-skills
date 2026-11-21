"""Structure tests for the question tree in the skills' prose (Epic 18 US-1, Story 18.2).

/analysis-framing creates the tree and /analysis-design links the design to its
node. Both live in SKILL.md prose, so these tests guard the load-bearing parts:
which tree_io commands the skills call, that the payloads they show are accepted
by the real tree_io, where the analyst is asked, and what the Framing Brief carries.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills._shown import run_shown_commands, run_shown_line
from tests.skills.test_skill_structure import _read_skill

_COMMAND = re.compile(r"(?<![\w/])tree_io ([a-z][a-z-]*)")


def _framing(heading: str) -> str:
    return section(_read_skill("analysis-framing"), heading)


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

    def test_a_theme_with_a_tree_leaves_4a_at_once(self) -> None:
        step = unwrap(_framing("#### 4a: "))
        assert "prints `{}`" in step
        assert "go to 4c now" in step


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
        step = unwrap(_framing("### Step 4: "))
        assert re.search(r"Do NOT create[^.]*`hypothesis_statement`", step)


class TestFramingWritesTheTreeThroughTreeIo:
    """US-1 AC 1, AC 2: create, add-node and decide, with payloads tree_io accepts."""

    def test_the_shown_commands_build_a_tree_with_a_start_decision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"

        ran = run_shown_commands(_framing("#### 5a: "), insight, monkeypatch)

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

    def test_a_failed_command_wrote_nothing_and_is_run_again(self) -> None:
        assert "non-zero" in unwrap(_framing("#### 5a: "))

    def test_the_brief_waits_for_the_start_decision(self) -> None:
        step = unwrap(_framing("#### 5a: "))
        assert (
            "Do not output the Framing Brief until the tree has a `start` decision"
            in step
        )

    def test_a_rerun_skips_what_the_tree_already_has(self) -> None:
        step = unwrap(_framing("#### 5a: "))
        rerun = re.search(r"[^.]*4c[^.]*skip `create`[^.]*\.", step)
        assert rerun, "no sentence says what a rerun skips"
        assert "`decide`" in rerun.group(0)


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
        run_shown_commands(_framing("#### 5a: "), insight, monkeypatch)

        ran = run_shown_commands(_framing("#### 4c: "), insight, monkeypatch)

        assert ran == ["revise-root"]
        revisions = tree_io.load_tree("LIB", base_dir=insight)["root_revisions"]
        assert [r["revision"] for r in revisions] == [1, 2]
        assert revisions[-1]["reason"]

    def test_the_analyst_is_asked_whether_to_raise_the_revision(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert "KEEP" in rerun
        assert "the old and the new root question and aim side by side" in rerun

    def test_a_tree_without_a_decision_goes_back_through_4b(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        unfinished = re.search(r"[^.]*no decision[^.]*\.", rerun)
        assert unfinished, "no sentence covers a tree without a decision"
        assert "4b" in unfinished.group(0)

    def test_the_revision_payload_is_complete(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert "the whole `aim`" in rerun
        assert re.search(r"`\"bump\": false`[^.]*no `reason`", rerun)

    def test_the_skill_never_picks_the_bump_itself(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert re.search(r"(?i)never[^.]*`bump`[^.]*yourself", rerun)

    def test_the_bump_question_gives_both_answers_and_what_each_does(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        asked = re.search(r"[^.]*both answers[^.]*\.", rerun)
        assert asked, "no sentence says how the bump question is put"
        assert "what each one does" in asked.group(0)

    def test_the_skill_holds_its_reading_until_the_analyst_answers(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert re.search(r"(?i)do not say which answer you expect", rerun)
        assert re.search(
            r"(?i)keep your reading[^.]*until the analyst has answered", rerun
        )
        assert re.search(r"(?i)do not ask for a `reason`[^.]*before", rerun)

    def test_the_reading_comes_out_only_after_a_no_on_a_change_of_meaning(self) -> None:
        rerun = unwrap(_framing("#### 4c: "))
        assert re.search(r"(?i)only then[^.]*which part changed", rerun)
        assert "ask once more" in rerun

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
        assert "printed in 5a" in brief
        assert "{theme_id}-Q{nn}" in brief


class TestDesignLinksItselfToTheNode:
    """US-1 AC 3: /analysis-design links the design it created to the Brief's node."""

    def test_the_brief_mapping_reads_the_node_id(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 1.5: ")
        assert "tree_io link" in table_row(step, "推奨方向.node_id")[2]

    def test_the_brief_mapping_covers_the_node_question(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 1.5: ")
        assert "`title`" in table_row(step, "推奨方向.論点")[1]

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
        code = run_shown_line(linking, "link", insight, monkeypatch)

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
        step = section(_read_skill("analysis-design"), "### Step 4: ")
        assert "question node it answers" in step


class TestSkillsCallOnlyCommandsTreeIoHas:
    """A command a skill names must exist, or the step fails at the analyst's desk."""

    @pytest.mark.parametrize(
        "skill",
        ["analysis-framing", "analysis-design", "analysis-reflection", "tree-upload"],
    )
    def test_every_named_command_exists(self, skill: str) -> None:
        named = set(_COMMAND.findall(_read_skill(skill)))

        assert named, f"{skill} names no tree_io command"
        for command in named:
            with pytest.raises(SystemExit) as exit_:
                tree_io._main([command, "--help"])
            assert exit_.value.code == 0, command


class TestFramingRendersTheTree:
    """Story 18.7: framing makes the HTML view; the model never writes it."""

    def test_the_shown_render_writes_the_html_next_to_the_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        run_shown_commands(_framing("#### 5a: "), insight, monkeypatch)
        step = _framing("#### 5c: ")
        assert re.search(r"^tree_io render --theme LIB$", step, re.M), (
            "5c shows no render command for the example theme"
        )
        code = run_shown_line(step, "render", insight, monkeypatch)

        assert code == 0
        assert (
            (insight / "themes" / "LIB_tree.html")
            .read_text()
            .startswith("<!doctype html>")
        )

    def test_the_render_follows_the_last_write_of_the_run(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        assert "after the last `tree_io` write of this run" in step
        assert "`revise-root`" in step

    def test_the_html_is_never_written_by_hand(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        by_hand = re.search(r"Never [^`]*`[^`]*_tree\.html`[^.]*\.", step)
        assert by_hand, "no sentence forbids writing the HTML by hand"
        assert "Write" in by_hand.group(0) and "Edit" in by_hand.group(0)

    def test_the_analyst_is_told_the_path_render_printed(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        assert "`path`" in step
        assert "論点ツリーの図" in step

    def test_a_failed_render_does_not_undo_the_tree(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        failed = re.search(r"[^.]*non-zero[^.]*\.", step)
        assert failed, "no sentence says what a failed render means"
        assert "the tree itself is written" in step

    def test_the_run_still_ends_on_the_design(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        assert step.rstrip().endswith('"仮説を設計するなら `/analysis-design`"')

    def test_framing_sends_the_html_nowhere(self) -> None:
        step = unwrap(_framing("#### 5c: "))
        assert "stays on this machine" in step
