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
