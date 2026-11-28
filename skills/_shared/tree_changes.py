"""What an answer changed, and what the answers below it cite (Epic 34, ADR-0056).

Pure: takes a ``QuestionTree`` and reads no file. Nothing here is stored, so the
same tree always gives the same values, also for a tree written before this
module existed. The values are models only so that a command can dump them as
JSON. The content of an event is not known here: ``tree_render`` pairs the ids
with the events it was given.

A change is told only by which events an answer cites and by the kind and text
of the statements that cite them. A reworded sentence and a withdrawn one look
the same from here, so no value says why something changed.
"""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise

from pydantic import BaseModel, ConfigDict

from insight_blueprint.models.tree import (
    Answer,
    AnswerStatement,
    QuestionNode,
    QuestionTree,
    StatementKind,
)


class ChangeKind(StrEnum):
    """How the last answer of a node uses an event, next to the answer before it."""

    newly_cited = "newly_cited"
    dropped = "dropped"
    reworded = "reworded"
    # The same words, with the mark of the analyst's view put on or taken off.
    view_changed = "view_changed"
    unchanged = "unchanged"


class EvidenceChange(BaseModel):
    """One cited event, with the statements that cited it before and cite it now."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    kind: ChangeKind
    before: tuple[AnswerStatement, ...]
    after: tuple[AnswerStatement, ...]


class AnswerChange(BaseModel):
    """The last answer of a node compared with the one before it.

    ``evidence`` holds one entry per event either answer cites: the events of
    the last answer in the order it cites them, then the dropped ones.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    round: int
    previous_round: int
    evidence: tuple[EvidenceChange, ...]


class UncitedBelow(BaseModel):
    """An event an answer below a node cites and the node's current answer does not.

    ``node_id`` is the node below whose current answer cites the event: the
    nearest one when answers at two levels cite it. ``last_cited_round`` is the
    last earlier answer of the node that cited the event, ``None`` when no answer
    of the node ever did. ``cited_instead`` holds the events the answer after
    that one newly cited; it is empty when the event was never cited.

    ``shown_before`` says whether the event was listed for this node before the
    last round of the tree too (ADR-0069): the answers the tree held before that
    round left it out in the same way. It is ``False`` for a node that had no
    answer then.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    node_id: str
    round: int
    statements: tuple[AnswerStatement, ...]
    last_cited_round: int | None
    cited_instead: tuple[str, ...]
    shown_before: bool


class CitedAbove(BaseModel):
    """An answer above a node that cites an event the node's current answer cites.

    ``round`` is the round of that answer. ``reworded_in`` is the first round,
    after the round of the node's answer, in which the node above said something
    else from the event than it said when the node answered. It is ``None`` when
    it says the same now, or did not cite the event yet then.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    node_id: str
    round: int
    statements: tuple[AnswerStatement, ...]
    reworded_in: int | None


def answer_changes(tree: QuestionTree) -> dict[str, AnswerChange]:
    """The change of each node that has an answer before its last one, by node id."""
    changes = {node.id: _change_of(node) for node in tree.nodes}
    return {node_id: change for node_id, change in changes.items() if change}


def _change_of(node: QuestionNode) -> AnswerChange | None:
    if len(node.answers) < 2:
        return None
    previous, current = node.answers[-2], node.answers[-1]
    before, after = _citing(previous), _citing(current)
    # dicts keep the order of first cite, so the rows come out the same each time.
    event_ids = [*after, *(e for e in before if e not in after)]
    return AnswerChange(
        node_id=node.id,
        round=current.round,
        previous_round=previous.round,
        evidence=tuple(
            _evidence_change(e, before.get(e, ()), after.get(e, ())) for e in event_ids
        ),
    )


def _citing(answer: Answer) -> dict[str, tuple[AnswerStatement, ...]]:
    """The statements of *answer* that cite each event, in the order written."""
    citing: dict[str, list[AnswerStatement]] = {}
    for statement in answer.statements:
        for event_id in dict.fromkeys(statement.cites):
            citing.setdefault(event_id, []).append(statement)
    return {event_id: tuple(found) for event_id, found in citing.items()}


def _evidence_change(
    event_id: str,
    before: tuple[AnswerStatement, ...],
    after: tuple[AnswerStatement, ...],
) -> EvidenceChange:
    if not before:
        kind = ChangeKind.newly_cited
    elif not after:
        kind = ChangeKind.dropped
    elif _said(before) != _said(after):
        kind = ChangeKind.reworded
    # Not refused: the analyst may take a view back, and the reader sees that it moved.
    elif _views(before) != _views(after):
        kind = ChangeKind.view_changed
    else:
        kind = ChangeKind.unchanged
    return EvidenceChange(event_id=event_id, kind=kind, before=before, after=after)


def _said(statements: tuple[AnswerStatement, ...]) -> set[tuple[StatementKind, str]]:
    """What the statements say, without their order and their other cites."""
    return {(s.kind, s.text) for s in statements}


def _views(statements: tuple[AnswerStatement, ...]) -> set[tuple[str, bool]]:
    """Which of the statements are the analyst's view, by what they say."""
    return {(s.text, s.analyst_view) for s in statements}


