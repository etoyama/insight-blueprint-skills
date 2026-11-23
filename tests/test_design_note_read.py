"""Tests of the notebook cells the analysis note shows (Epic 28, Epic 30).

``notebook_cells`` cuts a notebook at its ``# %% <name>`` lines and leaves out
the ``data_load`` cell, which holds the connection values (ADR-0022, ADR-0045).
A notebook whose cells are not the contract's seven, in order, or whose
data-load cell cannot be told apart, gives no code at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared.design_note import CodeCell
from skills._shared.design_note_read import notebook_cells

CONNECTION = "/Users/secret-analyst/data/reservations.csv"

LOAD = f'raw_df = pd.read_csv("{CONNECTION}")\n'

CONTRACT_CELLS = (
    "imports",
    "data_load",
    "data_prep",
    "analysis",
    "viz",
    "verdict",
    "lineage",
)
BODIES = {
    "imports": "import pandas as pd\n",
    "data_load": LOAD,
    "data_prep": "df_clean = raw_df.dropna()\n",
    "analysis": 'results = {"n": len(df_clean)}\n',
    "viz": "figure_manifest = []\n",
    "verdict": 'verdict = {"results": results}\n',
    "lineage": "print(verdict)\n",
}

NOTEBOOK = f'''"""LIB-H01 — reservations

- Hypothesis: reserved books come back later
"""

# %% imports
import pandas as pd

from insight_blueprint.lineage import LineageSession

# %% data_load
{LOAD}session = LineageSession(name="LIB-H01-analysis", design_id="LIB-H01")

# %% data_prep
def keep_known(df):
    kept = df.dropna()

    return kept


df_clean = keep_known(raw_df)

# %% analysis
results = {{"n": len(df_clean)}}

# %% viz
figure_manifest = []

# %% verdict
verdict = {{"results": results}}

# %% lineage
print(verdict)
'''

PREP = (
    "# %% data_prep\n"
    "def keep_known(df):\n    kept = df.dropna()\n\n    return kept\n\n\n"
    "df_clean = keep_known(raw_df)"
)


def _cell(name: str, body: str | None = None) -> str:
    return f"# %% {name}\n" + (BODIES[name] if body is None else body)


def _notebook(*cells: str, head: str = '"""LIB-H01"""\n') -> str:
    return head + "".join(cells)


def _contract(head: str = '"""LIB-H01"""\n', **bodies: str) -> str:
    """A notebook of the contract's seven cells; *bodies* replace a cell's body."""
    return _notebook(*(_cell(n, bodies.get(n)) for n in CONTRACT_CELLS), head=head)


def _shown_cell(position: int, name: str) -> CodeCell:
    return CodeCell(position=position, name=name, source=_cell(name).rstrip("\n"))


SHOWN = tuple(
    _shown_cell(i + 1, n) for i, n in enumerate(CONTRACT_CELLS) if n != "data_load"
)


def _crossing(body: str) -> str:
    """The contract's seven names, with *body* carrying the data_prep separator."""
    return _notebook(
        _cell("imports"),
        "# %% data_load\n" + body,
        *(_cell(n) for n in CONTRACT_CELLS[3:]),
    )


