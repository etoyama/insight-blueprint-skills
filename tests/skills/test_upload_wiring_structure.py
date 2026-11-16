"""Structure tests for the wiring from the report to the upload (Epic 12 US-5).

`/analysis-auto` starts `/report-upload` after the report, and the analyst is asked
about the upload exactly once: at the approval gate of `/report-upload` (ADR-0016).
No Python test can drive the autopilot, so these tests guard the sentences in the
SKILL.md files that keep the driver and `/analysis-report` from asking a second time.
"""

from __future__ import annotations

import re

from tests.skills.test_skill_structure import (
    _extract_chaining_edges,
    _read_skill,
    split_sections,
)


def _auto() -> str:
    return _read_skill("analysis-auto")


def _unwrap(prose: str) -> str:
    """Join wrapped lines, so an assertion reads the sentence and not where it breaks."""
    return re.sub(r"\s+", " ", prose)


def _gate_row(step: str) -> list[str]:
    """The cells of the Gate policy row whose first cell is ``step``."""
    policy = split_sections(_auto())["Gate policy"]
    for line in policy.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == step:
            return cells
    raise AssertionError(f"Gate policy has no '{step}' row")


def _drive_item(name: str) -> str:
    """The numbered item ``N. **name**`` of Step 2, up to the next item or heading."""
    match = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,3}} |\Z)",
        _auto(),
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"Step 2 has no '{name}' item"
    return _unwrap(match.group(0))


def _h3(skill: str, heading: str) -> str:
    text = _read_skill(skill)
    rest = text[text.index(heading) :]
    rest = rest[rest.index("\n") :]
    following = re.search(r"^#{1,3} ", rest, re.MULTILINE)
    return _unwrap(rest[: following.start()] if following else rest)


class TestChainingPointsBothWays:
    """US-5 AC 1: the report and the upload name each other, and the autopilot names the upload."""

    def test_the_report_points_at_the_upload(self) -> None:
        assert ("analysis-report", "report-upload") in _extract_chaining_edges(
            "analysis-report"
        )

    def test_the_autopilot_points_at_the_upload(self) -> None:
        assert ("analysis-auto", "report-upload") in _extract_chaining_edges(
            "analysis-auto"
        )


class TestAutopilotStartsTheUpload:
    """US-5 AC 2: the driver starts the upload and adds no question of its own."""

    def test_gate_policy_leaves_the_only_question_to_the_upload_skill(self) -> None:
        _, keep, auto = _gate_row("upload")
        assert "/report-upload" in keep
        assert "no question of its own" in keep
        assert "starting `/report-upload`" in auto

    def test_the_upload_follows_the_report(self) -> None:
        text = _auto()
        assert text.index("8. **report**") < text.index("9. **upload**")
        assert "/report-upload" in _drive_item("upload")

    def test_the_driver_does_not_ask_whether_to_upload(self) -> None:
        assert "do not ask whether to upload" in _drive_item("upload").lower()

    def test_the_driver_never_answers_the_gate_for_the_analyst(self) -> None:
        item = _drive_item("upload")
        assert "never answer" in item.lower()
        assert "ADR-0016" in item

    def test_no_report_means_no_upload(self) -> None:
        assert "when no report was written" in _drive_item("upload").lower()

    def test_a_missing_connector_goes_on_to_the_summary(self) -> None:
        item = _drive_item("upload")
        assert "connector" in item
        assert "summary" in item.lower()

    def test_the_run_ends_at_the_upload_not_at_the_report(self) -> None:
        assert "where the run ends" not in _drive_item("report")
        assert "where the run ends" in _drive_item("upload")

    def test_the_summary_carries_the_report_path_and_the_upload_outcome(self) -> None:
        summary = _h3("analysis-auto", "### Step 3:")
        assert "report's path" in summary
        assert "Doc URL" in summary

    def test_delegated_skills_name_the_report_and_the_upload(self) -> None:
        delegated = split_sections(_auto())["Delegated skills"]
        assert "`/analysis-report`" in delegated
        assert "`/report-upload`" in delegated


class TestReportHandsOffWithoutAsking:
    """US-5 AC 1, AC 2: /analysis-report names the next step but neither asks nor starts it."""

    def test_the_hand_off_names_the_upload(self) -> None:
        assert "/report-upload" in _h3("analysis-report", "### Step 4:")

    def test_the_hand_off_neither_asks_nor_starts_the_upload(self) -> None:
        hand_off = _h3("analysis-report", "### Step 4:").lower()
        assert "do not ask whether to upload" in hand_off
        assert "never start" in hand_off

    def test_word_and_pdf_go_through_the_upload(self) -> None:
        not_for = split_sections(_read_skill("analysis-report"))["When NOT to Use"]
        line = next(ln for ln in not_for.splitlines() if ".docx" in ln)
        assert "/report-upload" in line
