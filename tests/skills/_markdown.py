"""Markdown helpers shared by the structure tests of the skills' prose.

The structure tests assert on sentences inside one section of a SKILL.md or a
reference file. They all need the same three things: cut a section out, read a
sentence regardless of where its line breaks, and pick a table row by its first cell.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*(`{3,})(.*)$")
_HEADING = re.compile(r"^(#{1,6}) ")


def unwrap(prose: str) -> str:
    """Join wrapped lines, so an assertion reads the sentence and not where it breaks."""
    return re.sub(r"\s+", " ", prose)


def section(markdown: str, heading: str) -> str:
    """The body under the heading line that starts with ``heading``.

    The body ends at the next heading of the same or a higher level. Lines inside a
    fenced code block are never headings, so a ``# comment`` or a sample heading in a
    fence does not cut the section short.
    """
    depth = len(heading.split(" ", 1)[0])
    lines = markdown.splitlines(keepends=True)
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(heading)),
        None,
    )
    if start is None:
        raise AssertionError(f"no heading starts with {heading!r}")

    body: list[str] = []
    fence: str | None = None
    for line in lines[start + 1 :]:
        opened = _FENCE.match(line)
        if fence is None:
            if opened:
                fence = opened.group(1)
            else:
                found = _HEADING.match(line)
                if found and len(found.group(1)) <= depth:
                    break
        elif opened and len(opened.group(1)) >= len(fence) and not opened.group(2):
            fence = None
        body.append(line)
    return "".join(body)


def bold_item(markdown: str, label: str) -> str:
    """The first list item ``- **label**`` of ``markdown``, with its nested lines.

    The item ends at the first non-blank line indented no deeper than its ``-``: its
    next sibling, an item or paragraph further out, or a heading. Nested bullets and
    paragraphs indented under the item stay inside it.
    """
    lines = markdown.splitlines(keepends=True)
    opener = re.compile(rf"^ *- \*\*{re.escape(label)}\*\*")
    start = next((i for i, line in enumerate(lines) if opener.match(line)), None)
    if start is None:
        raise AssertionError(f"no list item - **{label}**")
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip(" ")) <= indent
        ),
        len(lines),
    )
    return "".join(lines[start:end])


def table_rows(markdown: str) -> list[list[str]]:
    """The cells of every table row in ``markdown``, header and separator rows included."""
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.strip().startswith("|")
    ]


def table_row(markdown: str, first_cell: str) -> list[str]:
    """The cells of the table row whose first cell is ``first_cell``."""
    for cells in table_rows(markdown):
        if cells[0] == first_cell:
            return cells
    raise AssertionError(f"no table row starts with {first_cell!r}")
