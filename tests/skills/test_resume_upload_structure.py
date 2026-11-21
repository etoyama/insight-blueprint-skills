"""Structure tests for the upload after a resumed run (Epic 27 US-1).

When `/analysis-auto` resumes a round whose report an earlier run wrote, the driver still
takes the analyst to the approval gate of `/report-upload`, so a report that was never sent
is not silently skipped. The driver keeps no record of what was sent, so it tells the analyst
that a report sent before needs no second upload, and asks nothing of its own (ADR-0016).
"""

from __future__ import annotations

from tests.skills._markdown import unwrap
from tests.skills.test_skill_structure import _read_skill, split_sections
from tests.skills.test_upload_wiring_structure import _drive_item, _gate_row


class TestAnExistingReportGoesToTheUpload:
    """AC 1: a report already there is not rewritten, and the round goes on to the upload."""

    def test_the_report_item_hands_an_existing_report_to_the_upload(self) -> None:
        item = _drive_item("report")
        assert "not written again" in item
        assert "go on to item 9" in item

    def test_the_report_item_no_longer_leaves_the_upload_to_the_analyst(self) -> None:
        assert "is theirs to run" not in _drive_item("report")

    def test_the_upload_runs_for_a_report_an_earlier_run_wrote(self) -> None:
        item = _drive_item("upload")
        assert "when the round has a report" in item.lower()
        assert "an earlier run" in item

    def test_the_upload_is_skipped_only_without_a_report(self) -> None:
        assert (
            "skip this item when the round has no report"
            in _drive_item("upload").lower()
        )

    def test_gate_policy_starts_the_upload_for_any_report_of_the_round(self) -> None:
        _, _, auto = _gate_row("upload")
        assert "once the round has a report" in auto


class TestTheGateSaysASentReportNeedsNoUpload:
    """AC 2: for a report an earlier run wrote, the gate comes with the note that it may be sent already."""

    def test_the_driver_adds_the_note_before_the_gate(self) -> None:
        item = _drive_item("upload")
        assert "前に送っていれば送らなくてよい" in item
        assert "Doc がもう1つできる" in item

    def test_the_note_is_only_for_a_report_an_earlier_run_wrote(self) -> None:
        item = _drive_item("upload")
        note_at = item.index("前に送っていれば")
        assert "an earlier run wrote" in item[:note_at]

    def test_the_note_is_not_a_question(self) -> None:
        item = _drive_item("upload")
        assert "the note asks nothing" in item.lower()
        _, keep, _ = _gate_row("upload")
        assert "no question of its own" in keep


class TestNothingIsCarriedOver:
    """AC 3: no record of the upload is kept, and no approval carries over (ADR-0016)."""

    def test_the_driver_keeps_no_record_of_the_upload(self) -> None:
        assert "keeps no record of what was sent" in _drive_item("upload")

    def test_an_earlier_approval_is_not_an_approval(self) -> None:
        item = _drive_item("upload")
        assert "an earlier run" in item
        assert "never treat an earlier" in item.lower()
        assert "ADR-0016" in item


class TestTheRestOfTheSkillAgrees:
    """AC 4: the chaining row and the summary name the upload for any report of the round."""

    def test_the_chaining_row_starts_the_upload_for_any_report(self) -> None:
        chaining = split_sections(_read_skill("analysis-auto"))["Chaining"]
        row = next(ln for ln in chaining.splitlines() if "→ /report-upload" in ln)
        assert "The round has a report" in row

    def test_the_summary_covers_a_report_an_earlier_run_wrote(self) -> None:
        summary = unwrap(split_sections(_read_skill("analysis-auto"))["Workflow"])
        step4 = summary[summary.index("### Step 4:") :]
        assert "When the round has a report" in step4
        assert "When a report was written" not in step4

    def test_the_plan_says_the_upload_is_asked_on_resume_too(self) -> None:
        workflow = unwrap(split_sections(_read_skill("analysis-auto"))["Workflow"])
        step1 = workflow[: workflow.index("### Step 2:")]
        assert "再開したときも" in step1
