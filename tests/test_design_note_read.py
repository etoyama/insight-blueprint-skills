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


def _assert_hides_connection(
    cells: tuple[CodeCell, ...] | None,
) -> tuple[CodeCell, ...]:
    assert cells
    assert all(CONNECTION not in c.source for c in cells)
    return cells


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
        _assert_hides_connection(notebook_cells(NOTEBOOK))

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


def _inserted(index: int, cell: str) -> str:
    cells = [_cell(n) for n in CONTRACT_CELLS]
    cells.insert(index, cell)
    return _notebook(*cells)


def _renamed(old: str, new: str) -> str:
    return _contract().replace(f"# %% {old}\n", f"{new}\n")


MARIMO = (
    "import marimo\n\napp = marimo.App()\n\n\n"
    "@app.cell\ndef _():\n    import pandas as pd\n    return (pd,)\n\n\n"
    f"@app.cell\ndef _(pd):\n    {LOAD}    return (raw_df,)\n\n\n"
    'if __name__ == "__main__":\n    app.run()\n'
)
MARIMO_WITH_PERCENT_COMMENTS = (
    "import marimo\n\napp = marimo.App()\n\n"
    "# %% imports\n@app.cell\ndef _():\n    import pandas as pd\n\n"
    f"# %% data_load\n@app.cell\ndef _(pd):\n    {LOAD}"
)

# Each way a notebook falls out of the contract's shape (US-2 AC 2). Each case
# is the contract's notebook with one thing changed, so the change is the cause.
OUT_OF_SHAPE = [
    # The cells are not the contract's seven, in order.
    pytest.param(_inserted(4, "# %% extra\nx = 1\n"), id="extra_cell"),
    pytest.param(
        _inserted(1, f'# %% config\nPATH = "{CONNECTION}"\n'),
        id="config_cell_with_the_connection",
    ),
    *(
        pytest.param(
            _notebook(*(_cell(n) for n in CONTRACT_CELLS if n != missing)),
            id=f"missing_{missing}",
        )
        for missing in CONTRACT_CELLS
    ),
    pytest.param(
        _notebook(
            *(_cell(n) for n in ("imports", "data_load", "analysis", "data_prep")),
            *(_cell(n) for n in CONTRACT_CELLS[4:]),
        ),
        id="out_of_order",
    ),
    *(
        pytest.param(
            _renamed("analysis", f"# %% {name}"), id=f"analysis_renamed_{name}"
        )
        for name in ("Analysis", "analysis_2", "config", "")
    ),
    pytest.param(_renamed("data_load", "# %% load"), id="no_cell_named_data_load"),
    pytest.param(_renamed("data_load", "# %% data_load v2"), id="data_load_v2"),
    pytest.param(_notebook(_cell("data_load")), id="only_the_data_load_cell"),
    pytest.param(
        _notebook(_contract(), "# %% data_load\nx = 1\n"), id="two_data_load_cells"
    ),
    pytest.param(
        _notebook(_contract(), _cell("data_load")),
        id="two_data_load_cells_that_both_assign_raw_df",
    ),
    # A # %% line splits the data_load cell; the second half once showed with the
    # second source's connection (Epic 30 gate).
    *(
        pytest.param(
            _contract(
                data_load=f'{LOAD}{line}\nother_df = pd.read_csv("{CONNECTION}.2")\n'
            ),
            id=f"data_load_split_by_{case}",
        )
        for case, line in [
            ("second_source", "# %% data_load (second source)"),
            ("bare", "# %%"),
            ("markdown", "# %% [markdown]"),
            ("data_load_2", "# %% data_load_2"),
        ]
    ),
    # raw_df is not bound in data_load alone.
    pytest.param(
        _contract(data_prep=f'raw_df = pd.read_csv("{CONNECTION}")\n'),
        id="raw_df_in_another_cell",
    ),
    pytest.param(
        _contract(data_prep="def reload():\n    global raw_df\n    raw_df = 1\n"),
        id="raw_df_in_a_function_of_another_cell",
    ),
    pytest.param(_contract(head=LOAD), id="raw_df_before_the_first_separator"),
    pytest.param(
        _contract(data_load=f'df = pd.read_csv("{CONNECTION}")\n'),
        id="data_load_without_raw_df",
    ),
    # A separator inside a statement.
    *(
        pytest.param(_crossing(body), id=case)
        for case, body in [
            (
                "in_a_call",
                f'raw_df = pd.read_csv(\n# %% data_prep\n    "{CONNECTION}"\n)\n',
            ),
            (
                "in_a_block",
                f'if True:\n# %% data_prep\n    raw_df = pd.read_csv("{CONNECTION}")\n',
            ),
            (
                "between_decorator_and_def",
                "raw_df = load()\n"
                f'@decorate\n# %% data_prep\ndef load():\n    return "{CONNECTION}"\n',
            ),
            (
                "in_a_bracketed_decorator",
                f'raw_df = 1\n@(\n# %% data_prep\nf)\ndef g(): return "{CONNECTION}"\n',
            ),
            ("in_a_list", f'raw_df = [\n# %% data_prep\n    "{CONNECTION}"]\n'),
            ("in_a_set", f'raw_df = {{\n# %% data_prep\n    "{CONNECTION}"}}\n'),
        ]
    ),
    # Away from data_load, so the raw_df check cannot stand in for this one.
    pytest.param(
        _notebook(
            *(_cell(n) for n in CONTRACT_CELLS[:3]),
            "# %% analysis\nresults = (\n# %% viz\n    1)\n",
            *(_cell(n) for n in CONTRACT_CELLS[5:]),
        ),
        id="in_a_statement_of_another_cell",
    ),
    # A statement other than the docstring before the first separator.
    *(
        pytest.param(_contract(head=head), id=f"head_{case}")
        for case, head in [
            ("import", '"""LIB-H01"""\nimport pandas as pd\n'),
            ("assignment", f'"""LIB-H01"""\nPATH = "{CONNECTION}"\n'),
            ("string_not_first", 'import pandas as pd\n"""not a docstring"""\n'),
            ("two_strings", '"""LIB-H01"""\n"""a second string"""\n'),
            ("f_string", 'f"""LIB-H01"""\n'),
        ]
    ),
    # Python would decode the file by the declaration; the note reads UTF-8.
    *(
        pytest.param(_contract(head=f"{before}{line}\n"), id=f"{case}{shebang}")
        for case, line in [
            ("utf_7", "# coding: utf-7"),
            ("latin_1", "# -*- coding: latin-1 -*-"),
            ("unknown_encoding", "# coding=nope"),
        ]
        for shebang, before in [
            ("", ""),
            ("_after_a_shebang", "#!/usr/bin/env python\n"),
        ]
    ),
    pytest.param(f"import pandas as pd\n\n{LOAD}", id="no_separator"),
    pytest.param(_contract(analysis="def _(:\n"), id="does_not_parse"),
    pytest.param(_contract(analysis="y = '\x00'\n"), id="null_character"),
    pytest.param(MARIMO, id="marimo"),
    pytest.param(MARIMO_WITH_PERCENT_COMMENTS, id="marimo_with_percent_comments"),
]


