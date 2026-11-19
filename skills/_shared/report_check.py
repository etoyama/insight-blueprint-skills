"""Check a finished report for markup that would still be active (Epic 13).

``/analysis-report`` tells the model to backslash-escape text that came from source
data. This module checks the result in code, so a rule the model skipped is caught
whichever model wrote the report. It only reads: it never rewrites the report.

The check fails closed and parses no Markdown. The only places it treats as safe
are a backslash escape and a ``mermaid`` fence at the left margin, which are all a
report laid out as the template says needs. Code spans and other fences are
checked like any text, because a renderer can end them where a line scanner would
not: GFM splits a table cell on "|" inside a code span, a link destination takes
a backtick before a code span can, and a list item ends the fence it holds.
Inline links and bare URLs are out of scope
(docs/design/epic-13-report-source-text.md, Decision ``checker-ignores-links``).

Usage from a skill (CLI):
    report_check --id FP-H01 [--base-dir .insight]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from skills._shared.ids import SAFE_ID_PATTERN

DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))

MAX_TEXT_LENGTH = 120

# CommonMark ends a line at any of the three, so a lone "\r" counts too.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")

# Where a tag, comment, declaration, or autolink can start. The rest of the tag is
# not parsed: a grammar that misses one shape (a ">" inside an attribute value, a
# tag that continues on the next line) lets that shape through.
_TAG_START = re.compile(r"<(?:/?[A-Za-z]|[!?])")
_MERMAID_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)

_FENCE_OPEN = re.compile(r"(`{3,}|~{3,})(.*)")
_FENCE_CLOSE = re.compile(r"(`{3,}|~{3,})[ \t]*")

# The only lines the lineage export writes (insight_blueprint.lineage.exporter),
# with its exact indent. Anything else in a mermaid fence (click, a directive, a
# subgraph) is not ours, and a label line with another indent may not be Mermaid.
_MERMAID_STATEMENT = re.compile(
    r"""graph\ LR
      | \ {4}Step\d+\["[^"]*"\]
      | \ {4}Step\d+\ -->\|"[^"]*"\|\ Step\d+
      | [ \t]*""",
    re.VERBOSE,
)

# An image is allowed only as a figure: a notebook output beside the report.
_FIGURE = re.compile(
    r"!\[(?:[^\[\]\\]|\\.)*\]\(\.\./notebooks/(?!.*\.\.)[A-Za-z0-9_.-]+\.png\)"
)


@dataclass(frozen=True)
class Violation:
    line: int
    kind: str  # "image" | "html" | "mermaid-html" | "mermaid-statement"
    text: str


def find_violations(markdown: str) -> list[Violation]:
    violations: list[Violation] = []
    mermaid_fence: str | None = None  # the marker that opened it, while open

    for number, line in enumerate(_LINE_BREAK.split(markdown), start=1):
        if mermaid_fence is None:
            hits = _scan_text(line)
            mermaid_fence = _opens_mermaid(line)
        elif _closes(line, mermaid_fence):
            hits = iter(())
            mermaid_fence = None
        else:
            hits = _scan_mermaid(line)
        violations.extend(
            Violation(number, kind, text[:MAX_TEXT_LENGTH]) for kind, text in hits
        )
    return violations


def _opens_mermaid(line: str) -> str | None:
    match = _FENCE_OPEN.fullmatch(line)
    if match is None:
        return None
    marker, info = match.group(1), match.group(2)
    if marker[0] == "`" and "`" in info:
        return None
    words = info.split()
    return marker if words and words[0].lower() == "mermaid" else None


def _closes(line: str, opened_by: str) -> bool:
    match = _FENCE_CLOSE.fullmatch(line)
    return (
        match is not None
        and match.group(1)[0] == opened_by[0]
        and len(match.group(1)) >= len(opened_by)
    )


def _scan_text(line: str) -> Iterator[tuple[str, str]]:
    i = 0
    while i < len(line):
        if line[i] == "\\":
            # Skipping the escaped character is what makes an odd run of
            # backslashes escape and an even run not.
            i += 2
        elif line.startswith("![", i):
            end = _inline_image_end(line, i)
            construct = line[i:] if end is None else line[i:end]
            if end is not None and _FIGURE.fullmatch(construct):
                i += 2  # a figure's alt text is still text that can carry a tag
            else:
                yield "image", construct
                i = i + 2 if end is None else end
        elif _TAG_START.match(line, i):
            tag = _tag_text(line, i)
            yield "html", tag
            i += len(tag)
        else:
            i += 1


def _scan_mermaid(line: str) -> Iterator[tuple[str, str]]:
    if _MERMAID_STATEMENT.fullmatch(line) is None:
        yield "mermaid-statement", line.strip()
        return
    # Mermaid reads no Markdown escape, so a tag after a backslash still counts.
    for match in _TAG_START.finditer(line):
        if _MERMAID_BR.match(line, match.start()) is None:
            yield "mermaid-html", _tag_text(line, match.start())


def _tag_text(line: str, start: int) -> str:
    end = line.find(">", start)
    return line[start:] if end == -1 else line[start : end + 1]


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
