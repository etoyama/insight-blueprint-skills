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

from pydantic import BaseModel, ConfigDict

from insight_blueprint.models.tree import (
    Answer,
    AnswerStatement,
    QuestionNode,
    QuestionTree,
    StatementKind,
    _ancestors,
)


class ChangeKind(StrEnum):
    """How the last answer of a node uses an event, next to the answer before it."""

    newly_cited = "newly_cited"
    dropped = "dropped"
    reworded = "reworded"
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
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    node_id: str
    round: int
    statements: tuple[AnswerStatement, ...]
    last_cited_round: int | None
    cited_instead: tuple[str, ...]


class CitedAbove(BaseModel):
    """An answer above a node that cites an event the node's current answer cites.

    ``round`` is the round of that answer. ``reworded_in`` is the first round,
    after the round of the node's answer, in which the node above said something
    else from the event than it said when the node answered. It is ``None`` when
    it said the same, or did not cite the event yet then.
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
    else:
        kind = ChangeKind.unchanged
    return EvidenceChange(event_id=event_id, kind=kind, before=before, after=after)


def _said(statements: tuple[AnswerStatement, ...]) -> set[tuple[StatementKind, str]]:
    """What the statements say, without their order and their other cites."""
    return {(s.kind, s.text) for s in statements}


def uncited_below(tree: QuestionTree) -> dict[str, tuple[UncitedBelow, ...]]:
    """For each node, the events cited below it that its current answer leaves out.

    A node without an answer leaves out every event cited below it. Nodes with
    nothing to list are left out of the dict.
    """
    parents = {node.id: node.parent_question_id for node in tree.nodes}
    cited_now = {node.id: _current_citing(node) for node in tree.nodes}
    # node id -> event id -> (distance, position of the node below, its id)
    nearest: dict[str, dict[str, tuple[int, int, str]]] = {}
    for position, below in enumerate(tree.nodes):
        for distance, above in enumerate(_ancestors(parents, below.id)):
            found = nearest.setdefault(above, {})
            for event_id in cited_now[below.id]:
                source = (distance, position, below.id)
                if event_id not in found or source < found[event_id]:
                    found[event_id] = source
    uncited: dict[str, tuple[UncitedBelow, ...]] = {}
    for node in tree.nodes:
        left_out = [
            (position, list(cited_now[below_id]).index(event_id), event_id, below_id)
            for event_id, (_, position, below_id) in nearest.get(node.id, {}).items()
            if event_id not in cited_now[node.id]
        ]
        if left_out:
            uncited[node.id] = tuple(
                _uncited(node, event_id, tree.node(below_id), cited_now[below_id])
                for *_, event_id, below_id in sorted(left_out)
            )
    return uncited


def _current_citing(node: QuestionNode) -> dict[str, tuple[AnswerStatement, ...]]:
    answer = node.current_answer()
    return {} if answer is None else _citing(answer)


def _uncited(
    node: QuestionNode,
    event_id: str,
    below: QuestionNode,
    citing: dict[str, tuple[AnswerStatement, ...]],
) -> UncitedBelow:
    last_cited_round: int | None = None
    cited_instead: tuple[str, ...] = ()
    # The answers before the current one, newest first, each with the one after it.
    pairs = list(zip(node.answers[:-1], node.answers[1:], strict=True))
    for earlier, after in reversed(pairs):
        cited_then = _citing(earlier)
        if event_id in cited_then:
            last_cited_round = earlier.round
            cited_instead = tuple(e for e in _citing(after) if e not in cited_then)
            break
    return UncitedBelow(
        event_id=event_id,
        node_id=below.id,
        round=below.answers[-1].round,
        statements=citing[event_id],
        last_cited_round=last_cited_round,
        cited_instead=cited_instead,
    )


def cited_above(tree: QuestionTree) -> dict[str, tuple[CitedAbove, ...]]:
    """For each node, the answers above it that cite what its current answer cites.

    The entries follow the cites of the node, the nearest node above first.
    Nodes with nothing to list are left out of the dict.
    """
    parents = {node.id: node.parent_question_id for node in tree.nodes}
    found: dict[str, tuple[CitedAbove, ...]] = {}
    for node in tree.nodes:
        answer = node.current_answer()
        if answer is None:
            continue
        above = [tree.node(a) for a in _ancestors(parents, node.id)]
        entries = tuple(
            _cited_above(event_id, upper, answer.round)
            for event_id in _citing(answer)
            for upper in above
            if event_id in _current_citing(upper)
        )
        if entries:
            found[node.id] = entries
    return found


def _cited_above(event_id: str, upper: QuestionNode, since: int) -> CitedAbove:
    """*upper* cites *event_id* now; *since* is the round of the node below's answer."""
    said = [(a.round, _said(_citing(a).get(event_id, ()))) for a in upper.answers]
    then = [s for round, s in said if round <= since]
    reworded_in = None
    if then and then[-1]:
        reworded_in = next(
            (round for round, s in said if round > since and s != then[-1]), None
        )
    return CitedAbove(
        event_id=event_id,
        node_id=upper.id,
        round=upper.answers[-1].round,
        statements=_current_citing(upper)[event_id],
        reworded_in=reworded_in,
    )
