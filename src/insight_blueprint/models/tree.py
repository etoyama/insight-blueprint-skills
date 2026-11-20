"""Pydantic data models for the question tree of a theme (Epic 18, ADR-0024).

The canonical file is ``.insight/themes/{theme_id}_tree.yaml``. These models
hold every invariant one file can decide on its own. Unknown fields are
rejected so that a derived value such as progress cannot be stored by mistake.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from insight_blueprint.models.common import THEME_ID_PATTERN
from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus

_EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_]+-H\d+-E\d+")


def design_id_of(event_id: str) -> str:
    """The design whose journal holds the event ``{design_id}-E{nn}``."""
    return event_id.rpartition("-E")[0]


class AimKind(StrEnum):
    """Whether the root question serves a business decision or a research claim."""

    business = "business"
    research = "research"


class Progress(StrEnum):
    """How far the analysis of a node has come. Derived, never stored."""

    not_started = "not_started"
    investigating = "investigating"
    analyzed = "analyzed"

    @classmethod
    def of(cls, statuses: Iterable[DesignStatus]) -> Progress:
        """Derive the progress of a node from the statuses of its linked designs."""
        found = set(statuses)
        if not found:
            return cls.not_started
        if found <= TERMINAL_STATUSES:
            return cls.analyzed
        return cls.investigating


class Aim(BaseModel):
    """What the root question is for.

    Business: who decides what. Research: who reads it and how far the claim
    reaches.
    """

    model_config = ConfigDict(extra="forbid")

    kind: AimKind
    decision_maker: str = ""
    decision: str = ""
    audience: str = ""
    claim_scope: str = ""

    @model_validator(mode="after")
    def _has_the_pair_of_its_kind(self) -> Self:
        if self.kind is AimKind.business:
            if not (self.decision_maker and self.decision):
                raise ValueError("a business aim needs decision_maker and decision")
        elif not (self.audience and self.claim_scope):
            raise ValueError("a research aim needs audience and claim_scope")
        return self


class RootRevision(BaseModel):
    """One version of the root question and its aim."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    question: str = Field(min_length=1)
    aim: Aim
    reason: str = ""
    created_at: datetime | None = None

    @model_validator(mode="after")
    def _later_revision_has_a_reason(self) -> Self:
        if self.revision > 1 and not self.reason:
            raise ValueError("reason: a root revision after the first needs a reason")
        return self


class StatementKind(StrEnum):
    """What one statement of an answer does."""

    claim = "claim"
    undetermined = "undetermined"
    weakening = "weakening"


class AnswerStatement(BaseModel):
    """One sentence of an answer and the journal events it rests on."""

    model_config = ConfigDict(extra="forbid")

    kind: StatementKind
    text: str = Field(min_length=1)
    cites: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _cites_look_like_events(self) -> Self:
        for cite in self.cites:
            if not _EVENT_ID_PATTERN.fullmatch(cite):
                raise ValueError(
                    f"cites: '{cite}' is not a journal event id ({{design_id}}-E{{nn}})"
                )
        return self


class Answer(BaseModel):
    """One round of the current answer to a node. The last one is the current one."""

    model_config = ConfigDict(extra="forbid")

    round: int = Field(ge=1)
    root_revision: int = Field(ge=1)
    statements: list[AnswerStatement] = Field(min_length=1)
    created_at: datetime | None = None


class NextCandidate(BaseModel):
    """What the analyst keeps about a node to ask a person next.

    The nodes worth asking about are derived (``QuestionTree.untouched_nodes``);
    this only holds the notes attached to one, and the answer that was heard.
    """

    model_config = ConfigDict(extra="forbid")

    ask: str = ""
    changes_if: str = ""
    known: str = ""
    answer: str = ""
    answered_by: str = ""
    answered_at: date | None = None

    @model_validator(mode="after")
    def _notes_hang_together(self) -> Self:
        if not (self.ask or self.changes_if or self.known):
            raise ValueError(
                "next_candidate: needs at least one of ask, changes_if, known"
            )
        if self.changes_if and not self.ask:
            raise ValueError("next_candidate: changes_if needs the ask it belongs to")
        heard = (self.answer, self.answered_by, self.answered_at)
        if any(heard) and not all(heard):
            raise ValueError(
                "next_candidate: answer, answered_by and answered_at are set together"
            )
        if self.answer and not self.ask:
            raise ValueError("next_candidate: an answer needs the ask it answers")
        return self


