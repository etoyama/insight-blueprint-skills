"""The sections of a tree page that show what ``tree_changes`` derives (ADR-0056).

What an answer changed since the answer before it, the results the answers
below it rest on and it leaves out, and the answers above that rest on the
results of a node.

Nothing is computed here: the values come from ``Context``, and this module
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
    Context,
    Shown,
    is_heard,
    link_to,
    result_lines,
    statement_list,
    word_of,
)
from skills._shared.tree_words import (
    CHANGE_WORDS,
    CHANGES_HEADING,
    HEARD_RESULT_WORD,
    NO_LONGER_WORDS,
    NOT_YET_WORDS,
    RESULT_WORD,
    SUBJECT,
    USED_ABOVE_WORDS,
    before_revision,
    changes_title,
    reflection,
    whose_answer,
)


def changes_section(
    context: Context, node: QuestionNode, heading_tag: str
) -> Html | None:
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
                f"{reflection(before)}の答えを読んだ人は、次の表だけ読み直せばよい。"
                "根拠か、根拠について言っていることが、"
                f"{reflection(before)}から変わった所を並べている。",
            ),
            _change_table(context, change, changed),
        ]
    else:
        body.append(
            el(
                "p",
                "根拠も、根拠について言っていることも、"
                f"{reflection(before)}から変わっていない。",
            )
        )
    body.append(
        el(
            "p",
            "、".join(
                f"{CHANGE_WORDS[k][0]} {found[k]}"
                for k in ChangeKind
                # The view rarely changes: a 0 in every answer is only more to read.
                if found[k] or k is not ChangeKind.view_changed
            ),
            class_="meta",
        )
    )
    if same:
        word = CHANGE_WORDS[ChangeKind.unchanged][0]
        body.append(
            el(
                "details",
                el("summary", f"{word}根拠 {len(same)} 件"),
                _change_table(context, change, same),
            )
        )
    title = changes_title(before, now)
    if now == context.tree.current_round():
        return el("div", el(heading_tag, title), join(body), class_="changes")
    return el(
        "details",
        el("summary", title, "　最新の振り返りの変化ではないので畳んである"),
        join(body),
        class_="changes",
    )


def _change_table(
    context: Context, change: AnswerChange, rows: Sequence[EvidenceChange]
) -> Html:
    heard = any(is_heard(context, row.event_id) for row in rows)
    earlier, last = context.tree.node(change.node_id).answers[-2:]
    # Two answers to different revisions of the subject differ for that reason
    # too, so the columns say which revision each one answered.
    revised = earlier.root_revision != last.root_revision

    def answered(answer: Answer) -> str:
        subject = before_revision(context.tree, answer.root_revision) or (
            f"今の{SUBJECT}への答え"
        )
        to = f"（{subject}）" if revised else ""
        return f"{reflection(answer.round)}{to}で"

    head = (
        "変わり方",
        f"{RESULT_WORD}、{HEARD_RESULT_WORD}" if heard else RESULT_WORD,
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


def _change_row(context: Context, row: EvidenceChange) -> Html:
    return el(
        "tr",
        el("th", CHANGE_WORDS[row.kind][0]),
        el("td", *result_lines(context, row.event_id)),
        _said_cell(context, row.before, "根拠にしていなかった"),
        _said_cell(context, row.after, "根拠にしていない"),
    )


def _said_cell(
    context: Context, statements: Sequence[AnswerStatement], none: str
) -> Html:
    if not statements:
        return el("td", none, class_="none")
    return el("td", statement_list(context, statements))


def _split_left_out(
    rows: Sequence[UncitedBelow],
) -> tuple[list[UncitedBelow], list[UncitedBelow]]:
    """The results never in the answer, and those the answer dropped."""
    return (
        [r for r in rows if r.last_cited_round is None],
        [r for r in rows if r.last_cited_round is not None],
    )


def left_out_sections(
    context: Context, node: QuestionNode, heading_tag: str
) -> list[Html]:
    """The results the answers below *node* rest on and its answer leaves out.

    One never in the answer stands out; one the answer dropped is folded. Why
    it was dropped is not on record, so only its rounds are said.
    """
    never, dropped = _split_left_out(context.uncited.get(node.id, ()))
    whose = whose_answer(node.is_root)
    parts: list[Html] = []
    if never:
        parts.append(
            el(
                "div",
                el(heading_tag, NOT_YET_WORDS.format(whose=whose)),
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
                    f"{NO_LONGER_WORDS.format(whose=whose)} {len(dropped)} 件",
                ),
                el("ul", join(_left_out_row(context, r) for r in dropped)),
                class_="uncited-before",
            )
        )
    return parts


def _left_out_row(context: Context, row: UncitedBelow) -> Html:
    parts: list[Html | str | None] = list(result_lines(context, row.event_id))
    if row.last_cited_round is not None:
        instead = (
            f"その次の答えで新しく根拠にした{RESULT_WORD}: "
            f"{'、'.join(row.cited_instead)}。"
            if row.cited_instead
            else None
        )
        parts.append(
            el(
                "p",
                f"{reflection(row.last_cited_round)}の答えまでは根拠にしていた。",
                instead,
            )
        )
    below = context.tree.node(row.node_id)
    if context.shown(below) is Shown.violating:
        parts.append(_unchecked_elsewhere(below))
    else:
        parts += [
            el(
                "p",
                f"論点 {below.id} の{reflection(row.round)}の答えが、"
                f"この{word_of(context, row.event_id)}について言っていること:",
            ),
            statement_list(context, row.statements),
        ]
    return el("li", *parts)


def used_above_section(
    context: Context, node: QuestionNode, answer: Answer
) -> Html | None:
    """How the answers above *node* use the results its answer rests on (US-2)."""
    rows = context.cited_above.get(node.id, ())
    if not rows:
        return None
    return el(
        "div",
        el("h4", USED_ABOVE_WORDS),
        el("ul", join(_used_above_row(context, r, answer) for r in rows)),
        class_="cited-above",
    )


def _used_above_row(context: Context, row: CitedAbove, answer: Answer) -> Html:
    upper = context.tree.node(row.node_id)
    word = word_of(context, row.event_id)
    # The subject's answer, and what it changed, lead the page.
    if upper.is_root:
        name, target, gap = f"論点 {upper.id}（{SUBJECT}）", "subject-answer", ""
    else:
        name, target, gap = f"論点 {upper.id}", upper.id, " "
    parts: list[Html | str | None] = [
        el(
            "p",
            f"{word} {row.event_id} を、",
            link_to(target, name),
            f"{gap}の{reflection(row.round)}の答えが根拠にしている:",
        )
    ]
    if context.shown(upper) is Shown.violating:
        parts.append(_unchecked_elsewhere(upper))
    else:
        parts.append(statement_list(context, row.statements))
    if row.reworded_in is not None:
        parts.append(
            el(
                "p",
                f"論点 {upper.id} の答えは{reflection(row.reworded_in)}から、"
                f"この{word}について言っていることを変えた。"
                f"この論点の答えは{reflection(answer.round)}のままで、変わっていない。",
            )
        )
    return el("li", *parts)


def pointers_to_the_top(context: Context, node: QuestionNode) -> list[Html]:
    """On the card of the subject: what the top of the page shows, one copy only."""
    words = []
    if context.shown(node) is Shown.sound and node.id in context.changes:
        words.append(CHANGES_HEADING)
    never, dropped = _split_left_out(context.uncited.get(node.id, ()))
    if never:
        words.append(NOT_YET_WORDS.format(whose=""))
    if dropped:
        words.append(NO_LONGER_WORDS.format(whose=""))
    return [
        el("p", link_to("subject-answer", f"{w}は、ページの冒頭に出している"))
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
        link_to(node.id, f"文は {node.id} のカードで確かめる"),
    )
