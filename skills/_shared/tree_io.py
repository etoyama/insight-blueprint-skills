"""YAML I/O for the question tree of a theme (Epic 18, ADR-0024).

The canonical file is ``.insight/themes/{theme_id}_tree.yaml``. Skills call this
instead of writing the file themselves. Every write is checked against the
``QuestionTree`` schema first (``insight_blueprint.validate.validate_tree_schema``):
the pre-write hook only guards the Write/Edit tool path, not direct python writes.

Progress is never written. ``progress`` derives it from the status of the
designs linked to each node.

``render`` writes the generated view ``{theme_id}_tree.html`` next to the
canonical file. The page is built by ``tree_render`` and is never edited.

Usage from a skill (CLI):
    echo '<json>' | python -m skills._shared.tree_io create --base-dir .insight
    echo '{"answers": [...]}' | python -m skills._shared.tree_io answer --theme LIB

Exit 0: done. Exit 1: error (message on stderr). Exit 3 (answer only): the check
found violations, so nothing was written; they are in the JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ruamel.yaml import YAMLError

from insight_blueprint.models.common import THEME_ID_PATTERN, now_jst
from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.tree import Progress, QuestionTree, design_id_of
from insight_blueprint.validate import validate_tree_schema
from skills._shared._atomic import atomic_write_text, atomic_write_yaml
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    _designs_dir,
    _resolve_base_dir,
    load_design,
    load_journal,
    read_yaml,
)
from skills._shared.tree_render import CitedEvent, DesignSummary, render_tree_html


def _tree_path(theme_id: str, base_dir: Path) -> Path:
    # theme_id becomes part of a path, so it is checked before any I/O.
    if not THEME_ID_PATTERN.fullmatch(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    return Path(base_dir) / "themes" / f"{theme_id}_tree.yaml"


def load_tree(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Load ``{theme_id}_tree.yaml`` as a dict; {} if absent."""
    return read_yaml(_tree_path(theme_id, base_dir))


def _require_tree(theme_id: str, base_dir: Path) -> dict:
    tree = load_tree(theme_id, base_dir)
    if not tree:
        raise ValueError(f"Theme '{theme_id}' has no question tree")
    return tree


def _named_like_its_file(model: QuestionTree, theme_id: str) -> QuestionTree:
    if model.theme_id != theme_id:
        raise ValueError(
            f"theme_id: '{model.theme_id}' does not match the file name "
            f"({theme_id}_tree.yaml)"
        )
    return model


