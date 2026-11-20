"""Render a question tree as one self-contained HTML page (Epic 18, ADR-0024).

Pure: no I/O. ``tree_io render`` reads the files and hands the data in here.
The page has no script, no external resource and no timestamp, so the same
inputs give the same bytes. Interaction is ``<details>`` only.

Every string that reaches the page comes from analysts or models, so none of it
is trusted. ``_el`` escapes each plain ``str`` it is given; only an ``_Html``
value, which only ``_el`` and the constants of this module produce, goes in
as markup.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from typing import TYPE_CHECKING

from insight_blueprint.models.design import DesignStatus
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

if TYPE_CHECKING:  # tree_check imports tree_io, which imports this module
    from skills._shared.tree_check import Violation


@dataclass(frozen=True)
class DesignSummary:
    id: str
    title: str
    status: str
    parent_id: str | None


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


class _Html(str):
    """Markup that is already safe to place in the page."""


def _el(tag: str, *children: str | None, **attrs: str | None) -> _Html:
    """Build ``<tag>``; a plain ``str`` child or attribute value is escaped.

    A ``None`` child or attribute is left out.
    """
    rendered = "".join(
        f' {name.rstrip("_")}="{escape(value, quote=True)}"'
        for name, value in attrs.items()
        if value is not None
    )
    inner = "".join(
        child if isinstance(child, _Html) else escape(child, quote=True)
        for child in children
        if child is not None
    )
    return _Html(f"<{tag}{rendered}>{inner}</{tag}>")


def _join(blocks: Iterable[_Html | None]) -> _Html:
    return _Html("\n".join(b for b in blocks if b is not None))


_CSS = """
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
.legend { background: var(--panel); border: 1px solid var(--line); padding: .5rem 1rem; }
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
_PROGRESS_WORDS = {
    Progress.not_started: ("未着手", "分析設計を結んでいない。"),
    Progress.investigating: ("検証中", "結んだ分析設計に、終わっていないものがある。"),
    Progress.analyzed: ("分析済み", "結んだ分析設計がすべて終わっている。"),
}

