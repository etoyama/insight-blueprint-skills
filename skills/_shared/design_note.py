"""The analysis note of one analysis design (Epic 28, ADR-0036).

Pure: no I/O. ``design_note_read`` reads the files and hands a ``DesignNote`` in
here. The note lays out what the design, the journal and the notebook output
say, as written. Nothing is computed, rounded or summarized: a number is the
literal text of the verdict JSON. The notebook's code comes cell by cell, never
with its data-load cell, which holds the connection values (ADR-0022).

The note is a fragment (``render_note``) so that the question-tree page can hold
one per design; ``render_note_page`` wraps it as a standalone page. Every id
inside it starts with the note anchor, so notes of several designs can share
one page.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import (
    AnalysisDesign,
    AnalysisIntent,
    DesignForm,
    DesignStatus,
)
from skills._shared._html import BASE_CSS, Html, el, join, page, table
from skills._shared.design_note_reviews import NoteReviewBatch, review_batch
from skills._shared.verdict_table import (
    Fixed,
    Text,
    TextTable,
    VerdictMetric,
    metric_tables,
)


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


def contradicting_evidence(
    events: Iterable[NoteEvent], form: DesignForm
) -> tuple[NoteEvent, ...]:
    """The evidence events against the hypothesis, in journal order.

    An exploration holds no hypothesis, so nothing stands against it, whatever
    direction an event carries (ADR-0050).
    """
    if not form.judges:
        return ()
    return tuple(
        e for e in events if e.type == "evidence" and e.direction == "contradicts"
    )


@dataclass(frozen=True)
class NoteVerdict:
    """What the note shows of ``{id}_verdict.json``, besides its figures."""

    metrics: tuple[VerdictMetric, ...]
    conclusion: str | None  # the one line the notebook wrote; None when absent


@dataclass(frozen=True)
class NoteFigure:
    file: str  # a bare file name under notebooks/, as the manifest gave it
    title: str
    axes: str
    how_to_read: str
    png: bytes


@dataclass(frozen=True)
class CodeCell:
    """One cell of the notebook ``.py``; never the data-load cell."""

    position: int  # 1-based place among the cells of the file
    name: str  # the text after "# %%" on the cell's first line; may be empty
    source: str  # as written, from the "# %%" line on


@dataclass(frozen=True)
class Conclusion:
    """What the records hold once a design reaches a terminal status.

    Copies of the journal and the design only: no sentence here is generated.
    """

    status: DesignStatus  # terminal
    conclude_events: tuple[NoteEvent, ...]
    # (field, text) of the next_action branch for the status, e.g. "if_rejected.pivot"
    next_action: tuple[tuple[str, str], ...]
    contradicting_evidence: tuple[NoteEvent, ...]
    reflect_events: tuple[NoteEvent, ...]
    open_questions: tuple[NoteEvent, ...]


@dataclass(frozen=True)
class DesignNote:
    design: AnalysisDesign
    sources: tuple[NoteSource, ...]
    events: tuple[NoteEvent, ...]  # journal order
    verdict: NoteVerdict | None  # None: no verdict file, so the notebook has not run
    figures: tuple[NoteFigure, ...]
    # None: no notebook, or one whose data-load cell cannot be told apart.
    cells: tuple[CodeCell, ...] | None
    lineage: str | None  # the Mermaid text of lineage/{id}.mmd
    local_files: tuple[str, ...]  # paths under .insight/ that exist, LOCAL_FILES order
    conclusion: Conclusion | None  # None: the design is not in a terminal status
    stage: AnalysisStage  # AnalysisStage.of the design and its journal (ADR-0061 6)
    reviews: tuple[NoteReviewBatch, ...] = ()  # newest first
    # The first stop event's text; None unless the stage is stopped.
    stop_reason: str | None = None
    # What each confirmation no answer names yet asks; () unless the stage waits for it.
    asks: tuple[str, ...] = ()


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
.design-note pre {
  background: var(--panel); border: 1px solid var(--line); padding: .5rem;
  overflow-x: auto; font-size: .85rem; line-height: 1.4;
}
.design-note ol.events li { margin: .4rem 0; }
"""

# What "手元のファイル" may link, as paths under .insight/. Both the tree page
# (themes/) and the standalone page (notes/) sit one level below .insight/, so
# "../" + path reaches the file from either.
_NOTEBOOK_PY = "notebooks/{id}.py"
LOCAL_FILES = (
    ("notebook の .py", _NOTEBOOK_PY),
    ("verdict", "notebooks/{id}_verdict.json"),
    ("lineage", "lineage/{id}.mmd"),
    ("notebook の HTML", "notebooks/{id}.html"),
)


