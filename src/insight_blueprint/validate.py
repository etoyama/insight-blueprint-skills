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

from pydantic import ValidationError

from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.models.tree import QuestionTree

# State-transition allow-table. This is the canonical definition; core/reviews.py
# imports it from here to avoid duplication.
VALID_TRANSITIONS: dict[DesignStatus, set[DesignStatus]] = {
    DesignStatus.in_review: {
        DesignStatus.revision_requested,
        DesignStatus.analyzing,
        DesignStatus.supported,
        DesignStatus.rejected,
        DesignStatus.inconclusive,
    },
    DesignStatus.revision_requested: {
        DesignStatus.in_review,
        DesignStatus.revision_requested,
        DesignStatus.analyzing,
        DesignStatus.supported,
        DesignStatus.rejected,
        DesignStatus.inconclusive,
    },
    DesignStatus.analyzing: {DesignStatus.in_review},
    DesignStatus.supported: set(),
    DesignStatus.rejected: set(),
    DesignStatus.inconclusive: set(),
}


def validate_transition(current: DesignStatus, target: DesignStatus) -> None:
    """Validate that a transition from *current* to *target* is allowed.

    Raises ValueError with the same message as the former
    ``reviews._validate_transition`` so MCP-path behaviour is unchanged.
    """
    valid_targets = VALID_TRANSITIONS.get(current, set())
    if target not in valid_targets:
        valid_str = (
            ", ".join(sorted(s.value for s in valid_targets))
            if valid_targets
            else "none"
        )
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
            validate_transition(current_model.status, new_model.status)
        except ValueError as exc:
            errors.append(str(exc))

    return errors


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
    revisions and decisions are history: none may be removed, only the last
    root revision may differ, and decisions may only be appended.
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
    return _revision_errors(on_disk, tree) + _decision_errors(on_disk, tree)


def _revision_errors(on_disk: QuestionTree, written: QuestionTree) -> list[str]:
    before, after = on_disk.root_revisions, written.root_revisions
    if len(after) < len(before):
        return [
            "root_revisions: a root revision cannot be removed "
            f"({len(before)} -> {len(after)})"
        ]
    # Only the last revision of the written tree may differ from the disk:
    # appending one freezes every revision that was there before.
    history = before if len(after) > len(before) else before[:-1]
    return [
        f"root_revisions: revision {old.revision} is history and cannot change"
        for old, new in zip(history, after, strict=False)
        if old != new
    ]


def _decision_errors(on_disk: QuestionTree, written: QuestionTree) -> list[str]:
    before, after = on_disk.decisions, written.decisions
    if len(after) < len(before):
        return [
            f"decisions: a decision cannot be removed ({len(before)} -> {len(after)})"
        ]
    return [
        f"decisions: decision {n} is history and cannot change"
        for n, (old, new) in enumerate(zip(before, after, strict=False), start=1)
        if old != new
    ]


def _format_validation_error(exc: ValidationError) -> list[str]:
    """Render a pydantic ValidationError as a list of human-readable lines."""
    lines: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"{loc}: {err['msg']}")
    return lines
