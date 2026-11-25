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

from insight_blueprint.models.design import (
    CONCLUSIONS_OF,
    TERMINAL_STATUSES,
    DesignForm,
    DesignStatus,
)
from insight_blueprint.validate import valid_targets, validate_transition
from tests.skills._markdown import bold_item, section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

_STATUS = "|".join(s.value for s in DesignStatus)
_MOVE = re.compile(rf"`({_STATUS}) → ({_STATUS})`")
# The prose outside /analysis-design's Status Flow names the moves of a design
# that concludes on a verdict; the Status Flow draws each form (ADR-0048).
_FORM = DesignForm.confirmation
# The label in the Status Flow above the diagram of each form.
_DIAGRAMS = {
    "Confirmation": DesignForm.confirmation,
    "Exploration": DesignForm.exploration,
}


def _assert_allowed(moves: list[tuple[str, str]]) -> None:
    assert moves, "the prose names no allowed move"
    for current, target in moves:
        validate_transition(DesignStatus(current), DesignStatus(target), _FORM)


def _assert_refused(moves: list[tuple[str, str]]) -> None:
    assert moves, "the prose names no refused move"
    for current, target in moves:
        with pytest.raises(ValueError):
            validate_transition(DesignStatus(current), DesignStatus(target), _FORM)


def _concludes_from_analyzing(moves: list[tuple[str, str]]) -> bool:
    return any(
        current == DesignStatus.analyzing and DesignStatus(target) in TERMINAL_STATUSES
        for current, target in moves
    )


class TestAnalysisDesignStatusFlow:
    """US-1 AC 3: the Status Flow of /analysis-design draws the table's moves."""

    def _flow(self) -> str:
        return section(_read_skill("analysis-design"), "### Status Flow")

    def _diagram(self, label: str) -> str:
        found = re.search(rf"\*\*{label}\*\*.*?```\n(.*?)```", self._flow(), re.S)
        assert found, f"the Status Flow has no {label} diagram"
        return found.group(1)

    @pytest.mark.parametrize("label", list(_DIAGRAMS))
    def test_the_analyzing_line_lists_every_status_the_table_allows(
        self, label: str
    ) -> None:
        line = next(
            line for line in self._diagram(label).splitlines() if "analyzing →" in line
        )
        after = line.split("analyzing →", 1)[1]
        targets = {DesignStatus(word) for word in re.findall(_STATUS, after)}
        assert targets == valid_targets(DesignStatus.analyzing, _DIAGRAMS[label])

    @pytest.mark.parametrize("label", list(_DIAGRAMS))
    def test_the_terminal_line_lists_the_conclusions_of_the_form(
        self, label: str
    ) -> None:
        line = next(
            line for line in self._diagram(label).splitlines() if "terminal" in line
        )
        targets = {DesignStatus(word) for word in re.findall(_STATUS, line)}
        assert targets == CONCLUSIONS_OF[_DIAGRAMS[label]]

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

    def _form_part(self, label: str) -> str:
        """The bullet ``- **label**`` of Step 4: the end of one form (Epic 32, ADR-0048)."""
        step = section(_read_skill("analysis-reflection"), "### Step 4")
        return unwrap(bold_item(step, label))

    @pytest.mark.parametrize("label, form", list(_DIAGRAMS.items()))
    def test_it_concludes_straight_from_analyzing(
        self, label: str, form: DesignForm
    ) -> None:
        moves = _MOVE.findall(self._form_part(label))
        assert moves, f"the {label} part names no move"
        for current, target in moves:
            validate_transition(DesignStatus(current), DesignStatus(target), form)
        assert _concludes_from_analyzing(moves)

    def test_every_move_of_step_4_sits_in_the_part_of_its_form(self) -> None:
        in_parts = sum(
            len(_MOVE.findall(self._form_part(label))) for label in _DIAGRAMS
        )
        assert in_parts == len(_MOVE.findall(self._step()))

    def test_a_review_of_the_result_is_optional_and_offered_before_the_transition(
        self,
    ) -> None:
        step = self._step()
        assert "/analysis-review is optional" in step
        assert step.index("/analysis-review is optional") < step.index(
            "--target supported"
        )

    def test_the_review_is_asked_before_the_conclude_is_recorded(self) -> None:
        """Trial F20: a review after `conclude` brings the design back for a second one."""
        step = self._step()
        assert step.index("/analysis-review") < step.index("type: conclude")

    def test_taking_the_review_leaves_one_conclude_for_after_it(self) -> None:
        step = self._step()
        assert "record no `conclude` yet" in step
        assert "one `conclude`" in step

    def test_it_offers_no_review_once_the_design_is_concluded(self) -> None:
        """/analysis-review exits on a terminal status, so offering it after is a dead end."""
        after = self._step().split("--target inconclusive", 1)[1]
        assert "/analysis-review" not in after


class TestAnalysisReviewCoversTheResult:
    """US-1 AC 4: /analysis-review says what a review of the result leads to."""

    def test_its_scope_sends_a_reviewed_result_to_reflection(self) -> None:
        scope = unwrap(section(_read_skill("analysis-review"), "## Scope"))
        assert "review of the result" in scope
        assert "/analysis-reflection" in scope


class TestPremortemSkipsEveryTerminalStatus:
    """Epic 32 US-2 AC 5: premortem's SKIP row names the canonical terminal set."""

    def test_the_skip_row_lists_exactly_the_terminal_statuses(self) -> None:
        levels = section(_read_skill("premortem"), "## Risk Levels")
        row = next(line for line in levels.splitlines() if "`SKIP`" in line)
        named = set(re.findall(rf"`({_STATUS})`", row))
        assert named == {s.value for s in TERMINAL_STATUSES}
