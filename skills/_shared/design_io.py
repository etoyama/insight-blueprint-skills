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
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from insight_blueprint.models.common import now_jst
from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.review import BatchComment, ReviewBatch
from insight_blueprint.validate import (
    VALID_TRANSITIONS,
    validate_schema,
    validate_transition,
)
from skills._shared._atomic import atomic_write_yaml

DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))

THEME_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")

# Server-independent id check (mirrors catalog_io.SAFE_ID_PATTERN). A design_id is
# interpolated into `{id}_*.yaml` paths, so reject anything that could escape the
# designs directory (path separators, `..`, etc.).
SAFE_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")


def _validate_id(design_id: str) -> None:
    if not SAFE_ID_PATTERN.fullmatch(design_id):
        raise ValueError(f"Invalid design_id '{design_id}': must match [a-zA-Z0-9_-]+")


# Sections a review comment may target. Kept here (not imported from the
# to-be-removed core/reviews.py) so design_io is server-independent.
ALLOWED_TARGET_SECTIONS: set[str] = {
    "hypothesis_statement",
    "hypothesis_background",
    "metrics",
    "explanatory",
    "chart",
    "next_action",
    "referenced_knowledge",
    "methodology",
    "analysis_intent",
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


def next_design_id(theme_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> str:
    """Return the next id ``{theme_id}-H{nn}`` using a max-N+1 strategy."""
    if not THEME_ID_PATTERN.match(theme_id):
        raise ValueError(f"Invalid theme_id '{theme_id}': must match [A-Z][A-Z0-9]*")
    designs_dir = _designs_dir(base_dir)
    prefix = f"{theme_id}-H"
    max_n = 0
    if designs_dir.exists():
        for path in designs_dir.glob(f"{prefix}*_hypothesis.yaml"):
            id_part = path.stem.replace("_hypothesis", "")
            try:
                max_n = max(max_n, int(id_part[len(prefix) :]))
            except (ValueError, IndexError):
                continue
    return f"{theme_id}-H{max_n + 1:02d}"


def create_design(
    *,
    title: str,
    hypothesis_statement: str,
    hypothesis_background: str,
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
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Create a design document. Validates via validate.py before writing.

    Returns the written dict. Raises ValueError (bad theme_id) or pydantic
    ValidationError (schema) without writing on failure.
    """
    design_id = next_design_id(theme_id, base_dir)
    candidate: dict[str, Any] = {
        "id": design_id,
        "theme_id": theme_id,
        "title": title,
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
    }
    if methodology is not None:
        candidate["methodology"] = methodology

    model = validate_schema(candidate)  # raises ValidationError if invalid
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

    Validates schema + transition via validate.py. Raises ValueError if the
    design is absent or the change is invalid; nothing is written on failure.
    """
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

    errors = _validation_errors(merged, current)
    if errors:
        raise ValueError("; ".join(errors))
    model = validate_schema(merged)
    data = model.model_dump(mode="json")
    atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml", data)
    return data


def _validation_errors(new_data: dict, current_data: dict | None) -> list[str]:
    """Run validate.py and return non-ValidationError messages (transition).

    Schema errors are surfaced by re-raising via validate_schema in the caller,
    so here we only collect the transition message. Kept thin: delegates to the
    same VALID_TRANSITIONS source.
    """
    errors: list[str] = []
    if current_data and new_data.get("status") != current_data.get("status"):
        try:
            validate_transition(
                DesignStatus(current_data["status"]),
                DesignStatus(new_data["status"]),
            )
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def transition_status(
    design_id: str, target: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Transition a design's status, guarded by validate_transition."""
    current = load_design(design_id, base_dir)
    if not current:
        raise ValueError(f"Design '{design_id}' not found")
    validate_transition(DesignStatus(current["status"]), DesignStatus(target))
    merged = {**current, "status": target, "updated_at": now_jst().isoformat()}
    model = validate_schema(merged)
    data = model.model_dump(mode="json")
    atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_hypothesis.yaml", data)
    return data


# ---------------------------------------------------------------------------
# Journal (skill-managed, no schema validation)
# ---------------------------------------------------------------------------


def load_journal(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    _validate_id(design_id)
    return read_yaml(_designs_dir(base_dir) / f"{design_id}_journal.yaml")


def write_journal(
    design_id: str, data: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> None:
    _validate_id(design_id)
    atomic_write_yaml(_designs_dir(base_dir) / f"{design_id}_journal.yaml", data)


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

    current = load_design(design_id, base_dir)
    if not current:
        raise ValueError(f"Design '{design_id}' not found")
    if DesignStatus(current["status"]) not in _REVIEWABLE:
        raise ValueError(
            f"Design must be reviewable to save a review batch, "
            f"current status: '{current['status']}'"
        )

    batch = ReviewBatch(
        id=f"RB-{uuid.uuid4().hex[:8]}",
        design_id=design_id,
        status_after=target,
        reviewer=reviewer,
        comments=[BatchComment(**c) for c in comments],
    )
    reviews_path = _designs_dir(base_dir) / f"{design_id}_reviews.yaml"
    existing = read_yaml(reviews_path)
    batches = [*existing.get("batches", []), batch.model_dump(mode="json")]
    atomic_write_yaml(reviews_path, {**existing, "batches": batches})

    transition_status(design_id, status_after, base_dir)
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


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="design_io")
    parser.add_argument(
        "command",
        choices=[
            "create",
            "update",
            "transition",
            "get",
            "list",
            "review-batch",
            "list-reviews",
        ],
    )
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--id", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args(argv)
    base = Path(args.base_dir)

    payload: dict = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    if args.command == "create":
        result: Any = create_design(base_dir=base, **payload)
    elif args.command == "update":
        result = update_design(args.id, payload, base_dir=base)
    elif args.command == "transition":
        result = transition_status(args.id, args.target, base_dir=base)
    elif args.command == "get":
        result = load_design(args.id, base_dir=base)
    elif args.command == "list":
        result = list_designs(base_dir=base, status=args.status)
    elif args.command == "review-batch":
        status_after = args.status or payload.get("status_after")
        if not status_after:
            raise ValueError("review-batch requires --status or payload.status_after")
        result = append_review_batch(
            args.id,
            status_after=status_after,
            comments=payload.get("comments", []),
            reviewer=payload.get("reviewer", "analyst"),
            base_dir=base,
        )
    elif args.command == "list-reviews":
        result = list_review_batches(args.id, base_dir=base)
    else:  # pragma: no cover - argparse restricts choices
        raise SystemExit(2)

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
