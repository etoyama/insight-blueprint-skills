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

from tests.docs._changelog import changelog_entry
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
        "key",
        [
            "hypothesis_direction",
            "decision_reason",
            "threshold",
            "pass",
            "support_line",
            "reject_line",
            "judgment",
        ],
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
        assert {"effect_size", "interval", "sample_size"} <= set(metric)

    def test_the_confirmation_results_keep_the_judgment(self) -> None:
        assert "hypothesis_direction" in _results_examples()["confirmation"]

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
            "and no line, judgment, `threshold` or `pass` in its metrics"
        ) in step


class TestAConfirmationTakesItsCriterionFromTheDesign:
    """Epic 32 US-3 AC 3, Epic 33 US-1 AC 1: the notebook copies the criterion."""

    @pytest.mark.parametrize(
        "text",
        [
            lambda: section(_contract(), "## `results` shape"),
            lambda: section(_read_skill("analysis-notebook"), "### Step 3: "),
        ],
        ids=["contract", "skill"],
    )
    def test_the_lines_and_the_threshold_are_copied_from_the_comparison(
        self, text
    ) -> None:
        rule = unwrap(text())
        assert (
            "copy the primary metric's `support_line` and `reject_line`, and each "
            "other metric's `threshold`, from that metric's own `comparison`"
        ) in rule
        assert "the notebook never makes up a line or a threshold" in rule

    def test_a_confirmation_without_a_criterion_stops_before_the_analysis(
        self,
    ) -> None:
        step = unwrap(section(_read_skill("analysis-notebook"), "### Step 1: "))
        assert (
            "If a confirmation has no primary metric whose `comparison` states its "
            "criterion, stop before any transition"
        ) in step

    @pytest.mark.parametrize(
        "text",
        [
            lambda: section(_contract(), "## `results` shape"),
            lambda: section(_read_skill("analysis-notebook"), "### Step 1: "),
        ],
        ids=["contract", "skill"],
    )
    def test_a_started_design_without_a_criterion_is_derived_not_edited(
        self, text
    ) -> None:
        """Epic 33: a design that began its analysis keeps its criterion (ADR-0053)."""
        rule = unwrap(text())
        assert (
            "a design that began its analysis cannot take a criterion any more, so "
            "suggest deriving a new design with /analysis-design (`parent_id`)"
        ) in rule

    def test_the_example_labels_are_not_part_of_a_notebook(self) -> None:
        layout = unwrap(section(_contract(), "## File layout"))
        assert "only labels the example; a notebook starts with its docstring" in layout


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


LINES = {"support_line", "reject_line"}
JUDGMENTS = {"supported", "rejected", "inconclusive"}
PASS_ITEMS = {"threshold", "pass"}
INTERVAL_KEYS = {"kind", "level", "lower", "upper"}
GROUP_ROW_KEYS = {"group", "value", "effect_size", "interval", "sample_size", "p_value"}


def _confirmation_metrics() -> dict[str, dict]:
    return _results_examples()["confirmation"]["metrics"]


def _judged(metrics: dict[str, dict]) -> list[dict]:
    return [metric for metric in metrics.values() if "judgment" in metric]


def _grouped(metrics: dict[str, dict]) -> dict[str, dict]:
    return {name: metric for name, metric in metrics.items() if "groups" in metric}


def _intervals(value: object) -> list[dict]:
    """Every object under *value* that holds bounds, whatever key it sits under."""
    if isinstance(value, list):
        return [found for item in value for found in _intervals(item)]
    if not isinstance(value, dict):
        return []
    own = [value] if {"lower", "upper"} <= set(value) else []
    return own + [found for item in value.values() for found in _intervals(item)]


def _results_rule() -> str:
    return unwrap(section(_contract(), "## `results` shape"))


def _skill_analysis_step() -> str:
    return unwrap(section(_read_skill("analysis-notebook"), "### Step 3: "))


class TestAPrimaryMetricHoldsItsLinesAndItsJudgment:
    """Epic 33 US-1 AC 1, AC 2: two lines and one of three judgments (ADR-0052)."""

    def test_the_example_judges_a_metric_by_its_lines(self) -> None:
        judged = _judged(_confirmation_metrics())
        assert judged
        for metric in judged:
            assert LINES & set(metric)
            assert metric["judgment"] in JUDGMENTS
            for line in LINES & set(metric):
                assert isinstance(metric[line], int | float)

    def test_the_example_shows_the_range_between_the_lines(self) -> None:
        """A value between the two lines is the case a pass could not say."""
        between = [
            metric
            for metric in _judged(_confirmation_metrics())
            if LINES <= set(metric)
            and min(metric["support_line"], metric["reject_line"])
            < metric["value"]
            < max(metric["support_line"], metric["reject_line"])
        ]
        assert between
        assert all(metric["judgment"] == "inconclusive" for metric in between)

    def test_a_judged_metric_is_not_also_passed_or_failed(self) -> None:
        for metric in _judged(_confirmation_metrics()):
            assert not PASS_ITEMS & set(metric)

    def test_a_metric_with_a_threshold_or_a_pass_holds_no_line_and_no_judgment(
        self,
    ) -> None:
        passed = [
            metric
            for metric in _confirmation_metrics().values()
            if PASS_ITEMS & set(metric)
        ]
        assert passed
        for metric in passed:
            assert not (LINES | {"judgment"}) & set(metric)

    @pytest.mark.parametrize(
        "sentence",
        [
            "The primary metric holds the criterion as `support_line` and "
            "`reject_line`, both numbers, and its `judgment`",
            "Write at least one of the two lines; a criterion of one line writes "
            "only `support_line`",
            "`judgment` is `supported`, `rejected` or `inconclusive`",
            "A value between the two lines is `inconclusive`",
            "Never say one of the three judgments with `pass`",
            "`hypothesis_direction` never disagrees with the `judgment` of the "
            "primary metric",
            "A secondary or guardrail metric holds one `threshold` and whether it "
            "passed (`pass`), and no line and no `judgment`",
            "Never write a `threshold` or a `pass` in the primary metric",
        ],
    )
    def test_the_contract_states_the_rule(self, sentence: str) -> None:
        assert sentence in _results_rule()

    def test_the_skill_writes_the_lines_and_the_judgment_in_the_primary_metric(
        self,
    ) -> None:
        step = _skill_analysis_step()
        assert (
            "the primary metric holds `support_line` and `reject_line` (at least "
            "one) and its `judgment`, never a `threshold` or a `pass`"
        ) in step
        assert (
            "a secondary or guardrail metric holds a `threshold` and a `pass`, "
            "never a line or a `judgment`"
        ) in step

    def test_an_exploration_holds_no_line_and_no_judgment(self) -> None:
        assert (
            "its metrics have no line, no `judgment`, no `threshold` and no `pass`"
        ) in _results_rule()


