"""Structure tests: the journal's metadata table names the marks of ADR-0064 (Story 35.2).

US-4 AC 5: the marks of a confirmation, its answer and a stop are written only
by the commands of design_io. /analysis-journal writes events by hand, so its
metadata table says which keys it never writes and which command does.
"""

from __future__ import annotations

import re

import pytest

from skills._shared import design_io
from skills._shared.analysis_stage import MARKS
from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill

ASKS_ANALYST, ANSWERS, STOPPED = MARKS


def _convention() -> str:
    return section(_read_skill("analysis-journal"), "## InsightType Convention")


@pytest.mark.parametrize(
    ("kind", "marks"),
    [("`question`", [ASKS_ANALYST]), ("`decide`", [ANSWERS, STOPPED])],
)
def test_the_row_of_the_event_names_its_marks(kind: str, marks: list[str]) -> None:
    # An escaped pipe in the metadata cell splits it, so the cells after the
    # first two are read as one.
    metadata = " ".join(table_row(_convention(), kind)[2:])
    for mark in marks:
        assert f"`{mark}:" in metadata


def test_the_commands_the_table_names_are_commands_of_design_io() -> None:
    named = set(re.findall(r"`design_io ([a-z-]+)`", _convention()))

    assert named == {"ask-analyst", "answer-analyst", "stop"}
    assert named <= set(design_io._COMMANDS)


def test_the_skill_never_writes_the_marks_by_hand() -> None:
    convention = unwrap(_convention())
    assert re.search(r"(?i)never write[^.]*by hand", convention)
    for mark in (ASKS_ANALYST, ANSWERS, STOPPED):
        sentence = next(s for s in convention.split(". ") if "by hand" in s)
        assert f"`{mark}`" in sentence
