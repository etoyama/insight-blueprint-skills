"""Reads of the question tree of a theme (Epic 18, ADR-0024).

Reads of the canonical file ``.insight/themes/{theme_id}_tree.yaml`` and of
the designs and journals it links to. Nothing here writes the canonical file:
``progress`` and ``position`` derive from the status of the linked designs, and
``render`` writes only the generated view ``{theme_id}_tree.html`` next to it. The page
is built by ``tree_render`` and is never edited.

``report`` writes the final report ``reports/{theme_id}.md``, also generated and
never edited.

Writes go through ``tree_io``, which also carries the CLI for these reads.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from insight_blueprint.models.common import THEME_ID_PATTERN
from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus
from insight_blueprint.models.tree import (
    Answer,
    Progress,
    QuestionNode,
    QuestionTree,
    TreeDecisionKind,
    design_id_of,
)
from insight_blueprint.validate import validate_tree_schema
from skills._shared._atomic import atomic_write_text
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    designs_of_theme,
    journal_events,
    load_design,
    read_yaml,
    theme_of,
)
from skills._shared.design_note import DesignNote, note_anchor, render_note
from skills._shared.design_note_read import load_design_note, render_design_note
from skills._shared.theme_report import (
    ReportDesign,
    ReportNode,
    ThemeReport,
    render_report,
)
from skills._shared.tree_check import Violation, check_cited, current_cites
from skills._shared.tree_render import (
    CheckFailed,
    CitedEvent,
    DesignSummary,
    render_tree_html,
)


def tree_path(theme_id: str, base_dir: Path) -> Path:
    """The canonical file of the tree of *theme_id*."""
    # theme_id becomes part of a path, so it is checked before any I/O.
    if not THEME_ID_PATTERN.fullmatch(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    return Path(base_dir) / "themes" / f"{theme_id}_tree.yaml"


def load_tree(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Load ``{theme_id}_tree.yaml`` as a dict; {} if absent."""
    return read_yaml(tree_path(theme_id, base_dir))


def named_like_its_file(model: QuestionTree, theme_id: str) -> QuestionTree:
    """*model*, if it names the theme its file is named after."""
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
    tree = load_tree(theme_id, base_dir)
    if not tree:
        raise ValueError(f"Theme '{theme_id}' has no question tree")
    return named_like_its_file(validate_tree_schema(tree), theme_id)


def require_design(design_id: str, base_dir: Path) -> dict:
    """The design *design_id*; ValueError if it does not exist."""
    design = load_design(design_id, base_dir)
    if not design:
        raise ValueError(f"design '{design_id}' not found")
    return design


def status_of(design: dict) -> DesignStatus:
    return DesignStatus(design["status"])


