"""Render a question tree as one self-contained HTML page (Epic 18, ADR-0024).

Pure: no I/O. ``tree_read.render`` (CLI: ``tree_io render``) reads the files
and hands the data in here.
The page has no script, no external resource and no timestamp, so the same
inputs give the same bytes. Interaction is ``<details>`` only.

Every string that reaches the page comes from analysts or models, so none of it
is trusted: see ``_html`` for how markup is told from text.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    DesignForm,
    DesignStatus,
)
from insight_blueprint.models.tree import (
    Aim,
    AimKind,
    Answer,
    AnswerStatement,
    Progress,
    QuestionNode,
    QuestionTree,
    StatementKind,
    TreeDecisionKind,
    design_id_of,
)
from skills._shared._html import BASE_CSS, Html, el, join, page
from skills._shared.design_io import design_number
from skills._shared.design_note import (
    FORM_WORDS,
    NOTE_CSS,
    DesignNote,
    direction_gloss,
    intent_word,
    intent_words_of,
    note_anchor,
    statement_of,
    status_word,
)
from skills._shared.design_note_reviews import (
    AFTER_ANALYSIS,
    comments_after_analysis,
)

if TYPE_CHECKING:  # tree_check imports this module (CitedEvent)
    from skills._shared.tree_check import Violation


@dataclass(frozen=True)
class DesignSummary:
    id: str
    title: str
    status: DesignStatus
    parent_id: str | None
    created_at: datetime
    form: DesignForm
    intent: str  # intent_word: a saved mixed design has its own word
    statement: str  # the question of an exploration, else the hypothesis
    comments_after_analysis: int = 0  # review comments of the result review

    @classmethod
    def of(cls, note: DesignNote) -> DesignSummary:
        """The words come from design_note, as the note's do (ADR-0051)."""
        design = note.design
        return cls(
            design.id,
            design.title,
            design.status,
            design.parent_id,
            design.created_at,
            form=design.form(),
            intent=intent_word(design),
            statement=statement_of(design)[0],
            comments_after_analysis=comments_after_analysis(note.reviews),
        )


@dataclass(frozen=True)
class CitedEvent:
    id: str
    type: str
    direction: str | None
    content: str


@dataclass(frozen=True)
class CheckFailed:
    """The cited-answer check could not run, so no answer is known to be sound."""

    message: str


_TREE_CSS = """.legend { background: var(--panel); border: 1px solid var(--line); padding: .5rem 1rem; }
.tree, .tree ul, .derivation, .derivation ul {
  list-style: none; margin: 0; padding-left: 1.25rem;
  border-left: 1px solid var(--line);
}
.tree { padding-left: 0; border-left: 0; }
.derivation { padding-left: 0; border-left: 0; }
.tree li, .derivation li { margin: .6rem 0; }
.node, .design {
  background: var(--panel); border: 1px solid var(--line); border-left-width: 6px;
  padding: .4rem .7rem; overflow-wrap: anywhere;
}
.progress-not_started { border-left-color: var(--not-started); }
.progress-investigating { border-left-color: var(--investigating); }
.progress-analyzed { border-left-color: var(--analyzed); }
.progress { font-weight: 700; }
.mark { color: var(--mark); font-weight: 700; margin-right: .6rem; }
.statements { margin: .3rem 0; padding-left: 1.2rem; }
.kind { font-weight: 700; }
.notice { border: 1px solid var(--investigating); padding: .4rem .8rem; }
.notes { margin: .3rem 0; padding-left: 1.2rem; }
.design-note { scroll-margin-top: 4rem; }
.branch {
  background: var(--panel); border: 1px dashed var(--line);
  padding: .4rem .7rem; overflow-wrap: anywhere;
}
.form-tag { font-weight: 700; margin-right: .4rem; }
.answer-heading { color: var(--muted); font-size: .9rem; margin-bottom: 0; }
.legend table { border-collapse: collapse; margin: .3rem 0; }
.legend th, .legend td { border: 1px solid var(--line); padding: .2rem .5rem; text-align: left; }
"""

