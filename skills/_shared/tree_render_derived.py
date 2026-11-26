"""The sections of a tree page that show what ``tree_changes`` derives (ADR-0056).

Nothing is computed here: the values come from ``_Context``, and this module
only decides how they read. Pure, like ``tree_render``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from insight_blueprint.models.tree import Answer, AnswerStatement, QuestionNode
from skills._shared._html import Html, el, join
from skills._shared.tree_changes import AnswerChange, ChangeKind, EvidenceChange
from skills._shared.tree_render_parts import (
    _CHANGE_WORDS,
    _HEARD_RESULT_WORD,
    _RESULT_WORD,
    _SUBJECT_REVISION,
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
