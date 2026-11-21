"""The JSON payload a *_io command reads from stdin."""

from __future__ import annotations

import json
import sys
from typing import Any


def read_payload() -> dict[str, Any]:
    """Parse stdin as a JSON object; empty stdin or a terminal gives ``{}``.

    Call it only for a command that takes a payload: stdin may be a pipe or
    socket that never closes (the desktop app's Bash), and reading it blocks.
    """
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}
