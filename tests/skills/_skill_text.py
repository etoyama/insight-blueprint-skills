"""Read a skill's prose where it is written: its SKILL.md or one of its reference files.

A long part of a SKILL.md that only some rounds need lives in ``references/`` (Epic 36,
US-7). A structure test asks for a heading and gets the body under it from the file that
holds it, so the test checks the moved sentences and never the pointer left in the body.
"""

from __future__ import annotations

from pathlib import Path

from tests.skills._markdown import section
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill


def references(skill: str) -> list[Path]:
    return sorted((SKILLS_DIR / skill / "references").glob("*.md"))


def skill_text(skill: str) -> str:
    """The SKILL.md and its reference files, for a check that holds the whole skill."""
    return "\n".join(
        [_read_skill(skill)]
        + [p.read_text(encoding="utf-8") for p in references(skill)]
    )


def skill_section(skill: str, heading: str) -> str:
    """The body under ``heading``, read from the reference file that holds it, else SKILL.md.

    A moved part leaves its heading in SKILL.md with a pointer under it, so the reference
    is read first. ``heading`` must name one heading line: ``### Step 3`` would match both
    ``### Step 3:`` in SKILL.md and ``### Step 3H:`` in a reference, and is refused.
    """
    texts = [p.read_text(encoding="utf-8") for p in references(skill)]
    texts.append(_read_skill(skill))
    matched = {
        line
        for text in texts
        for line in text.splitlines()
        if line.startswith("#") and line.startswith(heading)
    }
    assert len(matched) <= 1, f"{heading!r} names several headings: {sorted(matched)}"
    for text in texts:
        if any(line.startswith(heading) for line in text.splitlines()):
            return section(text, heading)
    raise AssertionError(f"{skill} has no heading that starts with {heading!r}")
