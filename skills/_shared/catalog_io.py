"""Server-free YAML I/O for the data catalog (Epic 3.5).

Skills call this instead of the catalog MCP tools. It replicates CatalogService
behaviour (source CRUD, schema, knowledge read) and replaces the SQLite FTS5
search with a glob + projection file search. Depends only on modules that
survive the server removal (E4): ``insight_blueprint.models.catalog``.

Search returns *compact* hits (id/name/snippet); full documents are fetched
on demand via ``get`` / ``get-knowledge`` — the same token-lean idiom as the
memory index. Skills invoke it as a CLI:

    echo '<json>' | python -m skills._shared.catalog_io create --base-dir .insight
    python -m skills._shared.catalog_io search --query "人口" --base-dir .insight
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from insight_blueprint.models.catalog import (
    ColumnSchema,
    DataSource,
    DomainKnowledge,
    DomainKnowledgeEntry,
)
from insight_blueprint.models.common import now_jst
from skills._shared._atomic import atomic_write_yaml
from skills._shared._stdin import read_payload
from skills._shared.ids import SAFE_ID_PATTERN

DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))


def _resolve_base_dir(base_dir: Path) -> Path:
    """Normalize the I/O base and reject an absurd anchor (defense in depth).

    ``INSIGHT_BASE_DIR`` / ``--base-dir`` flow verbatim into every read/write path, so an
    attacker-influenceable value should not be trusted as-is. We only reject genuinely
    absurd anchors (the filesystem root or the bare home dir) rather than enforcing a
    ``.insight`` suffix — the bin wrapper owns that stricter check, and tests / --base-dir
    back-compat legitimately use tmp dirs. Mirrors design_io._resolve_base_dir.
    See docs/adr/0006-plugin-execution-model.md and review-security-epic09.md (M1).
    """
    resolved = base_dir.expanduser().resolve()
    if resolved.parent == resolved:  # filesystem root, e.g. "/"
        raise ValueError(
            f"Invalid base_dir '{base_dir}': resolves to the filesystem root"
        )
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    if home is not None and resolved == home:
        raise ValueError(
            f"Invalid base_dir '{base_dir}': resolves to the home directory"
        )
    return resolved


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _sources_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "catalog" / "sources"


def _knowledge_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "catalog" / "knowledge"


def _validate_id(value: str) -> None:
    if not SAFE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid source_id '{value}': must match [a-zA-Z0-9_-]+")


def read_yaml(path: Path) -> dict:
    """Read a YAML file into a dict; {} if missing or empty."""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = _yaml().load(f)
    return dict(data) if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict) -> None:
    """Atomic YAML write (thin passthrough to _atomic; exposed for skills/tests)."""
    atomic_write_yaml(Path(path), data)


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------


def load_source(source_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    _validate_id(source_id)
    return read_yaml(_sources_dir(base_dir) / f"{source_id}.yaml")


def list_sources(base_dir: Path = DEFAULT_BASE_DIR) -> list[dict]:
    sources_dir = _sources_dir(base_dir)
    if not sources_dir.exists():
        return []
    out: list[dict] = []
    for path in sorted(sources_dir.glob("*.yaml")):
        data = read_yaml(path)
        if data:
            out.append(data)
    return out


# Key-name fragments that mark a credential (ADR-0023). Keys are compared lowercased
# with every non-alphanumeric character dropped, so api_key, API-Key, api.key and apiKey
# all match. Values are not checked: a secret cannot be told from an id or a hash
# without false alarms. The one exception is a *_env key, whose value must look like an
# environment variable name, or the exemption would let a literal secret through.
# The exemption matches the lowercased `_env` suffix exactly, so apiKeyEnv is refused,
# and only for a credential stem: conda_env keeps any value.
_CREDENTIAL_KEY_PARTS = (
    "password",
    "passwd",
    "passphrase",
    "secret",
    "token",
    "bearer",
    "apikey",
    "credential",
    "privatekey",
    "accesskey",
)
_ENV_VAR_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")


def _names_a_credential(key: str) -> bool:
    squashed = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in squashed for part in _CREDENTIAL_KEY_PARTS)


def _credential_keys(value: Any, path: str = "connection") -> list[str]:
    if isinstance(value, list):
        return [
            key
            for index, item in enumerate(value)
            for key in _credential_keys(item, f"{path}[{index}]")
        ]
    if not isinstance(value, dict):
        return []
    found: list[str] = []
    for key, inner in value.items():
        name = str(key)
        here = f"{path}.{key}"
        if name.lower().endswith("_env") and _names_a_credential(name[:-4]):
            if not (isinstance(inner, str) and _ENV_VAR_NAME.fullmatch(inner)):
                found.append(here)
        elif _names_a_credential(name):
            found.append(here)
        else:
            found.extend(_credential_keys(inner, here))
    return found


def _reject_credentials(connection: Any) -> None:
    # Name the keys, never their values: the message lands in a model's context.
    if connection is not None and not isinstance(connection, dict):
        raise ValueError("connection must be an object (ADR-0023)")
    keys = _credential_keys(connection)
    if keys:
        raise ValueError(
            f"connection holds credential keys ({', '.join(keys)}); the catalog "
            "stores no credentials (ADR-0023). Keep the secret in an environment "
            "variable and put its name (A-Z, 0-9, _) in a key ending in _env "
            "(e.g. password_env: PG_PASSWORD). For a source already stored with "
            "one, the analyst edits its YAML by hand; do not read the source with "
            "--with-connection or open the file, since that puts the secret in "
            "the model's context."
        )


def create_source(
    *,
    id: str,
    name: str,
    type: str,
    description: str,
    connection: dict,
    columns: list[dict] | None = None,
    tags: list[str] | None = None,
    primary_key: list[str] | None = None,
    row_count_estimate: int | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Create a catalog source (+ empty knowledge file). Validates before writing."""
    _validate_id(id)
    source_path = _sources_dir(base_dir) / f"{id}.yaml"
    if source_path.exists():
        raise ValueError(f"Source '{id}' already exists")
    _reject_credentials(connection)

    schema_info: dict[str, Any] = {"columns": columns or []}
    if primary_key is not None:
        schema_info["primary_key"] = primary_key
    if row_count_estimate is not None:
        schema_info["row_count_estimate"] = row_count_estimate

    source = DataSource(
        id=id,
        name=name,
        type=type,  # open string (E5c); DataSource enforces non-empty
        description=description,
        connection=connection,
        schema_info=schema_info,
        tags=tags or [],
    )
    data = source.model_dump(mode="json")
    write_yaml(source_path, data)
    # Empty knowledge container, mirroring CatalogService.add_source.
    write_yaml(
        _knowledge_dir(base_dir) / f"{id}.yaml",
        DomainKnowledge(source_id=id).model_dump(mode="json"),
    )
    return data


