"""Pydantic data models for review comments (SPEC-3)."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator
from typing_extensions import TypeAliasType

from insight_blueprint.models.common import now_jst
from insight_blueprint.models.design import DesignStatus

JsonValue = TypeAliasType(
    "JsonValue",
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"],
)


class ReviewComment(BaseModel):
    """A structured review comment on an analysis design."""

    id: str
    design_id: str
    comment: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(default="analyst", min_length=1, max_length=100)
    status_after: DesignStatus
    created_at: datetime = Field(default_factory=now_jst)
    extracted_knowledge: list[str] = Field(default_factory=list)


class BatchComment(BaseModel, extra="forbid"):
    """A single comment within a ReviewBatch."""

    comment: str = Field(min_length=1, max_length=2000)
    target_section: str | None = None
    target_content: JsonValue = None

    @model_validator(mode="after")
    def target_content_requires_section(self) -> Self:
        """Ensure target_content is provided when target_section is set."""
        if self.target_section is not None and self.target_content is None:
            raise ValueError("target_content is required when target_section is set")
        return self

    @model_validator(mode="after")
    def validate_comment_not_whitespace(self) -> Self:
        """Reject whitespace-only comments."""
        if not self.comment.strip():
            raise ValueError("comment must not be empty or whitespace-only")
        return self

    @model_validator(mode="after")
    def validate_target_section_not_empty(self) -> Self:
        """Reject empty string target_section (only None is valid for no section)."""
        if self.target_section is not None and self.target_section == "":
            raise ValueError("target_section must be None or a non-empty string")
        return self


class ReviewBatch(BaseModel, extra="forbid"):
    """A batch of review comments with a single status transition."""

    id: str
    design_id: str
    status_after: DesignStatus
    reviewer: str = Field(default="analyst", min_length=1, max_length=100)
    comments: list[BatchComment] = Field(min_length=1)
    created_at: datetime = Field(default_factory=now_jst)
    # Held as written, not derived from the analysis mark (ADR-0054 4).
    # None: a batch saved before Epic 33, which does not tell.
    after_analysis_started: bool | None = None
