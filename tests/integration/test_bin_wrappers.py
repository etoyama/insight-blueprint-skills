"""Integration tests for the bin/ wrappers (Epic 09).

The wrappers are the whole point of Epic 09: a skill command runs in the user's
project cwd, but `skills._shared` lives in the plugin. The wrapper must

  1. run the module from the plugin's own uv env (cd ${CLAUDE_PLUGIN_ROOT}),
  2. write to the *user project* via INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight,
  3. work from an arbitrary foreign cwd (the exact ModuleNotFoundError bug fixed).

These invoke the real `uv run`, so they are marked/kept in the integration suite.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

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


def test_wrapper_fails_loud_without_plugin_root(tmp_path: Path) -> None:
    """Missing CLAUDE_PLUGIN_ROOT must error, not silently run in the wrong env."""
    env = _base_env()
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)

    result = subprocess.run(
        [str(DESIGN_IO), "list"],
        input="",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert result.returncode != 0
    assert "CLAUDE_PLUGIN_ROOT" in result.stderr
