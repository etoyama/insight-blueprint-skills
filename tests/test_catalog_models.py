"""Tests for catalog Pydantic models.

E5c / ADR-0004: source ``type`` and knowledge ``category`` are open strings
(any non-empty value is valid); the conventional values live in the
``KNOWN_*`` tuples for UX hints only. ``KnowledgeImportance`` stays a closed
enum (ordinal scale). ``ColumnSchema`` / ``DataSource`` allow extra fields.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from insight_blueprint.models.catalog import (
    FINDING,
    KNOWN_KNOWLEDGE_CATEGORIES,
    KNOWN_SOURCE_TYPES,
    ColumnSchema,
    DataSource,
    DomainKnowledge,
    DomainKnowledgeEntry,
    KnowledgeImportance,
)


def _source(**over: object) -> DataSource:
    kwargs: dict = {
        "id": "test-src",
        "name": "Test Source",
        "type": "csv",
        "description": "A test source",
        "connection": {"file_path": "data.csv"},
        "schema_info": {"columns": []},
    }
    kwargs.update(over)
    return DataSource(**kwargs)


class TestSourceTypeOpen:
    def test_known_source_types_are_conventional_values(self) -> None:
        assert ("csv", "api", "sql") == KNOWN_SOURCE_TYPES

    def test_accepts_arbitrary_source_type(self) -> None:
        # the whole point of E5c: new kinds without a library release
        for t in ("parquet", "gsheet", "bigquery", "graphql"):
            assert _source(type=t).type == t

    def test_rejects_empty_source_type(self) -> None:
        with pytest.raises(ValidationError):
            _source(type="")


class TestColumnSchema:
    def test_column_schema_instantiation_with_required_fields(self) -> None:
        col = ColumnSchema(name="age", type="integer", description="User age")
        assert col.name == "age"
        assert col.type == "integer"
        assert col.description == "User age"

    def test_column_schema_optional_fields_default_to_none(self) -> None:
        col = ColumnSchema(name="age", type="integer", description="User age")
        assert col.nullable is True
        assert col.examples is None
        assert col.range is None
        assert col.unit is None

    def test_column_schema_allows_extra_domain_metadata(self) -> None:
        # E5c: extra="allow" — domain metadata rides along and survives round-trip
        col = ColumnSchema(
            name="ssn",
            type="string",
            description="Social security number",
            pii=True,
            source_system="SAP",
        )
        data = col.model_dump()
        assert data["pii"] is True
        assert data["source_system"] == "SAP"
        assert ColumnSchema(**data).model_dump()["pii"] is True


class TestDataSource:
    def test_data_source_instantiation_with_all_required_fields(self) -> None:
        source = _source()
        assert source.id == "test-src"
        assert source.type == "csv"
        assert source.tags == []

    def test_data_source_timestamps_default_to_jst(self) -> None:
        source = _source(type="api")
        assert isinstance(source.created_at, datetime)
        assert isinstance(source.updated_at, datetime)
        assert source.created_at.tzinfo is not None
        assert str(source.created_at.tzinfo) == "Asia/Tokyo"

    def test_data_source_model_dump_json_round_trip(self) -> None:
        source = _source(
            id="round-trip",
            type="sql",
            connection={"provider": "bigquery", "project_id": "my-proj"},
            tags=["test", "demo"],
        )
        data = source.model_dump(mode="json")
        restored = DataSource(**data)
        assert restored.id == source.id
        assert restored.type == source.type
        assert restored.tags == source.tags
        assert restored.connection == source.connection

    def test_data_source_allows_extra_fields(self) -> None:
        # E5c: extra="allow" on the source itself too
        source = _source(owner="data-team", refresh="daily")
        assert source.model_dump()["owner"] == "data-team"


class TestKnowledgeCategoryOpen:
    def test_known_categories_include_conventional_values(self) -> None:
        assert set(KNOWN_KNOWLEDGE_CATEGORIES) == {
            "methodology",
            "caution",
            "definition",
            "context",
            "finding",
        }

    def test_finding_constant(self) -> None:
        assert FINDING == "finding"
        assert FINDING in KNOWN_KNOWLEDGE_CATEGORIES

    def test_accepts_arbitrary_category(self) -> None:
        for cat in ("data-quality", "regulatory", "seasonality", "glossary"):
            entry = DomainKnowledgeEntry(
                key=f"k-{cat}", title="t", content="c", category=cat
            )
            assert entry.category == cat

    def test_rejects_empty_category(self) -> None:
        with pytest.raises(ValidationError):
            DomainKnowledgeEntry(key="k", title="t", content="c", category="")

    def test_category_round_trip(self) -> None:
        entry = DomainKnowledgeEntry(
            key="compat-test", title="t", content="c", category="methodology"
        )
        restored = DomainKnowledgeEntry(**entry.model_dump(mode="json"))
        assert restored.category == "methodology"


class TestKnowledgeImportanceClosed:
    def test_importance_enum_values(self) -> None:
        # E5c keeps importance a closed ordinal scale (drives sort/UX)
        assert KnowledgeImportance.high == "high"
        assert KnowledgeImportance.medium == "medium"
        assert KnowledgeImportance.low == "low"
        assert len(KnowledgeImportance) == 3

    def test_importance_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            DomainKnowledgeEntry(
                key="k", title="t", content="c", category="caution", importance="urgent"
            )


class TestDomainKnowledge:
    def test_domain_knowledge_entry_instantiation(self) -> None:
        entry = DomainKnowledgeEntry(
            key="test-entry",
            title="Test Entry",
            content="Some knowledge content",
            category="caution",
            importance=KnowledgeImportance.high,
        )
        assert entry.key == "test-entry"
        assert entry.category == "caution"
        assert entry.importance == KnowledgeImportance.high
        assert entry.source is None
        assert entry.affects_columns == []

    def test_domain_knowledge_container_with_empty_entries(self) -> None:
        dk = DomainKnowledge(source_id="test-source")
        assert dk.source_id == "test-source"
        assert dk.entries == []
