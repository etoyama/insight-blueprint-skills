"""Structure tests for the package allowlist (Epic 16 / ADR-0021, amended by ADR-0027).

``allowlist_ok`` is built by the driver from SKILL.md prose; no code reads
``package_allowlist.yaml``. These tests guard the load-bearing sentences: the default
allowlist is what every contract notebook imports and what the plugin env ships, it is
always allowed, the file only adds packages to it, and a missing file is never ``null``.
"""

from __future__ import annotations

import re
import tomllib

import yaml

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

REPO_ROOT = SKILLS_DIR.parent
CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
SAMPLE = REPO_ROOT / ".insight" / "rules" / "package_allowlist.yaml"
ALLOWLIST_FILE = "`.insight/rules/package_allowlist.yaml`"

# The names the contract's cells bind, and the module each one comes from.
CONTRACT_BINDINGS = {
    "pd": "pandas",
    "plt": "matplotlib",
    "np": "numpy",
    "LineageSession": "insight_blueprint",
    "mo": "marimo",
}


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

    def test_import_names_are_the_modules_the_cells_bind(self) -> None:
        cells = section(_contract(), "## Cells")
        for name in CONTRACT_BINDINGS:
            assert re.search(rf"\b{name}\b", cells), f"the cells bind {name}"
        assert set(_default_allowlist()) == set(CONTRACT_BINDINGS.values())


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

    def test_standard_library_modules_need_no_entry(self) -> None:
        assert "Standard-library modules need no entry" in unwrap(
            section(_contract(), "### Format")
        )

    def test_the_boundary_is_the_default_plus_the_file(self) -> None:
        boundary = unwrap(section(_contract(), "### Security"))
        assert f"the default allowlist plus {ALLOWLIST_FILE}" in boundary

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
        assert "A missing file is never `null`" in workflow
        assert "`null` only when the file exists but cannot be read" in workflow

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

    def test_allowlist_stop_points_at_the_file(self) -> None:
        assert (
            f"`package outside allowlist` → offer to declare the package in {ALLOWLIST_FILE}"
            in self._workflow()
        )

    def test_the_stop_no_longer_asks_to_copy_the_default(self) -> None:
        assert "start it from the default allowlist" not in self._workflow()
