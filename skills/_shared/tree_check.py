"""Check the current answers of a question tree against the journal (Epic 18, ADR-0025).

An answer may only state a number that a cited journal event records, and may
only cite events that exist. This module only reads: it never writes the tree.

Usage from a skill (CLI):
    tree_check --theme LIB [--base-dir .insight]

Exit 0: no violation. Exit 1: violations found. Exit 2: the check could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

from insight_blueprint.models.tree import AnswerStatement, QuestionTree, design_id_of
from skills._shared.design_io import DEFAULT_BASE_DIR, resolve_base_dir
from skills._shared.tree_render import CitedEvent

# The dashes and triangles writers use for "down" all read as one minus: a
# glyph left out passes as an unsigned number. The wave dash is left out
# on purpose, since it only ever writes a range.
_MINUS = "-‐‒–—―−▲△▼▽"
# A sign right after an ASCII letter or digit is the hyphen of a range (10-20),
# a date or an id (A-3), not a sign. Spaces may part the sign from its digits.
_NUMBER = re.compile(
    rf"(?:(?<![0-9A-Za-z])(?P<sign>[{_MINUS}+])\s*)?"
    r"(?P<digits>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
)

Sign = Literal["", "+", "-"]


@dataclass(frozen=True)
class Number:
    """Two numbers are the same when sign and value agree, however they are spelled."""

    token: str = field(compare=False)
    sign: Sign
    value: Decimal  # the magnitude; the direction is in sign


def numbers_in(text: str) -> list[Number]:
    """Numbers in *text*, compared by sign and value: unit and spelling do not count.

    A converted or rounded value is a different number, so an answer cannot pass
    by computing one. A written sign is part of the number: the direction of a
    change is a claim, so "-3.2" passes only when a record wrote it with a minus.
    """
    return [
        Number(
            m.group(),
            _sign_of(m.group("sign")),
            Decimal(m.group("digits").replace(",", "")),
        )
        for m in _NUMBER.finditer(unicodedata.normalize("NFKC", text))
    ]


def _sign_of(written: str | None) -> Sign:
    if written is None:
        return ""
    return "+" if written == "+" else "-"


ViolationKind = Literal["missing-event", "unlinked-design", "number-not-cited"]


@dataclass(frozen=True)
class Violation:
    node_id: str
    round: int
    statement: int  # 1-based position in the answer
    kind: ViolationKind
    text: str


def find_violations(tree: QuestionTree, events: Mapping[str, str]) -> list[Violation]:
    """Violations of the last answer of every node.

    *events* maps the id of each journal event that exists to its content text.
    Earlier rounds are history that cannot be rewritten, so they are not checked.
    """
    designs = tree.designs_by_branch()
    violations: list[Violation] = []
    for node in tree.nodes:
        answer = node.current_answer()
        if answer is None:
            continue
        for position, statement in enumerate(answer.statements, start=1):
            found = _statement_problems(statement, events, designs[node.id])
            violations += [
                Violation(node.id, answer.round, position, kind, text)
                for kind, text in found
            ]
    return violations


def _statement_problems(
    statement: AnswerStatement, events: Mapping[str, str], linked: set[str]
) -> list[tuple[ViolationKind, str]]:
    problems: list[tuple[ViolationKind, str]] = []
    for cite in statement.cites:
        if cite not in events:
            problems.append(("missing-event", cite))
        if design_id_of(cite) not in linked:
            problems.append(("unlinked-design", cite))
    seen = {
        number
        for cite in statement.cites
        if cite in events
        for number in numbers_in(events[cite])
    }
    for number in numbers_in(statement.text):
        if number not in seen:
            seen.add(number)
            problems.append(("number-not-cited", number.token))
    return problems


def check_theme(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> list[Violation]:
    """Load the tree of *theme_id* and the journals its answers cite, then check.

    Raises ValueError for an invalid theme id, a missing tree, a tree that
    fails its schema or names another theme, or a cited event id that two
    events share, and OSError or YAMLError for a file that cannot be read.
    """
    from skills._shared.tree_io import load_tree_model  # tree_io imports this

    return check_tree(load_tree_model(theme_id, base_dir), base_dir)


def check_tree(tree: QuestionTree, base_dir: Path) -> list[Violation]:
    """Check a tree already in memory against the journals under *base_dir*."""
    from skills._shared.tree_io import cited_events  # tree_io imports this

    return check_cited(tree, *cited_events(_current_cites(tree), base_dir))


def check_cited(
    tree: QuestionTree, events: Mapping[str, CitedEvent], duplicated: Iterable[str]
) -> list[Violation]:
    """Check *tree* against cited events already read (``tree_io.cited_events``).

    *events* may hold more than the current answers cite. A cited id that two
    events share raises ValueError: which of them backs the answer is unknown.
    """
    current = _current_cites(tree)
    for event_id in duplicated:
        if event_id in current:
            raise ValueError(
                f"journal event '{event_id}' appears twice in the journal "
                f"of {design_id_of(event_id)}"
            )
    return find_violations(tree, {i: e.content for i, e in events.items()})


def _current_cites(tree: QuestionTree) -> set[str]:
    return {
        cite
        for node in tree.nodes
        if (answer := node.current_answer()) is not None
        for statement in answer.statements
        for cite in statement.cites
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_check")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    args = parser.parse_args(argv)
    from skills._shared.tree_io import tree_path  # tree_io imports this

    # Exit 2, not 1: for this command 1 means "violations found".
    try:
        base = resolve_base_dir(Path(args.base_dir))
        violations = check_theme(args.theme, base)
        path = tree_path(args.theme, base)
    except Exception as exc:
        # Python would end an uncaught error with exit 1, which a caller reads
        # as "violations found" and tries to fix by rewriting the answer.
        print(f"tree_check: {exc}", file=sys.stderr)
        return 2

    json.dump(
        {"tree": str(path), "violations": [asdict(v) for v in violations]},
        sys.stdout,
        ensure_ascii=False,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(_main())