def load_tree_model(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> QuestionTree:
    """The validated tree of *theme_id*.

    Raises ValueError for an invalid theme id, a missing tree, a tree that
    fails its schema, or a tree that names another theme.
    """
    return _named_like_its_file(
        validate_tree_schema(_require_tree(theme_id, base_dir)), theme_id
    )


def _write_tree(tree: dict, theme_id: str, base_dir: Path) -> dict:
    """Validate *tree*, write it to the file of *theme_id*, and return it.

    An invalid tree raises pydantic ``ValidationError`` (a ValueError) and
    nothing is written. The path comes from the caller's theme, never from the
    file content, so a file that names another theme cannot redirect the write.
    """
    model = _named_like_its_file(validate_tree_schema(tree), theme_id)
    data = model.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    atomic_write_yaml(_tree_path(theme_id, base_dir), data)
    return data


def _node(tree: dict, node_id: str) -> dict:
    for node in tree["nodes"]:
        if node["id"] == node_id:
            return node
    raise ValueError(f"node '{node_id}' not found in the tree of {tree['theme_id']}")


def create_tree(
    *, theme_id: str, question: str, aim: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Create the tree of a theme with its root question and first root revision."""
    if _tree_path(theme_id, base_dir).exists():
        raise ValueError(f"The question tree of theme '{theme_id}' already exists")
    revision = {
        "revision": 1,
        "question": question,
        "aim": aim,
        "created_at": now_jst().isoformat(),
    }
    tree = {
        "theme_id": theme_id,
        "root_revisions": [revision],
        "nodes": [{"id": f"{theme_id}-Q01", "question": question}],
    }
    return _write_tree(tree, theme_id, base_dir)


def _next_node_id(tree: dict) -> str:
    prefix = f"{tree['theme_id']}-Q"
    max_n = max(int(n["id"][len(prefix) :]) for n in tree["nodes"])
    return f"{prefix}{max_n + 1:02d}"


def _require_question_event(event_id: str, base_dir: Path) -> None:
    design_id = design_id_of(event_id)
    events = load_journal(design_id, base_dir).get("events") or []
    event = next((e for e in events if e.get("id") == event_id), None)
    if event is None:
        raise ValueError(f"journal event '{event_id}' not found")
    if event.get("type") != "question":
        raise ValueError(
            f"journal event '{event_id}' is not a question (type: {event.get('type')})"
        )


def add_node(
    theme_id: str,
    *,
    question: str,
    parent_question_id: str | None,
    contribution: str = "",
    origin_event_id: str | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Add a node under *parent_question_id* and return it.

    With *origin_event_id* this promotes a journal ``question``: the event must
    exist and be a question.
    """
    tree = _require_tree(theme_id, base_dir)
    node_id = _next_node_id(tree)
    node: dict[str, Any] = {
        "id": node_id,
        "question": question,
        "parent_question_id": parent_question_id,
        "contribution": contribution,
        "origin_event_id": origin_event_id,
    }
    tree["nodes"].append(node)
    # The shape is checked before the journal is read, so a malformed event id
    # never reaches a path.
    validate_tree_schema(tree)
    if origin_event_id is not None:
        _require_question_event(origin_event_id, base_dir)
    return _node(_write_tree(tree, theme_id, base_dir), node_id)


def _require_design(design_id: str, base_dir: Path) -> dict:
    design = load_design(design_id, base_dir)
    if not design:
        raise ValueError(f"design '{design_id}' not found")
    return design


def link_design(
    theme_id: str, node_id: str, design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Link a design of the same theme to a node and return the node. Idempotent."""
    tree = _require_tree(theme_id, base_dir)
    node = _node(tree, node_id)
    design_theme = _require_design(design_id, base_dir).get("theme_id")
    if design_theme != theme_id:
        raise ValueError(
            f"design '{design_id}' belongs to theme '{design_theme}', not '{theme_id}'"
        )
    linked = list(node.get("design_ids") or [])
    if design_id not in linked:
        linked.append(design_id)
    node["design_ids"] = linked
    return _node(_write_tree(tree, theme_id, base_dir), node_id)


def revise_root(
    theme_id: str,
    *,
    question: str | None = None,
    aim: dict | None = None,
    bump: bool,
    reason: str = "",
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Change the root question or the aim, and return the tree.

    *bump* appends a new root revision, which needs *reason*. Without it the
    current revision is reworded in place and answers keep their revision.
    """
    # The payload is JSON a model wrote; "false" as a string would bump.
    if not isinstance(bump, bool):
        raise ValueError("bump must be true or false")
    if question is None and aim is None:
        raise ValueError("revise-root needs a new question or aim")
    if reason and not bump:
        raise ValueError("a reason is kept only with a bump; without one it is lost")
    tree = _require_tree(theme_id, base_dir)
    current = tree["root_revisions"][-1]
    revised = {
        **current,
        "question": question if question is not None else current["question"],
        "aim": aim if aim is not None else current["aim"],
    }
    if bump:
        revised |= {
            "revision": current["revision"] + 1,
            "reason": reason,
            "created_at": now_jst().isoformat(),
        }
        tree["root_revisions"].append(revised)
    else:
        tree["root_revisions"][-1] = revised
    root = next(n for n in tree["nodes"] if n.get("parent_question_id") is None)
    root["question"] = revised["question"]
    return _write_tree(tree, theme_id, base_dir)


def decide(
    theme_id: str,
    *,
    kind: str,
    node_id: str,
    reason: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Append a decision to the tree and return it."""
    tree = _require_tree(theme_id, base_dir)
    decision = {
        # No reflection round exists before Story 18.4, so every decision is
        # taken at round 0.
        "round": 0,
        "kind": kind,
        "node_id": node_id,
        "reason": reason,
        "created_at": now_jst().isoformat(),
    }
    tree.setdefault("decisions", []).append(decision)
    return _write_tree(tree, theme_id, base_dir)["decisions"][-1]


def answer(
    theme_id: str, *, answers: list[dict], base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Append one reflection round of answers, if the cited-answer check passes.

    *answers* holds ``{"node_id", "statements"}`` entries. The round and the root
    revision are never passed: the round is one past the highest in the tree, and
    the root revision is the current one. An entry whose statements equal the
    node's current answer, given under the current root revision, is unchanged
    and not written. The candidate tree is checked before it is saved, and with
    any violation in a node being written nothing is saved: the result then has
    those ``violations`` and an empty ``written``.
    """
    from skills._shared.tree_check import check_tree  # tree_check imports tree_io

    data = _require_tree(theme_id, base_dir)
    current = validate_tree_schema(data)
    revision = current.current_revision().revision
    # The payload is JSON a model wrote: a bare id in place of an entry must
    # be an error it can read, not a traceback.
    if not all(isinstance(entry, dict) for entry in answers):
        raise ValueError("answers: each entry is an object with node_id and statements")
    node_ids = [entry.get("node_id") for entry in answers]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("a node can be answered only once in one round")

    round_ = current.current_round() + 1
    written: list[dict] = []
    unchanged: list[str] = []
    for entry in answers:
        node = _node(data, entry.get("node_id", ""))
        last = (node.get("answers") or [None])[-1]
        if (
            last is not None
            and last["statements"] == entry.get("statements")
            and last["root_revision"] == revision
        ):
            unchanged.append(node["id"])
            continue
        written.append(
            {"node_id": node["id"], "previous_round": last["round"] if last else None}
        )
        node.setdefault("answers", []).append(
            {
                "round": round_,
                "root_revision": revision,
                "statements": entry.get("statements"),
                "created_at": now_jst().isoformat(),
            }
        )
    result: dict[str, Any] = {
        "round": current.current_round(),
        "root_revision": revision,
        "written": [],
        "unchanged": unchanged,
        "violations": [],
    }
    if not written:
        return result

    candidate = validate_tree_schema(data)
    being_written = {w["node_id"] for w in written}
    result["violations"] = [
        asdict(v) for v in check_tree(candidate, base_dir) if v.node_id in being_written
    ]
    if not result["violations"]:
        _write_tree(data, theme_id, base_dir)
        result |= {"round": round_, "written": written}
    return result


def progress(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Derive the progress of every node from the status of its linked designs."""
    tree = _require_tree(theme_id, base_dir)
    return {
        node["id"]: Progress.of(
            DesignStatus(_require_design(design_id, base_dir)["status"])
            for design_id in node.get("design_ids") or []
        ).value
        for node in tree["nodes"]
    }


def cited_journal_events(cited: set[str], base_dir: Path) -> Iterator[dict]:
    """The journal events whose id is in *cited*.

    An event counts only in the journal its id names: the same id written into
    another design's journal must not back a cite. An id that appears twice is
    yielded twice; the caller decides what that means.
    """
    for design_id in sorted({design_id_of(cite) for cite in cited}):
        journal = load_journal(design_id, base_dir).get("events")
        for event in journal if isinstance(journal, list) else []:
            event_id = event.get("id") if isinstance(event, dict) else None
            if (
                isinstance(event_id, str)
                and event_id in cited
                and design_id_of(event_id) == design_id
            ):
                yield event


def _cited_events(tree: QuestionTree, base_dir: Path) -> dict[str, CitedEvent]:
    """Each event cited by any answer of the tree, earlier rounds included.

    A cited id that two events share keeps the first: tree_check reports it,
    render must still show a page.
    """
    cited = {
        cite
        for node in tree.nodes
        for answer in node.answers
        for statement in answer.statements
        for cite in statement.cites
    }
    events: dict[str, CitedEvent] = {}
    for event in cited_journal_events(cited, base_dir):
        metadata = event.get("metadata")
        direction = metadata.get("direction") if isinstance(metadata, dict) else None
        content = event.get("content")
        events.setdefault(
            event["id"],
            CitedEvent(
                id=event["id"],
                type=str(event.get("type") or ""),
                direction=None if direction is None else str(direction),
                content="" if content is None else str(content),
            ),
        )
    return events


def _design_summaries(theme_id: str, base_dir: Path) -> dict[str, DesignSummary]:
    """The designs of the theme, known by file name as ``load_design`` knows them.

    A copied design file still carries the id of its source, so the id inside
    the file is not read. Only files of this theme are opened: a broken design
    of another theme must not stop the page.
    """
    name = re.compile(rf"({re.escape(theme_id)}-H\d+)_hypothesis\.yaml")
    summaries: dict[str, DesignSummary] = {}
    for path in sorted(_designs_dir(base_dir).glob(f"{theme_id}-H*_hypothesis.yaml")):
        matched = name.fullmatch(path.name)
        if matched is None:
            continue
        data = read_yaml(path)
        parent_id = data.get("parent_id")
        summaries[matched[1]] = DesignSummary(
            id=matched[1],
            title=str(data.get("title") or ""),
            status=str(data.get("status") or ""),
            parent_id=None if parent_id is None else str(parent_id),
        )
    return summaries


def _require_usable_links(
    tree: QuestionTree, designs: dict[str, DesignSummary]
) -> None:
    """Progress is derived from linked designs, so each must exist with a status."""
    statuses = {status.value for status in DesignStatus}
    for node in tree.nodes:
        for design_id in node.design_ids:
            if design_id not in designs:
                raise ValueError(f"design '{design_id}' not found")
            if designs[design_id].status not in statuses:
                raise ValueError(
                    f"design '{design_id}' has an unknown status "
                    f"'{designs[design_id].status}'"
                )


def render(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Write ``{theme_id}_tree.html`` from the canonical tree and return its path.

    The HTML is generated, never edited: the same tree, designs and journals give
    the same bytes. A linked design that no longer exists is an error (as in
    ``progress``) and nothing is written.
    """
    tree = load_tree_model(theme_id, base_dir)
    designs = _design_summaries(theme_id, base_dir)
    _require_usable_links(tree, designs)
    html = render_tree_html(tree, designs, _cited_events(tree, base_dir))
    path = _tree_path(theme_id, base_dir).with_suffix(".html")
    atomic_write_text(path, html)
    return {"path": str(path)}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_io")
    parser.add_argument(
        "command",
        choices=[
            "create",
            "add-node",
            "link",
            "decide",
            "revise-root",
            "answer",
            "get",
            "progress",
            "render",
        ],
    )
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--theme", default=None)
    parser.add_argument("--node", default=None)
    parser.add_argument("--design", default=None)
    args = parser.parse_args(argv)
    base = _resolve_base_dir(Path(args.base_dir))

    payload: dict = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    exit_code = 0
    try:
        if args.command != "create" and args.theme is None:
            raise ValueError(f"--theme is required for {args.command}")
        if args.command == "create":
            result: Any = create_tree(base_dir=base, **payload)
        elif args.command == "add-node":
            result = add_node(args.theme, base_dir=base, **payload)
        elif args.command == "link":
            result = link_design(args.theme, args.node, args.design, base_dir=base)
        elif args.command == "decide":
            result = decide(args.theme, base_dir=base, **payload)
        elif args.command == "revise-root":
            result = revise_root(args.theme, base_dir=base, **payload)
        elif args.command == "answer":
            result = answer(args.theme, base_dir=base, **payload)
            # 3, not 1: for this command 1 stays "error", and a caller must tell
            # "rewrite the answer" from "the tool broke".
            exit_code = 3 if result["violations"] else 0
        elif args.command == "get":
            result = load_tree(args.theme, base_dir=base)
        elif args.command == "render":
            result = render(args.theme, base_dir=base)
        else:
            result = progress(args.theme, base_dir=base)
    # A YAML file that cannot be parsed is the user's to fix, not a crash.
    except (ValueError, TypeError, YAMLError) as exc:
        print(f"tree_io: {exc}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_main())
