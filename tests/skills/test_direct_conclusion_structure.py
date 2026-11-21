"""Structure tests for concluding an analyzed design directly (Epic 19, Story #147).

``VALID_TRANSITIONS`` lets ``analyzing`` reach the conclusion statuses (ADR-0029),
and the prose that tells a model or a reader which moves exist must not contradict
it (US-1 AC 3, AC 4). The prose gives examples, so the tests check each example
against the table: a move named as allowed passes, a move named as refused raises.
Only the Status Flow diagram is complete, so only it is compared with a whole row.
"""

from __future__ import annotations

import re

import pytest

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignStatus
from insight_blueprint.validate import VALID_TRANSITIONS, validate_transition
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

_STATUS = "|".join(s.value for s in DesignStatus)
_MOVE = re.compile(rf"`({_STATUS}) → ({_STATUS})`")


def _assert_allowed(moves: list[tuple[str, str]]) -> None:
    assert moves, "the prose names no allowed move"
    for current, target in moves:
        validate_transition(DesignStatus(current), DesignStatus(target))


def _assert_refused(moves: list[tuple[str, str]]) -> None:
    assert moves, "the prose names no refused move"
    for current, target in moves:
        with pytest.raises(ValueError):
            validate_transition(DesignStatus(current), DesignStatus(target))


def _concludes_from_analyzing(moves: list[tuple[str, str]]) -> bool:
    return any(
        current == DesignStatus.analyzing and DesignStatus(target) in TERMINAL_STATUSES
        for current, target in moves
    )


class TestAnalysisDesignStatusFlow:
    """US-1 AC 3: the Status Flow of /analysis-design draws the table's moves."""

    def _flow(self) -> str:
        return section(_read_skill("analysis-design"), "### Status Flow")

    def test_the_analyzing_line_lists_every_status_the_table_allows(self) -> None:
        line = next(line for line in self._flow().splitlines() if "analyzing →" in line)
        after = line.split("analyzing →", 1)[1]
        targets = {DesignStatus(word) for word in re.findall(_STATUS, after)}
        assert targets == VALID_TRANSITIONS[DesignStatus.analyzing]

    def test_every_illegal_example_is_refused_by_the_table(self) -> None:
        _assert_refused(_MOVE.findall(unwrap(self._flow())))


class TestArchitectureStateGuard:
    """US-1 AC 3: ARCHITECTURE's state guard gives examples the table agrees with."""

    def _guard(self) -> str:
        text = (SKILLS_DIR.parent / "docs" / "ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )
        return next(line for line in text.splitlines() if "状態遷移ガード" in line)

    def test_its_allowed_example_concludes_from_analyzing(self) -> None:
        allowed = _MOVE.findall(self._guard().split("は許し")[0])
        _assert_allowed(allowed)
        assert _concludes_from_analyzing(allowed)

    def test_its_refused_example_is_refused_by_the_table(self) -> None:
        refused = self._guard().split("は許し")[-1].split("は拒む")[0]
        _assert_refused(_MOVE.findall(refused))


class TestReflectionConcludesFromAnalyzing:
    """US-1 AC 4: /analysis-reflection closes the design without a review first."""

    def _step(self) -> str:
        return unwrap(section(_read_skill("analysis-reflection"), "### Step 4"))

    def test_it_concludes_straight_from_analyzing(self) -> None:
        moves = _MOVE.findall(self._step())
        _assert_allowed(moves)
        assert _concludes_from_analyzing(moves)

    def test_a_review_of_the_result_is_optional(self) -> None:
        assert "/analysis-review is optional" in self._step()