_AIM_LABELS = {
    AimKind.business: (
        ("決める人", "decision_maker"),
        ("決めること", "decision"),
    ),
    AimKind.research: (
        ("想定読者", "audience"),
        ("主張の範囲", "claim_scope"),
    ),
}


class Mark(StrEnum):
    """What a reader must notice about the current answer of a node."""

    changed = "changed"
    first = "first"
    before_root_change = "before_root_change"
    violating = "violating"


# Each table holds the word shown on the page and what the legend says it means,
# so the legend cannot drift from the page.
PROGRESS_WORDS = {
    Progress.not_started: ("未着手", "分析設計を結んでいない。"),
    Progress.investigating: ("検証中", "結んだ分析設計に、終わっていないものがある。"),
    Progress.analyzed: ("分析済み", "結んだ分析設計がすべて終わっている。"),
}

# The words shown to the analyst are not the glossary's terms (ADR-0055): the
# kinds keep their YAML values, the page says what each one tells the analyst.
_KIND_WORDS = {
    StatementKind.claim: (
        "これまでわかっていること",
        "根拠にした分析結果から言えること。",
    ),
    StatementKind.undetermined: (
        "まだ決められないこと",
        "分析をしても、分析結果からは決められないこと。",
    ),
    StatementKind.weakening: (
        "注意すべきこと",
        "これまでわかっていることを弱める分析結果や、言える範囲の限定。",
    ),
}

# "{round}" is the round of the answer on a page and "N" in the legend.
_MARK_WORDS = {
    Mark.changed: (
        "回 {round} で変わった",
        "最も新しい振り返りの回（N）で、前の回から書き換わった答え。",
    ),
    Mark.first: (
        "回 {round} で初めて答えた",
        "最も新しい振り返りの回（N）で、初めて書いた答え。",
    ),
    Mark.before_root_change: (
        "見直す前の主題への答え",
        "主題か到達点を見直す前の、古い主題の版に対して書いた答え。",
    ),
    Mark.violating: (
        "記録と合わない答え",
        "引用した出来事が journal に無い、結んでいない分析設計の出来事を引いている、"
        "引用に無い数字を書いている、のどれかの答え。答えの文は閉じた中に畳む。",
    ),
}

_VIOLATION_WORDS = {
    "missing-event": "journal に無い出来事",
    "unlinked-design": "この論点に結んでいない分析設計の出来事",
    "number-not-cited": "引用した出来事に無い数字",
}

_DECISION_LABELS = {
    TreeDecisionKind.start: "最初の論点を選ぶ",
    TreeDecisionKind.deepen: "深める",
    TreeDecisionKind.return_: "親に戻る",
    TreeDecisionKind.close: "区切る",
}

_NOTE_LABELS = (
    ("ask", "人に聞く問い"),
    ("changes_if", "その答えで変わる判断"),
    ("known", "分かっていること"),
)


def render_tree_html(
    tree: QuestionTree,
    designs: Mapping[str, DesignSummary],
    events: Mapping[str, CitedEvent],
    violations: Sequence[Violation] | CheckFailed,
    design_notes: Mapping[str, Html],
) -> str:
    """The page. *design_notes* maps a design id to the markup ``render_note`` returned."""
    context = _Context.of(tree, designs, events, violations, design_notes)
    body = join(
        [
            _header(tree),
            _check_notice(violations),
            _legend(),
            _counts(context),
            _decisions(tree),
            _next_candidates(context),
            _question_tree(context),
            _derivation(context),
            _design_notes(context),
        ]
    )
    return page(f"論点ツリー {tree.theme_id}", BASE_CSS + _TREE_CSS + NOTE_CSS, body)


def _header(tree: QuestionTree) -> Html:
    revision = tree.current_revision()
    parts = [
        el("h1", f"論点ツリー {tree.theme_id}"),
        el("p", el("strong", "主題: "), revision.question),
        *(el("p", line) for line in _aim_lines(revision.aim)),
        el("p", f"主題の版 {revision.revision}", class_="meta"),
    ]
    if len(tree.root_revisions) > 1:
        parts.append(_root_history(tree))
    return el("header", join(parts), id="header")


