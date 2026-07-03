"""Report-only premortem CLI tests (Epic 5a).

premortem no longer issues tokens or reads run history — it prints a static
risk table and exits 2 when any design is HARD_BLOCK/HIGH, else 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.premortem.cli import main


def _payload() -> dict:
    return {
        "designs": [
            {"id": "FP-H01", "intent": "confirmatory", "status": "in_review"},
            {"id": "FP-H02", "intent": "exploratory", "status": "in_review"},
        ],
        "source_checks_map": {
            "FP-H01": {
                "source_registered": True,
                "location_ok": True,
                "allowlist_ok": True,
                "estimated_rows": 1000,
            },
            "FP-H02": {
                "source_registered": False,
                "location_ok": True,
                "allowlist_ok": True,
                "estimated_rows": 5000,
            },
        },
    }


def test_exit_2_when_hard_block(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(argv=["--base-dir", "/tmp/nope"], stdin_data=_payload())
    out = capsys.readouterr()
    assert rc == 2  # FP-H02 not registered -> HARD_BLOCK
    assert "FP-H01" in out.out and "FP-H02" in out.out
    assert "hard_block" in out.out
    assert "low" in out.out  # FP-H01 small rows


def test_exit_0_when_all_low(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "designs": [{"id": "A", "intent": "x", "status": "in_review"}],
        "source_checks_map": {
            "A": {
                "source_registered": True,
                "location_ok": True,
                "allowlist_ok": True,
                "estimated_rows": 10,
            }
        },
    }
    rc = main(argv=[], stdin_data=payload)
    assert rc == 0


def test_high_rows_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "designs": [{"id": "A", "intent": "x", "status": "in_review"}],
        "source_checks_map": {
            "A": {
                "source_registered": True,
                "location_ok": True,
                "allowlist_ok": True,
                "estimated_rows": 50_000_000,
            }
        },
    }
    assert main(argv=[], stdin_data=payload) == 2


def test_design_filter(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(argv=["--design", "FP-H01"], stdin_data=_payload())
    out = capsys.readouterr()
    assert rc == 0  # only FP-H01 (low), FP-H02 filtered out
    assert "FP-H01" in out.out and "FP-H02" not in out.out


def test_empty_payload_exit_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv=[], stdin_data={"designs": [], "source_checks_map": {}}) == 0


def test_no_token_written(tmp_path: Path) -> None:
    """Report-only: nothing is written under .insight/premortem/."""
    main(argv=["--base-dir", str(tmp_path / ".insight")], stdin_data=_payload())
    assert not (tmp_path / ".insight" / "premortem").exists()


# ---------------------------------------------------------------------------
# config resolution (Epic 09): the wrapper exports INSIGHT_BASE_DIR and the CLI
# must read <base_dir>/config.yaml from the *user project*, not the plugin root.
# ---------------------------------------------------------------------------


def _low_row_payload() -> dict:
    """A registered source with 1000 rows -> LOW under defaults (< 1M)."""
    return {
        "designs": [{"id": "A", "intent": "x", "status": "in_review"}],
        "source_checks_map": {
            "A": {
                "source_registered": True,
                "location_ok": True,
                "allowlist_ok": True,
                "estimated_rows": 1000,
            }
        },
    }


def _write_tuned_config(base: Path) -> None:
    """Config that lowers static_rows_high so 1000 rows becomes HIGH."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "config.yaml").write_text(
        "premortem:\n  static_rows_high: 500\n", encoding="utf-8"
    )


def test_config_read_from_base_dir(tmp_path: Path) -> None:
    """--base-dir drives the config path (previously dead code)."""
    base = tmp_path / ".insight"
    _write_tuned_config(base)
    # Default thresholds -> LOW (rc 0). Tuned config -> HIGH (rc 2).
    assert main(argv=[], stdin_data=_low_row_payload()) == 0
    rc = main(argv=["--base-dir", str(base)], stdin_data=_low_row_payload())
    assert rc == 2  # config.yaml under base_dir was honored


def test_config_read_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """INSIGHT_BASE_DIR (set by bin/premortem) resolves the config path."""
    import importlib

    import skills.premortem.cli as cli_mod

    base = tmp_path / ".insight"
    _write_tuned_config(base)
    monkeypatch.setenv("INSIGHT_BASE_DIR", str(base))
    reloaded = importlib.reload(cli_mod)
    try:
        rc = reloaded.main(argv=[], stdin_data=_low_row_payload())
        assert rc == 2  # env-derived config.yaml was honored
    finally:
        monkeypatch.delenv("INSIGHT_BASE_DIR", raising=False)
        importlib.reload(cli_mod)
