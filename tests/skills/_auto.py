"""Readers for the parts of the /analysis-auto SKILL.md that several structure tests check."""

from __future__ import annotations

import re

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill, split_sections


def auto() -> str:
    return _read_skill("analysis-auto")


def step_item(step: str, name: str) -> str:
    """The numbered item ``N. **name**`` under the heading *step*, up to the next item or heading."""
    found = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,4}} |\Z)",
        section(auto(), step),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"{step} has no '{name}' item"
    return unwrap(found.group(0))


def round_item(name: str) -> str:
    """An item of the round of one node (Step 3)."""
    return step_item("### Step 3:", name)


def handover_item(name: str) -> str:
    """An item of the round of several nodes (Step 3H)."""
    return step_item("### Step 3H:", name)


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
