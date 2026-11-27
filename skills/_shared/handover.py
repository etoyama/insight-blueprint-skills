"""What the analyst reads before designs are handed over, and where they differ (ADR-0063).

The one place of the rule: the tree page marks the rows it names, and
``tree_io handover`` gives the same rows to the driver, which sums them up in
the chat (ADR-0063 5). Holds no markup, and names no row: the page and the
command take the row words from ``tree_words``. A value is the text the design
holds, joined with the fewest words of its own (the axes of a chart).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import AnalysisDesign, DesignForm, MetricTier
from insight_blueprint.models.tree import QuestionTree, TreeDecisionKind
from skills._shared.design_note import intent_word, statement_of


class HandoverRow(StrEnum):
    """A row of the check, in the order the analyst reads it (ADR-0063 2)."""

    intent = "intent"
    statement = "statement"  # the question of an exploration, else the hypothesis
    criterion = "criterion"
    population = "population"
    grain = "grain"
    denominator = "denominator"
    sources = "sources"
    method = "method"
    metric = "metric"
    extraction = "extraction"
    chart = "chart"


# The rows a mark compares between the designs (ADR-0063 4): what is counted,
# and from what. The other rows differ by nature from one design to the next.
COMPARED_ROWS = (
    HandoverRow.population,
    HandoverRow.grain,
    HandoverRow.denominator,
    HandoverRow.sources,
)

# The stages a design is read from before it is handed over. One waiting for
# the analyst after its extraction changed may be read again (35.7): its stage
# goes here then.
READ_BEFORE_HANDOVER = frozenset({AnalysisStage.before_run})

# A row's value: a text, the steps of the extraction or the charts, or None
# when the design does not write it.
Value = str | tuple[str, ...] | None


def _step_text(step: object) -> str:
    """A step of ``methodology.steps`` as written: its description, or itself."""
    if isinstance(step, dict):
        description = cast("dict[str, object]", step).get("description")
        if isinstance(description, str):
            return description
    return str(step)


def _chart_text(intent: str, kind: str, description: str, x: str, y: str) -> str:
    axes = "、".join(
        f"{name}: {value}" for name, value in (("横", x), ("縦", y)) if value
    )
    detail = "。".join(part for part in (kind or intent, axes) if part)
    return f"{description}（{detail}）" if description else detail


def _values(design: AnalysisDesign) -> dict[HandoverRow, Value]:
    scope = design.data_scope
    methodology = design.methodology
    primary = [m for m in design.metrics if m.tier is MetricTier.primary]
    criterion = "、".join(m.comparison for m in primary if m.comparison)
    steps = (methodology.model_extra or {}).get("steps") if methodology else None
    return {
        HandoverRow.intent: intent_word(design),
        HandoverRow.statement: statement_of(design)[0] or None,
        # An exploration is not judged, so it has no criterion to read.
        HandoverRow.criterion: (criterion or None) if design.form().judges else None,
        HandoverRow.population: scope.population if scope else None,
        HandoverRow.grain: scope.grain if scope else None,
        HandoverRow.denominator: scope.denominator if scope else None,
        # The ids the extraction names as {source:ID}; a set, so the order is not compared.
        HandoverRow.sources: "、".join(sorted(set(design.source_ids))) or None,
        HandoverRow.method: (
            None
            if methodology is None
            else methodology.method
            + (f"（{methodology.package}）" if methodology.package else "")
        ),
        HandoverRow.metric: "、".join(
            m.target + (f"（{m.aggregation}）" if m.aggregation else "")
            for m in primary
        )
        or None,
        HandoverRow.extraction: (
            tuple(_step_text(s) for s in steps)
            if isinstance(steps, list) and steps
            else None
        ),
        HandoverRow.chart: tuple(
            _chart_text(c.intent.value, c.type, c.description, c.x, c.y)
            for c in design.chart
        )
        or None,
    }


@dataclass(frozen=True)
class HandoverDesign:
    """A design as the check lays it beside the others: one value a row."""

    id: str
    title: str
    form: DesignForm
    values: Mapping[HandoverRow, Value]

    @classmethod
    def of(cls, design: AnalysisDesign) -> HandoverDesign:
        return cls(design.id, design.title, design.form(), _values(design))


def to_hand_over(tree: QuestionTree, stages: Mapping[str, AnalysisStage]) -> list[str]:
    """The designs to read before the hand-over, in the order of the last decision.

    Those linked to a question the last decision names, at a stage read before
    the hand-over. A close hands nothing over. A design linked to two of the
    questions is read once.
    """
    if not tree.decisions or tree.decisions[-1].kind is TreeDecisionKind.close:
        return []
    named = (tree.node(n) for n in tree.decisions[-1].node_ids())
    linked = dict.fromkeys(d for node in named for d in node.design_ids)
    return [d for d in linked if stages.get(d) in READ_BEFORE_HANDOVER]


def differing_rows(designs: Sequence[HandoverDesign]) -> tuple[HandoverRow, ...]:
    """The compared rows whose values are not the same in every design.

    The text is compared as written: the same meaning in other words differs
    (ADR-0063, Consequences).
    """
    return tuple(
        row for row in COMPARED_ROWS if len({d.values[row] for d in designs}) > 1
    )
