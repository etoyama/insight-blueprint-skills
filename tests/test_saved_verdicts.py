"""A verdict saved before Epic 33 comes out with the values it had (Epic 33 US-1 AC 5, ADR-0052).

The new items of a metric are all optional, so a project's saved verdicts need
no rewrite. The expected values were taken from the code before the Epic; the
columns are those ADR-0052 8 keeps (Story 33.2).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared.design_note import render_note
from skills._shared.design_note_read import load_design_note
from tests._saved_verdicts import (
    NOTE_TABLES,
    SAVED_VERDICTS,
    save_design_with_verdict,
    table_rows,
)


def _metric_table(insight: Path, design_id: str) -> list[list[str]] | None:
    note = str(render_note(load_design_note(design_id, base_dir=insight)))
    values = note.split("指標の値", 1)[1].split("<h3", 1)[0]
    table = re.search(r"<table.*?</table>", values, re.S)
    return table_rows(table.group(0)) if table else None


@pytest.mark.parametrize("name", SAVED_VERDICTS)
def test_the_note_tabulates_a_saved_verdict_with_the_values_it_had(
    tmp_path: Path, name: str
) -> None:
    insight = tmp_path / ".insight"
    design_id = save_design_with_verdict(insight, *SAVED_VERDICTS[name])

    assert _metric_table(insight, design_id) == NOTE_TABLES[name]