class TestContractShape:
    def test_every_cell_but_data_load_comes_in_file_order_with_its_name(self) -> None:
        cells = notebook_cells(NOTEBOOK)

        assert cells == (
            CodeCell(
                position=1,
                name="imports",
                source="# %% imports\nimport pandas as pd\n\n"
                "from insight_blueprint.lineage import LineageSession",
            ),
            CodeCell(position=3, name="data_prep", source=PREP),
            CodeCell(
                position=4,
                name="analysis",
                source='# %% analysis\nresults = {"n": len(df_clean)}',
            ),
            CodeCell(position=5, name="viz", source="# %% viz\nfigure_manifest = []"),
            CodeCell(
                position=6,
                name="verdict",
                source='# %% verdict\nverdict = {"results": results}',
            ),
            CodeCell(position=7, name="lineage", source="# %% lineage\nprint(verdict)"),
        )

    def test_no_cell_carries_the_connection_value(self) -> None:
        cells = notebook_cells(NOTEBOOK)

        assert cells
        assert all(CONNECTION not in c.source for c in cells)

    def test_the_sample_notebook_of_the_contract_is_cut_into_six_cells(self) -> None:
        sample = Path("tests/integration/fixtures/sample_notebook.py").read_text(
            "utf-8"
        )

        cells = notebook_cells(sample)

        assert cells is not None
        assert [(c.position, c.name) for c in cells] == [
            (1, "imports"),
            (3, "data_prep"),
            (4, "analysis"),
            (5, "viz"),
            (6, "verdict"),
            (7, "lineage"),
        ]
        assert all("LineageSession(name=" not in c.source for c in cells)

    @pytest.mark.parametrize("line", ["# coding: utf-8", "# -*- coding: UTF8 -*-"])
    def test_a_declared_utf_8_encoding_is_cut(self, line: str) -> None:
        assert notebook_cells(_contract(head=f"{line}\n")) == SHOWN

    def test_a_coding_comment_after_the_second_line_declares_nothing(self) -> None:
        assert notebook_cells(_contract(head="\n\n# coding: utf-7\n")) == SHOWN

    def test_a_notebook_without_a_docstring_is_cut(self) -> None:
        assert notebook_cells(_contract(head="")) == SHOWN

    def test_comments_and_blank_lines_may_come_before_the_first_separator(
        self,
    ) -> None:
        text = _contract(head='# generated\n\n"""LIB-H01"""\n\n')

        assert notebook_cells(text) == SHOWN

    def test_raw_df_bound_by_unpacking_marks_the_data_load_cell(self) -> None:
        load = f'raw_df, extra = pd.read_csv("{CONNECTION}"), 1\n'

        assert notebook_cells(_contract(data_load=load)) == SHOWN

    def test_a_separator_after_an_indented_block_starts_the_next_cell(self) -> None:
        text = _contract(data_prep="def f():\n    return 1\n", analysis="y = f()\n")

        cells = notebook_cells(text)

        assert cells is not None
        assert cells[1:3] == (
            CodeCell(
                position=3,
                name="data_prep",
                source="# %% data_prep\ndef f():\n    return 1",
            ),
            CodeCell(position=4, name="analysis", source="# %% analysis\ny = f()"),
        )

    def test_an_indented_percent_comment_is_not_a_separator(self) -> None:
        text = _contract(data_prep="if True:\n    # %% not_a_cell\n    x = 1\n")

        cells = notebook_cells(text)

        assert cells is not None
        assert [c.name for c in cells] == [
            n for n in CONTRACT_CELLS if n != "data_load"
        ]
        assert cells[1].source == (
            "# %% data_prep\nif True:\n    # %% not_a_cell\n    x = 1"
        )


class TestTheCellsAreTheContractsSeven:
    """Code shows only when the cells are the contract's seven, in order."""

    def test_an_extra_cell(self) -> None:
        cells = [_cell(n) for n in CONTRACT_CELLS]
        cells.insert(4, "# %% extra\nx = 1\n")

        assert notebook_cells(_notebook(*cells)) is None

    # A missing data_load cell is test_no_cell_named_data_load.
    @pytest.mark.parametrize("missing", [n for n in CONTRACT_CELLS if n != "data_load"])
    def test_a_missing_cell(self, missing: str) -> None:
        text = _notebook(*(_cell(n) for n in CONTRACT_CELLS if n != missing))

        assert notebook_cells(text) is None

    def test_cells_out_of_order(self) -> None:
        order = ["imports", "data_load", "analysis", "data_prep", "viz", "verdict"]
        text = _notebook(*(_cell(n) for n in [*order, "lineage"]))

        assert notebook_cells(text) is None

    @pytest.mark.parametrize("name", ["Analysis", "analysis_2", "config", ""])
    def test_a_renamed_cell(self, name: str) -> None:
        text = _contract().replace("# %% analysis\n", f"# %% {name}\n")

        assert notebook_cells(text) is None

    @pytest.mark.parametrize(
        "line",
        [
            "# %% data_load (second source)",
            "# %%",
            "# %% [markdown]",
            "# %% data_load_2",
        ],
        ids=["second_source", "bare", "markdown", "data_load_2"],
    )
    def test_a_percent_line_that_splits_the_data_load_cell(self, line: str) -> None:
        # The second half once showed: it held the second source's connection.
        load = f'{LOAD}{line}\nother_df = pd.read_csv("{CONNECTION}.2")\n'

        assert notebook_cells(_contract(data_load=load)) is None

    def test_a_notebook_of_only_the_data_load_cell(self) -> None:
        assert notebook_cells(_notebook(_cell("data_load"))) is None

    def test_a_config_cell_that_holds_the_connection(self) -> None:
        cells = [_cell(n) for n in CONTRACT_CELLS]
        cells.insert(1, f'# %% config\nPATH = "{CONNECTION}"\n')

        assert notebook_cells(_notebook(*cells)) is None


