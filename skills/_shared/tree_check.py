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
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from insight_blueprint.models.tree import AnswerStatement, QuestionTree, design_id_of
from skills._shared.design_io import DEFAULT_BASE_DIR, _resolve_base_dir
from skills._shared.tree_io import _tree_path, cited_journal_events, load_tree_model

_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Number:
    token: str
    value: Decimal


def numbers_in(text: str) -> list[Number]:
    """Numbers in *text*, compared by value: unit, sign and spelling do not count.

    A converted or rounded value is a different number, so an answer cannot pass
    by computing one.
    """
    return [
        Number(m.group(), Decimal(m.group().replace(",", "")))
        for m in _NUMBER.finditer(unicodedata.normalize("NFKC", text))
    ]


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
    designs = _designs_by_branch(tree)
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
        n.value
        for cite in statement.cites
        if cite in events
        for n in numbers_in(events[cite])
    }
    for number in numbers_in(statement.text):
        if number.value not in seen:
            seen.add(number.value)
            problems.append(("number-not-cited", number.token))
    return problems


def _designs_by_branch(tree: QuestionTree) -> dict[str, set[str]]:
    """For each node, the designs linked to it or to any node below it."""
    children: dict[str, list[str]] = {}
    for node in tree.nodes:
        if node.parent_question_id is not None:
            children.setdefault(node.parent_question_id, []).append(node.id)
    own = {n.id: set(n.design_ids) for n in tree.nodes}

    def branch(node_id: str) -> set[str]:
        return own[node_id].union(*(branch(c) for c in children.get(node_id, [])))

    return {n.id: branch(n.id) for n in tree.nodes}


def check_theme(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> list[Violation]:
    """Load the tree of *theme_id* and the journals its answers cite, then check.

    Raises ValueError for an invalid theme id, a missing tree, a tree that
    fails its schema or names another theme, or a cited event id that two
    events share, and OSError or YAMLError for a file that cannot be read.
    """
    tree = load_tree_model(theme_id, base_dir)
    return find_violations(tree, _cited_events(tree, base_dir))


def _cited_events(tree: QuestionTree, base_dir: Path) -> dict[str, str]:
    """Content text of each cited event that exists in its design's journal."""
    cited = {
        cite
        for node in tree.nodes
        if (answer := node.current_answer()) is not None
        for statement in answer.statements
        for cite in statement.cites
    }
    events: dict[str, str] = {}
    for event in cited_journal_events(cited, base_dir):
        event_id = event["id"]
        if event_id in events:
            raise ValueError(
                f"journal event '{event_id}' appears twice in the journal "
                f"of {design_id_of(event_id)}"
            )
        content = event.get("content")
        # A hand-written "content: 34.6" loads as a float, not as text.
        events[event_id] = "" if content is None else str(content)
    return events


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_check")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    args = parser.parse_args(argv)

    # Exit 2, not 1: for this command 1 means "violations found".
    try:
        base = _resolve_base_dir(Path(args.base_dir))
        violations = check_theme(args.theme, base)
        tree_path = _tree_path(args.theme, base)
    except Exception as exc:
        # Python would end an uncaught error with exit 1, which a caller reads
        # as "violations found" and tries to fix by rewriting the answer.
        print(f"tree_check: {exc}", file=sys.stderr)
        return 2

    json.dump(
        {"tree": str(tree_path), "violations": [asdict(v) for v in violations]},
        sys.stdout,
        ensure_ascii=False,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(_main())
