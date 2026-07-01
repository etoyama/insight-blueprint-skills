"""Shared fixtures for integration tests.

Provides:
  - ``insight_root``: temp directory with .insight structure + methodology vocab
  - ``stub_claude_path``: injects stub claude bin onto PATH
  - ``mcp_responses``: loaded MCP response fixtures
  - ``sample_designs``: list of design dicts from fixtures
  - ``sample_design_payload``: ready-to-pipe JSON payload for cli.py
  - ``run_premortem_cli``: helper to invoke cli.py as subprocess
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from ruamel.yaml import YAML

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_E2E_DIR = _PROJECT_ROOT / "tests" / "e2e"
_FIXTURES_DIR = _E2E_DIR / "fixtures"
_STUB_BIN_DIR = _E2E_DIR / "bin"

JST = ZoneInfo("Asia/Tokyo")
yaml = YAML(typ="safe")
yaml_out = YAML()
yaml_out.preserve_quotes = True


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def insight_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary .insight directory with basic structure."""
    root = tmp_path / ".insight"
    root.mkdir()

    # Rules directory with methodology vocab
    rules_dir = root / "rules"
    rules_dir.mkdir()
    vocab_src = _PROJECT_ROOT / ".insight" / "rules" / "methodology_vocab.yaml"
    shutil.copy2(str(vocab_src), str(rules_dir / "methodology_vocab.yaml"))

    # Premortem directory (token destination)
    (root / "premortem").mkdir()

    # Runs directory
    (root / "runs").mkdir()

    # Designs directory
    (root / "designs").mkdir()

    # Catalog directory
    (root / "catalog").mkdir()

    # Change to tmp dir so relative paths work
    monkeypatch.chdir(tmp_path)

    return root


@pytest.fixture()
def insight_root_with_history(insight_root: Path) -> Path:
    """insight_root with past run history copied from e2e fixtures."""
    history_src = _FIXTURES_DIR / "runs_history"
    runs_dst = insight_root / "runs"
    for run_dir in sorted(history_src.iterdir()):
        if run_dir.is_dir():
            shutil.copytree(str(run_dir), str(runs_dst / run_dir.name))
    return insight_root


