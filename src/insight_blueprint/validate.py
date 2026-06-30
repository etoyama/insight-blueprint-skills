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


def _format_validation_error(exc: ValidationError) -> list[str]:
    """Render a pydantic ValidationError as a list of human-readable lines."""
    lines: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"{loc}: {err['msg']}")
    return lines
