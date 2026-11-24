"""Epic 31 US-2: a release is a tag; CI checks the tag, and nothing builds a wheel for PyPI.

docs/design/epic-31-drop-pypi-publish.md, ADR-0047 d2.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github/workflows"
CI = WORKFLOWS / "ci.yml"


def _load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _ci() -> dict:
    return _load(CI)


def _workflows() -> list[dict]:
    return [_load(path) for path in sorted(WORKFLOWS.glob("*.y*ml"))]


def _poe_tasks() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["poe"]["tasks"]


def _runs(job: dict) -> list[str]:
    return [step["run"] for step in job.get("steps", []) if "run" in step]


def _commands(job: dict) -> list[str]:
    """What each step runs or uses, so a publish action counts as much as a shell line."""
    return [step.get("run", step.get("uses", "")) for step in job.get("steps", [])]


class TestCiChecksTheTag:
    def test_ci_runs_on_a_v_tag_push(self) -> None:
        assert "v*" in _ci()["on"]["push"]["tags"]

    def test_a_job_checks_the_pushed_tag_against_the_version(self) -> None:
        jobs = [
            job
            for job in _ci()["jobs"].values()
            if any("scripts/check_tag_version.py" in run for run in _runs(job))
        ]
        assert len(jobs) == 1
        job = jobs[0]
        # A branch push or a PR has no tag to check; the script would fail on it.
        # A negated or widened condition would still mention the ref, so pin the
        # shape: one startsWith on the tag ref, nothing negating or OR-ing it.
        condition = job["if"]
        assert condition.startswith("startsWith(github.ref, 'refs/tags/v')")
        assert not any(op in condition for op in ("!", "||"))
        step = next(
            s
            for s in job["steps"]
            if "scripts/check_tag_version.py" in s.get("run", "")
        )
        assert step["env"]["TAG_NAME"] == "${{ github.ref_name }}"
        assert '--tag "$TAG_NAME"' in step["run"]

    def test_tag_check_stays_runnable_locally(self) -> None:
        assert "check_tag_version.py" in _poe_tasks()["check-tag-version"]["cmd"]


class TestNoWorkflowPublishes:
    """ADR-0047: no workflow uploads to PyPI, so no publish workflow is left either."""

    def test_no_workflow_uses_the_pypi_publish_action(self) -> None:
        for workflow in _workflows():
            for job in workflow["jobs"].values():
                assert not any(
                    "pypa/gh-action-pypi-publish" in command
                    or "uv publish" in command
                    or "twine" in command
                    for command in _commands(job)
                )

    def test_no_workflow_grants_an_id_token(self) -> None:
        """id-token: write exists only for trusted publishing."""
        for workflow in _workflows():
            scopes = [workflow, *workflow["jobs"].values()]
            for permissions in (scope.get("permissions") for scope in scopes):
                if isinstance(permissions, dict):
                    assert permissions.get("id-token") != "write"
                else:
                    assert permissions != "write-all"


class TestNoWheelTooling:
    def test_ci_has_no_build_check_job(self) -> None:
        assert "build-check" not in _ci()["jobs"]

    @pytest.mark.parametrize("word", ["uv build", "verify_wheel", "twine", "pypi"])
    def test_ci_runs_no_wheel_step(self, word: str) -> None:
        for job in _ci()["jobs"].values():
            assert not any(word in command.lower() for command in _commands(job))

    @pytest.mark.parametrize("task", ["verify-wheel", "release-dry-run"])
    def test_poe_has_no_wheel_task(self, task: str) -> None:
        assert task not in _poe_tasks()

    def test_pyproject_does_not_tell_to_install_the_package(self) -> None:
        """Epic 31 US-3 AC 1: the package is not published, so nothing says to add it."""
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "uv add" not in text
        assert "pypi" not in text.lower()
