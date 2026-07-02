"""Pydantic data models for the data catalog (SPEC-2)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from insight_blueprint.models.common import now_jst

# Source `type` and knowledge `category` are open strings (E5c / ADR-0004): the
# catalog must accept new kinds (parquet, gsheet, bigquery, "regulatory", ...)
# without a library release. These tuples are the *conventional* values — used for
# UX hints / skill suggestions, NOT for validation. Any non-empty string is valid.
KNOWN_SOURCE_TYPES: tuple[str, ...] = ("csv", "api", "sql")

KNOWN_KNOWLEDGE_CATEGORIES: tuple[str, ...] = (
    "methodology",
    "caution",
    "definition",
    "context",
    "finding",
)

# Named constant for the one category with special handling (findings are kept in
# reflection, not the catalog — see /knowledge-extract, E5b).
FINDING = "finding"


class KnowledgeImportance(StrEnum):
    """Importance level of domain knowledge entry."""

    high = "high"
    medium = "medium"
    low = "low"


class ColumnSchema(BaseModel):
    """Schema definition for a single column.

    ``extra="allow"`` (E5c): domain-specific column metadata (e.g. ``pii: true``,
    ``source_system: "SAP"``) rides along and survives the read/write round-trip.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    type: str
    description: str
    nullable: bool = True
    examples: list[str] | None = None
    range: dict | None = None
    unit: str | None = None


class DataSource(BaseModel):
    """A registered data source in the catalog."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: str = Field(min_length=1)  # open string (E5c); see KNOWN_SOURCE_TYPES
    description: str
    connection: dict
    schema_info: dict = Field(default_factory=lambda: {"columns": []})
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_jst)
    updated_at: datetime = Field(default_factory=now_jst)


class DomainKnowledgeEntry(BaseModel):
    """A single domain knowledge entry for a data source."""

    key: str
    title: str
    content: str
    category: str = Field(
        min_length=1
    )  # open string (E5c); see KNOWN_KNOWLEDGE_CATEGORIES
    importance: KnowledgeImportance = KnowledgeImportance.medium
    created_at: datetime = Field(default_factory=now_jst)
    source: str | None = None
    affects_columns: list[str] = Field(default_factory=list)


class DomainKnowledge(BaseModel):
    """Container for domain knowledge entries of a data source."""

    source_id: str
    entries: list[DomainKnowledgeEntry] = Field(default_factory=list)
