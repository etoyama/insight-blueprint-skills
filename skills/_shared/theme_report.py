"""The final report of a theme, written by code from its records (Epic 29).

Pure: no I/O. Every sentence is a fixed template or a text copied from the
records, so a model's wording cannot enter the report. A copied text keeps its
words: ``escape_source_text`` only makes its marks show as characters. Nothing is
computed or reformatted, and no time or path goes into the text: the same records
give the same bytes.

Every event id the text puts in brackets goes through one ``_Cites``, so the
Appendix lists exactly the records the report cites.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from insight_blueprint.models.design import DesignStatus
from insight_blueprint.models.tree import (
    Aim,
    AimKind,
    Answer,
    NextCandidate,
    Progress,
    StatementKind,
    TreeDecision,
    TreeDecisionKind,
)
from skills._shared.design_note import (
    EVENT_WORDS,
    LEAD_SENTENCES,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    VerdictMetric,
)
from skills._shared.tree_render import PROGRESS_WORDS, CitedEvent

_DASH = "—"

# The glossary's words a reader does not know, and what the report says instead.
# Every fixed sentence takes these words from here (ADR-0039).
READER_WORDS: Mapping[str, str] = {
    "根の問い": "主題",
    "journal の出来事": "記録",
    "分析設計": "分析",
    "親の論点": "上位の論点",
    "寄与": "答えると分かること",
}
_ROOT = READER_WORDS["根の問い"]
_RECORD = READER_WORDS["journal の出来事"]
_DESIGN = READER_WORDS["分析設計"]
_PARENT = READER_WORDS["親の論点"]
_CONTRIBUTION = READER_WORDS["寄与"]

# The eight characters ADR-0019 escapes, and two more: GFM strikes through
# ``~x~`` (``2019~2023``), and ``&lt;`` would show as ``<``.
_MARKS = re.compile(r"([\\`*_\[\]<|~&])")
# Line breaks and tabs: a table row or a list item ends at a line break.
_BREAKS = re.compile(r"[\t\n\v\f\r\x85\u2028\u2029]+")
# A mark that opens a block when a text heads a list item: a heading, a quote,
# a list. The fences' marks are escaped everywhere already. A rule would need
# the whole line, and a list item ends with the cited ids.
_HEAD_MARK = re.compile(
    r"^(\d{0,9})(#(?=#{0,5}(?:\s|$))|>|[-+](?=\s|$)|(?<=\d)[.)](?=\s|$))"
)
# The marks that close a heading: a run of ``#`` at the end, after a space or
# alone (a heading puts a space before the text).
_TAIL_MARK = re.compile(r"(?:(?<=\s)|^)#(?=#*$)")


def escape_source_text(text: str) -> str:
    """*text* from the records, as Markdown that shows it as characters (US-3 AC 3).

    Breaks fold into one space and the ends lose their spaces, which Markdown
    does not show anyway; every other character stays. Each of ADR-0019's eight
    characters, ``~`` and ``&`` get a backslash, and so does a mark that would
    open a block at the head (heading, quote, list) or close a heading at the
    end (``#``).
    """
    text = _MARKS.sub(r"\\\1", _BREAKS.sub(" ", text).strip())
    text = _HEAD_MARK.sub(r"\1\\\2", text, count=1)
    return _TAIL_MARK.sub(r"\\#", text, count=1)


_e = escape_source_text

# The order of this table is the order of the groups in the report.
_KIND_HEADINGS: dict[StatementKind, str] = {
    StatementKind.claim: "言えること",
    StatementKind.weakening: "留保すべきこと",
    StatementKind.undetermined: "まだ分からないこと",
}

# The fields of an aim are texts from the records; the sentences escape them.
_AIM_SENTENCES: dict[AimKind, str] = {
    AimKind.business: "{decision_maker}が、{decision}を決めるための分析である。",
    AimKind.research: (
        "{audience}が、主張を吟味するための分析である。主張の範囲は「{claim_scope}」である。"
    ),
}

# The two items of each kind of aim, as the Introduction lists them.
_AIM_ITEMS: dict[AimKind, tuple[tuple[str, str], ...]] = {
    AimKind.business: (("決める人", "decision_maker"), ("決めること", "decision")),
    AimKind.research: (("想定読者", "audience"), ("主張の範囲", "claim_scope")),
}

_ABSTRACT_LEAD = (
    f"{_ROOT}への現時点の答えは次のとおり。"
    f"文の後ろの括弧は根拠にした{_RECORD}の番号で、本文は Appendix にある。"
)

_NOT_CONCLUDED = f"この{_DESIGN}は、まだ結論が出ていない。"
_BEFORE_ROOT_CHANGE = f"この答えは、{_ROOT}を今の形に見直す前に書いた。"

# What a decision says about its node: where to look next, or where it stopped.
_DECISION_WORDS = {
    TreeDecisionKind.close: "調べるのを止めた論点",
}
_NEXT_NODE = "次に調べる論点"


@dataclass(frozen=True)
class ReportNode:
    """One question below the root, as the report shows it.

    ``answer`` is the current answer, given under whichever root revision; a
    node without one is a question not answered yet.
    """

    id: str
    question: str
    parent: str
    contribution: str
    progress: Progress
    answer: Answer | None
    design_ids: tuple[str, ...]
    next_candidate: NextCandidate | None


@dataclass(frozen=True)
class ReportDesign:
    """One design linked to the tree, as the report shows it.

    Holds no connection, no code and not the whole journal: only the events the
    report quotes. Every value is the text the records hold.
    """

    id: str
    title: str
    hypothesis: str
    method: str  # "" when the design has no methodology
    package: str
    method_reason: str
    status: DesignStatus
    conclude_events: tuple[NoteEvent, ...]
    contradicting_evidence: tuple[NoteEvent, ...]
    metrics: tuple[VerdictMetric, ...]
    figures: tuple[NoteFigure, ...]

    @property
    def lead_sentence(self) -> str | None:
        """The fixed sentence of a terminal status; None before the design concludes."""
        return LEAD_SENTENCES.get(self.status)

    @classmethod
    def of(cls, note: DesignNote) -> ReportDesign:
        """The part of the analysis note the report shows: both read the same records."""
        design = note.design
        methodology = design.methodology
        conclusion = note.conclusion
        return cls(
            id=design.id,
            title=design.title,
            hypothesis=design.hypothesis_statement,
            method="" if methodology is None else methodology.method,
            package="" if methodology is None else methodology.package,
            method_reason="" if methodology is None else methodology.reason,
            status=design.status,
            conclude_events=() if conclusion is None else conclusion.conclude_events,
            # Evidence against the hypothesis counts before the design concludes too.
            contradicting_evidence=tuple(
                e
                for e in note.events
                if e.type == "evidence" and e.direction == "contradicts"
            ),
            metrics=() if note.verdict is None else note.verdict.metrics,
            figures=note.figures,
        )


@dataclass(frozen=True)
class ThemeReport:
    """The final report of a theme, as read from its records. Never stored.

    ``nodes`` are the questions below the root and ``designs`` the designs
    linked to any node, both in tree order. ``records`` holds at least every
    event the report cites.
    """

    theme_id: str
    root_question: str
    aim: Aim
    round: int
    root_revision: int
    answer: Answer
    nodes: tuple[ReportNode, ...]
    designs: tuple[ReportDesign, ...]
    sources: tuple[NoteSource, ...]
    decision: TreeDecision | None
    records: Mapping[str, CitedEvent]

    def answered_nodes(self) -> list[ReportNode]:
        return [n for n in self.nodes if n.answer is not None]

    def evidence_of(self, node: ReportNode) -> list[ReportDesign]:
        """The designs linked to *node*, in the order it links them."""
        by_id = {d.id: d for d in self.designs}
        return [by_id[d] for d in node.design_ids]

    def figures(self) -> list[str]:
        """The file names of the figures the report shows, in its order, each once."""
        files: dict[str, None] = {}
        for node in self.answered_nodes():
            for design in self.evidence_of(node):
                for figure in design.figures:
                    files[figure.file] = None
        return list(files)


@dataclass
class _Cites:
    """The event ids the text cites, in the order first cited."""

    ids: dict[str, None] = field(default_factory=dict)

    def mark(self, ids: Iterable[str]) -> str:
        ids = list(ids)
        for event_id in ids:
            self.ids[event_id] = None
        # The tree checks the ids an answer cites; the ids of conclude events
        # and of evidence against come from the journal unchecked.
        return f"（{'、'.join(_e(i) for i in ids)}）"


def _cell(text: str) -> str:
    return text or _DASH


def _table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """A table; each cell of *rows* is escaped already, or an id."""
    lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
        *(f"| {' | '.join(_cell(c) for c in row)} |" for row in rows),
    ]
    return "\n".join(lines)


def _aim_sentence(aim: Aim) -> str:
    fields = {k: _e(v) for k, v in aim.model_dump().items() if isinstance(v, str)}
    return _AIM_SENTENCES[aim.kind].format(**fields)


def _statements(answer: Answer, cites: _Cites) -> list[str]:
    blocks: list[str] = []
    for kind, heading in _KIND_HEADINGS.items():
        lines = [
            f"- {_e(s.text)}{cites.mark(s.cites)}"
            for s in answer.statements
            if s.kind is kind
        ]
        if lines:
            blocks.append("\n".join([f"**{heading}**", "", *lines]))
    return blocks


def _abstract(report: ThemeReport, cites: _Cites) -> list[str]:
    return [
        "## Abstract",
        f"{_aim_sentence(report.aim)}{_ABSTRACT_LEAD}",
        *_statements(report.answer, cites),
    ]


def _introduction(report: ThemeReport) -> list[str]:
    aim = report.aim.model_dump()
    items = [f"- {_ROOT}: {_e(report.root_question)}"] + [
        f"- {label}: {_e(aim[key])}" for label, key in _AIM_ITEMS[report.aim.kind]
    ]
    if not report.nodes:
        return ["## Introduction", "\n".join(items), f"{_ROOT}を論点に分けていない。"]
    table = _table(
        ("論点", "問い", _PARENT, _CONTRIBUTION, "進捗"),
        (
            (
                n.id,
                _e(n.question),
                n.parent,
                _e(n.contribution),
                PROGRESS_WORDS[n.progress][0],
            )
            for n in report.nodes
        ),
    )
    return [
        "## Introduction",
        "\n".join(items),
        f"{_ROOT}を、次の論点に分けて調べた。",
        table,
    ]


def _method_text(design: ReportDesign) -> str:
    if design.method and design.package:
        return f"{_e(design.method)}（{_e(design.package)}）"
    return _e(design.method)


def _method(report: ThemeReport) -> list[str]:
    blocks = ["## Method"]
    if report.designs:
        answered = {
            d.id: [n.id for n in report.nodes if d.id in n.design_ids]
            for d in report.designs
        }
        blocks.append(
            _table(
                (_DESIGN, "答える論点", "仮説", "手法", "手法を選んだ理由"),
                (
                    (
                        f"{d.id} {_e(d.title)}",
                        "、".join(answered[d.id]),
                        _e(d.hypothesis),
                        _method_text(d),
                        _e(d.method_reason),
                    )
                    for d in report.designs
                ),
            )
        )
    else:
        blocks.append(f"論点に結んだ{_DESIGN}は無い。")
    if report.sources:
        blocks += [
            "分析に使ったデータソースは次のとおり。",
            _table(
                ("名前", "種類", "説明"),
                ((_e(s.name), _e(s.type), _e(s.description)) for s in report.sources),
            ),
        ]
    else:
        blocks.append("データソースは宣言していない。")
    return blocks


def _or_none(text: str | None) -> str | None:
    return None if text is None else _e(text)


# Each column of the metric table: its heading and how a metric fills it.
_METRIC_COLUMNS = (
    ("値", lambda m: _or_none(m.value)),
    (
        "効果量",
        lambda m: f"{_e(m.effect_size[1])}（{_e(m.effect_size[0])}）"
        if m.effect_size
        else None,
    ),
    (
        "信頼区間",
        lambda m: (
            f"水準 {_e(m.confidence_interval[0])}: "
            f"[{_e(m.confidence_interval[1])}, {_e(m.confidence_interval[2])}]"
        )
        if m.confidence_interval
        else None,
    ),
    ("標本サイズ", lambda m: _or_none(m.sample_size)),
    ("しきい値", lambda m: _or_none(m.threshold)),
    ("p 値", lambda m: _or_none(m.p)),
    ("合否", lambda m: None if m.passed is None else ("✓" if m.passed else "✗")),
)


def _metrics(metrics: Sequence[VerdictMetric]) -> list[str]:
    if not metrics:
        return []
    # A column no metric fills would be a column of dashes.
    columns = [
        (heading, fill)
        for heading, fill in _METRIC_COLUMNS
        if any(fill(m) is not None for m in metrics)
    ]
    return [
        _table(
            ("指標", *(heading for heading, _ in columns)),
            ([_e(m.name), *(fill(m) or "" for _, fill in columns)] for m in metrics),
        )
    ]


@dataclass
class _FigureNumbers:
    """Numbers the image links from the top of the report."""

    count: int = 0

    def block(self, figure: NoteFigure) -> list[str]:
        self.count += 1
        n = self.count
        return [
            # The file name passed the reader's check: a bare name, no brackets.
            f"![図 {n}](../notebooks/{figure.file})",
            f"図 {n}: {_e(figure.title)}。軸: {_e(figure.axes)}。"
            f"読み方: {_e(figure.how_to_read)}",
        ]


def _evidence(
    design: ReportDesign, cites: _Cites, numbers: _FigureNumbers
) -> list[str]:
    # A space before the closing ** would leave the bold open.
    name = " ".join(t for t in (design.id, _e(design.title)) if t)
    blocks = [f"**根拠となる{_DESIGN}: {name}**"]
    lead = design.lead_sentence
    if lead is None:
        blocks.append(_NOT_CONCLUDED)
    else:
        blocks.append(
            lead
            + "".join(
                f"{_e(e.content)}{cites.mark([e.id])}" for e in design.conclude_events
            )
        )
    blocks += _metrics(design.metrics)
    for figure in design.figures:
        blocks += numbers.block(figure)
    return blocks


def _results(report: ThemeReport, cites: _Cites) -> list[str]:
    blocks = ["## Results"]
    numbers = _FigureNumbers()
    answered = report.answered_nodes()
    if not answered:
        blocks.append("答えのある論点はまだ無い。")
    for node in answered:
        answer = node.answer
        if answer is None:  # answered_nodes() keeps only nodes with one
            continue
        blocks.append(f"### {node.id} {_e(node.question)}")
        if answer.root_revision < report.root_revision:
            blocks.append(_BEFORE_ROOT_CHANGE)
        blocks += _statements(answer, cites)
        for design in report.evidence_of(node):
            blocks += _evidence(design, cites, numbers)
    return blocks


def _event_items(events: Sequence[NoteEvent], cites: _Cites) -> str:
    return "\n".join(f"- {_e(e.content)}{cites.mark([e.id])}" for e in events)


def _limitations(report: ThemeReport, cites: _Cites) -> list[str]:
    blocks = ["### Limitations"]
    against = [d for d in report.designs if d.contradicting_evidence]
    for design in against:
        blocks += [
            f"{design.id} {_e(design.title)} の仮説に反する証拠:",
            _event_items(design.contradicting_evidence, cites),
        ]
    if not against:
        blocks.append("仮説に反する証拠は記録されていない。")
    unanswered = [n for n in report.nodes if n.answer is None]
    if unanswered:
        blocks += [
            "次の論点には、まだ答えていない。",
            _table(
                ("論点", "問い", _CONTRIBUTION),
                ((n.id, _e(n.question), _e(n.contribution)) for n in unanswered),
            ),
        ]
    else:
        blocks.append("まだ答えていない論点は無い。")
    return blocks


def _heard(node: ReportNode) -> str | None:
    candidate = node.next_candidate
    if candidate is None or not candidate.answer:
        return None
    return (
        f"- {node.id} について聞いた答え（{_e(candidate.answered_by)}、"
        f"{candidate.answered_at}）: {_e(candidate.answer)}"
    )


def _future_directions(report: ThemeReport) -> list[str]:
    lines: list[str] = []
    decision = report.decision
    if decision is None:
        lines.append("- ツリーの決定はまだ無い。")
    else:
        questions = {n.id: n.question for n in report.nodes}
        question = questions.get(decision.node_id, report.root_question)
        label = _DECISION_WORDS.get(decision.kind, _NEXT_NODE)
        lines += [
            f"- {label}: {decision.node_id} {_e(question)}",
            f"- 理由: {_e(decision.reason)}",
        ]
    lines += [line for n in report.nodes if (line := _heard(n)) is not None]
    return ["### Future Directions", "\n".join(lines)]


def _appendix(report: ThemeReport, cites: _Cites) -> list[str]:
    def row(event_id: str) -> tuple[str, str, str]:
        event = report.records[event_id]
        word = EVENT_WORDS.get(event.type) or _e(event.type)
        return (_e(event_id), word, _e(event.content))

    return [
        "## Appendix",
        f"### 根拠にした{_RECORD}",
        _table((f"{_RECORD}の番号", "種類", "本文"), (row(i) for i in cites.ids)),
    ]


def _blocks(report: ThemeReport) -> Iterator[str]:
    cites = _Cites()
    yield f"# {_e(report.root_question)}"
    yield (
        f"テーマ {report.theme_id} のレポート。"
        f"{report.round}回目の振り返りの時点の記録にもとづく。"
    )
    yield from _abstract(report, cites)
    yield from _introduction(report)
    yield from _method(report)
    yield from _results(report, cites)
    yield "## Discussion"
    yield from _limitations(report, cites)
    yield from _future_directions(report)
    # Last, so every id cited above is listed.
    yield from _appendix(report, cites)


def render_report(report: ThemeReport) -> str:
    """The Markdown of *report*."""
    return "\n\n".join(_blocks(report)) + "\n"
