"""Structure tests for the parts of a SKILL.md kept in its reference files (Epic 36, US-7).

The dialogue agent reads a SKILL.md whole every time. A long part that only some rounds
need lives in the skill's ``references/``, and the body says when to read it. These tests
hold the moved parts to one place and the links between body and reference to paths that
resolve from where Claude Code loads the plugin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

_LINK = re.compile(r"\]\(([^)\s]+)\)")
_HEADING = re.compile(r"^#{2,4} .+$", re.MULTILINE)

# (skill, reference file, the body heading that points to it)
MOVED = [
    ("analysis-auto", "handover.md", "### Step 3H:"),
    ("analysis-auto", "execution-brief.md", "### Step 3H:"),
    ("analysis-reflection", "theme-reflection.md", "## Theme Reflection"),
]


def _reference(skill: str, name: str) -> str:
    return (SKILLS_DIR / skill / "references" / name).read_text(encoding="utf-8")


def _prose() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md")) + sorted(
        SKILLS_DIR.glob("*/references/*.md")
    )


@pytest.mark.parametrize(("skill", "name", "heading"), MOVED)
class TestAMovedPartIsReadFromItsReference:
    """US-7 AC 1: the body says when to read the reference and links it."""

    def test_the_body_links_the_reference_under_its_heading(
        self, skill: str, name: str, heading: str
    ) -> None:
        assert f"](references/{name})" in section(_read_skill(skill), heading)

    def test_the_body_says_when_to_read_it(
        self, skill: str, name: str, heading: str
    ) -> None:
        pointer = unwrap(section(_read_skill(skill), heading))
        assert re.search(
            rf"(Read|read)[^.]*\[[^]]+\]\(references/{re.escape(name)}\)[^.]*"
            r"\b(when|before|whenever)\b",
            pointer,
        ), pointer

    def test_the_part_is_written_in_one_place_only(
        self, skill: str, name: str, heading: str
    ) -> None:
        body = _read_skill(skill)
        moved = set(_HEADING.findall(_reference(skill, name))) - {
            line for line in _HEADING.findall(body) if line.startswith(heading)
        }
        assert moved, f"{name} holds no heading"
        assert [h for h in moved if h in body.splitlines()] == []


def test_every_reference_is_named_by_its_skill() -> None:
    orphans = [
        ref.relative_to(SKILLS_DIR).as_posix()
        for ref in sorted(SKILLS_DIR.glob("*/references/*.md"))
        if f"references/{ref.name}" not in _read_skill(ref.parents[1].name)
    ]
    assert orphans == []


@pytest.mark.parametrize(
    "path", _prose(), ids=lambda p: p.relative_to(SKILLS_DIR).as_posix()
)
def test_relative_links_resolve_from_the_file(path: Path) -> None:
    dead = [
        target
        for target in _LINK.findall(path.read_text(encoding="utf-8"))
        if not target.startswith(("http://", "https://", "mailto:", "#"))
        and not (path.parent / target.split("#", 1)[0]).exists()
    ]
    assert dead == []


def test_a_round_of_one_node_reads_how_to_stop_an_analysis() -> None:
    """The stop is asked in a round of one node as well, and its steps are in handover.md."""
    pointer = unwrap(section(_read_skill("analysis-auto"), "### Step 3H:"))
    assert re.search(
        r"\[references/handover\.md\]\(references/handover\.md\)[^.]*"
        r"the analyst asks to stop an analysis",
        pointer,
    ), pointer
