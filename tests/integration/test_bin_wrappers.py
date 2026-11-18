"""Integration tests for the bin/ wrappers (Epic 09).

The wrappers are the whole point of Epic 09: a skill command runs in the user's
project cwd, but `skills._shared` lives in the plugin. The wrapper must

  1. run the module from the plugin's own uv env (cd to the plugin root),
  2. write to the *user project* via INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight,
  3. work from an arbitrary foreign cwd (the exact ModuleNotFoundError bug fixed).

These invoke the real `uv run`, so they are marked/kept in the integration suite.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_IO = REPO_ROOT / "bin" / "design_io"


def _base_env() -> dict[str, str]:
    """Environment without any inherited INSIGHT_BASE_DIR."""
    env = dict(os.environ)
    env.pop("INSIGHT_BASE_DIR", None)
    return env


def test_wrapper_writes_to_project_dir_from_foreign_cwd(tmp_path: Path) -> None:
    """design_io wrapper writes to CLAUDE_PROJECT_DIR/.insight, not cwd."""
    project = tmp_path / "userproj"
    project.mkdir()
    foreign_cwd = tmp_path / "elsewhere"
    foreign_cwd.mkdir()

    env = _base_env()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    env["CLAUDE_PROJECT_DIR"] = str(project)

    payload = {
        "theme_id": "FP",
        "title": "wrapper test",
        "hypothesis_statement": "a",
        "hypothesis_background": "b",
        "methodology": {"method": "OLS"},
    }
    result = subprocess.run(
        [str(DESIGN_IO), "create"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(foreign_cwd),
        env=env,
    )

    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["id"] == "FP-H01"
    # written to the user project, not the foreign cwd
    assert (project / ".insight" / "designs" / "FP-H01_hypothesis.yaml").exists()
    assert not (foreign_cwd / ".insight").exists()


@pytest.mark.parametrize(
    ("wrapper", "args"),
    [
        ("design_io", ["list"]),
        ("catalog_io", ["list"]),
        ("premortem", ["--help"]),
        ("report_check", ["--help"]),
    ],
)
def test_wrapper_runs_from_its_own_plugin_without_plugin_root(
    tmp_path: Path, wrapper: str, args: list[str]
) -> None:
    """Without CLAUDE_PLUGIN_ROOT the wrapper finds the plugin from its own path.

    Claude Code puts bin/ on the Bash tool's PATH but does not export
    CLAUDE_PLUGIN_ROOT or CLAUDE_PROJECT_DIR there, so this is how a skill
    actually calls the wrapper.
    """
    env = _base_env()
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["PATH"] = f"{REPO_ROOT / 'bin'}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [wrapper, *args],
        input="",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert result.returncode == 0, result.stderr


def test_report_check_wrapper_reads_the_project_report_from_foreign_cwd(
    tmp_path: Path,
) -> None:
    """report_check checks CLAUDE_PROJECT_DIR/.insight/reports and creates nothing."""
    project = tmp_path / "userproj"
    reports = project / ".insight" / "reports"
    reports.mkdir(parents=True)
    (reports / "X.md").write_text("![x](http://evil.example/a.png)\n", encoding="utf-8")
    foreign_cwd = tmp_path / "elsewhere"
    foreign_cwd.mkdir()

    env = _base_env()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    env["CLAUDE_PROJECT_DIR"] = str(project)

    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "report_check"), "--id", "X"],
        capture_output=True,
        text=True,
        cwd=str(foreign_cwd),
        env=env,
    )

    assert result.returncode == 1, result.stderr
    out = json.loads(result.stdout)
    assert [v["kind"] for v in out["violations"]] == ["image"]
    assert list(foreign_cwd.iterdir()) == []
    assert sorted(p.name for p in (project / ".insight").iterdir()) == ["reports"]
