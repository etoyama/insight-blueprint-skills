"""Structure tests for where the skills read a design's data sources (Epic 15, ADR-0020).

A design declares the data sources it uses in ``source_ids`` and nowhere else. The
asking and the reading live in SKILL.md prose, so these tests guard the load-bearing
parts: /analysis-design writes ``source_ids`` after checking the catalog, and keeps
``data_source`` as a note that no skill reads as an id.
"""

from __future__ import annotations

from pathlib import Path

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill


class TestAnalysisDesignDeclaresTheSources:
    """US-1: the analyst declares the data sources in ``source_ids``."""

    def test_field_table_lists_source_ids_as_registered_ids(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 2: ")
        description = table_row(step, "`source_ids`")[2]
        assert "registered" in description
        assert "catalog" in description

    def test_the_sources_are_checked_in_the_catalog_before_writing(self) -> None:
        asking = unwrap(section(_read_skill("analysis-design"), "#### Data sources"))
        assert "catalog_io get --id" in asking
        assert "/catalog-register" in asking
        # An unregistered id is never written: downstream skills would find nothing.
        assert "never write an unregistered id" in asking.lower()

    def test_data_source_is_a_note_and_not_an_id(self) -> None:
        asking = unwrap(section(_read_skill("analysis-design"), "#### Data sources"))
        assert "`data_source`" in asking
        assert "note" in asking
        assert "not read as a source id" in asking

    def test_code_patterns_come_from_source_ids(self) -> None:
        step = unwrap(section(_read_skill("analysis-design"), "### Step 2.6: "))
        assert "each id in `source_ids`" in step
        assert "`data_source` references" not in step

    def test_create_payload_shows_source_ids(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 3: ")
        assert '"source_ids": [' in step

    def test_design_io_reference_lists_source_ids(self) -> None:
        reference = section(_read_skill("analysis-design"), "## design_io Reference")
        assert "source_ids?" in table_row(reference, "`create`")[2]

    def test_framing_brief_data_drafts_source_ids(self) -> None:
        brief = section(_read_skill("analysis-design"), "### Step 1.5: ")
        assert "`source_ids`" in table_row(brief, "利用可能データ")[1]


def _report_skill() -> str:
    return _read_skill("analysis-report")


def _template() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "skills/analysis-report/references/apa-template.md"
    ).read_text(encoding="utf-8")


class TestReportShowsOnlyTheDeclaredSources:
    """US-2: the report reads ``source_ids`` alone and asks ``catalog_io describe``."""

    def test_skill_passes_source_ids_to_describe(self) -> None:
        gather = unwrap(section(_report_skill(), "### Step 2: "))
        assert "catalog_io describe --ids {source_ids}" in gather
        assert "`data_source`" not in gather

    def test_template_reads_source_ids_and_not_data_source(self) -> None:
        data = unwrap(section(_template(), "## Data description (Method)"))
        assert "`source_ids`" in data
        assert "is not read" in data and "`data_source`" in data
        # The candidate collection moved into catalog_io describe.
        assert "candidate" not in data
        assert "^[a-zA-Z0-9_-]+$" not in data

    def test_template_tells_the_analyst_about_empty_source_ids(self) -> None:
        data = unwrap(section(_template(), "## Data description (Method)"))
        assert "When `source_ids` is empty" in data
        assert "/analysis-design" in data

    def test_template_leaves_missing_ids_out_and_names_them(self) -> None:
        data = unwrap(section(_template(), "## Data description (Method)"))
        assert "`missing`" in data
        assert "never in the table" in data

    def test_hand_off_names_empty_or_missing_sources(self) -> None:
        handoff = unwrap(section(_report_skill(), "### Step 4: "))
        assert "`source_ids`" in handoff and "`missing`" in handoff

    def test_method_tables_say_why_there_is_no_data_source_column(self) -> None:
        tables = unwrap(section(_template(), "## Method tables (Method)"))
        assert "`data_source`" in tables
        assert "a note, not a source id" in tables


class TestUnregisteredIdIsDocumented:
    """US-2 AC 5: ``catalog_io get`` prints ``{}`` with exit code 0 for an unknown id."""

    def test_catalog_register_reference_says_what_get_returns(self) -> None:
        reference = unwrap(
            section(_read_skill("catalog-register"), "## catalog_io Reference")
        )
        assert "prints `{}` and exits 0" in reference

    def test_catalog_register_reference_lists_describe(self) -> None:
        reference = section(_read_skill("catalog-register"), "## catalog_io Reference")
        purpose = table_row(reference, "`describe --ids ID,ID`")[1]
        assert "`missing`" in purpose


class TestDownstreamSkillsReadSourceIds:
    """US-3: notebook, premortem and the autopilot read the sources from ``source_ids``."""

    def test_notebook_loads_each_id_in_source_ids(self) -> None:
        gather = unwrap(section(_read_skill("analysis-notebook"), "### Step 2: "))
        assert "For each id in the design's `source_ids`" in gather

    def test_notebook_stops_when_no_source_is_declared(self) -> None:
        gather = unwrap(section(_read_skill("analysis-notebook"), "### Step 2: "))
        assert "If `source_ids` is empty, stop" in gather
        assert "/analysis-design" in gather

    def test_premortem_builds_the_checks_from_source_ids(self) -> None:
        workflow = unwrap(section(_read_skill("premortem"), "## Workflow"))
        assert "for each id in its `source_ids`" in workflow

    def test_autopilot_defines_the_declared_sources(self) -> None:
        text = unwrap(_read_skill("analysis-auto"))
        assert "declared source(s) are the ids in the design's `source_ids`" in text
        assert "no declared source → offer /analysis-design" in text

    def test_no_skill_reads_data_source_as_an_id(self) -> None:
        for name in ("analysis-notebook", "premortem", "analysis-auto"):
            assert "data_source" not in _read_skill(name), name

    def test_premortem_blocks_a_design_that_declares_no_source(self) -> None:
        # cli.py treats a design missing from source_checks_map as registered, so the
        # prose must write the false itself, or the notebook is the first to stop.
        workflow = unwrap(section(_read_skill("premortem"), "## Workflow"))
        assert "An empty `source_ids` is `source_registered: false`" in workflow
