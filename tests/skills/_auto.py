"""Readers for the parts of the /analysis-auto SKILL.md that several structure tests check."""

from __future__ import annotations

import re

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill, split_sections


def auto() -> str:
    return _read_skill("analysis-auto")


def round_item(name: str) -> str:
    """The numbered item ``N. **name**`` of the round, up to the next item or heading."""
    found = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,4}} |\Z)",
        section(auto(), "### Step 3:"),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"the round has no '{name}' item"
    return unwrap(found.group(0))


def handover_item(name: str) -> str:
    """The numbered item ``N. **name**`` of Step 3H, up to the next item or heading."""
    found = re.search(
        rf"^\d+\. \*\*{re.escape(name)}\*\*.*?(?=^\d+\. \*\*|^#{{2,4}} |\Z)",
        section(auto(), "### Step 3H:"),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"Step 3H has no '{name}' item"
    return unwrap(found.group(0))


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
