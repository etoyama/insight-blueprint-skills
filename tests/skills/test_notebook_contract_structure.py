"""Structure tests for the notebook contract (Epic 30 / ADR-0045).

The notebook is a plain Python script whose cells start at ``# %% <name>`` lines. The
contract once followed marimo's rules, and a generated notebook stopped on rules that had
nothing to do with the analysis. These tests hold the contract and the /analysis-notebook
SKILL.md to the plain form and to the one-step run.
"""

from __future__ import annotations

import ast
import re

import pytest

from tests.skills._markdown import section, table_rows, unwrap
from tests.skills._notebook_run import RUN, WITH_EXCLUSION, WITH_SCOPE, commands
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
TWO_STEP_WORDS = ("marimo export", "_flat.py", ".html")


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def _cells_table() -> list[list[str]]:
    return table_rows(section(_contract(), "## Cells"))[2:]


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
        assert "the design's id, title and intent" in layout
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
        assert commands(section(_contract(), "## Execution")) == [RUN]

    def test_the_skill_runs_the_notebook_with_python(self) -> None:
        step = section(_read_skill("analysis-notebook"), "### Step 4: ")
        assert commands(step) == [RUN.replace("{id}", "{design_id}")]

    def test_supplying_a_package_layers_it_onto_the_same_command(self) -> None:
        supplying = section(_contract(), "### Supplying an allowlisted package")
        assert commands(supplying) == [
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


def _results_examples() -> dict[str, dict]:
    """The `results` examples of the contract, keyed by the comment that opens each block."""
    blocks = re.findall(
        r"```python\n(.*?)```", section(_contract(), "## `results` shape"), re.DOTALL
    )
    examples: dict[str, dict] = {}
    for block in blocks:
        label = block.splitlines()[0].removeprefix("# ").strip()
        tree = ast.parse(block)
        (assign,) = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["results"]
        ]
        examples[label] = ast.literal_eval(assign.value)
    return examples


def _docstring_lines(block_label: str) -> list[str]:
    """The lines of the docstring example whose block opens with ``block_label``."""
    for block in re.findall(r"```python\n(.*?)```", _contract(), re.DOTALL):
        if block.startswith(f"# {block_label}\n"):
            docstring = ast.get_docstring(ast.parse(block), clean=False)
            assert docstring is not None
            return docstring.splitlines()
    raise AssertionError(f"no python block opens with # {block_label}")


class TestAnExplorationKeepsWhatItMeasured:
    """Epic 32 US-3 AC 1: no prediction and no pass in an exploration's results."""

    def test_the_contract_shows_one_results_example_per_form(self) -> None:
        assert set(_results_examples()) == {"confirmation", "exploration"}

    @pytest.mark.parametrize(
        "key", ["hypothesis_direction", "decision_reason", "threshold", "pass"]
    )
    def test_the_exploration_results_carry_no_prediction_and_no_pass(
        self, key: str
    ) -> None:
        exploration = _results_examples()["exploration"]
        assert key not in exploration
        for metric in exploration["metrics"].values():
            assert key not in metric

    def test_each_exploration_metric_holds_the_measured_value(self) -> None:
        metrics = _results_examples()["exploration"]["metrics"]
        assert metrics
        assert all("value" in metric for metric in metrics.values())

    def test_an_exploration_metric_may_carry_the_optional_items(self) -> None:
        (metric,) = _results_examples()["exploration"]["metrics"].values()
        assert {"effect_size", "confidence_interval", "sample_size"} <= set(metric)

    def test_the_confirmation_results_keep_the_judgment(self) -> None:
        confirmation = _results_examples()["confirmation"]
        assert "hypothesis_direction" in confirmation
        (metric,) = confirmation["metrics"].values()
        assert {"value", "threshold", "pass"} <= set(metric)

    def test_the_results_follow_the_form_of_the_design(self) -> None:
        """A saved `mixed` design reads as a confirmation; an old exploration as one."""
        rule = unwrap(section(_contract(), "## `results` shape"))
        assert "Choose the shape by the form of the design" in rule
        assert (
            "`exploratory` intent, an old exploration with a hypothesis included"
            in rule
        )

    def test_an_exploration_writes_no_pass_even_with_a_p_value(self) -> None:
        rule = unwrap(section(_contract(), "## `results` shape"))
        assert "An exploration may write a p-value but never a pass or fail" in rule

    def test_the_verdict_keeps_the_metrics_in_both_forms(self) -> None:
        verdict = unwrap(section(_contract(), "## `verdict` shape"))
        assert "The verdict keeps `metrics` in both forms" in verdict
        assert "confirmatory: persist" not in verdict

    def test_the_skill_asks_the_exploration_for_no_prediction(self) -> None:
        step = unwrap(section(_read_skill("analysis-notebook"), "### Step 3: "))
        assert "four required fields" not in step
        assert (
            "an exploration has no `hypothesis_direction`, no `decision_reason`, "
            "and no `threshold` or `pass` in its metrics"
        ) in step


class TestAConfirmationTakesItsCriterionFromTheDesign:
    """Epic 32 US-3 AC 3: the notebook copies the threshold and never makes one up."""

    @pytest.mark.parametrize(
        "text",
        [
            lambda: section(_contract(), "## `results` shape"),
            lambda: section(_read_skill("analysis-notebook"), "### Step 3: "),
        ],
        ids=["contract", "skill"],
    )
    def test_the_threshold_is_copied_from_the_primary_comparison(self, text) -> None:
        rule = unwrap(text())
        assert (
            "copy each `threshold` from the `comparison` of the design's primary metric"
        ) in rule
        assert "the notebook never makes up a threshold" in rule

    def test_a_comparison_without_a_criterion_stops_the_generation(self) -> None:
        rule = unwrap(section(_contract(), "## `results` shape"))
        assert "states no criterion, stop and suggest /analysis-design" in rule


class TestTheDocstringStatesWhatTheDesignAnswers:
    """Epic 32 US-3 AC 4: the question for an exploration, the hypothesis otherwise."""

    @pytest.mark.parametrize(
        "text",
        [
            lambda: section(_contract(), "## File layout"),
            lambda: section(_read_skill("analysis-notebook"), "### Step 3: "),
        ],
        ids=["contract", "skill"],
    )
    def test_the_docstring_names_the_question_or_the_hypothesis(self, text) -> None:
        rule = unwrap(text())
        assert "`- Question:` line with `exploration_question`" in rule
        assert "`- Hypothesis:` line with `hypothesis_statement`" in rule

    def test_the_question_and_the_hypothesis_take_the_title_escape(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert (
            "Apply the same escape to the title, the question and the hypothesis"
            in (layout)
        )

    def test_the_exploration_example_writes_the_question(self) -> None:
        lines = _docstring_lines("exploration")
        assert any(line.startswith("- Question: ") for line in lines)
        assert not any(line.startswith("- Hypothesis: ") for line in lines)
        assert "- Intent: exploratory" in lines

    def test_the_confirmation_example_writes_the_hypothesis(self) -> None:
        lines = _docstring_lines("confirmation")
        assert any(line.startswith("- Hypothesis: ") for line in lines)
        assert not any(line.startswith("- Question: ") for line in lines)