class TestOutOfShape:
    """Each way a notebook falls out of the shape gives no code (US-2 AC 2)."""

    def test_no_cell_named_data_load(self) -> None:
        text = _contract().replace("# %% data_load\n", "# %% load\n")

        assert notebook_cells(text) is None

    def test_two_cells_named_data_load(self) -> None:
        text = _notebook(_contract(), "# %% data_load\nx = 1\n")

        assert notebook_cells(text) is None

    def test_two_cells_named_data_load_that_both_assign_raw_df(self) -> None:
        text = _notebook(_contract(), _cell("data_load"))

        assert notebook_cells(text) is None

    def test_raw_df_assigned_in_another_cell(self) -> None:
        prep = f'raw_df = pd.read_csv("{CONNECTION}")\n'

        assert notebook_cells(_contract(data_prep=prep)) is None

    def test_raw_df_assigned_in_a_function_of_another_cell(self) -> None:
        prep = "def reload():\n    global raw_df\n    raw_df = 1\n"

        assert notebook_cells(_contract(data_prep=prep)) is None

    def test_raw_df_assigned_before_the_first_separator(self) -> None:
        assert notebook_cells(_contract(head=LOAD)) is None

    def test_a_data_load_cell_that_does_not_assign_raw_df(self) -> None:
        load = f'df = pd.read_csv("{CONNECTION}")\n'

        assert notebook_cells(_contract(data_load=load)) is None

    @pytest.mark.parametrize(
        "body",
        [
            f'raw_df = pd.read_csv(\n# %% data_prep\n    "{CONNECTION}"\n)\n',
            f'if True:\n# %% data_prep\n    raw_df = pd.read_csv("{CONNECTION}")\n',
            "raw_df = load()\n"
            f'@decorate\n# %% data_prep\ndef load():\n    return "{CONNECTION}"\n',
        ],
        ids=["in_a_call", "in_a_block", "between_decorator_and_def"],
    )
    def test_a_separator_inside_a_statement(self, body: str) -> None:
        assert notebook_cells(_crossing(body)) is None

    @pytest.mark.parametrize(
        "head",
        [
            '"""LIB-H01"""\nimport pandas as pd\n',
            f'"""LIB-H01"""\nPATH = "{CONNECTION}"\n',
            'import pandas as pd\n"""not a docstring"""\n',
            '"""LIB-H01"""\n"""a second string"""\n',
            'f"""LIB-H01"""\n',
        ],
        ids=["import", "assignment", "string_not_first", "two_strings", "f_string"],
    )
    def test_a_statement_other_than_the_docstring_before_the_first_separator(
        self, head: str
    ) -> None:
        assert notebook_cells(_contract(head=head)) is None

    @pytest.mark.parametrize(
        "body",
        [
            f'raw_df = 1\n@(\n# %% data_prep\nf)\ndef g(): return "{CONNECTION}"\n',
            f'raw_df = [\n# %% data_prep\n    "{CONNECTION}"]\n',
            f'raw_df = {{\n# %% data_prep\n    "{CONNECTION}"}}\n',
        ],
        ids=["in_a_bracketed_decorator", "in_a_list", "in_a_set"],
    )
    def test_a_separator_inside_brackets(self, body: str) -> None:
        assert notebook_cells(_crossing(body)) is None

    @pytest.mark.parametrize(
        "line", ["# coding: utf-7", "# -*- coding: latin-1 -*-", "# coding=nope"]
    )
    @pytest.mark.parametrize("before", ["", "#!/usr/bin/env python\n"])
    def test_a_declared_encoding_other_than_utf_8(self, line: str, before: str) -> None:
        # Python would decode the file by the declaration; the note reads UTF-8.
        assert notebook_cells(_contract(head=f"{before}{line}\n")) is None

    @pytest.mark.parametrize(
        "statement",
        ["x = " + "+".join(['"a"'] * 5000), "x = " + "not " * 20000 + "1"],
        ids=["a_long_sum", "a_long_negation"],
    )
    def test_a_file_too_deep_to_parse_gives_no_code_and_no_error(
        self, statement: str
    ) -> None:
        # Which depth ends the parse depends on the Python version.
        cells = notebook_cells(_contract(analysis=f"{statement}\n"))

        assert cells is None or all(CONNECTION not in c.source for c in cells)

    def test_no_separator(self) -> None:
        assert notebook_cells(f"import pandas as pd\n\n{LOAD}") is None

    def test_a_file_that_does_not_parse(self) -> None:
        assert notebook_cells(_contract(analysis="def _(:\n")) is None

    def test_a_file_with_a_null_character(self) -> None:
        assert notebook_cells(_contract(analysis="y = '\x00'\n")) is None

    def test_a_marimo_notebook(self) -> None:
        text = (
            "import marimo\n\napp = marimo.App()\n\n\n"
            "@app.cell\ndef _():\n    import pandas as pd\n    return (pd,)\n\n\n"
            f"@app.cell\ndef _(pd):\n    {LOAD}    return (raw_df,)\n\n\n"
            'if __name__ == "__main__":\n    app.run()\n'
        )

        assert notebook_cells(text) is None

    def test_a_marimo_notebook_with_percent_comments_between_its_cells(self) -> None:
        text = (
            "import marimo\n\napp = marimo.App()\n\n"
            "# %% imports\n@app.cell\ndef _():\n    import pandas as pd\n\n"
            f"# %% data_load\n@app.cell\ndef _(pd):\n    {LOAD}"
        )

        assert notebook_cells(text) is None