class QuestionNode(BaseModel):
    """One node of the tree: a question, and what answering it does for its parent."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str = Field(min_length=1)
    parent_question_id: str | None = None
    contribution: str = ""
    origin_event_id: str | None = None
    design_ids: list[str] = Field(default_factory=list)
    answers: list[Answer] = Field(default_factory=list)
    next_candidate: NextCandidate | None = None

    def current_answer(self) -> Answer | None:
        return self.answers[-1] if self.answers else None

    @model_validator(mode="after")
    def _check_node(self) -> Self:
        if self.parent_question_id is not None and not self.contribution:
            raise ValueError(f"contribution: {self.id} has a parent and needs one")
        if self.origin_event_id is not None and not _EVENT_ID_PATTERN.fullmatch(
            self.origin_event_id
        ):
            raise ValueError(
                f"origin_event_id: '{self.origin_event_id}' is not a journal "
                "event id ({design_id}-E{nn})"
            )
        if len(set(self.design_ids)) != len(self.design_ids):
            raise ValueError(f"design_ids: {self.id} links the same design twice")
        rounds = [a.round for a in self.answers]
        if rounds != sorted(set(rounds)):
            raise ValueError(
                f"answers: rounds of {self.id} must increase, got {rounds}"
            )
        return self


class TreeDecisionKind(StrEnum):
    """What a tree decision decided; ``node_id`` is the node to investigate next."""

    start = "start"
    deepen = "deepen"
    return_ = "return"
    close = "close"


class TreeDecision(BaseModel):
    """One decision about where the investigation goes, and why."""

    model_config = ConfigDict(extra="forbid")

    round: int = Field(ge=0)
    kind: TreeDecisionKind
    node_id: str
    reason: str = Field(min_length=1)
    created_at: datetime | None = None

    @model_validator(mode="after")
    def _start_precedes_the_first_round(self) -> Self:
        if self.kind is TreeDecisionKind.start and self.round != 0:
            raise ValueError("round: a start decision is taken at round 0")
        return self


class QuestionTree(BaseModel):
    """The question tree of one theme. Aggregate root."""

    model_config = ConfigDict(extra="forbid")

    theme_id: str = Field(pattern=rf"^{THEME_ID_PATTERN.pattern}$")
    root_revisions: list[RootRevision] = Field(min_length=1)
    nodes: list[QuestionNode] = Field(min_length=1)
    decisions: list[TreeDecision] = Field(default_factory=list)

    def current_revision(self) -> RootRevision:
        return self.root_revisions[-1]

    def current_round(self) -> int:
        """The reflection round last written; a round numbers the whole tree."""
        return max((a.round for n in self.nodes for a in n.answers), default=0)

    def root(self) -> QuestionNode:
        return next(n for n in self.nodes if n.parent_question_id is None)

    def current_node_id(self) -> str | None:
        """The node of the last decision: where the investigation is now."""
        return self.decisions[-1].node_id if self.decisions else None

    def untouched_nodes(self) -> list[QuestionNode]:
        """The next candidates: no design is linked to the node or anything below it."""
        touched = {n.id for n in self.nodes if n.design_ids}
        parents = {n.id: n.parent_question_id for n in self.nodes}
        for node_id in list(touched):
            parent = parents[node_id]
            while parent is not None:
                touched.add(parent)
                parent = parents[parent]
        return [
            n
            for n in self.nodes
            if n.parent_question_id is not None and n.id not in touched
        ]

    def _is_within(self, node_id: str, branch_id: str) -> bool:
        parents = {n.id: n.parent_question_id for n in self.nodes}
        found: str | None = node_id
        while found is not None:
            if found == branch_id:
                return True
            found = parents[found]
        return False

    @model_validator(mode="after")
    def _check_tree(self) -> Self:
        self._check_revisions()
        self._check_node_ids()
        self._check_references()
        self._check_answer_revisions()
        self._check_parents()
        self._check_decisions()
        if self.root().question != self.current_revision().question:
            raise ValueError(
                "the root question must equal the question of the current root revision"
            )
        return self

    def _check_revisions(self) -> None:
        numbers = [r.revision for r in self.root_revisions]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"root_revisions must count up from 1, got {numbers}")

    def _check_node_ids(self) -> None:
        id_pattern = re.compile(rf"{re.escape(self.theme_id)}-Q\d{{2,}}")
        for node in self.nodes:
            if not id_pattern.fullmatch(node.id):
                raise ValueError(f"node id '{node.id}' must be {self.theme_id}-Q{{nn}}")
        duplicated = [i for i, c in Counter(n.id for n in self.nodes).items() if c > 1]
        if duplicated:
            raise ValueError(f"duplicated node id: {', '.join(duplicated)}")

    def _check_references(self) -> None:
        # A tree gathers the designs of its own theme, so an id of another
        # theme (or anything that is not a design id) is never a valid link.
        design_id = rf"{re.escape(self.theme_id)}-H\d+"
        design_pattern = re.compile(design_id)
        event_pattern = re.compile(rf"{design_id}-E\d+")
        for node in self.nodes:
            for linked in node.design_ids:
                if not design_pattern.fullmatch(linked):
                    raise ValueError(
                        f"{node.id}: design '{linked}' must be {self.theme_id}-H{{nn}}"
                    )
            origin = node.origin_event_id
            if origin is not None and not event_pattern.fullmatch(origin):
                raise ValueError(
                    f"{node.id}: origin '{origin}' must be "
                    f"{self.theme_id}-H{{nn}}-E{{nn}}"
                )
            for answer in node.answers:
                for statement in answer.statements:
                    for cite in statement.cites:
                        if not event_pattern.fullmatch(cite):
                            raise ValueError(
                                f"{node.id}: cite '{cite}' must be "
                                f"{self.theme_id}-H{{nn}}-E{{nn}}"
                            )

    def _check_answer_revisions(self) -> None:
        current = self.current_revision().revision
        for node in self.nodes:
            for answer in node.answers:
                if answer.root_revision > current:
                    raise ValueError(
                        f"{node.id}: answer round {answer.round} has root_revision "
                        f"{answer.root_revision}, but the current root revision "
                        f"is {current}"
                    )

    def _check_decisions(self) -> None:
        node_ids = {n.id for n in self.nodes}
        for decision in self.decisions:
            if decision.node_id not in node_ids:
                raise ValueError(
                    f"decisions: node '{decision.node_id}' is not in the tree"
                )
        starts = sum(d.kind is TreeDecisionKind.start for d in self.decisions)
        if starts > 1:
            raise ValueError("decisions: a tree has at most one start decision")
        previous: TreeDecision | None = None
        for decision in self.decisions:
            self._check_decision_after(decision, previous)
            previous = decision

    def _check_decision_after(
        self, decision: TreeDecision, previous: TreeDecision | None
    ) -> None:
        kind = decision.kind
        if previous is None:
            if kind is not TreeDecisionKind.start:
                raise ValueError("decisions: the first decision must be a start")
            return
        if decision.round < previous.round:
            raise ValueError(
                f"decisions: rounds must not decrease, got {previous.round} "
                f"then {decision.round}"
            )
        if decision.round > self.current_round():
            raise ValueError(
                f"decisions: round {decision.round} is past the last reflection "
                f"round {self.current_round()}"
            )
        inside = self._is_within(decision.node_id, previous.node_id)
        if kind is TreeDecisionKind.deepen and not inside:
            raise ValueError(
                f"decisions: deepen goes to {previous.node_id} or below it, "
                f"not {decision.node_id}"
            )
        if kind is TreeDecisionKind.return_ and inside:
            raise ValueError(
                f"decisions: return leaves {previous.node_id}, "
                f"but {decision.node_id} is inside it"
            )
        if kind is TreeDecisionKind.close and decision.node_id != previous.node_id:
            raise ValueError(
                f"decisions: close stops at {previous.node_id}, not {decision.node_id}"
            )

    def _check_parents(self) -> None:
        parents = {n.id: n.parent_question_id for n in self.nodes}
        roots = [i for i, p in parents.items() if p is None]
        if len(roots) != 1:
            raise ValueError(
                f"a tree has exactly one root question, got {len(roots)}: {roots}"
            )
        for node_id, parent in parents.items():
            if parent is not None and parent not in parents:
                raise ValueError(f"{node_id}: parent '{parent}' is not in the tree")
        for node_id in parents:
            seen = {node_id}
            parent = parents[node_id]
            while parent is not None:
                if parent in seen:
                    raise ValueError(f"cycle of parents through {node_id}")
                seen.add(parent)
                parent = parents[parent]
