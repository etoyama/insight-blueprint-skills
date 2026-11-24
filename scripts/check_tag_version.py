"""Check that a git tag matches the version in pyproject.toml.

Usage:
    python scripts/check_tag_version.py [--tag vX.Y.Z] [--pyproject pyproject.toml]

Without --tag, the tag on HEAD is checked (``git describe --tags --exact-match``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


def check_tag_version(tag: str | None, pyproject_path: Path) -> tuple[bool, str]:
    """Check that a git tag matches the pyproject.toml version.

    Args:
        tag: The git tag string (e.g. "v0.1.0"). If None, attempts
             to detect from git.
        pyproject_path: Path to pyproject.toml.

    Returns:
        A tuple of (success, message).
    """
    # Read version from pyproject.toml
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    pyproject_version = data["project"]["version"]

    # If no tag provided, try to detect from git
    if tag is None:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return (
                False,
                "No tag provided and no git tag found on current commit. "
                "Use --tag to specify a tag, or create a tag with: "
                f"git tag v{pyproject_version}",
            )
        tag = result.stdout.strip()

    # Validate v prefix
    if not tag.startswith("v"):
        return (
            False,
            f"Tag '{tag}' does not start with 'v' prefix. "
            f"Expected format: v{pyproject_version}",
        )

    # Extract version from tag (strip 'v' prefix)
    tag_version = tag[1:]

    # Compare versions
    if tag_version == pyproject_version:
        return True, f"OK: Tag {tag} matches pyproject.toml version {pyproject_version}"
    else:
        return (
            False,
            f"Version mismatch: tag {tag} (version {tag_version}) "
            f"does not match pyproject.toml version {pyproject_version}",
        )


def main() -> None:
    """CLI entry point for tag-version check."""
    parser = argparse.ArgumentParser(description="Check tag-version consistency")
    parser.add_argument(
        "--tag",
        default=None,
        help="Git tag to check (e.g. v0.1.0). If omitted, detects from git describe.",
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    args = parser.parse_args()

    pyproject_path = Path(args.pyproject)
    if not pyproject_path.exists():
        print(f"ERROR: {pyproject_path} not found")
        sys.exit(1)

    ok, message = check_tag_version(args.tag, pyproject_path)
    print(message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
