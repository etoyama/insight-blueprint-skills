"""Readers for the parts of /analysis-reflection that several structure tests check.

The theme reflection (Steps T1 to T7) lives in ``references/theme-reflection.md``; the
reflection on one design stays in SKILL.md.
"""

from __future__ import annotations

from tests.skills._skill_text import skill_section, skill_text
from tests.skills.test_skill_structure import _read_skill


def reflection() -> str:
    """The SKILL.md of /analysis-reflection, without its reference files."""
    return _read_skill("analysis-reflection")


def reflection_all() -> str:
    """The SKILL.md of /analysis-reflection and its reference files."""
    return skill_text("analysis-reflection")


def reflection_section(heading: str) -> str:
    """The body under a heading of /analysis-reflection, from the file that holds it."""
    return skill_section("analysis-reflection", heading)
