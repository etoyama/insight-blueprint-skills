"""Tests for the Markdown helpers the structure tests share (tests/skills/_markdown.py)."""

from __future__ import annotations

import pytest

from tests.skills._markdown import bold_item

LIST = """\
Intro.

- **First** — one line
  wrapped on to a second.
  - a nested bullet stays inside
  - **Nested** — a nested bold bullet stays inside too

  a paragraph indented under the item stays inside
- **Second** — the next sibling ends the first.
Plain text at the margin.

1. A numbered item
   - **Inner** — ends where a line is not indented past its marker
   - **Other** — the sibling
2. The next numbered item
"""


class TestBoldItem:
    def test_the_item_ends_at_its_next_sibling(self) -> None:
        item = bold_item(LIST, "First")
        assert item.startswith("- **First** — one line")
        assert "wrapped on to a second." in item
        assert "**Second**" not in item

    def test_nested_lines_and_indented_paragraphs_stay_inside(self) -> None:
        item = bold_item(LIST, "First")
        assert "- **Nested**" in item
        assert "a paragraph indented under the item stays inside" in item

    def test_a_line_at_the_margin_ends_the_item(self) -> None:
        assert "Plain text" not in bold_item(LIST, "Second")

    def test_an_indented_item_ends_at_a_shallower_line(self) -> None:
        assert "**Other**" not in bold_item(LIST, "Inner")
        assert "The next numbered item" not in bold_item(LIST, "Other")

    def test_the_label_is_matched_literally(self) -> None:
        text = "- **axb** — not this\n- **a.b** — dot\n"
        assert bold_item(text, "a.b") == "- **a.b** — dot\n"

    def test_a_missing_label_fails_the_test(self) -> None:
        with pytest.raises(AssertionError, match="Missing"):
            bold_item(LIST, "Missing")
