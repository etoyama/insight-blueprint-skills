"""Structure tests for the package allowlist (Epic 16 / ADR-0021, amended by ADR-0027).

``allowlist_ok`` is built by the driver from SKILL.md prose; no code reads
``package_allowlist.yaml``. These tests guard the load-bearing sentences: the default
allowlist is what every contract notebook imports and what the plugin env ships, it is
always allowed, the file only adds packages to it, and a missing file is never ``null``.
"""

from __future__ import annotations

import re
import sys
import tomllib

import yaml

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

REPO_ROOT = SKILLS_DIR.parent
CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
SAMPLE = REPO_ROOT / ".insight" / "rules" / "package_allowlist.yaml"
ALLOWLIST_FILE = "`.insight/rules/package_allowlist.yaml`"

# Where each name in cell 0's return tuple comes from.
CELL0_SOURCES = {
    "pd": "pandas",
    "plt": "matplotlib",
    "np": "numpy",
    "LineageSession": "insight_blueprint",
    "tracked_pipe": "insight_blueprint",
    "export_lineage_as_mermaid": "insight_blueprint",
    "json": "json",
    "Path": "pathlib",
}
STALE_PHRASES = (
    "only the file counts",
    "not merged in",
    "copy the default allowlist",
    "allows nothing",
    "Standard-library modules need no entry",
)


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def _default_allowlist() -> dict[str, str]:
    block = section(_contract(), "### Default allowlist")
    fenced = re.search(r"```yaml\n(.*?)```", block, re.DOTALL)
    assert fenced, "the default allowlist is a yaml block"
    return yaml.safe_load(fenced.group(1))["allowed_packages"]


def _plugin_env() -> set[str]:
    """The pip names the plugin env ships: the project itself and its notebook extra."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    project = pyproject["project"]
    extra = project["optional-dependencies"]["notebook"]
    return {project["name"]} | {re.split(r"[<>=!~\[; ]", dep)[0] for dep in extra}


class TestDefaultAllowlistIsWhatTheContractImports:
    """The default allowlist is the plugin env and every non-stdlib import the cells fix."""

    def test_pip_names_are_what_the_plugin_env_ships(self) -> None:
        assert set(_default_allowlist().values()) == _plugin_env()

    def test_the_plugin_library_is_allowed_by_its_import_name(self) -> None:
        assert _default_allowlist()["insight_blueprint"] == "insight-blueprint-lineage"

    def test_import_names_are_every_non_stdlib_module_the_cells_import(self) -> None:
        returns = table_row(section(_contract(), "## Cells"), "0")[3]
        names = re.findall(r"\w+", returns)
        assert set(names) == set(CELL0_SOURCES), "cell 0 returns only known names"
        modules = set(CELL0_SOURCES.values()) | {"marimo"}
        assert "`import marimo as mo`" in _contract()
        assert modules - sys.stdlib_module_names == set(_default_allowlist())

    def test_only_the_stdlib_modules_of_cell_0_need_no_entry(self) -> None:
        stdlib = set(CELL0_SOURCES.values()) & sys.stdlib_module_names
        assert stdlib == {"json", "pathlib"}
        block = unwrap(section(_contract(), "### Format"))
        assert (
            "The standard-library modules cell 0 imports (`json`, `pathlib`) need no entry"
            in block
        )
        assert "any other standard-library module is checked like a package" in block


class TestDefaultAllowlistIsAlwaysAllowed:
    """ADR-0027: a file adds packages to the default allowlist and cannot remove any."""

    def _block(self) -> str:
        return unwrap(section(_contract(), "### Default allowlist"))

    def test_it_is_allowed_whether_or_not_the_file_exists(self) -> None:
        assert "always allowed, whether or not the file exists" in self._block()

    def test_the_file_adds_packages_to_it(self) -> None:
        assert "the file adds packages to it" in self._block()

    def test_an_empty_map_is_readable_and_adds_nothing(self) -> None:
        assert (
            "An empty `allowed_packages` is readable and adds nothing" in self._block()
        )

    def test_an_unreadable_file_is_an_error(self) -> None:
        assert "is an error, not a fallback to the default" in self._block()

    def test_one_more_package_is_the_only_entry_the_file_needs(self) -> None:
        assert "list only that package in the file" in self._block()

    def test_the_boundary_points_at_the_package_allowlist_section(self) -> None:
        boundary = unwrap(section(_contract(), "### Security"))
        assert 'allowlisted packages (see "Package allowlist" below)' in boundary

    def test_the_replaced_rules_are_gone(self) -> None:
        texts = [_contract()] + [
            _read_skill(name) for name in ("premortem", "analysis-auto")
        ]
        for text in texts:
            for phrase in STALE_PHRASES:
                assert phrase not in unwrap(text), phrase

    def test_supplying_points_at_the_default_instead_of_listing_it(self) -> None:
        supplying = section(_contract(), "### Supplying an allowlisted package")
        assert "Baseline packages (" not in supplying
        assert "default allowlist" in supplying

    def test_the_repo_sample_lists_only_packages_beyond_the_default(self) -> None:
        allowed = yaml.safe_load(SAMPLE.read_text("utf-8"))["allowed_packages"]
        assert allowed
        assert not set(allowed) & set(_default_allowlist())


class TestPremortemBuildsAllowlistOk:
    """/premortem checks methodology.package and never turns a missing file into null."""

    def _workflow(self) -> str:
        return unwrap(section(_read_skill("premortem"), "## Workflow"))

    def test_it_checks_each_package_of_the_methodology(self) -> None:
        workflow = self._workflow()
        assert "each package named in `methodology.package`" in workflow
        assert "import names and pip names" in workflow
        assert "An empty `methodology.package` is `true`" in workflow

    def test_it_compares_top_level_modules_case_insensitively(self) -> None:
        workflow = self._workflow()
        assert "the part before the first `.`" in workflow
        assert "case-insensitively" in workflow
        assert "words that are not package names" in workflow

    def test_it_checks_against_the_default_plus_the_file(self) -> None:
        workflow = self._workflow()
        assert (
            f"the default allowlist plus the packages in {ALLOWLIST_FILE}" in workflow
        )
        assert "references/notebook-contract.md" in workflow

    def test_null_is_kept_for_a_file_that_cannot_be_read(self) -> None:
        workflow = self._workflow()
        assert "A missing file adds nothing and is never `null`" in workflow
        assert "`null` only when the file exists but cannot be read" in workflow
        assert "even when every package is in the default allowlist" in workflow

    def test_high_row_names_only_an_unreadable_file(self) -> None:
        levels = section(_read_skill("premortem"), "## Risk Levels")
        assert (
            "allowlist file that exists but cannot be read"
            in table_row(levels, "`HIGH`")[1]
        )


class TestAutopilotUsesTheSameAllowlist:
    """The notebook gate uses the default plus the file; the stop says how to allow."""

    def _workflow(self) -> str:
        return unwrap(section(_read_skill("analysis-auto"), "## Workflow"))

    def test_notebook_gate_uses_the_default_plus_the_file(self) -> None:
        assert (
            f"the default allowlist in the notebook contract plus {ALLOWLIST_FILE}"
            in self._workflow()
        )

    def test_the_stop_asks_for_only_the_missing_package(self) -> None:
        assert "list only that package" in self._workflow()

    def test_allowlist_stop_points_at_the_file(self) -> None:
        assert (
            f"`package outside allowlist` → offer to declare the package in {ALLOWLIST_FILE}"
            in self._workflow()
        )