_KIND_WORDS = {
    StatementKind.claim: ("言えること", "引用する出来事が支える主張。"),
    StatementKind.undetermined: ("未判別", "記録からは決められないこと。"),
    StatementKind.weakening: (
        "弱める証拠と留保",
        "主張を弱める証拠や、言える範囲の限定。",
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
        "根の変更前の答え",
        "根の問いか到達点が変わる前の根の版に対して書いた答え。",
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

_DIRECTION_GLOSSES = {
    "supports": "仮説を支持する",
    "contradicts": "仮説に反する",
}


def render_tree_html(
    tree: QuestionTree,
    designs: Mapping[str, DesignSummary],
    events: Mapping[str, CitedEvent],
    violations: Sequence[Violation] | CheckFailed = (),
) -> str:
    title = f"論点ツリー {tree.theme_id}"
    head = _el(
        "head",
        _Html('<meta charset="utf-8">'),
        _Html('<meta name="viewport" content="width=device-width, initial-scale=1">'),
        _el("title", title),
        _el("style", _Html(_CSS)),
    )
    context = _Context.of(tree, designs, events, violations)
    body = _el(
        "body",
        _join(
            [
                _header(tree),
                _check_notice(violations),
                _legend(),
                _counts(context),
                _decisions(tree),
                _next_candidates(context),
                _question_tree(context),
                _derivation(context),
            ]
        ),
    )
    return "<!doctype html>\n" + _el("html", head, body, lang="ja") + "\n"


def _header(tree: QuestionTree) -> _Html:
    revision = tree.current_revision()
    parts = [
        _el("h1", f"論点ツリー {tree.theme_id}"),
        _el("p", _el("strong", "根の問い: "), revision.question),
        *(_el("p", line) for line in _aim_lines(revision.aim)),
        _el("p", f"根の版 {revision.revision}", class_="meta"),
    ]
    if len(tree.root_revisions) > 1:
        parts.append(_root_history(tree))
    return _el("header", _join(parts), id="header")


def _aim_lines(aim: Aim) -> list[str]:
    return [f"{label}: {getattr(aim, field)}" for label, field in _AIM_LABELS[aim.kind]]


def _root_history(tree: QuestionTree) -> _Html:
    rows = []
    for revision in tree.root_revisions:
        aim = "、".join(_aim_lines(revision.aim))
        rows.append(
            _el(
                "li",
                f"根の版 {revision.revision}: {revision.question}（{aim}）",
                f" 理由: {revision.reason}" if revision.reason else "",
            )
        )
    return _el(
        "details",
        _el("summary", "根の版の履歴"),
        _el("ul", _join(rows)),
        id="root-history",
    )


def _word_list(words: Iterable[tuple[str, str]]) -> _Html:
    return _el("ul", _join(_el("li", f"{word}: {meaning}") for word, meaning in words))


def _legend() -> _Html:
    return _el(
        "section",
        _el("h2", "読み方"),
        _el(
            "p",
            "進捗は、論点に結んだ分析設計の状態から導いた言葉。色は添えただけで、"
            "意味は言葉が持つ。",
        ),
        _word_list(_PROGRESS_WORDS.values()),
        _el("p", "現時点の答えは、文ごとに種類の言葉を付けて並べる。"),
        _word_list(_KIND_WORDS.values()),
        _el("p", "答えの上に出す印。"),
        _word_list(
            (word.format(round="N"), meaning) for word, meaning in _MARK_WORDS.values()
        ),
        _el("p", "まだ分析設計を結んでいない論点は「次の候補」に並べる。"),
        _el(
            "p",
            "各論点の「根拠を開く」を押すと、引用した journal の出来事、前の回の答え、"
            "結んだ分析設計が開く。",
        ),
        _el("p", "論点の親子と分析設計の派生は別の構造なので、2つの節に分けて並べる。"),
        class_="legend",
        id="legend",
    )


@dataclass(frozen=True)
class _Context:
    """The inputs of a page and the facts derived from them, computed once."""

    tree: QuestionTree
    designs: Mapping[str, DesignSummary]
    events: Mapping[str, CitedEvent]
    progress: Mapping[str, Progress]
    violations: Mapping[str, Sequence[Violation]]

    @classmethod
    def of(
        cls,
        tree: QuestionTree,
        designs: Mapping[str, DesignSummary],
        events: Mapping[str, CitedEvent],
        checked: Sequence[Violation] | CheckFailed,
    ) -> _Context:
        for node in tree.nodes:
            for design_id in node.design_ids:
                if design_id not in designs:
                    raise ValueError(
                        f"design '{design_id}' is linked to {node.id} but not given"
                    )
        progress = {
            node.id: Progress.of(
                DesignStatus(designs[d].status) for d in node.design_ids
            )
            for node in tree.nodes
        }
        violations: dict[str, list[Violation]] = {}
        for violation in () if isinstance(checked, CheckFailed) else checked:
            violations.setdefault(violation.node_id, []).append(violation)
        return cls(tree, designs, events, progress, violations)

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


def _link(target: str, label: str) -> _Html:
    return _el("a", label, href=f"#{target}")


def _counts(context: _Context) -> _Html:
    found = Counter(context.progress.values())
    return _el(
        "section",
        _el("h2", "進捗の数"),
        _el(
            "p",
            _join(
                _el("span", f"{_PROGRESS_WORDS[p][0]} {found[p]}", class_="count")
                for p in Progress
            ),
        ),
        id="counts",
    )


def _decisions(tree: QuestionTree) -> _Html:
    rows = [
        _el(
            "li",
            _DECISION_LABELS[d.kind],
            None
            if d.kind is TreeDecisionKind.start
            else f"（回 {d.round} の答えを見て）",
            ": ",
            _link(d.node_id, d.node_id),
            f" {d.reason}",
        )
        for d in tree.decisions
    ]
    body = _el("ul", _join(rows)) if rows else _el("p", "まだ決めていない。")
    return _el("section", _el("h2", "ツリーの決定"), body, id="decisions")


def _check_notice(violations: Sequence[Violation] | CheckFailed) -> _Html | None:
    if not isinstance(violations, CheckFailed):
        return None
    return _el(
        "p",
        f"答えを記録と照らして確かめられなかった（{violations.message}）。"
        "答えが記録と合うかは確かめていない。",
        class_="notice",
        id="check-notice",
    )


def _notes(node: QuestionNode) -> _Html | None:
    note = node.next_candidate
    if note is None:
        return None
    rows = [
        _el("li", f"{label}: {getattr(note, field)}")
        for field, label in _NOTE_LABELS
        if getattr(note, field)
    ]
    if note.answer:
        rows.append(
            _el(
                "li",
                f"聞いてきた答え: {note.answer}"
                f"（{note.answered_by}、{note.answered_at}）",
            )
        )
    return _el("ul", _join(rows), class_="notes")


def _next_candidates(context: _Context) -> _Html:
    items = [
        _el(
            "li",
            _el("strong", _link(node.id, node.id)),
            f" {node.question}",
            _notes(node) or _el("p", "まだメモは無い。", class_="note"),
        )
        for node in context.tree.untouched_nodes()
    ]
    return _el(
        "section",
        _el("h2", "次の候補"),
        _el(
            "p",
            "分析設計をまだ結んでいない論点。人に聞く問いと、聞いてきた答えを添える。",
            class_="note",
        ),
        _el("ul", _join(items)) if items else _el("p", "着手していない論点は無い。"),
        id="next-candidates",
    )


def _question_tree(context: _Context) -> _Html:
    tree = context.tree
    children: dict[str | None, list[QuestionNode]] = {}
    for node in tree.nodes:
        children.setdefault(node.parent_question_id, []).append(node)

    def branch(node: QuestionNode) -> _Html:
        below = children.get(node.id, [])
        return _el(
            "li",
            _node_card(context, node),
            _el("ul", _join(branch(c) for c in below)) if below else None,
            id=node.id,
        )

    return _el(
        "section",
        _el("h2", "論点ツリー"),
        _el("ul", branch(tree.root()), class_="tree"),
        id="question-tree",
    )


def _node_card(context: _Context, node: QuestionNode) -> _Html:
    progress = context.progress[node.id]
    meta: list[_Html | str] = [
        "進捗: ",
        _el("span", _PROGRESS_WORDS[progress][0], class_="progress"),
    ]
    if node.parent_question_id is not None:
        meta.append(f"　寄与: {node.contribution}")
    if node.origin_event_id is not None:
        meta.append(f"　発見元: {node.origin_event_id}")
    answer = node.current_answer()
    parts: list[_Html] = [
        _el("p", _el("strong", node.id), f" {node.question}"),
        _el("p", *meta, class_="meta"),
    ]
    if answer is None:
        parts.append(_el("p", "まだ答えていない"))
    else:
        marks = [
            _el("span", _mark_text(mark, answer), class_="mark")
            for mark in context.marks_of(node)
        ]
        if marks:
            parts.append(_el("p", *marks))
        if node.id not in context.violations:
            parts.append(
                _el(
                    "ul",
                    _join(_statement(s) for s in answer.statements),
                    class_="statements",
                )
            )
        parts.append(_round_meta(answer))
    notes = _notes(node)
    if notes is not None:
        parts.append(notes)
    parts.append(_evidence(context, node))
    return _el("div", _join(parts), class_=f"node progress-{progress.value}")


def _mark_text(mark: Mark, answer: Answer) -> str:
    word = _MARK_WORDS[mark][0].format(round=answer.round)
    if mark is Mark.before_root_change:
        return f"{word}（根の版 {answer.root_revision} への答え）"
    return word


def _statement(statement: AnswerStatement, *tail: str) -> _Html:
    return _el(
        "li",
        _el("span", _KIND_WORDS[statement.kind][0], class_="kind"),
        f" {statement.text}",
        *tail,
    )


def _round_meta(answer: Answer) -> _Html:
    return _el(
        "p",
        f"振り返りの回 {answer.round}（根の版 {answer.root_revision}）",
        class_="meta",
    )


def _evidence(context: _Context, node: QuestionNode) -> _Html:
    answer = node.current_answer()
    sections: list[_Html] = []
    if answer is not None:
        if node.id in context.violations:
            sections += [
                _el("h4", "記録と合わない点"),
                _el(
                    "ul",
                    _join(_violation(v) for v in context.violations[node.id]),
                ),
                _el(
                    "details",
                    _el("summary", "記録と合わなかった答えの文"),
                    _cited_statements(context, answer),
                ),
            ]
        else:
            sections += [
                _el("h4", "現時点の答えの根拠"),
                _cited_statements(context, answer),
            ]
        earlier = list(reversed(node.answers[:-1]))
        if earlier:
            sections.append(_el("h4", "前の回の答え"))
            sections += [_earlier_answer(a) for a in earlier]
    if node.design_ids:
        sections += [
            _el("h4", "結んだ分析設計"),
            _el(
                "ul",
                _join(
                    _el(
                        "li",
                        _link(f"design-{design.id}", design.id),
                        f" {design.title}　状態: {design.status}",
                    )
                    for design in (context.designs[d] for d in node.design_ids)
                ),
            ),
        ]
    if not sections:
        sections.append(_el("p", "まだ根拠は無い。"))
    return _el("details", _el("summary", f"{node.id} の根拠を開く"), _join(sections))


def _violation(violation: Violation) -> _Html:
    word = _VIOLATION_WORDS.get(violation.kind, violation.kind)
    return _el(
        "li",
        f"文 {violation.statement}: {word}（{violation.kind}）",
        _el("blockquote", violation.text),
    )


def _cited_statements(context: _Context, answer: Answer) -> _Html:
    return _el(
        "ul",
        _join(
            _statement(s, _el("ul", _join(_cited_event(context, c) for c in s.cites)))
            for s in answer.statements
        ),
    )


def _cited_event(context: _Context, event_id: str) -> _Html:
    event = context.events.get(event_id)
    if event is None:
        return _el("li", f"journal に見つからない出来事 {event_id}")
    design_id = design_id_of(event_id)
    parts: list[_Html | str] = [
        _el("strong", event_id),
        " design: ",
        _link(f"design-{design_id}", design_id),
    ]
    if event.type:
        parts.append(f" type: {event.type}")
    if event.direction:
        gloss = _DIRECTION_GLOSSES.get(event.direction)
        parts.append(
            f" direction: {event.direction}" + (f"（{gloss}）" if gloss else "")
        )
    parts.append(_el("blockquote", event.content))
    return _el("li", *parts)


def _earlier_answer(answer: Answer) -> _Html:
    return _el(
        "div",
        _round_meta(answer),
        _el(
            "ul",
            _join(
                _statement(s, f"（引用: {', '.join(s.cites)}）")
                for s in answer.statements
            ),
        ),
    )


def _derivation(context: _Context) -> _Html:
    designs = context.designs
    linked_by: dict[str, list[str]] = {}
    for node in context.tree.nodes:
        for design_id in node.design_ids:
            linked_by.setdefault(design_id, []).append(node.id)
    children: dict[str, list[str]] = {}
    for design in designs.values():
        if design.parent_id in designs:
            children.setdefault(design.parent_id, []).append(design.id)
    shown: set[str] = set()

    def branch(design_id: str) -> _Html:
        shown.add(design_id)
        design = designs[design_id]
        nodes = linked_by.get(design_id, [])
        facts: list[_Html | str] = [f"状態: {design.status}　"]
        facts += (
            ["結んだ論点: ", *(_join_links(nodes))] if nodes else ["論点に結んでいない"]
        )
        if design.parent_id is not None and design.parent_id not in designs:
            facts.append(f"　派生元: {design.parent_id}")
        below = [c for c in sorted(children.get(design_id, [])) if c not in shown]
        return _el(
            "li",
            _el(
                "div",
                _el("p", _el("strong", design.id), f" {design.title}"),
                _el("p", *facts, class_="meta"),
                class_="design",
            ),
            _el("ul", _join(branch(c) for c in below)) if below else None,
            id=f"design-{design_id}",
        )

    top = [d for d in sorted(designs) if designs[d].parent_id not in designs]
    items = [branch(d) for d in top]
    # A cycle of parents has no top-level design; show its members anyway.
    items += [branch(d) for d in sorted(designs) if d not in shown]
    body = (
        _el("ul", _join(items), class_="derivation")
        if items
        else _el("p", "分析設計はまだ無い。")
    )
    return _el(
        "section",
        _el("h2", "分析設計の派生"),
        _el(
            "p",
            "分析設計の parent_id で辿る親子。論点の親子とは別の構造。",
            class_="note",
        ),
        body,
        id="derivation",
    )


def _join_links(node_ids: list[str]) -> list[_Html | str]:
    parts: list[_Html | str] = []
    for position, node_id in enumerate(node_ids):
        if position:
            parts.append("、")
        parts.append(_link(node_id, node_id))
    return parts
