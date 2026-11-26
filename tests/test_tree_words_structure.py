"""Structure tests: the words shown to the analyst live in one module (#273).

The page of a question tree and the report say a reflection round and the
subject in the same words, so both read them from ``tree_words``. A name a
module keeps to itself (a leading underscore) stays inside that module.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED = REPO_ROOT / "skills" / "_shared"
WORDS = "tree_words.py"
SOURCES = sorted(
    [
        *SHARED.glob("*.py"),
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


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
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
