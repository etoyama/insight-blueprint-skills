"""Structural validation for the /analysis-report skill's prose contract (Epic 10).

The report skill is Claude-native (assembly logic lives in prose, not Python), so these
tests guard the load-bearing contract in SKILL.md + apa-template.md the same way
TestFramingBrief guards analysis-framing's output template: the mandatory figure captions
(ADR-0008), the graceful-degrade branch, the English APA headings, and the terminal-status
precondition. Without these, a heading or caption field could silently rot.
"""

from __future__ import annotations

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
