"""Reads for the analysis note of one design, and its generated page (Epic 28, ADR-0036).

Reads ``.insight/designs/{id}_hypothesis.yaml``, its journal, the catalog,
``.insight/notebooks/{id}_verdict.json`` with the figures it lists, the notebook
``.py`` and ``.insight/lineage/{id}.mmd``. Nothing here
writes a canonical file: ``render_design_note`` writes only the generated page
``.insight/notes/{id}.html``, which is built by ``design_note`` and never edited.

Kept apart from ``tree_read`` so a Story that extends the note and a Story that
changes the tree page do not edit one file.
"""

from __future__ import annotations

import ast
import codecs
import io
import json
import re
import tokenize
from itertools import pairwise
from pathlib import Path
from typing import cast

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    DesignStatus,
)
from skills._shared._atomic import atomic_write_text
from skills._shared.catalog_io import describe
from skills._shared.design_io import DEFAULT_BASE_DIR, journal_events, load_design
from skills._shared.design_note import (
    CodeCell,
    Conclusion,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    NoteVerdict,
    VerdictMetric,
    contradicting_evidence,
    local_file_paths,
    render_note_page,
)

# A figure is a bare file name: it becomes a path under notebooks/.
_FIGURE_FILE = re.compile(r"[A-Za-z0-9_.-]+")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The line ends of the tokenizer, which ast line numbers count.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
# A comment at column 0 that starts with this opens a cell; the rest is its name.
_SEPARATOR = "# %%"
# The encoding declaration of PEP 263, read on the first two lines.
_CODING = re.compile(r"[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")
DATA_LOAD_CELL = "data_load"
# The cells of the notebook contract, in order (notebook-contract.md, ADR-0045).
CONTRACT_CELLS = (
    "imports",
    DATA_LOAD_CELL,
    "data_prep",
    "analysis",
    "viz",
    "verdict",
    "lineage",
)

# The next_action fields the note's recommendation takes for each terminal
# status. A dot steps into a mapping.
NEXT_ACTION_BRANCHES = {
    DesignStatus.supported: ("if_supported",),
    DesignStatus.rejected: ("if_rejected.reason", "if_rejected.pivot"),
    DesignStatus.inconclusive: (),
}

# A question event is open until a conclude event names it in
# metadata.resolves (analysis-journal/SKILL.md, Open Questions).
QUESTION = "question"
CONCLUDE = "conclude"
RESOLVES = "resolves"


def _text(value: object) -> str | None:
    """The text of a journal value, or None when the event has no such value."""
    return None if value is None else str(value)


class _Number(str):
    """A JSON number or constant of the verdict, kept as the text the notebook wrote."""


def _json_text(value: object) -> str:
    if isinstance(value, _Number):
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


def _interval(item: object) -> tuple[str, str, str] | None:
    parts = _all_of(item, "level", "lower", "upper")
    return (parts[0], parts[1], parts[2]) if parts else None


def _metric(name: object, entry: dict) -> VerdictMetric:
    passed = entry.get("pass")
    return VerdictMetric(
        name=str(name),
        value=_verdict_text(entry.get("value")),
        threshold=_verdict_text(entry.get("threshold")),
        p=_verdict_text(entry.get("p")),
        passed=passed if isinstance(passed, bool) else None,
        effect_size=_effect_size(entry.get("effect_size")),
        confidence_interval=_interval(entry.get("confidence_interval")),
        sample_size=_verdict_text(entry.get("sample_size")),
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
        # Only an image goes in: a manifest that names the notebook embeds nothing.
        if not _is_own_file(path):
            continue
        png = path.read_bytes()
        if not png.startswith(_PNG_SIGNATURE):
            continue
        figures.append(
            NoteFigure(
                file=file,
                title=str(entry.get("title") or ""),
                axes=str(entry.get("axes") or ""),
                how_to_read=str(entry.get("how_to_read") or ""),
                png=png,
            )
        )
    return tuple(figures)


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
    resolved = _resolved_ids(raw)

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
        contradicting_evidence=contradicting_evidence(events),
        reflect_events=of("reflect"),
        open_questions=tuple(e for e in of(QUESTION) if e.id not in resolved),
    )


def _separators(source: str) -> dict[int, str]:
    """The cell name of each separator line, by its 1-based line number.

    A separator is a comment that starts at column 0 with ``# %%``. The
    tokenizer tells a comment from the same characters in a string.
    """
    return {
        token.start[0]: token.string.removeprefix(_SEPARATOR).strip()
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
        and token.start[1] == 0
        and token.string.startswith(_SEPARATOR)
    }


