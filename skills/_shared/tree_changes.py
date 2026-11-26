"""What an answer changed since the answer before it (Epic 34, ADR-0056).

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
