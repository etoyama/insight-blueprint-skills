"""Readers for the parts of the /analysis-auto SKILL.md that several structure tests check."""

from __future__ import annotations

import re

from tests.skills._markdown import section, table_row, unwrap
from tests.skills._skill_text import skill_section, skill_text
from tests.skills.test_skill_structure import _read_skill, split_sections


def auto() -> str:
    """The SKILL.md of /analysis-auto, without its reference files."""
    return _read_skill("analysis-auto")


def auto_all() -> str:
    """The SKILL.md of /analysis-auto and its reference files."""
    return skill_text("analysis-auto")


def step_item_text(step: str, name: str) -> str:
    """The numbered item ``N. **name**`` under the heading *step*, as written.

    It ends at the next item or heading, so its commands keep their lines.
    """
    found = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,4}} |\Z)",
        auto_step(step),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"{step} has no '{name}' item"
    return found.group(0)


def step_item(step: str, name: str) -> str:
    """The item of ``step_item_text`` with its wrapped lines joined."""
    return unwrap(step_item_text(step, name))


def round_item(name: str) -> str:
    """An item of the round of one node (Step 3)."""
    return step_item("### Step 3:", name)


def handover_item(name: str) -> str:
    """An item of the round of several nodes (Step 3H)."""
    return step_item("### Step 3H:", name)


def handover_item_text(name: str) -> str:
    """An item of the round of several nodes (Step 3H), as written."""
    return step_item_text("### Step 3H:", name)


def handover_part(heading: str) -> str:
    """The body under a ``####`` heading of Step 3H or of the brief, as written."""
    return skill_section("analysis-auto", heading)


def design_beat(name: str) -> str:
    """The numbered design beat ``N. **name**`` of the round's design item."""
    found = re.search(
        rf"^\s+\d\. \*\*{re.escape(name)}\*\*.*?(?=^\s+\d\. \*\*|^\s*After all)",
        auto(),
        re.M | re.S,
    )
    assert found, f"no design beat named {name!r}"
    return unwrap(found.group(0))


def gate_row(step: str) -> list[str]:
    """The cells of the Gate policy row whose first cell is ``step``."""
    return table_row(split_sections(auto())["Gate policy"], step)


def auto_gates() -> str:
    """The Gate policy section of /analysis-auto."""
    return split_sections(auto())["Gate policy"]


def auto_step(heading: str) -> str:
    """The body under a heading of /analysis-auto, from the file that holds it."""
    return skill_section("analysis-auto", heading)


def framing_section(heading: str) -> str:
    """The body under a heading of /analysis-framing."""
    return section(_read_skill("analysis-framing"), heading)
