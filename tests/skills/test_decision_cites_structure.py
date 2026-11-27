"""Structure tests: the decision gate cites its reason and offers the subject (Epic 34, Story 34.4).

US-4 AC 4: /analysis-reflection puts the journal events the analyst's reason rests
on into the decision, and writes a reason that rests on none without cites. US-4
AC 5: the gate offers 主題そのものを見直す beside the three kinds, and choosing it
goes to the step of /analysis-framing that raises the root revision (ADR-0058).
The steps live in SKILL.md prose, so these tests guard the load-bearing parts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from insight_blueprint.models.tree import TreeDecisionKind
from skills._shared import tree_io
from tests.docs._changelog import changelog_entry
from tests.skills._markdown import section, table_row, unwrap
from tests.skills._shown import run_shown_commands
from tests.skills.test_next_candidate_structure import _library
from tests.skills.test_skill_structure import _read_skill

REVISE = "主題そのものを見直す"
RENDER = "`tree_io render --theme {theme_id}`"


def _gate() -> str:
    return section(_read_skill("analysis-reflection"), "### Step T7: ")


def _auto_walk() -> str:
    return unwrap(section(_read_skill("analysis-auto"), "### Step 3:"))


class TestTheDecisionCitesWhatItsReasonRestsOn:
    """US-4 AC 4."""

    def test_the_shown_command_writes_a_decision_with_its_cites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        insight = tmp_path / ".insight"
        _library(insight)
        run_shown_commands(
            section(_read_skill("analysis-reflection"), "### Step T6: "),
            insight,
            monkeypatch,
        )

        run_shown_commands(_gate(), insight, monkeypatch)

        decision = tree_io.load_tree("LIB", base_dir=insight)["decisions"][-1]
        assert decision["cites"] == ["LIB-H01-E01"]

    def test_events_behind_the_reason_go_into_cites(self) -> None:
        assert re.search(
            r"(?i)when the reason rests on[^.]*journal event[^.]*`cites`",
            unwrap(_gate()),
        )

    def test_a_reason_that_rests_on_no_event_is_written_without_cites(self) -> None:
        assert re.search(
            r"(?i)rests on no (journal )?event[^.]*without `cites`", unwrap(_gate())
        )

    def test_the_skill_never_adds_a_cite_to_make_a_reason_look_backed(self) -> None:
        assert re.search(r"(?i)never add a cite[^.]*does not rest on", unwrap(_gate()))

    def test_the_cited_results_are_read_back_in_the_analysts_words(self) -> None:
        step = unwrap(_gate())
        assert "根拠にした分析結果" in step
        assert re.search(r"read the decision back[^.]*kind, node, reason", step)

    def test_a_violation_means_nothing_was_written(self) -> None:
        step = unwrap(_gate())
        assert re.search(r"(?i)exit code 3[^.]*`violations`[^.]*wrote nothing", step)

    @pytest.mark.parametrize(
        "kind", ["number-not-cited", "missing-event", "unlinked-design"]
    )
    def test_each_violation_has_a_way_out(self, kind: str) -> None:
        assert table_row(_gate(), f"`{kind}`")[1]

    def test_an_id_or_the_round_in_the_reason_is_not_asked_away(self) -> None:
        # Epic 35, US-6 (ADR-0065): only a date is read as a number among names.
        row = table_row(_gate(), "`number-not-cited`")[1]
        assert re.search(r"id of a node[^.]*not counted", row)
        assert "回目の振り返り" in row
        assert "`fix`" in row

    def test_the_cites_are_never_dropped_to_get_past_the_check(self) -> None:
        assert re.search(
            r"(?i)never drop[^.]*`cites`[^.]*pass the check", unwrap(_gate())
        )

    def test_the_reason_is_reworded_only_by_the_analyst(self) -> None:
        assert re.search(r"(?i)never reword[^.]*reason[^.]*yourself", unwrap(_gate()))

    def test_the_reference_says_decide_checks_the_cites(self) -> None:
        reference = section(
            _read_skill("analysis-reflection"), "## tree_io / tree_check Reference"
        )
        assert (
            "cites"
            in table_row(reference, "`tree_io decide --theme T` (stdin JSON)")[1]
        )


class TestTheGateOffersToReviseTheSubject:
    """US-4 AC 5."""

    def test_the_fourth_choice_stands_beside_the_three_kinds(self) -> None:
        step = _gate()
        assert "which of the four" in unwrap(step)
        assert REVISE in table_row(step, "—")[1]

    def test_the_kinds_of_decision_stay_four(self) -> None:
        # The fourth choice at the gate is not a fourth kind to write here:
        # with `start`, the model already has four, and none of them is this.
        assert {k.value for k in TreeDecisionKind} == {
            "start",
            "deepen",
            "return",
            "close",
        }
        step = unwrap(_gate())
        assert re.search(rf"{REVISE}[^.]*is not a `kind`", step)
        assert re.search(r"(?i)no decision is written for it", step)

    def test_choosing_it_goes_to_the_step_that_raises_the_revision(self) -> None:
        step = unwrap(_gate())
        chosen = re.search(rf"When the analyst chooses {REVISE}[^.]*\.", step)
        assert chosen, "no sentence says where the fourth choice leads"
        assert "/analysis-framing {theme_id}" in chosen.group(0)
        assert "4c" in chosen.group(0)

    def test_the_revision_is_asked_by_framing_not_here(self) -> None:
        step = _gate()
        assert "| tree_io revise-root" not in step
        assert re.search(r"(?i)never run `tree_io revise-root`[^.]*here", unwrap(step))

    def test_the_gate_asks_again_after_the_revision(self) -> None:
        assert re.search(
            r"(?i)after the revision[^.]*come back to this gate[^.]*ask[^.]*again",
            unwrap(_gate()),
        )

    def test_the_page_shows_the_new_subject_before_the_decision_is_asked_again(
        self,
    ) -> None:
        # Only 4c of /analysis-framing runs, not its 5c: without a render here the
        # HTML still shows the old 主題 while the gate asks under the new one.
        step = unwrap(_gate())
        after = step[step.index("After the revision") :]
        render = after.index(RENDER)
        assert render < after.index("ask the decision again")
        assert "`path`" in after[render : after.index("ask the decision again")]

    def test_framing_is_left_before_it_asks_for_the_next_node(self) -> None:
        # 4d of /analysis-framing asks for the next node and may write a decision:
        # passing it on the way back would ask the analyst the same thing twice.
        assert re.search(
            r"(?i)only[^.]*4c[^.]*\.[^.]*do not go on to 4d or 5b", unwrap(_gate())
        )

    def test_a_journal_that_cannot_be_read_is_reported_not_asked_again(self) -> None:
        step = unwrap(_gate())
        assert re.search(r"appears twice[^.]*report[^.]*analyst[^.]*stop", step)

    def test_the_choice_is_named_in_the_analysts_words(self) -> None:
        # ADR-0055: what the analyst reads says 主題, never 根の問い.
        assert "根の" not in _gate()


class TestTheDriverLetsTheGateReviseTheSubject:
    """US-4 AC 5 inside the walk: the round is not over when the subject is revised."""

    def test_the_gate_of_the_round_names_the_fourth_choice(self) -> None:
        walk = _auto_walk()
        chosen = re.search(rf"[^.]*{REVISE}[^.]*\.", walk)
        assert chosen, "the walk does not say what happens on the fourth choice"
        assert "4c" in chosen.group(0)

    def test_the_round_goes_on_at_the_same_gate(self) -> None:
        assert re.search(
            rf"{REVISE}[^.]*\.[^.]*round is not over[^.]*Step T7", _auto_walk()
        )


class TestTheChangelogWarnsOlderPlugins:
    """`TreeDecision` forbids keys it does not know, so a plugin from before Epic 34
    rejects a tree whose decision has `cites`."""

    def test_the_upgrade_note_says_an_older_plugin_cannot_read_the_tree(self) -> None:
        changelog = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text(
            encoding="utf-8"
        )
        entry = changelog_entry(changelog, "a decision that has `cites`")
        note = unwrap(section(entry, "### Upgrade note"))
        assert re.search(
            r"a decision that has `cites` cannot be read by an earlier version", note
        )
