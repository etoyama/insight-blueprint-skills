"""Structure tests for explaining a metric before the method is asked (Epic 32 US-7, #210).

An analyst asked to confirm metrics they have never seen cannot judge them, and
approves a method they do not understand. The explaining lives in SKILL.md prose, so
these tests guard its load-bearing parts: every metric gets one sentence, a metric
built from two or more quantities that is new to the theme gets the five parts, the
example numbers never come from the result to be judged, and a confirmation's
criterion says what it means and what changes the verdict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from skills._shared import design_io
from tests.docs._changelog import changelog_entry
from tests.skills._auto import design_beat, gate_row, round_item
from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

HEADING = "#### Metrics explained before they are asked"
FIVE_PARTS = ("何を表す数か", "作り方", "実データの例", "迷いやすい点", "言えないこと")
COMPOSITE_KINDS = ("標準化", "期待値との差", "比の比", "モデルの係数", "合成した指数")
TOLD_FIRST = "どの指標にも、詳しい解説を求められます"


def _design() -> str:
    return _read_skill("analysis-design")


def _explained() -> str:
    return section(_design(), HEADING)


def _rule() -> str:
    """The rules of the section, without its sample."""
    return unwrap(_explained().split("Sample", 1)[0])


def _sample() -> str:
    found = re.search(r"Sample.*?```text\n(.*?)```", _explained(), re.S)
    assert found, "the section shows no sample of the explanation"
    return found.group(1)


def _in_order(text: str, parts: tuple[str, ...]) -> bool:
    places = [text.find(part) for part in parts]
    return -1 not in places and places == sorted(places)


class TestEveryMetricGetsOneSentence:
    """US-7 AC 1: each metric says what number it is."""

    def test_the_explanation_comes_after_the_data_sources_and_before_the_criterion(
        self,
    ) -> None:
        step = section(_design(), "### Step 2: ")
        assert (
            step.index("#### Data sources")
            < step.index(HEADING)
            < step.index("#### Criterion")
        )

    def test_every_metric_gets_one_sentence_of_what_it_is(self) -> None:
        rule = _rule()
        assert "Every metric" in rule
        assert "one sentence" in rule
        assert "何を表す数か" in rule


class TestACompositeMetricNewToTheThemeGetsFiveParts:
    """US-7 AC 2: the five parts, and which metrics get them."""

    def test_the_five_parts_are_named_in_order(self) -> None:
        bold = tuple(f"**{part}**" for part in FIVE_PARTS)
        assert _in_order(_rule(), bold)

    def test_a_metric_from_two_or_more_quantities_gets_them(self) -> None:
        rule = _rule()
        assert "two or more quantities" in rule
        for kind in COMPOSITE_KINDS:
            assert kind in rule, kind

    def test_only_a_metric_not_yet_in_a_design_of_the_theme_gets_them(self) -> None:
        rule = _rule()
        assert "`design_io list`" in rule
        assert "`theme_id`" in rule
        assert "`metrics[].target`" in rule

    def test_design_io_list_shows_the_metrics_of_each_theme(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        for theme, target in (("LIB", "wait_days_mean"), ("OTHER", "wait_excess_days")):
            design_io.create_design(
                title=target,
                theme_id=theme,
                analysis_intent="exploratory",
                exploration_question="予約はどれだけ待つか",
                exploration_background="苦情が増えた",
                methodology={"method": "記述統計"},
                metrics=[{"target": target, "tier": "primary"}],
                base_dir=tmp_path,
            )
        capsys.readouterr()
        assert design_io._main(["list", "--base-dir", str(tmp_path)]) == 0
        seen = {
            metric["target"]
            for design in json.loads(capsys.readouterr().out)
            if design["theme_id"] == "LIB"
            for metric in design["metrics"]
        }
        assert seen == {"wait_days_mean"}

    def test_a_metric_from_one_quantity_gets_the_sentence_only(self) -> None:
        assert "sentence only" in _rule()

    def test_the_explanation_comes_before_the_question(self) -> None:
        rule = _rule()
        assert rule.index("**言えないこと**") < rule.index("Then confirm the metrics")

    def test_a_design_under_default_treats_the_metric_as_new(self) -> None:
        assert "`DEFAULT` treats every such metric as new" in _rule()

    def test_a_metric_added_by_update_is_explained_too(self) -> None:
        assert "`design_io update` (Step 3b) is explained the same way" in _rule()

    def test_the_sample_shows_the_five_parts_in_order(self) -> None:
        assert _in_order(_sample(), FIVE_PARTS)


class TestTheExampleNumbersAreNotTheResult:
    """US-7 AC 3: the numbers come from the journal or another group."""

    def test_the_numbers_come_from_the_journal_or_another_group(self) -> None:
        rule = _rule()
        assert "journal" in rule
        assert "another group" in rule and "same way" in rule

    def test_the_result_to_be_judged_is_never_used(self) -> None:
        assert "Never use the result" in _rule()

    def test_an_approximation_is_marked(self) -> None:
        assert "概算" in _rule()
        assert "概算" in _sample()

    def test_the_sample_says_where_its_numbers_come_from(self) -> None:
        sample = _sample()
        assert "journal" in sample or "別の群" in sample


class TestTheCriterionSaysWhatItMeans:
    """US-7 AC 4: a confirmation's criterion says what it means and what changes it."""

    def _criterion(self) -> str:
        return unwrap(section(_design(), "#### Criterion"))

    def test_the_meaning_of_the_criterion_is_given(self) -> None:
        criterion = self._criterion()
        assert "what the criterion means" in criterion

    def test_a_change_of_handling_and_its_effect_on_the_verdict_is_given(self) -> None:
        criterion = self._criterion()
        assert "how the verdict changes" in criterion
        assert "扱い" in criterion

    def test_an_exploration_gets_no_meaning_of_a_criterion(self) -> None:
        exploration = self._criterion().split("An exploration's `comparison`", 1)[1]
        assert "how the verdict changes" not in exploration
        assert "no threshold" in exploration

    def test_a_metric_of_one_quantity_names_the_handling_that_moves_it(self) -> None:
        assert "name the handling that moves its verdict most" in self._criterion()


