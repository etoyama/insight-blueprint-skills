"""The context of a tree page and the parts its sections share.

The words come from ``tree_words``. Pure, like ``tree_render``: every string is
untrusted and goes through ``_html``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from insight_blueprint.models.analysis_stage import AnalysisStage
from insight_blueprint.models.design import DesignForm, DesignStatus
from insight_blueprint.models.tree import (
    Answer,
    AnswerStatement,
    Progress,
    QuestionNode,
    QuestionTree,
    TreeDecision,
    TreeDecisionKind,
    design_id_of,
)
from skills._shared._html import Html, el, join
from skills._shared.design_note import DesignNote, intent_word, statement_of
from skills._shared.design_note_reviews import comments_after_analysis
from skills._shared.tree_changes import (
    AnswerChange,
    CitedAbove,
    UncitedBelow,
    answer_changes,
    cited_above,
    uncited_below,
)
from skills._shared.tree_check import CitedEvent, Violation
from skills._shared.tree_words import (
    HEARD_RESULT_WORD,
    HEARD_WORD,
    KIND_WORDS,
    RESULT_WORD,
    Mark,
    left_as_written,
    mark_text,
    reflection,
)


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
    stage: AnalysisStage
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
            stage=note.stage,
            comments_after_analysis=comments_after_analysis(note.reviews),
        )


@dataclass(frozen=True)
class CheckFailed:
    """The cited-answer check could not run, so no answer is known to be sound."""

    message: str


class Shown(StrEnum):
    """How much of the current answer of a node the page shows."""

    unanswered = "unanswered"
    # The answer failed the check: its statements stay folded in its card.
    violating = "violating"
    sound = "sound"


@dataclass(frozen=True)
class Context:
    """The inputs of a page and the facts derived from them, computed once."""

    tree: QuestionTree
    designs: Mapping[str, DesignSummary]
    events: Mapping[str, CitedEvent]
    design_notes: Mapping[str, Html]
    # The progress word of each node that has one (QuestionTree.progress). A node
    # with a design below it and none of its own shows the progress below it.
    progress: Mapping[str, Progress]
    # The progress of every node under each node, those without a word left out.
    below: Mapping[str, Counter[Progress]]
    violations: Mapping[str, Sequence[Violation]]
    # Node ids that link a design, in page order: the first one shows its card.
    linked_by: Mapping[str, list[str]]
    changes: Mapping[str, AnswerChange]
    uncited: Mapping[str, tuple[UncitedBelow, ...]]
    cited_above: Mapping[str, tuple[CitedAbove, ...]]
    # Cited ids two journal events share: which of them backs a cite is unknown.
    shared: frozenset[str]

    @classmethod
    def of(
        cls,
        tree: QuestionTree,
        designs: Mapping[str, DesignSummary],
        events: Mapping[str, CitedEvent],
        checked: Sequence[Violation] | CheckFailed,
        design_notes: Mapping[str, Html],
        shared: frozenset[str],
    ) -> Context:
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
        progress = tree.progress({d: s.stage for d, s in designs.items()})
        violations: dict[str, list[Violation]] = {}
        for violation in () if isinstance(checked, CheckFailed) else checked:
            violations.setdefault(violation.node_id, []).append(violation)
        linked_by: dict[str, list[str]] = {}
        for node in tree.walk():
            for design_id in node.design_ids:
                linked_by.setdefault(design_id, []).append(node.id)
        return cls(
            tree,
            designs,
            events,
            design_notes,
            progress,
            tree.progress_below(progress),
            violations,
            linked_by,
            answer_changes(tree),
            uncited_below(tree),
            cited_above(tree),
            shared,
        )

    def shown(self, node: QuestionNode) -> Shown:
        if node.current_answer() is None:
            return Shown.unanswered
        if node.id in self.violations:
            return Shown.violating
        return Shown.sound

    def closed_by(self, node: QuestionNode) -> TreeDecision | None:
        """The latest decision naming *node*, when it closed the node."""
        naming = [d for d in self.tree.decisions if node.id in d.node_ids()]
        if naming and naming[-1].kind is TreeDecisionKind.close:
            return naming[-1]
        return None

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


def link_to(target: str, label: str) -> Html:
    return el("a", label, href=f"#{target}")


def mark_line(context: Context, node: QuestionNode, answer: Answer) -> Html | None:
    marks = [
        el("span", mark_text(context.tree, mark, answer), class_="mark")
        for mark in context.marks_of(node)
    ]
    return el("p", *marks) if marks else None


def answer_lines(
    context: Context, node: QuestionNode, answer: Answer, heading: str | None = None
) -> list[Html | None]:
    """An answer that passed the check: its marks, statements and round."""
    return [
        mark_line(context, node, answer),
        el("p", heading, class_="answer-heading") if heading else None,
        statement_list(context, answer.statements),
        current_round_meta(context, answer),
    ]


def is_heard(context: Context, event_id: str) -> bool:
    event = context.events.get(event_id)
    return event is not None and event.type == "hearing"


def result_lines(context: Context, event_id: str) -> list[Html | str]:
    """An analysis result as the analyst reads it: where it comes from, then what it says."""
    event = context.events.get(event_id)
    if event is None:
        return [f"記録に見つからない {event_id}"]
    design_id = design_id_of(event_id)
    word = word_of(context, event_id)
    nodes = context.linked_by.get(design_id, [])
    source: list[Html | str] = ["論点 ", *join_links(nodes), "、"] if nodes else []
    source += ["分析設計 ", link_to(f"design-{design_id}", design_id)]
    return [
        el("strong", f"{word} {event_id}"),
        " ",
        el("span", *source, class_="meta"),
        el("blockquote", event.content),
    ]


def statement_item(statement: AnswerStatement, *tail: str) -> Html:
    return el(
        "li",
        el("span", KIND_WORDS[statement.kind][0], class_="kind"),
        f" {statement.text}",
        *tail,
    )


def _heard_word(context: Context, statement: AnswerStatement) -> tuple[str, ...]:
    """The word for a statement whose every cited event is what a person said.

    The check counts a number in a hearing event as recorded, so the page is
    where a reader sees that no event of the data stands behind the statement.
    """
    if all(is_heard(context, cite) for cite in statement.cites):
        return (f" {HEARD_WORD}",)
    return ()


def current_round_meta(context: Context, answer: Answer) -> Html:
    """The round of a current answer, and that later rounds left it as it is.

    The marks only know the latest round, so without this line a round that
    passes would leave no trace on an answer it did not touch.
    """
    latest = context.tree.current_round()
    untouched = (
        f"　{left_as_written(latest, answer.round)}" if answer.round < latest else None
    )
    return el("p", el("span", reflection(answer.round), class_="meta"), untouched)


def join_links(node_ids: list[str]) -> list[Html | str]:
    parts: list[Html | str] = []
    for position, node_id in enumerate(node_ids):
        if position:
            parts.append("、")
        parts.append(link_to(node_id, node_id))
    return parts


def statement_list(context: Context, statements: Sequence[AnswerStatement]) -> Html:
    return el(
        "ul",
        join(statement_item(s, *_heard_word(context, s)) for s in statements),
        class_="statements",
    )


def word_of(context: Context, event_id: str) -> str:
    """What an answer rests on: what a person said, or an analysis result."""
    return HEARD_RESULT_WORD if is_heard(context, event_id) else RESULT_WORD
