"""Unit tests for the static premortem risk evaluator (Epic 5a).

Post-E5a: no run-history extrapolation; risk is a pure function of source
pre-flight checks + estimated rows.
"""

from __future__ import annotations

import pytest

from skills._shared.models import PremortemConfig, RiskLevel, SourceChecks
from skills.premortem.lib.risk_evaluator import evaluate

CONFIG = PremortemConfig(static_rows_high=10_000_000, static_rows_medium=1_000_000)


def _checks(**over: object) -> SourceChecks:
    base: dict = {
        "source_registered": True,
        "location_ok": True,
        "allowlist_ok": True,
        "estimated_rows": 0,
    }
    base.update(over)
    return SourceChecks(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["supported", "rejected", "inconclusive"])
def test_terminal_status_skips(status: str) -> None:
    assert evaluate({"status": status}, CONFIG, _checks()).level is RiskLevel.SKIP


def test_source_not_registered_hard_blocks() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(source_registered=False))
    assert d.level is RiskLevel.HARD_BLOCK
    assert any("registered" in r for r in d.reasons)


def test_allowlist_false_hard_blocks() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(allowlist_ok=False))
    assert d.level is RiskLevel.HARD_BLOCK
    assert any("allowlist" in r for r in d.reasons)


def test_location_false_hard_blocks() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(location_ok=False))
    assert d.level is RiskLevel.HARD_BLOCK


def test_api_failure_none_is_high_with_flag() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(location_ok=None))
    assert d.level is RiskLevel.HIGH
    assert "location_check_failed" in d.flags


def test_rows_above_high_is_high() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(estimated_rows=20_000_000))
    assert d.level is RiskLevel.HIGH


def test_rows_above_medium_is_medium() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(estimated_rows=2_000_000))
    assert d.level is RiskLevel.MEDIUM


def test_small_rows_is_low() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(estimated_rows=1000))
    assert d.level is RiskLevel.LOW


def test_none_rows_is_low() -> None:
    d = evaluate({"status": "in_review"}, CONFIG, _checks(estimated_rows=None))
    assert d.level is RiskLevel.LOW


def test_hard_block_precedes_high_rows() -> None:
    """HARD_BLOCK wins even when rows would be HIGH."""
    d = evaluate(
        {"status": "in_review"},
        CONFIG,
        _checks(source_registered=False, estimated_rows=99_000_000),
    )
    assert d.level is RiskLevel.HARD_BLOCK
