"""Reads for the analysis note of one design, and its generated page (Epic 28, ADR-0036).

Reads ``.insight/designs/{id}_hypothesis.yaml``, its journal, the catalog,
``.insight/notebooks/{id}_verdict.json`` with the figures it lists, the notebook
``.py``, ``.insight/lineage/{id}.mmd`` and ``.insight/designs/{id}_reviews.yaml``. Nothing here
writes a canonical file: ``render_design_note`` writes only the generated page
``.insight/notes/{id}.html``, which is built by ``design_note`` and never edited.

Kept apart from ``tree_read`` so a Story that extends the note and a Story that
changes the tree page do not edit one file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from ruamel.yaml import YAMLError

from insight_blueprint.models.analysis_stage import (
    StageReading,
    answered_confirmation_ids,
)
from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    DesignStatus,
)
from insight_blueprint.models.journal import CONCLUDE, QUESTION
from skills._shared._atomic import atomic_write_text
from skills._shared.catalog_io import describe
from skills._shared.design_check import check_reading
from skills._shared.design_io import (
    DEFAULT_BASE_DIR,
    journal_events,
    load_design,
    read_yaml,
)
from skills._shared.design_note import (
    Conclusion,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    NoteVerdict,
    contradicting_evidence,
    local_file_paths,
    render_note_page,
)
from skills._shared.design_note_check import NoteCheck
from skills._shared.design_note_reviews import (
    NoteReviewBatch,
    NoteReviewComment,
)
from skills._shared.notebook_files import (
    Number,
    is_own_file,
    notebook_cells,
    notebook_path,
    notebooks_dir,
    parse_verdict,
    read_own_bytes,
    read_own_text,
    verdict_figures,
    verdict_metrics,
    verdict_path,
)
from skills._shared.tree_words import note_stage_line
from skills._shared.verdict_table import (
    CONFIDENCE,
    MetricGroup,
    MetricJudgment,
    ValueInterval,
    VerdictMetric,
)

# The next_action fields the note's recommendation takes for each terminal
# status. A dot steps into a mapping.
NEXT_ACTION_BRANCHES = {
    # An exploration holds no next_action: nothing waits on a verdict (ADR-0048).
    DesignStatus.explored: (),
    DesignStatus.supported: ("if_supported",),
    DesignStatus.rejected: ("if_rejected.reason", "if_rejected.pivot"),
    DesignStatus.inconclusive: (),
}

# A question event is open until a conclude event names it in
# metadata.resolves (analysis-journal/SKILL.md, Open Questions).
RESOLVES = "resolves"


def _text(value: object) -> str | None:
    """The text of a journal value, or None when the event has no such value."""
    return None if value is None else str(value)


def _json_text(value: object) -> str:
    if isinstance(value, Number):
        return str(value)
    if isinstance(value, dict):
        items = cast(dict[str, object], value).items()
        return (
            "{" + ", ".join(f"{_json_text(k)}: {_json_text(v)}" for k, v in items) + "}"
        )
    if isinstance(value, list):
        return "[" + ", ".join(_json_text(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def _verdict_text(value: object) -> str | None:
    """A verdict value as the notebook wrote it, or None when there is none.

    A string shows bare; an object or a list shows as its JSON text, not as a
    Python repr.
    """
    if value is None:
        return None
    return value if isinstance(value, str) else _json_text(value)


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
    return [cast(str, _verdict_text(found[key])) for key in keys]


def _effect_size(item: object) -> tuple[str, str] | None:
    kind_and_value = _all_of(item, "kind", "value")
    return (kind_and_value[0], kind_and_value[1]) if kind_and_value else None


def _interval(entry: dict) -> ValueInterval | None:
    """The interval of the value in *entry*, a metric or a group row.

    A verdict saved before ADR-0052 holds ``confidence_interval``, with no
    kind; ``interval`` wins when both can be read.
    """
    named = _all_of(entry.get("interval"), "kind", "level", "lower", "upper")
    if named:
        return ValueInterval(*named)
    saved = _all_of(entry.get("confidence_interval"), "level", "lower", "upper")
    return ValueInterval(CONFIDENCE, *saved) if saved else None


def _judgment(value: object) -> MetricJudgment | None:
    # Python 3.11 raises on ``"x" in MetricJudgment``, so the value is tried.
    try:
        return MetricJudgment(value)
    except ValueError:
        return None


def _p(entry: dict) -> str | None:
    # The contract writes "p_value"; a verdict saved before may hold "p".
    p = entry.get("p")
    return _verdict_text(entry.get("p_value") if p is None else p)


def _names(value: object, count: int | None = None) -> tuple[str, ...] | None:
    """The names in *value*, a list of *count* JSON scalars; None for anything else."""
    if not isinstance(value, list) or not value:
        return None
    if count is not None and len(value) != count:
        return None
    if any(name is None or isinstance(name, dict | list) for name in value):
        return None
    return tuple(cast(str, _verdict_text(name)) for name in value)


def _groups(entry: dict) -> tuple[tuple[str, ...], tuple[MetricGroup, ...]]:
    """The axes of *entry* and its rows, or no axes and no rows.

    One row that does not fit the axes voids them all: a table short of a row
    would read as the whole set of groups.
    """
    by = _names(entry.get("by"))
    rows = entry.get("groups")
    if by is None or not isinstance(rows, list) or not rows:
        return (), ()
    groups: list[MetricGroup] = []
    for row in rows:
        group = _names(row.get("group"), len(by)) if isinstance(row, dict) else None
        if group is None:
            return (), ()
        groups.append(
            MetricGroup(
                group=group,
                value=_verdict_text(row.get("value")),
                p=_p(row),
                effect_size=_effect_size(row.get("effect_size")),
                interval=_interval(row),
                sample_size=_verdict_text(row.get("sample_size")),
            )
        )
    return by, tuple(groups)


def _metric(name: object, entry: dict) -> VerdictMetric:
    passed = entry.get("pass")
    by, groups = _groups(entry)
    return VerdictMetric(
        name=str(name),
        value=_verdict_text(entry.get("value")),
        threshold=_verdict_text(entry.get("threshold")),
        p=_p(entry),
        passed=passed if isinstance(passed, bool) else None,
        effect_size=_effect_size(entry.get("effect_size")),
        interval=_interval(entry),
        sample_size=_verdict_text(entry.get("sample_size")),
        support_line=_verdict_text(entry.get("support_line")),
        reject_line=_verdict_text(entry.get("reject_line")),
        judgment=_judgment(entry.get("judgment")),
        by=by,
        groups=groups,
    )


def _verdict_metrics(verdict: dict) -> tuple[VerdictMetric, ...]:
    return tuple(_metric(name, entry) for name, entry in verdict_metrics(verdict))


def _verdict_figures(verdict: dict, notebooks: Path) -> tuple[NoteFigure, ...]:
    return tuple(
        NoteFigure(
            file=figure.file,
            title=str(figure.entry.get("title") or ""),
            axes=str(figure.entry.get("axes") or ""),
            how_to_read=str(figure.entry.get("how_to_read") or ""),
            png=figure.png,
        )
        for figure in verdict_figures(verdict, notebooks)
    )


def _verdict_conclusion(verdict: dict) -> str | None:
    conclusion = verdict.get("conclusion")
    return conclusion if isinstance(conclusion, str) else None


def _branch_text(next_action: object, field: str) -> str | None:
    value = next_action
    for key in field.split("."):
        if not isinstance(value, dict):
            return None
        value = cast(dict[str, object], value).get(key)
    return value if isinstance(value, str) and value else None


def _resolved_ids(events: list[dict]) -> set[str]:
    resolved: set[str] = set()
    for event in events:
        metadata = event.get("metadata")
        if event.get("type") != CONCLUDE or not isinstance(metadata, dict):
            continue
        ids = metadata.get(RESOLVES)
        if isinstance(ids, list):
            resolved |= {str(i) for i in ids}
        elif ids is not None:
            resolved.add(str(ids))
    return resolved


def _conclusion(
    design: AnalysisDesign, raw: list[dict], events: tuple[NoteEvent, ...]
) -> Conclusion | None:
    """The records of a terminal design, copied; None before it concludes."""
    if design.status not in TERMINAL_STATUSES:
        return None
    # A confirmation the analyst answered is settled by that answer, as a
    # question a conclusion resolves is (ADR-0064 9).
    settled = _resolved_ids(raw) | answered_confirmation_ids(raw)

    def of(kind: str) -> tuple[NoteEvent, ...]:
        return tuple(e for e in events if e.type == kind)

    return Conclusion(
        status=design.status,
        conclude_events=of(CONCLUDE),
        next_action=tuple(
            (field, text)
            for field in NEXT_ACTION_BRANCHES[design.status]
            if (text := _branch_text(design.next_action, field)) is not None
        ),
        contradicting_evidence=contradicting_evidence(events, design.form()),
        reflect_events=of("reflect"),
        open_questions=tuple(e for e in of(QUESTION) if e.id not in settled),
    )


def _review_text(value: object) -> str:
    # An unquoted timestamp loads as a datetime; its text keeps the ISO form.
    if isinstance(value, datetime):
        return value.isoformat()
    return "" if value is None else str(value)


def _target_content(value: object) -> str | None:
    """The target of a comment as text: a string bare, any other JSON value as JSON."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _review_comment(item: object) -> NoteReviewComment | None:
    if not isinstance(item, dict):
        return None
    entry = cast(dict[str, object], item)
    comment = entry.get("comment")
    if not isinstance(comment, str) or not comment.strip():
        return None
    section = entry.get("target_section")
    try:
        content = _target_content(entry.get("target_content"))
    except ValueError:  # json.dumps refuses a value that holds itself
        return None
    return NoteReviewComment(
        comment=comment,
        target_section=None if section is None else str(section),
        target_content=content,
    )


