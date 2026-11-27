"""YAML I/O for the question tree of a theme (Epic 18, ADR-0024).

The canonical file is ``.insight/themes/{theme_id}_tree.yaml``. Skills call this
instead of writing the file themselves. Every write is checked against the
``QuestionTree`` schema first (``insight_blueprint.validate.validate_tree_schema``):
the pre-write hook only guards the Write/Edit tool path, not direct python writes.
Each writer holds ``write_lock`` from reading the tree to writing it back
(ADR-0062), so two writers at once never lose each other's change.

Progress is never written. What is derived from the tree (``progress``,
``position``, ``changes``, ``handover``, the generated view ``render`` writes) lives in
``tree_read``; the CLI here runs those commands too.

Usage from a skill (CLI):
    echo '<json>' | python -m skills._shared.tree_io create --base-dir .insight
    echo '{"answers": [...]}' | python -m skills._shared.tree_io answer --theme LIB
    python -m skills._shared.tree_io render --design LIB-H01   # the analysis note
    python -m skills._shared.tree_io changes --theme LIB   # what each answer changed
    python -m skills._shared.tree_io report --theme LIB   # .insight/reports/LIB.md

Exit 0: done. Exit 1: error (message on stderr). Exit 3 (answer, decide and report
only): nothing was written, and why is in the JSON on stdout: the check found
violations (answer, decide), or no report can be trusted (report, its ``reasons``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from ruamel.yaml import YAMLError

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.common import now_jst
from insight_blueprint.models.design import TERMINAL_STATUSES
from insight_blueprint.models.journal import HEARING, QUESTION
from insight_blueprint.models.tree import (
    Answer,
    AnswerStatement,
    NextCandidate,
    QuestionNode,
    QuestionTree,
    RootRevision,
    TreeDecision,
    TreeDecisionKind,
    design_id_of,
)
from insight_blueprint.validate import validate_tree_schema
from skills._shared._atomic import atomic_write_yaml, write_lock
from skills._shared._stdin import read_payload
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    append_journal_event,
    journal_events,
    resolve_base_dir,
    stage_in,
)
from skills._shared.tree_check import check_last_decision, check_tree, reported
from skills._shared.tree_read import (
    ReportStop,
    WalkState,
    changes,
    handover,
    load_tree,
    load_tree_model,
    named_like_its_file,
    position,
    progress,
    render,
    render_design,
    report,
    require_design,
    status_of,
    tree_path,
)


def _dump(model: BaseModel) -> dict:
    """*model* as it is written to the file and returned to a caller."""
    return model.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def _checked(tree: QuestionTree, theme_id: str) -> QuestionTree:
    """*tree* after every check of the schema has run again.

    Commands change a loaded tree in place, which pydantic does not check, so
    the invariants that span nodes are checked here. Raises pydantic
    ``ValidationError`` (a ValueError).
    """
    return named_like_its_file(validate_tree_schema(_dump(tree)), theme_id)


def _save(checked: QuestionTree, theme_id: str, base_dir: Path) -> QuestionTree:
    """Write a tree that ``_checked`` returned to the file of *theme_id*.

    The path comes from the caller's theme, never from the content, so a tree
    that names another theme cannot redirect the write.
    """
    atomic_write_yaml(tree_path(theme_id, base_dir), _dump(checked))
    return checked


def _write_tree(tree: QuestionTree, theme_id: str, base_dir: Path) -> QuestionTree:
    """Check *tree* and write it; an invalid tree raises and nothing is written."""
    return _save(_checked(tree, theme_id), theme_id, base_dir)


def create_tree(
    *, theme_id: str, question: str, aim: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Create the tree of a theme with its root question and first root revision."""
    with write_lock(base_dir):
        if tree_path(theme_id, base_dir).exists():
            raise ValueError(f"The question tree of theme '{theme_id}' already exists")
        revision = {
            "revision": 1,
            "question": question,
            "aim": aim,
            "created_at": now_jst(),
        }
        tree = {
            "theme_id": theme_id,
            "root_revisions": [revision],
            "nodes": [{"id": f"{theme_id}-Q01", "question": question}],
        }
        checked = named_like_its_file(validate_tree_schema(tree), theme_id)
        return _dump(_save(checked, theme_id, base_dir))


def _next_node_id(tree: QuestionTree) -> str:
    prefix = f"{tree.theme_id}-Q"
    max_n = max(int(n.id[len(prefix) :]) for n in tree.nodes)
    return f"{prefix}{max_n + 1:02d}"


