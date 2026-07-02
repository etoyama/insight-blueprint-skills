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
    KnowledgeCategory,
    SourceType,
)
from insight_blueprint.models.common import now_jst
from skills._shared._atomic import atomic_write_yaml

DEFAULT_BASE_DIR = Path(".insight")

# Server-independent id check (mirrors core/validation.SAFE_ID_PATTERN).
SAFE_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")


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

    schema_info: dict[str, Any] = {"columns": columns or []}
    if primary_key is not None:
        schema_info["primary_key"] = primary_key
    if row_count_estimate is not None:
        schema_info["row_count_estimate"] = row_count_estimate

    source = DataSource(
        id=id,
        name=name,
        type=SourceType(type),  # raises ValueError on invalid type
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
    source = DataSource.model_validate(merged)  # validates
    data = source.model_dump(mode="json")
    write_yaml(_sources_dir(base_dir) / f"{source_id}.yaml", data)
    return data


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
        cat = KnowledgeCategory(category).value
        entries = [e for e in entries if e.get("category") == cat]
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


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalog_io")
    parser.add_argument(
        "command",
        choices=[
            "create",
            "update",
            "get",
            "list",
            "get-schema",
            "search",
            "get-knowledge",
            "add-knowledge",
        ],
    )
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--id", default=None)
    parser.add_argument("--query", default=None)
    parser.add_argument("--type", default=None)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--category", default=None)
    args = parser.parse_args(argv)
    base = Path(args.base_dir)

    payload: dict = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    if args.command == "create":
        result: Any = create_source(base_dir=base, **payload)
    elif args.command == "update":
        result = update_source(args.id, payload, base_dir=base)
    elif args.command == "get":
        result = load_source(args.id, base_dir=base)
    elif args.command == "list":
        result = list_sources(base_dir=base)
    elif args.command == "get-schema":
        result = get_schema(args.id, base_dir=base)
    elif args.command == "get-knowledge":
        result = get_knowledge(args.id, category=args.category, base_dir=base)
    elif args.command == "add-knowledge":
        result = add_knowledge(args.id, payload.get("entries", []), base_dir=base)
    elif args.command == "search":
        result = search(
            args.query or payload.get("query", ""),
            source_type=args.type,
            tags=tags,
            base_dir=base,
        )
    else:  # pragma: no cover - argparse restricts choices
        raise SystemExit(2)

    json.dump(result, sys.stdout, ensure_ascii=False, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
