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

from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    AnalysisIntent,
    DesignForm,
    DesignStatus,
)
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

# The intent is chosen before the analysis: changing it afterwards would let a
# hypothesis be set after seeing the result (ADR-0048).
INTENT_CHANGEABLE = frozenset({DesignStatus.in_review, DesignStatus.revision_requested})


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
      file. When given and the status actually changes, the transition is
      checked. New files are schema-only (no transition check), matching the
      existing ``DesignService.create_design`` behaviour.
    """
    errors: list[str] = []

    try:
        new_model = validate_schema(new_data)
    except ValidationError as exc:
        # Schema is the gate: if new_data is malformed, report and stop. A
        # transition check on unparseable data would be meaningless.
        return _format_validation_error(exc)

    if current_data is None:
        return errors

    try:
        current_model = validate_schema(current_data)
    except ValidationError:
        # The on-disk file is already invalid; we cannot derive a reliable
        # "current status" from it. Skip the transition check rather than
        # blocking on a pre-existing corruption the user may be fixing.
        return errors

    if new_model.status != current_model.status:
        try:
            validate_transition(
                current_model.status, new_model.status, new_model.form()
            )
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def validate_creation(
    new: AnalysisDesign, current: AnalysisDesign | None = None
) -> list[str]:
    """The check of the create path: only the new forms are written (ADR-0049).

    ``design_io`` runs it on create (*current* is ``None``) and on update
    (*current* is the design on disk), after the schema has passed. The read
    check (the schema, which the hook runs) lets a legacy exploration and a
    mixed design through, so saved designs still read; this one refuses to
    make either. Never raises: returns human-readable error strings.
    """
    errors: list[str] = []
    intent_changed = current is not None and new.analysis_intent != (
        current.analysis_intent
    )
    if new.analysis_intent is AnalysisIntent.mixed and (
        current is None or intent_changed
    ):
        errors.append(
            "analysis_intent: 'mixed' cannot be chosen any more; "
            "choose exploratory or confirmatory"
        )
    if new.form() is DesignForm.legacy_exploration and (
        current is None or current.form() is not DesignForm.legacy_exploration
    ):
        errors.append(
            "an exploratory design holds exploration_question and "
            "exploration_background, not hypothesis_statement"
        )
    # Swapping the fields changes the form without touching the intent (a legacy
    # exploration into the new form), so the form is held to the same rule.
    reshaped = intent_changed or (current is not None and new.form() != current.form())
    if current is not None and reshaped and not _may_change_intent(current, new):
        errors.append(
            f"analysis_intent: changes only while in_review or revision_requested "
            f"(status: {current.status.value}); derive a new design for another intent"
        )
    if new.form() is DesignForm.confirmation and (current is None or intent_changed):
        errors += [
            f"{name}: a confirmation needs it written"
            for name in ("hypothesis_statement", "hypothesis_background")
            if not (getattr(new, name) or "").strip()
        ]
    return errors


def _may_change_intent(current: AnalysisDesign, new: AnalysisDesign) -> bool:
    if current.status in INTENT_CHANGEABLE:
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
