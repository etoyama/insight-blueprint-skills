"""Server-free YAML I/O for analysis design documents (Epic 3).

Skills call this instead of MCP tools. It replicates the DesignService /
ReviewService behaviour (id generation, timestamps, merge, transition, review
batches) but depends only on modules that survive the server removal (E4):
``insight_blueprint.validate`` (the single validation source) and
``insight_blueprint.models``. All writes go through validation first — the
pre-write hook only guards the Write/Edit tool path, not direct python writes.

Usage from a skill (CLI):
    echo '<json>' | python -m skills._shared.design_io create --base-dir .insight
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML

from insight_blueprint.models.analysis_stage import (
    ASKS_FROM,
    MARKS,
    STOPS_FROM,
    AnalysisStage,
    answer,
    asks_analyst,
    confirmation,
    open_confirmations,
    stop,
)
from insight_blueprint.models.common import THEME_ID_PATTERN, now_jst
from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.models.review import BatchComment, ReviewBatch
from insight_blueprint.validate import (
    VALID_TRANSITIONS,
    analysis_started,
    validate_creation,
    validate_repair,
    validate_schema,
    validate_transition,
    validate_update,
    with_analysis_mark,
)
from skills._shared._atomic import atomic_write_yaml, write_lock
from skills._shared._stdin import read_payload
from skills._shared.ids import SAFE_ID_PATTERN

DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))


def _validate_id(design_id: str) -> None:
    if not SAFE_ID_PATTERN.fullmatch(design_id):
        raise ValueError(f"Invalid design_id '{design_id}': must match [a-zA-Z0-9_-]+")


def resolve_base_dir(base_dir: Path) -> Path:
    """Normalize the I/O base and reject an absurd anchor (defense in depth).

    ``INSIGHT_BASE_DIR`` / ``--base-dir`` flow verbatim into every read/write path, so an
    attacker-influenceable value should not be trusted as-is. We only reject genuinely
    absurd anchors (the filesystem root or the bare home dir) rather than enforcing a
    ``.insight`` suffix — the bin wrapper owns that stricter check, and tests / --base-dir
    back-compat legitimately use tmp dirs.
    See docs/adr/0006-plugin-execution-model.md and review-security-epic09.md (M1).
    """
    resolved = base_dir.expanduser().resolve()
    if resolved.parent == resolved:  # filesystem root, e.g. "/"
        raise ValueError(
            f"Invalid base_dir '{base_dir}': resolves to the filesystem root"
        )
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    if home is not None and resolved == home:
        raise ValueError(
            f"Invalid base_dir '{base_dir}': resolves to the home directory"
        )
    return resolved


# Sections a review comment may target. Kept here (not imported from the
# to-be-removed core/reviews.py) so design_io is server-independent.
ALLOWED_TARGET_SECTIONS: set[str] = {
    "exploration_question",
    "exploration_background",
    "hypothesis_statement",
    "hypothesis_background",
    "metrics",
    "explanatory",
    "chart",
    "next_action",
    "referenced_knowledge",
    "methodology",
    "analysis_intent",
    "decision_context",
    # The result, for a review after the analysis (ADR-0054 1).
    "notebook",
    "verdict",
    "figures",
}

_REVIEWABLE = {DesignStatus.in_review, DesignStatus.revision_requested}


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _designs_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "designs"


def read_yaml(path: Path) -> dict:
    """Read a YAML file into a dict; {} if missing or empty."""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = _yaml().load(f)
    return dict(data) if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Design CRUD
# ---------------------------------------------------------------------------


def load_design(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Load ``{design_id}_hypothesis.yaml`` as a dict; {} if absent."""
    _validate_id(design_id)
    return read_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml")


