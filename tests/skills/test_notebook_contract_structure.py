"""Structure tests for the notebook contract (Epic 30 / ADR-0045).

The notebook is a plain Python script whose cells start at ``# %% <name>`` lines. The
contract once followed marimo's rules, and a generated notebook stopped on rules that had
nothing to do with the analysis. These tests hold the contract and the /analysis-notebook
SKILL.md to the plain form and to the one-step run.
"""

from __future__ import annotations

import re

import pytest

from tests.skills._markdown import section, table_rows, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
CELL_NAMES = [
    "imports",
    "data_load",
    "data_prep",
    "analysis",
    "viz",
    "verdict",
    "lineage",
]
CONTRACT_VARIABLES = {
    "raw_df": "data_load",
    "session": "data_load",
    "df_clean": "data_prep",
    "results": "analysis",
    "figure_manifest": "viz",
    "verdict": "verdict",
}
RUN = (
    'uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook '
    "python .insight/notebooks/{id}.py"
)
TWO_STEP_WORDS = ("marimo export", "_flat.py", ".html")
# `--with insight-blueprint-lineage` would layer the frozen PyPI copy over the plugin's
# own source, so each place that tells when to pass `--with` names the exclusion.
WITH_SCOPE = "in neither the `notebook` extra nor the default allowlist"
WITH_EXCLUSION = (
    "never pass a default-allowlist package such as `insight_blueprint` to `--with`"
)


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def _cells_table() -> list[list[str]]:
    return table_rows(section(_contract(), "## Cells"))[2:]


def _commands(markdown: str) -> list[str]:
    """The shell commands of the bash blocks, with ``\\`` continuations joined."""
    blocks = re.findall(r"```bash\n(.*?)```", markdown, re.DOTALL)
    joined = [re.sub(r"\\\n\s*", "", block) for block in blocks]
    return [
        line.strip()
        for block in joined
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class TestTheContractLaysOutSevenPercentCells:
    """US-1 AC 1: seven named cells, a docstring first, each variable in one cell."""

    def test_the_cells_are_the_seven_names_in_order(self) -> None:
        assert [row[0] for row in _cells_table()] == [f"`{n}`" for n in CELL_NAMES]

    def test_a_cell_starts_at_a_line_that_names_it(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert "`# %% <name>`" in layout
        assert "at the start of a line" in layout
        assert "up to the next `# %%` line" in layout

    def test_the_notebook_has_the_seven_cells_and_no_other_percent_line(
        self,
    ) -> None:
        """Epic 30 gate: a stray `# %%` line in data_load showed its second half."""
        for text in (
            section(_contract(), "## File layout"),
            section(_read_skill("analysis-notebook"), "### Step 3: "),
        ):
            rule = unwrap(text)
            assert "exactly these seven cells, in this order" in rule
            assert "Write no other `# %%` line" in rule
            assert "read a second source inside the `data_load` cell" in rule

    def test_the_file_opens_with_a_docstring_of_the_design(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert "opens with a docstring" in layout
        assert "the design's id, title, hypothesis and intent" in layout
        assert "Only the docstring comes before the first `# %%` line" in layout

    def test_the_docstring_escapes_what_would_end_it(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert 'write each `\\` as `\\\\` and each `"` as `\\"`' in layout

    @pytest.mark.parametrize(("variable", "cell"), CONTRACT_VARIABLES.items())
    def test_each_contract_variable_belongs_to_one_cell(
        self, variable: str, cell: str
    ) -> None:
        owners = [row[0] for row in _cells_table() if f"`{variable}`" in row[1]]
        assert owners == [f"`{cell}`"]

    def test_a_contract_variable_is_assigned_only_in_its_cell(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert "Assign each contract variable only in the cell that makes it" in layout

    def test_every_import_lives_in_the_imports_cell(self) -> None:
        """A client import in data_load would be hidden from the analysis note."""
        layout = unwrap(section(_contract(), "## File layout"))
        assert "Put every import in the `imports` cell" in layout
        assert "the source's client library" in layout

    def test_connection_values_are_written_only_in_data_load(self) -> None:
        """ADR-0022: the note hides only data_load, so a value elsewhere would show."""
        sentence = "Write every `connection` value only in the `data_load` cell"
        assert sentence in unwrap(section(_contract(), "## File layout"))
        assert sentence in unwrap(
            section(_read_skill("analysis-notebook"), "### Step 3: ")
        )
        assert "the client that takes one" in unwrap(
            section(_contract(), "## File layout")
        )

    def test_every_delimiter_in_the_examples_carries_only_a_name(self) -> None:
        lines = re.findall(r"^# %%.*$", _contract(), re.M)
        assert lines
        assert all(re.fullmatch(r"# %% \w+", line) for line in lines), lines

    def test_the_contract_does_not_mention_marimo(self) -> None:
        assert "marimo" not in _contract().lower()


class TestTheRunIsOneStep:
    """US-1 AC 3: the contract and the SKILL.md run the notebook with one command."""

    def test_the_contract_runs_the_notebook_with_python(self) -> None:
        assert _commands(section(_contract(), "## Execution")) == [RUN]

    def test_the_skill_runs_the_notebook_with_python(self) -> None:
        step = section(_read_skill("analysis-notebook"), "### Step 4: ")
        assert _commands(step) == [RUN.replace("{id}", "{design_id}")]

    def test_supplying_a_package_layers_it_onto_the_same_command(self) -> None:
        supplying = section(_contract(), "### Supplying an allowlisted package")
        assert _commands(supplying) == [
            RUN.replace("--extra notebook", "--extra notebook --with scikit-learn")
        ]

    @pytest.mark.parametrize(
        "text",
        [
            lambda: section(_contract(), "### Supplying an allowlisted package"),
            lambda: section(_read_skill("analysis-notebook"), "## Prerequisites"),
        ],
        ids=["contract", "skill"],
    )
    def test_with_supplies_only_packages_outside_the_plugin_env(self, text) -> None:
        rule = unwrap(text())
        assert WITH_SCOPE in rule
        assert WITH_EXCLUSION in rule

    @pytest.mark.parametrize("word", TWO_STEP_WORDS)
    def test_the_two_step_run_is_gone(self, word: str) -> None:
        assert word not in _contract()
        assert word not in _read_skill("analysis-notebook")

    def test_the_skill_does_not_mention_marimo(self) -> None:
        assert "marimo" not in _read_skill("analysis-notebook").lower()

    def test_the_skill_generates_the_seven_cells_by_name(self) -> None:
        step = unwrap(section(_read_skill("analysis-notebook"), "### Step 3: "))
        listed = re.findall(r"^- `# %% (\w+)`", step.replace(" - ", "\n- "), re.M)
        assert listed == CELL_NAMES
