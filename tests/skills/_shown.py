"""Run the ``*_io`` commands a SKILL.md shows, so the structure tests prove they work.

A shown command that no longer runs against the library is a broken instruction, so
the tests execute the text itself instead of a copy of it.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from skills._shared import design_io, tree_io

PIPED = re.compile(r"echo '(?P<payload>\{.*?\})' \| tree_io (?P<args>[^\n]+)", re.S)
DESIGN_PIPED = re.compile(
    r"echo '(?P<payload>\{.*?\})' \| design_io (?P<args>[^\n]+)", re.S
)


def run_shown_commands(
    prose: str, insight: Path, monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    """Run every ``echo '<json>' | tree_io ...`` shown in *prose* against *insight*."""
    ran: list[str] = []
    for shown in PIPED.finditer(prose):
        args = shown["args"].split()
        monkeypatch.setattr("sys.stdin", io.StringIO(shown["payload"]))
        assert tree_io._main([*args, "--base-dir", str(insight)]) == 0, shown[0]
        ran.append(args[0])
    return ran


def run_shown_line(
    prose: str, command: str, insight: Path, monkeypatch: pytest.MonkeyPatch
) -> int:
    """Run the one-line ``tree_io <command> ...`` shown in *prose* with empty stdin."""
    shown = re.search(rf"^[ \t]*tree_io ({re.escape(command)} [^\n]+)$", prose, re.M)
    assert shown, f"no tree_io {command} command is shown"
    args = shown[1].split()
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    return tree_io._main([*args, "--base-dir", str(insight)])


def run_shown_design_commands(
    prose: str,
    insight: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> list[dict]:
    """Run every ``echo '<json>' | design_io ...`` shown in *prose*; return each result."""
    results: list[dict] = []
    for shown in DESIGN_PIPED.finditer(prose):
        monkeypatch.setattr("sys.stdin", io.StringIO(shown["payload"]))
        capsys.readouterr()
        args = [*shown["args"].split(), "--base-dir", str(insight)]
        assert design_io._main(args) == 0, shown[0]
        results.append(json.loads(capsys.readouterr().out))
    return results
