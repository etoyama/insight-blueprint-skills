"""Where each analysis of a tree page stands: its stage, and what waits for the analyst.

Pure, like ``tree_render``: every string is untrusted and goes through
``_html``. The words come from ``tree_words``; the stage from
``AnalysisStage`` (ADR-0061 6), never from the status alone.
"""

from __future__ import annotations

from insight_blueprint.models.analysis_stage import AnalysisStage
from skills._shared._html import Html, el, join
from skills._shared.design_note import status_word
from skills._shared.tree_render_parts import (
    Context,
    DesignSummary,
    id_key,
    join_links,
    link_to,
)
from skills._shared.tree_words import (
    ASKS_LEAD,
    LINKED_NODES,
    STAGE_WORDS,
    STAGES_WITH_STATUS,
    STOP_REASON,
    WHAT_IS_ASKED,
    asks_heading,
)

STAGE_CSS = """.progress-stopped { border-left-color: var(--stopped); }
.stage {
  font-weight: 700; border: 1px solid; border-radius: 3px; padding: 0 .4em;
  white-space: nowrap;
}
.stage-before_run { color: var(--muted); border-style: dashed; }
.stage-running { color: var(--accent); }
.stage-awaiting_confirmation { color: var(--awaiting-confirmation); }
.stage-stopped { color: var(--stopped); }
.stage-awaiting_reflection { color: var(--awaiting-reflection); }
.stage-finished { color: var(--analyzed); }
.asks {
  border: 2px solid var(--awaiting-confirmation); padding: .2rem 1rem .6rem;
  margin: 1rem 0;
}
.asks h2 { margin-top: .6rem; }
"""


def stage_parts(design: DesignSummary) -> list[Html | str]:
    """The stage word, and the status word where it adds to the stage.

    A design keeps its status while it waits, stops or has its results, so a
    status word there would read against the stage.
    """
    parts: list[Html | str] = [
        el(
            "span",
            STAGE_WORDS[design.stage][0],
            class_=f"stage stage-{design.stage.value}",
        )
    ]
    if design.stage in STAGES_WITH_STATUS:
        parts.append(f"　{status_word(design.form, design.status)}")
    return parts


def stage_notes(design: DesignSummary) -> list[Html]:
    """What a design waiting for the analyst asks, or why it was stopped."""
    notes = [el("p", f"{WHAT_IS_ASKED}: {ask}") for ask in design.asks]
    if design.stop_reason is not None:
        notes.append(el("p", f"{STOP_REASON}: {design.stop_reason}"))
    return notes


def _ask_item(context: Context, design: DesignSummary) -> Html:
    nodes = context.linked_by.get(design.id, [])
    head = el(
        "p",
        el("strong", link_to(f"design-{design.id}", design.id)),
        f" {design.title}",
    )
    linked = (
        el("p", f"{LINKED_NODES}: ", *join_links(nodes), class_="meta")
        if nodes
        else None
    )
    return el("li", join([head, linked, *stage_notes(design)]))


def asks_section(context: Context) -> Html | None:
    """The analyses that wait for the analyst, ahead of the answer; none, no section."""
    waiting = [
        d
        for d in sorted(context.designs.values(), key=lambda d: id_key(d.id))
        if d.stage is AnalysisStage.awaiting_confirmation
    ]
    if not waiting:
        return None
    items = join(_ask_item(context, d) for d in waiting)
    return el(
        "section",
        join(
            [
                el("h2", asks_heading(len(waiting))),
                el("p", ASKS_LEAD),
                el("ul", items),
            ]
        ),
        class_="asks",
        id="asks",
    )
