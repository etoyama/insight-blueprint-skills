"""The analysis note of one analysis design (Epic 28, ADR-0036).

Pure: no I/O. ``design_note_read`` reads the files and hands a ``DesignNote`` in
here. The note lays out what the design, the journal and the notebook output
say, as written. Nothing is computed, rounded or summarized: a number is the
literal text of the verdict JSON.

The note is a fragment (``render_note``) so that the question-tree page can hold
one per design; ``render_note_page`` wraps it as a standalone page. Every id
inside it starts with the note anchor, so notes of several designs can share
one page.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from insight_blueprint.models.design import AnalysisDesign
from skills._shared._html import BASE_CSS, Html, el, join, page


@dataclass(frozen=True)
class NoteSource:
    """A data source as a note may show it; it has no place for a connection."""

    name: str
    type: str
    description: str


@dataclass(frozen=True)
class NoteEvent:
    """One journal event."""

    id: str
    type: str
    direction: str | None
    content: str
    created_at: str  # as written in the journal; "" when absent


@dataclass(frozen=True)
class VerdictMetric:
    """One entry of ``verdict.metrics``. Every number is the literal JSON text."""

    name: str
    value: str | None
    threshold: str | None
    p: str | None
    passed: bool | None
    effect_size: tuple[str, str] | None  # (kind, value)
    confidence_interval: tuple[str, str, str] | None  # (level, lower, upper)
    sample_size: str | None


@dataclass(frozen=True)
class NoteFigure:
    title: str
    axes: str
    how_to_read: str
    png: bytes


@dataclass(frozen=True)
class DesignNote:
    design: AnalysisDesign
    sources: tuple[NoteSource, ...]
    events: tuple[NoteEvent, ...]  # journal order
    # None: no verdict file, so the notebook has not run. (): a verdict that
    # holds no metric values.
    metrics: tuple[VerdictMetric, ...] | None
    figures: tuple[NoteFigure, ...]


NOTE_CSS = """
.design-note { margin: 0 0 3rem; overflow-wrap: anywhere; }
.design-note section { margin: 0; }
.design-note .table-wrap { overflow-x: auto; }
.design-note table { border-collapse: collapse; margin: .5rem 0; }
.design-note th, .design-note td {
  border: 1px solid var(--line); padding: .25rem .6rem; text-align: left;
  vertical-align: top; overflow-wrap: break-word;
}
.design-note th { background: var(--panel); white-space: nowrap; }
.design-note figure { margin: 1rem 0; }
.design-note img { max-width: 100%; height: auto; border: 1px solid var(--line); }
.design-note figcaption { color: var(--muted); font-size: .9rem; }
.design-note .status { background: var(--panel); border: 1px solid var(--line); padding: .5rem 1rem; }
.design-note .status p { margin: .2rem 0; }
"""

_DASH = "—"

_DIRECTION_GROUPS = (
    ("supports", "仮説を支持する証拠"),
    ("contradicts", "仮説に反する証拠"),
)
_NEUTRAL_GROUP = "向きの無い証拠"

_SECTIONS = (
    ("hypothesis", "仮説と背景"),
    ("decision", "決定の文脈"),
    ("method", "手法"),
    ("metrics", "指標の定義"),
    ("explanatory", "説明変数"),
    ("sources", "データソース"),
    ("results", "結果"),
)


def note_anchor(design_id: str) -> str:
    return f"note-{design_id}"


def _cell(text: str) -> str:
    return text if text else _DASH


def _table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> Html:
    return el(
        "div",
        el(
            "table",
            el("thead", el("tr", *(el("th", h) for h in headers))),
            el("tbody", *(el("tr", *(el("td", c) for c in row)) for row in rows)),
        ),
        class_="table-wrap",
    )


def _section(anchor: str, name: str, heading: str, *content: Html | None) -> Html:
    return el(
        "section",
        el("h3", heading),
        join(content),
        id=f"{anchor}-{name}",
    )


def _status(note: DesignNote, anchor: str) -> Html:
    last = note.events[-1] if note.events else None
    if last is None:
        journal = "journal にまだ出来事が無い。"
    else:
        journal = f"載せた journal の最後の出来事の時刻: {last.created_at or '（時刻の記載なし）'}"
    verdict = "あり" if note.metrics is not None else "まだ無い"
    return el(
        "div",
        el("p", f"状態: {note.design.status.value}"),
        el("p", journal),
        el("p", f"notebook の結果（verdict）: {verdict}"),
        el(
            "ul",
            *(
                el("li", el("a", label, href=f"#{anchor}-{name}"))
                for name, label in _SECTIONS
            ),
        ),
        class_="status",
        id=f"{anchor}-status",
    )


def _hypothesis(design: AnalysisDesign, anchor: str) -> Html:
    return _section(
        anchor,
        "hypothesis",
        "仮説と背景",
        el("p", design.hypothesis_statement),
        el("p", design.hypothesis_background),
    )


def _decision(design: AnalysisDesign, anchor: str) -> Html:
    context = design.decision_context
    body = (
        el("p", "決定の文脈は書かれていない。")
        if context is None
        else join(
            [
                el("p", f"決める人: {context.decision_maker}"),
                el("p", f"決めること: {context.decision}"),
            ]
        )
    )
    return _section(anchor, "decision", "決定の文脈", body)


def _method(design: AnalysisDesign, anchor: str) -> Html:
    methodology = design.methodology
    if methodology is None:
        return _section(anchor, "method", "手法", el("p", "手法は書かれていない。"))
    steps = (methodology.model_extra or {}).get("steps")
    return _section(
        anchor,
        "method",
        "手法",
        el("p", f"手法: {methodology.method}"),
        el("p", f"パッケージ: {methodology.package}") if methodology.package else None,
        el("p", f"理由: {methodology.reason}") if methodology.reason else None,
        el("ol", *(el("li", str(step)) for step in steps))
        if isinstance(steps, list)
        else None,
    )


def _metric_definitions(design: AnalysisDesign, anchor: str) -> Html:
    body = (
        _table(
            ("対象", "区分", "集計", "グループ", "絞り込み", "比べ方"),
            (
                (
                    _cell(m.target),
                    m.tier.value,
                    _cell(m.aggregation),
                    _cell(", ".join(str(g) for g in m.grouping)),
                    _cell(m.filter),
                    _cell(m.comparison),
                )
                for m in design.metrics
            ),
        )
        if design.metrics
        else el("p", "指標の定義は無い。")
    )
    return _section(anchor, "metrics", "指標の定義", body)


def _explanatory(design: AnalysisDesign, anchor: str) -> Html:
    body = (
        _table(
            ("名前", "役割", "説明", "時点"),
            (
                (
                    _cell(v.name),
                    v.role.value,
                    _cell(v.description),
                    _cell(v.time_points),
                )
                for v in design.explanatory
            ),
        )
        if design.explanatory
        else el("p", "説明変数は無い。")
    )
    return _section(anchor, "explanatory", "説明変数", body)


def _sources(note: DesignNote, anchor: str) -> Html:
    body = (
        _table(
            ("名前", "種類", "説明"),
            (
                (_cell(s.name), _cell(s.type), _cell(s.description))
                for s in note.sources
            ),
        )
        if note.sources
        else el("p", "データソースは宣言していない。")
    )
    return _section(anchor, "sources", "データソース", body)


def _event_list(events: Sequence[NoteEvent]) -> Html:
    return el(
        "ul",
        *(el("li", el("span", f"{e.id} ", class_="meta"), e.content) for e in events),
    )


def _events(note: DesignNote) -> list[Html]:
    observed = [e for e in note.events if e.type == "observe"]
    evidence = [e for e in note.events if e.type == "evidence"]
    if not observed and not evidence:
        return [el("p", "journal に観察も証拠もまだ記録されていない。")]
    blocks: list[Html] = []
    if observed:
        blocks += [el("h4", "観察"), _event_list(observed)]
    known = {direction for direction, _ in _DIRECTION_GROUPS}
    groups = [
        (label, [e for e in evidence if e.direction == direction])
        for direction, label in _DIRECTION_GROUPS
    ] + [(_NEUTRAL_GROUP, [e for e in evidence if e.direction not in known])]
    for label, members in groups:
        if members:
            blocks += [el("h4", label), _event_list(members)]
    return blocks


def _pass_mark(passed: bool | None) -> str:
    if passed is None:
        return _DASH
    return "✓" if passed else "✗"


def _metric_row(m: VerdictMetric) -> list[str]:
    effect = f"{m.effect_size[1]}（{m.effect_size[0]}）" if m.effect_size else _DASH
    interval = (
        f"水準 {m.confidence_interval[0]}: "
        f"[{m.confidence_interval[1]}, {m.confidence_interval[2]}]"
        if m.confidence_interval
        else _DASH
    )
    return [
        _cell(m.name),
        m.value or _DASH,
        effect,
        interval,
        m.sample_size or _DASH,
        m.threshold or _DASH,
        m.p or _DASH,
        _pass_mark(m.passed),
    ]


def _metric_values(metrics: tuple[VerdictMetric, ...]) -> list[Html]:
    if not metrics:
        return [el("h4", "指標の値"), el("p", "verdict に指標の値は無い。")]
    return [
        el("h4", "指標の値"),
        _table(
            ("指標", "値", "効果量", "信頼区間", "N", "しきい値", "p", "合否"),
            (_metric_row(m) for m in metrics),
        ),
    ]


def _figure(figure: NoteFigure, number: int) -> Html:
    encoded = base64.b64encode(figure.png).decode("ascii")
    return el(
        "figure",
        el("img", src=f"data:image/png;base64,{encoded}", alt=f"図 {number}"),
        el(
            "figcaption",
            el("div", el("strong", figure.title)),
            el("div", f"軸の説明: {figure.axes}"),
            el("div", f"図の読み方: {figure.how_to_read}"),
        ),
    )


def _figures(note: DesignNote, anchor: str) -> Html:
    body = (
        join(_figure(f, i) for i, f in enumerate(note.figures, start=1))
        if note.figures
        else el("p", "図はまだ無い。")
    )
    return el("div", el("h4", "図"), body, id=f"{anchor}-figures")


def _results(note: DesignNote, anchor: str) -> Html:
    return _section(
        anchor,
        "results",
        "結果",
        el("p", "notebook をまだ実行していない（verdict が無い）。")
        if note.metrics is None
        else None,
        join(_events(note)),
        join(_metric_values(note.metrics)) if note.metrics is not None else None,
        _figures(note, anchor),
    )


def render_note(note: DesignNote) -> Html:
    """The note as one ``<section>``, ready to sit inside a page."""
    design = note.design
    anchor = note_anchor(design.id)
    return el(
        "section",
        el("h2", f"分析ノート {design.id} {design.title}"),
        _status(note, anchor),
        _hypothesis(design, anchor),
        _decision(design, anchor),
        _method(design, anchor),
        _metric_definitions(design, anchor),
        _explanatory(design, anchor),
        _sources(note, anchor),
        _results(note, anchor),
        class_="design-note",
        id=anchor,
    )


def render_note_page(note: DesignNote) -> str:
    return page(f"分析ノート {note.design.id}", BASE_CSS + NOTE_CSS, render_note(note))
