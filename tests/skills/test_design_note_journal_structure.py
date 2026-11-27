"""The conclusion section of the analysis note against the journal skill (Epic 28, Story 28.3).

Story 29.5 removed the report's template, so the note no longer has a template to be
held equal to (Epic 29 US-5 AC 3). What stays is the journal skill's definition of an
open question, which the note reads, and a fixed sentence and a recommendation for
every terminal status.
"""

from __future__ import annotations

import re
from pathlib import Path

from insight_blueprint.models.design import CONCLUSIONS_OF, TERMINAL_STATUSES
from skills._shared.design_note import FORM_WORDS
from skills._shared.design_note_read import (
    CONCLUDE,
    NEXT_ACTION_BRANCHES,
    QUESTION,
    RESOLVES,
)
from tests.skills._markdown import section, unwrap

JOURNAL_SKILL = Path(__file__).resolve().parents[2] / "skills/analysis-journal/SKILL.md"


def test_every_terminal_status_has_a_lead_sentence_and_a_recommendation() -> None:
    # Each form opens a conclusion it can reach, and only those (Epic 32, ADR-0051).
    assert {f: set(w.lead_sentences) for f, w in FORM_WORDS.items()} == {
        f: set(statuses) for f, statuses in CONCLUSIONS_OF.items()
    }
    assert set(NEXT_ACTION_BRANCHES) == set(TERMINAL_STATUSES)


def test_open_questions_follow_the_journal_skill_definition() -> None:
    board = section(
        JOURNAL_SKILL.read_text(encoding="utf-8"), "## Open Questions (Inquiry Board)"
    )

    definition = unwrap(board)
    assert f"`{QUESTION}` event is considered **open**" in definition
    assert (
        f"no `{CONCLUDE}` event references it via `metadata.{RESOLVES}`" in definition
    )


def test_an_answered_confirmation_is_not_an_open_question() -> None:
    """Epic 35 US-4 AC 3 (ADR-0064 9): the note and the journal skill read it alike."""
    board = unwrap(
        section(
            JOURNAL_SKILL.read_text(encoding="utf-8"),
            "## Open Questions (Inquiry Board)",
        )
    )

    assert re.search(r"`asks_analyst`[^.]*`answers`[^.]*not open", board)
    reflection = unwrap(
        section(
            (JOURNAL_SKILL.parents[1] / "analysis-reflection/SKILL.md").read_text(
                encoding="utf-8"
            ),
            "### Step 2",
        )
    )
    assert re.search(r"Open Questions[^.]*/analysis-journal", reflection)