def local_file_paths(design_id: str) -> tuple[str, ...]:
    return tuple(path.format(id=design_id) for _, path in LOCAL_FILES)


_DASH = "—"

_NEUTRAL_GROUP = "向きの無い証拠"
_ALL_EVIDENCE = "証拠"

# The section keeps the anchor name "hypothesis" for every form, so a link
# into a note does not change with its form; its heading comes from FormWords.
_OPENING = "hypothesis"
_SECTIONS = (
    (_OPENING, ""),
    ("decision", "決定の文脈"),
    ("method", "手法"),
    ("metrics", "指標の定義"),
    ("explanatory", "説明変数"),
    ("sources", "データソース"),
    ("results", "結果"),
    ("reviews", "レビュー"),
    ("conclusion", "結論"),
    ("code", "分析コード"),
    ("lineage", "データ加工の履歴"),
    ("progress", "分析の経過"),
    ("files", "手元のファイル"),
)
# The headings of the note by anchor: the check before a hand-over names its
# rows of the method and the sources in them, so the two read alike.
SECTION_WORDS = dict(_SECTIONS)

# The words of the note that the check before a hand-over also names its rows
# by (ADR-0063 2): what the design means to do, what it counts (ADR-0066 5),
# and its figures.
INTENT_LABEL = "意図"
SCOPE_WORDS = {"population": "対象", "grain": "粒度", "denominator": "分母"}
FIGURES_HEADING = "図"


@dataclass(frozen=True)
class FormWords:
    """The words the reader sees for one form of design (ADR-0051).

    The note, the report and the question tree take them from here, so no two of
    them word a form differently.
    """

    statement: str  # what the design's first field is called
    background: str
    # (direction, heading) of each evidence group; () for a form that is not judged
    directed: tuple[tuple[str, str], ...]
    lead_sentences: Mapping[DesignStatus, str]  # one for each conclusion of the form


def _verdict_words(statement: str) -> FormWords:
    return FormWords(
        statement=statement,
        background="背景",
        directed=(
            ("supports", f"{statement}を支持する証拠"),
            ("contradicts", f"{statement}に反する証拠"),
        ),
        lead_sentences={
            DesignStatus.supported: f"{statement}は支持された。",
            DesignStatus.rejected: f"{statement}は棄却された。",
            DesignStatus.inconclusive: (
                f"{statement}を支持するとも棄却するとも結論できなかった。"
            ),
        },
    )


FORM_WORDS: Mapping[DesignForm, FormWords] = {
    DesignForm.exploration: FormWords(
        statement="探索の問い",
        background="背景",
        directed=(),
        lead_sentences={DesignStatus.explored: "探索を終えた。判定はしていない。"},
    ),
    DesignForm.confirmation: _verdict_words("検証仮説"),
    # A legacy exploration keeps the words it was written with (ADR-0049).
    DesignForm.legacy_exploration: _verdict_words("仮説"),
}

LEGACY_NOTE = "旧形式の探索: 探索の分析設計に、仮説と判定が書かれている。"

# The intent as the reader sees it, one word for each (intent, form) a design can
# hold; a saved mixed design reads as a confirmation (ADR-0049, ADR-0051).
_INTENT_WORDS: Mapping[tuple[AnalysisIntent, DesignForm], str] = {
    (AnalysisIntent.exploratory, DesignForm.exploration): "探索",
    (AnalysisIntent.confirmatory, DesignForm.confirmation): "検証",
    (AnalysisIntent.mixed, DesignForm.confirmation): "探索と検証（旧形式）",
    (AnalysisIntent.exploratory, DesignForm.legacy_exploration): "探索（旧形式）",
}

# The words of a status that are the same for every form (ADR-0051).
_STATUS_WORDS = {
    DesignStatus.in_review: "レビュー中",
    DesignStatus.revision_requested: "修正待ち",
    DesignStatus.analyzing: "分析中",
    DesignStatus.explored: "探索済み（判定はしない）",
}
_VERDICT_WORDS = {
    DesignStatus.supported: "支持",
    DesignStatus.rejected: "棄却",
    DesignStatus.inconclusive: "結論できず",
}


def intent_word(design: AnalysisDesign) -> str:
    """The intent as the reader sees it: one of four words (ADR-0051)."""
    return _INTENT_WORDS[design.analysis_intent, design.form()]


def intent_words_of(form: DesignForm) -> tuple[str, ...]:
    """Every intent word a design of *form* may be shown with; the first is its own."""
    return tuple(word for (_, f), word in _INTENT_WORDS.items() if f is form)


