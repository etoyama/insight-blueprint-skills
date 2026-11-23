"""Structure tests for where the skills read a design's data sources (Epic 15, ADR-0020).

A design declares the data sources it uses in ``source_ids`` and nowhere else. The
asking and the reading live in SKILL.md prose, so these tests guard the load-bearing
parts: /analysis-design writes ``source_ids`` after checking the catalog, the other
skills read the sources from it, and ``data_source`` stays a note no skill reads as an id.
The report's side lives with the other report tests (``test_analysis_report_structure``).
"""

from __future__ import annotations

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

# Shell-safe and the only shape catalog_io accepts as an id.
_ID_FILTER = "fully match `^[a-zA-Z0-9_-]+$`"


class TestAnalysisDesignDeclaresTheSources:
    """US-1: the analyst declares the data sources in ``source_ids``."""

    def test_field_table_lists_source_ids(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 2: ")
        assert "Data sources" in table_row(step, "`source_ids`")[2]

    def test_the_ids_are_checked_in_the_catalog_before_writing(self) -> None:
        asking = unwrap(section(_read_skill("analysis-design"), "#### Data sources"))
        assert "catalog_io describe --ids=" in asking
        assert _ID_FILTER in asking
        assert "Write the ids of `sources`" in asking
        assert "/catalog-register" in asking
        assert "never write an unregistered id" in asking.lower()

    def test_data_source_is_a_note_and_not_an_id(self) -> None:
        asking = unwrap(section(_read_skill("analysis-design"), "#### Data sources"))
        assert "`data_source`" in asking
        assert "not read as a source id" in asking

    def test_code_patterns_come_from_source_ids(self) -> None:
        step = unwrap(section(_read_skill("analysis-design"), "### Step 2.6: "))
        assert "each id in `source_ids`" in step

    def test_create_payload_shows_source_ids(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 3: ")
        assert '"source_ids": [' in step

    def test_design_io_reference_lists_source_ids(self) -> None:
        reference = section(_read_skill("analysis-design"), "## design_io Reference")
        assert "source_ids?" in table_row(reference, "`create`")[2]

    def test_typed_reference_says_design_io_does_not_check_the_ids(self) -> None:
        reference = section(
            _read_skill("analysis-design"), "## Typed Field Values Reference"
        )
        assert "Not checked by `design_io`" in table_row(reference, "`source_ids`")[2]

    def test_framing_brief_data_drafts_source_ids(self) -> None:
        brief = section(_read_skill("analysis-design"), "### Step 1.5: ")
        assert "`source_ids`" in table_row(brief, "利用可能データ")[1]


class TestAnExistingDesignCanDeclareItsSources:
    """US-1: a design made before ADR-0020 is sent here, so the way back must work."""

    def test_step_0_lets_the_user_change_an_existing_design(self) -> None:
        gate = unwrap(section(_read_skill("analysis-design"), "### Step 0: "))
        assert "existing design" in gate and "Step 3b" in gate

    def test_step_3b_checks_the_ids_like_step_2(self) -> None:
        update = unwrap(section(_read_skill("analysis-design"), "### Step 3b: "))
        assert '{"source_ids": [' in update
        assert 'check the ids as "Data sources" (Step 2) says' in update
        assert "replaced as a whole" in update


class TestDownstreamSkillsReadSourceIds:
    """US-3: notebook, premortem and the autopilot read the sources from ``source_ids``."""

    def test_notebook_loads_each_id_in_source_ids(self) -> None:
        gather = unwrap(section(_read_skill("analysis-notebook"), "### Step 2: "))
        assert "For each id in the design's `source_ids`" in gather

    def test_notebook_stops_before_any_transition_when_no_source_is_declared(
        self,
    ) -> None:
        load = unwrap(section(_read_skill("analysis-notebook"), "### Step 1: "))
        assert "If `source_ids` is empty, stop before any transition" in load
        assert load.index("stop before any transition") < load.index("--target")

    def test_premortem_builds_one_entry_per_design_from_source_ids(self) -> None:
        workflow = unwrap(section(_read_skill("premortem"), "## Workflow"))
        assert "for each id in its `source_ids`" in workflow
        assert "`false` when it fails for any of its sources" in workflow

    def test_premortem_passes_the_design_as_design_io_returned_it(self) -> None:
        # risk_evaluator reads source_ids from the design itself.
        workflow = unwrap(section(_read_skill("premortem"), "## Workflow"))
        assert "as `design_io get` returned it" in workflow
        assert "`no data source declared`" in workflow

    def test_autopilot_confirms_the_sources_at_the_data_extraction_beat(self) -> None:
        text = unwrap(_read_skill("analysis-auto"))
        beat = text[text.index("3. **data-extraction**") : text.index("4. **charts**")]
        assert "`source_ids`" in beat

    def test_autopilot_tells_the_two_premortem_reasons_apart(self) -> None:
        text = unwrap(_read_skill("analysis-auto"))
        assert "`source not registered` → offer /catalog-register" in text
        assert "`no data source declared` → offer /analysis-design" in text
        assert "declared source(s) are the ids in the design's `source_ids`" in text

    def test_no_other_skill_mentions_data_source(self) -> None:
        # Only the producer explains the note. Anything else would be reading it.
        allowed = {"analysis-design"}
        for skill in sorted(SKILLS_DIR.iterdir()):
            if skill.name in allowed or not (skill / "SKILL.md").exists():
                continue
            for path in skill.rglob("*.md"):
                assert "data_source" not in path.read_text(encoding="utf-8"), path


class TestCatalogRegisterReference:
    """US-2 AC 5: what ``get`` prints for an unknown id, and the ``describe`` row."""

    def test_reference_says_what_get_returns_for_an_unknown_id(self) -> None:
        reference = unwrap(
            section(_read_skill("catalog-register"), "## catalog_io Reference")
        )
        assert "prints `{}` and exits 0" in reference

    def test_reference_lists_describe(self) -> None:
        reference = section(_read_skill("catalog-register"), "## catalog_io Reference")
        assert (
            "`{sources, missing}`" in table_row(reference, "`describe --ids=ID,ID`")[1]
        )
