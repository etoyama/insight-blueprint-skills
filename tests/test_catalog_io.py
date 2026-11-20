"""Unit tests for skills/_shared/catalog_io.py (Epic 3.5, Story 3.5.1).

catalog_io is the server-free YAML I/O helper for the data catalog. It replaces
the CatalogService + SQLite FTS5 path with glob + projection search, depending
only on insight_blueprint.models.catalog (which survives the E4 server removal).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

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


_BAD_IDS = ["../evil", "a/b", "..", "x/../y", "", "with space"]


class TestBaseDirEnv:
    """DEFAULT_BASE_DIR honors INSIGHT_BASE_DIR (set by the bin/ wrappers, Epic 09)."""

    def test_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        monkeypatch.setenv("INSIGHT_BASE_DIR", "/tmp/ib-env/.insight")
        mod = importlib.reload(catalog_io)
        try:
            assert str(mod.DEFAULT_BASE_DIR) == "/tmp/ib-env/.insight"
        finally:
            monkeypatch.delenv("INSIGHT_BASE_DIR", raising=False)
            importlib.reload(mod)

    def test_default_is_dot_insight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        monkeypatch.delenv("INSIGHT_BASE_DIR", raising=False)
        mod = importlib.reload(catalog_io)
        assert str(mod.DEFAULT_BASE_DIR) == ".insight"


class TestResolveBaseDir:
    """_resolve_base_dir rejects an absurd anchor (defense in depth for M1, ADR-0006)."""

    def test_tmp_base_passes(self, tmp_path: Path) -> None:
        base = tmp_path / ".insight"
        assert catalog_io._resolve_base_dir(base) == base.resolve()

    def test_non_insight_leaf_passes(self, tmp_path: Path) -> None:
        # The .insight suffix is enforced by the wrapper, not here (back-compat / tests).
        base = tmp_path / "workdir"
        assert catalog_io._resolve_base_dir(base) == base.resolve()

    def test_filesystem_root_rejected(self) -> None:
        with pytest.raises(ValueError, match="filesystem root"):
            catalog_io._resolve_base_dir(Path("/"))

    def test_home_dir_rejected(self) -> None:
        with pytest.raises(ValueError, match="home directory"):
            catalog_io._resolve_base_dir(Path.home())


class TestIdValidation:
    """source_id is interpolated into paths — reject traversal on read/update too."""

    @pytest.mark.parametrize("bad", _BAD_IDS)
    def test_read_update_reject_bad_id(self, insight: Path, bad: str) -> None:
        with pytest.raises(ValueError):
            catalog_io.load_source(bad, base_dir=insight)
        with pytest.raises(ValueError):
            catalog_io.get_schema(bad, base_dir=insight)
        with pytest.raises(ValueError):
            catalog_io.load_knowledge(bad, base_dir=insight)
        with pytest.raises(ValueError):
            catalog_io.get_knowledge(bad, base_dir=insight)
        with pytest.raises(ValueError):
            catalog_io.update_source(bad, {}, base_dir=insight)
        with pytest.raises(ValueError):
            catalog_io.add_knowledge(bad, [], base_dir=insight)


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

    def test_open_source_type_accepted(self, insight: Path) -> None:
        # E5c: source type is an open string; new kinds need no library release
        d = _create(insight, id="pq-src", type="parquet")
        assert d["type"] == "parquet"

    def test_empty_source_type_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError):
            _create(insight, id="empty-type", type="")

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
# add_knowledge (write / upsert-by-key; E5b)
# ---------------------------------------------------------------------------


def _entry(key: str, **over: object) -> dict:
    e: dict = {
        "key": key,
        "title": f"title-{key}",
        "content": f"content-{key}",
        "category": "caution",
    }
    e.update(over)
    return e


class TestAddKnowledge:
    def test_appends_entries_to_empty_source(self, insight: Path) -> None:
        _create(insight)
        result = catalog_io.add_knowledge(
            "jp-pop", [_entry("k1"), _entry("k2")], base_dir=insight
        )
        assert [e["key"] for e in result["entries"]] == ["k1", "k2"]
        # persisted round-trip
        reloaded = catalog_io.get_knowledge("jp-pop", base_dir=insight)
        assert [e["key"] for e in reloaded["entries"]] == ["k1", "k2"]

    def test_upsert_by_key_replaces_in_place(self, insight: Path) -> None:
        _create(insight)
        catalog_io.add_knowledge(
            "jp-pop", [_entry("k1", content="old"), _entry("k2")], base_dir=insight
        )
        catalog_io.add_knowledge(
            "jp-pop", [_entry("k1", content="new")], base_dir=insight
        )
        entries = catalog_io.get_knowledge("jp-pop", base_dir=insight)["entries"]
        # k1 updated in place (still first), k2 preserved — no duplicate key
        assert [e["key"] for e in entries] == ["k1", "k2"]
        k1 = next(e for e in entries if e["key"] == "k1")
        assert k1["content"] == "new"

    def test_new_keys_append_after_existing(self, insight: Path) -> None:
        _create(insight)
        catalog_io.add_knowledge("jp-pop", [_entry("k1")], base_dir=insight)
        catalog_io.add_knowledge("jp-pop", [_entry("k2")], base_dir=insight)
        entries = catalog_io.get_knowledge("jp-pop", base_dir=insight)["entries"]
        assert [e["key"] for e in entries] == ["k1", "k2"]

    def test_unknown_source_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            catalog_io.add_knowledge("nope", [_entry("k1")], base_dir=insight)

    def test_invalid_entry_rejected(self, insight: Path) -> None:
        _create(insight)
        # missing required 'content' -> Pydantic validation error, nothing written
        with pytest.raises(ValidationError):
            catalog_io.add_knowledge(
                "jp-pop",
                [{"key": "k1", "title": "t", "category": "caution"}],
                base_dir=insight,
            )
        assert catalog_io.get_knowledge("jp-pop", base_dir=insight)["entries"] == []

    def test_open_category_accepted(self, insight: Path) -> None:
        # E5c: category is an open string; domain-specific categories are allowed
        _create(insight)
        result = catalog_io.add_knowledge(
            "jp-pop", [_entry("k1", category="data-quality")], base_dir=insight
        )
        assert result["entries"][0]["category"] == "data-quality"

    def test_empty_category_rejected(self, insight: Path) -> None:
        _create(insight)
        with pytest.raises(ValidationError):
            catalog_io.add_knowledge(
                "jp-pop", [_entry("k1", category="")], base_dir=insight
            )

    def test_importance_defaults_to_medium(self, insight: Path) -> None:
        _create(insight)
        result = catalog_io.add_knowledge("jp-pop", [_entry("k1")], base_dir=insight)
        assert result["entries"][0]["importance"] == "medium"


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

    def test_cli_add_knowledge_stdin_to_file(self, insight: Path) -> None:
        _create(insight)
        root = Path(__file__).resolve().parents[1]
        payload = {
            "entries": [
                {
                    "key": "seasonal",
                    "title": "季節調整",
                    "content": "人口は季節調整が必要",
                    "category": "methodology",
                }
            ]
        }
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills._shared.catalog_io",
                "add-knowledge",
                "--id",
                "jp-pop",
                "--base-dir",
                str(insight),
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["entries"][0]["key"] == "seasonal"
        # persisted to the source-scoped knowledge file
        reloaded = catalog_io.get_knowledge("jp-pop", base_dir=insight)
        assert [e["key"] for e in reloaded["entries"]] == ["seasonal"]


def _run_cli(
    insight: Path, *args: str, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "skills._shared.catalog_io",
            *args,
            "--base-dir",
            str(insight),
        ],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


class TestCliKeepsTheConnectionBack:
    """ADR-0018: reading a source prints no `connection` unless the caller asks for it."""

    SECRET = "/Users/someone/secret/pop.csv"

    def _register(self, insight: Path) -> None:
        _create(insight, connection={"file_path": self.SECRET})
        # A source stored before ADR-0023 may still hold a credential; reading it
        # back must not change, so the read tests keep one in the stored YAML.
        path = insight / "catalog" / "sources" / "jp-pop.yaml"
        stored = catalog_io.read_yaml(path)
        stored["connection"]["password"] = "hunter2"
        catalog_io.write_yaml(path, stored)

    def test_get_prints_the_source_without_its_connection(self, insight: Path) -> None:
        self._register(insight)
        res = _run_cli(insight, "get", "--id", "jp-pop")
        assert res.returncode == 0, res.stderr
        source = json.loads(res.stdout)
        assert "connection" not in source
        assert self.SECRET not in res.stdout and "hunter2" not in res.stdout
        assert (source["name"], source["type"]) == ("人口統計", "csv")
        assert source["description"] == "市区町村別の人口データ"

    def test_get_prints_the_connection_when_asked(self, insight: Path) -> None:
        self._register(insight)
        res = _run_cli(insight, "get", "--id", "jp-pop", "--with-connection")
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["connection"]["file_path"] == self.SECRET

    def test_get_still_prints_an_empty_object_for_an_unregistered_id(
        self, insight: Path
    ) -> None:
        res = _run_cli(insight, "get", "--id", "nope")
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout) == {}

    def test_list_prints_every_source_without_its_connection(
        self, insight: Path
    ) -> None:
        self._register(insight)
        res = _run_cli(insight, "list")
        assert res.returncode == 0, res.stderr
        assert [s["id"] for s in json.loads(res.stdout)] == ["jp-pop"]
        assert "connection" not in res.stdout
        assert self.SECRET not in res.stdout

    def test_list_prints_the_connections_when_asked(self, insight: Path) -> None:
        self._register(insight)
        res = _run_cli(insight, "list", "--with-connection")
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)[0]["connection"]["file_path"] == self.SECRET

    def test_update_prints_the_source_without_its_stored_connection(
        self, insight: Path
    ) -> None:
        _create(insight, connection={"file_path": self.SECRET})
        res = _run_cli(
            insight, "update", "--id", "jp-pop", stdin='{"description": "新しい説明"}'
        )
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["description"] == "新しい説明"
        assert "connection" not in res.stdout
        assert self.SECRET not in res.stdout
        stored = catalog_io.load_source("jp-pop", base_dir=insight)
        assert stored["connection"]["file_path"] == self.SECRET

    def test_create_prints_the_source_without_its_connection(
        self, insight: Path
    ) -> None:
        payload = {
            "id": "cli-src",
            "name": "CLI源",
            "type": "csv",
            "description": "テスト用のソース",
            "connection": {"file_path": self.SECRET},
        }
        res = _run_cli(insight, "create", stdin=json.dumps(payload))
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["id"] == "cli-src"
        assert "connection" not in res.stdout
        assert self.SECRET not in res.stdout

    def test_update_prints_the_connection_when_asked(self, insight: Path) -> None:
        _create(insight, connection={"file_path": self.SECRET})
        res = _run_cli(
            insight, "update", "--id", "jp-pop", "--with-connection", stdin="{}"
        )
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout)["connection"]["file_path"] == self.SECRET


class TestConnectionHoldsNoCredentials:
    """ADR-0023: the catalog refuses a connection key that names a credential."""

    @pytest.mark.parametrize(
        ("connection", "key"),
        [
            ({"password": "hunter2"}, "connection.password"),
            ({"API-Key": "abc123"}, "connection.API-Key"),
            ({"apiKey": "abc123"}, "connection.apiKey"),
            ({"auth": {"client_secret": "s3"}}, "connection.auth.client_secret"),
            ({"hosts": [{"token": "t0k"}]}, "connection.hosts[0].token"),
            ({"private_key": "-----BEGIN"}, "connection.private_key"),
            ({"aws_access_key_id": "AKIA"}, "connection.aws_access_key_id"),
            ({"credentials": {"user": "u"}}, "connection.credentials"),
            ({"api.key": "abc123"}, "connection.api.key"),
            ({"ssh_passphrase": "s3"}, "connection.ssh_passphrase"),
            ({"bearer": "t0k"}, "connection.bearer"),
            ({"password_env": "hunter2"}, "connection.password_env"),
            ({"token_env": "export X=t0k"}, "connection.token_env"),
        ],
    )
    def test_create_refuses_a_credential_key_and_writes_nothing(
        self, insight: Path, connection: dict, key: str
    ) -> None:
        with pytest.raises(ValueError, match=re.escape(key)) as err:
            _create(insight, connection=connection)
        assert not (insight / "catalog" / "sources" / "jp-pop.yaml").exists()
        for value in ("hunter2", "abc123", "s3", "t0k", "-----BEGIN", "AKIA"):
            assert value not in str(err.value)
        assert "_env" in str(err.value)

    def test_create_accepts_the_name_of_an_environment_variable(
        self, insight: Path
    ) -> None:
        connection = {"password_env": "PG_PASSWORD", "auth": "api_key"}
        assert _create(insight, connection=connection)["connection"] == connection

    def test_update_refuses_a_credential_key_and_keeps_the_stored_source(
        self, insight: Path
    ) -> None:
        _create(insight)
        with pytest.raises(ValueError, match="connection.token"):
            catalog_io.update_source(
                "jp-pop", {"connection": {"token": "t0k"}}, base_dir=insight
            )
        stored = catalog_io.load_source("jp-pop", base_dir=insight)
        assert stored["connection"] == {"path": "data/pop.csv"}

    def test_a_stored_credential_is_still_read_but_blocks_an_update(
        self, insight: Path
    ) -> None:
        _create(insight)
        path = insight / "catalog" / "sources" / "jp-pop.yaml"
        stored = catalog_io.read_yaml(path)
        stored["connection"]["password"] = "hunter2"
        catalog_io.write_yaml(path, stored)

        assert (
            catalog_io.load_source("jp-pop", base_dir=insight)["connection"]["password"]
            == "hunter2"
        )
        with pytest.raises(ValueError, match="connection.password"):
            catalog_io.update_source("jp-pop", {"description": "x"}, base_dir=insight)
        fixed = catalog_io.update_source(
            "jp-pop",
            {"connection": {"path": "data/pop.csv", "password_env": "PG_PASSWORD"}},
            base_dir=insight,
        )
        assert "password" not in fixed["connection"]

    def test_the_cli_exits_non_zero_and_names_the_key_but_not_the_value(
        self, insight: Path
    ) -> None:
        payload = {
            "id": "cli-src",
            "name": "CLI源",
            "type": "csv",
            "description": "テスト用のソース",
            "connection": {"file_path": "data/x.csv", "password": "hunter2"},
        }
        res = _run_cli(insight, "create", stdin=json.dumps(payload))
        assert res.returncode != 0
        assert "connection.password" in res.stderr
        assert "hunter2" not in res.stderr + res.stdout
        assert not (insight / "catalog" / "sources" / "cli-src.yaml").exists()


class TestDescribe:
    """ADR-0020: the sources a design declares, as the report may show them."""

    def test_returns_the_registered_sources_in_the_order_given(
        self, insight: Path
    ) -> None:
        _create(insight)
        _create(insight, id="sales", name="月次売上", description="店舗別の売上")
        result = catalog_io.describe(["sales", "jp-pop"], base_dir=insight)
        assert result == {
            "sources": [
                {
                    "id": "sales",
                    "name": "月次売上",
                    "type": "csv",
                    "description": "店舗別の売上",
                },
                {
                    "id": "jp-pop",
                    "name": "人口統計",
                    "type": "csv",
                    "description": "市区町村別の人口データ",
                },
            ],
            "missing": [],
        }

    def test_a_repeated_id_appears_once(self, insight: Path) -> None:
        _create(insight)
        result = catalog_io.describe(["jp-pop", "jp-pop", "nope", "nope"], insight)
        assert [s["id"] for s in result["sources"]] == ["jp-pop"]
        assert result["missing"] == ["nope"]

    def test_an_unregistered_id_is_missing(self, insight: Path) -> None:
        _create(insight)
        result = catalog_io.describe(["nope", "jp-pop"], base_dir=insight)
        assert [s["id"] for s in result["sources"]] == ["jp-pop"]
        assert result["missing"] == ["nope"]

    @pytest.mark.parametrize("bad", _BAD_IDS)
    def test_a_value_that_is_not_an_id_is_missing(
        self, insight: Path, bad: str
    ) -> None:
        # create_source rejects these, so no catalog can hold them.
        assert catalog_io.describe([bad], base_dir=insight) == {
            "sources": [],
            "missing": [bad],
        }

    def test_cli_never_prints_the_connection(self, insight: Path) -> None:
        secret = "/Users/someone/secret/pop.csv"
        _create(insight, connection={"file_path": secret})
        res = _run_cli(insight, "describe", "--ids=jp-pop,nope")
        assert res.returncode == 0, res.stderr
        assert secret not in res.stdout and "connection" not in res.stdout
        result = json.loads(res.stdout)
        assert [s["id"] for s in result["sources"]] == ["jp-pop"]
        assert result["missing"] == ["nope"]

    def test_cli_refuses_to_describe_with_the_connection(self, insight: Path) -> None:
        _create(insight)
        res = _run_cli(insight, "describe", "--ids=jp-pop", "--with-connection")
        assert res.returncode == 2
        assert res.stdout == ""

    def test_cli_takes_an_id_that_starts_with_a_dash(self, insight: Path) -> None:
        _create(insight, id="-dash")
        res = _run_cli(insight, "describe", "--ids=-dash")
        assert res.returncode == 0, res.stderr
        assert [s["id"] for s in json.loads(res.stdout)["sources"]] == ["-dash"]

    def test_cli_with_no_ids_describes_nothing(self, insight: Path) -> None:
        res = _run_cli(insight, "describe", "--ids=")
        assert res.returncode == 0, res.stderr
        assert json.loads(res.stdout) == {"sources": [], "missing": []}
