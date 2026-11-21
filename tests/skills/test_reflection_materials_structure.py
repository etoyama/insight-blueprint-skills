"""Structure tests for the files to read in /analysis-reflection (Epic 26, Story #159).

Step 2 shows the analyst where the figures, the verdict and the notebook are, and
the definition of each metric, before Step 3 asks for a conclusion (US-1). The
block is prose, so the tests check it against what it names: the paths are the
ones /analysis-notebook writes, and every field it shows exists on ``Metric`` or
in the figures manifest.
"""

from __future__ import annotations

import re

from insight_blueprint.models.design import Metric
from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

_HEADER = "── 読むもの ──"
_PATH = re.compile(r"\.insight/notebooks/\{design_id\}[\w{}.]*")


def _step() -> str:
    return section(_read_skill("analysis-reflection"), "### Step 2")


def _block() -> str:
    """The lines of the block, from its header to the end of the fence it is in."""
    step = _step()
    assert _HEADER in step, "Step 2 shows no block of files to read"
    return step.split(_HEADER, 1)[1].split("```", 1)[0]


def _placeholders(lines: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\{{{prefix}\.(\w+)\}}", lines))


def _rules() -> str:
    """The prose of Step 2 after the template, where the rules of the block live."""
    return unwrap(_step().split(_HEADER, 1)[1].split("```", 1)[1])


class TestTheBlockNamesTheNotebookOutputs:
    """US-1 AC 1: the block lists the figures, the verdict and the notebook by path."""

    def test_it_comes_after_the_journal_summary(self) -> None:
        step = _step()
        assert step.index("── Branches ──") < step.index(_HEADER)

    def test_it_names_each_output_of_the_notebook(self) -> None:
        paths = set(_PATH.findall(_block()))
        assert paths == {
            ".insight/notebooks/{design_id}_fig{NN}.png",
            ".insight/notebooks/{design_id}_verdict.json",
            ".insight/notebooks/{design_id}.py",
            ".insight/notebooks/{design_id}.html",
        }

    def test_each_path_is_one_the_notebook_skill_writes(self) -> None:
        notebook = (SKILLS_DIR / "analysis-notebook" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        written = notebook.replace("{NN:02d}", "{NN}")
        for path in _PATH.findall(_block()):
            assert path in written, f"/analysis-notebook writes no {path}"


class TestOnlyFilesThatExist:
    """US-1 AC 2: a file that is not there gets no line."""

    def test_it_lists_only_files_that_exist(self) -> None:
        assert "only the files that exist" in _rules()

    def test_it_says_so_when_the_notebook_left_nothing(self) -> None:
        assert "notebook の出力がまだ無い" in _rules()


class TestFiguresCarryTheirManifest:
    """US-1 AC 3: each figure shows its manifest entry as written."""

    def test_each_figure_field_is_one_the_manifest_holds(self) -> None:
        contract = (
            SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
        ).read_text(encoding="utf-8")
        manifest = section(contract, "## `figure_manifest` shape")
        fields = _placeholders(_block(), "figure")
        assert fields == {"title", "axes", "how_to_read"}
        for field in fields:
            assert f'"{field}":' in manifest

    def test_a_figure_missing_from_the_manifest_shows_its_path_only(self) -> None:
        assert "not in the manifest, show its path only" in _rules()


class TestMetricsAsWritten:
    """US-1 AC 4: every metric of the design, field by field, as written."""

    def test_each_metric_field_is_a_field_of_metric(self) -> None:
        fields = _placeholders(_block(), "metric")
        assert "target" in fields
        # data_source is a note only /analysis-design explains (Epic 15); the notebook
        # shows where the data came from.
        assert fields <= set(Metric.model_fields) - {"data_source"}

    def test_it_neither_rewords_nor_shows_empty_fields(self) -> None:
        rules = _rules()
        assert "as the design writes it" in rules
        assert "Leave out a field that is empty" in rules


class TestNothingIsWritten:
    """US-1 AC 5: the block reads files and writes none."""

    def test_it_writes_no_file_and_embeds_no_figure(self) -> None:
        rules = _rules()
        assert "Write no file for this block" in rules
        assert "never embed a figure" in rules
