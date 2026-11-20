"""YAML I/O for the question tree of a theme (Epic 18, ADR-0024).

The canonical file is ``.insight/themes/{theme_id}_tree.yaml``. Skills call this
instead of writing the file themselves. Every write goes through
``insight_blueprint.validate.validate_tree`` first: the pre-write hook only
guards the Write/Edit tool path, not direct python writes.

Progress is never written. ``progress`` derives it from the status of the
designs linked to each node.

Usage from a skill (CLI):
    echo '<json>' | python -m skills._shared.tree_io create --base-dir .insight
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from insight_blueprint.models.common import now_jst
from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.tree import THEME_ID_PATTERN, Progress, QuestionTree
from insight_blueprint.validate import validate_tree
from skills._shared._atomic import atomic_write_yaml
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    _resolve_base_dir,
    load_design,
    load_journal,
    read_yaml,
)


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


def _write_tree(tree: dict, base_dir: Path) -> dict:
    """Validate *tree*, write it, and return what was written."""
    theme_id = str(tree.get("theme_id", ""))
    path = _tree_path(theme_id, base_dir)
    errors = validate_tree(tree, expected_theme_id=theme_id)
    if errors:
        raise ValueError("Invalid question tree: " + "; ".join(errors))
    data = QuestionTree.model_validate(tree).model_dump(
        mode="json", exclude_none=True, exclude_defaults=True
    )
    atomic_write_yaml(path, data)
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
    return _write_tree(tree, base_dir)


def _next_node_id(tree: dict) -> str:
    prefix = f"{tree['theme_id']}-Q"
    max_n = max(int(n["id"][len(prefix) :]) for n in tree["nodes"])
    return f"{prefix}{max_n + 1:02d}"


def _require_question_event(event_id: str, base_dir: Path) -> None:
    design_id = event_id.rpartition("-E")[0]
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
    errors = validate_tree(tree)
    if errors:
        raise ValueError("Invalid question tree: " + "; ".join(errors))
    if origin_event_id is not None:
        _require_question_event(origin_event_id, base_dir)
    return _node(_write_tree(tree, base_dir), node_id)


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
    return _node(_write_tree(tree, base_dir), node_id)


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
    if question is None and aim is None:
        raise ValueError("revise-root needs a new question or aim")
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
    return _write_tree(tree, base_dir)


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


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_io")
    parser.add_argument(
        "command",
        choices=["create", "add-node", "link", "revise-root", "get", "progress"],
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

    try:
        if args.command == "create":
            result: Any = create_tree(base_dir=base, **payload)
        elif args.command == "add-node":
            result = add_node(args.theme, base_dir=base, **payload)
        elif args.command == "link":
            result = link_design(args.theme, args.node, args.design, base_dir=base)
        elif args.command == "revise-root":
            result = revise_root(args.theme, base_dir=base, **payload)
        elif args.command == "get":
            result = load_tree(args.theme, base_dir=base)
        else:
            result = progress(args.theme, base_dir=base)
    except (ValueError, TypeError) as exc:
        print(f"tree_io: {exc}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
