"""Pydantic data models for the question tree of a theme (Epic 18, ADR-0024).

The canonical file is ``.insight/themes/{theme_id}_tree.yaml``. These models
hold every invariant one file can decide on its own. Unknown fields are
rejected so that a derived value such as progress cannot be stored by mistake.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from insight_blueprint.models.design import DesignStatus

THEME_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9]*")
_EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_]+-H\d+-E\d+")

_TERMINAL_STATUSES = frozenset(
    {DesignStatus.supported, DesignStatus.rejected, DesignStatus.inconclusive}
)


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
        if found <= _TERMINAL_STATUSES:
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


class QuestionNode(BaseModel):
    """One node of the tree: a question, and what answering it does for its parent."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str = Field(min_length=1)
    parent_question_id: str | None = None
    contribution: str = ""
    origin_event_id: str | None = None
    design_ids: list[str] = Field(default_factory=list)

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
        return self


class QuestionTree(BaseModel):
    """The question tree of one theme. Aggregate root."""

    model_config = ConfigDict(extra="forbid")

    theme_id: str = Field(pattern=rf"^{THEME_ID_PATTERN.pattern}$")
    root_revisions: list[RootRevision] = Field(min_length=1)
    nodes: list[QuestionNode] = Field(min_length=1)

    def current_revision(self) -> RootRevision:
        return self.root_revisions[-1]

    def root(self) -> QuestionNode:
        return next(n for n in self.nodes if n.parent_question_id is None)

    def node(self, node_id: str) -> QuestionNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    @model_validator(mode="after")
    def _check_tree(self) -> Self:
        self._check_revisions()
        self._check_node_ids()
        self._check_parents()
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
