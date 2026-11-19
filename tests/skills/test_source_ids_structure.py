"""Structure tests for where the skills read a design's data sources (Epic 15, ADR-0020).

A design declares the data sources it uses in ``source_ids`` and nowhere else. The
asking and the reading live in SKILL.md prose, so these tests guard the load-bearing
parts: /analysis-design writes ``source_ids`` after checking the catalog, and keeps
``data_source`` as a note that no skill reads as an id.
"""

from __future__ import annotations

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
