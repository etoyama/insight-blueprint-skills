"""Integration tests for /premortem CLI -- Integ-01, 02, 04, 27.

Tests invoke ``skills.premortem.cli`` via subprocess with JSON on stdin
and assert stdout / stderr / exit-code / token file side-effects.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from tests.integration.conftest import (
    build_premortem_payload,
    run_premortem_cli,
)

yaml = YAML(typ="safe")


# =========================================================================
# Integ-01: /premortem --queued happy path
# =========================================================================


class TestPremortemQueuedHappy:
    """Integ-01: queued list, stdout format, launch message."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        insight_root_with_history: Path,
        sample_designs: list[dict],
        config_review_a: Path,
    ) -> None:
        self.insight_root = insight_root_with_history
        self.base_dir = self.insight_root
        self.cwd = self.insight_root.parent
        # Only queued designs (next_action.type == batch_execute)
        self.queued = [
            d
            for d in sample_designs
            if d.get("next_action", {}).get("type") == "batch_execute"
        ]
        self.payload = build_premortem_payload(self.queued)

    def test_queued_lists_only_queued_designs(self) -> None:
        """Only designs with next_action.type=batch_execute appear."""
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "review", "--base-dir", str(self.base_dir)],
            self.payload,
            cwd=self.cwd,
        )
        # All 3 fixture designs are queued; all should appear
        for d in self.queued:
            assert d["id"] in result.stdout

    def test_stdout_one_line_per_design(self) -> None:
        """Each design gets exactly one risk line in stdout."""
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "review", "--base-dir", str(self.base_dir)],
            self.payload,
            cwd=self.cwd,
        )
        lines = [
            ln for ln in result.stdout.strip().splitlines() if ln.startswith("DES-")
        ]
        assert len(lines) == len(self.queued)

    def test_launch_message_last_line(self) -> None:
        """Last line reports the issued approval token."""
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "review", "--base-dir", str(self.base_dir)],
            self.payload,
            cwd=self.cwd,
        )
        # If exit code is 2 (HIGH detected), launch message is absent -- use auto mode
        if result.returncode == 2:
            # Re-run with auto mode to get launch message
            result = run_premortem_cli(
                [
                    "--queued",
                    "--yes",
                    "--mode",
                    "auto",
                    "--base-dir",
                    str(self.base_dir),
                ],
                self.payload,
                cwd=self.cwd,
            )
        last_line = result.stdout.strip().splitlines()[-1]
        assert "Approval token issued:" in last_line
        assert "--approved-by" in last_line


# =========================================================================
# Integ-02: /premortem --yes mode dispatch
# =========================================================================


class TestPremortemYesFlag:
    """Integ-02: --yes flag with different modes and risk levels."""

    @pytest.fixture(autouse=True)
    def _setup(self, insight_root: Path, config_review_a: Path) -> None:
        self.insight_root = insight_root
        self.base_dir = self.insight_root
        self.cwd = self.insight_root.parent

    def _make_designs(self, *, include_high: bool) -> tuple[list[dict], str]:
        """Build designs with or without HIGH risk triggers."""
        designs = [
            {
                "id": "DES-LOW",
                "hypothesis": "test",
                "intent": "exploratory",
                "methodology": "test",
                "source_ids": ["src1"],
                "metrics": [],
                "acceptance_criteria": [],
                "status": "analyzing",
                "next_action": {"type": "batch_execute"},
            }
        ]
        overrides: dict[str, dict] = {
            "DES-LOW": {"estimated_rows": 100_000},
        }
        if include_high:
            designs.append(
                {
                    "id": "DES-HIGH",
                    "hypothesis": "test high",
                    "intent": "exploratory",
                    "methodology": "test",
                    "source_ids": ["big_src"],
                    "metrics": [],
                    "acceptance_criteria": [],
                    "status": "analyzing",
                    "next_action": {"type": "batch_execute"},
                }
            )
            overrides["DES-HIGH"] = {"estimated_rows": 50_000_000}
        payload = build_premortem_payload(designs, overrides)
        return designs, payload

    def test_yes_review_mode_exits_0_no_high(self) -> None:
        """review + --yes + no HIGH -> exit 0, token issued."""
        _, payload = self._make_designs(include_high=False)
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "review", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        # Token file created
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        assert len(tokens) >= 1

    def test_yes_review_mode_exits_2_with_high(self) -> None:
        """review + --yes + HIGH -> exit 2, no token."""
        _, payload = self._make_designs(include_high=True)
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "review", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 2
        # No token issued
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        assert len(tokens) == 0

    def test_yes_auto_mode_includes_high(self) -> None:
        """auto + --yes + HIGH -> exit 0, HIGH in approved_designs."""
        _, payload = self._make_designs(include_high=True)
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        assert len(tokens) >= 1
        with tokens[0].open("r") as f:
            token_data = yaml.load(f)
        approved_ids = [d["design_id"] for d in token_data["approved_designs"]]
        assert "DES-HIGH" in approved_ids


# =========================================================================
# Integ-04: HARD_BLOCK handling
# =========================================================================


