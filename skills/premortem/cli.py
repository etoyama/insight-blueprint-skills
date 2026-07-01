"""Premortem CLI -- decision engine for pre-flight risk evaluation.

Reads design data as JSON from stdin (Claude Code pipes MCP results),
evaluates risk via ``risk_evaluator`` + ``history_query``, and issues
an approval token via ``token_manager``.

Exit codes:
  0 -- token issued, batch may proceed
  2 -- review mode + HIGH detected, batch should stop
  1 -- unexpected error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skills._shared.config_loader import load_premortem_config
from skills._shared.models import (
    PremortemConfig,
    RiskLevel,
    SourceChecks,
)
from skills._shared.token_manager import compute_design_hash
from skills._shared.token_manager import issue as token_issue
from skills.premortem.lib.history_query import query as history_query
from skills.premortem.lib.risk_evaluator import evaluate as risk_evaluate

_CONFIG_PATH = Path(".insight/config.yaml")
_DEFAULT_BASE_DIR = Path(".insight")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="premortem",
        description="Pre-flight risk evaluation and approval token issuance.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--queued",
        action="store_true",
        help="Evaluate all designs with next_action.type=batch_execute",
    )
    group.add_argument(
        "--design",
        type=str,
        metavar="ID",
        help="Evaluate a single design by ID",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all designs regardless of queue status",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive mode (skip prompts, follow mode rules)",
    )
    parser.add_argument(
        "--mode",
        choices=["manual", "review", "auto"],
        default="manual",
        help="Automation mode (default: manual)",
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
            "designs": [{ design dict with id, hypothesis, ... }],
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
    return f"{design_id:<12} {intent:<14} {rows_str} {strategy:<12} {level.value:<12} {reasons_str}"


def _render_header() -> str:
    return (
        f"{'DESIGN_ID':<12} {'INTENT':<14} {'EST_ROWS':>10} {'STRATEGY':<12} {'RISK':<12} REASONS\n"
        + "-" * 90
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


def _prompt_for_design(design_id: str, level: RiskLevel, reasons: list[str]) -> str:
    """Prompt user for action on a design. Returns action character."""
    options = "[s]kip / [e]dit / [a]bort"
    if level != RiskLevel.HARD_BLOCK:
        options += " / [c]ontinue"
    prompt_text = f"\n  {design_id} ({level.value}): {'; '.join(reasons)}\n  Action? ({options}): "
    print(prompt_text, end="", flush=True)

    if not sys.stdin.isatty():
        print("\nError: interactive mode requires a TTY", file=sys.stderr)
        sys.exit(1)

    response = input().strip().lower()
    if response in ("s", "e", "a", "c"):
        return response
    return "s"  # default to skip on invalid input


def main(argv: list[str] | None = None, stdin_data: dict | None = None) -> int:
    """Main entry point. Returns exit code.

    Parameters
    ----------
    argv:
        Command-line arguments (for testing). ``None`` = ``sys.argv[1:]``.
    stdin_data:
        Pre-parsed stdin payload (for testing). ``None`` = read from stdin.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Load config
    config = load_premortem_config(args.config)

    # Read design data
    if stdin_data is not None:
        payload = stdin_data
    else:
        payload = _read_stdin_payload()

    designs = payload.get("designs", [])
    source_checks_map = payload.get("source_checks_map", {})

    if not designs:
        print("No designs to evaluate.", file=sys.stderr)
        return 0

    # Filter based on selection mode
    if args.design:
        designs = [d for d in designs if d.get("id") == args.design]
        if not designs:
            print(f"Design {args.design} not found in payload.", file=sys.stderr)
            return 1

    # Evaluate each design
    results: list[dict] = []
    print(_render_header())

    for design in designs:
        design_id = design.get("id", "unknown")
        intent = design.get("intent", "unknown")
        source_ids = design.get("source_ids", [])

        # Source checks
        sc_data = source_checks_map.get(design_id, {})
        source_checks = SourceChecks(
            source_registered=sc_data.get("source_registered", True),
            location_ok=sc_data.get("location_ok", True),
            allowlist_ok=sc_data.get("allowlist_ok", True),
            estimated_rows=sc_data.get("estimated_rows"),
        )

        # History query
        history = history_query(
            source_ids=source_ids,
            min_samples=config.history_min_samples,
            runs_dir=args.base_dir / "runs",
        )

        # Risk evaluation
        decision = risk_evaluate(
            design=design,
            history=history,
            config=config,
            source_checks=source_checks,
        )

        strategy = _infer_strategy(source_checks.estimated_rows)

        print(
            _format_risk_line(
                design_id=design_id,
                intent=intent,
                estimated_rows=source_checks.estimated_rows,
                strategy=strategy,
                level=decision.level,
                reasons=decision.reasons,
            )
        )

        results.append(
            {
                "design_id": design_id,
                "design": design,
                "decision": decision,
                "source_checks": source_checks,
            }
        )

    # Separate into categories
    skipped: list[dict] = []
    hard_blocked: list[dict] = []
    high_risk: list[dict] = []
    approved: list[dict] = []

    for r in results:
        level = r["decision"].level
        if level == RiskLevel.SKIP:
            # Terminal status -- not included in token at all
            continue
        elif level == RiskLevel.HARD_BLOCK:
            hard_blocked.append(r)
        elif level == RiskLevel.HIGH:
            high_risk.append(r)
        else:
            approved.append(r)

    # Mode-based dispatch
    mode = args.mode
    use_yes = args.yes

    # HARD_BLOCK designs are always skipped (all modes)
    for r in hard_blocked:
        skipped.append(r)

    if mode == "manual":
        # Interactive approval required for everything
        return _handle_manual(
            high_risk=high_risk,
            approved=approved,
            skipped=skipped,
            config=config,
            base_dir=args.base_dir,
        )

    elif mode == "review":
        if high_risk:
            if use_yes:
                # --yes + review + HIGH -> exit 2 (batch should stop)
                print(
                    f"\nHIGH risk detected ({len(high_risk)} design(s)). "
                    "review mode with --yes: blocking batch.",
                    file=sys.stderr,
                )
                return 2
            else:
                # Interactive: let user decide per HIGH design
                return _handle_manual(
                    high_risk=high_risk,
                    approved=approved,
                    skipped=skipped,
                    config=config,
                    base_dir=args.base_dir,
                )
        else:
            # No HIGH -> auto-approve LOW/MEDIUM
            return _issue_token(
                approved=approved,
                skipped=skipped,
                approved_by="auto" if use_yes else "human",
                mode=mode,
                config=config,
                base_dir=args.base_dir,
            )

    elif mode == "auto":
        # All designs (including HIGH) go to approved
        for r in high_risk:
            approved.append(r)
        return _issue_token(
            approved=approved,
            skipped=skipped,
            approved_by="auto",
            mode=mode,
            config=config,
            base_dir=args.base_dir,
        )

    return 1  # unreachable in normal flow