class TestPercentInAString:
    """A ``# %%`` written in a string is text, not a separator (US-2 AC 3)."""

    def test_a_line_of_a_multi_line_string_stays_in_its_cell(self) -> None:
        prep = 'note = """\n# %% data_load\n"""\ndf_clean = raw_df\n'

        cells = notebook_cells(_contract(data_prep=prep))

        assert cells is not None
        assert cells[1] == CodeCell(
            position=3, name="data_prep", source=f"# %% data_prep\n{prep.rstrip()}"
        )

    def test_a_line_of_the_docstring_is_not_a_separator(self) -> None:
        text = _contract(head='"""LIB-H01\n# %% data_load\n"""\n')

        assert notebook_cells(text) == SHOWN

    def test_a_string_in_the_data_load_cell_hides_with_its_cell(self) -> None:
        load = (
            f'query = """\n# %% shown\n{CONNECTION}\n"""\nraw_df = pd.read_sql(query)\n'
        )

        assert notebook_cells(_contract(data_load=load)) == SHOWN

    def test_a_one_line_string_is_not_a_separator(self) -> None:
        cells = notebook_cells(_contract(data_prep='mark = "# %% x"\n'))

        assert cells is not None
        assert [c.name for c in cells] == [
            n for n in CONTRACT_CELLS if n != "data_load"
        ]


class TestSeparatorLine:
    @pytest.mark.parametrize(
        "line",
        ["# %% data_load", "# %%data_load", "# %%   data_load  ", "# %%\tdata_load"],
    )
    def test_the_name_is_the_rest_of_the_line_without_its_outer_spaces(
        self, line: str
    ) -> None:
        text = _contract().replace("# %% data_load\n", f"{line}\n")

        assert notebook_cells(text) == SHOWN

    @pytest.mark.parametrize("line", ["#%% data_load", "# % % data_load", "#  %% x"])
    def test_a_comment_that_does_not_start_with_the_marker_is_a_comment(
        self, line: str
    ) -> None:
        assert notebook_cells(_contract(data_load=f"{LOAD}{line}\n")) == SHOWN

    def test_a_name_with_more_words_is_another_name(self) -> None:
        text = _contract().replace("# %% data_load\n", "# %% data_load v2\n")

        assert notebook_cells(text) is None