def _declares_another_encoding(lines: list[str]) -> bool:
    """Whether the file declares an encoding that is not UTF-8 (PEP 263).

    Python decodes the file by the declaration and the note reads it as
    UTF-8, so the two could see different separator lines.
    """
    for line in lines[:2]:
        declared = _CODING.match(line)
        if declared:
            try:
                return codecs.lookup(declared[1]).name != "utf-8"
            except LookupError:
                return True
    return False


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _binds_raw_df(statement: ast.stmt) -> bool:
    return any(
        isinstance(node, ast.Name)
        and node.id == "raw_df"
        and isinstance(node.ctx, ast.Store)
        for node in ast.walk(statement)
    )


def _cell_source(lines: list[str]) -> str:
    """The lines of a cell as written, without the blank lines after them."""
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return "\n".join(lines)


def _body(lines: list[str]) -> list[ast.stmt]:
    return ast.parse("\n".join(lines)).body


def _dumps(statements: list[ast.stmt]) -> list[str]:
    return [ast.dump(statement) for statement in statements]


def notebook_cells(text: str) -> tuple[CodeCell, ...] | None:
    """The cells of a notebook, without its data-load cell (ADR-0045).

    A cell runs from a ``# %% <name>`` line to the line before the next one.
    The cells must be the contract's seven, in order; the data-load cell is the
    one named ``data_load``. It holds the connection values (ADR-0022), so a
    notebook where it cannot be told apart gives no code at all: any cell could
    hold them.
    """
    # ast, the tokenizer and the slices all read these lines, so a line number
    # means the same line in each. str.splitlines() also breaks on \x0c, \x85,
    # U+2028 and others, which would shift a slice onto the data-load cell.
    lines = _LINE_BREAK.split(text)
    if _declares_another_encoding(lines):
        return None
    try:
        names = _separators("\n".join(lines))
        starts = sorted(names)
        # Any other cell could be a piece of data_load cut off by a stray # %% line.
        if tuple(names[start] for start in starts) != CONTRACT_CELLS:
            return None
        slices = [
            lines[a - 1 : b - 1] for a, b in pairwise([1, *starts, len(lines) + 1])
        ]
        head, *cells = map(_body, slices)
        # A separator inside a statement leaves a slice that does not parse, or
        # one that parses to other statements than the file's.
        if _dumps(_body(lines)) != _dumps([s for body in [head, *cells] for s in body]):
            return None
    # A deeply nested expression ends the parse with RecursionError, or with
    # MemoryError ("Parser stack overflowed", CPython 3.14).
    except (SyntaxError, ValueError, tokenize.TokenError, RecursionError, MemoryError):
        return None
    if head and (len(head) > 1 or not _is_docstring(head[0])):
        return None
    binders = {i for i, body in enumerate(cells) if any(map(_binds_raw_df, body))}
    if binders != {CONTRACT_CELLS.index(DATA_LOAD_CELL)}:
        return None
    return tuple(
        CodeCell(position=index + 1, name=name, source=_cell_source(cell))
        for index, (name, cell) in enumerate(
            zip(CONTRACT_CELLS, slices[1:], strict=True)
        )
        if name != DATA_LOAD_CELL
    )


def _is_own_file(path: Path) -> bool:
    """Whether *path* is a regular file and not a link.

    The note may leave the machine, so a link out of .insight/ is never read,
    embedded or listed.
    """
    return not path.is_symlink() and path.is_file()


def _read_own_text(path: Path) -> str | None:
    """The text of *path*; None when it is not an own file or not UTF-8."""
    if not _is_own_file(path):
        return None
    try:
        return path.read_text("utf-8")
    except UnicodeDecodeError:
        return None


def _read_verdict(path: Path) -> dict:
    # Each number, NaN and Infinity included, keeps the text the notebook wrote.
    try:
        verdict = json.loads(
            path.read_text("utf-8"),
            parse_float=_Number,
            parse_int=_Number,
            parse_constant=_Number,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc}") from None
    if not isinstance(verdict, dict):
        raise ValueError(f"{path.name} must hold a JSON object")
    return verdict


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
    events = tuple(_note_event(e) for e in raw)
    base = Path(base_dir)
    notebooks = base / "notebooks"
    notebook = _read_own_text(notebooks / f"{design_id}.py")
    cells = None if notebook is None else notebook_cells(notebook)
    lineage = _read_own_text(base / "lineage" / f"{design_id}.mmd")
    local_files = tuple(
        path for path in local_file_paths(design_id) if _is_own_file(base / path)
    )
    verdict_path = notebooks / f"{design_id}_verdict.json"
    verdict = _read_verdict(verdict_path) if _is_own_file(verdict_path) else None
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
        figures=() if verdict is None else _verdict_figures(verdict, notebooks),
        cells=cells,
        lineage=lineage,
        local_files=local_files,
        conclusion=_conclusion(design, raw, events),
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
