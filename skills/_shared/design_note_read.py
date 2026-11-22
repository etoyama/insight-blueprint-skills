"""Reads for the analysis note of one design, and its generated page (Epic 28, ADR-0036).

Reads ``.insight/designs/{id}_hypothesis.yaml``, its journal, the catalog and
``.insight/notebooks/{id}_verdict.json`` with the figures it lists. Nothing here
writes a canonical file: ``render_design_note`` writes only the generated page
``.insight/notes/{id}.html``, which is built by ``design_note`` and never edited.

Kept apart from ``tree_read`` so a Story that extends the note and a Story that
changes the tree page do not edit one file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

from insight_blueprint.models.design import AnalysisDesign
from skills._shared._atomic import atomic_write_text
from skills._shared.catalog_io import describe
from skills._shared.design_io import DEFAULT_BASE_DIR, journal_events, load_design
from skills._shared.design_note import (
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    VerdictMetric,
    render_note_page,
)

# A figure is a bare file name: it becomes a path under notebooks/.
_FIGURE_FILE = re.compile(r"[A-Za-z0-9_.-]+")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _text(value: object) -> str | None:
    """The text of a JSON scalar, or None when the verdict has no such value."""
    return None if value is None else str(value)


def _note_event(event: dict) -> NoteEvent:
    metadata = event.get("metadata")
    direction = metadata.get("direction") if isinstance(metadata, dict) else None
    content = event.get("content")
    created_at = event.get("created_at")
    return NoteEvent(
        id=str(event.get("id") or ""),
        type=str(event.get("type") or ""),
        direction=_text(direction),
        # A hand-written "content: 34.6" loads as a float, not as text.
        content="" if content is None else str(content),
        created_at="" if created_at is None else str(created_at),
    )


def _all_of(item: object, *keys: str) -> list[str] | None:
    """The text of each of *keys* in *item*, or None when one is missing.

    ``effect_size`` and ``confidence_interval`` are all-or-nothing: a partial
    item cannot be read correctly, so it counts as absent (ADR-0013).
    """
    if not isinstance(item, dict):
        return None
    found = cast(dict[str, object], item)
    if any(found.get(key) is None for key in keys):
        return None
    return [str(found[key]) for key in keys]


def _effect_size(item: object) -> tuple[str, str] | None:
    kind_and_value = _all_of(item, "kind", "value")
    return (kind_and_value[0], kind_and_value[1]) if kind_and_value else None


def _interval(item: object) -> tuple[str, str, str] | None:
    parts = _all_of(item, "level", "lower", "upper")
    return (parts[0], parts[1], parts[2]) if parts else None


def _metric(name: object, entry: dict) -> VerdictMetric:
    passed = entry.get("pass")
    return VerdictMetric(
        name=str(name),
        value=_text(entry.get("value")),
        threshold=_text(entry.get("threshold")),
        p=_text(entry.get("p")),
        passed=passed if isinstance(passed, bool) else None,
        effect_size=_effect_size(entry.get("effect_size")),
        confidence_interval=_interval(entry.get("confidence_interval")),
        sample_size=_text(entry.get("sample_size")),
    )


def _verdict_metrics(verdict: dict) -> tuple[VerdictMetric, ...]:
    metrics = verdict.get("metrics")
    if not isinstance(metrics, dict):
        return ()
    return tuple(
        _metric(name, entry)
        for name, entry in metrics.items()
        if isinstance(entry, dict)
    )


def _verdict_figures(verdict: dict, notebooks: Path) -> tuple[NoteFigure, ...]:
    entries = verdict.get("figures")
    if not isinstance(entries, list):
        return ()
    figures: list[NoteFigure] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        file = entry.get("file")
        # The name is checked before it touches a path: a manifest is data from
        # a notebook, and a traversal value would read a file outside notebooks/.
        if (
            not isinstance(file, str)
            or not _FIGURE_FILE.fullmatch(file)
            or ".." in file
        ):
            continue
        path = notebooks / file
        # The note may leave the machine, so only an image goes in: a manifest
        # that names the notebook, or a link out of notebooks/, embeds nothing.
        if path.is_symlink() or not path.is_file():
            continue
        png = path.read_bytes()
        if not png.startswith(_PNG_SIGNATURE):
            continue
        figures.append(
            NoteFigure(
                title=str(entry.get("title") or ""),
                axes=str(entry.get("axes") or ""),
                how_to_read=str(entry.get("how_to_read") or ""),
                png=png,
            )
        )
    return tuple(figures)


def _read_verdict(path: Path) -> dict:
    # parse_float / parse_int keep each number as the text the notebook wrote.
    try:
        verdict = json.loads(path.read_text("utf-8"), parse_float=str, parse_int=str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc}") from None
    if not isinstance(verdict, dict):
        raise ValueError(f"{path.name} must hold a JSON object")
    return verdict


def load_design_note(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> DesignNote:
    """The note of *design_id*, read from the files of the design.

    Raises ValueError for a design that does not exist or fails its schema, and
    for a verdict file that is not a JSON object. A design whose notebook has
    not run has no verdict: ``metrics`` is None then, and there are no figures.
    """
    data = load_design(design_id, base_dir)
    if not data:
        raise ValueError(f"design '{design_id}' not found")
    design = AnalysisDesign.model_validate(data)
    # Only these three fields of a source are read: its connection stays unread.
    sources = tuple(
        NoteSource(
            name=str(s["name"]), type=str(s["type"]), description=str(s["description"])
        )
        for s in describe(design.source_ids, base_dir)["sources"]
    )
    events = tuple(_note_event(e) for e in journal_events(design_id, base_dir))
    notebooks = Path(base_dir) / "notebooks"
    verdict_path = notebooks / f"{design_id}_verdict.json"
    if not verdict_path.is_file():
        return DesignNote(design, sources, events, metrics=None, figures=())
    verdict = _read_verdict(verdict_path)
    return DesignNote(
        design,
        sources,
        events,
        metrics=_verdict_metrics(verdict),
        figures=_verdict_figures(verdict, notebooks),
    )


def render_design_note(
    design_id: str, base_dir: Path = DEFAULT_BASE_DIR
) -> dict[str, str]:
    """Write ``.insight/notes/{design_id}.html`` and return its path.

    The page is generated, never edited: the same design, journal and notebook
    output give the same bytes. When loading fails, nothing is written.
    """
    html = render_note_page(load_design_note(design_id, base_dir))
    path = Path(base_dir) / "notes" / f"{design_id}.html"
    atomic_write_text(path, html)
    return {"path": str(path)}
