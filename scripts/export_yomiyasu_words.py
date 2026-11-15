"""Export docs/UBIQUITOUS_LANGUAGE.md into the yomiyasu word lists (docs/WORKFLOW.md §8).

UBIQUITOUS_LANGUAGE stays canonical; .yomiyasu-words/ is generated so the two cannot drift.
tests/docs/test_canonical_docs.py fails when the generated files are stale.

Usage: uv run python scripts/export_yomiyasu_words.py
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADER = "# Generated from docs/UBIQUITOUS_LANGUAGE.md by scripts/export_yomiyasu_words.py. Do not edit.\n"

TERM = "用語"
CODE_NAME = "コード上の名前"
DEFINITION = "定義"
AVOID = "使わない言い換え"


def strip_code_fences(markdown: str) -> str:
    """Drop fenced blocks so a quoted template's headings and tables are not read as the document's."""
    return re.sub(r"^```.*?^```[^\n]*$", "", markdown, flags=re.MULTILINE | re.DOTALL)


def section(markdown: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)",
        markdown,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"'## {title}' section not found")
    return match.group(1)


def terms_rows(markdown: str) -> list[dict[str, str]]:
    lines = [
        line for line in section(markdown, "Terms").splitlines() if line.startswith("|")
    ]
    header, *body = [
        [cell.strip() for cell in line.strip("|").split("|")] for line in lines
    ]
    return [dict(zip(header, cells, strict=True)) for cells in body[1:]]


def render(markdown: str) -> dict[str, str]:
    allow: list[str] = []
    flag: list[str] = []
    for row in terms_rows(markdown):
        allow.append(row[TERM])
        for variant in row[AVOID].split("、"):
            # A variant qualified with a condition (「…（…とき）」) is only wrong in some
            # contexts, so flagging every occurrence would be noise.
            if variant in ("", "—") or "（" in variant:
                continue
            flag.append(f"{variant}\t{row[TERM]}")
    return {
        "allow.txt": HEADER + "\n".join(allow) + "\n",
        "flag.txt": HEADER + "\n".join(flag) + "\n",
    }


def main() -> None:
    markdown = (REPO_ROOT / "docs/UBIQUITOUS_LANGUAGE.md").read_text(encoding="utf-8")
    out_dir = REPO_ROOT / ".yomiyasu-words"
    out_dir.mkdir(exist_ok=True)
    for name, content in render(markdown).items():
        (out_dir / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
