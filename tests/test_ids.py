"""Tests for skills/_shared/ids.py: the one id pattern the CLIs share (Epic 13)."""

from __future__ import annotations

import pytest

from skills._shared import catalog_io, design_io, ids


@pytest.mark.parametrize("value", ["FP-H01", "monthly_sales", "a", "A_b-9"])
def test_safe_id_accepts_letters_digits_underscore_and_hyphen(value: str) -> None:
    assert ids.SAFE_ID_PATTERN.fullmatch(value)


@pytest.mark.parametrize(
    "value", ["", "../x", "a/b", "a\\b", "a.b", "a b", "ok\n", "日本"]
)
def test_safe_id_rejects_anything_that_could_leave_its_directory(value: str) -> None:
    assert ids.SAFE_ID_PATTERN.fullmatch(value) is None


@pytest.mark.parametrize("module", [design_io, catalog_io])
def test_every_cli_checks_ids_with_the_shared_pattern(module: object) -> None:
    # Copies drifted in their comments before; one object cannot drift.
    assert module.SAFE_ID_PATTERN is ids.SAFE_ID_PATTERN  # type: ignore[attr-defined]