def update_source(
    source_id: str, changes: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict:
    """Read-merge-write a source; refreshes updated_at. Raises if absent."""
    current = load_source(source_id, base_dir)
    if not current:
        raise ValueError(f"Source '{source_id}' not found")
    merged = {**current, **changes, "updated_at": now_jst().isoformat()}
    _reject_credentials(merged.get("connection"))
    source = DataSource.model_validate(merged)  # validates
    data = source.model_dump(mode="json")
    write_yaml(_sources_dir(base_dir) / f"{source_id}.yaml", data)
    return data


_DESCRIBED_FIELDS = ("id", "name", "type", "description")


def describe(source_ids: list[str], base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """The declared sources as a distributable report may show them (ADR-0020).

    Registered sources come back in the order given, once each, with only
    id/name/type/description. Every other value is ``missing``: an id that is not
    registered, or a value no catalog can hold because create_source rejects it.
    """
    sources: list[dict] = []
    missing: list[str] = []
    for source_id in dict.fromkeys(source_ids):
        source = (
            load_source(source_id, base_dir)
            if SAFE_ID_PATTERN.fullmatch(source_id)
            else {}
        )
        if source:
            sources.append({key: source[key] for key in _DESCRIBED_FIELDS})
        else:
            missing.append(source_id)
    return {"sources": sources, "missing": missing}


def get_schema(source_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    """Return the column schema of a source ({} if absent)."""
    data = load_source(source_id, base_dir)
    if not data:
        return {}
    schema_info = data.get("schema_info", {})
    columns = [ColumnSchema(**c).model_dump() for c in schema_info.get("columns", [])]
    return {
        "source_id": source_id,
        "columns": columns,
        "primary_key": schema_info.get("primary_key"),
        "row_count_estimate": schema_info.get("row_count_estimate"),
    }


# ---------------------------------------------------------------------------
# Knowledge (read + write; extraction itself is Claude-native, see /knowledge-extract)
# ---------------------------------------------------------------------------


def load_knowledge(source_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict:
    _validate_id(source_id)
    return read_yaml(_knowledge_dir(base_dir) / f"{source_id}.yaml")


def get_knowledge(
    source_id: str,
    category: str | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Load knowledge for a source, optionally filtered by category ({} if absent)."""
    data = load_knowledge(source_id, base_dir)
    if not data:
        return {}
    entries = data.get("entries", [])
    if category is not None:
        # category is an open string (E5c); filter by exact match, no enum coercion
        entries = [e for e in entries if e.get("category") == category]
    return {"source_id": data.get("source_id", source_id), "entries": entries}


def add_knowledge(
    source_id: str,
    entries: list[dict],
    base_dir: Path = DEFAULT_BASE_DIR,
) -> dict:
    """Append/upsert domain-knowledge entries for a registered source.

    Each entry is validated against ``DomainKnowledgeEntry`` and upserted by
    ``key`` (same key replaces in place, new key appends), then the whole
    container is written atomically. Raises if the source is not registered
    (knowledge is source-scoped; there is no orphan knowledge without a source).

    Extraction is Claude-native: the ``/knowledge-extract`` skill builds the
    entries; this function only validates and persists them.
    """
    _validate_id(source_id)
    if not load_source(source_id, base_dir):
        raise ValueError(f"Source '{source_id}' not found")

    validated = [DomainKnowledgeEntry.model_validate(e) for e in entries]

    current = load_knowledge(source_id, base_dir)
    merged: dict[str, dict] = {
        e["key"]: e for e in current.get("entries", []) if "key" in e
    }
    for entry in validated:
        merged[entry.key] = entry.model_dump(mode="json")

    container = DomainKnowledge.model_validate(
        {"source_id": source_id, "entries": list(merged.values())}
    ).model_dump(mode="json")
    write_yaml(_knowledge_dir(base_dir) / f"{source_id}.yaml", container)
    return container


# ---------------------------------------------------------------------------
# Search — glob + projection over sources and knowledge
# ---------------------------------------------------------------------------


def _snippet(text: str, needle: str, width: int = 40) -> str:
    idx = text.lower().find(needle.lower())
    if idx == -1:
        return text[:width]
    start = max(0, idx - 10)
    end = min(len(text), idx + len(needle) + 20)
    return (
        ("..." if start else "") + text[start:end] + ("..." if end < len(text) else "")
    )


def search(
    query: str,
    source_type: str | None = None,
    tags: list[str] | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
    limit: int = 20,
) -> list[dict]:
    """Search sources and knowledge by substring; return compact ranked hits.

    Each hit is a small dict (never the full document). Ranking is by match
    count (crude but adequate at catalog scale). Full docs: ``load_source`` /
    ``get_knowledge``.
    """
    q = query.strip().lower()
    if not q:
        return []

    hits: list[tuple[int, dict]] = []

    for data in list_sources(base_dir):
        if source_type is not None and data.get("type") != source_type:
            continue
        if tags is not None and not (set(tags) & set(data.get("tags", []))):
            continue
        cols = data.get("schema_info", {}).get("columns", [])
        haystack = " ".join(
            [
                data.get("name", ""),
                data.get("description", ""),
                " ".join(data.get("tags", [])),
                " ".join(
                    f"{c.get('name', '')} {c.get('description', '')}" for c in cols
                ),
            ]
        )
        count = haystack.lower().count(q)
        if count:
            hits.append(
                (
                    count,
                    {
                        "doc_type": "source",
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "tags": data.get("tags", []),
                        "snippet": _snippet(data.get("description", ""), q),
                    },
                )
            )

    knowledge_dir = _knowledge_dir(base_dir)
    if knowledge_dir.exists():
        for path in sorted(knowledge_dir.glob("*.yaml")):
            kn = read_yaml(path)
            for entry in kn.get("entries", []):
                haystack = f"{entry.get('title', '')} {entry.get('content', '')}"
                count = haystack.lower().count(q)
                if count:
                    hits.append(
                        (
                            count,
                            {
                                "doc_type": "knowledge",
                                "id": kn.get("source_id"),
                                "title": entry.get("title"),
                                "category": entry.get("category"),
                                "snippet": _snippet(entry.get("content", ""), q),
                            },
                        )
                    )

    hits.sort(key=lambda t: t[0], reverse=True)
    return [h for _, h in hits[:limit]]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _without_connection(source: dict) -> dict:
    # A connection holds paths, queries, hosts and sometimes credentials, and whatever
    # the CLI prints lands in a model's context and can ride into a distributed report
    # (ADR-0018). The stored YAML and load_source() keep it.
    return {key: value for key, value in source.items() if key != "connection"}


# Every command whose result is a whole source. update belongs here too: a partial
# change echoes the stored connection, which the caller never supplied.
_PRINTS_SOURCES = frozenset({"create", "update", "get", "list"})


_TAKES_PAYLOAD = frozenset({"create", "update", "add-knowledge"})


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalog_io")
    parser.add_argument(
        "command",
        choices=[
            "create",
            "update",
            "get",
            "list",
            "describe",
            "get-schema",
            "search",
            "get-knowledge",
            "add-knowledge",
        ],
    )
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--id", default=None)
    parser.add_argument(
        "--ids", default=None, help="comma-separated source ids (describe)"
    )
    parser.add_argument("--query", default=None)
    parser.add_argument("--type", default=None)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--category", default=None)
    parser.add_argument(
        "--with-connection",
        action="store_true",
        help="include each printed source's connection (left out by default)",
    )
    args = parser.parse_args(argv)
    if args.command == "describe" and args.with_connection:
        # describe feeds a distributable report; say no rather than ignore the flag.
        parser.error("describe never prints a connection; use get --with-connection")
    base = _resolve_base_dir(Path(args.base_dir))

    payload = read_payload() if args.command in _TAKES_PAYLOAD else {}

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    if args.command == "create":
        result: Any = create_source(base_dir=base, **payload)
    elif args.command == "update":
        result = update_source(args.id, payload, base_dir=base)
    elif args.command == "get":
        result = load_source(args.id, base_dir=base)
    elif args.command == "list":
        result = list_sources(base_dir=base)
    elif args.command == "describe":
        ids = [i.strip() for i in (args.ids or "").split(",") if i.strip()]
        result = describe(ids, base_dir=base)
    elif args.command == "get-schema":
        result = get_schema(args.id, base_dir=base)
    elif args.command == "get-knowledge":
        result = get_knowledge(args.id, category=args.category, base_dir=base)
    elif args.command == "add-knowledge":
        result = add_knowledge(args.id, payload.get("entries", []), base_dir=base)
    elif args.command == "search":
        result = search(
            args.query or "",
            source_type=args.type,
            tags=tags,
            base_dir=base,
        )
    else:  # pragma: no cover - argparse restricts choices
        raise SystemExit(2)

    if args.command in _PRINTS_SOURCES and not args.with_connection:
        result = (
            [_without_connection(source) for source in result]
            if isinstance(result, list)
            else _without_connection(result)
        )

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
