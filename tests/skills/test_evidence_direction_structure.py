"""Structure tests for the direction of a journal evidence event (Epic 32 / ADR-0050).

An exploration answers a question without a prediction, so its evidence cannot lean for or
against anything. The notebook contract once gave exploratory evidence a direction by
whether it matched the prediction. These tests hold the contract and /analysis-journal to
one meaning of `direction`: the lean against the hypothesis of a confirmation.
"""

from __future__ import annotations

import re

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"


def _mapping() -> str:
    return section(CONTRACT.read_text(encoding="utf-8"), "## verdict → journal events")


class TestAnExplorationsEvidenceHasNoDirection:
    """US-3 AC 2: the verdict of an exploration maps to evidence without a direction."""

    def test_the_exploration_evidence_sets_no_direction(self) -> None:
        rule = unwrap(_mapping())
        assert (
            "exploration: leave `metadata.direction` out of every evidence event"
        ) in rule

    def test_no_rule_leans_the_evidence_by_a_prediction(self) -> None:
        """A rule like "matches prediction → supports" would bring the guess back."""
        assert not re.search(
            r"predict(ed|ion)", CONTRACT.read_text(encoding="utf-8"), re.I
        )

    def test_the_confirmation_keeps_its_direction(self) -> None:
        rule = unwrap(_mapping())
        assert "confirmation: `supported`→`supports`, `rejected`→`contradicts`" in rule

    def test_an_ambiguous_exploration_still_routes_to_a_question(self) -> None:
        rule = unwrap(_mapping())
        assert '`confidence_level == "ambiguous"` → emit a `question`' in rule


class TestTheJournalSaysWhatDirectionLeansAgainst:
    """US-3 AC 5: `direction` is against the hypothesis; a guess goes to `hypothesize`."""

    def _evidence_row(self) -> str:
        convention = section(
            _read_skill("analysis-journal"), "## InsightType Convention"
        )
        return unwrap(" | ".join(table_row(convention, "`evidence`")))

    def test_direction_is_the_lean_against_the_hypothesis(self) -> None:
        assert "lean against `hypothesis_statement`" in self._evidence_row()

    def test_an_explorations_evidence_has_no_direction(self) -> None:
        assert "an exploration's evidence has no `direction`" in self._evidence_row()

    def test_a_guess_during_an_exploration_is_a_hypothesize_event(self) -> None:
        convention = unwrap(
            section(_read_skill("analysis-journal"), "## InsightType Convention")
        )
        assert (
            "A guess formed during an exploration is a `hypothesize` event, "
            "not a `direction`"
        ) in convention