def _handle_manual(
    high_risk: list[dict],
    approved: list[dict],
    skipped: list[dict],
    config: PremortemConfig,
    base_dir: Path,
) -> int:
    """Handle manual/interactive mode for HIGH and all other designs."""
    # Process HIGH designs interactively
    for r in high_risk:
        action = _prompt_for_design(
            r["design_id"], r["decision"].level, r["decision"].reasons
        )
        if action == "c":
            approved.append(r)
        elif action == "a":
            print("Aborted by user.", file=sys.stderr)
            return 1
        elif action == "e":
            print(
                f"  -> Edit design with: /analysis-design {r['design_id']}",
                file=sys.stderr,
            )
            skipped.append(r)
        else:
            skipped.append(r)

    # In manual mode, confirm all remaining designs too
    print("\nApprove remaining designs? [y/N]: ", end="", flush=True)
    if not sys.stdin.isatty():
        print("\nError: interactive mode requires a TTY", file=sys.stderr)
        return 1

    confirm = input().strip().lower()
    if confirm != "y":
        print("Aborted by user.", file=sys.stderr)
        return 1

    return _issue_token(
        approved=approved,
        skipped=skipped,
        approved_by="human",
        mode="manual",
        config=config,
        base_dir=base_dir,
    )


def _issue_token(
    approved: list[dict],
    skipped: list[dict],
    approved_by: str,
    mode: str,
    config: PremortemConfig,
    base_dir: Path,
) -> int:
    """Issue token and print launch message."""
    approved_entries = []
    for r in approved:
        design_hash = compute_design_hash(r["design"])
        approved_entries.append(
            {
                "design_id": r["design_id"],
                "design_hash": design_hash,
                "risk_at_approval": r["decision"].level.value,
                "est_min": r["decision"].extrapolated_time_min,
            }
        )

    skipped_entries = []
    for r in skipped:
        skipped_entries.append(
            {
                "design_id": r["design_id"],
                "risk_at_approval": r["decision"].level.value,
                "reason": "; ".join(r["decision"].reasons),
            }
        )

    token_id = token_issue(
        approved=approved_entries,
        skipped=skipped_entries,
        approved_by=approved_by,
        automation_mode=mode,
        ttl_hours=config.token_ttl_hours,
        base_dir=base_dir,
    )

    print(f"\nApproval token issued: {token_id} (use --approved-by {token_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
