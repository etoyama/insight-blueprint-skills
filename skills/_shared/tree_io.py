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
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from ruamel.yaml import YAMLError

from insight_blueprint.models.common import THEME_ID_PATTERN, now_jst
from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus
from insight_blueprint.models.tree import (
    AnswerStatement,
    Progress,
    QuestionTree,
    TreeDecisionKind,
    design_id_of,
)
from insight_blueprint.validate import validate_tree_schema
from skills._shared._atomic import atomic_write_text, atomic_write_yaml
from skills._shared._stdin import read_payload
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    _designs_dir,
    _resolve_base_dir,
    append_journal_event,
    load_design,
    load_journal,
    read_yaml,
)
from skills._shared.tree_render import (
    CheckFailed,
    CitedEvent,
    DesignSummary,
    render_tree_html,
)

if TYPE_CHECKING:  # tree_check imports this module
    from skills._shared.tree_check import Violation


def _tree_path(theme_id: str, base_dir: Path) -> Path:
    # theme_id becomes part of a path, so it is checked before any I/O.
    if not THEME_ID_PATTERN.fullmatch(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    return Path(base_dir) / "themes" / f"{theme_id}_tree.yaml"


def load_tree(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Load ``{theme_id}_tree.yaml`` as a dict; {} if absent."""
    return read_yaml(_tree_path(theme_id, base_dir))


def _read_tree(theme_id: str, base_dir: Path) -> tuple[dict, QuestionTree]:
    tree = load_tree(theme_id, base_dir)
    if not tree:
        raise ValueError(f"Theme '{theme_id}' has no question tree")
    return tree, _named_like_its_file(validate_tree_schema(tree), theme_id)


def _require_tree(theme_id: str, base_dir: Path) -> dict:
    """The tree of *theme_id* as a dict, validated before any command reads it."""
    return _read_tree(theme_id, base_dir)[0]


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
    return _read_tree(theme_id, base_dir)[1]


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


def link_derived_design(
    theme_id: str, design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Link a derived design to every node its parent is linked to. Idempotent.

    A derived design is another hypothesis for the question its parent answers,
    so nobody is asked for the node. ``node_ids`` is empty when the parent is
    on no node or the theme has no tree: nothing is written then.
    """
    design = _require_design(design_id, base_dir)
    parent_id = design.get("parent_id")
    if not parent_id:
        raise ValueError(f"design '{design_id}' has no parent_id")
    design_theme = design.get("theme_id")
    if design_theme != theme_id:
        raise ValueError(
            f"design '{design_id}' belongs to theme '{design_theme}', not '{theme_id}'"
        )
    result = {"design_id": design_id, "parent_id": parent_id, "node_ids": []}
    if not load_tree(theme_id, base_dir):
        return result
    tree = _require_tree(theme_id, base_dir)
    shared = [n for n in tree["nodes"] if parent_id in n.get("design_ids", [])]
    missing = [node for node in shared if design_id not in node["design_ids"]]
    for node in missing:
        node["design_ids"].append(design_id)
    if missing:
        _write_tree(tree, theme_id, base_dir)
    return {**result, "node_ids": [node["id"] for node in shared]}


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
    """Append a decision to the tree and return it.

    The round is never passed: a ``start`` is taken at round 0, any other kind
    at the last reflection round, which is the one whose answers it was made on.
    """
    is_start = TreeDecisionKind(kind) is TreeDecisionKind.start
    tree = _require_tree(theme_id, base_dir)
    decision = {
        "round": 0 if is_start else validate_tree_schema(tree).current_round(),
        "kind": kind,
        "node_id": node_id,
        "reason": reason,
        "created_at": now_jst().isoformat(),
    }
    tree.setdefault("decisions", []).append(decision)
    return _write_tree(tree, theme_id, base_dir)["decisions"][-1]


_HEARD_FIELDS = ("answer", "answered_by", "answered_at")


def candidates(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> list[dict]:
    """The next candidates: untouched nodes, each with its notes when it has any."""
    return [
        {
            "id": node.id,
            "question": node.question,
            "parent_question_id": node.parent_question_id,
            "contribution": node.contribution,
            **(
                {
                    "next_candidate": node.next_candidate.model_dump(
                        mode="json", exclude_defaults=True
                    )
                }
                if node.next_candidate
                else {}
            ),
        }
        for node in load_tree_model(theme_id, base_dir).untouched_nodes()
    ]


def candidate(
    theme_id: str,
    node_id: str,
    *,
    ask: str = "",
    changes_if: str = "",
    known: str = "",
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Replace the notes of a node and return it; a recorded answer is kept.

    The answer answers the old question, so *ask* cannot change while one is
    recorded.
    """
    tree = _require_tree(theme_id, base_dir)
    node = _node(tree, node_id)
    heard = {
        k: v
        for k, v in (node.get("next_candidate") or {}).items()
        if k in _HEARD_FIELDS
    }
    if heard and ask != node["next_candidate"].get("ask", ""):
        raise ValueError(
            f"{node_id} already has an answer to its ask; the ask cannot change"
        )
    node["next_candidate"] = {
        "ask": ask,
        "changes_if": changes_if,
        "known": known,
        **heard,
    }
    return _node(_write_tree(tree, theme_id, base_dir), node_id)


def hear(
    theme_id: str,
    node_id: str,
    *,
    answer: str,
    answered_by: str,
    answered_at: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Record the answer a person gave to the ask of a node and return the node.

    Recording again replaces the answer.
    """
    tree = _require_tree(theme_id, base_dir)
    node = _node(tree, node_id)
    note = node.get("next_candidate")
    if not note or not note.get("ask"):
        raise ValueError(f"{node_id} has no ask to answer")
    given = {"answer": answer, "answered_by": answered_by, "answered_at": answered_at}
    note |= {field: given[field] for field in _HEARD_FIELDS}
    return _node(_write_tree(tree, theme_id, base_dir), node_id)


def copy_hearing(
    theme_id: str,
    node_id: str,
    design_id: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Copy the recorded answer of a node into the journal of *design_id*.

    The text goes in verbatim, by code, so a model never retypes it. It is
    written once: the same answer already in the journal is not written again.
    A design in a terminal status is refused: nothing is added to its journal.
    """
    tree = load_tree_model(theme_id, base_dir)
    node = next((n for n in tree.nodes if n.id == node_id), None)
    if node is None:
        raise ValueError(f"node '{node_id}' not found in the tree of {theme_id}")
    if design_id not in node.design_ids:
        raise ValueError(f"design '{design_id}' is not linked to {node_id}")
    note = node.next_candidate
    if note is None or not note.answer:
        return {"copied": False, "reason": f"{node_id} has no answer to copy"}

    assert note.answered_at is not None  # the model requires it with an answer
    metadata = {
        "node_id": node_id,
        "ask": note.ask,
        "answered_by": note.answered_by,
        "answered_at": note.answered_at.isoformat(),
    }
    journal = load_journal(design_id, base_dir)
    events = journal.get("events")
    same = {k: metadata[k] for k in ("node_id", "answered_by", "answered_at")}
    for existing in events if isinstance(events, list) else []:
        if not isinstance(existing, dict):
            continue
        old = existing.get("metadata")
        old = old if isinstance(old, dict) else {}
        # YAML reads an unquoted date back as a date, not the string we wrote.
        if (
            existing.get("type") == "hearing"
            and existing.get("content") == note.answer
            and {k: str(old.get(k)) for k in same} == same
        ):
            return {"copied": False, "reason": "the answer is already in the journal"}

    status = _status_of(design_id, base_dir)
    if status in TERMINAL_STATUSES:
        # A concluded analysis keeps the record it was concluded on.
        raise ValueError(
            f"{design_id} is {status.value}: a finished design takes no new hearing. "
            f"The answer stays on {node_id}; copy it into the next design linked there"
        )

    event = append_journal_event(
        design_id,
        {"type": "hearing", "content": note.answer, "metadata": metadata},
        base_dir,
    )
    return {"copied": True, "event": event}


class _AnswerEntry(BaseModel):
    """What a caller says about one node in ``answer``: nothing tree_io sets."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    statements: list[AnswerStatement] = Field(min_length=1)


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

    ``round`` in the result is the last round the tree holds after the call: the
    new round when answers were written, the earlier one when none were. A
    violation carries the round its answer would have had.
    """
    from skills._shared.tree_check import check_tree  # tree_check imports tree_io

    # The payload is JSON a model wrote, so it is parsed before anything reads it.
    entries = TypeAdapter(list[_AnswerEntry]).validate_python(answers)
    data = _require_tree(theme_id, base_dir)
    current = validate_tree_schema(data)
    written, unchanged = _append_round(data, current, entries)
    result: dict[str, Any] = {
        "round": current.current_round(),
        "root_revision": current.current_revision().revision,
        "written": [],
        "unchanged": unchanged,
        "violations": [],
    }
    if not written:
        return result

    being_written = {w["node_id"] for w in written}
    result["violations"] = [
        asdict(v)
        for v in check_tree(validate_tree_schema(data), base_dir)
        if v.node_id in being_written
    ]
    if not result["violations"]:
        _write_tree(data, theme_id, base_dir)
        result |= {"round": current.current_round() + 1, "written": written}
    return result


def _append_round(
    data: dict, current: QuestionTree, entries: list[_AnswerEntry]
) -> tuple[list[dict], list[str]]:
    """Append the next round to *data* in place; return what was written and what was not."""
    names = [entry.node_id for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("a node can be answered only once in one round")
    nodes = {node.id: node for node in current.nodes}
    revision = current.current_revision().revision
    written: list[dict] = []
    unchanged: list[str] = []
    for entry in entries:
        if entry.node_id not in nodes:
            raise ValueError(
                f"node '{entry.node_id}' not found in the tree of {current.theme_id}"
            )
        last = nodes[entry.node_id].current_answer()
        same = last is not None and last.statements == entry.statements
        if last is not None and same and last.root_revision == revision:
            unchanged.append(entry.node_id)
            continue
        written.append(
            {
                "node_id": entry.node_id,
                "previous_round": last.round if last else None,
                # The same statements, written again for a newer root revision.
                "restated": same,
            }
        )
        _node(data, entry.node_id).setdefault("answers", []).append(
            {
                "round": current.current_round() + 1,
                "root_revision": revision,
                "statements": [s.model_dump(mode="json") for s in entry.statements],
                "created_at": now_jst().isoformat(),
            }
        )
    return written, unchanged


def progress(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Derive the progress of every node from the status of its linked designs."""
    tree = _require_tree(theme_id, base_dir)
    return {
        node["id"]: Progress.of(
            _status_of(design_id, base_dir)
            for design_id in node.get("design_ids") or []
        ).value
        for node in tree["nodes"]
    }


class WalkState(StrEnum):
    """Where the walk of a theme stands. Derived by ``position``, never stored."""

    no_tree = "no_tree"
    no_decision = "no_decision"
    not_started = "not_started"
    in_progress = "in_progress"
    concluded = "concluded"
    closed = "closed"


def _status_of(design_id: str, base_dir: Path) -> DesignStatus:
    return DesignStatus(_require_design(design_id, base_dir)["status"])


def _made_after(design_id: str, decision_time: datetime | None, base_dir: Path) -> bool:
    """Whether the design was created after the decision.

    A decision without a time (a tree written by hand) counts every design as
    later: the caller then reaches the theme reflection, where the analyst is
    asked, instead of designing the node a second time unasked.
    """
    if decision_time is None:
        return True
    raw = _require_design(design_id, base_dir).get("created_at")
    try:
        return datetime.fromisoformat(str(raw)) > decision_time
    except (TypeError, ValueError):
        # Guessing here would pin the walk to one state run after run.
        raise ValueError(
            f"design '{design_id}': created_at {raw!r} cannot be compared with "
            f"the decision of {decision_time.isoformat()}"
        ) from None


def position(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Where the walk of the theme stands, derived from the last decision. Writes nothing.

    ``state`` is a ``WalkState``:

    - ``no_tree`` / ``no_decision``: nothing names a node yet.
    - ``in_progress``: ``design_ids`` are the unfinished designs on the node.
      After a ``close`` only designs made since the close count: what the
      analyst left unfinished when closing stays closed.
    - ``concluded``: ``design_ids`` were made after the decision and are all
      finished; the round still lacks its theme reflection and its decision.
    - ``not_started``: no design was made on the node since the decision.
    - ``closed``: the last decision closed the walk at ``node_id``, and no
      design was made on it since.
    """
    if not load_tree(theme_id, base_dir):
        return {"state": WalkState.no_tree}
    tree = load_tree_model(theme_id, base_dir)
    if not tree.decisions:
        return {"state": WalkState.no_decision}
    decision = tree.decisions[-1]
    closed = decision.kind is TreeDecisionKind.close
    node = next(n for n in tree.nodes if n.id == decision.node_id)

    def later(design_ids: list[str]) -> list[str]:
        return [d for d in design_ids if _made_after(d, decision.created_at, base_dir)]

    unfinished = [
        d for d in node.design_ids if _status_of(d, base_dir) not in TERMINAL_STATUSES
    ]
    if closed:
        unfinished = later(unfinished)
    if unfinished:
        state, design_ids = WalkState.in_progress, unfinished
    elif made_since := later(node.design_ids):
        state, design_ids = WalkState.concluded, made_since
    else:
        state = WalkState.closed if closed else WalkState.not_started
        design_ids = []
    return {
        "state": state,
        "node_id": decision.node_id,
        "decision": decision.model_dump(mode="json"),
        "design_ids": design_ids,
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


def _check_for_page(
    tree: QuestionTree, base_dir: Path
) -> list[Violation] | CheckFailed:
    """The violations of the current answers, or why they could not be found.

    A stale answer is not stored as withdrawn, so the page is where it shows. A
    cited id that two events share stops the check, not the page: it says so on
    the page. A journal that cannot be read already stopped ``render`` before
    this runs, so the analyst is told which file to fix.
    """
    from skills._shared.tree_check import check_tree  # tree_check imports tree_io

    try:
        return check_tree(tree, base_dir)
    except ValueError as exc:
        return CheckFailed(str(exc))


def render(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Write ``{theme_id}_tree.html`` from the canonical tree and return its path.

    The HTML is generated, never edited: the same tree, designs and journals give
    the same bytes. A linked design that no longer exists is an error (as in
    ``progress``) and nothing is written.
    """
    tree = load_tree_model(theme_id, base_dir)
    designs = _design_summaries(theme_id, base_dir)
    _require_usable_links(tree, designs)
    html = render_tree_html(
        tree, designs, _cited_events(tree, base_dir), _check_for_page(tree, base_dir)
    )
    path = _tree_path(theme_id, base_dir).with_suffix(".html")
    atomic_write_text(path, html)
    return {"path": str(path)}


def _required(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if value is None:
        raise ValueError(f"--{name} is required for {args.command}")
    return value


def _say_where_it_looked(theme_id: str, base_dir: Path) -> None:
    # "No tree" also comes back when the caller stands in another directory,
    # so say which file was looked for.
    looked = _tree_path(theme_id, base_dir).resolve()
    print(f"tree_io: no tree at {looked}", file=sys.stderr)


_TAKES_PAYLOAD = frozenset(
    {"create", "add-node", "decide", "candidate", "hear", "revise-root", "answer"}
)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_io")
    parser.add_argument(
        "command",
        choices=[
            "create",
            "add-node",
            "link",
            "link-derived",
            "decide",
            "candidates",
            "candidate",
            "hear",
            "copy-hearing",
            "revise-root",
            "answer",
            "get",
            "position",
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

    exit_code = 0
    try:
        payload = read_payload() if args.command in _TAKES_PAYLOAD else {}
        if args.command != "create" and args.theme is None:
            raise ValueError(f"--theme is required for {args.command}")
        if args.command == "create":
            result: Any = create_tree(base_dir=base, **payload)
        elif args.command == "add-node":
            result = add_node(args.theme, base_dir=base, **payload)
        elif args.command == "link":
            result = link_design(
                args.theme,
                _required(args, "node"),
                _required(args, "design"),
                base_dir=base,
            )
        elif args.command == "link-derived":
            result = link_derived_design(
                args.theme, _required(args, "design"), base_dir=base
            )
        elif args.command == "decide":
            result = decide(args.theme, base_dir=base, **payload)
        elif args.command == "candidates":
            result = candidates(args.theme, base_dir=base)
        elif args.command == "candidate":
            result = candidate(
                args.theme, _required(args, "node"), base_dir=base, **payload
            )
        elif args.command == "hear":
            result = hear(args.theme, _required(args, "node"), base_dir=base, **payload)
        elif args.command == "copy-hearing":
            result = copy_hearing(
                args.theme,
                _required(args, "node"),
                _required(args, "design"),
                base_dir=base,
            )
        elif args.command == "revise-root":
            result = revise_root(args.theme, base_dir=base, **payload)
        elif args.command == "answer":
            result = answer(args.theme, base_dir=base, **payload)
            # 3, not 1: 1 stays "the call or a file is wrong", and a caller must
            # tell that apart from "rewrite the answer".
            exit_code = 3 if result["violations"] else 0
        elif args.command == "get":
            result = load_tree(args.theme, base_dir=base)
            if not result:
                _say_where_it_looked(args.theme, base)
        elif args.command == "position":
            result = position(args.theme, base_dir=base)
            if result["state"] is WalkState.no_tree:
                _say_where_it_looked(args.theme, base)
        elif args.command == "render":
            result = render(args.theme, base_dir=base)
        else:
            result = progress(args.theme, base_dir=base)
    # A payload or a file that cannot be read is the caller's to fix, not a crash.
    except (ValueError, TypeError, YAMLError, OSError) as exc:
        print(f"tree_io: {exc}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(_main())