def _aim_lines(aim: Aim) -> list[str]:
    return [f"{label}: {getattr(aim, field)}" for label, field in _AIM_LABELS[aim.kind]]


def _root_history(tree: QuestionTree) -> Html:
    rows = []
    for revision in tree.root_revisions:
        aim = "、".join(_aim_lines(revision.aim))
        rows.append(
            el(
                "li",
                f"主題の版 {revision.revision}: {revision.question}（{aim}）",
                f" 理由: {revision.reason}" if revision.reason else "",
            )
        )
    return el(
        "details",
        el("summary", "主題の版の履歴"),
        el("ul", join(rows)),
        id="root-history",
    )


def _word_list(words: Iterable[tuple[str, str]]) -> Html:
    return el("ul", join(el("li", f"{word}: {meaning}") for word, meaning in words))


def _legend() -> Html:
    return el(
        "section",
        el("h2", "読み方"),
        el(
            "p",
            "進捗は、論点に結んだ分析設計の状態から導いた言葉。色は添えただけで、"
            "意味は言葉が持つ。",
        ),
        _word_list(PROGRESS_WORDS.values()),
        el("p", "現時点の答えは、文ごとに種類の言葉を付けて並べる。"),
        _word_list(_KIND_WORDS.values()),
        el("p", "答えの上に出す印。"),
        _word_list(
            (word.format(round="N"), meaning) for word, meaning in _MARK_WORDS.values()
        ),
        el(
            "p",
            f"文の後ろの「{_HEARD_WORD}」は、引用した出来事がすべて人に聞いた答え"
            "（hearing）で、データの出来事が1つも無い文に付ける。",
        ),
        el("p", "まだ分析設計を結んでいない論点は「次の候補」に並べる。"),
        el(
            "p",
            "論点の下には、その論点に結んだ分析設計を、子の論点より先に並べる。"
            "分析設計のカードは破線の枠で、「分析設計・」と意図の言葉で始まる。"
            "同じ分析設計を2つ目の論点からは、id、状態の言葉、最初に出た論点への"
            "リンクだけの短い行で出す。",
        ),
        el(
            "p",
            "分析設計の状態は、次の言葉で出す。判定は分析設計の検証仮説（旧形式では"
            "仮説）に対するもので、論点の答えではない。論点の答えは、論点のカードの"
            "「現時点の答え」に書く。",
        ),
        _status_table(),
        el(
            "p",
            "各論点の「根拠を開く」を押すと、引用した journal の出来事と、前の回の答えが開く。",
        ),
        el("p", "論点の親子と分析設計の派生は別の構造なので、2つの節に分けて並べる。"),
        el(
            "p",
            "「分析ノートを開く」は、その分析設計の分析ノートへ飛ぶ。分析ノートはこの"
            "ページの下に、分析設計ごとに並べてある。分析ノートの冒頭と末尾の"
            "「論点ツリーへ戻る」で、論点ツリーの節へ戻る。",
        ),
        class_="legend",
        id="legend",
    )


def _status_rows() -> list[tuple[str, DesignStatus, list[str]]]:
    """(word, YAML value, intent words) for each status a form can take."""
    rows: dict[str, tuple[DesignStatus, list[str]]] = {}
    for status in DesignStatus:
        for form in DesignForm:
            if not form.allows(status):
                continue
            word = status_word(form, status)
            rows.setdefault(word, (status, []))[1].extend(intent_words_of(form))
    return [(word, status, intents) for word, (status, intents) in rows.items()]


def _status_table() -> Html:
    head = el("tr", join(el("th", h) for h in ("表示の言葉", "YAML の status", "意図")))
    body = join(
        el("tr", el("td", word), el("td", status.value), el("td", "、".join(intents)))
        for word, status, intents in _status_rows()
    )
    return el("table", el("thead", head), el("tbody", body), id="status-words")