class TestAnIntervalNamesItsKind:
    """Epic 33 US-2 AC 1: the interval of a value says which interval it is."""

    def test_every_interval_of_the_examples_names_its_kind(self) -> None:
        intervals = _intervals(list(_results_examples().values()))
        assert intervals
        assert all(set(interval) == INTERVAL_KEYS for interval in intervals)

    def test_the_examples_show_more_than_one_kind(self) -> None:
        kinds = {
            interval["kind"]
            for interval in _intervals(list(_results_examples().values()))
        }
        assert len(kinds) > 1

    def test_the_optional_items_list_the_interval_with_its_four_keys(self) -> None:
        items = section(_contract(), "## Optional metric items")
        (row,) = [r for r in table_rows(items) if r[0] == "`interval`"]
        assert row[1] == (
            '`{"kind": str, "level": float, "lower": float, "upper": float}`'
        )
        assert "an open string" in row[2]

    @pytest.mark.parametrize(
        "sentence",
        [
            "`interval` without `kind`",
            "Write the interval of a value in `interval`, with its `kind`; never "
            "write `confidence_interval`",
            "A verdict saved before ADR-0052 may hold `confidence_interval`; the "
            "consumer reads it as an `interval` of the kind `confidence`",
        ],
    )
    def test_the_contract_states_the_rule(self, sentence: str) -> None:
        assert sentence in unwrap(section(_contract(), "## Optional metric items"))

    def test_the_skill_names_the_interval(self) -> None:
        assert "`interval` (with its `kind`)" in _skill_analysis_step()


class TestAMetricPerGroupHoldsRows:
    """Epic 33 US-2 AC 3: axes in ``by``, one row per group, no group in a name."""

    def test_the_example_holds_a_metric_with_groups(self) -> None:
        assert _grouped(_confirmation_metrics())

    def test_each_row_names_one_group_per_axis(self) -> None:
        for metric in _grouped(_confirmation_metrics()).values():
            assert metric["by"]
            assert all(isinstance(axis, str) for axis in metric["by"])
            assert metric["groups"]
            for row in metric["groups"]:
                assert len(row["group"]) == len(metric["by"])

    def test_a_row_holds_a_value_and_only_the_optional_items(self) -> None:
        for metric in _grouped(_confirmation_metrics()).values():
            for row in metric["groups"]:
                assert "value" in row
                assert set(row) <= GROUP_ROW_KEYS

    def test_a_metric_with_groups_holds_no_value_of_its_own(self) -> None:
        for metric in _grouped(_confirmation_metrics()).values():
            assert "value" not in metric

    def test_no_group_is_written_into_the_name_of_a_metric(self) -> None:
        """Not into the metric that holds the rows, and not into one beside it."""
        examples = _results_examples().values()
        names = [name for example in examples for name in example["metrics"]]
        groups = {
            str(group)
            for example in examples
            for metric in _grouped(example["metrics"]).values()
            for row in metric["groups"]
            for group in row["group"]
        }
        assert groups
        for name in names:
            assert not [group for group in groups if group in name], name
            assert not set("[|]") & set(name), name

    @pytest.mark.parametrize(
        "sentence",
        [
            "A metric measured per group holds the names of its axes in `by` and "
            "one row per group in `groups`",
            "as many names in `group` as `by` has axes",
            "A row holds no `judgment`, no line, no `threshold` and no `pass`",
            "A metric holds either one `value` or `groups`, never both",
            "Never write a group into the name of a metric",
        ],
    )
    def test_the_contract_states_the_rule(self, sentence: str) -> None:
        assert sentence in _results_rule()

    def test_the_skill_writes_groups_as_rows(self) -> None:
        assert (
            "a metric measured per group holds `by` and `groups`, never a group in "
            "its name"
        ) in _skill_analysis_step()


class TestTheChangelogTellsWhatANotebookWritesNow:
    """Story 33.1: a notebook generated before keeps reading; a new one writes the new items."""

    def _entry(self) -> str:
        changelog = (SKILLS_DIR.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        return unwrap(
            changelog_entry(changelog, "judges its primary metric by two lines")
        )

    def test_it_names_the_new_items(self) -> None:
        entry = self._entry()
        for item in ("support_line", "reject_line", "judgment", "interval", "groups"):
            assert f"`{item}`" in entry, item

    def test_it_says_a_saved_verdict_needs_no_rewrite(self) -> None:
        assert "A verdict saved before reads as it did" in self._entry()