def progress(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Derive the progress of every node from the status of its linked designs."""
    return {
        node.id: Progress.of(
            status_of(require_design(design_id, base_dir))
            for design_id in node.design_ids
        ).value
        for node in load_tree_model(theme_id, base_dir).nodes
    }


class WalkState(StrEnum):
    """Where the walk of a theme stands. Derived by ``position``, never stored."""

    no_tree = "no_tree"
    no_decision = "no_decision"
    not_started = "not_started"
    in_progress = "in_progress"
    concluded = "concluded"
    closed = "closed"


def _made_after(design_id: str, design: dict, decision_time: datetime | None) -> bool:
    """Whether the design was created after the decision.

    A decision without a time (a tree written by hand) counts every design as
    later: the caller then reaches the theme reflection, where the analyst is
    asked, instead of designing the node a second time unasked.
    """
    if decision_time is None:
        return True
    raw = design.get("created_at")
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
    node = tree.node(decision.node_id)
    designs: dict[str, dict] = {}
    statuses: dict[str, DesignStatus] = {}
    # One design at a time, so the first broken design is the one reported.
    for design_id in node.design_ids:
        designs[design_id] = require_design(design_id, base_dir)
        statuses[design_id] = status_of(designs[design_id])

    def later(design_ids: list[str]) -> list[str]:
        return [
            d for d in design_ids if _made_after(d, designs[d], decision.created_at)
        ]

    unfinished = [
        d for d, status in statuses.items() if status not in TERMINAL_STATUSES
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
        for event in journal_events(design_id, base_dir):
            event_id = event.get("id")
            if (
                isinstance(event_id, str)
                and event_id in cited
                and design_id_of(event_id) == design_id
            ):
                yield event


def cited_events(
    cited: Iterable[str], base_dir: Path
) -> tuple[dict[str, CitedEvent], list[str]]:
    """Each event whose id is in *cited*, and the ids two events share, in the order found.

    A shared id keeps its first event: tree_check refuses to check on it, but
    render must still show a page.
    """
    events: dict[str, CitedEvent] = {}
    duplicated: list[str] = []
    for event in cited_journal_events(set(cited), base_dir):
        event_id = event["id"]
        if event_id in events:
            duplicated.append(event_id)
            continue
        metadata = event.get("metadata")
        direction = metadata.get("direction") if isinstance(metadata, dict) else None
        content = event.get("content")
        events[event_id] = CitedEvent(
            id=event_id,
            type=str(event.get("type") or ""),
            direction=None if direction is None else str(direction),
            # A hand-written "content: 34.6" loads as a float, not as text.
            content="" if content is None else str(content),
        )
    return events, duplicated


def _design_notes(theme_id: str, base_dir: Path) -> dict[str, DesignNote]:
    """The note of every design of the theme, keyed by the id of its file name.

    One design that cannot be built stops the whole page.
    """
    return {
        design_id: _note_of(design_id, base_dir)
        for design_id in designs_of_theme(theme_id, base_dir)
    }


def _note_of(design_id: str, base_dir: Path) -> DesignNote:
    """The note of *design_id*; an error names the design whose note failed."""
    try:
        return load_design_note(design_id, base_dir)
    except ValueError as exc:
        reason = " ".join(str(exc).split())
        raise ValueError(
            f"analysis note of '{design_id}' cannot be built: {reason}"
        ) from exc


def _require_linked_designs_exist(tree: QuestionTree, designs: Iterable[str]) -> None:
    """Progress is derived from linked designs, so each must exist."""
    known = set(designs)
    for node in tree.nodes:
        for design_id in node.design_ids:
            if design_id not in known:
                raise ValueError(f"design '{design_id}' not found")


def render(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, str]:
    """Write ``{theme_id}_tree.html`` from the canonical tree and return its path.

    The HTML is generated, never edited: the same tree, designs and journals give
    the same bytes. A linked design that no longer exists is an error (as in
    ``progress``) and nothing is written. Once the page is written, the
    standalone page ``notes/{id}.html`` of each design it holds is removed.

    A stale answer is not stored as withdrawn, so the page is where it shows. A
    cited id that two events share stops the check, not the page: it says so on
    the page. A journal that cannot be read stops ``render``, so the analyst is
    told which file to fix.
    """
    tree = load_tree_model(theme_id, base_dir)
    design_notes = _design_notes(theme_id, base_dir)
    _require_linked_designs_exist(tree, design_notes)
    designs = {
        design_id: DesignSummary(
            design_id,
            note.design.title,
            note.design.status,
            note.design.parent_id,
            note.design.created_at,
        )
        for design_id, note in design_notes.items()
    }
    # Every round is read, since the page shows the history of each answer.
    events, duplicated = cited_events(
        (
            cite
            for node in tree.nodes
            for answer in node.answers
            for statement in answer.statements
            for cite in statement.cites
        ),
        base_dir,
    )
    checked: list[Violation] | CheckFailed
    try:
        checked = check_cited(tree, events, duplicated)
    except ValueError as exc:
        checked = CheckFailed(str(exc))
    html = render_tree_html(
        tree,
        designs,
        events,
        checked,
        {d: render_note(n) for d, n in design_notes.items()},
    )
    path = tree_path(theme_id, base_dir).with_suffix(".html")
    atomic_write_text(path, html)
    # A standalone page left from before the theme had a tree would be a
    # second, older reading surface. Removed only once the tree page is written.
    for design_id in design_notes:
        (Path(base_dir) / "notes" / f"{design_id}.html").unlink(missing_ok=True)
    return {"path": str(path)}


def render_design(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, Any]:
    """Write the page that holds the analysis note of *design_id* and say where the note is.

    With a tree for the theme the note sits in ``{theme_id}_tree.html``, which
    is rewritten: ``path``, ``anchor`` (the note in that page) and ``node_ids``
    (the questions that link the design, in tree order, possibly none). Without
    one it is ``render_design_note``'s standalone page and only ``path``.
    A tree that exists but is invalid is an error, never a fallback.
    """
    require_design(design_id, base_dir)
    # The theme is read from the file name, as designs_of_theme does for the page.
    theme_id = theme_of(design_id)
    if theme_id is None or not load_tree(theme_id, base_dir):
        return render_design_note(design_id, base_dir)
    tree = load_tree_model(theme_id, base_dir)
    path = render(theme_id, base_dir)["path"]
    return {
        "path": path,
        "anchor": note_anchor(design_id),
        "node_ids": [n.id for n in tree.nodes if design_id in n.design_ids],
    }


class ReportStop(StrEnum):
    """Why no report is written."""

    no_tree = "no_tree"
    no_root_answer = "no_root_answer"
    violations = "violations"


def _root_answer(tree: QuestionTree) -> Answer | None:
    """The answer of the root, if it was given under the current root revision."""
    answer = tree.root().current_answer()
    if answer is None or answer.root_revision != tree.current_revision().revision:
        return None
    return answer


def _linked_notes(tree: QuestionTree, base_dir: Path) -> dict[str, DesignNote]:
    """The note of every linked design, in tree order, each once.

    The report reads a design the way its analysis note does, so the two cannot
    disagree (ADR-0039).
    """
    notes: dict[str, DesignNote] = {}
    for node in tree.nodes:
        for design_id in node.design_ids:
            if design_id not in notes:
                notes[design_id] = _note_of(design_id, base_dir)
    return notes


def _add_design_records(
    records: dict[str, CitedEvent], designs: Iterable[ReportDesign]
) -> None:
    """Add the events the report quotes from each design, as its own journal holds them.

    Their ids are not checked like the cites of an answer, so the text comes
    from the journal the report quotes, never from the journal an id names. An
    id that already stands for another text would show two texts under one id.
    """
    for design in designs:
        for event in (*design.conclude_events, *design.contradicting_evidence):
            record = CitedEvent(event.id, event.type, event.direction, event.content)
            known = records.setdefault(event.id, record)
            if (known.type, known.content) != (record.type, record.content):
                raise ValueError(
                    f"journal of '{design.id}': event id '{event.id}' also stands "
                    "for another event the report cites"
                )


def _report_node(node: QuestionNode, notes: dict[str, DesignNote]) -> ReportNode:
    return ReportNode(
        id=node.id,
        question=node.question,
        parent=node.parent_question_id or "",
        contribution=node.contribution,
        progress=Progress.of(notes[d].design.status for d in node.design_ids),
        answer=node.current_answer(),
        design_ids=tuple(node.design_ids),
        next_candidate=node.next_candidate,
    )


def _theme_report(
    tree: QuestionTree,
    root_answer: Answer,
    cited: dict[str, CitedEvent],
    base_dir: Path,
) -> ThemeReport:
    """The report of *tree*.

    *cited* are the events the check read: the report quotes what it passed.
    """
    notes = _linked_notes(tree, base_dir)
    root = tree.root()
    nodes = tuple(_report_node(n, notes) for n in tree.nodes if n is not root)
    designs = tuple(ReportDesign.of(note) for note in notes.values())
    # Two designs may read the same source; the report lists it once.
    sources = tuple(dict.fromkeys(s for note in notes.values() for s in note.sources))
    records = dict(cited)
    _add_design_records(records, designs)
    revision = tree.current_revision()
    return ThemeReport(
        theme_id=tree.theme_id,
        root_question=revision.question,
        aim=revision.aim,
        round=tree.current_round(),
        root_revision=revision.revision,
        answer=root_answer,
        nodes=nodes,
        designs=designs,
        sources=sources,
        decision=tree.decisions[-1] if tree.decisions else None,
        records=records,
    )


def report(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, Any]:
    """Write ``reports/{theme_id}.md`` from the records of the theme, unless it cannot be trusted.

    Nothing is written, and an older report is left as it is, when the theme has
    no tree, when its root has no answer under the current root revision, or when
    the check finds a violation on any node. The result then holds ``reasons``,
    each with its ``kind`` (a ``ReportStop``) and a ``message``.

    A tree that fails its schema, a journal that cannot be read and a cited id
    that two events share stay errors. So does a linked design that no longer
    exists, as in ``progress``. A linked design that is not finished does not
    stop the report: ``unfinished_designs`` names it. ``round`` is the last
    reflection round of the tree, ``root_answer_round`` the one that wrote the
    answer to the root.
    """
    if not load_tree(theme_id, base_dir):
        return {
            "written": False,
            "reasons": [
                {
                    "kind": ReportStop.no_tree,
                    "message": f"Theme '{theme_id}' has no question tree",
                }
            ],
        }
    tree = load_tree_model(theme_id, base_dir)
    reasons: list[dict[str, Any]] = []
    root_answer = _root_answer(tree)
    if root_answer is None:
        revision = tree.current_revision().revision
        reasons.append(
            {
                "kind": ReportStop.no_root_answer,
                "message": f"The root of theme '{theme_id}' has no answer given "
                f"under root revision {revision}",
            }
        )
    # Read once: a journal rewritten between the check and the report would
    # put a number the check never saw into the report.
    events, duplicated = cited_events(current_cites(tree), base_dir)
    violations = check_cited(tree, events, duplicated)
    if violations:
        reasons.append(
            {
                "kind": ReportStop.violations,
                "message": f"The answers of theme '{theme_id}' have "
                f"{len(violations)} violation(s) of the cited-answer check",
                "violations": [asdict(v) for v in violations],
            }
        )
    if reasons or root_answer is None:
        return {"written": False, "reasons": reasons}

    theme_report = _theme_report(tree, root_answer, events, base_dir)
    report_path = Path(base_dir) / "reports" / f"{theme_id}.md"
    atomic_write_text(report_path, render_report(theme_report))
    return {
        "written": True,
        "path": str(report_path),
        "figures": theme_report.figures(),
        "round": theme_report.round,
        # A later round may have answered other nodes only, so the last round
        # does not say how old the answer to the root is.
        "root_answer_round": root_answer.round,
        "unfinished_designs": [
            d.id for d in theme_report.designs if d.status not in TERMINAL_STATUSES
        ],
    }
