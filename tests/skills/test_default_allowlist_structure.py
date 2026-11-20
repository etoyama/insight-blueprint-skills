"""Structure tests for the default package allowlist (Epic 16, ADR-0021).

``allowlist_ok`` is built by the driver from SKILL.md prose; no code reads
``package_allowlist.yaml``. These tests guard the load-bearing sentences: a project
without the file uses the default allowlist, the default allowlist is the packages the
plugin env ships, and a missing file is never ``null``.
"""

from __future__ import annotations

import re
import tomllib

import yaml

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

REPO_ROOT = SKILLS_DIR.parent
CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
ALLOWLIST_FILE = "`.insight/rules/package_allowlist.yaml`"


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


class TestDefaultAllowlistIsThePluginEnv:
    """AC 1: the default allowlist lives in the notebook contract and matches the env."""

    def test_pip_names_are_what_the_plugin_env_ships(self) -> None:
        assert set(_default_allowlist().values()) == _plugin_env()

    def test_the_plugin_library_is_allowed_by_its_import_name(self) -> None:
        assert _default_allowlist()["insight_blueprint"] == "insight-blueprint-lineage"

    def test_it_applies_only_when_the_file_does_not_exist(self) -> None:
        block = unwrap(section(_contract(), "### Default allowlist"))
        assert f"When {ALLOWLIST_FILE} does not exist" in block
        assert "only the file counts" in block
        assert "not merged in" in block

    def test_the_boundary_names_the_default_too(self) -> None:
        boundary = unwrap(section(_contract(), "### Security"))
        assert "the default allowlist when the file does not exist" in boundary

    def test_supplying_points_at_the_default_instead_of_listing_it(self) -> None:
        supplying = section(_contract(), "### Supplying an allowlisted package")
        assert "Baseline packages (" not in supplying
        assert "default allowlist" in supplying

    def test_an_empty_map_is_readable_and_allows_nothing(self) -> None:
        block = unwrap(section(_contract(), "### Default allowlist"))
        assert "An empty `allowed_packages` is readable and allows nothing" in block

    def test_a_new_file_starts_from_the_default(self) -> None:
        block = unwrap(section(_contract(), "### Default allowlist"))
        assert "copy the default allowlist into the file" in block


class TestPremortemBuildsAllowlistOk:
    """AC 2: /premortem checks methodology.package and never turns a missing file into null."""

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

    def test_a_missing_file_falls_back_to_the_default_allowlist(self) -> None:
        workflow = self._workflow()
        assert "If the file does not exist, use the default allowlist" in workflow
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
    """AC 3, AC 4: the notebook gate falls back to the default; the stop says how to allow."""

    def _steps(self) -> str:
        return unwrap(_read_skill("analysis-auto"))

    def test_notebook_gate_uses_the_default_when_the_file_is_missing(self) -> None:
        assert (
            "the default allowlist in the notebook contract when the file does not exist"
            in self._steps()
        )

    def test_allowlist_stop_points_at_the_file(self) -> None:
        assert (
            f"`package outside allowlist` → offer to declare the package in {ALLOWLIST_FILE}"
            in self._steps()
        )


CONTRACT_IMPORTS_RULE = (
    "The contract imports (`marimo`, `insight_blueprint`) are always allowed"
)


def _contract_imports() -> dict[str, str]:
    block = section(_contract(), "### Contract imports")
    fenced = re.search(r"```yaml\n(.*?)```", block, re.DOTALL)
    assert fenced, "the contract imports are a yaml block"
    return yaml.safe_load(fenced.group(1))["allowed_packages"]


class TestContractImportsAreAlwaysAllowed:
    """ADR-0027: a file can never exclude the imports the contract itself requires."""

    def test_they_are_the_two_modules_the_contract_imports(self) -> None:
        assert set(_contract_imports()) == {"marimo", "insight_blueprint"}

    def test_they_are_part_of_the_default_allowlist(self) -> None:
        assert _contract_imports().items() <= _default_allowlist().items()

    def test_they_are_allowed_whether_or_not_the_file_exists(self) -> None:
        block = unwrap(section(_contract(), "### Contract imports"))
        assert "always allowed, whether or not the file exists" in block
        assert "whatever the file lists" in block

    def test_the_boundary_rule_covers_every_other_import(self) -> None:
        block = unwrap(section(_contract(), "### Format"))
        assert "every other top-level `import X`" in block

    def test_only_the_file_counts_apart_from_the_contract_imports(self) -> None:
        block = unwrap(section(_contract(), "### Default allowlist"))
        assert "only the file counts, apart from the contract imports" in block

    def test_premortem_allows_them(self) -> None:
        workflow = unwrap(section(_read_skill("premortem"), "## Workflow"))
        assert CONTRACT_IMPORTS_RULE in workflow

    def test_the_autopilot_notebook_gate_allows_them(self) -> None:
        assert CONTRACT_IMPORTS_RULE in unwrap(_read_skill("analysis-auto"))

    def test_the_repo_sample_starts_from_the_default_allowlist(self) -> None:
        sample = REPO_ROOT / ".insight" / "rules" / "package_allowlist.yaml"
        allowed = yaml.safe_load(sample.read_text("utf-8"))["allowed_packages"]
        assert _default_allowlist().items() <= allowed.items()
