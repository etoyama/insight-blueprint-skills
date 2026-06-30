"""Integration tests for wheel packaging (Integ-01 through Integ-04b).

These tests build an actual wheel and verify its contents.
They are slower than unit tests (~5-10s each) due to the build step.
"""

from __future__ import annotations

import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _build_wheel(tmp_path: Path) -> Path:
    """Build a wheel into tmp_path and return the .whl path."""
    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"uv build failed:\n{result.stderr}")

    wheels = list(tmp_path.glob("*.whl"))
    if not wheels:
        pytest.fail(f"No .whl files found in {tmp_path}")

    return wheels[0]


def _read_wheel_names(whl_path: Path) -> list[str]:
    """Read all file names from a wheel (ZIP) archive."""
    with zipfile.ZipFile(whl_path) as zf:
        return zf.namelist()


def _read_wheel_metadata(whl_path: Path) -> str:
    """Read the METADATA file from a wheel."""
    with zipfile.ZipFile(whl_path) as zf:
        metadata_files = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        if not metadata_files:
            pytest.fail("No METADATA file found in wheel")
        return zf.read(metadata_files[0]).decode("utf-8")


class TestWheelContents:
    """Tests for required files in the built wheel."""

    def test_wheel_contains_py_typed(self, tmp_path: Path) -> None:
        """Integ-01: Built wheel should contain py.typed marker (PEP 561)."""
        whl_path = _build_wheel(tmp_path)
        names = _read_wheel_names(whl_path)
        assert any(n == "insight_blueprint/py.typed" for n in names), (
            f"py.typed not found in wheel. Files: {sorted(names)}"
        )

    def test_wheel_metadata_version_matches_pyproject(self, tmp_path: Path) -> None:
        """Integ-02: Wheel METADATA version should match pyproject.toml."""
        whl_path = _build_wheel(tmp_path)
        metadata = _read_wheel_metadata(whl_path)

        # Extract Version from METADATA
        wheel_version = None
        for line in metadata.splitlines():
            if line.startswith("Version: "):
                wheel_version = line.split(": ", 1)[1].strip()
                break

        assert wheel_version is not None, "Version not found in METADATA"

        with open(PYPROJECT_PATH, "rb") as f:
            pyproject_version = tomllib.load(f)["project"]["version"]

        assert wheel_version == pyproject_version, (
            f"Wheel version {wheel_version} != pyproject.toml {pyproject_version}"
        )

    def test_wheel_metadata_contains_scientific_classifiers(
        self, tmp_path: Path
    ) -> None:
        """Integ-03: Wheel METADATA should contain scientific classifiers."""
        whl_path = _build_wheel(tmp_path)
        metadata = _read_wheel_metadata(whl_path)

        classifiers = [
            line.split(": ", 1)[1].strip()
            for line in metadata.splitlines()
            if line.startswith("Classifier: ")
        ]

        assert "Intended Audience :: Science/Research" in classifiers, (
            f"Missing 'Intended Audience :: Science/Research'. "
            f"Found classifiers: {classifiers}"
        )
        assert (
            "Topic :: Scientific/Engineering :: Information Analysis" in classifiers
        ), (
            f"Missing 'Topic :: Scientific/Engineering :: Information Analysis'. "
            f"Found classifiers: {classifiers}"
        )
