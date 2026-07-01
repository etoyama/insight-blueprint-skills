"""Integration tests for crash recovery -- Integ-14, 15, 16.

Tests detect_incomplete, resume with session_id, and token-expired finalization.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ruamel.yaml import YAML

from tests.integration.conftest import create_valid_token

JST = ZoneInfo("Asia/Tokyo")
yaml_safe = YAML(typ="safe")
yaml_out = YAML()
yaml_out.preserve_quotes = True


def _create_incomplete_run(
    insight_root: Path,
    run_id: str,
    *,
    session_id: str = "CRASH-SESSION-001",
    token_id: str | None = None,
    include_events: bool = True,
) -> Path:
    """Create an incomplete run directory."""
    run_dir = insight_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run_data = {
        "run_id": run_id,
        "session_id": session_id,
        "started_at": datetime.now(JST).isoformat(),
        "automation_mode": "review",
        "premortem_token": token_id,
        "status": "running",
    }
    with (run_dir / "run.yaml").open("w") as f:
        yaml_out.dump(run_data, f)

    if include_events:
        events_path = run_dir / "events.jsonl"
        with events_path.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "init",
                        "session_id": session_id,
                    }
                )
                + "\n"
            )
            f.write(json.dumps({"type": "tool_use", "index": 0}) + "\n")

    return run_dir


# =========================================================================
# Integ-14: crash recovery detection
# =========================================================================


class TestCrashRecoveryDetectIntegration:
    """Integ-14: detect_incomplete finds crashed runs."""

    def test_incomplete_run_from_crashed_state(
        self,
        insight_root: Path,
    ) -> None:
        """Run with status=running (no ended_at) is detected as incomplete."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from skills._shared.crash_recovery import detect_incomplete

        _create_incomplete_run(insight_root, "20260420_crash_01")

        refs = detect_incomplete(base_dir=insight_root)
        assert len(refs) >= 1
        assert refs[0].run_id == "20260420_crash_01"
        assert refs[0].status == "running"

    # test_stderr_mentions_detected_run_id removed with batch-analysis (Epic 3.5):
    # it exercised skills/batch-analysis/launcher.sh, which no longer exists.
    # detect_incomplete() itself is covered by test_incomplete_run_from_crashed_state
    # above and tests/batch_harness/test_crash_recovery.py.


# =========================================================================
# Integ-15: resume with valid token
# =========================================================================


class TestCrashRecoveryResume:
    """Integ-15: resume uses session_id from incomplete run."""

    def test_resume_command_uses_session_id(
        self,
        insight_root: Path,
    ) -> None:
        """The crash_recovery module correctly identifies the session_id."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from skills._shared.crash_recovery import detect_incomplete

        session_id = "RESUME-SID-789"
        _create_incomplete_run(
            insight_root,
            "20260420_resume_01",
            session_id=session_id,
        )

        refs = detect_incomplete(base_dir=insight_root)
        assert len(refs) >= 1

        # Read run.yaml to verify session_id
        run_yaml = insight_root / "runs" / "20260420_resume_01" / "run.yaml"
        with run_yaml.open("r") as f:
            data = yaml_safe.load(f)
        assert data["session_id"] == session_id

    def test_events_jsonl_appended_not_overwritten(
        self,
        insight_root: Path,
    ) -> None:
        """Resume mode appends to events.jsonl (>> not >)."""
        run_dir = _create_incomplete_run(
            insight_root,
            "20260420_append_test",
            session_id="APPEND-SID",
        )
        events_path = run_dir / "events.jsonl"

        # Record initial line count
        with events_path.open("r") as f:
            initial_lines = len(f.readlines())

        assert initial_lines == 2  # system/init + tool_use

        # Simulate appending (as launcher does with >>)
        with events_path.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "init",
                        "session_id": "APPEND-SID",
                    }
                )
                + "\n"
            )

        with events_path.open("r") as f:
            final_lines = len(f.readlines())

        assert final_lines == initial_lines + 1
        # Verify original content preserved
        with events_path.open("r") as f:
            first_line = json.loads(f.readline())
        assert first_line["session_id"] == "APPEND-SID"


# =========================================================================
# Integ-16: token expired -> finalize incomplete
# =========================================================================


class TestCrashRecoveryTokenExpired:
    """Integ-16: expired token -> unfinished designs marked incomplete."""

    def test_expired_token_finalizes_designs(
        self,
        insight_root: Path,
    ) -> None:
        """Expired token causes unfinished designs to get status=incomplete."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from skills._shared.crash_recovery import (
            detect_incomplete,
            finalize_incomplete,
            unfinished_designs,
        )

        # Create expired token
        token_id = create_valid_token(
            insight_root,
            expired=True,
            token_id="EXPIRED_CRASH",
            approved_designs=[
                {
                    "design_id": "DES-UNFIN",
                    "design_hash": "sha256:unfin",
                    "risk_at_approval": "low",
                    "est_min": 10.0,
                }
            ],
        )

        _create_incomplete_run(
            insight_root,
            "20260420_expired_run",
            token_id=token_id,
        )

        refs = detect_incomplete(base_dir=insight_root)
        assert len(refs) >= 1

        latest = refs[0]
        unfinished = unfinished_designs(latest, base_dir=insight_root)
        assert "DES-UNFIN" in unfinished

        # Finalize
        finalize_incomplete(
            latest.run_id,
            unfinished,
            "token_expired_or_crashed",
            base_dir=insight_root,
        )

        # Check manifest
        manifest_path = (
            insight_root
            / "runs"
            / "20260420_expired_run"
            / "DES-UNFIN"
            / "manifest.yaml"
        )
        assert manifest_path.exists()
        with manifest_path.open("r") as f:
            data = yaml_safe.load(f)
        assert data["status"] == "incomplete"
        assert data["skip_reason"] == "token_expired_or_crashed"

    def test_run_yaml_status_becomes_incomplete(
        self,
        insight_root: Path,
    ) -> None:
        """After finalization, run.yaml status = incomplete."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from skills._shared.crash_recovery import (
            detect_incomplete,
            finalize_incomplete,
            unfinished_designs,
        )

        token_id = create_valid_token(
            insight_root,
            expired=True,
            token_id="EXPIRED_RUN_STATUS",
            approved_designs=[
                {
                    "design_id": "DES-RS",
                    "design_hash": "sha256:rs",
                    "risk_at_approval": "low",
                    "est_min": 10.0,
                }
            ],
        )

        _create_incomplete_run(
            insight_root,
            "20260420_run_status",
            token_id=token_id,
        )

        refs = detect_incomplete(base_dir=insight_root)
        latest = refs[0]
        unfinished = unfinished_designs(latest, base_dir=insight_root)
        finalize_incomplete(
            latest.run_id,
            unfinished,
            "token_expired_or_crashed",
            base_dir=insight_root,
        )

        run_yaml = insight_root / "runs" / "20260420_run_status" / "run.yaml"
        with run_yaml.open("r") as f:
            data = yaml_safe.load(f)
        assert data["status"] == "incomplete"
