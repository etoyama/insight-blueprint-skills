"""The one reader of the files a notebook leaves under ``.insight/notebooks/``.

The analysis note shows the notebook ``.py``, its verdict and the figures the
verdict lists; the check of the computation (ADR-0070) compares the same ones
against the design. Both read them here, so the check cannot count a figure or
a metric the note does not show, nor cut the cells another way.

A leaf: it imports no other module of ``skills._shared``.
"""

from __future__ import annotations

import ast
import codecs
import io
import json
import re
import tokenize
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import cast

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


def notebooks_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "notebooks"


def notebook_path(design_id: str, base_dir: Path) -> Path:
    return notebooks_dir(base_dir) / f"{design_id}.py"


def verdict_path(design_id: str, base_dir: Path) -> Path:
    return notebooks_dir(base_dir) / f"{design_id}_verdict.json"


def is_own_file(path: Path) -> bool:
    """Whether *path* is a regular file and not a link.

    The note may leave the machine, so a link out of .insight/ is never read,
    embedded or listed.
    """
    return not path.is_symlink() and path.is_file()


def read_own_bytes(path: Path) -> bytes | None:
    """The bytes of *path*; None when it is not an own file."""
    return path.read_bytes() if is_own_file(path) else None


def read_own_text(path: Path) -> str | None:
    """The text of *path*; None when it is not an own file or not UTF-8."""
    if not is_own_file(path):
        return None
    try:
        # Python runs a .py that opens with a byte order mark; so does the note.
        return path.read_text("utf-8-sig")
    except UnicodeDecodeError:
        return None


def text_of(raw: bytes) -> str | None:
    """The text of the bytes of an own file; None when they are not UTF-8."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


class Number(str):
    """A JSON number or constant of the verdict, kept as the text the notebook wrote."""


def parse_verdict(raw: bytes, name: str) -> dict:
    """The verdict in *raw*, the bytes of the file *name*.

    Each number, NaN and Infinity included, keeps the text the notebook wrote.
    Raises ValueError for bytes that are not a JSON object in UTF-8.
    """
    try:
        verdict = json.loads(
            raw.decode("utf-8"),
            parse_float=Number,
            parse_int=Number,
            parse_constant=Number,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"{name} is not valid JSON: {exc}") from None
    if not isinstance(verdict, dict):
        raise ValueError(f"{name} must hold a JSON object")
    return verdict


def verdict_metrics(verdict: dict) -> tuple[tuple[str, dict], ...]:
    """The metrics of *verdict* by name; an entry that is no object is not one."""
    metrics = verdict.get("metrics")
    if not isinstance(metrics, dict):
        return ()
    return tuple(
        (str(name), cast(dict, entry))
        for name, entry in metrics.items()
        if isinstance(entry, dict)
    )


@dataclass(frozen=True)
class VerdictFigure:
    """A figure the verdict lists whose file is an own PNG under notebooks/."""

    file: str
    entry: dict  # the entry of the verdict as written
    png: bytes


def verdict_figures(verdict: dict, notebooks: Path) -> tuple[VerdictFigure, ...]:
    entries = verdict.get("figures")
    if not isinstance(entries, list):
        return ()
    figures: list[VerdictFigure] = []
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
        # Only an image goes in: a manifest that names the notebook embeds nothing.
        png = read_own_bytes(notebooks / file)
        if png is None or not png.startswith(_PNG_SIGNATURE):
            continue
        figures.append(VerdictFigure(file=file, entry=entry, png=png))
    return tuple(figures)


@dataclass(frozen=True)
class CodeCell:
    """One cell of the notebook ``.py``; never the data-load cell."""

    position: int  # 1-based place among the cells of the file
    name: str  # the text after "# %%" on the cell's first line; may be empty
    source: str  # as written, from the "# %%" line on


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
