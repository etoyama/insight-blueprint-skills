"""What the analyst reads before designs are handed over, and where they differ (ADR-0063).

The one place of the rule: the tree page marks the rows it names, and
``tree_io handover`` gives the same rows to the driver, which sums them up in
the chat (ADR-0063 5). Holds no markup and no word: a value is what the design
holds, and ``tree_words`` says it to the analyst.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple, cast

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import AnalysisDesign, Metric, MetricTier
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

# The stages a design is read from before it is handed over.
READ_BEFORE_HANDOVER = frozenset({AnalysisStage.before_run})


class Absent(StrEnum):
    """Why a row has no value: the design does not write it, or has no such thing."""

    not_written = "not_written"
    # An exploration is not judged, so it has no criterion (ADR-0063 3).
    not_judged = "not_judged"


class ChartPlan(NamedTuple):
    """A chart as the design plans it; ``kind`` is its type, else its intent."""

    description: str
    kind: str
    x: str
    y: str


# A row's value: a text, the steps of the extraction, the charts, or why none.
Value = str | tuple[str, ...] | tuple[ChartPlan, ...] | Absent


def _step_text(step: object) -> str:
    """A step of ``methodology.steps`` as written: its description, or itself."""
    if isinstance(step, dict):
        description = cast("dict[str, object]", step).get("description")
        if isinstance(description, str):
            return description
    return str(step)


def _steps(steps: object) -> tuple[str, ...] | Absent:
    if isinstance(steps, list) and steps:
        return tuple(_step_text(s) for s in steps)
    # A query written as one text is still the query the analyst reads.
    if isinstance(steps, str) and steps:
        return (steps,)
    return Absent.not_written


def _criterion(design: AnalysisDesign, primary: list[Metric]) -> str | Absent:
    if not design.form().judges:
        return Absent.not_judged
    return (
        "、".join(m.comparison for m in primary if m.comparison) or Absent.not_written
    )


def _values(design: AnalysisDesign) -> dict[HandoverRow, Value]:
    scope = design.data_scope
    methodology = design.methodology
    primary = [m for m in design.metrics if m.tier is MetricTier.primary]
    missing = Absent.not_written
    return {
        HandoverRow.intent: intent_word(design),
        HandoverRow.statement: statement_of(design)[0] or missing,
        HandoverRow.criterion: _criterion(design, primary),
        HandoverRow.population: scope.population if scope else missing,
        HandoverRow.grain: scope.grain if scope else missing,
        HandoverRow.denominator: scope.denominator if scope else missing,
        # The ids the extraction names as {source:ID}; a set, so the order is not compared.
        HandoverRow.sources: "、".join(sorted(set(design.source_ids))) or missing,
        HandoverRow.method: (
            missing
            if methodology is None
            else methodology.method
            + (f"（{methodology.package}）" if methodology.package else "")
        ),
        HandoverRow.metric: "、".join(
            m.target + (f"（{m.aggregation}）" if m.aggregation else "")
            for m in primary
        )
        or missing,
        HandoverRow.extraction: _steps(
            (methodology.model_extra or {}).get("steps") if methodology else None
        ),
        HandoverRow.chart: tuple(
            ChartPlan(c.description, c.type or c.intent.value, c.x, c.y)
            for c in design.chart
        )
        or missing,
    }


@dataclass(frozen=True)
class HandoverDesign:
    """A design as the check lays it beside the others: one value a row."""

    id: str
    title: str
    values: Mapping[HandoverRow, Value]

    states_scope: bool

    @classmethod
    def of(cls, design: AnalysisDesign) -> HandoverDesign:
        return cls(
            design.id, design.title, _values(design), design.data_scope is not None
        )


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
