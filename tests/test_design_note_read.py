"""Tests of the notebook cells the analysis note shows (Epic 28, Story 28.2).

``notebook_cells`` cuts a marimo notebook into its cells and leaves out the
data-load cell, which holds the connection values (ADR-0022, ADR-0036).
"""

from __future__ import annotations

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
