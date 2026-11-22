"""The conclusion section of the analysis note against the report's template (Epic 28, Story 28.3).

The note's conclusion section and ``/analysis-report`` read the same records. Its
fixed sentence, the sources of its recommendation, and its open questions follow
the prose contract of apa-template.md and the journal skill; these tests catch
either side drifting (US-3 AC 5).
"""

from __future__ import annotations

import re
from pathlib import Path

from insight_blueprint.models.design import TERMINAL_STATUSES
from skills._shared.design_note import LEAD_SENTENCES
from skills._shared.design_note_read import (
    CONCLUDE,
    NEXT_ACTION_BRANCHES,
    QUESTION,
    RESOLVES,
)
from tests.skills._markdown import section, table_row, unwrap

SKILLS = Path(__file__).resolve().parents[2] / "skills"
TEMPLATE = SKILLS / "analysis-report" / "references" / "apa-template.md"
JOURNAL_SKILL = SKILLS / "analysis-journal" / "SKILL.md"


def _template_section(heading: str) -> str:
    return section(TEMPLATE.read_text(encoding="utf-8"), heading)


def _fields(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def test_every_terminal_status_has_the_abstract_lead_sentence() -> None:
    lead = _template_section("## Abstract (lead sentence)")

    assert set(LEAD_SENTENCES) == set(TERMINAL_STATUSES)
    for status, sentence in LEAD_SENTENCES.items():
        assert table_row(lead, f"`{status.value}`")[1] == sentence


def test_the_recommendation_takes_the_next_action_branch_of_the_template() -> None:
    discussion = _template_section("## Implications and Recommendation (Discussion)")

    for status, fields in NEXT_ACTION_BRANCHES.items():
        named = _fields(table_row(discussion, f"`{status.value}`")[1])
        parts = list(dict.fromkeys(p for f in fields for p in f.split(".")))
        assert named == parts, status
    assert "`decision_context`" in discussion
    assert set(NEXT_ACTION_BRANCHES) == set(TERMINAL_STATUSES)


def test_open_questions_follow_the_journal_skill_definition() -> None:
    journal = _template_section("## Journal events")
    board = section(
        JOURNAL_SKILL.read_text(encoding="utf-8"), "## Open Questions (Inquiry Board)"
    )

    assert "analysis-journal/SKILL.md#open-questions-inquiry-board" in journal
    definition = unwrap(board)
    assert f"`{QUESTION}` event is considered **open**" in definition
    assert (
        f"no `{CONCLUDE}` event references it via `metadata.{RESOLVES}`" in definition
    )
