"""PremortemConfig loading tests (Epic 5a: static row thresholds only)."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from skills._shared.config_loader import load_premortem_config
from skills._shared.models import PremortemConfig


def _write(path: Path, data: dict) -> None:
    yaml = YAML()
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


def test_defaults_when_missing(tmp_path: Path) -> None:
    cfg = load_premortem_config(tmp_path / "nope.yaml")
    assert cfg == PremortemConfig()
    assert cfg.static_rows_high == 10_000_000
    assert cfg.static_rows_medium == 1_000_000


def test_partial_override(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    _write(path, {"premortem": {"static_rows_high": 5_000_000}})
    cfg = load_premortem_config(path)
    assert cfg.static_rows_high == 5_000_000
    assert cfg.static_rows_medium == 1_000_000  # default retained


def test_both_thresholds(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    _write(path, {"premortem": {"static_rows_high": 9, "static_rows_medium": 3}})
    cfg = load_premortem_config(path)
    assert (cfg.static_rows_high, cfg.static_rows_medium) == (9, 3)


def test_ignores_unknown_and_batch_keys(tmp_path: Path) -> None:
    """Legacy batch/history keys are ignored (removed in E5a)."""
    path = tmp_path / "config.yaml"
    _write(
        path,
        {
            "premortem": {"static_rows_high": 7, "history_min_samples": 5},
            "batch": {"automation": "auto"},
        },
    )
    cfg = load_premortem_config(path)
    assert cfg.static_rows_high == 7