def direction_gloss(form: DesignForm, direction: str) -> str | None:
    """What a cited event's direction means for its design (ADR-0051).

    None when the form holds no hypothesis to lean on, or the direction is unknown.
    """
    headings = dict(FORM_WORDS[form].directed)
    if direction not in headings:
        return None
    return headings[direction].removesuffix("証拠")


def against_heading(form: DesignForm) -> str:
    """The heading of the evidence against the hypothesis of a judged *form*."""
    return dict(FORM_WORDS[form].directed)["contradicts"]


def status_word(form: DesignForm, status: DesignStatus) -> str:
    """The status as the reader sees it, worded by its role (ADR-0051)."""
    if status in _STATUS_WORDS:
        return _STATUS_WORDS[status]
    return f"{FORM_WORDS[form].statement}の判定: {_VERDICT_WORDS[status]}"


def lead_sentence(form: DesignForm, status: DesignStatus) -> str | None:
    """The fixed sentence a conclusion opens with; None before the design concludes.

    The note's conclusion and the report both take it from here.
    """
    return FORM_WORDS[form].lead_sentences.get(status)


def statement_of(design: AnalysisDesign) -> tuple[str, str]:
    """(statement, background) as the design holds them: its question or its hypothesis."""
    if not design.form().judges:
        return design.exploration_question or "", design.exploration_background or ""
    return design.hypothesis_statement or "", design.hypothesis_background or ""


def opening_heading(form: DesignForm) -> str:
    words = FORM_WORDS[form]
    return f"{words.statement}と{words.background}"


# The kinds of journal event (docs/UBIQUITOUS_LANGUAGE.md).
EVENT_WORDS = {
    "observe": "観察",
    "hypothesize": "仮説",
    "evidence": "証拠",
    "hearing": "人に聞いた答え",
    "question": "問い",
    "decide": "決定",
    "reflect": "振り返り",
    "conclude": "結論",
    "branch": "派生",
}


def note_anchor(design_id: str) -> str:
    return f"note-{design_id}"


def _cell(text: str) -> str:
    return text if text else _DASH


def _section(anchor: str, name: str, heading: str, *content: Html | None) -> Html:
    return el(
        "section",
        el("h3", heading),
        join(content),
        id=f"{anchor}-{name}",
    )


def _status(note: DesignNote, anchor: str, stage_line: str | None) -> Html:
    last = note.events[-1] if note.events else None
    if last is None:
        journal = "journal にまだ出来事が無い。"
    else:
        journal = f"載せた journal の最後の出来事の時刻: {last.created_at or '（時刻の記載なし）'}"
    verdict = "あり" if note.verdict is not None else "まだ無い"
    concluded = note.conclusion is not None
    design = note.design
    form = design.form()
    return el(
        "div",
        el("p", f"{INTENT_LABEL}: {intent_word(design)}"),
        el("p", LEGACY_NOTE) if form is DesignForm.legacy_exploration else None,
        el("p", f"状態: {status_word(form, design.status)}（{design.status.value}）"),
        None if stage_line is None else el("p", stage_line),
        el("p", journal),
        el("p", f"notebook の結果（verdict）: {verdict}"),
        None
        if concluded
        else el("p", "結論はまだ出ていない（分析設計が terminal status でない）。"),
        el(
            "ul",
            *(
                el(
                    "li",
                    el(
                        "a",
                        opening_heading(form) if name == _OPENING else label,
                        href=f"#{anchor}-{name}",
                    ),
                )
                for name, label in _SECTIONS
                if concluded or name != "conclusion"
            ),
        ),
        class_="status",
        id=f"{anchor}-status",
    )


