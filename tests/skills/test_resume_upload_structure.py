"""Structure tests for the upload after a resumed run (Epic 27 US-1).

When `/analysis-auto` resumes a round whose report was written before this run, the driver
still takes the analyst to the approval gate of `/report-upload`, so a report that was never
sent is not silently skipped. The driver keeps no record of what was sent, so the gate's
message says that a report sent before needs no second upload, and asks nothing more
(ADR-0016).

The kept report going on to the upload, and the upload skipped only without a report, are
guarded in test_auto_walk_structure.py and test_upload_wiring_structure.py.
"""

from __future__ import annotations

import re

from tests.skills._auto import auto, gate_row, round_item
from tests.skills._markdown import section, table_rows, unwrap
from tests.skills.test_skill_structure import split_sections

NOTE = "このレポートは前に書いた。前に送っていれば送らなくてよい。送ると Doc がもう1つできる"


class TestAReportFromBeforeGoesToTheUpload:
    """AC 1: the upload runs for any report of the round, also one written before this run."""

    def test_the_upload_runs_for_a_report_that_was_there_before(self) -> None:
        assert re.search(
            r"when the round has a report, run `/report-upload \{design_id\}`[^.]*"
            r"also for a report that was there before this run",
            round_item("upload"),
        )

    def test_gate_policy_starts_the_upload_for_any_report_of_the_round(self) -> None:
        _, _, auto_cell = gate_row("upload")
        assert (
            "once the round has a report, written by this run or before it" in auto_cell
        )


class TestTheGateSaysASentReportNeedsNoUpload:
    """AC 2: for a report from before this run, the gate's message carries the note."""

    def test_the_note_goes_in_the_gate_message_only_for_a_report_from_before(
        self,
    ) -> None:
        assert re.search(
            r"when the report was there before this run, write this line in the gate's message, "
            r"right before \"送ってよい？\": \"" + re.escape(NOTE) + '"',
            round_item("upload"),
        )

    def test_the_note_is_not_a_question(self) -> None:
        assert "The note asks nothing: the gate stays the one question" in round_item(
            "upload"
        )


class TestNothingIsCarriedOver:
    """AC 3: no record of the upload is kept, and no approval carries over (ADR-0016)."""

    def test_the_driver_keeps_no_record_of_the_upload(self) -> None:
        assert "The driver keeps no record of what was sent" in round_item("upload")

    def test_an_approval_from_an_earlier_run_is_not_an_approval(self) -> None:
        assert re.search(
            r"never treat an earlier \"yes\" as a \"yes\" to the upload, "
            r"an approval given in an earlier run included \(\[ADR-0016\]",
            round_item("upload"),
        )


class TestTheRestOfTheSkillAgrees:
    """AC 4: the plan, the theme reflection, the summary and the chaining row agree."""

    def test_the_plan_says_a_report_from_before_is_asked_about_too(self) -> None:
        assert "前に書いたレポートも、送るかを聞く" in unwrap(
            section(auto(), "### Step 1:")
        )

    def test_the_theme_reflection_always_adds_the_upload_outcome(self) -> None:
        item = round_item("theme reflection")
        assert "add the upload outcome." in item
        assert "when this run has one" not in item

    def test_the_summary_covers_any_report_of_the_round(self) -> None:
        summary = unwrap(section(auto(), "### Step 4:"))
        assert "When the round has a report, add the report's path" in summary

    def test_the_chaining_row_starts_the_upload_for_any_report(self) -> None:
        rows = table_rows(split_sections(auto())["Chaining"])
        when = next(row[2] for row in rows if row[1] == "→ /report-upload")
        assert when.startswith(
            "The round has a report, written by this run or before it"
        )
