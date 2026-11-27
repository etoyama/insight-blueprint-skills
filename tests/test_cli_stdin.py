"""The *_io CLIs read stdin only for the commands that take a payload (#129).

The Bash tool of the desktop app's Code tab hands a socket that never reaches EOF
as stdin, so a command that reads it waits forever.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from skills._shared import catalog_io, design_io, tree_io

REPO = Path(__file__).resolve().parents[1]

NO_PAYLOAD = [
    ("design_io", "transition", "--id", "FP-H01", "--target", "analyzing"),
    ("design_io", "get", "--id", "FP-H01"),
    ("design_io", "list"),
    ("design_io", "list-reviews", "--id", "FP-H01"),
    ("catalog_io", "get", "--id", "src"),
    ("catalog_io", "list"),
    ("catalog_io", "describe", "--ids", "src"),
    ("catalog_io", "get-schema", "--id", "src"),
    ("catalog_io", "get-knowledge", "--id", "src"),
    ("catalog_io", "search", "--query", "src"),
    ("tree_io", "link", "--theme", "LIB", "--node", "LIB-Q01", "--design", "LIB-H01"),
    ("tree_io", "link-derived", "--theme", "LIB", "--design", "LIB-H01"),
    ("tree_io", "candidates", "--theme", "LIB"),
    ("tree_io", "copy-hearing", "--theme", "LIB", "--node", "LIB-Q01")
    + ("--design", "LIB-H01"),
    ("tree_io", "get", "--theme", "LIB"),
    ("tree_io", "position", "--theme", "LIB"),
    ("tree_io", "progress", "--theme", "LIB"),
    ("tree_io", "changes", "--theme", "LIB"),
    ("tree_io", "render", "--theme", "LIB"),
    ("tree_io", "report", "--theme", "LIB"),
]


@pytest.mark.parametrize("argv", NO_PAYLOAD, ids=[" ".join(a[:2]) for a in NO_PAYLOAD])
def test_a_command_without_payload_returns_while_stdin_stays_open(
    tmp_path: Path, argv: tuple[str, ...]
) -> None:
    module, command, *rest = argv
    insight = tmp_path / ".insight"
    insight.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-m", f"skills._shared.{module}", command, *rest]
        + ["--base-dir", str(insight)],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO,
    )
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail(f"{module} {command} waited on an open stdin")
    finally:
        assert proc.stdin is not None
        proc.stdin.close()
    assert proc.stderr is not None
    err = proc.stderr.read().decode()
    # An exit that never reached the command would pass the wait as well.
    assert "usage:" not in err
    assert "ImportError" not in err
    assert "ModuleNotFoundError" not in err


WITH_PAYLOAD = [
    (design_io, "answer-analyst"),
    (design_io, "ask-analyst"),
    (design_io, "create"),
    (design_io, "review-batch"),
    (design_io, "stop"),
    (design_io, "update"),
    (catalog_io, "add-knowledge"),
    (catalog_io, "create"),
    (catalog_io, "update"),
    (tree_io, "add-node"),
    (tree_io, "answer"),
    (tree_io, "candidate"),
    (tree_io, "create"),
    (tree_io, "decide"),
    (tree_io, "hear"),
    (tree_io, "revise-root"),
]


@pytest.mark.parametrize("module", [design_io, catalog_io, tree_io])
def test_every_command_is_listed_as_reading_stdin_or_not(module) -> None:
    name = module.__name__.rsplit(".", 1)[-1]
    listed = [a[1] for a in NO_PAYLOAD if a[0] == name] + [
        c for m, c in WITH_PAYLOAD if m is module
    ]
    assert sorted(listed) == sorted(module._COMMANDS)


@pytest.mark.parametrize(
    "module, command",
    WITH_PAYLOAD,
    ids=lambda v: v if isinstance(v, str) else v.__name__.rsplit(".", 1)[-1],
)
def test_a_command_with_payload_reads_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module, command: str
) -> None:
    stdin = io.StringIO("{}")
    monkeypatch.setattr(sys, "stdin", stdin)
    try:
        theme = ["--theme", "LIB"] if module is tree_io else []
        module._main([command, *theme, "--base-dir", str(tmp_path)])
    except Exception:  # an empty payload is not a valid call; only the read matters
        pass
    assert stdin.tell() == 2
