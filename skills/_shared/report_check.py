"""Check a finished report for source text that would be active markup (Epic 13).

``/analysis-report`` tells the model to backslash-escape text that came from source
data. This module checks the result in code, so a rule the model skipped is caught
whichever model wrote the report. It only reads: it never rewrites the report.

Everything is judged on the raw Markdown with an approximation of CommonMark, not a
parser, so no dependency is added. Links and bare URLs are out of scope on purpose
(docs/design/epic-13-report-source-text.md, Decision ``checker-ignores-links``).

Usage from a skill (CLI):
    report_check --id FP-H01 [--base-dir .insight]
"""

from __future__ import annotations

import argparse
import enum
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))

# Same pattern as design_io / catalog_io. Copied (third copy) because importing
# design_io would pull in the pydantic models for a read-only check.
SAFE_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")

MAX_TEXT_LENGTH = 120

_FENCE_OPEN = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
_FENCE_CLOSE = re.compile(r" {0,3}(`{3,}|~{3,})[ \t]*")

# Where a tag, comment, declaration, or autolink can start. The check fails closed:
# it does not parse the rest of the tag, because a grammar that misses one shape
# (a ">" inside an attribute value, a tag that continues on the next line) lets
# that shape through.
_TAG_START = re.compile(r"<(?:/?[A-Za-z]|[!?])")
_MERMAID_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)

# The only statements the lineage export writes (insight_blueprint.lineage.exporter).
# Anything else in a mermaid fence — click, a directive, a subgraph — is not ours.
_MERMAID_STATEMENT = re.compile(
    r"""\s*(?:graph\ LR
        | Step\d+\["[^"]*"\]
        | Step\d+\ -->\|"[^"]*"\|\ Step\d+
        )?\s*""",
    re.VERBOSE,
)

# An image is allowed only as a figure: a notebook output beside the report.
_FIGURE = re.compile(
    r"!\[(?:[^\[\]\\]|\\.)*\]\(\.\./notebooks/(?P<file>[A-Za-z0-9_.-]+)\.png\)"
)


@dataclass(frozen=True)
class Violation:
    line: int
    kind: str  # "image" | "html" | "mermaid-html" | "mermaid-statement"
    text: str


class _Fence(enum.Enum):
    OUTSIDE = enum.auto()
    MERMAID = enum.auto()
    OTHER = enum.auto()


@dataclass(frozen=True)
class _Hit:
    pos: int
    kind: str
    text: str


def find_violations(markdown: str) -> list[Violation]:
    state = _Fence.OUTSIDE
    fence_char = ""
    fence_len = 0
    violations: list[Violation] = []

    for number, raw in enumerate(markdown.split("\n"), start=1):
        line = raw.removesuffix("\r")

        if state is _Fence.OUTSIDE:
            opened = _open_fence(line)
            if opened is not None:
                fence_char, fence_len, is_mermaid = opened
                state = _Fence.MERMAID if is_mermaid else _Fence.OTHER
                continue
            hits = _scan_prose(line)
        elif _closes_fence(line, fence_char, fence_len):
            state = _Fence.OUTSIDE
            continue
        elif state is _Fence.MERMAID:
            hits = _scan_mermaid(line)
        else:
            continue

        violations.extend(
            Violation(number, h.kind, h.text[:MAX_TEXT_LENGTH]) for h in hits
        )
    return violations


def _open_fence(line: str) -> tuple[str, int, bool] | None:
    match = _FENCE_OPEN.fullmatch(line)
    if match is None:
        return None
    marker, info = match.group(1), match.group(2).strip()
    if marker[0] == "`" and "`" in info:
        return None
    words = info.split()
    return marker[0], len(marker), bool(words) and words[0].lower() == "mermaid"


def _closes_fence(line: str, fence_char: str, fence_len: int) -> bool:
    match = _FENCE_CLOSE.fullmatch(line)
    if match is None:
        return False
    marker = match.group(1)
    return marker[0] == fence_char and len(marker) >= fence_len


def _scan_mermaid(line: str) -> list[_Hit]:
    if _MERMAID_STATEMENT.fullmatch(line) is None:
        return [_Hit(0, "mermaid-statement", line.strip())]
    return [
        _Hit(m.start(), "mermaid-html", _tag_text(line, m.start()))
        for m in _TAG_START.finditer(line)
        if _MERMAID_BR.match(line, m.start()) is None
    ]


def _tag_text(line: str, start: int) -> str:
    end = line.find(">", start)
    return line[start:] if end == -1 else line[start : end + 1]


def _scan_prose(line: str) -> list[_Hit]:
    hits: list[_Hit] = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "\\":
            # Skipping the escaped character is what makes an odd run of
            # backslashes escape and an even run not.
            i += 2
        elif char == "`":
            i = _skip_code_span(line, i)
        elif line.startswith("![", i):
            i = _scan_image(line, i, hits)
        elif _TAG_START.match(line, i):
            html = _tag_text(line, i)
            hits.append(_Hit(i, "html", html))
            i += len(html)
        else:
            i += 1
    return hits


def _skip_code_span(line: str, start: int) -> int:
    length = _run_length(line, start)
    j = start + length
    while j < len(line):
        if line[j] != "`":
            j += 1
            continue
        closing = _run_length(line, j)
        if closing == length:
            return j + closing
        j += closing
    return start + length


def _run_length(line: str, start: int) -> int:
    end = start
    while end < len(line) and line[end] == line[start]:
        end += 1
    return end - start


def _scan_image(line: str, start: int, hits: list[_Hit]) -> int:
    """Record a violation for the image at ``start`` unless it is a figure.

    Returns where scanning resumes. An allowed figure resumes inside its alt text
    because the alt text is still prose that can carry a tag.
    """
    end = _inline_image_end(line, start)
    if end is None:
        hits.append(_Hit(start, "image", line[start:]))
        return start + 2
    construct = line[start:end]
    figure = _FIGURE.fullmatch(construct)
    if figure is None or ".." in figure.group("file"):
        hits.append(_Hit(start, "image", construct))
        return end
    return start + 2


def _inline_image_end(line: str, start: int) -> int | None:
    """End (exclusive) of ``![alt](dest)`` at ``start``, or None if it is not closed."""
    i = start + 2
    while i < len(line) and line[i] != "]":
        i += 2 if line[i] == "\\" else 1
    if not line.startswith("](", i):
        return None
    i += 2
    depth = 1
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == "(":
            depth += 1
        elif line[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="report_check")
    parser.add_argument("--id", required=True)
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    args = parser.parse_args(argv)

    if not SAFE_ID_PATTERN.fullmatch(args.id):
        print(
            f"report_check: invalid id {args.id!r}: must match [a-zA-Z0-9_-]+",
            file=sys.stderr,
        )
        return 2

    report = Path(args.base_dir) / "reports" / f"{args.id}.md"
    try:
        markdown = report.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"report_check: cannot read {report}: {exc}", file=sys.stderr)
        return 2

    violations = find_violations(markdown)
    json.dump(
        {"report": str(report), "violations": [asdict(v) for v in violations]},
        sys.stdout,
        ensure_ascii=False,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(_main())
