"""Load PremortemConfig from .insight/config.yaml with default merging."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from skills._shared.models import PremortemConfig

# Mapping: config YAML key -> PremortemConfig field name (static risk thresholds)
_PREMORTEM_KEY_MAP: dict[str, str] = {
    "static_rows_high": "static_rows_high",
    "static_rows_medium": "static_rows_medium",
}


def load_premortem_config(path: Path) -> PremortemConfig:
    """Load config from *path*, merging with defaults.

    If the file does not exist or the ``premortem`` section is absent,
    ``PremortemConfig()`` defaults are used.
    """
    path = Path(path)
    if not path.exists():
        return PremortemConfig()

    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.load(f)

    if not isinstance(raw, dict):
        return PremortemConfig()

    overrides: dict[str, object] = {}
    premortem_section = raw.get("premortem")
    if isinstance(premortem_section, dict):
        for yaml_key, field_name in _PREMORTEM_KEY_MAP.items():
            if yaml_key in premortem_section:
                overrides[field_name] = premortem_section[yaml_key]

    return PremortemConfig(**overrides)  # type: ignore[arg-type]
