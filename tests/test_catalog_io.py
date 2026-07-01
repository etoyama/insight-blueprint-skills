"""Unit tests for skills/_shared/catalog_io.py (Epic 3.5, Story 3.5.1).

catalog_io is the server-free YAML I/O helper for the data catalog. It replaces
the CatalogService + SQLite FTS5 path with glob + projection search, depending
only on insight_blueprint.models.catalog (which survives the E4 server removal).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skills._shared import catalog_io


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "catalog" / "sources").mkdir(parents=True)
    (base / "catalog" / "knowledge").mkdir(parents=True)
    return base


def _create(insight: Path, **over: object) -> dict:
    kwargs: dict = {
        "id": "jp-pop",
        "name": "人口統計",
        "type": "csv",
        "description": "市区町村別の人口データ",
        "connection": {"path": "data/pop.csv"},
        "columns": [
            {"name": "pref", "type": "str", "description": "都道府県"},
            {"name": "population", "type": "int", "description": "人口"},
        ],
        "tags": ["gov"],
        "base_dir": insight,
    }
    kwargs.update(over)
    return catalog_io.create_source(**kwargs)


# ---------------------------------------------------------------------------
# create / load / list
# ---------------------------------------------------------------------------


class TestCreateSource:
    def test_creates_source_and_empty_knowledge(self, insight: Path) -> None:
        d = _create(insight)
        assert d["id"] == "jp-pop"
        assert (insight / "catalog" / "sources" / "jp-pop.yaml").exists()
        # empty knowledge file created alongside
        assert (insight / "catalog" / "knowledge" / "jp-pop.yaml").exists()
        kn = catalog_io.load_knowledge("jp-pop", base_dir=insight)
        assert kn["source_id"] == "jp-pop"
        assert kn["entries"] == []

    def test_invalid_id_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError):
            _create(insight, id="bad id/slash")

    def test_invalid_type_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError):
            _create(insight, type="parquet")

    def test_duplicate_rejected(self, insight: Path) -> None:
        _create(insight)
        with pytest.raises(ValueError, match="exists"):
            _create(insight)


class TestLoadList:
    def test_load_missing_returns_empty(self, insight: Path) -> None:
        assert catalog_io.load_source("nope", base_dir=insight) == {}

    def test_list_sorted(self, insight: Path) -> None:
        _create(insight, id="b-src")
        _create(insight, id="a-src")
        ids = [s["id"] for s in catalog_io.list_sources(base_dir=insight)]
        assert ids == ["a-src", "b-src"]


# ---------------------------------------------------------------------------
# schema / update
# ---------------------------------------------------------------------------


class TestSchemaUpdate:
    def test_get_schema(self, insight: Path) -> None:
        _create(insight)
        schema = catalog_io.get_schema("jp-pop", base_dir=insight)
        assert schema["source_id"] == "jp-pop"
        assert [c["name"] for c in schema["columns"]] == ["pref", "population"]

    def test_update_source(self, insight: Path) -> None:
        _create(insight)
        updated = catalog_io.update_source(
            "jp-pop", {"description": "更新後"}, base_dir=insight
        )
        assert updated["description"] == "更新後"
        assert updated["updated_at"] >= updated["created_at"]

    def test_update_missing_raises(self, insight: Path) -> None:
        with pytest.raises(ValueError):
            catalog_io.update_source("nope", {"description": "x"}, base_dir=insight)


# ---------------------------------------------------------------------------
# knowledge
# ---------------------------------------------------------------------------


class TestKnowledge:
    def test_get_knowledge_filter_by_category(self, insight: Path) -> None:
        _create(insight)
        # seed knowledge directly (E3.5 doesn't add a knowledge-writer; test read path)
        kn_path = insight / "catalog" / "knowledge" / "jp-pop.yaml"
        catalog_io.write_yaml(
            kn_path,
            {
                "source_id": "jp-pop",
                "entries": [
                    {
                        "key": "k1",
                        "title": "欠損注意",
                        "content": "人口は欠損あり",
                        "category": "caution",
                    },
                    {
                        "key": "k2",
                        "title": "定義",
                        "content": "人口=常住人口",
                        "category": "definition",
                    },
                ],
            },
        )
        cautions = catalog_io.get_knowledge(
            "jp-pop", category="caution", base_dir=insight
        )
        assert [e["key"] for e in cautions["entries"]] == ["k1"]
        all_kn = catalog_io.get_knowledge("jp-pop", base_dir=insight)
        assert len(all_kn["entries"]) == 2


# ---------------------------------------------------------------------------
# search (glob + projection, source + knowledge)
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_matches_source_description(self, insight: Path) -> None:
        _create(insight)
        hits = catalog_io.search("人口", base_dir=insight)
        assert any(h["doc_type"] == "source" and h["id"] == "jp-pop" for h in hits)

    def test_search_matches_column_name(self, insight: Path) -> None:
        _create(insight)
        hits = catalog_io.search("population", base_dir=insight)
        assert any(h["id"] == "jp-pop" for h in hits)

    def test_search_spans_knowledge(self, insight: Path) -> None:
        _create(insight)
        catalog_io.write_yaml(
            insight / "catalog" / "knowledge" / "jp-pop.yaml",
            {
                "source_id": "jp-pop",
                "entries": [
                    {
                        "key": "k1",
                        "title": "季節調整",
                        "content": "季節調整が必要",
                        "category": "methodology",
                    }
                ],
            },
        )
        hits = catalog_io.search("季節調整", base_dir=insight)
        assert any(h["doc_type"] == "knowledge" and h["id"] == "jp-pop" for h in hits)

    def test_search_returns_compact_not_full(self, insight: Path) -> None:
        _create(insight)
        hits = catalog_io.search("人口", base_dir=insight)
        src = next(h for h in hits if h["doc_type"] == "source")
        # compact: no full connection/schema_info payload
        assert "connection" not in src
        assert "schema_info" not in src
        assert {"doc_type", "id", "name"} <= set(src)

    def test_search_type_filter(self, insight: Path) -> None:
        _create(insight, id="csv-src", type="csv")
        _create(insight, id="api-src", type="api")
        hits = catalog_io.search("人口", source_type="api", base_dir=insight)
        assert all(h["id"] != "csv-src" for h in hits)

    def test_search_empty_query_returns_empty(self, insight: Path) -> None:
        _create(insight)
        assert catalog_io.search("", base_dir=insight) == []

    def test_search_no_match(self, insight: Path) -> None:
        _create(insight)
        assert catalog_io.search("まったく無関係なクエリxyz", base_dir=insight) == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_create_and_search(self, insight: Path) -> None:
        payload = {
            "id": "cli-src",
            "name": "CLI源",
            "type": "csv",
            "description": "テスト用のソース",
            "connection": {"path": "x.csv"},
            "columns": [{"name": "col", "type": "str", "description": "列"}],
        }
        root = Path(__file__).resolve().parents[1]
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills._shared.catalog_io",
                "create",
                "--base-dir",
                str(insight),
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["id"] == "cli-src"

        res2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills._shared.catalog_io",
                "search",
                "--query",
                "テスト",
                "--base-dir",
                str(insight),
            ],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        assert res2.returncode == 0, res2.stderr
        assert any(h["id"] == "cli-src" for h in json.loads(res2.stdout))
