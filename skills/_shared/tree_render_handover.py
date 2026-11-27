"""The check before a hand-over on a tree page: the designs side by side (ADR-0063).

Pure, like ``tree_render``: every string is untrusted and goes through
``_html``. Which designs are read is chosen by the caller with
``handover.to_hand_over``, which rows differ by ``handover.differing_rows``;
the words come from ``tree_words``.
"""

from __future__ import annotations

from collections.abc import Sequence

from skills._shared._html import Html, el, join
from skills._shared.handover import (
    Absent,
    ChartPlan,
    HandoverDesign,
    HandoverRow,
    differing_rows,
)
from skills._shared.tree_render_parts import Context, join_links, link_to
from skills._shared.tree_words import (
    ABSENT_WORDS,
    COMMENT_WORD,
    DIFFERS_WORD,
    GATHER_BUTTON,
    GATHERED_HEAD,
    GATHERED_NOTE,
    HANDOVER_LEAD,
    HANDOVER_ROW_WORDS,
    LINKED_NODES,
    NO_COMMENT,
    chart_text,
    handover_heading,
)

HANDOVER_CSS = """.handover {
  border: 2px solid var(--accent); padding: .2rem 1rem .6rem; margin: 1rem 0;
}
.handover h2 { margin-top: .6rem; }
.handover .scroll { overflow-x: auto; }
.handover table { border-collapse: collapse; width: 100%; }
.handover th, .handover td {
  border: 1px solid var(--line); padding: .3rem .5rem; text-align: left;
  vertical-align: top; overflow-wrap: anywhere;
}
.handover thead th { min-width: 16rem; }
.handover thead .meta { display: block; font-weight: 400; }
.handover tbody th { width: 7.5em; white-space: nowrap; }
.handover tr.differs th { border-left: 4px solid var(--investigating); }
.handover .differs-word {
  display: block; color: var(--investigating); font-weight: 700; font-size: .85rem;
}
.handover pre {
  margin: 0 0 .3rem; white-space: pre-wrap; overflow-wrap: break-word;
  background: var(--bg); padding: .3rem .4rem; font-size: .85rem;
}
.handover ul { margin: 0; padding-left: 1.1rem; }
.handover textarea { width: 100%; box-sizing: border-box; min-height: 4.5em; font: inherit; }
.handover button { font: inherit; margin: .6rem 0 .3rem; padding: .2rem .8rem; }
"""

# Gathers the comment of each design after its id into the read-only box. It
# reads the page and writes the page: nothing leaves it (ADR-0063 7). The words
# are the box's data attributes, so the script holds none.
HANDOVER_SCRIPT = """(function () {
  var button = document.getElementById("handover-gather");
  var out = document.getElementById("handover-gathered");
  if (!button || !out) { return; }
  button.addEventListener("click", function () {
    var lines = [];
    document.querySelectorAll("textarea[data-design-id]").forEach(function (box) {
      var text = box.value.trim();
      if (text) { lines.push(box.dataset.designId + ": " + text); }
    });
    out.value = lines.length ? out.dataset.head + "\\n" + lines.join("\\n") : out.dataset.none;
    out.hidden = false;
    out.focus();
    out.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(out.value).catch(function () {});
    }
  });
})();
"""


def _value(design: HandoverDesign, row: HandoverRow) -> Html:
    value = design.values[row]
    if isinstance(value, Absent):
        return el("td", ABSENT_WORDS[value])
    if isinstance(value, str):
        return el("td", value)
    if row is HandoverRow.extraction:
        # In full, each step as written: the analyst reads the query itself.
        return el("td", join(el("pre", str(step)) for step in value))
    lines = (chart_text(v) if isinstance(v, ChartPlan) else v for v in value)
    return el("td", el("ul", join(el("li", line) for line in lines)))


def _row(designs: Sequence[HandoverDesign], row: HandoverRow, differs: bool) -> Html:
    head = el(
        "th",
        HANDOVER_ROW_WORDS[row],
        el("span", DIFFERS_WORD, class_="differs-word") if differs else None,
        scope="row",
    )
    return el(
        "tr",
        head,
        *(_value(d, row) for d in designs),
        class_="differs" if differs else None,
        data_row=row.value,
    )


def _column_head(context: Context, design: HandoverDesign) -> Html:
    nodes = context.linked_by.get(design.id, [])
    return el(
        "th",
        el("strong", link_to(f"design-{design.id}", design.id)),
        f" {design.title} ",
        el("span", f"{LINKED_NODES}: ", *join_links(nodes), class_="meta")
        if nodes
        else None,
        scope="col",
    )


def _comment_row(designs: Sequence[HandoverDesign]) -> Html:
    return el(
        "tr",
        el("th", COMMENT_WORD, scope="row"),
        *(
            el(
                "td",
                el(
                    "textarea",
                    "",
                    data_design_id=d.id,
                    aria_label=f"{d.id} {COMMENT_WORD}",
                ),
            )
            for d in designs
        ),
        data_row="comment",
    )


def handover_section(
    context: Context, designs: Sequence[HandoverDesign]
) -> Html | None:
    """*designs*, chosen by ``handover.to_hand_over``, side by side; none, no section."""
    if not designs:
        return None
    differs = set(differing_rows(designs))
    table = el(
        "table",
        el(
            "thead",
            el("tr", el("td", ""), *(_column_head(context, d) for d in designs)),
        ),
        el(
            "tbody",
            join(_row(designs, row, row in differs) for row in HandoverRow),
            _comment_row(designs),
        ),
    )
    return el(
        "section",
        join(
            [
                el("h2", handover_heading(len(designs))),
                el("p", HANDOVER_LEAD),
                el("div", table, class_="scroll"),
                el("button", GATHER_BUTTON, type="button", id="handover-gather"),
                el(
                    "textarea",
                    "",
                    id="handover-gathered",
                    readonly="",
                    hidden="",
                    aria_label=GATHERED_HEAD,
                    data_head=GATHERED_HEAD,
                    data_none=NO_COMMENT,
                ),
                el("p", GATHERED_NOTE, class_="note"),
            ]
        ),
        class_="handover",
        id="handover",
    )