@dataclass(frozen=True)
class _Context:
    """The inputs of a page and the facts derived from them, computed once."""

    tree: QuestionTree
    designs: Mapping[str, DesignSummary]
    events: Mapping[str, CitedEvent]
    design_notes: Mapping[str, Html]
    progress: Mapping[str, Progress]
    violations: Mapping[str, Sequence[Violation]]
    # Node ids that link a design, in page order: the first one shows its card.
    linked_by: Mapping[str, list[str]]
    children: Mapping[str | None, list[QuestionNode]]

    @classmethod
    def of(
        cls,
        tree: QuestionTree,
        designs: Mapping[str, DesignSummary],
        events: Mapping[str, CitedEvent],
        checked: Sequence[Violation] | CheckFailed,
        design_notes: Mapping[str, Html],
    ) -> _Context:
        for node in tree.nodes:
            for design_id in node.design_ids:
                if design_id not in designs:
                    raise ValueError(
                        f"design '{design_id}' is linked to {node.id} but not given"
                    )
        # Every anchor to a note needs its target, so a missing note stops the page.
        for design_id in designs:
            if design_id not in design_notes:
                raise ValueError(f"design '{design_id}' has no analysis note")
        progress = {
            node.id: Progress.of(designs[d].status for d in node.design_ids)
            for node in tree.nodes
        }
        violations: dict[str, list[Violation]] = {}
        for violation in () if isinstance(checked, CheckFailed) else checked:
            violations.setdefault(violation.node_id, []).append(violation)
        children: dict[str | None, list[QuestionNode]] = {}
        for node in tree.nodes:
            children.setdefault(node.parent_question_id, []).append(node)
        linked_by: dict[str, list[str]] = {}
        for node in _page_order(tree.root(), children):
            for design_id in node.design_ids:
                linked_by.setdefault(design_id, []).append(node.id)
        return cls(
            tree,
            designs,
            events,
            design_notes,
            progress,
            violations,
            linked_by,
            children,
        )

    def marks_of(self, node: QuestionNode) -> list[Mark]:
        answer = node.current_answer()
        if answer is None:
            return []
        marks: list[Mark] = []
        if node.id in self.violations:
            marks.append(Mark.violating)
        elif answer.round == self.tree.current_round():
            if len(node.answers) == 1:
                marks.append(Mark.first)
            elif answer.statements != node.answers[-2].statements:
                marks.append(Mark.changed)
        if answer.root_revision < self.tree.current_revision().revision:
            marks.append(Mark.before_root_change)
        return marks


