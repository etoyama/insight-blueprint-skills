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


def _terms_rows(markdown: str) -> list[list[str]]:
    match = re.search(
        r"^## Terms\s*$(.*?)(?=^## |\Z)", markdown, re.MULTILINE | re.DOTALL
    )
    if not match:
        raise ValueError("'## Terms' section not found")
    rows = [line for line in match.group(1).splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def render(markdown: str) -> dict[str, str]:
    allow: list[str] = []
    flag: list[str] = []
    for term, _code, _definition, avoid, _origin in _terms_rows(markdown):
        allow.append(term)
        for variant in re.split(r"、", avoid):
            # A variant qualified with a condition (「…（…とき）」) is only wrong in some
            # contexts, so flagging every occurrence would be noise.
            if variant in ("", "—") or "（" in variant:
                continue
            flag.append(f"{variant}\t{term}")
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