def _opening(design: AnalysisDesign, anchor: str) -> Html:
    statement, background = statement_of(design)
    return _section(
        anchor,
        _OPENING,
        opening_heading(design.form()),
        el("p", statement) if statement else None,
        el("p", background) if background else None,
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


def _data_scope(design: AnalysisDesign) -> list[Html]:
    """What the analysis counts, next to how it counts it (ADR-0066 5)."""
    scope = design.data_scope
    if scope is None:
        return []
    return [
        el("p", f"{SCOPE_WORDS[field]}: {getattr(scope, field)}")
        for field in SCOPE_WORDS
    ]


def _method(design: AnalysisDesign, anchor: str) -> Html:
    scope = _data_scope(design)
    methodology = design.methodology
    if methodology is None:
        return _section(
            anchor, "method", "手法", *scope, el("p", "手法は書かれていない。")
        )
    steps = (methodology.model_extra or {}).get("steps")
    return _section(
        anchor,
        "method",
        "手法",
        *scope,
        el("p", f"手法: {methodology.method}"),
        el("p", f"パッケージ: {methodology.package}") if methodology.package else None,
        el("p", f"理由: {methodology.reason}") if methodology.reason else None,
        el("ol", *(el("li", str(step)) for step in steps))
        if isinstance(steps, list)
        else None,
    )


def _metric_definitions(design: AnalysisDesign, anchor: str) -> Html:
    body = (
        table(
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
        table(
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
        table(
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
    form = note.design.form()
    if not form.judges:
        # An exploration's evidence has no direction to group by (ADR-0050).
        groups = [(_ALL_EVIDENCE, evidence)]
    else:
        directed = FORM_WORDS[form].directed
        known = {direction for direction, _ in directed}
        groups = [
            (label, [e for e in evidence if e.direction == direction])
            for direction, label in directed
        ] + [(_NEUTRAL_GROUP, [e for e in evidence if e.direction not in known])]
    for label, members in groups:
        if members:
            blocks += [el("h4", label), _event_list(members)]
    return blocks


def _text(text: Text) -> str:
    """A cell or a heading; one that holds no text is a dash."""
    return "".join(text) or _DASH


def _title(text: Text) -> str:
    # The note dashes each empty name of a title, so "m（— × y）" keeps its axes.
    return "".join(p if isinstance(p, Fixed) else _cell(p) for p in text)


def _value_table(values: TextTable) -> list[Html]:
    return [
        *([] if values.title is None else [el("h5", _title(values.title))]),
        table(
            [_text(h) for h in values.headings],
            ([_text(c) for c in row] for row in values.rows),
        ),
    ]


def _metric_values(metrics: tuple[VerdictMetric, ...], form: DesignForm) -> list[Html]:
    if not metrics:
        return [el("h4", "指標の値"), el("p", "verdict に指標の値は無い。")]
    tables = metric_tables(metrics, form, sample_size="N", p="p")
    return [el("h4", "指標の値"), *(b for t in tables for b in _value_table(t))]


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
    return el("div", el("h4", FIGURES_HEADING), body, id=f"{anchor}-figures")


def _results(note: DesignNote, anchor: str) -> Html:
    return _section(
        anchor,
        "results",
        "結果",
        el("p", "notebook をまだ実行していない（verdict が無い）。")
        if note.verdict is None
        else None,
        join(_events(note)),
        join(_metric_values(note.verdict.metrics, note.design.form()))
        if note.verdict is not None
        else None,
        _figures(note, anchor),
    )


def _status_after(form: DesignForm, written: str) -> str:
    try:
        status = DesignStatus(written)
    except ValueError:
        return written
    return f"{status_word(form, status)}（{status.value}）"


def _reviews(note: DesignNote, anchor: str) -> Html:
    body = (
        join(
            review_batch(b, _status_after(note.design.form(), b.status_after))
            for b in note.reviews
        )
        if note.reviews
        else el("p", "review はまだ無い。")
    )
    return _section(
        anchor,
        "reviews",
        "レビュー",
        el(
            "p",
            "review batch を新しい順に出す。review コメントと対象は書かれたとおりに写す。",
        ),
        body,
    )


def _recommendation_sources(
    design: AnalysisDesign, conclusion: Conclusion
) -> list[Html]:
    context = design.decision_context
    lines = (
        []
        if context is None
        else [
            el("p", f"決める人: {context.decision_maker}"),
            el("p", f"決めること: {context.decision}"),
        ]
    ) + [
        el("p", f"next_action の {field}: {text}")
        for field, text in conclusion.next_action
    ]
    return [el("h4", "勧めの元"), *lines] if lines else []


def _records(heading: str, events: Sequence[NoteEvent]) -> list[Html]:
    return [el("h4", heading), _event_list(events)] if events else []


def _conclusion(note: DesignNote, anchor: str) -> Html | None:
    conclusion = note.conclusion
    if conclusion is None:
        return None
    form = note.design.form()
    return _section(
        anchor,
        "conclusion",
        "結論",
        el("p", lead_sentence(form, conclusion.status)),
        el(
            "p",
            "この節は journal と分析設計の記録を書かれたとおりに写す。"
            "conclude と reflect の本文は「分析の経過」にも在る。",
        ),
        *_records("conclude の本文", conclusion.conclude_events),
        *_recommendation_sources(note.design, conclusion),
        *(
            _records(against_heading(form), conclusion.contradicting_evidence)
            if form.judges
            else ()
        ),
        *_records("reflect の本文", conclusion.reflect_events),
        *_records("未解決の問い", conclusion.open_questions),
    )


def _cell_heading(cell: CodeCell) -> str:
    return (
        f"cell {cell.position} · {cell.name}" if cell.name else f"cell {cell.position}"
    )


def _code(note: DesignNote, anchor: str) -> Html:
    if note.cells is not None:
        body = join(
            [
                el(
                    "p",
                    "notebook の .py を cell ごとに、名前を添えて出す。"
                    "データ取得の cell は載せない（接続情報が入るため）。"
                    "手元の notebook の .py で読む。",
                ),
                *(
                    el(
                        "details",
                        el("summary", _cell_heading(c)),
                        el("pre", el("code", c.source)),
                    )
                    for c in note.cells
                ),
            ]
        )
    elif _NOTEBOOK_PY.format(id=note.design.id) in note.local_files:
        body = el(
            "p",
            "notebook が契約の形でなく、データ取得の cell を特定できないので、"
            "コードを1つも載せない。/analysis-notebook で作り直すと載る。"
            "手元の notebook の .py で読む。",
        )
    else:
        body = el("p", "notebook の .py はまだ無い。")
    return _section(anchor, "code", "分析コード", body)


def _lineage(note: DesignNote, anchor: str) -> Html:
    body = (
        el("p", "lineage はまだ無い。")
        if note.lineage is None
        else el(
            "details",
            el("summary", "lineage の Mermaid の文字"),
            el("pre", el("code", note.lineage)),
        )
    )
    return _section(anchor, "lineage", "データ加工の履歴", body)


def _verdict_conclusion(verdict: NoteVerdict | None) -> Html:
    if verdict is None:
        return el("p", "notebook をまだ実行していない（verdict が無い）。")
    if verdict.conclusion is None:
        return el("p", "verdict に conclusion は無い。")
    return el("p", f"notebook の結論（verdict の conclusion）: {verdict.conclusion}")


def _event_item(event: NoteEvent) -> Html:
    word = EVENT_WORDS.get(event.type, event.type)
    at = event.created_at or "（時刻の記載なし）"
    return el(
        "li",
        el("div", f"{at} {word} {event.id}", class_="meta"),
        el("div", event.content),
    )


def _progress(note: DesignNote, anchor: str) -> Html:
    events = (
        el(
            "details",
            el("summary", f"journal のすべての出来事（{len(note.events)} 件）"),
            el("ol", *(_event_item(e) for e in note.events), class_="events"),
        )
        if note.events
        else el("p", "journal にまだ出来事が無い。")
    )
    return _section(
        anchor,
        "progress",
        "分析の経過",
        el(
            "p",
            "分析中の判断と解釈の記録である。journal に書いた順（書いた時刻の順）に出す。",
        ),
        _verdict_conclusion(note.verdict),
        events,
    )


def _local_files(note: DesignNote, anchor: str) -> Html:
    present = [
        (label, path)
        for label, template in LOCAL_FILES
        if (path := template.format(id=note.design.id)) in note.local_files
    ]
    body = (
        join(
            [
                el(
                    "p",
                    "このリンクは、このページを手元で開いたときだけ開ける。"
                    "Artifact では開けない。",
                ),
                el(
                    "ul",
                    *(
                        el("li", el("a", f"{label}（{path}）", href=f"../{path}"))
                        for label, path in present
                    ),
                ),
            ]
        )
        if present
        else el("p", "手元のファイルはまだ無い。")
    )
    return _section(anchor, "files", "手元のファイル", body)


def render_note(note: DesignNote, stage_line: str | None = None) -> Html:
    """The note as one ``<section>``, ready to sit inside a page.

    *stage_line* goes under the status line. Its words belong to the tree page
    (``tree_words.note_stage_line``), which this module cannot import, so the
    caller hands the line in.
    """
    design = note.design
    anchor = note_anchor(design.id)
    return el(
        "section",
        el("h2", f"分析ノート {design.id} {design.title}"),
        _status(note, anchor, stage_line),
        _opening(design, anchor),
        _decision(design, anchor),
        _method(design, anchor),
        _metric_definitions(design, anchor),
        _explanatory(design, anchor),
        _sources(note, anchor),
        _results(note, anchor),
        _reviews(note, anchor),
        _conclusion(note, anchor),
        _code(note, anchor),
        _lineage(note, anchor),
        _progress(note, anchor),
        _local_files(note, anchor),
        class_="design-note",
        id=anchor,
    )


def render_note_page(note: DesignNote, stage_line: str | None = None) -> str:
    return page(
        f"分析ノート {note.design.id}",
        BASE_CSS + NOTE_CSS,
        render_note(note, stage_line),
    )
