"""Structure tests for the /report-upload skill's prose contract (Epic 12 US-4).

The upload runs through a connector the host owns, so no Python test can drive it.
These tests guard the parts of SKILL.md that keep the analyst safe: nothing leaves
`.insight/` before the approval (ADR-0016), the skill stops where the connector is
missing (ADR-0015), and a figure that cannot be uploaded degrades to a note.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.skills.test_skill_structure import (
    REQUIRED_SECTIONS,
    parse_chaining_table,
    parse_frontmatter,
    split_sections,
)

SKILL = Path(__file__).resolve().parents[2] / "skills" / "report-upload" / "SKILL.md"


def _skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def _step(number: int) -> str:
    """The body of ``### Step {number}`` up to the next heading."""
    text = _skill()
    rest = text[text.index(f"### Step {number}:") :]
    rest = rest[rest.index("\n") :]
    following = re.search(r"^#{1,3} ", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


class TestFrontmatter:
    """The name and the first sentence are what the analyst sees before invoking."""

    def test_name_is_report_upload(self) -> None:
        assert parse_frontmatter(_skill())["name"] == "report-upload"

    def test_is_never_invoked_by_the_model(self) -> None:
        assert parse_frontmatter(_skill())["disable-model-invocation"] is True

    def test_first_sentence_names_the_destination_and_the_private_start(self) -> None:
        description = parse_frontmatter(_skill())["description"]
        first = description.split(". ", 1)[0]
        assert "Claude Docs" in first
        assert "only you can see" in first


class TestSections:
    def test_has_the_required_sections(self) -> None:
        sections = split_sections(_skill())
        for required in REQUIRED_SECTIONS:
            assert required in sections, f"missing '## {required}'"

    def test_chaining_names_both_callers(self) -> None:
        rows = parse_chaining_table(split_sections(_skill())["Chaining"])
        edges = {(r["from"], r["to"].lstrip("→ ").strip()) for r in rows}
        assert ("/analysis-report", "/report-upload") in edges
        assert ("/analysis-auto", "/report-upload") in edges


class TestReportIsTheOnlySource:
    """US-4 AC 1: read the report, make a new Doc, show the URL."""

    def test_reads_the_report_by_design_id(self) -> None:
        assert ".insight/reports/{design_id}.md" in _step(1)

    def test_rejects_a_design_id_that_could_leave_the_reports_directory(self) -> None:
        assert "[a-zA-Z0-9_-]+" in _step(1)

    def test_missing_report_points_at_analysis_report_and_stops(self) -> None:
        step = _step(1)
        assert "/analysis-report" in step
        assert "exit" in step.lower()

    def test_always_creates_a_new_doc(self) -> None:
        text = _skill()
        assert "new Doc" in text
        assert "never overwrite" in text.lower()

    def test_shows_the_url(self) -> None:
        assert "URL" in _step(5)

    def test_never_writes_under_insight(self) -> None:
        assert "writes nothing under `.insight/`" in _skill()


class TestConnectorIsOptional:
    """US-4 AC 3 and ADR-0015: without the connector nothing is sent."""

    def test_missing_connector_stops_before_the_approval(self) -> None:
        step = _step(2)
        assert "Claude Docs connector" in step
        assert "send nothing" in step.lower()
        assert "exit" in step.lower()

    def test_tells_the_analyst_the_markdown_report_remains(self) -> None:
        assert "Markdown" in _step(2)

    def test_names_no_tool(self) -> None:
        # Tool names carry a prefix that differs per environment (spike-constraints).
        assert "mcp__" not in _skill()

    def test_never_installs_or_configures_a_connector(self) -> None:
        assert "never install or configure" in _skill().lower()


class TestApprovalGate:
    """US-4 AC 2 and ADR-0016: list the files, wait, and remember nothing."""

    def test_is_a_keep_gate(self) -> None:
        assert "KEEP" in _step(3)

    def test_lists_the_report_and_the_figures(self) -> None:
        step = _step(3)
        assert "report" in step and "figure" in step
        assert "list" in step.lower()

    def test_shows_the_destination_and_the_private_start_with_the_list(self) -> None:
        step = _step(3)
        assert "Claude Docs" in step
        assert "自分だけに見える" in step

    def test_no_approval_means_nothing_is_sent(self) -> None:
        step = _step(3)
        assert "send nothing" in step.lower()

    def test_approval_is_not_automatic_inside_analysis_auto(self) -> None:
        step = _step(3)
        assert "/analysis-auto" in step
        assert "never automatic" in step.lower()

    def test_approval_covers_one_run_and_is_not_remembered(self) -> None:
        step = _step(3)
        assert "one run" in step.lower()
        assert "never remember" in step.lower()

    def test_the_gate_comes_before_any_send(self) -> None:
        text = _skill()
        assert text.index("### Step 3:") < text.index("### Step 4:")
        assert "only after" in _step(4).lower()

    def test_cites_the_rule(self) -> None:
        assert "ADR-0016" in _skill()


class TestFigures:
    """US-4 AC 4: figures ride along; one that cannot is dropped with a note."""

    def test_takes_the_figures_from_the_report_links(self) -> None:
        assert "../notebooks/" in _step(1)

    def test_figure_file_must_be_a_bare_png_basename(self) -> None:
        step = _step(1)
        assert "basename" in step
        assert ".png" in step

    def test_unavailable_or_failed_upload_drops_the_figure_with_a_note(self) -> None:
        step = _step(4)
        assert "omit" in step.lower()
        assert "one-line note" in step.lower()

    def test_a_failed_figure_does_not_fail_the_upload(self) -> None:
        assert "never fail the upload" in _step(4).lower()

    def test_no_local_path_reaches_the_doc(self) -> None:
        assert "no local path" in _step(4).lower()
