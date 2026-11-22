"""Tests of the notebook cells the analysis note shows (Epic 28, Story 28.2).

``notebook_cells`` cuts a marimo notebook into its cells and leaves out the
data-load cell, which holds the connection values (ADR-0022, ADR-0036).
"""

from __future__ import annotations

import re

import pytest

from skills._shared import design_note_read
from skills._shared.design_note import CodeCell
from skills._shared.design_note_read import notebook_cells

CONNECTION = "/Users/secret-analyst/data/reservations.csv"

# The cells are not in contract order: the data-load cell comes second here,
# as in tests/integration/fixtures/sample_notebook.py.
NOTEBOOK = f'''import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    return (pd,)


@app.cell
def _(LineageSession, pd):
    import marimo as mo

    raw_df = pd.read_csv("{CONNECTION}")
    session = LineageSession(name="LIB-H01-analysis", design_id="LIB-H01")
    return mo, raw_df, session


@app.cell(hide_code=True)
def _(mo):
    mo.md("# LIB-H01")
    return


@app.cell
def _(raw_df):
    df_clean = raw_df.dropna()
    return (df_clean,)


if __name__ == "__main__":
    app.run()
'''


def test_every_cell_but_the_data_load_cell_comes_with_its_position_and_source() -> None:
    cells = notebook_cells(NOTEBOOK)

    assert cells == (
        CodeCell(
            position=1,
            source="@app.cell\ndef _():\n    import pandas as pd\n    return (pd,)",
        ),
        CodeCell(
            position=3,
            source='@app.cell(hide_code=True)\ndef _(mo):\n    mo.md("# LIB-H01")\n'
            "    return",
        ),
        CodeCell(
            position=4,
            source="@app.cell\ndef _(raw_df):\n    df_clean = raw_df.dropna()\n"
            "    return (df_clean,)",
        ),
    )


def test_no_cell_carries_the_connection_value() -> None:
    cells = notebook_cells(NOTEBOOK)

    assert cells
    assert all(CONNECTION not in c.source for c in cells)


def test_raw_df_bound_by_unpacking_marks_the_data_load_cell() -> None:
    text = (
        "@app.cell\ndef _(pd):\n"
        f'    raw_df, extra = pd.read_csv("{CONNECTION}"), 1\n'
        "    return (raw_df,)\n\n\n"
        "@app.cell\ndef _(raw_df):\n    return\n"
    )

    cells = notebook_cells(text)

    assert cells == (
        CodeCell(position=2, source="@app.cell\ndef _(raw_df):\n    return"),
    )


def test_a_notebook_that_does_not_parse_gives_no_code() -> None:
    assert notebook_cells("@app.cell\ndef _(:\n") is None


def test_a_file_without_cells_gives_no_code() -> None:
    assert notebook_cells(f'raw = open("{CONNECTION}").read()\n') is None


def test_a_notebook_without_a_cell_that_binds_raw_df_gives_no_code() -> None:
    text = (
        f'@app.cell\ndef _(pd):\n    df = pd.read_csv("{CONNECTION}")\n'
        "    return (df,)\n"
    )

    assert notebook_cells(text) is None


def test_a_notebook_with_two_cells_that_bind_raw_df_gives_no_code() -> None:
    text = (
        f'@app.cell\ndef _(pd):\n    raw_df = pd.read_csv("{CONNECTION}")\n'
        "    return (raw_df,)\n\n\n"
        '@app.cell\ndef _(pd):\n    raw_df = pd.read_csv("other.csv")\n'
        "    return (raw_df,)\n"
    )

    assert notebook_cells(text) is None


def test_a_function_that_is_not_a_cell_is_neither_shown_nor_counted() -> None:
    text = (
        "def helper():\n    raw_df = 1\n    return raw_df\n\n\n"
        f'@app.cell\ndef _(pd):\n    raw_df = pd.read_csv("{CONNECTION}")\n'
        "    return (raw_df,)\n\n\n"
        "@app.cell\ndef _(raw_df):\n    return\n"
    )

    cells = notebook_cells(text)

    assert cells == (
        CodeCell(position=2, source="@app.cell\ndef _(raw_df):\n    return"),
    )


# str.splitlines() also breaks on these; the tokenizer, and so ast, does not.
# Six of them shift the slice of a later cell onto the data-load cell.
NOT_LINE_BREAKS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"]


@pytest.mark.parametrize("separator", NOT_LINE_BREAKS, ids=lambda s: f"U+{ord(s):04X}")
def test_a_character_that_is_not_a_line_break_shifts_no_cell(separator: str) -> None:
    comment = f"    # {separator * 6}\n"
    text = NOTEBOOK.replace(
        "    import pandas as pd\n", comment + "    import pandas as pd\n"
    )

    cells = notebook_cells(text)

    assert cells is not None
    assert all(CONNECTION not in c.source for c in cells)
    assert [c.position for c in cells] == [1, 3, 4]
    assert cells[0].source == (
        f"@app.cell\ndef _():\n{comment}    import pandas as pd\n    return (pd,)"
    )
    assert cells[2].source == (
        "@app.cell\ndef _(raw_df):\n    df_clean = raw_df.dropna()\n"
        "    return (df_clean,)"
    )


def test_cells_of_a_notebook_with_crlf_line_ends_are_cut_at_the_cell() -> None:
    cells = notebook_cells(NOTEBOOK.replace("\n", "\r\n"))

    assert cells is not None
    assert all(CONNECTION not in c.source for c in cells)
    assert cells[2].source == (
        "@app.cell\ndef _(raw_df):\n    df_clean = raw_df.dropna()\n"
        "    return (df_clean,)"
    )


def test_a_slice_that_is_not_its_cell_gives_no_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The split of str.splitlines() is put back, so the slices are off again.
    monkeypatch.setattr(
        design_note_read,
        "_LINE_BREAK",
        re.compile(r"\r\n|[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]"),
    )
    text = NOTEBOOK.replace(
        "    import pandas as pd\n",
        "    # " + "\x0c" * 6 + "\n    import pandas as pd\n",
    )

    assert notebook_cells(text) is None
