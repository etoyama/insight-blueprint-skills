"""Structure tests for a round with more than one design (#161).

`tree_io position` returns every design made since the decision when the round is
`concluded`, so `design_ids` can hold more than one. The driver carries each of them through
the report and the upload, in that order, so no report is skipped without the analyst knowing.
Each upload keeps its own approval gate (ADR-0016); no new kind of gate is added.
"""

from __future__ import annotations

from tests.skills._auto import auto, round_item
from tests.skills._markdown import section, table_row, unwrap


class TestEveryDesignOfTheRoundIsCarried:
    def test_a_concluded_position_enters_the_report_for_each_design(self) -> None:
        _, _, enter_at = table_row(section(auto(), "### Step 1:"), "`concluded`")
        assert enter_at == "Step 3, item 8, for each of the `design_ids` in turn"

    def test_the_report_and_the_upload_run_once_for_each_design(self) -> None:
        assert (
            "items 8 and 9 run once for each design of the round, in the order of "
            "`design_ids`" in round_item("report")
        )

    def test_one_design_finishes_its_upload_before_the_next_report(self) -> None:
        assert (
            "finish the upload of one design before the report of the next, and leave "
            "none of them out" in round_item("report")
        )

    def test_without_the_connector_the_next_design_still_gets_its_report(self) -> None:
        assert (
            "go on to the next design's report, or after the last one go on to the "
            "theme reflection" in round_item("upload")
        )


class TestTheRestOfTheRoundShowsEveryReport:
    def test_the_theme_reflection_shows_the_report_of_each_design(self) -> None:
        assert (
            "The reports are those of all of this round's designs, also when an earlier "
            "run wrote them; for each, add the upload outcome."
            in round_item("theme reflection")
        )

    def test_the_summary_lists_each_report(self) -> None:
        assert (
            "add the report's path and the upload outcome, for each report of the round"
            in (unwrap(section(auto(), "### Step 4:")))
        )