def _review_batch(item: object) -> NoteReviewBatch | None:
    """One batch as written; None when it holds no comment the note can read."""
    if not isinstance(item, dict):
        return None
    entry = cast(dict[str, object], item)
    listed = entry.get("comments")
    if not isinstance(listed, list):
        return None
    comments = tuple(c for c in map(_review_comment, listed) if c is not None)
    if not comments:
        return None
    after = entry.get("after_analysis_started")
    return NoteReviewBatch(
        id=_review_text(entry.get("id")),
        created_at=_review_text(entry.get("created_at")),
        # Held as written, never derived from the analysis mark (ADR-0054 4).
        after_analysis_started=after if isinstance(after, bool) else None,
        status_after=_review_text(entry.get("status_after")),
        reviewer=_review_text(entry.get("reviewer")),
        comments=comments,
    )


def _read_reviews(path: Path) -> tuple[NoteReviewBatch, ...]:
    """The batches of *path*, newest first; none when the file cannot be read.

    Reviews only add to the note, so a broken file leaves the rest of it as it
    was. Newest first means by the text of ``created_at``, a timestamp YAML read
    as a date taken as its ISO text; batches of the same time keep the file's
    order.
    """
    if not is_own_file(path):
        return ()
    try:
        entries = read_yaml(path).get("batches")
    # ValueError: a timestamp that is no date, such as 2026-02-30.
    except (YAMLError, UnicodeDecodeError, RecursionError, ValueError, OSError):
        return ()
    if not isinstance(entries, list):
        return ()
    batches = [b for b in map(_review_batch, entries) if b is not None]
    return tuple(sorted(batches, key=lambda b: b.created_at, reverse=True))


