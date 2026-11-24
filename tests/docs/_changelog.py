"""Find a CHANGELOG entry by a phrase in it, not by its heading.

A release renames `## [Unreleased]` to `## [X.Y.Z] - date`, and the next Epic opens a
new `[Unreleased]`. A test that names either heading has to be rewritten at one of the
two, so a structure test looks its notes up with ``changelog_entry`` instead.
"""

from __future__ import annotations

import re

from tests.skills._markdown import section, unwrap

_ENTRY = re.compile(r"^## \[[^\]]+\].*$", re.MULTILINE)


def changelog_entry(changelog: str, phrase: str) -> str:
    """The body of the one `## [...]` entry whose text contains ``phrase``.

    Line breaks do not count, so ``phrase`` may span a wrapped line. A phrase in no
    entry, or in two, fails: in two, the test cannot tell which notes it means, and a
    longer phrase picks one.
    """
    found = [
        (heading, body)
        for heading in _ENTRY.findall(changelog)
        if phrase in unwrap(body := section(changelog, heading))
    ]
    if not found:
        raise AssertionError(f"no CHANGELOG entry contains {phrase!r}")
    if len(found) > 1:
        headings = ", ".join(heading for heading, _ in found)
        raise AssertionError(
            f"{phrase!r} is in more than one CHANGELOG entry: {headings}"
        )
    return found[0][1]
