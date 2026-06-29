#!/usr/bin/env python3
"""Pre-write hook: validate analysis design documents before they are written.

Registered as a Claude Code PreToolUse hook for Write/Edit/MultiEdit. It is the
only enforcement point for design-document integrity once the MCP server is gone
(ADR-0001 / Epic 02). The hook is a thin I/O shell: it reconstructs the resulting
YAML, reads the current on-disk document, and delegates the actual checks to the
pure functions in ``insight_blueprint.validate``.

Contract:
- Reads a PreToolUse JSON payload on stdin (``tool_name`` + ``tool_input``).
- Only acts on writes to ``.insight/designs/*_hypothesis.yaml``; anything else
  exits 0 (allow).
- On a schema or state-transition violation: prints details to stderr and exits
  2 (block the write).
- On an unexpected internal error: warns on stderr and exits 0 (fail open) so a
  hook bug cannot brick every design write. The MCP path still validates.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

# Make the insight_blueprint package importable even when the hook is run with a
# bare ``python3`` (settings.json uses ``uv run`` where it is already installed).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

EXIT_ALLOW = 0
EXIT_BLOCK = 2

DESIGN_SUFFIX = "_hypothesis.yaml"


def _yaml():  # noqa: ANN202 - ruamel YAML instance
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def is_design_file(file_path: str | None) -> bool:
    """True if *file_path* is a ``.insight/designs/*_hypothesis.yaml`` document."""
    if not file_path:
        return False
    path = Path(file_path)
    return (
        path.name.endswith(DESIGN_SUFFIX)
        and path.parent.name == "designs"
        and path.parent.parent.name == ".insight"
    )


def extract_target_path(tool_input: dict) -> str | None:
    """Return the write target. Write/Edit/MultiEdit all use ``file_path``."""
    value = tool_input.get("file_path")
    return value if isinstance(value, str) else None


def _apply_edit(text: str, old: str, new: str, replace_all: bool) -> str:
    """Apply a single Edit replacement, mirroring the Edit tool's semantics."""
    if old == "" or old not in text:
        # Nothing to replace (or a create-style edit we cannot reconstruct);
        # leave the text unchanged. A genuinely invalid edit would be rejected
        # by the Edit tool itself before any write happens.
        return text
    if replace_all:
        return text.replace(old, new)
    return text.replace(old, new, 1)


def reconstruct_content(tool_name: str, tool_input: dict, current_text: str) -> str:
    """Compute the resulting file text for a Write/Edit/MultiEdit operation."""
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return content if isinstance(content, str) else ""

    if tool_name == "Edit":
        return _apply_edit(
            current_text,
            tool_input.get("old_string", ""),
            tool_input.get("new_string", ""),
            bool(tool_input.get("replace_all", False)),
        )

    if tool_name == "MultiEdit":
        text = current_text
        for edit in tool_input.get("edits", []):
            text = _apply_edit(
                text,
                edit.get("old_string", ""),
                edit.get("new_string", ""),
                bool(edit.get("replace_all", False)),
            )
        return text

    return current_text


def parse_yaml(text: str) -> dict:
    """Parse YAML text into a dict ({} for empty/None)."""
    result = _yaml().load(StringIO(text))
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise ValueError("design document must be a YAML mapping")
    return dict(result)


def evaluate(tool_name: str, tool_input: dict) -> list[str]:
    """Validate a pending write. Returns error strings (empty = allow).

    Performs the file I/O, then delegates to the pure validation library.
    """
    from insight_blueprint.validate import validate_design_change

    file_path = extract_target_path(tool_input)
    if not is_design_file(file_path):
        return []

    path = Path(file_path)  # type: ignore[arg-type]
    current_text = path.read_text(encoding="utf-8") if path.exists() else None

    new_text = reconstruct_content(tool_name, tool_input, current_text or "")
    try:
        new_data = parse_yaml(new_text)
    except Exception as exc:  # noqa: BLE001 - any parse failure blocks the write
        return [f"invalid YAML: {exc}"]

    current_data: dict | None = None
    if current_text is not None:
        try:
            current_data = parse_yaml(current_text)
        except Exception:  # noqa: BLE001 - pre-existing corruption: skip transition
            current_data = None

    return validate_design_change(new_data, current_data)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # noqa: BLE001 - malformed payload: fail open
        print(f"validate-design hook: could not read payload ({exc})", file=sys.stderr)
        return EXIT_ALLOW

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    try:
        errors = evaluate(tool_name, tool_input)
    except Exception as exc:  # noqa: BLE001 - hook bug must not brick writes
        print(
            f"validate-design hook: internal error, allowing ({exc})", file=sys.stderr
        )
        return EXIT_ALLOW

    if errors:
        target = extract_target_path(tool_input) or "(unknown)"
        print(
            f"Design validation failed for {target}:\n"
            + "\n".join(f"  - {e}" for e in errors),
            file=sys.stderr,
        )
        return EXIT_BLOCK

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(main())
