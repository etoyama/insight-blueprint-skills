"""Tests for the pre-write design-validation hook (Epic 02, Story 2.2).

The hook is the I/O shell around ``insight_blueprint.validate``. Pure helpers
(path matching, edit reconstruction) are unit-tested by importing the hook
module directly; the end-to-end contract (stdin JSON -> exit code) is tested by
running the hook as a subprocess, the way Claude Code invokes it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "validate-design.py"


def load_hook_module() -> ModuleType:
    """Import the hook script as a module for unit-testing its pure helpers."""
    spec = importlib.util.spec_from_file_location("validate_design_hook", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load_hook_module()


def design_dict(**overrides: object) -> dict:
    base: dict = {
        "id": "FP-H01",
        "title": "Test design",
        "hypothesis_statement": "X improves Y",
        "hypothesis_background": "Because Z",
        "status": "in_review",
    }
    base.update(overrides)
    return base


def dump_yaml(data: dict) -> str:
    from io import StringIO

    yaml = YAML()
    buf = StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()


def write_design(tmp_path: Path, design_id: str, data: dict) -> Path:
    """Write a design YAML to a temp project's .insight/designs/ and return path."""
    designs = tmp_path / ".insight" / "designs"
    designs.mkdir(parents=True, exist_ok=True)
    path = designs / f"{design_id}_hypothesis.yaml"
    path.write_text(dump_yaml(data), encoding="utf-8")
    return path


def run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    """Invoke the hook as a subprocess with a PreToolUse JSON payload on stdin."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Pure helpers: path matching
# ---------------------------------------------------------------------------


class TestIsDesignFile:
    def test_matches_hypothesis_yaml_in_designs(self) -> None:
        assert hook.is_design_file("/p/.insight/designs/FP-H01_hypothesis.yaml")

    def test_rejects_journal_yaml(self) -> None:
        assert not hook.is_design_file("/p/.insight/designs/FP-H01_journal.yaml")

    def test_rejects_outside_designs_dir(self) -> None:
        assert not hook.is_design_file("/p/elsewhere/FP-H01_hypothesis.yaml")

    def test_rejects_none(self) -> None:
        assert not hook.is_design_file(None)


# ---------------------------------------------------------------------------
# Pure helpers: edit reconstruction
# ---------------------------------------------------------------------------


class TestReconstructContent:
    def test_write_returns_content(self) -> None:
        out = hook.reconstruct_content("Write", {"content": "a: 1\n"}, "old")
        assert out == "a: 1\n"

    def test_edit_replaces_first_occurrence(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "in_review", "new_string": "analyzing"},
            "status: in_review\n",
        )
        assert out == "status: analyzing\n"

    def test_edit_replace_all(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "x", "new_string": "y", "replace_all": True},
            "x x x",
        )
        assert out == "y y y"

    def test_edit_missing_old_string_is_noop(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "absent", "new_string": "z"},
            "status: in_review\n",
        )
        assert out == "status: in_review\n"

    def test_multiedit_applies_in_sequence(self) -> None:
        out = hook.reconstruct_content(
            "MultiEdit",
            {
                "edits": [
                    {"old_string": "a", "new_string": "b"},
                    {"old_string": "b", "new_string": "c"},
                ]
            },
            "a",
        )
        assert out == "c"


# ---------------------------------------------------------------------------
# End-to-end: subprocess invocation
# ---------------------------------------------------------------------------


class TestHookSubprocessAllow:
    def test_non_design_file_is_ignored(self, tmp_path: Path) -> None:
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(tmp_path / "notes.md"),
                    "content": "hello",
                },
            }
        )
        assert result.returncode == 0

    def test_write_new_valid_design_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(design_dict()),
                },
            }
        )
        assert result.returncode == 0, result.stderr

    def test_valid_transition_via_write_allowed(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="in_review"))
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(design_dict(status="analyzing")),
                },
            }
        )
        assert result.returncode == 0, result.stderr

    def test_body_only_edit_on_terminal_design_allowed(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="supported"))
        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "title: Test design",
                    "new_string": "title: Edited design",
                },
            }
        )
        assert result.returncode == 0, result.stderr


class TestHookSubprocessBlock:
    def test_schema_violation_blocks(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        bad = design_dict(methodology={"method": ""})
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(path), "content": dump_yaml(bad)},
            }
        )
        assert result.returncode == 2
        assert "validation failed" in result.stderr.lower()

    def test_invalid_transition_via_write_blocks(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(design_dict(status="supported")),
                },
            }
        )
        assert result.returncode == 2
        assert "transition" in result.stderr.lower()

    def test_invalid_transition_via_inplace_edit_blocks(self, tmp_path: Path) -> None:
        """The headline guard: editing status: in place on a terminal design."""
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "status: analyzing",
                    "new_string": "status: supported",
                },
            }
        )
        assert result.returncode == 2
        assert "transition" in result.stderr.lower()

    def test_malformed_yaml_blocks(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": "status: [unclosed",
                },
            }
        )
        assert result.returncode == 2


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "MultiEdit"])
def test_hook_handles_all_three_tools(tmp_path: Path, tool_name: str) -> None:
    """All three intercepted tools reach a clean allow on a valid no-op change."""
    path = write_design(tmp_path, "FP-H01", design_dict(status="in_review"))
    if tool_name == "Write":
        tool_input = {"file_path": str(path), "content": dump_yaml(design_dict())}
    elif tool_name == "Edit":
        tool_input = {
            "file_path": str(path),
            "old_string": "title: Test design",
            "new_string": "title: Renamed",
        }
    else:
        tool_input = {
            "file_path": str(path),
            "edits": [{"old_string": "title: Test design", "new_string": "title: R"}],
        }
    result = run_hook({"tool_name": tool_name, "tool_input": tool_input})
    assert result.returncode == 0, result.stderr
