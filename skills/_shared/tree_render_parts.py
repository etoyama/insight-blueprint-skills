"""The context of a tree page, its words, and the parts its sections share.

The words shown to the analyst live here, each table next to what the legend
says it means, so ``tree_render`` and ``tree_render_derived`` say the same.
Pure, like ``tree_render``: every string is untrusted and goes through ``_html``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from insight_blueprint.models.design import DesignForm, DesignStatus
from insight_blueprint.models.tree import (
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
from skills._shared._html import Html, el, join
from skills._shared.design_note import DesignNote, intent_word, statement_of
from skills._shared.design_note_reviews import comments_after_analysis
from skills._shared.tree_changes import AnswerChange, ChangeKind, answer_changes

if TYPE_CHECKING:  # tree_check imports CitedEvent from here, through tree_render
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


# The words the page says of the subject (ADR-0055); YAML and code say root.
_SUBJECT = "主題"


_SUBJECT_REVISION = f"{_SUBJECT}の版"


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
KIND_WORDS = {
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
        "これまでわかっていることを弱める分析結果や、言える範囲を狭める条件。",
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
        f"見直す前の{_SUBJECT}への答え",
        f"{_SUBJECT}か到達点を見直す前の、古い{_SUBJECT_REVISION}に対して書いた答え。",
    ),
    Mark.violating: (
        "記録と合わない答え",
        "引用した出来事が journal に無い、結んでいない分析設計の出来事を引いている、"
        "引用に無い数字を書いている、のどれかの答え。答えの文は閉じた中に畳む。",
    ),
}


# How the last answer of a node uses an analysis result, next to the answer
# before it. The page says only what the cites show (ADR-0056): it never says
# that a result moved the answer or that a claim was withdrawn.
_CHANGE_WORDS = {
    ChangeKind.newly_cited: (
        "新しく根拠にした",
        "前の回の答えでは根拠にしていなかった分析結果を、この答えで根拠にした。",
    ),
    ChangeKind.dropped: (
        "根拠から外した",
        "前の回の答えでは根拠にしていた分析結果を、この答えでは根拠にしていない。",
    ),
    ChangeKind.reworded: (
        "言っていることが変わった",
        "同じ分析結果を根拠にしたまま、そこから言っている文か、文の種類が変わった。"
        "言い回しを変えただけでも、ここに出る。",
    ),
    ChangeKind.unchanged: (
        "変わっていない",
        "同じ分析結果から、同じ文を言っている。表では畳んで出す。",
    ),
}


# What an answer rests on, in the analyst's words: an event of the data, or what
# a person said (a hearing event is not called an analysis result, US-5 AC 5).
_RESULT_WORD = "分析結果"


_HEARD_RESULT_WORD = "人に聞いた答え"


_HEARD_WORD = f"（{_HEARD_RESULT_WORD}による）"


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


class Shown(StrEnum):
    """How much of the current answer of a node the page shows."""

    unanswered = "unanswered"
    # The answer failed the check: its statements stay folded in its card.
    violating = "violating"
    sound = "sound"


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
    changes: Mapping[str, AnswerChange]

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
            answer_changes(tree),
        )

    def shown(self, node: QuestionNode) -> Shown:
        if node.current_answer() is None:
            return Shown.unanswered
        if node.id in self.violations:
            return Shown.violating
        return Shown.sound

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


def _marks(context: _Context, node: QuestionNode, answer: Answer) -> Html | None:
    marks = [
        el("span", _mark_text(mark, answer), class_="mark")
        for mark in context.marks_of(node)
    ]
    return el("p", *marks) if marks else None


def _answer_lines(
    context: _Context, node: QuestionNode, answer: Answer, heading: str | None = None
) -> list[Html | None]:
    """An answer that passed the check: its marks, statements and round."""
    return [
        _marks(context, node, answer),
        el("p", heading, class_="answer-heading") if heading else None,
        el(
            "ul",
            join(_statement(s, *_heard_word(context, s)) for s in answer.statements),
            class_="statements",
        ),
        _current_round_meta(context, answer),
    ]


def _is_heard(context: _Context, event_id: str) -> bool:
    event = context.events.get(event_id)
    return event is not None and event.type == "hearing"


def _result(context: _Context, event_id: str) -> list[Html | str]:
    """An analysis result as the analyst reads it: where it comes from, then what it says."""
    event = context.events.get(event_id)
    if event is None:
        return [f"記録に見つからない {event_id}"]
    design_id = design_id_of(event_id)
    word = _HEARD_RESULT_WORD if _is_heard(context, event_id) else _RESULT_WORD
    nodes = context.linked_by.get(design_id, [])
    source: list[Html | str] = ["論点 ", *_join_links(nodes), "、"] if nodes else []
    source += ["分析設計 ", _link(f"design-{design_id}", design_id)]
    return [
        el("strong", f"{word} {event_id}"),
        " ",
        el("span", *source, class_="meta"),
        el("blockquote", event.content),
    ]


def _mark_text(mark: Mark, answer: Answer) -> str:
    word = _MARK_WORDS[mark][0].format(round=answer.round)
    if mark is Mark.before_root_change:
        return f"{word}（{_SUBJECT_REVISION} {answer.root_revision} への答え）"
    return word


def _statement(statement: AnswerStatement, *tail: str) -> Html:
    return el(
        "li",
        el("span", KIND_WORDS[statement.kind][0], class_="kind"),
        f" {statement.text}",
        *tail,
    )


def _heard_word(context: _Context, statement: AnswerStatement) -> tuple[str, ...]:
    """The word for a statement whose every cited event is what a person said.

    The check counts a number in a hearing event as recorded, so the page is
    where a reader sees that no event of the data stands behind the statement.
    """
    if all(_is_heard(context, cite) for cite in statement.cites):
        return (f" {_HEARD_WORD}",)
    return ()


def _round_line(answer: Answer) -> str:
    return f"振り返りの回 {answer.round}（{_SUBJECT_REVISION} {answer.root_revision}）"


def _round_meta(answer: Answer) -> Html:
    return el("p", _round_line(answer), class_="meta")


def _current_round_meta(context: _Context, answer: Answer) -> Html:
    """The round of a current answer, and that later rounds left it as it is.

    The marks only know the latest round, so without this line a round that
    passes would leave no trace on an answer it did not touch.
    """
    latest = context.tree.current_round()
    untouched = (
        f"　最新の振り返りは回 {latest} で、回 {answer.round} より後の回では、"
        "この答えを書き直していない。"
        if answer.round < latest
        else None
    )
    return el("p", el("span", _round_line(answer), class_="meta"), untouched)


def _join_links(node_ids: list[str]) -> list[Html | str]:
    parts: list[Html | str] = []
    for position, node_id in enumerate(node_ids):
        if position:
            parts.append("、")
        parts.append(_link(node_id, node_id))
    return parts


def _checked_in_its_card(node: QuestionNode) -> Html:
    """In place of an answer that failed the check: its mark and its card."""
    return el(
        "p",
        el("span", _MARK_WORDS[Mark.violating][0], class_="mark"),
        " ",
        _link(node.id, f"{node.id} のカードで確かめる"),
    )
