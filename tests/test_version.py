"""Tests for version single-source-of-truth (FR-1.3, FR-1.4)."""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import insight_blueprint

# PEP 440 regex (simplified but covers standard cases + local versions)
PEP440_PATTERN = re.compile(
    r"^([1-9][0-9]*!)?"  # epoch
    r"(0|[1-9][0-9]*)"  # major
    r"(\.(0|[1-9][0-9]*))*"  # minor / patch
    r"((a|b|rc)(0|[1-9][0-9]*))?"  # pre-release
    r"(\.post(0|[1-9][0-9]*))?"  # post-release
    r"(\.dev(0|[1-9][0-9]*))?"  # dev release
    r"(\+[a-z0-9]+([._-][a-z0-9]+)*)?$",  # local version
    re.IGNORECASE,
)

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Read version from pyproject.toml."""
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


class TestVersionSingleSource:
    """Tests for version consistency between __init__.py and pyproject.toml."""

    def test_version_matches_pyproject(self) -> None:
        """__version__ should match the version declared in pyproject.toml."""
        pyproject_version = _read_pyproject_version()
        assert insight_blueprint.__version__ == pyproject_version

    def test_version_is_pep440(self) -> None:
        """__version__ should be a valid PEP 440 version string."""
        assert PEP440_PATTERN.match(insight_blueprint.__version__), (
            f"Version '{insight_blueprint.__version__}' is not PEP 440 compliant"
        )


class TestVersionFallback:
    """Tests for version fallback when package metadata is unavailable."""

    def test_version_fallback_on_package_not_found(self) -> None:
        """When importlib.metadata.version raises PackageNotFoundError,
        __version__ should fall back to '0.0.0+unknown'."""
        from importlib.metadata import PackageNotFoundError

        try:
            with patch(
                "importlib.metadata.version",
                side_effect=PackageNotFoundError("insight-blueprint-lineage"),
            ):
                importlib.reload(insight_blueprint)
                assert insight_blueprint.__version__ == "0.0.0+unknown"
        finally:
            importlib.reload(insight_blueprint)

    def test_version_fallback_is_pep440(self) -> None:
        """The fallback version '0.0.0+unknown' should be PEP 440 compliant."""
        from importlib.metadata import PackageNotFoundError

        try:
            with patch(
                "importlib.metadata.version",
                side_effect=PackageNotFoundError("insight-blueprint-lineage"),
            ):
                importlib.reload(insight_blueprint)
                fallback = insight_blueprint.__version__

            assert PEP440_PATTERN.match(fallback), (
                f"Fallback version '{fallback}' is not PEP 440 compliant"
            )
        finally:
            importlib.reload(insight_blueprint)
