"""The sections of a tree page that show what ``tree_changes`` derives (ADR-0056).

What an answer changed since the answer before it, the results the answers
below it rest on and it leaves out, and the answers above that rest on the
results of a node.

Nothing is computed here: the values come from ``_Context``, and this module
only decides how they read. Pure, like ``tree_render``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from insight_blueprint.models.tree import Answer, AnswerStatement, QuestionNode
from skills._shared._html import Html, el, join
from skills._shared.tree_changes import (
    AnswerChange,
    ChangeKind,
    CitedAbove,
    EvidenceChange,
    UncitedBelow,
)
from skills._shared.tree_render_parts import (
    _CHANGE_WORDS,
    _HEARD_RESULT_WORD,
    _NO_LONGER_WORDS,
    _NOT_YET_WORDS,
    _RESULT_WORD,
    _SUBJECT,
    _SUBJECT_REVISION,
    _USED_ABOVE_WORDS,
    Shown,
    _Context,
    _heard_word,
    _is_heard,
    _link,
    _result,
    _statement,
)


def _changes_on_the_card(context: _Context, node: QuestionNode) -> Html | None:
    if node.parent_question_id is None and node.id in context.changes:
        # The table of the subject is at the top of the page; one copy is enough.
        return el(
            "p",
            _link(
                "subject-answer", "前の回から変わったことは、ページの冒頭に出している"
            ),
        )
    return _changes(context, node, "h4")


def _changes(context: _Context, node: QuestionNode, heading_tag: str) -> Html | None:
    """What the last answer of *node* changed since the answer before it (ADR-0056)."""
    change = context.changes.get(node.id)
    if change is None:
        return None
    before, now = change.previous_round, change.round
    changed = [e for e in change.evidence if e.kind is not ChangeKind.unchanged]
    same = [e for e in change.evidence if e.kind is ChangeKind.unchanged]
    found = Counter(e.kind for e in change.evidence)
    body: list[Html | None] = []
    if changed:
        body += [
            el(
                "p",
                f"回 {before} の答えを読んだ人は、次の表だけ読み直せばよい。"
                f"根拠か、そこから言っていることが、回 {before} から変わった所を並べている。",
            ),
            _change_table(context, change, changed),
        ]
    else:
        body.append(
            el(
                "p",
                f"根拠も、そこから言っていることも、回 {before} から変わっていない。",
            )
        )
    body.append(
        el(
            "p",
            "、".join(f"{_CHANGE_WORDS[k][0]} {found[k]}" for k in ChangeKind),
            class_="meta",
        )
    )
    if same:
        word = _CHANGE_WORDS[ChangeKind.unchanged][0]
        body.append(
            el(
                "details",
                el("summary", f"{word}根拠 {len(same)} 件"),
                _change_table(context, change, same),
            )
        )
    title = f"前の回から変わったこと（回 {before} → 回 {now}）"
    if now == context.tree.current_round():
        return el("div", el(heading_tag, title), join(body), class_="changes")
    return el(
        "details",
        el("summary", title, "　最新の回の変化ではないので畳んである"),
        join(body),
        class_="changes",
    )


def _change_table(
    context: _Context, change: AnswerChange, rows: Sequence[EvidenceChange]
) -> Html:
    heard = any(_is_heard(context, row.event_id) for row in rows)
    earlier, last = context.tree.node(change.node_id).answers[-2:]
    # Two answers to different revisions of the subject differ for that reason
    # too, so the columns say which revision each one answered.
    revised = earlier.root_revision != last.root_revision

    def answered(answer: Answer) -> str:
        to = (
            f"（{_SUBJECT_REVISION} {answer.root_revision} への答え）"
            if revised
            else " "
        )
        return f"回 {answer.round}{to}で、ここから"

    head = (
        "変わり方",
        f"{_RESULT_WORD}、{_HEARD_RESULT_WORD}" if heard else _RESULT_WORD,
        f"{answered(earlier)}言っていたこと",
        f"{answered(last)}言っていること",
    )
    return el(
        "div",
        el(
            "table",
            el("thead", el("tr", join(el("th", h) for h in head))),
            el("tbody", join(_change_row(context, row) for row in rows)),
        ),
        class_="scroll",
    )


def _change_row(context: _Context, row: EvidenceChange) -> Html:
    return el(
        "tr",
        el("th", _CHANGE_WORDS[row.kind][0]),
        el("td", *_result(context, row.event_id)),
        _said_cell(context, row.before, "根拠にしていなかった"),
        _said_cell(context, row.after, "根拠にしていない"),
    )


def _said_cell(
    context: _Context, statements: Sequence[AnswerStatement], none: str
) -> Html:
    if not statements:
        return el("td", none, class_="none")
    return el(
        "td",
        el("ul", join(_statement(s, *_heard_word(context, s)) for s in statements)),
    )


def _left_out(context: _Context, node: QuestionNode, whose: str) -> list[Html | None]:
    """The results the answers below *node* rest on and its answer leaves out.

    One never in the answer stands out; one the answer dropped is folded. Why
    it was dropped is not on record, so only its rounds are said.
    """
    rows = context.uncited.get(node.id, ())
    never = [r for r in rows if r.last_cited_round is None]
    dropped = [r for r in rows if r.last_cited_round is not None]
    heading = "h3" if node.parent_question_id is None else "h4"
    parts: list[Html | None] = []
    if never:
        parts.append(
            el(
                "div",
                el(heading, _NOT_YET_WORDS.format(whose=whose)),
                el(
                    "p",
                    f"{whose}答えが一度も根拠にしていない分析結果。"
                    "差が出なかった分析の結果も、ここに出る。"
                    "答えに入れるかは分析者が決める。",
                    class_="meta",
                ),
                el("ul", join(_left_out_row(context, r) for r in never)),
                class_="uncited",
            )
        )
    if dropped:
        parts.append(
            el(
                "details",
                el(
                    "summary",
                    f"{_NO_LONGER_WORDS.format(whose=whose)} {len(dropped)} 件",
                ),
                el("ul", join(_left_out_row(context, r) for r in dropped)),
                class_="uncited-before",
            )
        )
    return parts


def _left_out_row(context: _Context, row: UncitedBelow) -> Html:
    parts: list[Html | str | None] = list(_result(context, row.event_id))
    if row.last_cited_round is not None:
        instead = (
            f"その次の答えで新しく根拠にした{_RESULT_WORD}: "
            f"{'、'.join(row.cited_instead)}。"
            if row.cited_instead
            else None
        )
        parts.append(
            el("p", f"回 {row.last_cited_round} の答えまでは根拠にしていた。", instead)
        )
    below = context.tree.node(row.node_id)
    if context.shown(below) is Shown.violating:
        parts.append(_unchecked_elsewhere(below))
    else:
        parts += [
            el(
                "p",
                f"論点 {below.id} の回 {row.round} の答えが、"
                f"この{_word_of(context, row.event_id)}から言っていること:",
            ),
            _said(context, row.statements),
        ]
    return el("li", *parts)


def _used_above(context: _Context, node: QuestionNode, answer: Answer) -> Html | None:
    """How the answers above *node* use the results its answer rests on (US-2)."""
    rows = context.cited_above.get(node.id, ())
    if not rows:
        return None
    return el(
        "div",
        el("h4", _USED_ABOVE_WORDS),
        el("ul", join(_used_above_row(context, r, answer) for r in rows)),
        class_="cited-above",
    )


def _used_above_row(context: _Context, row: CitedAbove, answer: Answer) -> Html:
    upper = context.tree.node(row.node_id)
    word = _word_of(context, row.event_id)
    # The subject's answer, and what it changed, lead the page.
    if upper.parent_question_id is None:
        name, target, gap = f"論点 {upper.id}（{_SUBJECT}）", "subject-answer", ""
    else:
        name, target, gap = f"論点 {upper.id}", upper.id, " "
    parts: list[Html | str | None] = [
        el(
            "p",
            f"{word} {row.event_id} を、",
            _link(target, name),
            f"{gap}の回 {row.round} の答えが根拠にしている:",
        )
    ]
    if context.shown(upper) is Shown.violating:
        parts.append(_unchecked_elsewhere(upper))
    else:
        parts.append(_said(context, row.statements))
    if row.reworded_in is not None:
        parts.append(
            el(
                "p",
                f"論点 {upper.id} の答えは回 {row.reworded_in} から、"
                f"この{word}から言っていることを変えた。"
                f"この論点の答えは回 {answer.round} のままで、変わっていない。",
            )
        )
    return el("li", *parts)


def _said(context: _Context, statements: Sequence[AnswerStatement]) -> Html:
    return el(
        "ul",
        join(_statement(s, *_heard_word(context, s)) for s in statements),
        class_="statements",
    )


def _word_of(context: _Context, event_id: str) -> str:
    return _HEARD_RESULT_WORD if _is_heard(context, event_id) else _RESULT_WORD


def _left_out_on_the_card(context: _Context, node: QuestionNode) -> list[Html | None]:
    if node.parent_question_id is not None:
        return _left_out(context, node, "この論点の")
    # The lists of the subject are at the top of the page; one copy is enough.
    rows = context.uncited.get(node.id, ())
    words = []
    if any(r.last_cited_round is None for r in rows):
        words.append(_NOT_YET_WORDS.format(whose=""))
    if any(r.last_cited_round is not None for r in rows):
        words.append(_NO_LONGER_WORDS.format(whose=""))
    return [
        el("p", _link("subject-answer", f"{w}は、ページの冒頭に出している"))
        for w in words
    ]


def _unchecked_elsewhere(node: QuestionNode) -> Html:
    """In place of another node's answer that failed the check.

    Its statements stay folded in its own card. The mark is not used here: on
    this card it would read as the mark of this node's answer.
    """
    return el(
        "p",
        f"論点 {node.id} の答えは記録と合わない。",
        _link(node.id, f"文は {node.id} のカードで確かめる"),
    )