def _page_order(
    root: QuestionNode, children: Mapping[str | None, list[QuestionNode]]
) -> list[QuestionNode]:
    """The nodes as the tree section lists them: each before its children."""
    ordered: list[QuestionNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        ordered.append(node)
        stack.extend(reversed(children.get(node.id, [])))
    return ordered


def _link(target: str, label: str) -> Html:
    return el("a", label, href=f"#{target}")


def _id_key(design_id: str) -> tuple[int, str]:
    """Order by the number after ``-H``: ``H10`` follows ``H9``."""
    number = design_number(design_id)
    return (-1 if number is None else number, design_id)


def _newest_first(group: list[DesignSummary]) -> list[DesignSummary]:
    naive = [d for d in group if d.created_at.tzinfo is None]
    if naive and len(naive) != len(group):
        aware = next(d for d in group if d.created_at.tzinfo is not None)
        # Which zone a bare time means is unknowable, so no order is guessed.
        raise ValueError(
            f"created_at of '{naive[0].id}' has no time zone but that of "
            f"'{aware.id}' has one: they cannot be ordered"
        )
    return sorted(group, key=lambda d: (d.created_at, _id_key(d.id)), reverse=True)


def _card_order(designs: list[DesignSummary]) -> list[DesignSummary]:
    """Unfinished designs first, then finished ones; the newest first in each."""
    finished = [d for d in designs if d.status in TERMINAL_STATUSES]
    unfinished = [d for d in designs if d not in finished]
    return _newest_first(unfinished) + _newest_first(finished)


def _note_link(design_id: str) -> Html:
    return _link(note_anchor(design_id), "分析ノートを開く")


def _counts(context: _Context) -> Html:
    found = Counter(context.progress.values())
    return el(
        "section",
        el("h2", "進捗の数"),
        el(
            "p",
            join(
                el("span", f"{PROGRESS_WORDS[p][0]} {found[p]}", class_="count")
                for p in Progress
            ),
        ),
        id="counts",
    )


def _decisions(tree: QuestionTree) -> Html:
    rows = [
        el(
            "li",
            _DECISION_LABELS[d.kind],
            None
            if d.kind is TreeDecisionKind.start
            else (
                "（振り返りの前）"
                if d.round == 0
                else f"（回 {d.round} の振り返りの後）"
            ),
            ": ",
            _link(d.node_id, d.node_id),
            f" {d.reason}",
        )
        for d in tree.decisions
    ]
    body = el("ul", join(rows)) if rows else el("p", "まだ決めていない。")
    return el("section", el("h2", "ツリーの決定"), body, id="decisions")


def _check_notice(violations: Sequence[Violation] | CheckFailed) -> Html | None:
    if not isinstance(violations, CheckFailed):
        return None
    return el(
        "p",
        f"答えを記録と照らして確かめられなかった（{violations.message}）。"
        "答えが記録と合うかは確かめていない。",
        class_="notice",
        id="check-notice",
    )


def _notes(node: QuestionNode) -> Html | None:
    note = node.next_candidate
    if note is None:
        return None
    rows = [
        el("li", f"{label}: {getattr(note, field)}")
        for field, label in _NOTE_LABELS
        if getattr(note, field)
    ]
    if note.answer:
        rows.append(
            el(
                "li",
                f"聞いてきた答え: {note.answer}"
                f"（{note.answered_by}、{note.answered_at}）",
            )
        )
    return el("ul", join(rows), class_="notes")


def _next_candidates(context: _Context) -> Html:
    items = [
        el(
            "li",
            el("strong", _link(node.id, node.id)),
            f" {node.question}",
            _notes(node) or el("p", "まだメモは無い。", class_="note"),
        )
        for node in context.tree.untouched_nodes()
    ]
    return el(
        "section",
        el("h2", "次の候補"),
        el(
            "p",
            "分析設計をまだ結んでいない論点。人に聞く問いと、聞いてきた答えを添える。",
            class_="note",
        ),
        el("ul", join(items)) if items else el("p", "着手していない論点は無い。"),
        id="next-candidates",
    )


def _question_tree(context: _Context) -> Html:
    tree = context.tree

    def branch(node: QuestionNode) -> Html:
        designs = [
            el("li", _design_card(context, node, design))
            for design in _card_order([context.designs[d] for d in node.design_ids])
        ]
        below = [branch(c) for c in context.children.get(node.id, [])]
        items = designs + below
        return el(
            "li",
            _node_card(context, node),
            el("ul", join(items)) if items else None,
            id=node.id,
        )

    return el(
        "section",
        el("h2", "論点ツリー"),
        el("ul", branch(tree.root()), class_="tree"),
        id="question-tree",
    )


def _comments_after_analysis(count: int) -> list[str]:
    """The count of the result review's comments; nothing when there is none."""
    return [f"{AFTER_ANALYSIS} コメント: {count} 件", "　"] if count else []


def _design_card(context: _Context, node: QuestionNode, design: DesignSummary) -> Html:
    """The full card under the first node on the page; a short row under the others."""
    word = status_word(design.form, design.status)
    first = context.linked_by[design.id][0]
    if first != node.id:
        return el(
            "div",
            el(
                "p",
                el("strong", design.id),
                f"　{word}　",
                _link(first, f"{first} の下に出ている"),
                class_="meta",
            ),
            class_=f"branch form-{design.form.value}",
        )
    statement = FORM_WORDS[design.form].statement
    return el(
        "div",
        el(
            "p",
            el("span", f"分析設計・{design.intent}", class_="form-tag"),
            el("strong", _link(f"design-{design.id}", design.id)),
            f" {design.title}",
        ),
        el("p", f"{statement}: {design.statement}") if design.statement else None,
        el(
            "p",
            word,
            "　",
            *_comments_after_analysis(design.comments_after_analysis),
            _note_link(design.id),
            class_="meta",
        ),
        class_=f"branch form-{design.form.value}",
    )


def _node_card(context: _Context, node: QuestionNode) -> Html:
    progress = context.progress[node.id]
    meta: list[Html | str] = [
        "進捗: ",
        el("span", PROGRESS_WORDS[progress][0], class_="progress"),
    ]
    if node.parent_question_id is not None:
        meta.append(f"　寄与: {node.contribution}")
    if node.origin_event_id is not None:
        meta.append(f"　発見元: {node.origin_event_id}")
    answer = node.current_answer()
    violated = context.violations.get(node.id, ())
    parts: list[Html | None] = [
        el("p", el("strong", node.id), f" {node.question}"),
        el("p", *meta, class_="meta"),
    ]
    if answer is None:
        parts.append(el("p", "まだ答えていない"))
    else:
        marks = [
            el("span", _mark_text(mark, answer), class_="mark")
            for mark in context.marks_of(node)
        ]
        if marks:
            parts.append(el("p", *marks))
        if not violated:
            parts.append(el("p", "現時点の答え", class_="answer-heading"))
            parts.append(
                el(
                    "ul",
                    join(
                        _statement(s, *_heard_word(context, s))
                        for s in answer.statements
                    ),
                    class_="statements",
                )
            )
        parts.append(_round_meta(answer))
    parts += [_notes(node), _evidence(context, node, violated)]
    return el("div", join(parts), class_=f"node progress-{progress.value}")


def _mark_text(mark: Mark, answer: Answer) -> str:
    word = _MARK_WORDS[mark][0].format(round=answer.round)
    if mark is Mark.before_root_change:
        return f"{word}（主題の版 {answer.root_revision} への答え）"
    return word


def _statement(statement: AnswerStatement, *tail: str) -> Html:
    return el(
        "li",
        el("span", _KIND_WORDS[statement.kind][0], class_="kind"),
        f" {statement.text}",
        *tail,
    )


_HEARD_WORD = "（人に聞いた答えによる）"


def _heard_word(context: _Context, statement: AnswerStatement) -> tuple[str, ...]:
    """The word for a statement whose every cited event is what a person said.

    The check counts a number in a hearing event as recorded, so the page is
    where a reader sees that no event of the data stands behind the statement.
    """
    cited = [context.events.get(cite) for cite in statement.cites]
    if all(event is not None and event.type == "hearing" for event in cited):
        return (f" {_HEARD_WORD}",)
    return ()


def _round_meta(answer: Answer) -> Html:
    return el(
        "p",
        f"振り返りの回 {answer.round}（主題の版 {answer.root_revision}）",
        class_="meta",
    )


def _evidence(
    context: _Context, node: QuestionNode, violated: Sequence[Violation]
) -> Html:
    answer = node.current_answer()
    sections: list[Html] = []
    if answer is not None:
        if violated:
            sections += [
                el("h4", "記録と合わない点"),
                el(
                    "ul",
                    join(_violation(v) for v in violated),
                ),
                el(
                    "details",
                    el("summary", "記録と合わなかった答えの文"),
                    _cited_statements(context, answer),
                ),
            ]
        else:
            sections += [
                el("h4", "現時点の答えの根拠"),
                _cited_statements(context, answer),
            ]
        earlier = list(reversed(node.answers[:-1]))
        if earlier:
            sections.append(el("h4", "前の回の答え"))
            sections += [_earlier_answer(a) for a in earlier]
    if not sections:
        sections.append(el("p", "まだ根拠は無い。"))
    return el("details", el("summary", f"{node.id} の根拠を開く"), join(sections))


def _violation(violation: Violation) -> Html:
    word = _VIOLATION_WORDS[violation.kind]
    return el(
        "li",
        f"文 {violation.statement}: {word}（{violation.kind}）",
        el("blockquote", violation.text),
    )


def _cited_statements(context: _Context, answer: Answer) -> Html:
    return el(
        "ul",
        join(
            _statement(s, el("ul", join(_cited_event(context, c) for c in s.cites)))
            for s in answer.statements
        ),
    )


def _cited_event(context: _Context, event_id: str) -> Html:
    event = context.events.get(event_id)
    if event is None:
        return el("li", f"journal に見つからない出来事 {event_id}")
    design_id = design_id_of(event_id)
    parts: list[Html | str] = [
        el("strong", event_id),
        " design: ",
        _link(f"design-{design_id}", design_id),
    ]
    if event.type:
        parts.append(f" type: {event.type}")
    design = context.designs.get(design_id)
    form = None if design is None else design.form
    # An exploration holds no hypothesis, so no direction leans on one (ADR-0051).
    if event.direction and (form is None or form.judges):
        gloss = None if form is None else direction_gloss(form, event.direction)
        parts.append(
            f" direction: {event.direction}" + (f"（{gloss}）" if gloss else "")
        )
    parts.append(el("blockquote", event.content))
    return el("li", *parts)


def _earlier_answer(answer: Answer) -> Html:
    return el(
        "div",
        _round_meta(answer),
        el(
            "ul",
            join(
                _statement(s, f"（引用: {', '.join(s.cites)}）")
                for s in answer.statements
            ),
        ),
    )


def _derivation(context: _Context) -> Html:
    designs = context.designs
    children: dict[str, list[str]] = {}
    for design in designs.values():
        if design.parent_id in designs:
            children.setdefault(design.parent_id, []).append(design.id)
    shown: set[str] = set()

    def branch(design_id: str) -> Html:
        shown.add(design_id)
        design = designs[design_id]
        nodes = context.linked_by.get(design_id, [])
        facts: list[Html | str] = [
            f"{status_word(design.form, design.status)}　",
            # A linked design shows its count on its card; one linked to no node has
            # no card, so its count goes here. Each count is on the page once.
            *(
                []
                if nodes
                else _comments_after_analysis(design.comments_after_analysis)
            ),
            _note_link(design_id),
            "　",
        ]
        facts += (
            ["結んだ論点: ", *(_join_links(nodes))] if nodes else ["論点に結んでいない"]
        )
        if design.parent_id is not None and design.parent_id not in designs:
            facts.append(f"　派生元: {design.parent_id}")
        below = [
            c
            for c in sorted(children.get(design_id, []), key=_id_key)
            if c not in shown
        ]
        return el(
            "li",
            el(
                "div",
                el("p", el("strong", design.id), f" {design.title}"),
                el("p", *facts, class_="meta"),
                class_="design",
            ),
            el("ul", join(branch(c) for c in below)) if below else None,
            id=f"design-{design_id}",
        )

    top = [
        d for d in sorted(designs, key=_id_key) if designs[d].parent_id not in designs
    ]
    items = [branch(d) for d in top]
    # A cycle of parents has no top-level design; show its members anyway.
    items += [branch(d) for d in sorted(designs, key=_id_key) if d not in shown]
    body = (
        el("ul", join(items), class_="derivation")
        if items
        else el("p", "分析設計はまだ無い。")
    )
    return el(
        "section",
        el("h2", "分析設計の派生"),
        el(
            "p",
            "分析設計の parent_id で辿る親子。論点の親子とは別の構造。",
            class_="note",
        ),
        body,
        id="derivation",
    )


def _join_links(node_ids: list[str]) -> list[Html | str]:
    parts: list[Html | str] = []
    for position, node_id in enumerate(node_ids):
        if position:
            parts.append("、")
        parts.append(_link(node_id, node_id))
    return parts


def _back_links(context: _Context, design_id: str) -> Html:
    nodes = context.linked_by.get(design_id, [])
    parts: list[Html | str] = [_link("question-tree", "論点ツリーへ戻る")]
    if nodes:
        parts += ["　結んだ論点: ", *_join_links(nodes)]
    return el("p", *parts, class_="meta")


def _design_notes(context: _Context) -> Html:
    # The back link sits above and below a note: the note is long, so the way
    # back must be in reach from both ends.
    blocks = [
        join(
            [
                _back_links(context, design_id),
                context.design_notes[design_id],
                _back_links(context, design_id),
            ]
        )
        for design_id in sorted(context.designs, key=_id_key)
    ]
    return el(
        "section",
        el("h2", "分析設計ごとの分析ノート"),
        join(blocks) if blocks else el("p", "分析ノートはまだ無い。"),
        id="design-notes",
    )