@pytest.fixture()
def stub_claude_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject stub claude bin ahead on PATH."""
    old_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{_STUB_BIN_DIR}:{old_path}")


@pytest.fixture()
def mcp_responses() -> dict[str, Any]:
    """Load MCP response fixtures."""
    with (_FIXTURES_DIR / "mcp_responses.yaml").open("r") as f:
        return yaml.load(f)


@pytest.fixture()
def sample_designs(mcp_responses: dict[str, Any]) -> list[dict]:
    """Return list of design dicts from MCP fixtures."""
    return mcp_responses["list_analysis_designs"]


@pytest.fixture()
def config_review_a(insight_root: Path) -> Path:
    """Write review Phase A config to insight root."""
    config_src = _FIXTURES_DIR / "config" / "review_phase_a.yaml"
    dst = insight_root.parent / ".insight" / "config.yaml"
    shutil.copy2(str(config_src), str(dst))
    return dst


@pytest.fixture()
def config_review_b(insight_root: Path) -> Path:
    """Write review Phase B config to insight root."""
    config_src = _FIXTURES_DIR / "config" / "review_phase_b.yaml"
    dst = insight_root.parent / ".insight" / "config.yaml"
    shutil.copy2(str(config_src), str(dst))
    return dst


@pytest.fixture()
def config_auto(insight_root: Path) -> Path:
    """Write auto mode config."""
    config_src = _FIXTURES_DIR / "config" / "auto.yaml"
    dst = insight_root.parent / ".insight" / "config.yaml"
    shutil.copy2(str(config_src), str(dst))
    return dst


@pytest.fixture()
def config_manual(insight_root: Path) -> Path:
    """Write manual mode config."""
    config_src = _FIXTURES_DIR / "config" / "manual.yaml"
    dst = insight_root.parent / ".insight" / "config.yaml"
    shutil.copy2(str(config_src), str(dst))
    return dst


@pytest.fixture()
def config_no_automation(insight_root: Path) -> Path:
    """Write a config with no automation key."""
    dst = insight_root.parent / ".insight" / "config.yaml"
    data = {"schema_version": 1, "premortem": {"token_ttl_hours": 24}}
    with dst.open("w") as f:
        yaml_out.dump(data, f)
    return dst


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def build_premortem_payload(
    designs: list[dict],
    source_checks_overrides: dict[str, dict] | None = None,
) -> str:
    """Build JSON payload for cli.py stdin."""
    source_checks_map: dict[str, dict] = {}
    for d in designs:
        design_id = d.get("id", "unknown")
        default_checks = {
            "source_registered": True,
            "location_ok": True,
            "allowlist_ok": True,
            "estimated_rows": 1_500_000,
        }
        if source_checks_overrides and design_id in source_checks_overrides:
            default_checks.update(source_checks_overrides[design_id])
        source_checks_map[design_id] = default_checks

    return json.dumps({"designs": designs, "source_checks_map": source_checks_map})


# ---------------------------------------------------------------------------
# CLI runner helpers
# ---------------------------------------------------------------------------


def run_premortem_cli(
    args: list[str],
    payload: str,
    *,
    cwd: Path | None = None,
    env_override: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run ``python -m skills.premortem.cli`` as subprocess.

    Always runs from PROJECT_ROOT so the ``skills`` package is importable.
    If ``--base-dir`` is present but ``--config`` is not, a ``--config``
    flag is auto-injected pointing to ``<base-dir>/config.yaml``.
    """
    final_args = list(args)
    # Auto-inject --config if --base-dir is present but --config is not
    if "--base-dir" in final_args and "--config" not in final_args:
        bd_idx = final_args.index("--base-dir")
        base_dir_value = final_args[bd_idx + 1]
        config_path = str(Path(base_dir_value) / "config.yaml")
        final_args.extend(["--config", config_path])

    cmd = [sys.executable, "-m", "skills.premortem.cli", *final_args]
    env = os.environ.copy()
    # Ensure the skills package is on PYTHONPATH
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        cmd,
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(_PROJECT_ROOT),
        env=env,
        timeout=timeout,
    )


# run_launcher was removed with batch-analysis (Epic 3.5); premortem/crash-recovery
# integration now exercises the Python functions directly.


def create_valid_token(
    insight_root: Path,
    *,
    approved_designs: list[dict] | None = None,
    skipped_designs: list[dict] | None = None,
    automation_mode: str = "review",
    ttl_hours: int = 24,
    token_id: str | None = None,
    expired: bool = False,
) -> str:
    """Create a valid token YAML file and return the token_id."""
    now = datetime.now(JST)
    if token_id is None:
        token_id = now.strftime("%Y%m%d_%H%M%S")

    if expired:
        created_at = (now - timedelta(hours=ttl_hours + 1)).isoformat()
        expires_at = (now - timedelta(hours=1)).isoformat()
    else:
        created_at = now.isoformat()
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()

    token_data = {
        "token_id": token_id,
        "created_at": created_at,
        "expires_at": expires_at,
        "approved_by": "auto",
        "automation_mode": automation_mode,
        "risk_summary": {"low": 1},
        "approved_designs": approved_designs or [],
        "skipped_designs": skipped_designs or [],
    }
    token_path = insight_root / "premortem" / f"{token_id}.yaml"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open("w") as f:
        yaml_out.dump(token_data, f)
    return token_id


def collect_mtimes(directory: Path) -> dict[str, float]:
    """Collect mtime of all files under directory recursively."""
    mtimes: dict[str, float] = {}
    if not directory.exists():
        return mtimes
    for p in directory.rglob("*"):
        if p.is_file():
            mtimes[str(p)] = p.stat().st_mtime
    return mtimes