class TestSource:
    def test_a_cell_starts_at_its_separator_line_and_drops_its_last_blank_lines(
        self,
    ) -> None:
        text = _contract(data_prep="\n\nx = 1\n\n  \n", lineage="y = 2\n\n\n")

        cells = notebook_cells(text)

        assert cells is not None
        assert cells[1].source == "# %% data_prep\n\n\nx = 1"
        assert cells[-1].source == "# %% lineage\ny = 2"

    def test_a_cell_keeps_its_comments_and_inner_blank_lines_as_written(self) -> None:
        body = "# why: drop unknowns\nx = 1  # one\n\n\ny = 'a'  \t# two"

        cells = notebook_cells(_contract(data_prep=f"{body}\n"))

        assert cells is not None
        assert cells[1] == CodeCell(
            position=3, name="data_prep", source=f"# %% data_prep\n{body}"
        )

    def test_a_cell_without_code_is_still_listed(self) -> None:
        cells = notebook_cells(_contract(data_prep=""))

        assert cells is not None
        assert cells[1] == CodeCell(
            position=3, name="data_prep", source="# %% data_prep"
        )


# str.splitlines() also breaks on these; the tokenizer, and so ast, does not.
NOT_LINE_BREAKS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "]


class TestLineEnds:
    """A cut that is off by a line would show the data-load cell (Epic 28 gate)."""

    @pytest.mark.parametrize("char", NOT_LINE_BREAKS, ids=lambda s: f"U+{ord(s):04X}")
    def test_a_character_that_is_not_a_line_break_shifts_no_cell(
        self, char: str
    ) -> None:
        comment = f"# {char * 6}\n"
        text = NOTEBOOK.replace(
            "import pandas as pd\n", comment + "import pandas as pd\n"
        )

        cells = notebook_cells(text)

        assert cells is not None
        assert all(CONNECTION not in c.source for c in cells)
        assert [c.position for c in cells] == [1, 3, 4, 5, 6, 7]
        assert cells[0].source.startswith(
            "# %% imports\n" + comment + "import pandas as pd\n"
        )
        assert cells[1].source == PREP

    @pytest.mark.parametrize("char", NOT_LINE_BREAKS, ids=lambda s: f"U+{ord(s):04X}")
    def test_such_a_character_before_a_marker_in_a_string_makes_no_separator(
        self, char: str
    ) -> None:
        # str.splitlines() would put "# %% leak" at the start of a line.
        load = f'note = "{char}# %% leak"\n{LOAD}'

        assert notebook_cells(_contract(data_load=load)) == SHOWN

    @pytest.mark.parametrize("end", ["\r\n", "\r"], ids=["CRLF", "CR"])
    def test_cells_of_a_notebook_with_other_line_ends_are_cut_at_the_cell(
        self, end: str
    ) -> None:
        cells = notebook_cells(NOTEBOOK.replace("\n", end))

        assert cells is not None
        assert all(CONNECTION not in c.source for c in cells)
        assert [c.position for c in cells] == [1, 3, 4, 5, 6, 7]
        assert cells[1].source == PREP

    def test_a_file_without_a_final_line_end_is_cut(self) -> None:
        assert notebook_cells(_contract().rstrip("\n")) == SHOWN

    def test_a_form_feed_before_a_separator_keeps_the_line_out_of_the_cut(
        self,
    ) -> None:
        # Not at column 0, so not a separator: the line stays in the data-load cell.
        load = f'{LOAD}\x0c# %% tail\nPATH = "{CONNECTION}"\n'

        assert notebook_cells(_contract(data_load=load)) == SHOWN


def test_no_shared_module_tells_a_marimo_cell_apart() -> None:
    for module in Path("skills/_shared").glob("*.py"):
        text = module.read_text("utf-8")
        assert "app.cell" not in text, module
        assert "marimo" not in text, module
