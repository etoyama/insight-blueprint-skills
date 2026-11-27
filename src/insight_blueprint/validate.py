"""Pure-function validation library for analysis design documents.

This module is the single source of truth for design-document integrity
(ADR-0001). It consolidates the Pydantic schema validation of
:class:`AnalysisDesign` and the state-transition guard formerly living in
``core/reviews.py``.

It must stay **pure**: no file/network I/O, no service-layer imports. The
pre-write hook (``.claude/hooks/validate-design.py``) and the MCP review
service both call these functions; the hook owns all I/O and passes plain
dicts in.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    AnalysisIntent,
    DesignForm,
    DesignStatus,
    MetricTier,
)
from insight_blueprint.models.journal import JOURNAL_MARKS
from insight_blueprint.models.tree import QuestionTree

# State-transition allow-table, for every form at once: which conclusion a
# design may reach is narrowed by its form (DesignForm.allows). This is the
# canonical definition.
VALID_TRANSITIONS: dict[DesignStatus, set[DesignStatus]] = {
    DesignStatus.in_review: {
        DesignStatus.revision_requested,
        DesignStatus.analyzing,
        *TERMINAL_STATUSES,
    },
    DesignStatus.revision_requested: {
        DesignStatus.in_review,
        DesignStatus.revision_requested,
        DesignStatus.analyzing,
        *TERMINAL_STATUSES,
    },
    # A reflection concludes an analyzed design directly; in_review stays for an
    # optional review of the result (ADR-0029).
    DesignStatus.analyzing: {DesignStatus.in_review, *TERMINAL_STATUSES},
    DesignStatus.explored: set(),
    DesignStatus.supported: set(),
    DesignStatus.rejected: set(),
    DesignStatus.inconclusive: set(),
}

# The statuses a design takes only once its analysis has started.
ANALYSIS_STARTED_STATUSES = frozenset({DesignStatus.analyzing, *TERMINAL_STATUSES})


def analysis_started(design: AnalysisDesign) -> bool:
    """Whether the analysis of *design* has started (ADR-0053).

    The mark tells it in any status, so a review of the result that sends the
    design back to in_review does not hide it. A design saved before the mark
    existed is read by its status.
    """
    return (
        design.analysis_started_at is not None
        or design.status in ANALYSIS_STARTED_STATUSES
    )


def with_analysis_mark(new: AnalysisDesign, current: AnalysisDesign) -> AnalysisDesign:
    """*new* with the analysis mark, when the write over *current* puts it on.

    The first move into analyzing or a conclusion starts the analysis. A design
    saved before the mark existed shows its analysis only by its status, so its
    next move writes the mark too, with the time of that move (ADR-0053
    decisions 1, 2). ``_mark_errors`` holds every write to this rule.
    """
    moves = new.status != current.status
    starts = new.status in ANALYSIS_STARTED_STATUSES or analysis_started(current)
    if new.analysis_started_at is None and moves and starts:
        return new.model_copy(update={"analysis_started_at": new.updated_at})
    return new


def valid_targets(current: DesignStatus, form: DesignForm) -> set[DesignStatus]:
    """The statuses a design of *form* may move to from *current*."""
    return {t for t in VALID_TRANSITIONS.get(current, set()) if form.allows(t)}


def validate_transition(
    current: DesignStatus, target: DesignStatus, form: DesignForm
) -> None:
    """Validate that a design of *form* may move from *current* to *target*.

    Raises ValueError naming the valid targets of that form.
    """
    targets = valid_targets(current, form)
    if target not in targets:
        valid_str = ", ".join(sorted(s.value for s in targets)) if targets else "none"
        raise ValueError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Valid targets: {valid_str}"
        )


def validate_schema(data: dict) -> AnalysisDesign:
    """Validate a raw design dict against the AnalysisDesign schema.

    Returns the parsed model. Raises pydantic ``ValidationError`` on a schema
    violation (e.g. empty ``methodology.method``, invalid ``status``, missing
    required field). Backward-compat coercions (metrics/chart) run inside the
    model's validators.
    """
    return AnalysisDesign.model_validate(data)


def validate_design_change(
    new_data: dict, current_data: dict | None = None
) -> list[str]:
    """Validate a pending write to a design document.

    Hook-facing aggregator. Never raises: returns a list of human-readable
    error strings (empty list means the write is valid).

    - *new_data*: the design dict about to be written.
    - *current_data*: the design dict currently on disk, or ``None`` for a new
      file. A new file is checked by the schema only, the opening ADR-0049
      leaves; a write over a readable design meets ``validate_update``, the
      check ``design_io`` runs on update, and one over a broken design meets
      ``validate_repair``.
    """
    try:
        new_model = validate_schema(new_data)
    except ValidationError as exc:
        # Schema is the gate: if new_data is malformed, report and stop. A
        # transition check on unparseable data would be meaningless.
        return _format_validation_error(exc)

    if current_data is None:
        return []

    try:
        current_model = validate_schema(current_data)
    except ValidationError:
        # The on-disk file is already invalid and the write may be repairing
        # it: only what a started analysis holds is compared.
        return validate_repair(new_model, current_data)

    return validate_update(new_model, current_model)


_INTENT_HELD = (
    "analysis_intent: the intent and the form change only before the "
    "analysis starts; derive a new design (parent_id) for another intent"
)
_MIXED_REFUSED = (
    "analysis_intent: 'mixed' cannot be chosen any more; "
    "choose exploratory or confirmatory"
)
_LEGACY_REFUSED = (
    "an exploratory design holds exploration_question and "
    "exploration_background, not hypothesis_statement"
)


def validate_creation(new: AnalysisDesign) -> list[str]:
    """The check of a new design: only the new forms are written (ADR-0049).

    Runs after the schema has passed. The read check (the schema) lets a legacy
    exploration and a mixed design through, so saved designs still read; this
    one refuses to make either. Never raises: returns human-readable error strings.
    """
    errors: list[str] = []
    if new.analysis_intent is AnalysisIntent.mixed:
        errors.append(_MIXED_REFUSED)
    if new.form() is DesignForm.legacy_exploration:
        errors.append(_LEGACY_REFUSED)
    if new.form() is DesignForm.confirmation:
        errors += _unwritten_hypothesis(new)
    return errors


def validate_update(new: AnalysisDesign, current: AnalysisDesign) -> list[str]:
    """The check of a write over *current*, the design on disk (ADR-0048, ADR-0049).

    A saved legacy exploration or mixed design is updated in its form, but no
    design is turned into one; the intent and the form change only before the
    analysis, and a status change follows the transitions of the new form. Once
    the analysis has started, the mark of it stays and a design that judges a
    hypothesis keeps that hypothesis and its criterion (ADR-0053). Never raises:
    returns human-readable error strings.
    """
    errors: list[str] = []
    intent_changed = new.analysis_intent != current.analysis_intent
    if new.analysis_intent is AnalysisIntent.mixed and intent_changed:
        errors.append(_MIXED_REFUSED)
    if (
        new.form() is DesignForm.legacy_exploration
        and current.form() is not DesignForm.legacy_exploration
    ):
        errors.append(_LEGACY_REFUSED)
    # Swapping the fields changes the form without touching the intent (a legacy
    # exploration into the new form), so the form is held to the same rule.
    reshaped = intent_changed or new.form() != current.form()
    if reshaped and not _may_change_intent(current, new):
        errors.append(_INTENT_HELD)
    if new.form() is DesignForm.confirmation and intent_changed:
        errors += _unwritten_hypothesis(new)
    if new.status != current.status:
        try:
            validate_transition(current.status, new.status, new.form())
        except ValueError as exc:
            errors.append(str(exc))
    return (
        errors
        + _mark_errors(new, current)
        + _held_errors(new, current)
        + _criterion_errors(new, current)
    )


_MARK_HELD = (
    "analysis_started_at: the mark of a started analysis is neither removed nor changed"
)


def _left_without_the_mark(status: DesignStatus) -> str:
    return (
        f"analysis_started_at: a design that leaves {status.value} keeps the "
        "mark of its analysis; move it with design_io transition, which writes "
        "the mark"
    )


def _mark_errors(new: AnalysisDesign, current: AnalysisDesign) -> list[str]:
    was, now = current.analysis_started_at, new.analysis_started_at
    if was is not None:
        return [] if now == was else [_MARK_HELD]
    if analysis_started(current) and not analysis_started(new):
        # A design saved before the mark existed shows its analysis only by its
        # status: leaving that status without the mark would erase the trace.
        return [_left_without_the_mark(current.status)]
    entered = analysis_started(current) or new.status in ANALYSIS_STARTED_STATUSES
    if now is not None and not entered:
        return [
            "analysis_started_at: the mark is written when the design first "
            "enters analyzing or a conclusion, not before"
        ]
    return []


_DERIVE = "derive a new design (parent_id) and leave this one as it was analyzed"
_HYPOTHESIS_HELD = (
    "hypothesis_statement: the hypothesis does not change once the analysis "
    f"has started; {_DERIVE}"
)
_CRITERIA_HELD = (
    "metrics: the primary metrics (target, comparison, tier) do not change "
    f"once the analysis has started; {_DERIVE}"
)


def _held_errors(new: AnalysisDesign, current: AnalysisDesign) -> list[str]:
    """What a started design that judges a hypothesis keeps (ADR-0053 decision 3)."""
    if not (analysis_started(current) and current.form().judges):
        return []
    errors: list[str] = []
    # Dropping the hypothesis altogether is a change of form, refused as one.
    reworded = new.form().judges and (
        new.hypothesis_statement != current.hypothesis_statement
    )
    if reworded:
        errors.append(_HYPOTHESIS_HELD)
    if _criteria(new) != _criteria(current):
        errors.append(_CRITERIA_HELD)
    return errors


def _criteria(design: AnalysisDesign) -> list[tuple[str, str]]:
    """The primary metrics as what the judgment rests on, whatever their order."""
    return sorted(
        (m.target, m.comparison) for m in design.metrics if m.tier is MetricTier.primary
    )


def validate_repair(new: AnalysisDesign, current: dict) -> list[str]:
    """The check of a write over *current*, a design on disk that no longer reads.

    The write may be repairing it, so the update check does not run. Yet a
    broken record that tells its analysis started, by the mark or by its
    status, keeps what a readable one keeps: the mark, the intent, the
    hypothesis and, when it judges a hypothesis, its primary metrics (ADR-0053
    decisions 1, 3, 5). Without that, breaking a record would lift the hold.
    The record may be broken anywhere, so each item is compared only when it
    still reads, and an item that does not read is not taken as unchanged
    either. Never raises: returns human-readable error strings.
    """
    if not _record_started(current):
        return []
    errors = _record_mark_errors(new, current)
    if _record_intent_changed(new, current):
        errors.append(_INTENT_HELD)
    was = current.get("hypothesis_statement")
    if (was is None or isinstance(was, str)) and new.hypothesis_statement != was:
        errors.append(_HYPOTHESIS_HELD)
    if _record_judges(current) and _record_criteria_changed(new, current):
        errors.append(_CRITERIA_HELD)
    return errors


_MARK_READER = TypeAdapter(datetime)
_E = TypeVar("_E", bound=Enum)


def _read_as(kind: type[_E], value: Any) -> _E | None:
    """*value* as a member of *kind*, or None when the record does not read so."""
    try:
        return kind(value)
    except (ValueError, TypeError):
        return None


def _record_status(record: dict) -> DesignStatus | None:
    return _read_as(DesignStatus, record.get("status", DesignStatus.in_review))


def _record_intent(record: dict) -> AnalysisIntent | None:
    return _read_as(
        AnalysisIntent, record.get("analysis_intent", AnalysisIntent.confirmatory)
    )


def _record_started(record: dict) -> bool:
    return (
        record.get("analysis_started_at") is not None
        or _record_status(record) in ANALYSIS_STARTED_STATUSES
    )


def _record_mark_errors(new: AnalysisDesign, record: dict) -> list[str]:
    was = record.get("analysis_started_at")
    if was is None:
        # Started by its status alone, as a design saved before the mark.
        status = _record_status(record)
        if analysis_started(new) or status is None:
            return []
        return [_left_without_the_mark(status)]
    if new.analysis_started_at is None:
        return [_MARK_HELD]
    try:
        mark = _MARK_READER.validate_python(was)
    except ValidationError:
        return []  # only that the mark is there reads
    return [] if mark == new.analysis_started_at else [_MARK_HELD]


def _record_intent_changed(new: AnalysisDesign, record: dict) -> bool:
    was = _record_intent(record)
    if was is None or was is new.analysis_intent:
        return False
    # ADR-0049 decision 6, as _may_change_intent allows it on a readable record.
    fixed_as_confirmation = (
        was is AnalysisIntent.exploratory
        and record.get("exploration_question") is None
        and new.analysis_intent is AnalysisIntent.confirmatory
        and _record_status(record) == new.status
        and record.get("hypothesis_statement") == new.hypothesis_statement
        and record.get("hypothesis_background") == new.hypothesis_background
    )
    return not fixed_as_confirmation


def _record_judges(record: dict) -> bool:
    """Whether the record is not an exploration; one that does not read is held."""
    asks = record.get("exploration_question") is not None
    return not (asks and _record_intent(record) is AnalysisIntent.exploratory)


def _record_criteria_changed(new: AnalysisDesign, record: dict) -> bool:
    read = _record_criteria(record)
    if read is None:
        return False
    held, unread = read
    now = Counter(_criteria(new))
    # A metric that does not read may be the one the write repairs into a
    # primary one, so it may stand for one criterion of the write, no more.
    return bool(held - now) or (now - held).total() > unread


def _record_criteria(
    record: dict,
) -> tuple[Counter[tuple[str, str]], int] | None:
    """The primary metrics the record reads as, and how many metrics do not read.

    None when the metrics do not read at all. A metric without tier is primary,
    as the schema reads it; the legacy shapes are the ones the schema migrates.
    """
    metrics = record.get("metrics", [])
    if metrics is None or metrics == {}:
        metrics = []
    elif isinstance(metrics, dict) and "target" in metrics:
        metrics = [metrics]
    if not isinstance(metrics, list):
        return None
    held: Counter[tuple[str, str]] = Counter()
    unread = 0
    for metric in metrics:
        tier = (
            _read_as(MetricTier, metric.get("tier", MetricTier.primary))
            if isinstance(metric, dict)
            else None
        )
        if tier is None:
            unread += 1
        elif tier is MetricTier.primary:
            target, comparison = metric.get("target"), metric.get("comparison", "")
            if isinstance(target, str) and isinstance(comparison, str):
                held[(target, comparison)] += 1
            else:
                unread += 1
    return held, unread


_NEEDS_CRITERION = frozenset(
    {DesignStatus.analyzing, DesignStatus.supported, DesignStatus.rejected}
)


def _criterion_errors(new: AnalysisDesign, current: AnalysisDesign) -> list[str]:
    """A judging design starts with its criterion written (decisions 4 and 8).

    Without one it is neither analyzed nor given a verdict of its hypothesis; it
    may still be closed as inconclusive, the way out of an analysis not run.
    Only the first entry is checked: a started design can no longer write its
    criterion, so asking again would leave a saved one nowhere to go.
    """
    entering = new.status in _NEEDS_CRITERION and not analysis_started(current)
    if not (entering and new.form().judges):
        return []
    criteria = _criteria(new)
    unwritten = [target for target, comparison in criteria if not comparison.strip()]
    if criteria and not unwritten:
        return []
    lacking = f" (comparison is empty: {', '.join(unwritten)})" if unwritten else ""
    return [
        f"metrics: a design that judges a hypothesis enters {new.status.value} "
        "only when it has a primary metric and every primary metric (a metric "
        "without tier is primary) states the criterion in its comparison"
        f"{lacking}; write it with /analysis-design before any result is seen, "
        "or close the design as inconclusive"
    ]


def _unwritten_hypothesis(new: AnalysisDesign) -> list[str]:
    return [
        f"{name}: a confirmation needs it written"
        for name in ("hypothesis_statement", "hypothesis_background")
        if not (getattr(new, name) or "").strip()
    ]


def _may_change_intent(current: AnalysisDesign, new: AnalysisDesign) -> bool:
    if not analysis_started(current):
        return True
    # A legacy exploration whose substance is a confirmation is fixed in any
    # status, since only the intent changes: the hypothesis and the status stay
    # as they were written before the result (ADR-0049 decision 6).
    return (
        current.form() is DesignForm.legacy_exploration
        and new.analysis_intent is AnalysisIntent.confirmatory
        and new.status == current.status
        and new.hypothesis_statement == current.hypothesis_statement
        and new.hypothesis_background == current.hypothesis_background
    )


def _marked_events(data: dict | None) -> list:
    events = (data or {}).get("events") or []
    if not isinstance(events, list):
        raise ValueError("events: a journal holds a list of events")
    # Read as plain data, so the order of keys in a mapping does not count.
    return [
        json.loads(json.dumps(event, default=str))
        for event in events
        if isinstance(event, dict)
        and isinstance(event.get("metadata"), dict)
        and any(mark in event["metadata"] for mark in JOURNAL_MARKS)
    ]


def validate_journal_change(new: dict, current: dict | None) -> list[str]:
    """Errors for a hand write of a journal (ADR-0067). Empty means allowed.

    The events that hold a mark of ``JOURNAL_MARKS`` must stay exactly as they
    are: a mark is added, changed or removed only by design_io, whose writes
    the hook does not see. Every other event is free. A journal on disk that
    cannot be read is read as holding no marks.
    """
    try:
        written = _marked_events(new)
    except ValueError as exc:
        return [str(exc)]
    try:
        kept = _marked_events(current)
    except ValueError:
        kept = []
    if written == kept:
        return []
    return [
        f"metadata.{'/'.join(JOURNAL_MARKS)}: events with these marks are written "
        "only by design_io ask-analyst, answer-analyst and stop, and never "
        "changed or removed by hand"
    ]


def validate_tree_schema(data: dict) -> QuestionTree:
    """Validate a raw question tree dict against the QuestionTree schema.

    Returns the parsed model. Raises pydantic ``ValidationError`` when the
    shape or an invariant of the tree is broken.
    """
    return QuestionTree.model_validate(data)


def validate_tree(
    data: dict,
    expected_theme_id: str | None = None,
    current: dict | None = None,
) -> list[str]:
    """Validate a question tree document (ADR-0024).

    Hook-facing. Never raises: returns human-readable error strings (empty
    list means the tree is valid). *expected_theme_id* is the theme the file name carries;
    the caller owns the path and passes it in so this stays pure.
    *current* is the tree on disk, or ``None`` for a new file: its root
    revisions, decisions and answers are history: none may be removed, only the
    last root revision may differ, and decisions and answers may only be appended.
    """
    try:
        tree = validate_tree_schema(data)
    except ValidationError as exc:
        return _format_validation_error(exc)
    if expected_theme_id is not None and tree.theme_id != expected_theme_id:
        return [
            f"theme_id: '{tree.theme_id}' does not match the file name "
            f"({expected_theme_id}_tree.yaml)"
        ]
    if current is None:
        return []
    try:
        on_disk = validate_tree_schema(current)
    except ValidationError:
        # The file on disk is already broken; do not block the write that
        # may be repairing it.
        return []
    return (
        _revision_errors(on_disk, tree)
        + _decision_errors(on_disk, tree)
        + _answer_errors(on_disk, tree)
    )


def _revision_errors(on_disk: QuestionTree, written: QuestionTree) -> list[str]:
    before, after = on_disk.root_revisions, written.root_revisions
    # Only the last revision of the written tree may differ from the disk:
    # appending one freezes every revision that was there before.
    frozen = len(before) if len(after) > len(before) else len(before) - 1
    return _append_only_errors(
        "root_revisions",
        removed="a root revision",
        names=[f"revision {r.revision}" for r in before],
        before=before,
        after=after,
        frozen=frozen,
    )


def _decision_errors(on_disk: QuestionTree, written: QuestionTree) -> list[str]:
    before, after = on_disk.decisions, written.decisions
    return _append_only_errors(
        "decisions",
        removed="a decision",
        # A decision carries no number of its own, so its position names it.
        names=[f"decision {n}" for n in range(1, len(before) + 1)],
        before=before,
        after=after,
        frozen=len(before),
    )


def _answer_errors(on_disk: QuestionTree, written: QuestionTree) -> list[str]:
    now = {n.id: n.answers for n in written.nodes}
    errors: list[str] = []
    for node in on_disk.nodes:
        errors += _append_only_errors(
            f"{node.id}.answers",
            removed="an answer",
            # tree_check names an answer by its round, and a node need not be
            # answered every round: the position would point at another answer.
            names=[f"the answer of round {a.round}" for a in node.answers],
            before=node.answers,
            after=now.get(node.id, []),
            frozen=len(node.answers),
        )
    return errors


def _append_only_errors(
    field: str,
    *,
    removed: str,
    names: Sequence[str],
    before: Sequence[BaseModel],
    after: Sequence[BaseModel],
    frozen: int,
) -> list[str]:
    """Errors for a history list: nothing removed, the first *frozen* items unchanged.

    *names* gives what a message calls each item of *before*.
    """
    if len(after) < len(before):
        return [f"{field}: {removed} cannot be removed ({len(before)} -> {len(after)})"]
    return [
        f"{field}: {name} is history and cannot change"
        for name, old, new in zip(names, before[:frozen], after, strict=False)
        if old != new
    ]


def _format_validation_error(exc: ValidationError) -> list[str]:
    """Render a pydantic ValidationError as a list of human-readable lines."""
    lines: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"{loc}: {err['msg']}")
    return lines
