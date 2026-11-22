"""Structure tests for a concluded round with more than one design (#161).

`tree_io position` returns every design made since the decision when the round is
`concluded`, so `design_ids` can hold more than one, all of them finished. The driver carries
each of them through the report and the upload, in that order, so no report of such a round is
skipped without the analyst knowing. Each upload keeps its own approval gate (ADR-0016); no new
kind of gate is added. Any other round carries the one design it worked on.
"""

from __future__ import annotations

import re

from tests.skills._auto import auto, round_item
from tests.skills._markdown import section, table_row, unwrap


def round_intro() -> str:
    """The prose of Step 3 before its first numbered item."""
    return unwrap(section(auto(), "### Step 3:").split("\n1. ", 1)[0])


class TestAConcludedRoundCarriesEachDesign:
    def test_a_concluded_position_enters_the_report_for_each_design(self) -> None:
        _, _, enter_at = table_row(section(auto(), "### Step 1:"), "`concluded`")
        assert "for each of the `design_ids`" in enter_at

    def test_only_a_concluded_round_runs_the_report_and_upload_per_design(self) -> None:
        assert re.search(
            r"When the round enters at item 8 from a `concluded` position, items 8 and 9 run "
            r"for each of its `design_ids`, in that order",
            round_intro(),
        )

    def test_any_other_round_carries_the_one_design_it_worked_on(self) -> None:
        assert "Any other round carries the one design it worked on" in round_intro()

    def test_one_design_finishes_its_upload_before_the_next_report(self) -> None:
        intro = round_intro()
        assert "finish one design's upload before the next design's report" in intro
        assert "leave none of them out" in intro

    def test_a_declined_figure_that_ends_the_turn_does_not_end_the_loop(self) -> None:
        assert re.search(
            r"When a declined figure ends the turn, go on with the next design's report on the "
            r"next turn",
            round_intro(),
        )

    def test_an_answer_at_one_gate_is_not_the_answer_for_the_next(self) -> None:
        assert (
            "an answer at one design's gate, yes or no, is not the answer for the next"
            in round_intro()
        )

    def test_without_the_connector_the_next_design_still_gets_its_report(self) -> None:
        assert (
            "go on to the next design's report, or after the last one go on to the "
            "theme reflection" in round_item("upload")
        )


class TestTheRestOfTheRoundShowsEveryReport:
    def test_the_theme_reflection_shows_the_path_of_each_report(self) -> None:
        item = round_item("theme reflection")
        assert "show each report's path" in item
        assert "for each, add the upload outcome" in item

    def test_the_theme_reflection_no_longer_names_a_single_report(self) -> None:
        item = round_item("theme reflection")
        assert "The report is the one of this round's design" not in item

    def test_the_summary_lists_each_report(self) -> None:
        summary = unwrap(section(auto(), "### Step 4:"))
        assert (
            "For each report of the round, add the report's path and the upload outcome"
            in (summary)
        )