def load_design_note(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> DesignNote:
    """The note of *design_id*, read from the files of the design.

    Raises ValueError for a design that does not exist or fails its schema, and
    for a verdict file that is not a JSON object. A design whose notebook has
    not run has no verdict: ``verdict`` is None then, and there are no figures.
    A design not in a terminal status has no ``conclusion``. A notebook ``.py``
    that is missing, a link, or not in the contract's shape gives ``cells`` None.
    """
    data = load_design(design_id, base_dir)
    if not data:
        raise ValueError(f"design '{design_id}' not found")
    # A copied design file still carries the id of its source, so the note
    # takes the file-name id: heading, anchor and local files name this design.
    design = AnalysisDesign.model_validate(data).model_copy(update={"id": design_id})
    # Only these three fields of a source are read: its connection stays unread.
    sources = tuple(
        NoteSource(
            name=str(s["name"]), type=str(s["type"]), description=str(s["description"])
        )
        for s in describe(design.source_ids, base_dir)["sources"]
    )
    raw = journal_events(design_id, base_dir)
    reading = StageReading.of(design.status, raw, design.analysis_started_at)
    events = tuple(_note_event(e) for e in raw)
    base = Path(base_dir)
    notebook = read_own_text(notebook_path(design_id, base))
    cells = None if notebook is None else notebook_cells(notebook)
    lineage = read_own_text(base / "lineage" / f"{design_id}.mmd")
    local_files = tuple(
        path for path in local_file_paths(design_id) if is_own_file(base / path)
    )
    where = verdict_path(design_id, base)
    saved = read_own_bytes(where)
    verdict = None if saved is None else parse_verdict(saved, where.name)
    return DesignNote(
        design,
        sources,
        events,
        verdict=None
        if verdict is None
        else NoteVerdict(
            metrics=_verdict_metrics(verdict),
            conclusion=_verdict_conclusion(verdict),
        ),
        figures=()
        if verdict is None
        else _verdict_figures(verdict, notebooks_dir(base)),
        cells=cells,
        lineage=lineage,
        local_files=local_files,
        conclusion=_conclusion(design, raw, events),
        stage=reading.stage,
        reviews=_read_reviews(base / "designs" / f"{design_id}_reviews.yaml"),
        stop_reason=reading.stop_reason,
        stage_line=note_stage_line(reading.stage, reading.stop_reason),
        asks=tuple(ask.content for ask in reading.asks),
        check=NoteCheck.of(check_reading(design_id, base_dir)),
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
