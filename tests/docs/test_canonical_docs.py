"""Structure tests for the canonical documents (Epic 11, docs/design/epic-11-repo-template-compliance.md).

docs/WORKFLOW.md §2 says each piece of information has one canonical home and
CLAUDE.md only points at them. These tests catch the drift that rule cannot:
dead links, a canonical body copied back into CLAUDE.md, and names that no longer
exist in the code.
"""

from __future__ import annotations

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
