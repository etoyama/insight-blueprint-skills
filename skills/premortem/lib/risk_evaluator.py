"""Risk evaluator: pure-function decision tree for premortem risk assessment.

No I/O — all inputs are passed as arguments. Post-E5a: run-history extrapolation
was removed; risk is assessed statically from source checks + estimated rows.
"""

from __future__ import annotations

from skills._shared.models import (
    PremortemConfig,
    RiskDecision,
    RiskLevel,
    SourceChecks,
)

_TERMINAL_STATUSES = frozenset({"supported", "rejected", "inconclusive"})


def evaluate(
    design: dict,
    config: PremortemConfig,
    source_checks: SourceChecks,
) -> RiskDecision:
    """Evaluate risk for a single design (static, no history).

    Decision tree (priority order):
      1. Terminal status -> SKIP
      2. HARD_BLOCK (source/allowlist/location explicit False)
      3. API failure (location/allowlist None) -> HIGH + flags
      4. Row-count tiers: > static_rows_high -> HIGH, > static_rows_medium ->
         MEDIUM, else LOW
    """
    # 1. Terminal status -> SKIP
    if design.get("status", "") in _TERMINAL_STATUSES:
        return RiskDecision(level=RiskLevel.SKIP, reasons=["terminal status"], flags=[])

    # 2. HARD_BLOCK conditions (explicit False)
    hard_block_reasons: list[str] = []
    if source_checks.source_registered is False:
        hard_block_reasons.append("source not registered")
    if source_checks.allowlist_ok is False:
        hard_block_reasons.append("package outside allowlist")
    if source_checks.location_ok is False:
        hard_block_reasons.append("BQ location mismatch")
    if hard_block_reasons:
        return RiskDecision(
            level=RiskLevel.HARD_BLOCK, reasons=hard_block_reasons, flags=[]
        )

    # 3. API failure (None = check attempted but errored)
    api_flags: list[str] = []
    api_reasons: list[str] = []
    if source_checks.location_ok is None:
        api_flags.append("location_check_failed")
        api_reasons.append("BQ location check failed (API error)")
    if source_checks.allowlist_ok is None:
        api_flags.append("allowlist_check_failed")
        api_reasons.append("allowlist check failed (read error)")
    if api_flags:
        return RiskDecision(level=RiskLevel.HIGH, reasons=api_reasons, flags=api_flags)

    # 4. Static row-count tiers
    estimated_rows = source_checks.estimated_rows or 0
    if estimated_rows > config.static_rows_high:
        return RiskDecision(
            level=RiskLevel.HIGH,
            reasons=[
                f"estimated rows {estimated_rows:,} > {config.static_rows_high:,}"
            ],
            flags=[],
        )
    if estimated_rows > config.static_rows_medium:
        return RiskDecision(
            level=RiskLevel.MEDIUM,
            reasons=[
                f"estimated rows {estimated_rows:,} > {config.static_rows_medium:,}"
            ],
            flags=[],
        )
    return RiskDecision(
        level=RiskLevel.LOW,
        reasons=[f"estimated rows {estimated_rows:,} within safe range"],
        flags=[],
    )
