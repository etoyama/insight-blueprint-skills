"""Premortem CLI -- report-only pre-flight risk evaluation.

Reads design data as JSON from stdin (Claude Code builds it via design_io /
catalog_io), evaluates each design statically via ``risk_evaluator``, and prints
a risk table. No token is issued and nothing is written to disk.

Exit codes:
  0 -- no HARD_BLOCK / HIGH risk
  2 -- at least one HARD_BLOCK or HIGH design (warning signal)
  1 -- unexpected error / bad input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skills._shared.config_loader import load_premortem_config
from skills._shared.models import RiskLevel, SourceChecks
from skills.premortem.lib.risk_evaluator import evaluate as risk_evaluate

_CONFIG_PATH = Path(".insight/config.yaml")
_DEFAULT_BASE_DIR = Path(".insight")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="premortem",
        description="Report-only pre-flight risk evaluation for analysis designs.",
    )
    parser.add_argument(
        "--design",
        type=str,
        metavar="ID",
        default=None,
        help="Evaluate only the design with this ID (default: all in payload)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=_DEFAULT_BASE_DIR,
        help=argparse.SUPPRESS,  # testing override
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_CONFIG_PATH,
        help=argparse.SUPPRESS,  # testing override
    )
    return parser


def _read_stdin_payload() -> dict:
    """Read JSON payload from stdin.

    Expected schema::

        {
            "designs": [{ "id": ..., "intent": ..., "status": ..., ... }],
            "source_checks_map": {
                "<design_id>": {
                    "source_registered": bool,
                    "location_ok": bool | null,
                    "allowlist_ok": bool | null,
                    "estimated_rows": int | null
                }
            }
        }
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return {"designs": [], "source_checks_map": {}}
    return json.loads(raw)


def _format_risk_line(
    design_id: str,
    intent: str,
    estimated_rows: int | None,
    strategy: str,
    level: RiskLevel,
    reasons: list[str],
) -> str:
    """Format a single design's risk as a table row."""
    rows_str = f"{estimated_rows:>10,}" if estimated_rows else "       N/A"
    reasons_str = "; ".join(reasons) if reasons else "-"
    return (
        f"{design_id:<12} {intent:<14} {rows_str} "
        f"{strategy:<12} {level.value:<12} {reasons_str}"
    )


def _render_header() -> str:
    return (
        f"{'DESIGN_ID':<12} {'INTENT':<14} {'EST_ROWS':>10} "
        f"{'STRATEGY':<12} {'RISK':<12} REASONS\n" + "-" * 90
    )


def _infer_strategy(estimated_rows: int | None) -> str:
    """Infer data volume strategy from estimated rows."""
    if estimated_rows is None:
        return "unknown"
    if estimated_rows < 1_000_000:
        return "direct"
    if estimated_rows <= 10_000_000:
        return "sample"
    return "agg_first"


def main(argv: list[str] | None = None, stdin_data: dict | None = None) -> int:
    """Main entry point. Returns exit code.

    ``argv`` / ``stdin_data`` are injectable for testing.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = load_premortem_config(args.config)

    payload = stdin_data if stdin_data is not None else _read_stdin_payload()
    designs = payload.get("designs", [])
    source_checks_map = payload.get("source_checks_map", {})

    if args.design is not None:
        designs = [d for d in designs if d.get("id") == args.design]
        if not designs:
            print(f"Design {args.design} not found in payload.", file=sys.stderr)
            return 1

    if not designs:
        print("No designs to evaluate.", file=sys.stderr)
        return 0

    print(_render_header())

    elevated = 0  # count of HARD_BLOCK / HIGH
    for design in designs:
        design_id = design.get("id", "unknown")
        sc_data = source_checks_map.get(design_id, {})
        source_checks = SourceChecks(
            source_registered=sc_data.get("source_registered", True),
            location_ok=sc_data.get("location_ok", True),
            allowlist_ok=sc_data.get("allowlist_ok", True),
            estimated_rows=sc_data.get("estimated_rows"),
        )
        decision = risk_evaluate(
            design=design, config=config, source_checks=source_checks
        )
        if decision.level in (RiskLevel.HARD_BLOCK, RiskLevel.HIGH):
            elevated += 1

        print(
            _format_risk_line(
                design_id=design_id,
                intent=design.get("intent", "unknown"),
                estimated_rows=source_checks.estimated_rows,
                strategy=_infer_strategy(source_checks.estimated_rows),
                level=decision.level,
                reasons=decision.reasons,
            )
        )

    if elevated:
        print(
            f"\n{elevated} design(s) at HARD_BLOCK/HIGH risk — review before "
            "expensive data access.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
