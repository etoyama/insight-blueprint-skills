"""Structure tests for removing the old report (Epic 29, Story 29.5, US-5).

The report is now the final report of a theme, written by `tree_io report --theme` and
exported by `/report-export` (ADR-0039, ADR-0040). The per-design report, its upload, its
template and its checker leave in one step (Decision `the-old-report-leaves-in-one-step`),
so these tests guard that nothing shipped still names them. The roadmap of the PRD and the
Epic mapping of the architecture are history and keep the old names.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared.design_note import LOCAL_FILES
from tests.skills._auto import auto, gate_row, round_item
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import (
    _extract_chaining_edges,
    split_sections,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_NAMES = re.compile(r"/analysis-report|/report-upload|report_check|apa-template")

# Sections that record what earlier Epics did; they keep the names of that time.
_HISTORY = {
    "docs/PRD.md": "## ロードマップ",
    "docs/ARCHITECTURE.md": "## Epic マッピング",
}


def _without_history(path: str) -> str:
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    heading = _HISTORY.get(path)
    return text.replace(section(text, heading), "") if heading else text


def _shipped_files() -> list[Path]:
    roots = [REPO_ROOT / "skills", REPO_ROOT / "bin", REPO_ROOT / ".claude-plugin"]
    return sorted(
        p
        for root in roots
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )


class TestTheOldReportIsGone:
    """AC 1: the two skills, the template and the checker are removed."""

    @pytest.mark.parametrize(
        "path",
        [
            "skills/analysis-report",
            "skills/report-upload",
            "bin/report_check",
            "skills/_shared/report_check.py",
            "tests/test_report_check.py",
        ],
    )
    def test_the_old_file_does_not_exist(self, path: str) -> None:
        assert not (REPO_ROOT / path).exists()

    def test_no_shipped_file_names_the_old_report(self) -> None:
        named = [
            str(p.relative_to(REPO_ROOT))
            for p in _shipped_files()
            if OLD_NAMES.search(p.read_text(encoding="utf-8", errors="ignore"))
        ]
        assert named == []

    @pytest.mark.parametrize(
        "path",
        [
            "README.md",
            "docs/ARCHITECTURE.md",
            "docs/PRD.md",
            "docs/UBIQUITOUS_LANGUAGE.md",
        ],
    )
    def test_the_canonical_document_names_the_old_report_only_as_history(
        self, path: str
    ) -> None:
        assert OLD_NAMES.findall(_without_history(path)) == []


class TestTheAutopilotOnlyNamesTheExport:
    """AC 2: /analysis-auto has no report or upload step and names /report-export."""

    @pytest.mark.parametrize("step", ["report", "upload"])
    def test_the_gate_policy_has_no_step(self, step: str) -> None:
        with pytest.raises(AssertionError):
            gate_row(step)

    @pytest.mark.parametrize("item", ["report", "upload"])
    def test_the_round_has_no_item(self, item: str) -> None:
        with pytest.raises(AssertionError):
            round_item(item)

    def test_the_round_goes_from_the_reflection_to_the_theme_reflection(
        self,
    ) -> None:
        walk = section(auto(), "### Step 3:")
        assert walk.index("7. **reflection**") < walk.index("8. **theme reflection**")
        assert "9. **next round**" in walk

    def test_a_concluded_position_enters_the_theme_reflection(self) -> None:
        located = section(auto(), "### Step 1:")
        row = next(ln for ln in located.splitlines() if "`concluded`" in ln)
        assert row.rstrip(" |").endswith("Step 3, item 8")

    def test_carrying_one_design_runs_up_to_its_reflection(self) -> None:
        build = unwrap(section(auto(), "### Step 2:"))
        assert re.search(
            r"only this design[^.]*items 2[–-]7[^.]*no item 1, 8 or 9", build
        )

    def test_the_summary_names_the_export_after_the_theme_reflection(self) -> None:
        summary = unwrap(section(auto(), "### Step 4:"))
        assert "`/report-export {theme_id}`" in summary
        assert re.search(r"never start it[^.]*do not ask whether to export", summary)
        assert "ADR-0040" in summary

    def test_the_export_is_not_an_edge_of_the_chaining(self) -> None:
        # Naming the skill is a hint, not a chain: only the analyst starts the export.
        targets = [to for _, to in _extract_chaining_edges("analysis-auto")]
        assert "report-export" not in targets

    def test_the_export_is_not_a_delegated_skill(self) -> None:
        assert "/report-export" not in split_sections(auto())["Delegated skills"]


class TestTheNoteNoLongerLinksTheReport:
    """AC 3: the analysis note's local files carry no report."""

    def test_local_files_have_no_report(self) -> None:
        assert [path for _, path in LOCAL_FILES if path.startswith("reports/")] == []
        assert "レポート" not in [label for label, _ in LOCAL_FILES]

    def test_the_template_comparison_is_gone(self) -> None:
        assert not (
            REPO_ROOT / "tests" / "skills" / "test_design_note_report_structure.py"
        ).exists()
