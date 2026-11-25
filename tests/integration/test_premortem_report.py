"""Report-only premortem CLI tests (Epic 5a).

premortem no longer issues tokens or reads run history — it prints a static
risk table and exits 2 when any design is HARD_BLOCK/HIGH, else 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills._shared.design_io import create_design
from skills.premortem.cli import main


def _payload() -> dict:
    return {
        "designs": [
            {
                "id": "FP-H01",
                "analysis_intent": "confirmatory",
                "status": "in_review",
                "source_ids": ["src"],
            },
            {
                "id": "FP-H02",
                "analysis_intent": "exploratory",
                "status": "in_review",
                "source_ids": ["src"],
            },
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


def test_intent_column_shows_analysis_intent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """INTENT shows analysis_intent as design_io writes it, so a key drift fails."""
    # Each intent in the form create accepts for it (ADR-0048).
    forms = {
        "confirmatory": {"hypothesis_statement": "h", "hypothesis_background": "b"},
        "exploratory": {"exploration_question": "q", "exploration_background": "b"},
    }
    designs = [
        create_design(
            title="t",
            theme_id="FP",
            analysis_intent=intent,
            source_ids=["src"],
            base_dir=tmp_path,
            **fields,
        )
        for intent, fields in forms.items()
    ]
    main(
        argv=["--base-dir", str(tmp_path)],
        stdin_data={"designs": designs, "source_checks_map": {}},
    )
    rows = {
        line.split()[0]: line.split()[1]
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("FP-H")
    }
    assert rows == {"FP-H01": "confirmatory", "FP-H02": "exploratory"}


def test_exit_0_when_all_low(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "designs": [
            {
                "id": "A",
                "analysis_intent": "x",
                "status": "in_review",
                "source_ids": ["src"],
            }
        ],
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
        "designs": [
            {
                "id": "A",
                "analysis_intent": "x",
                "status": "in_review",
                "source_ids": ["src"],
            }
        ],
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
        "designs": [
            {
                "id": "A",
                "analysis_intent": "x",
                "status": "in_review",
                "source_ids": ["src"],
            }
        ],
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


def test_allowlist_stop_prints_where_to_declare_the_package(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-0021: the risk table tells the analyst how to allow the package."""
    payload = {
        "designs": [{"id": "AL-H01", "status": "in_review", "source_ids": ["src"]}],
        "source_checks_map": {"AL-H01": {"allowlist_ok": False}},
    }
    rc = main(argv=["--base-dir", "/tmp/nope"], stdin_data=payload)
    out = capsys.readouterr().out
    assert rc == 2
    assert "hard_block" in out
    assert "declare it in .insight/rules/package_allowlist.yaml" in out
