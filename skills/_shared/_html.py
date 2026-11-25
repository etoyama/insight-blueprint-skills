"""Trusted-markup helpers shared by the page renderers (Epic 18, Epic 28).

Every string that reaches a page comes from analysts or models, so none of it is
trusted. ``el`` escapes each plain ``str`` it is given; only an ``Html`` value,
which only ``el`` and the constants of the renderers produce, goes in as markup.
The question-tree page and the analysis note share this one type so that a note
placed inside the tree page is not escaped a second time.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape


class Html(str):
    """Markup that is already safe to place in the page."""


def el(tag: str, *children: str | None, **attrs: str | None) -> Html:
    """Build ``<tag>``; a plain ``str`` child or attribute value is escaped.

    A ``None`` child or attribute is left out.
    """
    rendered = "".join(
        f' {name.rstrip("_")}="{escape(value, quote=True)}"'
        for name, value in attrs.items()
        if value is not None
    )
    inner = "".join(
        child if isinstance(child, Html) else escape(child, quote=True)
        for child in children
        if child is not None
    )
    return Html(f"<{tag}{rendered}>{inner}</{tag}>")


def table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> Html:
    """A table in a ``table-wrap`` box, which scrolls when the table is wide."""
    return el(
        "div",
        el(
            "table",
            el("thead", el("tr", *(el("th", h) for h in headers))),
            el("tbody", *(el("tr", *(el("td", c) for c in row)) for row in rows)),
        ),
        class_="table-wrap",
    )


def join(blocks: Iterable[Html | None]) -> Html:
    return Html("\n".join(b for b in blocks if b is not None))


BASE_CSS = """
:root {
  --bg: #fbfaf7; --fg: #1f2328; --muted: #59636e; --line: #c9ced6;
  --panel: #ffffff; --accent: #0b5cad;
  --not-started: #6b7280; --investigating: #9a6700; --analyzed: #1a7f37;
  --mark: #8250df;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14171a; --fg: #e6e8ea; --muted: #9aa4af; --line: #3a4048;
    --panel: #1c2024; --accent: #6cb2ff;
    --not-started: #9aa4af; --investigating: #e3b341; --analyzed: #56d364;
    --mark: #c297ff;
  }
}
body {
  background: var(--bg); color: var(--fg); margin: 0 auto; padding: 16px;
  max-width: 60rem; line-height: 1.6;
  font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif;
}
h1 { font-size: 1.4rem; margin: 0 0 .5rem; }
h2 { font-size: 1.1rem; margin: 2rem 0 .5rem; border-bottom: 1px solid var(--line); }
a { color: var(--accent); }
details { margin: .4rem 0; }
summary { cursor: pointer; color: var(--accent); }
.note, .meta { color: var(--muted); font-size: .9rem; }
"""


def page(title: str, css: str, body: Html) -> str:
    """A standalone page: no script, no external resource, no timestamp."""
    head = el(
        "head",
        Html('<meta charset="utf-8">'),
        Html('<meta name="viewport" content="width=device-width, initial-scale=1">'),
        el("title", title),
        el("style", Html(css)),
    )
    return "<!doctype html>\n" + el("html", head, el("body", body), lang="ja") + "\n"
