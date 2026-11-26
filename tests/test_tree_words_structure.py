"""Structure tests: the words shown to the analyst live in one module (#273).

The page of a question tree and the report say a reflection round and the
subject in the same words, so both read them from ``tree_words``. A name a
module keeps to itself (a leading underscore) stays inside that module.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from skills._shared import tree_words

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED = REPO_ROOT / "skills" / "_shared"
WORDS = "tree_words.py"
SOURCES = sorted(
    [
        *(REPO_ROOT / "skills").rglob("*.py"),
        *(REPO_ROOT / "scripts").glob("*.py"),
        *(REPO_ROOT / "src").rglob("*.py"),
    ]
)


def _strings(path: Path) -> list[str]:
    """Every string a module holds that is not a docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_the_words_module_is_listed_with_the_shared_modules() -> None:
    layout = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    (shared_line,) = [line for line in layout.splitlines() if "_shared/（" in line]

    assert "tree_words.py" in shared_line


# 回目 counts a reflection round or a revision of the subject; 主題 is the
# word for the root question (ADR-0055).
@pytest.mark.parametrize("word", ["回目", "主題"])
def test_only_the_words_module_spells_a_word_the_page_and_the_report_share(
    word: str,
) -> None:
    spelled = [
        path.name
        for path in sorted(SHARED.glob("*.py"))
        if any(word in text for text in _strings(path))
    ]

    assert spelled == [WORDS]


def _japanese_strings(value: object) -> Iterator[str]:
    """Every string inside *value* that an analyst could read (field names are ASCII)."""
    if isinstance(value, str):
        if not value.isascii():
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _japanese_strings(item)
    elif isinstance(value, tuple):
        for item in value:
            yield from _japanese_strings(item)


def test_no_other_shared_module_holds_a_copy_of_a_word() -> None:
    """A heading the legend quotes, or a label the report repeats, is read from the module."""
    # A word the module borrows (the name of a journal event) is spelled by its owner.
    spelled_here = set(_strings(SHARED / WORDS))
    words = {
        word
        for name, value in vars(tree_words).items()
        if not name.startswith("_")
        for word in _japanese_strings(value)
        if word in spelled_here
    }
    assert words
    copies = {
        path.name: sorted(words.intersection(_strings(path)))
        for path in sorted(SHARED.glob("*.py"))
        if path.name != WORDS
    }

    assert {name: found for name, found in copies.items() if found} == {}


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_module_imports_a_name_another_module_keeps_to_itself(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    private = [
        f"{node.module}.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name.startswith("_") and not alias.name.startswith("__")
    ]

    assert private == []