def _require_question_event(event_id: str, base_dir: Path) -> None:
    events = journal_events(design_id_of(event_id), base_dir)
    event = next((e for e in events if e.get("id") == event_id), None)
    if event is None:
        raise ValueError(f"journal event '{event_id}' not found")
    if event.get("type") != QUESTION:
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
    with write_lock(base_dir):
        tree = load_tree_model(theme_id, base_dir)
        node_id = _next_node_id(tree)
        tree.nodes.append(
            QuestionNode.model_validate(
                {
                    "id": node_id,
                    "question": question,
                    "parent_question_id": parent_question_id,
                    "contribution": contribution,
                    "origin_event_id": origin_event_id,
                }
            )
        )
        # The shape is checked before the journal is read, so a malformed event id
        # never reaches a path.
        checked = _checked(tree, theme_id)
        if origin_event_id is not None:
            _require_question_event(origin_event_id, base_dir)
        return _dump(_save(checked, theme_id, base_dir).node(node_id))


def link_design(
    theme_id: str, node_id: str, design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Link a design of the same theme to a node and return the node. Idempotent."""
    with write_lock(base_dir):
        tree = load_tree_model(theme_id, base_dir)
        node = tree.node(node_id)
        design_theme = require_design(design_id, base_dir).get("theme_id")
        if design_theme != theme_id:
            raise ValueError(
                f"design '{design_id}' belongs to theme '{design_theme}', not '{theme_id}'"
            )
        if design_id not in node.design_ids:
            node.design_ids.append(design_id)
        return _dump(_write_tree(tree, theme_id, base_dir).node(node_id))


def link_derived_design(
    theme_id: str, design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Link a derived design to every node its parent is linked to. Idempotent.

    A derived design is another hypothesis for the question its parent answers,
    so nobody is asked for the node. ``node_ids`` is empty when the parent is
    on no node or the theme has no tree: nothing is written then.
    """
    with write_lock(base_dir):
        design = require_design(design_id, base_dir)
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
        tree = load_tree_model(theme_id, base_dir)
        shared = [n for n in tree.nodes if parent_id in n.design_ids]
        missing = [node for node in shared if design_id not in node.design_ids]
        for node in missing:
            node.design_ids.append(design_id)
        if missing:
            _write_tree(tree, theme_id, base_dir)
        return {**result, "node_ids": [node.id for node in shared]}


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
    with write_lock(base_dir):
        # The payload is JSON a model wrote; "false" as a string would bump.
        if not isinstance(bump, bool):
            raise ValueError("bump must be true or false")
        if question is None and aim is None:
            raise ValueError("revise-root needs a new question or aim")
        if reason and not bump:
            raise ValueError(
                "a reason is kept only with a bump; without one it is lost"
            )
        tree = load_tree_model(theme_id, base_dir)
        current = tree.current_revision()
        revised = current.model_dump()
        if question is not None:
            revised["question"] = question
        if aim is not None:
            revised["aim"] = aim
        if bump:
            revised |= {
                "revision": current.revision + 1,
                "reason": reason,
                "created_at": now_jst(),
            }
            tree.root_revisions.append(RootRevision.model_validate(revised))
        else:
            tree.root_revisions[-1] = RootRevision.model_validate(revised)
        tree.root().question = tree.current_revision().question
        return _dump(_write_tree(tree, theme_id, base_dir))


def decide(
    theme_id: str,
    *,
    kind: str,
    node_id: str,
    reason: str,
    cites: Sequence[str] = (),
    with_node_ids: Sequence[str] = (),
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Append a decision to the tree and return it, if its cites pass the check.

    *with_node_ids* names the questions handed over together with *node_id*
    (ADR-0061 1). They take no kind: the kind says how *node_id* stands to the
    questions the decision before named.

    The round is never passed: a ``start`` is taken at round 0, any other kind
    at the last reflection round, which is the one whose answers it was made on.

    *cites* names the journal events the reason rests on (ADR-0058). A decision
    that cites is checked before it is saved, and with any violation nothing is
    saved: the result is then ``{"violations": [...]}`` instead of the decision.
    A reason without cites is not checked.
    """
    with write_lock(base_dir):
        is_start = TreeDecisionKind(kind) is TreeDecisionKind.start
        tree = load_tree_model(theme_id, base_dir)
        tree.decisions.append(
            TreeDecision.model_validate(
                {
                    "round": 0 if is_start else tree.current_round(),
                    "kind": kind,
                    "node_id": node_id,
                    "with_node_ids": with_node_ids,
                    "reason": reason,
                    "cites": cites,
                    "created_at": now_jst(),
                }
            )
        )
        # Checked before the journals are read, so a malformed cite never reaches a path.
        candidate_tree = _checked(tree, theme_id)
        violations = [
            reported(v) for v in check_last_decision(candidate_tree, base_dir)
        ]
        if violations:
            return {"violations": violations}
        return _dump(_save(candidate_tree, theme_id, base_dir).decisions[-1])


def candidates(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> list[dict]:
    """The next candidates: untouched nodes, each with its notes when it has any."""
    return [
        {
            "id": node.id,
            "question": node.question,
            "parent_question_id": node.parent_question_id,
            "contribution": node.contribution,
            **(
                {"next_candidate": _dump(node.next_candidate)}
                if node.next_candidate is not None
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
    with write_lock(base_dir):
        tree = load_tree_model(theme_id, base_dir)
        node = tree.node(node_id)
        note = node.next_candidate
        recorded = note if note is not None and note.answer else None
        if recorded is not None and ask != recorded.ask:
            raise ValueError(
                f"{node_id} already has an answer to its ask; the ask cannot change"
            )
        node.next_candidate = NextCandidate.model_validate(
            (recorded.model_dump() if recorded is not None else {})
            | {"ask": ask, "changes_if": changes_if, "known": known}
        )
        return _dump(_write_tree(tree, theme_id, base_dir).node(node_id))


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
    with write_lock(base_dir):
        tree = load_tree_model(theme_id, base_dir)
        node = tree.node(node_id)
        note = node.next_candidate
        if note is None or not note.ask:
            raise ValueError(f"{node_id} has no ask to answer")
        node.next_candidate = NextCandidate.model_validate(
            note.model_dump()
            | {"answer": answer, "answered_by": answered_by, "answered_at": answered_at}
        )
        return _dump(_write_tree(tree, theme_id, base_dir).node(node_id))


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
    with write_lock(base_dir):
        node = load_tree_model(theme_id, base_dir).node(node_id)
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
        same = {k: metadata[k] for k in ("node_id", "answered_by", "answered_at")}
        for existing in journal_events(design_id, base_dir):
            old = existing.get("metadata")
            old = old if isinstance(old, dict) else {}
            # YAML reads an unquoted date back as a date, not the string we wrote.
            if (
                existing.get("type") == HEARING
                and existing.get("content") == note.answer
                and {k: str(old.get(k)) for k in same} == same
            ):
                return {
                    "copied": False,
                    "reason": "the answer is already in the journal",
                }

        design = require_design(design_id, base_dir)
        status = status_of(design)
        # A concluded analysis keeps the record it was concluded on, and a
        # stopped one is not resumed (ADR-0064 7).
        if stage_in(design_id, design, base_dir) is AnalysisStage.stopped:
            ended = "stopped: a stopped analysis takes no new hearing"
        elif status in TERMINAL_STATUSES:
            ended = f"{status.value}: a finished design takes no new hearing"
        else:
            ended = None
        if ended is not None:
            raise ValueError(
                f"{design_id} is {ended}. "
                f"The answer stays on {node_id}; copy it into the next design linked there"
            )

        event = append_journal_event(
            design_id,
            {"type": HEARING, "content": note.answer, "metadata": metadata},
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
    with write_lock(base_dir):
        # The payload is JSON a model wrote, so it is parsed before anything reads it.
        entries = TypeAdapter(list[_AnswerEntry]).validate_python(answers)
        tree = load_tree_model(theme_id, base_dir)
        result: dict[str, Any] = {
            "round": tree.current_round(),
            "root_revision": tree.current_revision().revision,
            "written": [],
            "unchanged": [],
            "violations": [],
        }
        written, result["unchanged"] = _append_round(tree, entries)
        if not written:
            return result

        # Checked before the journals are read, so a malformed cite never reaches a path.
        candidate_tree = _checked(tree, theme_id)
        being_written = {w["node_id"] for w in written}
        result["violations"] = [
            reported(v)
            for v in check_tree(candidate_tree, base_dir)
            if v.node_id in being_written
        ]
        if not result["violations"]:
            _save(candidate_tree, theme_id, base_dir)
            result |= {"round": result["round"] + 1, "written": written}
        return result


def _append_round(
    tree: QuestionTree, entries: list[_AnswerEntry]
) -> tuple[list[dict], list[str]]:
    """Append the next round to *tree* in place; return what was written and what was not."""
    names = [entry.node_id for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("a node can be answered only once in one round")
    next_round = tree.current_round() + 1
    revision = tree.current_revision().revision
    written: list[dict] = []
    unchanged: list[str] = []
    for entry in entries:
        node = tree.node(entry.node_id)
        last = node.current_answer()
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
        node.answers.append(
            Answer(
                round=next_round,
                root_revision=revision,
                statements=entry.statements,
                created_at=now_jst(),
            )
        )
    return written, unchanged


def _required(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if value is None:
        raise ValueError(f"--{name} is required for {args.command}")
    return value


def _say_where_it_looked(theme_id: str, base_dir: Path) -> None:
    # "No tree" also comes back when the caller stands in another directory,
    # so say which file was looked for.
    looked = tree_path(theme_id, base_dir).resolve()
    print(f"tree_io: no tree at {looked}", file=sys.stderr)


def _get(args: argparse.Namespace, base: Path, payload: dict) -> Any:
    tree = load_tree(args.theme, base_dir=base)
    if not tree:
        _say_where_it_looked(args.theme, base)
    return tree


def _position(args: argparse.Namespace, base: Path, payload: dict) -> Any:
    where = position(args.theme, base_dir=base)
    if where["state"] is WalkState.no_tree:
        _say_where_it_looked(args.theme, base)
    return where


def _report(args: argparse.Namespace, base: Path, payload: dict) -> dict[str, Any]:
    result = report(args.theme, base_dir=base)
    if not result["written"] and result["reasons"][0]["kind"] is ReportStop.no_tree:
        _say_where_it_looked(args.theme, base)
    return result


def _render(args: argparse.Namespace, base: Path, payload: dict) -> dict[str, Any]:
    if (args.theme is None) == (args.design is None):
        raise ValueError("render takes exactly one of --theme and --design")
    if args.design is not None:
        return render_design(args.design, base_dir=base)
    return render(args.theme, base_dir=base)


_Handler = Callable[[argparse.Namespace, Path, dict], Any]

# name -> (handler, whether the command reads a JSON payload from stdin)
_COMMANDS: dict[str, tuple[_Handler, bool]] = {
    "create": (lambda a, base, p: create_tree(base_dir=base, **p), True),
    "add-node": (lambda a, base, p: add_node(a.theme, base_dir=base, **p), True),
    "link": (
        lambda a, base, p: link_design(
            a.theme, _required(a, "node"), _required(a, "design"), base_dir=base
        ),
        False,
    ),
    "link-derived": (
        lambda a, base, p: link_derived_design(
            a.theme, _required(a, "design"), base_dir=base
        ),
        False,
    ),
    "decide": (lambda a, base, p: decide(a.theme, base_dir=base, **p), True),
    "candidates": (lambda a, base, p: candidates(a.theme, base_dir=base), False),
    "candidate": (
        lambda a, base, p: candidate(a.theme, _required(a, "node"), base_dir=base, **p),
        True,
    ),
    "hear": (
        lambda a, base, p: hear(a.theme, _required(a, "node"), base_dir=base, **p),
        True,
    ),
    "copy-hearing": (
        lambda a, base, p: copy_hearing(
            a.theme, _required(a, "node"), _required(a, "design"), base_dir=base
        ),
        False,
    ),
    "revise-root": (lambda a, base, p: revise_root(a.theme, base_dir=base, **p), True),
    "answer": (lambda a, base, p: answer(a.theme, base_dir=base, **p), True),
    "get": (_get, False),
    "position": (_position, False),
    "handover": (lambda a, base, p: handover(a.theme, base_dir=base), False),
    "progress": (lambda a, base, p: progress(a.theme, base_dir=base), False),
    "changes": (lambda a, base, p: changes(a.theme, base_dir=base), False),
    "render": (_render, False),
    "report": (_report, False),
}

# 3, not 1: 1 stays "the call or a file is wrong", and a caller must
# tell that apart from "rewrite the answer" or "fix what the reason names".
_NOTHING_WRITTEN: dict[str, Callable[[dict], bool]] = {
    "answer": lambda result: bool(result["violations"]),
    "decide": lambda result: "violations" in result,
    "report": lambda result: not result["written"],
}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tree_io")
    parser.add_argument("command", choices=list(_COMMANDS))
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--theme", default=None)
    parser.add_argument("--node", default=None)
    parser.add_argument("--design", default=None)
    args = parser.parse_args(argv)
    base = resolve_base_dir(Path(args.base_dir))
    handler, takes_payload = _COMMANDS[args.command]

    try:
        payload = read_payload() if takes_payload else {}
        if args.command not in ("create", "render") and args.theme is None:
            raise ValueError(f"--theme is required for {args.command}")
        result = handler(args, base, payload)
    # A payload or a file that cannot be read is the caller's to fix, not a crash.
    except (ValueError, TypeError, YAMLError, OSError) as exc:
        print(f"tree_io: {exc}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    refused = _NOTHING_WRITTEN.get(args.command)
    return 3 if refused is not None and refused(result) else 0


if __name__ == "__main__":
    raise SystemExit(_main())
