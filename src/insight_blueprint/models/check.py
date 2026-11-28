"""The record of a check of the computation (Epic 36, ADR-0070).

A check tells, subject by subject, whether the notebook computed what its
design says. It reads the design, the notebook and the verdict; it touches no
data and judges neither the numbers nor the design. ``design_io check`` is its
only writer, and the record lives in ``.insight/designs/{id}_check.yaml``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator


class CheckSubject(StrEnum):
    """What a check compares between the design and the notebook."""

    population = "population"
    grain = "grain"
    denominator = "denominator"
    extraction = "extraction"
    metrics = "metrics"
    compared_against = "compared_against"
    figures = "figures"
    criterion = "criterion"
    cells = "cells"


# The subjects the code decides. A reader's answer never stands for them (ADR-0070 6).
CODE_SUBJECTS = (CheckSubject.metrics, CheckSubject.figures, CheckSubject.cells)


class CheckResult(StrEnum):
    agrees = "agrees"
    differs = "differs"
    not_checkable = "not_checkable"


class CheckedBy(StrEnum):
    """Who read the subjects the code cannot decide (ADR-0070 9)."""

    check_agent = "check_agent"
    # The session that wrote the notebook read it itself: not an independent eye.
    same_session = "same_session"


class CheckItem(BaseModel):
    """The result of one subject. ``cell`` is the name of the notebook cell read."""

    subject: CheckSubject
    result: CheckResult
    note: str = ""
    cell: str | None = None

    @model_validator(mode="after")
    def _a_result_that_does_not_agree_is_explained(self) -> Self:
        if self.result is CheckResult.agrees:
            return self
        if not self.note.strip():
            raise ValueError(
                f"note: {self.subject.value} is {self.result.value}, so say what "
                "differs or why it could not be checked"
            )
        # The order of the cells is not read in any one of them.
        needs_cell = (
            self.result is CheckResult.differs
            and self.subject is not CheckSubject.cells
        )
        if needs_cell and not (self.cell or "").strip():
            raise ValueError(
                f"cell: {self.subject.value} differs, so name the notebook cell "
                "the difference was read in"
            )
        return self


def verdict_digest(verdict: bytes) -> str:
    """The name a check remembers its verdict by: the bytes of the file, hashed.

    The time of the file would change on a copy or a checkout, and the check
    would read as not done for a verdict it did check.
    """
    return f"sha256:{hashlib.sha256(verdict).hexdigest()}"


# The fields of a design the subjects of a check are written in. Any other may
# change and the check stays done: a review of the result moves the status, a
# reflection adds referenced knowledge, and neither changes what was compared.
COMPARED_FIELDS = (
    "analysis_intent",  # with exploration_question, whether there is a criterion
    "exploration_question",
    "hypothesis_statement",
    "data_scope",  # population, grain, denominator
    "methodology",  # extraction
    "source_ids",
    "metrics",  # metrics, what a result is compared against, the criterion
    "explanatory",
    "chart",  # figures
)


def design_digest(design: Mapping[str, object]) -> str:
    """The name a check remembers its design by: its ``COMPARED_FIELDS``, hashed.

    *design* is the file as read. The order of its keys does not count, and a
    field that is absent reads as one that is null.
    """
    said = {field: design.get(field) for field in COMPARED_FIELDS}
    text = json.dumps(said, sort_keys=True, ensure_ascii=False, default=str)
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


class DesignCheck(BaseModel):
    """The check of one design, for one verdict. A later check replaces it."""

    design_id: str
    verdict_digest: str
    design_digest: str
    checked_by: CheckedBy
    items: list[CheckItem]

    @model_validator(mode="after")
    def _each_subject_is_checked_once(self) -> Self:
        count = Counter(item.subject for item in self.items)
        twice = [s.value for s, n in count.items() if n > 1]
        if twice:
            raise ValueError(f"items: given more than once: {', '.join(twice)}")
        # Only a design that judges a hypothesis has a criterion; the model does
        # not see the design, so the writer holds that rule.
        missing = [
            s.value
            for s in CheckSubject
            if s is not CheckSubject.criterion and s not in count
        ]
        if missing:
            raise ValueError(f"items: not checked: {', '.join(missing)}")
        return self

    def is_current(self, verdict: bytes, design: Mapping[str, object]) -> bool:
        """Whether *verdict* and *design*, the files as they are now, are the ones checked.

        A design changed after the check would leave a difference that is no
        longer one, or hide one that now is (ADR-0070 7).
        """
        return self.verdict_digest == verdict_digest(
            verdict
        ) and self.design_digest == design_digest(design)

    def differences(self) -> list[CheckItem]:
        return [item for item in self.items if item.result is CheckResult.differs]
