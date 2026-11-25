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


def _literal(text: str) -> str:
    # yomiyasu accepts a backslash only before a symbol, so re.escape (which also
    # escapes spaces) cannot be used.
    return re.sub(r"([.^$*+?{}\[\]\\|()])", r"\\\1", text)


def _pattern(word: str, terms: list[str]) -> str:
    """Match ``word`` except where it is part of another term (検証仮説, 探索の問い)."""
    behind: list[str] = []
    ahead: list[str] = []
    for term in terms:
        at = term.find(word)
        if term == word or at < 0:
            continue
        if at > 0:
            behind.append(f"(?<!{_literal(term[:at])})")
        else:
            ahead.append(f"(?!{_literal(term[len(word) :])})")
    return (
        "".join(dict.fromkeys(behind)) + _literal(word) + "".join(dict.fromkeys(ahead))
    )


def _word(variant: str) -> str:
    word = variant.split("（", 1)[0].strip()
    if not word:
        raise ValueError(f"variant {variant!r} has no word before its condition")
    return word


def render(markdown: str) -> dict[str, str]:
    rows = terms_rows(markdown)
    terms = [row[TERM] for row in rows]
    flag: list[str] = []
    patterns: list[str] = []
    pattern_words: set[str] = set()
    for row in rows:
        for variant in row[AVOID].split("、"):
            if variant in ("", "—"):
                continue
            if "（" not in variant:
                flag.append(f"{variant}\t{row[TERM]}")
                continue
            # A variant qualified with a condition (「…（…とき）」) is only wrong in some
            # contexts. A flag.txt word would also match inside the terms that contain it
            # (仮説 in 検証仮説), so it goes to flag-patterns.txt with those terms skipped,
            # and the pattern's name carries the condition for the reader.
            word = _word(variant)
            regex = _pattern(word, terms)
            if word.isascii() and word.isalnum():
                regex = rf"\b{regex}\b"
            patterns.append(f"{variant}は{row[TERM]}\t{regex}")
            pattern_words.add(word)
    # yomiyasu drops a pattern's hit when the matched text is in allow.txt, so a term
    # that is also a pattern's word (仮説, アップロード) is left out of it.
    allow = [term for term in terms if term not in pattern_words]
    return {
        "allow.txt": HEADER + "\n".join(allow) + "\n",
        "flag.txt": HEADER + "\n".join(flag) + "\n",
        "flag-patterns.txt": HEADER + "\n".join(patterns) + "\n",
    }


def main() -> None:
    markdown = (REPO_ROOT / "docs/UBIQUITOUS_LANGUAGE.md").read_text(encoding="utf-8")
    out_dir = REPO_ROOT / ".yomiyasu-words"
    out_dir.mkdir(exist_ok=True)
    for name, content in render(markdown).items():
        (out_dir / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
