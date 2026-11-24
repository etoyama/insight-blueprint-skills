"""Structure tests for /data-lineage (Epic 31 US-1, ADR-0047).

/data-lineage runs the notebook /analysis-notebook made, in the plugin env, with the
same command. It installs nothing outside the plugin and stops on any other target.
"""

from __future__ import annotations

import re

import pytest

from tests.skills._markdown import section, unwrap
from tests.skills._notebook_run import RUN, WITH_EXCLUSION, WITH_SCOPE, commands
from tests.skills.test_skill_structure import _read_skill

# A command that installs a package, not a mention such as "nothing to `pip install`".
INSTALL_COMMAND = re.compile(r"\b(uv add|pip install)\s+[\w\"'\[-]")


def _skill() -> str:
    return _read_skill("data-lineage")


class TestDataLineagePrerequisites:
    """/data-lineage installs nothing outside the plugin (ADR-0047)."""

    def test_data_lineage_tells_to_install_nothing(self) -> None:
        """SKILL.md has no install command (US-1 AC 1)."""
        assert not INSTALL_COMMAND.search(_skill())

    def test_data_lineage_argument_hint_has_no_setup(self) -> None:
        """The argument hint offers no setup subcommand (US-1 AC 1)."""
        hint = re.search(r"^argument-hint:(.*)$", _skill(), re.MULTILINE)
        assert hint is not None
        assert "setup" not in hint.group(1)

    def test_data_lineage_runs_notebook_with_analysis_notebook_command(self) -> None:
        """Modes B and C run the notebook with /analysis-notebook's command (US-1 AC 2)."""
        assert commands(section(_skill(), "## Running the notebook")) == [RUN]

    def test_data_lineage_supplies_allowlisted_packages_with_with(self) -> None:
        """Only a package outside the plugin env is added with --with."""
        running = unwrap(section(_skill(), "## Running the notebook"))
        assert "--with <pip-name>" in running
        assert "package_allowlist.yaml" in running
        assert WITH_SCOPE in running
        assert WITH_EXCLUSION in running
        assert "Package allowlist — format & supplying packages" in running

    def test_data_lineage_targets_contract_notebook_and_stops_otherwise(self) -> None:
        """Only the contract notebook is a target; others stop with a pointer (US-1 AC 3)."""
        target = section(_skill(), "## Target")
        assert "design_io get --id {id}" in target
        assert ".insight/notebooks/{id}.py` exists" in target
        assert "uses `tracked_pipe`" in target
        assert "/analysis-notebook {id}" in target
        assert "**stop**" in target

    def test_an_id_with_no_design_stops_before_it_reaches_a_path(self) -> None:
        """{id} goes into a path and a shell command, so the design lookup is a gate."""
        target = section(_skill(), "## Target")
        checks = re.findall(r"^\d+\. (.*)$", target, re.MULTILINE)
        assert "design_io get --id {id}" in checks[0]
        assert "`{}`" in checks[0]
        rule = unwrap(target)
        assert "first that fails" in rule
        assert "no design" in rule

    @pytest.mark.parametrize("mode", ["### Mode B", "### Mode C"])
    def test_each_mode_checks_the_target_before_it_runs_the_notebook(
        self, mode: str
    ) -> None:
        """Both modes check the target, then run the notebook (US-1 AC 2, AC 3)."""
        body = section(_skill(), mode)
        target = body.index('"Target"')
        run = body.index('"Running the notebook"')
        assert target < run