def list_designs(
    base_dir: Path = DEFAULT_BASE_DIR, status: str | None = None
) -> list[dict]:
    """List designs as dicts, sorted by id, optionally filtered by status."""
    designs_dir = _designs_dir(base_dir)
    if not designs_dir.exists():
        return []
    out: list[dict] = []
    for path in sorted(designs_dir.glob("*_hypothesis.yaml")):
        data = read_yaml(path)
        if not data:
            continue
        if status is None or data.get("status") == status:
            out.append(data)
    return out


# A design id is ``{theme_id}-H{nn}``: the theme is read from it, as from a file name.
_DESIGN_ID = re.compile(r"(.+)-H(\d+)")


def _design_id_parts(design_id: str) -> tuple[str, int] | None:
    found = _DESIGN_ID.fullmatch(design_id)
    if not found or not THEME_ID_PATTERN.fullmatch(found[1]):
        return None
    return found[1], int(found[2])


def theme_of(design_id: str) -> str | None:
    """The theme of *design_id*, or None when the id is not ``{theme_id}-H{nn}``."""
    parts = _design_id_parts(design_id)
    return parts[0] if parts else None


def design_number(design_id: str) -> int | None:
    """The number after ``-H`` in *design_id*, or None when the id is not ``{theme_id}-H{nn}``."""
    parts = _design_id_parts(design_id)
    return parts[1] if parts else None