@pytest.mark.parametrize("text", OUT_OF_SHAPE)
def test_a_notebook_out_of_the_contracts_shape_gives_no_code(text: str) -> None:
    assert notebook_cells(text) is None


@pytest.mark.parametrize(
    "statement",
    ["x = " + "+".join(['"a"'] * 5000), "x = " + "not " * 20000 + "1"],
    ids=["a_long_sum", "a_long_negation"],
)
def test_a_file_too_deep_to_parse_gives_no_code_and_no_error(statement: str) -> None:
    # Which depth ends the parse depends on the Python version.
    cells = notebook_cells(_contract(analysis=f"{statement}\n"))

    assert cells is None or all(CONNECTION not in c.source for c in cells)


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

        cells = _assert_hides_connection(notebook_cells(text))

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
        cells = _assert_hides_connection(notebook_cells(NOTEBOOK.replace("\n", end)))

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


# Story 32.5 (Epic 32 US-5): an exploration holds no hypothesis, so the note
# reads no evidence as standing against one (ADR-0050).


def test_an_explored_design_reads_no_evidence_against_a_hypothesis(
    tmp_path: Path,
) -> None:
    from skills._shared import design_io
    from skills._shared.design_note_read import load_design_note

    insight = tmp_path / ".insight"
    (insight / "designs").mkdir(parents=True)
    design_id = design_io.create_design(
        theme_id="LIB",
        title="館ごとの期限切れ",
        analysis_intent="exploratory",
        exploration_question="期限切れはどの館で多いか",
        exploration_background="館ごとの差をまだ見ていない",
        base_dir=insight,
    )["id"]
    design_io.write_journal(
        design_id,
        {
            "events": [
                {
                    "id": f"{design_id}-E01",
                    "type": "evidence",
                    "content": "分館で少ない",
                    # An older notebook may still have written a direction.
                    "metadata": {"direction": "contradicts"},
                },
            ]
        },
        base_dir=insight,
    )
    design_io.transition_status(design_id, "explored", base_dir=insight)

    conclusion = load_design_note(design_id, base_dir=insight).conclusion

    assert conclusion is not None
    assert conclusion.contradicting_evidence == ()


# The notebook contract writes a metric's p value as "p_value"; verdicts saved
# before may hold "p". The note reads both, "p" first (#230, from Story 32.4).


def _p_of(tmp_path: Path, entry: dict) -> str | None:
    import json

    from skills._shared import design_io
    from skills._shared.design_note_read import load_design_note

    insight = tmp_path / ".insight"
    (insight / "designs").mkdir(parents=True)
    design_id = design_io.create_design(
        theme_id="LIB",
        title="館ごとの期限切れ",
        hypothesis_statement="延ばすと減る",
        hypothesis_background="7日で多い",
        base_dir=insight,
    )["id"]
    notebooks = insight / "notebooks"
    notebooks.mkdir()
    (notebooks / f"{design_id}_verdict.json").write_text(
        json.dumps({"metrics": {"差": entry}}), encoding="utf-8"
    )
    verdict = load_design_note(design_id, base_dir=insight).verdict
    assert verdict is not None
    return verdict.metrics[0].p


@pytest.mark.parametrize(
    ("entry", "p"),
    [
        ({"value": 1.8, "p_value": 0.03}, "0.03"),
        ({"value": 1.8, "p": 0.04}, "0.04"),
        ({"value": 1.8, "p": 0.04, "p_value": 0.03}, "0.04"),
        ({"value": 1.8}, None),
    ],
)
def test_the_p_value_is_read_as_the_contract_or_an_older_verdict_writes_it(
    tmp_path: Path, entry: dict, p: str | None
) -> None:
    assert _p_of(tmp_path, entry) == p
