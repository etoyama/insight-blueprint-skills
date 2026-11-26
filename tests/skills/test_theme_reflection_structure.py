"""Structure tests for the theme reflection in /analysis-reflection (Epic 18, Story 18.4).

Given a theme, the skill writes the current answer of each node across the
designs of the theme (US-3 AC 1-3) and lets none reach the analyst before the
tree check passes (US-4 AC 2). The steps live in SKILL.md prose, so these tests
guard the load-bearing parts: which commands the skill calls, that the payload
it shows is accepted by the real tree_io, and what it does with a violation.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import get_args

import pytest

from insight_blueprint.models.tree import Progress
from skills._shared import design_io, tree_check, tree_io
from skills._shared._atomic import atomic_write_yaml
from skills._shared.tree_words import BELOW_WORDS, PROGRESS_WORDS
from tests.skills._markdown import section, table_row, unwrap
from tests.skills._shown import PIPED
from tests.skills.test_skill_structure import _read_skill

_COMMAND = re.compile(r"(?<![\w/])tree_(io|check) ([a-z][a-z-]*|--theme)")


def _skill() -> str:
    return _read_skill("analysis-reflection")


def _step(heading: str) -> str:
    return unwrap(section(_skill(), heading))


def _library(insight: Path) -> None:
    """LIB-Q02 under the root, linked to LIB-H01, whose journal holds one event."""
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
    tree_io.add_node(
        "LIB",
        question="期限切れを一貫して数えられるか",
        parent_question_id="LIB-Q01",
        contribution="予約取消が混ざると、延長で改善しうる件数が変わる",
        base_dir=insight,
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
    atomic_write_yaml(
        insight / "designs" / "LIB-H01_journal.yaml",
        {
            "design_id": "LIB-H01",
            "events": [
                {
                    "id": "LIB-H01-E01",
                    "type": "evidence",
                    "content": "状態の履歴から取消を除くと、期限切れは152件だった",
                    "metadata": {"direction": "supports"},
                }
            ],
        },
    )


class TestReflectionTakesAThemeOrADesign:
    """Scope of Epic 18: the reflection on one design stays as it was."""

    def test_the_argument_is_a_design_or_a_theme(self) -> None:
        assert 'argument-hint: "[design_id | theme_id]"' in _skill()

    def test_a_theme_id_starts_the_theme_reflection(self) -> None:
        mode = _step("### Step 0: ")
        assert "`{theme_id}-H{nn}`" in mode
        assert "Theme Reflection" in mode

    def test_the_design_reflection_keeps_its_steps(self) -> None:
        skill = _skill()
        for heading in (
            "### Step 1: Load Design + Journal",
            "### Step 3: Guided Reflection (3 Questions)",
            "### Step 4: Record Conclusion",
        ):
            assert heading in skill

    def test_a_journal_with_only_a_heard_answer_is_not_reflected_on(self) -> None:
        # The heard answer is copied in before the analysis runs (/analysis-design).
        load = _step("### Step 1: ")
        assert "other than `hearing`" in load

    def test_a_theme_without_a_tree_is_sent_to_framing(self) -> None:
        load = _step("### Step T1: ")
        assert "`tree_io get --theme {theme_id}`" in load
        assert "/analysis-framing" in load


class TestThemeReflectionWritesCitedAnswers:
    """US-3 AC 1: per node, statements with a kind and one or more cited events."""

    def test_it_reads_the_journal_of_every_linked_design(self) -> None:
        load = _step("### Step T1: ")
        assert "`design_ids`" in load
        assert "_journal.yaml" in load

    @pytest.mark.parametrize(
        ("kind", "label"),
        [
            ("claim", "これまでわかっていること"),
            ("undetermined", "まだ決められないこと"),
            ("weakening", "注意すべきこと"),
        ],
    )
    def test_each_kind_of_statement_is_explained(self, kind: str, label: str) -> None:
        row = table_row(section(_skill(), "### Step T2: "), f"`{kind}`")
        assert label in row[1]

    def test_every_statement_cites_an_event(self) -> None:
        write = _step("### Step T2: ")
        assert "Every statement cites one or more journal events" in write
        assert "A sentence you cannot cite is not written" in write

    def test_a_node_without_events_gets_no_answer(self) -> None:
        assert "no journal event" in _step("### Step T2: ")


class TestParentAnswersCiteDescendants:
    """US-3 AC 2: never inferred from how many children are done."""

    def test_a_parent_cites_the_events_of_its_descendants_designs(self) -> None:
        write = _step("### Step T2: ")
        assert "designs linked to the nodes below it" in write

    def test_a_parent_is_never_answered_from_progress(self) -> None:
        write = _step("### Step T2: ")
        never = re.search(r"Never [^.]*progress[^.]*\.", write)
        assert never, "no sentence forbids answering a parent from progress"
        assert "count" in never.group(0)

    def test_a_child_answer_is_not_a_source(self) -> None:
        assert "not the answer of a child" in _step("### Step T2: ")


class TestAnswersGoThroughTreeIo:
    """US-3 AC 3: append-only, with the round and the root revision tree_io sets."""

    def test_the_shown_command_writes_the_first_round(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)
        (shown,) = PIPED.finditer(section(_skill(), "### Step T3: "))
        monkeypatch.setattr("sys.stdin", io.StringIO(shown["payload"]))

        code = tree_io._main([*shown["args"].split(), "--base-dir", str(insight)])

        assert code == 0
        nodes = {n["id"]: n for n in tree_io.load_tree("LIB", insight)["nodes"]}
        (answer,) = nodes["LIB-Q02"]["answers"]
        assert (answer["round"], answer["root_revision"]) == (1, 1)
        assert tree_check.check_theme("LIB", insight) == []

    def test_one_call_carries_every_node_of_the_reflection(self) -> None:
        assert "one call" in _step("### Step T3: ")

    def test_the_skill_never_sets_the_round_itself(self) -> None:
        write = _step("### Step T3: ")
        assert "`tree_io` sets `round` and `root_revision`" in write

    def test_the_file_is_never_written_by_hand(self) -> None:
        by_hand = re.search(
            r"Never [^`]*`[^`]*_tree\.yaml`[^.]*\.", _step("### Step T3: ")
        )
        assert by_hand, "no sentence forbids writing the tree file by hand"
        assert "Write" in by_hand.group(0) and "Edit" in by_hand.group(0)

    def test_the_changed_nodes_are_shown_to_the_analyst(self) -> None:
        present = _step("### Step T5: ")
        assert "`written`" in present
        assert "`previous_round`" in present
        assert "`unchanged`" in present

    def test_an_answer_to_an_earlier_root_is_marked(self) -> None:
        assert "`root_revision`" in _step("### Step T5: ")


class TestViolationsAreFixedBeforeTheAnalystSeesThem:
    """US-4 AC 2: fix, or remove and say so; nothing is delivered before the check."""

    def test_exit_3_means_nothing_was_written(self) -> None:
        fix = _step("### Step T3: ")
        assert "Exit code 3" in fix
        assert "wrote nothing" in fix

    @pytest.mark.parametrize("kind", get_args(tree_check.ViolationKind))
    def test_every_kind_of_violation_has_a_fix(self, kind: str) -> None:
        row = table_row(section(_skill(), "### Step T3: "), f"`{kind}`")
        assert row[1], f"no fix for {kind}"

    def test_ids_and_dates_stay_out_of_the_text(self) -> None:
        write = _step("### Step T2: ")
        assert "No id and no date in `text`" in write
        assert "`cites`" in write

    def test_a_number_is_written_the_way_the_record_wrote_it(self) -> None:
        row = table_row(section(_skill(), "### Step T3: "), "`number-not-cited`")
        assert "the way the record wrote it" in row[1]
        assert "sign" in row[1]

    def test_a_number_is_never_computed(self) -> None:
        write = _step("### Step T2: ")
        never = re.search(r"Never compute[^.]*\.", write)
        assert never, "no sentence forbids computing a number"
        assert "ratio" in never.group(0)

    def test_exit_1_is_not_always_the_payload(self) -> None:
        fix = _step("### Step T3: ")
        broken = re.search(r"[^.]*cannot be read[^.]*\.", fix)
        assert broken, "no sentence says what to do when a file cannot be read"
        assert "stop" in broken.group(0)

    def test_an_unchanged_answer_is_the_same_statements_under_the_same_root(
        self,
    ) -> None:
        fix = _step("### Step T3: ")
        assert "`restated`" in fix
        assert "root revision" in fix

    def test_a_stale_answer_that_cannot_be_rewritten_does_not_hold_the_rest(
        self,
    ) -> None:
        check = _step("### Step T4: ")
        assert "no event left to cite" in check
        assert "Stale answers" in check
        assert "Stale answers" in _step("### Step T5: ")

    def test_the_journal_is_never_edited_to_pass(self) -> None:
        assert "Never edit a journal" in _step("### Step T3: ")

    def test_a_statement_that_cannot_be_fixed_is_removed_and_reported(self) -> None:
        assert "remove the statement" in _step("### Step T3: ")
        assert "removed" in _step("### Step T5: ")

    def test_the_tree_check_runs_after_the_answers_are_written(self) -> None:
        assert "`tree_check --theme {theme_id}`" in _step("### Step T4: ")

    def test_a_check_that_could_not_run_stops_the_reflection(self) -> None:
        check = _step("### Step T4: ")
        could_not = re.search(r"[^.]*Exit code 2[^.]*\.[^.]*\.", check)
        assert could_not, "no sentence says what exit code 2 means"
        assert "Do not rewrite" in could_not.group(0)

    def test_the_html_is_rendered_again_once_the_check_passes(self) -> None:
        check = _step("### Step T4: ")
        assert check.count("`tree_io render --theme {theme_id}`") == 1
        assert "path" in _step("### Step T5: ")

    def test_nothing_is_shown_before_the_check_passes(self) -> None:
        check = _step("### Step T4: ")
        assert "Show no answer to the analyst before `tree_check` has run" in check
        assert "never show an answer that `tree_check` reports" in check


class TestReflectionCallsOnlyCommandsThatExist:
    def test_every_named_tree_io_command_exists(self) -> None:
        named = {c for tool, c in _COMMAND.findall(_skill()) if tool == "io"}

        assert {"get", "progress", "answer", "render"} <= named
        for command in named:
            with pytest.raises(SystemExit) as exit_:
                tree_io._main([command, "--help"])
            assert exit_.value.code == 0, command


def _below_words(whose: str) -> str:
    """The counts below a node as the page says them, with placeholders for the numbers."""
    counts = "、".join(
        f"{PROGRESS_WORDS[p][0]} {n}"
        for p, n in zip(reversed(Progress), "abc", strict=True)
    )
    return BELOW_WORDS.format(whose=whose, count="{N}") + counts


class TestProgressIsShownAsThePageShowsIt:
    """A node with no progress word shows the counts below it, never 未着手 (ADR-0057)."""

    def test_the_load_step_reads_the_word_or_null_and_the_counts_below(self) -> None:
        load = _step("### Step T1: ")
        assert "`progress`" in load and "`below`" in load
        assert re.search(r"`null`[^.]*`below`", load)

    def test_the_presented_progress_uses_the_words_of_the_page(self) -> None:
        present = _step("### Step T5: ")
        assert _below_words("主題") in present
        assert _below_words("この論点") in present

    def test_a_node_without_a_word_is_never_shown_as_not_started(self) -> None:
        present = _step("### Step T5: ")
        never = re.search(r"`null`[^.]*never[^.]*未着手[^.]*\.", present)
        assert never, "no sentence keeps a node without a word from reading 未着手"
