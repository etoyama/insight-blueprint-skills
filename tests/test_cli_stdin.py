"""The *_io CLIs read stdin only for the commands that take a payload (#129).

The Bash tool of the desktop app's Code tab hands a socket that never reaches EOF
as stdin, so a command that reads it waits forever.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

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
    ("tree_io", "link", "--theme", "LIB", "--node", "LIB-Q01", "--design", "LIB-H01"),
    ("tree_io", "candidates", "--theme", "LIB"),
    ("tree_io", "copy-hearing", "--theme", "LIB", "--node", "LIB-Q01")
    + ("--design", "LIB-H01"),
    ("tree_io", "get", "--theme", "LIB"),
    ("tree_io", "progress", "--theme", "LIB"),
    ("tree_io", "render", "--theme", "LIB"),
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
        stderr=subprocess.DEVNULL,
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