class TestTheAnalystCanAskForAnyMetric:
    """US-7 AC 5: told first, and /analysis-auto's design ② says the same."""

    def test_the_analyst_is_told_before_the_question(self) -> None:
        rule = _rule()
        assert TOLD_FIRST in rule
        assert rule.index(TOLD_FIRST) < rule.index("confirm")

    def test_the_gate_row_of_design_two_names_the_explanation(self) -> None:
        keep = unwrap(gate_row("design ② methodology")[1])
        assert '"Metrics explained"' in keep
        assert "one sentence" in keep and "five parts" in keep

    def test_the_methodology_beat_names_the_explanation(self) -> None:
        beat = design_beat("methodology")
        assert '"Metrics explained"' in beat
        assert TOLD_FIRST in beat

    def test_the_design_item_of_the_round_still_reads(self) -> None:
        assert "methodology" in round_item("design")

    def test_the_driver_never_uses_the_word_it_keeps_out(self) -> None:
        assert "響" not in _read_skill("analysis-auto")


class TestTheDeferredWordingFollowsTheForms:
    """The two deferred findings on /analysis-design (32.7 handoff)."""

    def test_reflection_chains_to_a_hypothesis_or_a_question(self) -> None:
        row = table_row(section(_design(), "## Chaining"), "/analysis-reflection")
        assert "派生仮説" not in row[2]
        assert "検証仮説" in row[2] and "探索の問い" in row[2]

    def test_the_parent_is_not_said_to_be_checked_for_a_status(self) -> None:
        derived = unwrap(section(_design(), "### Derived Hypotheses"))
        assert "active" not in derived
        assert "`design_io` does not check the parent" in derived
        assert "what status it is in" in derived


class TestTheChangeIsRecorded:
    def test_the_unreleased_entry_names_the_explanation(self) -> None:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        entry = changelog_entry(changelog, "explains a metric")
        assert "`/analysis-design`" in unwrap(entry)