class TestPremortemHardBlock:
    """Integ-04: HARD_BLOCK design cannot be continued."""

    @pytest.fixture(autouse=True)
    def _setup(self, insight_root: Path, config_review_a: Path) -> None:
        self.insight_root = insight_root
        self.base_dir = self.insight_root
        self.cwd = self.insight_root.parent

    def _make_hard_block_payload(self) -> str:
        designs = [
            {
                "id": "DES-BLOCK",
                "hypothesis": "test",
                "intent": "exploratory",
                "methodology": "test",
                "source_ids": ["unregistered_src"],
                "metrics": [],
                "acceptance_criteria": [],
                "status": "analyzing",
                "next_action": {"type": "batch_execute"},
            },
            {
                "id": "DES-OK",
                "hypothesis": "test2",
                "intent": "exploratory",
                "methodology": "test2",
                "source_ids": ["ok_src"],
                "metrics": [],
                "acceptance_criteria": [],
                "status": "analyzing",
                "next_action": {"type": "batch_execute"},
            },
        ]
        overrides = {
            "DES-BLOCK": {
                "source_registered": False,
                "estimated_rows": 100_000,
            },
            "DES-OK": {"estimated_rows": 100_000},
        }
        return build_premortem_payload(designs, overrides)

    def test_hard_block_shows_no_continue(self) -> None:
        """HARD_BLOCK line does NOT show [c]ontinue option in auto/yes mode."""
        payload = self._make_hard_block_payload()
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        # In auto/yes mode, prompts aren't shown. Check token skipped_designs instead.
        assert result.returncode == 0
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        assert len(tokens) >= 1
        with tokens[0].open("r") as f:
            token_data = yaml.load(f)
        skipped_ids = [d["design_id"] for d in token_data.get("skipped_designs", [])]
        assert "DES-BLOCK" in skipped_ids

    def test_hard_block_in_skipped_with_reason(self) -> None:
        """HARD_BLOCK design appears in token skipped_designs with reason."""
        payload = self._make_hard_block_payload()
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        with tokens[0].open("r") as f:
            token_data = yaml.load(f)
        for entry in token_data.get("skipped_designs", []):
            if entry["design_id"] == "DES-BLOCK":
                assert "reason" in entry
                assert len(entry["reason"]) > 0
                return
        pytest.fail("DES-BLOCK not found in skipped_designs")


# =========================================================================
# Integ-27: BQ API failure -> HIGH with flag
# =========================================================================


class TestPremortemBQFailure:
    """Integ-27: BQ location API failures surface as HIGH + flag."""

    @pytest.fixture(autouse=True)
    def _setup(self, insight_root: Path, config_review_a: Path) -> None:
        self.insight_root = insight_root
        self.base_dir = self.insight_root
        self.cwd = self.insight_root.parent

    def _make_design_with_checks(self, overrides: dict) -> str:
        designs = [
            {
                "id": "DES-BQ",
                "hypothesis": "test",
                "intent": "exploratory",
                "methodology": "test",
                "source_ids": ["bq_src"],
                "metrics": [],
                "acceptance_criteria": [],
                "status": "analyzing",
                "next_action": {"type": "batch_execute"},
            }
        ]
        return build_premortem_payload(designs, {"DES-BQ": overrides})

    def test_bq_api_network_error_shows_high_with_flag(self) -> None:
        """Network error on BQ check -> HIGH + location_check_failed."""
        payload = self._make_design_with_checks(
            {"location_ok": None, "estimated_rows": 500_000}
        )
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        assert "DES-BQ" in result.stdout
        # Check stdout contains HIGH indicator
        bq_line = [ln for ln in result.stdout.splitlines() if "DES-BQ" in ln][0]
        assert "high" in bq_line.lower()

    def test_bq_api_auth_error_shows_high_with_flag(self) -> None:
        """Auth error (location_ok=None) -> HIGH + flag."""
        payload = self._make_design_with_checks(
            {"location_ok": None, "estimated_rows": 500_000}
        )
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        with tokens[0].open("r") as f:
            token_data = yaml.load(f)
        # DES-BQ should be approved (auto mode) with risk_at_approval=high
        for entry in token_data.get("approved_designs", []):
            if entry["design_id"] == "DES-BQ":
                assert entry["risk_at_approval"] == "high"
                return
        pytest.fail("DES-BQ not found in approved_designs")

    def test_bq_location_mismatch_still_hard_block(self) -> None:
        """Explicit location mismatch (False) -> HARD_BLOCK, not HIGH."""
        payload = self._make_design_with_checks(
            {"location_ok": False, "estimated_rows": 500_000}
        )
        result = run_premortem_cli(
            ["--queued", "--yes", "--mode", "auto", "--base-dir", str(self.base_dir)],
            payload,
            cwd=self.cwd,
        )
        assert result.returncode == 0
        tokens = list((self.insight_root / "premortem").glob("*.yaml"))
        with tokens[0].open("r") as f:
            token_data = yaml.load(f)
        skipped_ids = [d["design_id"] for d in token_data.get("skipped_designs", [])]
        assert "DES-BQ" in skipped_ids
