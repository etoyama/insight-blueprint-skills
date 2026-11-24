"""Epic 31 US-2: a release is a tag; CI checks the tag, and nothing builds a wheel for PyPI.

docs/design/epic-31-drop-pypi-publish.md, ADR-0047 d2.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github/workflows/ci.yml"


def _ci() -> dict:
    return YAML(typ="safe").load(CI.read_text(encoding="utf-8"))


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
        assert job["if"] == "startsWith(github.ref, 'refs/tags/v')"
        step = next(
            s
            for s in job["steps"]
            if "scripts/check_tag_version.py" in s.get("run", "")
        )
        assert step["env"]["TAG_NAME"] == "${{ github.ref_name }}"
        assert '--tag "$TAG_NAME"' in step["run"]

    def test_tag_check_stays_runnable_locally(self) -> None:
        assert "check_tag_version.py" in _poe_tasks()["check-tag-version"]["cmd"]


class TestNoWheelTooling:
    @pytest.mark.parametrize(
        "rel",
        [
            ".github/workflows/publish.yml",
            "scripts/verify_wheel.py",
            "tests/test_verify_wheel.py",
            "tests/test_packaging.py",
        ],
    )
    def test_file_is_gone(self, rel: str) -> None:
        assert not (REPO_ROOT / rel).exists()

    def test_ci_has_no_build_check_job(self) -> None:
        assert "build-check" not in _ci()["jobs"]

    @pytest.mark.parametrize("word", ["uv build", "verify_wheel", "twine", "pypi"])
    def test_ci_runs_no_wheel_step(self, word: str) -> None:
        for job in _ci()["jobs"].values():
            assert not any(word in command.lower() for command in _commands(job))

    @pytest.mark.parametrize("task", ["verify-wheel", "release-dry-run"])
    def test_poe_has_no_wheel_task(self, task: str) -> None:
        assert task not in _poe_tasks()
