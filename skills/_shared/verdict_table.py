"""The metrics of a verdict and the tables they make (Epic 33, ADR-0052 8, 9).

Pure: no I/O, no escaping. The analysis note (HTML) and the theme report
(Markdown) escape in their own ways, so the rules of the tables live here once,
as text not yet escaped: a ``TextTable``. A renderer escapes each written piece
of it and draws it.

Every number is the literal text of the verdict JSON: nothing is computed,
rounded or sorted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from insight_blueprint.models.design import DesignForm


class MetricJudgment(StrEnum):
    """What a confirmation's primary metric says of the hypothesis (ADR-0052)."""

    supported = "supported"
    rejected = "rejected"
    inconclusive = "inconclusive"


# The kind of an interval saved as ``confidence_interval``, before intervals named theirs.
CONFIDENCE = "confidence"


@dataclass(frozen=True)
class ValueInterval:
    """The interval of a metric's value. ``kind`` is the name the notebook gave it."""

    kind: str
    level: str
    lower: str
    upper: str


@dataclass(frozen=True)
class MetricGroup:
    """The value of a metric in one group. It is measured, never judged."""

    group: tuple[str, ...]  # one name per axis of the metric's ``by``
    value: str | None
    p: str | None
    effect_size: tuple[str, str] | None  # (kind, value)
    interval: ValueInterval | None
    sample_size: str | None


@dataclass(frozen=True)
class VerdictMetric:
    """One entry of ``verdict.metrics``. Every number is the literal JSON text.

    The lines and the judgment belong to a confirmation's primary metric; the
    threshold and the pass to a secondary or guardrail metric. Nothing here
    enforces that: a metric shows what the notebook wrote.
    """

    name: str
    value: str | None
    threshold: str | None
    p: str | None
    passed: bool | None
    effect_size: tuple[str, str] | None  # (kind, value)
    interval: ValueInterval | None
    sample_size: str | None
    support_line: str | None = None
    reject_line: str | None = None
    judgment: MetricJudgment | None = None
    by: tuple[str, ...] = ()  # the axes of ``groups``; empty when there are none
    groups: tuple[MetricGroup, ...] = ()


class Fixed(str):
    """Words the table writes itself: a renderer shows them without escaping.

    Markdown would turn the brackets of an interval into ``\\[``, so the pieces
    a renderer escapes have to be told apart from the template's.
    """


# One cell, heading or title, in pieces: a ``Fixed`` piece is the table's own,
# any other piece is text from the verdict. () where the verdict holds nothing.
Text = tuple[str, ...]


@dataclass(frozen=True)
class TextTable:
    """A table before escaping."""

    title: Text | None  # a group table's metric and axes; None for the table of metrics
    headings: tuple[Text, ...]
    rows: tuple[tuple[Text, ...], ...]


_DASH = "—"

JUDGMENT_WORDS: Mapping[MetricJudgment, str] = {
    MetricJudgment.supported: "支持",
    MetricJudgment.rejected: "棄却",
    MetricJudgment.inconclusive: "結論しない",
}

# The kinds of interval with a word; any other shows as written (ADR-0052 8).
INTERVAL_WORDS: Mapping[str, str] = {
    CONFIDENCE: "信頼区間",
    "hdi": "HDI",
    "eti": "等裾信用区間",
}


def interval_text(interval: ValueInterval) -> Text:
    """The kind, the level and the bounds as written: the level is not made a percent."""
    word = INTERVAL_WORDS.get(interval.kind)
    kind = Fixed(word) if word else (interval.kind or Fixed(_DASH))
    return (
        kind,
        Fixed(" 水準 "),
        interval.level,
        Fixed(": ["),
        interval.lower,
        Fixed(", "),
        interval.upper,
        Fixed("]"),
    )


# The columns an exploration leaves out: it measures, and judges nothing (ADR-0050).
_JUDGING = frozenset(("支持の線", "棄却の線", "判定", "しきい値", "合否"))
# The headings each renderer words its own way, since before Epic 33.
_SAMPLE_SIZE = "N"
_P = "p"

# A row's cells as (column heading, text); None where the verdict holds nothing.
_Cells = tuple[tuple[str, Text | None], ...]


def _written(text: str | None) -> Text | None:
    return None if text is None else (text,)


