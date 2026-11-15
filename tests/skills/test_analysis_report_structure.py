"""Structural validation for the /analysis-report skill's prose contract (Epic 10).

The report skill is Claude-native (assembly logic lives in prose, not Python), so these
tests guard the load-bearing contract in SKILL.md + apa-template.md the same way
TestFramingBrief guards analysis-framing's output template: the mandatory figure captions
(ADR-0008), the graceful-degrade branch, the English APA headings, and the terminal-status
precondition. Without these, a heading or caption field could silently rot.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "analysis-report"
NOTEBOOK_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "analysis-notebook"
    / "references"
    / "notebook-contract.md"
)

# The optional per-metric items of ADR-0013, and the Results table column each one fills.
OPTIONAL_METRIC_COLUMNS = {
    "effect_size": "Effect size",
    "confidence_interval": "CI",
    "sample_size": "N",
}


def _skill() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def _template() -> str:
    return (SKILL_DIR / "references" / "apa-template.md").read_text(encoding="utf-8")


class TestApaTemplate:
    """apa-template.md is the canonical report contract."""

    def test_has_english_imrad_headings(self) -> None:
        t = _template()
        for h in (
            "## Abstract",
            "## Introduction",
            "## Method",
            "## Results",
            "## Discussion",
            "### Limitations",
            "### Future Directions",
            "## References",
        ):
            assert h in t, f"apa-template.md missing APA heading '{h}'"

    def test_mandates_axes_and_how_to_read_captions(self) -> None:
        t = _template()
        assert "軸の説明" in t and "図の読み方" in t, (
            "figure captions must be documented"
        )
        assert "figures[N].axes" in t and "figures[N].how_to_read" in t, (
            "figure caption placeholders must map to the manifest fields"
        )

    def test_documents_graceful_degrade(self) -> None:
        t = _template()
        assert "Graceful degrade" in t
        # the degrade trigger the SKILL.md Step 2 relies on
        assert "figures == []" in t


def _section(markdown: str, heading: str) -> str:
    """The body under ``heading`` up to the next heading of the same level."""
    level = heading.split(" ", 1)[0]
    rest = markdown[markdown.index(heading) + len(heading) :]
    end = rest.find(f"\n{level} ")
    return rest if end == -1 else rest[:end]


class TestNumbersTable:
    """US-1 (Epic 12): the Results numbers table shows effect size, CI and sample size."""

    def test_notebook_contract_defines_the_three_optional_items(self) -> None:
        contract = NOTEBOOK_CONTRACT.read_text(encoding="utf-8")
        section = _section(contract, "## Optional metric items")
        for key in OPTIONAL_METRIC_COLUMNS:
            assert f"`{key}`" in section, f"notebook contract must define `{key}`"
        for sub_key in ("kind", "level", "lower", "upper"):
            assert f'"{sub_key}"' in section, f"contract must define '{sub_key}'"
        assert "optional" in section.lower()
        assert "ADR-0013" in section

    def test_template_maps_each_item_to_a_column(self) -> None:
        section = _section(_template(), "## Results numbers table")
        for key, column in OPTIONAL_METRIC_COLUMNS.items():
            assert f"`{key}`" in section, f"numbers table must read `{key}`"
            assert f"| {column} |" in section, f"table must have a '{column}' column"

    def test_template_omits_a_column_no_metric_fills(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "omit the column" in section.lower()

    def test_template_keeps_the_table_for_a_verdict_without_the_items(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "| Metric | Value | Threshold | p | Pass |" in section, (
            "a verdict that predates ADR-0013 must get the table it gets today"
        )
        assert "Graceful degrade" in section

    def test_template_forbids_computing_a_missing_item(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "never compute" in section.lower()

    def test_skill_reads_the_items_and_omits_empty_columns(self) -> None:
        t = _skill()
        for key in OPTIONAL_METRIC_COLUMNS:
            assert f"`{key}`" in t, f"SKILL.md must read `{key}` from verdict.metrics"
        assert "omit the column" in t.lower()
        assert "never compute" in t.lower()


class TestReportSkill:
    """SKILL.md wires the read-only consumer with a terminal-status guard."""

    def test_terminal_status_guard(self) -> None:
        t = _skill()
        for status in ("supported", "rejected", "inconclusive"):
            assert status in t, f"terminal-status guard must mention '{status}'"

    def test_declares_read_only(self) -> None:
        t = _skill()
        assert "read-only" in t, "report must declare itself a read-only consumer"

    def test_figure_file_basename_safety(self) -> None:
        t = _skill()
        assert "basename" in t, "SKILL.md must constrain figures[].file to a basename"


def _skeleton() -> str:
    """The fenced heading skeleton of the report (it contains H2 lines itself)."""
    t = _template()
    start = t.index("```", t.index("## Heading skeleton"))
    return t[start : t.index("\n```\n", start + 3)]


def _commands(text: str, cli: str) -> set[str]:
    """Subcommands of ``cli`` that the text invokes, e.g. ``design_io get``."""
    return set(re.findall(rf"{cli} ([a-z][a-z-]*)", text))


class TestDecisionContextInIntroduction:
    """US-3 AC 1 (Epic 12): the Introduction states who decides what."""

    def test_skeleton_puts_the_decision_context_in_the_introduction(self) -> None:
        skeleton = _skeleton()
        introduction = skeleton[
            skeleton.index("## Introduction") : skeleton.index("## Method")
        ]
        assert "decision_context" in introduction

    def test_template_reads_both_sides_and_omits_when_absent(self) -> None:
        section = _section(_template(), "## Decision context (Introduction)")
        assert "`decision_maker`" in section and "`decision`" in section
        assert "omit" in section.lower()
        assert "ADR-0014" in section

    def test_skill_reads_the_decision_context(self) -> None:
        gather = _section(_skill(), "### Step 2: ")
        assert "`decision_context`" in gather
        assemble = _section(_skill(), "### Step 3: ")
        assert "decision_context" in assemble[: assemble.index("**Method**")]


class TestDataDescriptionInMethod:
    """US-3 AC 2 (Epic 12): Method names the data sources and the row-count changes."""

    def test_skeleton_has_a_data_subsection_under_method(self) -> None:
        skeleton = _skeleton()
        method = skeleton[skeleton.index("## Method") : skeleton.index("## Results")]
        assert "### Data" in method

    def test_template_lists_name_type_and_description_from_the_catalog(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert "catalog_io get" in section
        assert "| Data source | Type | Description |" in section
        for field in ("`name`", "`type`", "`description`"):
            assert field in section, f"data source table must read {field}"

    def test_template_never_transcribes_the_connection(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert "`connection`" in section
        assert "never" in section[section.index("`connection`") - 200 :].lower()

    def test_template_reads_the_row_counts_from_the_lineage_file(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert ".insight/lineage/{id}.mmd" in section
        assert "| Step | Reason | Rows | Change |" in section
        assert "never compute" in section.lower()

    def test_template_omits_what_has_no_material(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert "Graceful degrade" in section
        assert "omit" in section.lower()

    def test_skill_reads_the_catalog_and_the_lineage(self) -> None:
        gather = _section(_skill(), "### Step 2: ")
        assert "catalog_io get --id" in gather
        assert ".insight/lineage/{design_id}.mmd" in gather
        assert "`connection`" in gather


class TestImplicationsAndRecommendation:
    """US-3 AC 3 (Epic 12): the Discussion says what the result means and what to do."""

    def test_discussion_headings_come_in_reading_order(self) -> None:
        skeleton = _skeleton()
        order = [
            skeleton.index(h)
            for h in (
                "## Discussion",
                "### Implications",
                "### Recommendation",
                "### Limitations",
                "### Future Directions",
                "## References",
            )
        ]
        assert order == sorted(order)

    def test_recommendation_is_written_from_next_action_and_decision_context(
        self,
    ) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "`next_action`" in section and "`decision_context`" in section
        for branch in ("if_supported", "if_rejected"):
            assert branch in section, f"Recommendation must map '{branch}'"

    def test_recommendation_is_omitted_when_both_inputs_are_absent(self) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "omit the section" in section.lower()

    def test_recommendation_never_invents_an_action(self) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "never invent" in section.lower()

    def test_skill_reads_next_action_and_assembles_both_sections(self) -> None:
        gather = _section(_skill(), "### Step 2: ")
        assert "`next_action`" in gather
        assemble = _section(_skill(), "### Step 3: ")
        assert "Implications" in assemble and "Recommendation" in assemble
        assert "omit the section" in assemble.lower()


class TestAppendix:
    """US-3 AC 4 (Epic 12): the Appendix carries the lineage diagram and the notebook."""

    def test_skeleton_ends_with_the_appendix(self) -> None:
        skeleton = _skeleton()
        assert skeleton.index("## References") < skeleton.index("## Appendix")

    def test_template_embeds_the_lineage_diagram_as_mermaid(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert ".insight/lineage/{id}.mmd" in section
        assert "```mermaid" in section

    def test_template_gives_the_notebook_path(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert ".insight/notebooks/{id}.py" in section

    def test_template_omits_what_is_missing(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert "Graceful degrade" in section
        assert "omit" in section.lower()

    def test_skill_assembles_the_appendix(self) -> None:
        assemble = _section(_skill(), "### Step 3: ")
        assert "**Appendix**" in assemble
        assert ".insight/notebooks/{design_id}.py" in _skill()


class TestReadOnlyConsumer:
    """US-3 AC 5 (Epic 12): the skill only reads, and never computes a number."""

    def test_only_reading_commands_are_invoked(self) -> None:
        for text in (_skill(), _template()):
            assert _commands(text, "design_io") <= {"get"}
            assert _commands(text, "catalog_io") <= {"get"}

    def test_references_list_only_the_reading_commands(self) -> None:
        t = _skill()
        assert "`get --id ID`" in _section(t, "## design_io Reference")
        assert "`get --id SOURCE`" in _section(t, "## catalog_io Reference")

    def test_the_report_is_the_only_file_written(self) -> None:
        handoff = _section(_skill(), "### Step 4: ")
        assert ".insight/reports/{design_id}.md" in handoff
        assert "only file this skill writes" in handoff

    def test_every_new_input_is_mapped_to_a_section(self) -> None:
        mapping = _section(_template(), "## Input → section mapping")
        for source in (
            "`decision_context`",
            "`next_action`",
            "catalog_io get",
            ".insight/lineage/{id}.mmd",
            ".insight/notebooks/{id}.py",
        ):
            assert source in mapping, f"mapping must name {source}"

    def test_numbers_are_transcribed_not_computed(self) -> None:
        assert "never compute" in _section(_skill(), "### Step 3: ").lower()
        assert "Read, do not write" in _section(_skill(), "### Step 2: ")
