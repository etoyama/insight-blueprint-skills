"""Shared data models for premortem risk evaluation.

Enums use ``StrEnum`` (member UPPER_SNAKE_CASE, value lower_snake_case).
Dataclasses are ``frozen=True``. Post-E5a: batch/run/token/history models were
removed (premortem is a report-only static risk assessor).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk classification for premortem evaluation."""

    HARD_BLOCK = "hard_block"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SKIP = "skip"


@dataclass(frozen=True)
class RiskDecision:
    """Output of risk_evaluator.evaluate."""

    level: RiskLevel
    reasons: list[str]
    flags: list[str]


@dataclass(frozen=True)
class SourceChecks:
    """Results of source pre-flight checks.

    ``True`` = check passed, ``False`` = failed (HARD_BLOCK), ``None`` = check
    attempted but errored (treated as HIGH). ``estimated_rows`` drives the
    static row-count risk tiers.
    """

    source_registered: bool
    location_ok: bool | None
    allowlist_ok: bool | None
    estimated_rows: int | None


@dataclass(frozen=True)
class PremortemConfig:
    """Static risk thresholds (rows). Loaded from .insight/config.yaml."""

    static_rows_high: int = 10_000_000
    static_rows_medium: int = 1_000_000