def uncited_below(tree: QuestionTree) -> dict[str, tuple[UncitedBelow, ...]]:
    """For each node, the events cited below it that its current answer leaves out.

    A node without an answer leaves out every event cited below it. Nodes with
    nothing to list are left out of the dict.
    """
    cited_now = {node.id: _current_citing(node) for node in tree.nodes}
    listed_before = _left_out_before(tree, tree.current_round())
    position = {node.id: at for at, node in enumerate(tree.walk())}
    uncited: dict[str, tuple[UncitedBelow, ...]] = {}
    for node in tree.nodes:
        nearest = _nearest_citing_below(tree, node, cited_now)

        def page_order(item: tuple[str, QuestionNode]) -> tuple[int, int]:
            event_id, below = item
            return position[below.id], list(cited_now[below.id]).index(event_id)

        rows = sorted(nearest.items(), key=page_order)
        if rows:
            uncited[node.id] = tuple(
                _uncited(
                    node,
                    event_id,
                    below,
                    cited_now[below.id],
                    shown_before=event_id in listed_before.get(node.id, ()),
                )
                for event_id, below in rows
            )
    return uncited


_Citing = dict[str, tuple[AnswerStatement, ...]]


def _nearest_citing_below(
    tree: QuestionTree, node: QuestionNode, cited: dict[str, _Citing]
) -> dict[str, QuestionNode]:
    """The events cited below *node* that it leaves out, each with the nearest node citing it.

    *cited* holds what the answer of each node cites, by node id.
    """
    # The first node to cite an event, level by level, is the nearest one.
    nearest: dict[str, QuestionNode] = {}
    level = tree.children(node.id)
    while level:
        for below in level:
            for event_id in cited[below.id]:
                if event_id not in cited[node.id]:
                    nearest.setdefault(event_id, below)
        level = [c for below in level for c in tree.children(below.id)]
    return nearest


def _left_out_before(tree: QuestionTree, round: int) -> dict[str, set[str]]:
    """What each node left out of the events cited below it, before *round* was written.

    Only the nodes that had an answer then: a node without one was asked nothing.
    """
    answered = {
        node.id: _citing(answers[-1])
        for node in tree.nodes
        if (answers := [a for a in node.answers if a.round < round])
    }
    cited_then = {node.id: answered.get(node.id, {}) for node in tree.nodes}
    return {
        node.id: set(_nearest_citing_below(tree, node, cited_then))
        for node in tree.nodes
        if node.id in answered
    }


def _current_citing(node: QuestionNode) -> dict[str, tuple[AnswerStatement, ...]]:
    answer = node.current_answer()
    return {} if answer is None else _citing(answer)


def _uncited(
    node: QuestionNode,
    event_id: str,
    below: QuestionNode,
    citing: dict[str, tuple[AnswerStatement, ...]],
    *,
    shown_before: bool,
) -> UncitedBelow:
    answer = below.current_answer()
    assert answer is not None  # a node cites something only through an answer
    last_cited_round: int | None = None
    cited_instead: tuple[str, ...] = ()
    for earlier, after in reversed(list(pairwise(node.answers))):
        cited_then = _citing(earlier)
        if event_id in cited_then:
            last_cited_round = earlier.round
            cited_instead = tuple(e for e in _citing(after) if e not in cited_then)
            break
    return UncitedBelow(
        event_id=event_id,
        node_id=below.id,
        round=answer.round,
        statements=citing[event_id],
        last_cited_round=last_cited_round,
        cited_instead=cited_instead,
        shown_before=shown_before,
    )


def cited_above(tree: QuestionTree) -> dict[str, tuple[CitedAbove, ...]]:
    """For each node, the answers above it that cite what its current answer cites.

    The entries follow the cites of the node, the nearest node above first.
    Nodes with nothing to list are left out of the dict.
    """
    cited_now = {node.id: _current_citing(node) for node in tree.nodes}
    found: dict[str, tuple[CitedAbove, ...]] = {}
    for node in tree.nodes:
        answer = node.current_answer()
        if answer is None:
            continue
        above = tree.ancestors(node.id)
        entries = tuple(
            _cited_above(event_id, upper, answer.round, cited_now[upper.id])
            for event_id in cited_now[node.id]
            for upper in above
            if event_id in cited_now[upper.id]
        )
        if entries:
            found[node.id] = entries
    return found


def _cited_above(
    event_id: str,
    upper: QuestionNode,
    since: int,
    citing: dict[str, tuple[AnswerStatement, ...]],
) -> CitedAbove:
    """*upper* cites *event_id* now; *since* is the round of the node below's answer."""
    said = [(a.round, _said(_citing(a).get(event_id, ()))) for a in upper.answers]
    said_then = [what for when, what in said if when <= since]
    reworded_in = None
    # Citing it for the first time after *since* is not saying something else,
    # and an answer that says again what it said then has nothing to tell.
    if said_then and said_then[-1] and said[-1][1] != said_then[-1]:
        reworded_in = next(
            (when for when, what in said if when > since and what != said_then[-1]),
            None,
        )
    answer = upper.current_answer()
    assert answer is not None  # *upper* cites the event through its answer
    return CitedAbove(
        event_id=event_id,
        node_id=upper.id,
        round=answer.round,
        statements=citing[event_id],
        reworded_in=reworded_in,
    )
