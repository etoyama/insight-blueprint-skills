"""Structure tests for the canonical documents (Epic 11, docs/design/epic-11-repo-template-compliance.md).

docs/WORKFLOW.md §2 says each piece of information has one canonical home and
CLAUDE.md only points at them. These tests catch the drift that rule cannot:
dead links, a canonical body copied back into CLAUDE.md, and names that no longer
exist in the code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _h2_titles(text: str) -> list[str]:
    return [
        re.sub(r"^\d+\.\s*", "", line[3:].strip())
        for line in text.splitlines()
        if line.startswith("## ")
    ]


def _dead_links(rel: str) -> list[str]:
    base = (REPO_ROOT / rel).parent
    dead = []
    for target in _LINK.findall(_read(rel)):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if not (base / path).exists():
            dead.append(target)
    return dead


class TestClaudeMd:
    """US-1: CLAUDE.md holds only a summary and pointers."""

    def test_has_the_repo_template_sections(self) -> None:
        titles = _h2_titles(_read("CLAUDE.md"))
        for expected in (
            "Documents",
            "Development Workflow",
            "ADR",
            "Coding Principles",
            "Rules and Templates",
            "Language",
        ):
            assert any(t.startswith(expected) for t in titles), expected

    def test_does_not_hold_canonical_bodies(self) -> None:
        text = _read("CLAUDE.md")
        titles = _h2_titles(text)
        assert not any(
            t.startswith(("Skills", "Skill-Managed Data", "Validation Guard"))
            for t in titles
        )
        assert not re.search(r"^\|\s*`/[a-z-]+`\s*\|", text, re.MULTILINE), (
            "Skills table belongs to README"
        )

    def test_relative_links_resolve(self) -> None:
        assert _dead_links("CLAUDE.md") == []

    def test_code_review_names_tools_that_exist(self) -> None:
        text = _read("CLAUDE.md")
        assert "orchestra:team-review" not in text
        assert "thermos" in text
        assert "/code-review" in text


class TestContributing:
    """US-1 AC 4: CONTRIBUTING.md keeps only the repo-specific sections."""

    def test_has_only_the_four_sections(self) -> None:
        titles = _h2_titles(_read("CONTRIBUTING.md"))
        assert titles == ["Setup", "Common Commands", "Testing", "Security Checklist"]

    def test_relative_links_resolve(self) -> None:
        assert _dead_links("CONTRIBUTING.md") == []


MODEL_FILES = [
    *sorted((REPO_ROOT / "src/insight_blueprint/models").glob("*.py")),
    REPO_ROOT / "skills/_shared/models.py",
]
EPIC_DOCS = sorted((REPO_ROOT / "docs/design").glob("epic-*.md"))
REMOVED_FEATURE_TERMS = (
    "WebUI",
    "REST API",
    "MCP server",
    "MCP サーバ",
    "SQLite",
    "batch-analysis",
)


def _section(text: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert match, f"section '## {title}' not found"
    return match.group(1)


def _model_class_names() -> set[str]:
    names: set[str] = set()
    for path in MODEL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names |= {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    return names


def _terms_rows() -> list[list[str]]:
    body = _section(_read("docs/UBIQUITOUS_LANGUAGE.md"), "Terms")
    rows = [line for line in body.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


class TestRoadmap:
    """US-2 AC 1, AC 2: every Epic DesignDoc is on the PRD roadmap and the ARCHITECTURE Epic mapping."""

    def test_prd_roadmap_links_every_epic(self) -> None:
        roadmap = _section(_read("docs/PRD.md"), "ロードマップ")
        missing = [p.name for p in EPIC_DOCS if f"design/{p.name}" not in roadmap]
        assert missing == []

    def test_architecture_epic_mapping_links_every_epic(self) -> None:
        mapping = _section(_read("docs/ARCHITECTURE.md"), "Epic マッピング")
        missing = [p.name for p in EPIC_DOCS if f"design/{p.name}" not in mapping]
        assert missing == []

    def test_architecture_has_a_context_map(self) -> None:
        assert "コンテキストマップ" in _h2_titles(_read("docs/ARCHITECTURE.md"))

    def test_relative_links_resolve(self) -> None:
        for rel in (
            "docs/PRD.md",
            "docs/ARCHITECTURE.md",
            "docs/UBIQUITOUS_LANGUAGE.md",
        ):
            assert _dead_links(rel) == [], rel


class TestDomainModelDiagram:
    """US-2 AC 3: the overall classDiagram lists exactly the model classes in the code."""

    def test_class_diagram_matches_the_model_classes(self) -> None:
        section = _section(_read("docs/ARCHITECTURE.md"), "Domain Model")
        diagram = re.search(
            r"```mermaid\s*\nclassDiagram\n(.*?)```", section, re.DOTALL
        )
        assert diagram, "classDiagram block not found"
        drawn = set(re.findall(r"^\s*class (\w+)", diagram.group(1), re.MULTILINE))
        assert drawn == _model_class_names()


class TestUbiquitousLanguage:
    """US-2 AC 4, AC 5: the first edition holds domain terms whose code names exist."""

    def test_context_is_filled_in(self) -> None:
        text = _read("docs/UBIQUITOUS_LANGUAGE.md")
        assert "<コンテキスト名>" not in text
        assert "雛形" not in text

    def test_code_names_exist_in_the_code(self) -> None:
        code = "\n".join(
            p.read_text(encoding="utf-8")
            for root in ("src", "skills")
            for p in (REPO_ROOT / root).rglob("*")
            if p.is_file() and p.suffix in {".py", ".md"}
        )
        missing = [
            name
            for row in _terms_rows()
            for name in re.findall(r"`([^`]+)`", row[1])
            if name not in code
        ]
        assert missing == []

    def test_has_no_removed_feature_terms(self) -> None:
        for row in _terms_rows():
            for term in REMOVED_FEATURE_TERMS:
                assert term not in " ".join(row[:3]), (term, row[0])

    def test_analysis_design_is_the_canonical_term(self) -> None:
        rows = {row[0]: row for row in _terms_rows()}
        assert "分析設計" in rows
        assert "設計書" in rows["分析設計"][3]
