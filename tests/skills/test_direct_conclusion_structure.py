"""Structure tests for concluding an analyzed design directly (Epic 19, Story #147).

``VALID_TRANSITIONS`` lets ``analyzing`` reach the conclusion statuses, and the
prose that tells a model or a reader which moves exist must say the same
(US-1 AC 3, AC 4). Each test reads what the prose claims and checks it against
the table, so a later change to the table that leaves the prose behind fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from insight_blueprint.models.design import DesignStatus
from insight_blueprint.validate import VALID_TRANSITIONS, validate_transition
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import _read_skill

_REPO = Path(__file__).resolve().parents[2]
_STATUS = "|".join(s.value for s in DesignStatus)
_MOVE = re.compile(rf"`({_STATUS}) → ({_STATUS})`")
_NAMED = re.compile(rf"`({_STATUS})`")


def _statuses(text: str) -> set[DesignStatus]:
    return {DesignStatus(name) for name in _NAMED.findall(text)}


def _sentence_with(prose: str, marker: str) -> str:
    """The sentence of ``prose`` (already unwrapped) that contains ``marker``.

    An English sentence ends at a period followed by a capital, so "e.g." does not
    cut one short.
    """
    for sentence in re.split(r"(?<=。)|(?<=\.)\s+(?=[A-Z])", prose):
        if marker in sentence:
            return sentence
    raise AssertionError(f"no sentence contains {marker!r}")


def _assert_refused(moves: list[tuple[str, str]]) -> None:
    assert moves, "the prose names no example of a refused move"
    for current, target in moves:
        with pytest.raises(ValueError):
            validate_transition(DesignStatus(current), DesignStatus(target))


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
        sentence = _sentence_with(unwrap(self._flow()), "Illegal moves")
        _assert_refused(_MOVE.findall(sentence))


class TestArchitectureStateGuard:
    """US-1 AC 3: ARCHITECTURE's state guard names the moves the table allows."""

    def _guard(self) -> str:
        text = (_REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        return next(line for line in text.splitlines() if "状態遷移ガード" in line)

    def test_it_names_where_analyzing_goes_as_the_table_does(self) -> None:
        reach = re.search(r"`analyzing` から進めるのは(.+?)で、", self._guard())
        assert reach, "the state guard does not say where analyzing goes"
        assert _statuses(reach.group(1)) == VALID_TRANSITIONS[DesignStatus.analyzing]

    def test_its_refused_example_is_refused_by_the_table(self) -> None:
        _assert_refused(_MOVE.findall(self._guard().split("は拒む")[0]))


class TestReflectionConcludesFromAnalyzing:
    """US-1 AC 4: /analysis-reflection closes the design without a review first."""

    def _step(self) -> str:
        return unwrap(section(_read_skill("analysis-reflection"), "### Step 4"))

    def test_it_names_every_status_a_conclusion_can_follow(self) -> None:
        sentence = _sentence_with(self._step(), "accepts a terminal status from")
        expected = {
            status
            for status, targets in VALID_TRANSITIONS.items()
            if DesignStatus.supported in targets
        }
        assert _statuses(sentence) == expected

    def test_a_review_of_the_result_is_optional(self) -> None:
        sentence = _sentence_with(self._step(), "/analysis-review")
        assert "optional" in sentence

    def test_it_does_not_send_the_design_through_a_review_first(self) -> None:
        assert "go through the review process first" not in self._step()