def designs_of_theme(
    theme_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict[str, dict]:
    """The designs of *theme_id*, keyed by the id in their file name as ``load_design`` knows them.

    A copied design file still carries the id of its source, so the id inside
    the file is not read. Only files of this theme are opened: a broken design
    of another theme must not stop a reader of this one.
    """
    # theme_id goes into a glob and a pattern, so it is checked before any I/O.
    if not THEME_ID_PATTERN.fullmatch(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    found: dict[str, dict] = {}
    for path in sorted(_designs_dir(base_dir).glob(f"{theme_id}-H*_hypothesis.yaml")):
        design_id = path.name.removesuffix("_hypothesis.yaml")
        if theme_of(design_id) == theme_id:
            found[design_id] = read_yaml(path)
    return found


def next_design_id(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> str:
    """Return the next id ``{theme_id}-H{nn}`` using a max-N+1 strategy."""
    if not THEME_ID_PATTERN.fullmatch(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    designs_dir = _designs_dir(base_dir)
    max_n = 0
    if designs_dir.exists():
        for path in designs_dir.glob(f"{theme_id}-H*_hypothesis.yaml"):
            design_id = path.name.removesuffix("_hypothesis.yaml")
            if theme_of(design_id) == theme_id:
                max_n = max(max_n, design_number(design_id) or 0)
    return f"{theme_id}-H{max_n + 1:02d}"


def create_design(
    *,
    title: str,
    hypothesis_statement: str | None = None,
    hypothesis_background: str | None = None,
    exploration_question: str | None = None,
    exploration_background: str | None = None,
    theme_id: str = "DEFAULT",
    parent_id: str | None = None,
    analysis_intent: str = "confirmatory",
    methodology: dict | None = None,
    metrics: list[dict] | None = None,
    explanatory: list[dict] | None = None,
    chart: list[dict] | None = None,
    source_ids: list[str] | None = None,
    next_action: dict | None = None,
    referenced_knowledge: dict[str, list[str]] | None = None,
    decision_context: dict | None = None,
    data_scope: dict | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Create a design document. Validates via validate.py before writing.

    An exploration passes ``exploration_question`` and ``exploration_background``,
    a confirmation ``hypothesis_statement`` and ``hypothesis_background``
    (ADR-0048). Returns the written dict. Raises ValueError (bad theme_id, or a
    form that cannot be created: mixed, a legacy exploration) or pydantic
    ValidationError (schema) without writing on failure.
    """
    with write_lock(base_dir):
        design_id = next_design_id(theme_id, base_dir)
        candidate: dict[str, Any] = {
            "id": design_id,
            "theme_id": theme_id,
            "title": title,
            "exploration_question": exploration_question,
            "exploration_background": exploration_background,
            "hypothesis_statement": hypothesis_statement,
            "hypothesis_background": hypothesis_background,
            "analysis_intent": analysis_intent,
            "parent_id": parent_id,
            "metrics": metrics or [],
            "explanatory": explanatory or [],
            "chart": chart or [],
            "source_ids": source_ids or [],
            "next_action": next_action,
            "referenced_knowledge": referenced_knowledge or {},
            "decision_context": decision_context,
        }
        if methodology is not None:
            candidate["methodology"] = methodology
        if data_scope is not None:
            candidate["data_scope"] = data_scope

        model = validate_schema(candidate)  # raises ValidationError if invalid
        errors = validate_creation(model)
        if errors:
            raise ValueError("; ".join(errors))
        data = model.model_dump(mode="json")
        atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml", data)
        return data


def _merge_referenced_knowledge(
    current: dict[str, list[str]], incoming: dict[str, list[str]]
) -> dict[str, list[str]]:
    result = dict(current)
    for key, new_keys in incoming.items():
        result[key] = list(dict.fromkeys([*result.get(key, []), *new_keys]))
    return result


def update_design(
    design_id: str, changes: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Read-merge-write a design. Refreshes updated_at, merges referenced_knowledge.

    Validates schema, the create-path check (intent and form) and the transition
    via validate.py. A field of the other form is dropped by passing it as None.
    Raises ValueError if the design is absent or the change is invalid; nothing
    is written on failure.
    """
    with write_lock(base_dir):
        current = load_design(design_id, base_dir)
        if not current:
            raise ValueError(f"Design '{design_id}' not found")

        changes = dict(changes)
        if "referenced_knowledge" in changes:
            changes["referenced_knowledge"] = _merge_referenced_knowledge(
                dict(current.get("referenced_knowledge", {})),
                changes["referenced_knowledge"],
            )

        merged = {**current, **changes, "updated_at": now_jst().isoformat()}

        model = validate_schema(merged)  # raises ValidationError if invalid
        on_disk = _parsed_or_none(current)
        if on_disk is None and model.status.value != current.get("status"):
            # Without a readable design there is no form to check the move against.
            raise ValueError(
                f"Design '{design_id}' on disk is invalid: repair it without "
                "changing its status, then transition"
            )
        # A design broken on disk is checked as a new one, so an update may repair
        # it, but it keeps what a started analysis holds.
        if on_disk is None:
            errors = validate_creation(model) + validate_repair(model, current)
        else:
            model = with_analysis_mark(model, on_disk)
            errors = validate_update(model, on_disk)
        if errors:
            raise ValueError("; ".join(errors))
        data = model.model_dump(mode="json")
        atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml", data)
        return data


def _parsed_or_none(data: dict) -> AnalysisDesign | None:
    try:
        return validate_schema(data)
    except ValidationError:
        return None


def transition_status(
    design_id: str, target: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Transition a design's status, under the checks an update meets."""
    with write_lock(base_dir):
        current = load_design(design_id, base_dir)
        if not current:
            raise ValueError(f"Design '{design_id}' not found")
        data = _moved(current, validate_schema(current), target)
        atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml", data)
        return data


def _moved(current: dict, on_disk: AnalysisDesign, target: str) -> dict:
    """*current*, read as *on_disk*, moved to *target* and ready to write.

    Raises ValueError if refused.
    """
    validate_transition(on_disk.status, DesignStatus(target), on_disk.form())
    merged = {**current, "status": target, "updated_at": now_jst().isoformat()}
    model = with_analysis_mark(validate_schema(merged), on_disk)
    errors = validate_update(model, on_disk)
    if errors:
        raise ValueError("; ".join(errors))
    return model.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Journal (skill-managed, no schema validation)
# ---------------------------------------------------------------------------


def load_journal(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """The journal of *design_id*; {} if it does not exist or is empty.

    A journal that is not a mapping raises ValueError: read as empty, its events
    would look missing instead of unreadable.
    """
    _validate_id(design_id)
    return _read_journal(_designs_dir(base_dir) / f"{design_id}_journal.yaml")


def journal_events(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> list[dict]:
    """The events of the journal of *design_id*; [] without a journal.

    A hand-edited journal may hold anything under ``events``: only mappings are
    events, so a reader never trips over the rest.
    """
    events = load_journal(design_id, base_dir).get("events")
    return (
        [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
    )


def write_journal(
    design_id: str, data: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> None:
    with write_lock(base_dir):
        _validate_id(design_id)
        atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_journal.yaml", data)


def append_journal_event(
    design_id: str, event_fields: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Append an event to the journal of *design_id* and return it as written.

    The id is one past the highest ``{design_id}-E{nn}`` and ``created_at`` is
    set here. A journal that does not exist yet gets the header
    ``/analysis-journal`` writes. A journal that is not a mapping with a list of
    events is refused and left untouched: reading it as empty would overwrite it.
    The marks of a confirmation, an answer and a stop are refused here, so a
    writer through this module goes through ``ask_analyst``, ``answer_analyst``
    or ``stop_analysis``. A journal written by hand is held to the same rule by
    the skills' own text (analysis-journal, ADR-0064 8).
    """
    metadata = event_fields.get("metadata")
    marked = [m for m in MARKS if m in metadata] if isinstance(metadata, dict) else []
    if marked:
        raise ValueError(
            f"metadata.{marked[0]} is written only by design_io ask-analyst, "
            "answer-analyst and stop"
        )
    return _append_event(design_id, event_fields, base_dir)


def _append_event(design_id: str, event_fields: dict, base_dir: Path) -> dict:
    with write_lock(base_dir):
        _validate_id(design_id)
        path = _designs_dir(base_dir) / f"{design_id}_journal.yaml"
        now = now_jst().isoformat()
        journal = _read_journal(path)
        if not journal:
            journal = {
                "metadata": {"design_id": design_id, "created_at": now},
                "events": [],
            }
        events = journal.get("events") or []
        if not isinstance(events, list):
            raise ValueError(f"'events' in {path.name} is not a list")
        taken = [
            int(m[1])
            for e in events
            if isinstance(e, dict)
            and (m := re.fullmatch(rf"{re.escape(design_id)}-E(\d+)", str(e.get("id"))))
        ]
        event = {
            "id": f"{design_id}-E{max(taken, default=0) + 1:02d}",
            **event_fields,
            "created_at": now,
        }
        journal["events"] = [*events, event]
        metadata = journal.get("metadata")
        if not isinstance(metadata, dict):
            metadata = journal["metadata"] = {}
        metadata["updated_at"] = now
        write_journal(design_id, journal, base_dir)
        return event


def _read_journal(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = _yaml().load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a mapping")
    return data


# ---------------------------------------------------------------------------
# Confirmations, answers and stops (ADR-0064 8): the only writers of the marks
# ---------------------------------------------------------------------------


def _required_text(text: str | None, what: str) -> str:
    """*text* itself; ValueError if it is missing or blank (a payload may omit it)."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{what} is empty")
    return text


def _stage_and_events(
    design_id: str, base_dir: Path
) -> tuple[AnalysisStage, list[dict]]:
    design = load_design(design_id, base_dir)
    if not design:
        raise ValueError(f"Design '{design_id}' not found")
    return _stage_in(design_id, design, base_dir)


def stage_in(design_id: str, design: dict, base_dir: Path) -> AnalysisStage:
    """The analysis stage of *design_id*, whose file the caller already read as *design*."""
    return _stage_in(design_id, design, base_dir)[0]


def _stage_in(
    design_id: str, design: dict, base_dir: Path
) -> tuple[AnalysisStage, list[dict]]:
    try:
        status = DesignStatus(design.get("status"))
    except ValueError:
        raise ValueError(
            f"Design '{design_id}' on disk has no valid status: repair it first"
        ) from None
    events = journal_events(design_id, base_dir)
    stage = AnalysisStage.of(status, events, design.get("analysis_started_at"))
    return stage, events


def stage_of(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> AnalysisStage:
    """The analysis stage of *design_id*, read from its design and journal.

    Raises ValueError if the design does not exist.
    """
    return _stage_and_events(design_id, base_dir)[0]


def _check_stage(
    design_id: str, allowed: frozenset[AnalysisStage], refusal: str, base_dir: Path
) -> None:
    """ValueError saying *refusal* unless the stage of *design_id* is in *allowed*."""
    stage = stage_of(design_id, base_dir)
    if stage not in allowed:
        raise ValueError(f"{design_id} is {stage.value}: {refusal}")


def ask_analyst(
    design_id: str, content: str | None, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Record that a running analysis waits for the analyst, and what it asks.

    *content* says what the analysis cannot go on without changing (ADR-0064 1).
    """
    content = _required_text(content, "the confirmation")
    with write_lock(base_dir):
        _check_stage(
            design_id, ASKS_FROM, "only a running analysis asks the analyst", base_dir
        )
        return _append_event(design_id, confirmation(content), base_dir)


def answer_analyst(
    design_id: str,
    question_id: str | None,
    content: str | None,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Record the analyst's answer to the confirmation *question_id*."""
    content = _required_text(content, "the answer")
    with write_lock(base_dir):
        stage, events = _stage_and_events(design_id, base_dir)
        # An open confirmation keeps the stage at awaiting_confirmation, so the
        # check that counts is the one below; this one names a stopped or
        # finished analysis instead of saying its confirmation was answered.
        if stage in (AnalysisStage.stopped, AnalysisStage.finished):
            raise ValueError(f"{design_id} is {stage.value}: it takes no answer")
        if not any(e.get("id") == question_id and asks_analyst(e) for e in events):
            raise ValueError(
                f"{question_id} is not a confirmation in the journal of {design_id}"
            )
        if not any(e.get("id") == question_id for e in open_confirmations(events)):
            raise ValueError(f"{question_id} is already answered")
        return _append_event(design_id, answer(str(question_id), content), base_dir)


def stop_analysis(
    design_id: str, reason: str | None, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Record why the analysis of *design_id* stops. Its status does not change.

    A stopped analysis is not resumed: to try again, derive another design
    (ADR-0064 7).
    """
    reason = _required_text(reason, "the reason")
    with write_lock(base_dir):
        _check_stage(design_id, STOPS_FROM, "it cannot be stopped", base_dir)
        return _append_event(design_id, stop(reason), base_dir)


# ---------------------------------------------------------------------------
# Review batches
# ---------------------------------------------------------------------------


def append_review_batch(
    design_id: str,
    status_after: str,
    comments: list[dict],
    reviewer: str = "analyst",
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Append a review batch to ``{id}_reviews.yaml`` and transition the design.

    Mirrors ReviewService.save_review_batch: validates status is a post-review
    target, the design is reviewable, comments are non-empty with allowed
    target_section, then writes the batch and transitions status.
    """
    target = DesignStatus(status_after)
    if target not in VALID_TRANSITIONS[DesignStatus.in_review]:
        valid = ", ".join(
            sorted(s.value for s in VALID_TRANSITIONS[DesignStatus.in_review])
        )
        raise ValueError(f"Invalid post-review status '{status_after}'. Valid: {valid}")

    if not comments:
        raise ValueError("comments must not be empty")
    for c in comments:
        section = c.get("target_section")
        if section is not None and section not in ALLOWED_TARGET_SECTIONS:
            raise ValueError(
                f"Invalid target_section '{section}'. "
                f"Allowed: {sorted(ALLOWED_TARGET_SECTIONS)}"
            )

    with write_lock(base_dir):
        current = load_design(design_id, base_dir)
        if not current:
            raise ValueError(f"Design '{design_id}' not found")
        if DesignStatus(current["status"]) not in _REVIEWABLE:
            raise ValueError(
                f"Design must be reviewable to save a review batch, "
                f"current status: '{current['status']}'"
            )
        on_disk = validate_schema(current)
        # Moved before the batch is written: a move the design cannot make must
        # not leave a batch behind with the status unchanged.
        moved = _moved(current, on_disk, status_after)

        batch = ReviewBatch(
            id=f"RB-{uuid.uuid4().hex[:8]}",
            design_id=design_id,
            status_after=target,
            reviewer=reviewer,
            comments=[BatchComment(**c) for c in comments],
            # Read before the move: the approval that first enters analyzing
            # writes the mark, yet its review came before the analysis.
            after_analysis_started=analysis_started(on_disk),
        )
        designs = _designs_dir(base_dir)
        reviews_path = designs / f"{design_id}_reviews.yaml"
        existing = read_yaml(reviews_path)
        batches = [*existing.get("batches", []), batch.model_dump(mode="json")]
        atomic_write_yaml(reviews_path, {**existing, "batches": batches})
        atomic_write_yaml(designs / f"{design_id}_hypothesis.yaml", moved)
        return batch.model_dump(mode="json")


def list_review_batches(
    design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> list[dict]:
    """List review batches (newest first) from ``{id}_reviews.yaml``."""
    _validate_id(design_id)
    existing = read_yaml(_designs_dir(base_dir) / f"{design_id}_reviews.yaml")
    batches = existing.get("batches", [])
    return sorted(batches, key=lambda b: b.get("created_at", ""), reverse=True)


# ---------------------------------------------------------------------------
# CLI — thin entry point for skills (JSON in/out via stdin/stdout)
# ---------------------------------------------------------------------------


def _review_batch(args: argparse.Namespace, base: Path, payload: dict) -> Any:
    status_after = args.status or payload.get("status_after")
    if not status_after:
        raise ValueError("review-batch requires --status or payload.status_after")
    return append_review_batch(
        args.id,
        status_after=status_after,
        comments=payload.get("comments", []),
        reviewer=payload.get("reviewer", "analyst"),
        base_dir=base,
    )


_Handler = Callable[[argparse.Namespace, Path, dict], Any]

# name -> (handler, whether the command reads a JSON payload from stdin)
_COMMANDS: dict[str, tuple[_Handler, bool]] = {
    "create": (lambda a, base, p: create_design(base_dir=base, **p), True),
    "update": (lambda a, base, p: update_design(a.id, p, base_dir=base), True),
    "transition": (
        lambda a, base, p: transition_status(a.id, a.target, base_dir=base),
        False,
    ),
    "get": (lambda a, base, p: load_design(a.id, base_dir=base), False),
    "list": (lambda a, base, p: list_designs(base_dir=base, status=a.status), False),
    "review-batch": (_review_batch, True),
    "ask-analyst": (
        lambda a, base, p: ask_analyst(a.id, p.get("content"), base_dir=base),
        True,
    ),
    "answer-analyst": (
        lambda a, base, p: answer_analyst(
            a.id, p.get("answers"), p.get("content"), base_dir=base
        ),
        True,
    ),
    "stop": (
        lambda a, base, p: stop_analysis(a.id, p.get("content"), base_dir=base),
        True,
    ),
    "list-reviews": (
        lambda a, base, p: list_review_batches(a.id, base_dir=base),
        False,
    ),
}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="design_io")
    parser.add_argument("command", choices=list(_COMMANDS))
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--id", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args(argv)
    base = resolve_base_dir(Path(args.base_dir))
    handler, takes_payload = _COMMANDS[args.command]

    payload = read_payload() if takes_payload else {}
    result = handler(args, base, payload)

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
