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
            f"if {ALLOWLIST_FILE} does not exist, the default allowlist"
            in self._steps()
        )

    def test_allowlist_stop_points_at_the_file(self) -> None:
        assert (
            f"`package outside allowlist` → offer to declare the package in {ALLOWLIST_FILE}"
            in self._steps()
        )