def _measured(item: VerdictMetric | MetricGroup) -> _Cells:
    """The cells a metric and a group share: what was measured."""
    effect = item.effect_size
    return (
        ("値", _written(item.value)),
        (
            "効果量",
            None
            if effect is None
            else (effect[1], Fixed("（"), effect[0], Fixed("）")),
        ),
        ("区間", None if item.interval is None else interval_text(item.interval)),
        (_SAMPLE_SIZE, _written(item.sample_size)),
    )


def _metric_cells(m: VerdictMetric) -> _Cells:
    return (
        *_measured(m),
        ("支持の線", _written(m.support_line)),
        ("棄却の線", _written(m.reject_line)),
        ("判定", None if m.judgment is None else (Fixed(JUDGMENT_WORDS[m.judgment]),)),
        ("しきい値", _written(m.threshold)),
        (_P, _written(m.p)),
        ("合否", None if m.passed is None else (Fixed("✓" if m.passed else "✗"),)),
    )


def _group_cells(g: MetricGroup) -> _Cells:
    return (*_measured(g), (_P, _written(g.p)))


def _filled_table(
    title: Text | None,
    leading: Sequence[Text],
    names: Sequence[Sequence[str]],
    rows: Sequence[_Cells],
    heading: Callable[[str], str],
    shown: Callable[[str], bool] = lambda heading: True,
) -> TextTable:
    """Each row's *names*, then its cells; a column of cells no row fills is left out."""
    keep = [
        i
        for i, (h, _) in enumerate(rows[0])
        if shown(h) and any(row[i][1] is not None for row in rows)
    ]
    return TextTable(
        title,
        (*leading, *((Fixed(heading(rows[0][i][0])),) for i in keep)),
        tuple(
            (*((n,) for n in row_names), *(row[i][1] or () for i in keep))
            for row_names, row in zip(names, rows, strict=True)
        ),
    )


def _title(m: VerdictMetric) -> Text:
    axes: list[str] = []
    for i, axis in enumerate(m.by):
        axes += [Fixed(" × "), axis] if i else [axis]
    return (m.name, Fixed("（"), *axes, Fixed("）"))


def _across(m: VerdictMetric) -> TextTable | None:
    """Two axes of values only: the first axis down, the second across (ADR-0052 9).

    The names keep the order they were first written in: sorting could put "10"
    before "9". None when a pair is written twice, since one value would hide.
    """
    if len(m.by) != 2 or any(
        v is not None for g in m.groups for _, v in _group_cells(g)[1:]
    ):
        return None
    values = {g.group: g.value for g in m.groups}
    if len(values) != len(m.groups):
        return None
    down = dict.fromkeys(g.group[0] for g in m.groups)
    across = dict.fromkeys(g.group[1] for g in m.groups)
    return TextTable(
        _title(m),
        ((m.by[0],), *((a,) for a in across)),
        tuple(
            ((d,), *(_written(values.get((d, a))) or () for a in across)) for d in down
        ),
    )


def metric_tables(
    metrics: Sequence[VerdictMetric], form: DesignForm, *, sample_size: str, p: str
) -> tuple[TextTable, ...]:
    """The table of metrics, then a table of its own for each metric with groups.

    *sample_size* and *p* head those columns: the note and the report word them
    apart, as they did before Epic 33.
    """
    words = {_SAMPLE_SIZE: sample_size, _P: p}

    def heading(key: str) -> str:
        return words.get(key, key)

    def shown(key: str) -> bool:
        return form.judges or key not in _JUDGING

    # A metric that shows nothing but groups is shown in its own table only.
    listed = [
        m
        for m in metrics
        if not m.groups or any(v is not None and shown(h) for h, v in _metric_cells(m))
    ]
    main = (
        (
            _filled_table(
                None,
                [(Fixed("指標"),)],
                [[m.name] for m in listed],
                [_metric_cells(m) for m in listed],
                heading,
                shown,
            ),
        )
        if listed
        else ()
    )
    grouped = tuple(
        _across(m)
        or _filled_table(
            _title(m),
            [(axis,) for axis in m.by],
            [g.group for g in m.groups],
            [_group_cells(g) for g in m.groups],
            heading,
        )
        for m in metrics
        if m.groups
    )
    return main + grouped
