"""Tests for review workflow models (SPEC-3 Tasks 1.1 + 1.2)."""

import re
from datetime import datetime

import pytest
from pydantic import ValidationError

from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.models.review import BatchComment, ReviewBatch, ReviewComment


class TestDesignStatusExtension:
    def test_design_status_in_review_value(self) -> None:
        """AC1: in_review enum value is stored correctly."""
        assert DesignStatus.in_review == "in_review"
        assert DesignStatus("in_review") == DesignStatus.in_review


class TestAnalysisDesignSourceIds:
    def test_analysis_design_source_ids_default_empty(self) -> None:
        """AC4: source_ids defaults to empty list when not provided."""
        design = AnalysisDesign(
            id="TEST-H01",
            title="Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        assert design.source_ids == []

    def test_analysis_design_source_ids_with_values(self) -> None:
        """Extra: source_ids preserves explicit values."""
        design = AnalysisDesign(
            id="TEST-H01",
            title="Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
            source_ids=["src-1", "src-2"],
        )
        assert design.source_ids == ["src-1", "src-2"]


class TestReviewComment:
    def test_review_comment_timestamps_default_to_jst(self) -> None:
        """AC2: created_at defaults to now_jst()."""
        comment = ReviewComment(
            id="RC-aabbccdd",
            design_id="TEST-H01",
            comment="Good analysis",
            status_after=DesignStatus.supported,
        )
        assert isinstance(comment.created_at, datetime)
        assert comment.created_at.tzinfo is not None
        assert str(comment.created_at.tzinfo) == "Asia/Tokyo"

    def test_review_comment_extracted_knowledge_default_empty(self) -> None:
        """AC5: extracted_knowledge defaults to empty list."""
        comment = ReviewComment(
            id="RC-aabbccdd",
            design_id="TEST-H01",
            comment="Good analysis",
            status_after=DesignStatus.supported,
        )
        assert comment.extracted_knowledge == []

    def test_review_comment_json_round_trip(self) -> None:
        """AC3: JSON serialize + deserialize produces equivalent model."""
        comment = ReviewComment(
            id="RC-aabbccdd",
            design_id="TEST-H01",
            comment="Needs more data",
            reviewer="senior_analyst",
            status_after=DesignStatus.revision_requested,
            extracted_knowledge=["TEST-H01-0"],
        )
        data = comment.model_dump(mode="json")
        restored = ReviewComment(**data)
        assert restored.id == comment.id
        assert restored.design_id == comment.design_id
        assert restored.comment == comment.comment
        assert restored.reviewer == comment.reviewer
        assert restored.status_after == comment.status_after
        assert restored.extracted_knowledge == comment.extracted_knowledge

    def test_review_comment_status_after_supported(self) -> None:
        """Extra: status_after accepts DesignStatus.supported."""
        comment = ReviewComment(
            id="RC-11223344",
            design_id="TEST-H01",
            comment="Well done",
            status_after=DesignStatus.supported,
        )
        assert comment.status_after == DesignStatus.supported


class TestBatchComment:
    """Unit tests for BatchComment model (FR-11)."""

    def test_valid_batch_comment(self) -> None:
        """FR-11: comment + target_section + target_content constructs successfully."""
        bc = BatchComment(
            comment="Hypothesis is vague",
            target_section="hypothesis_statement",
            target_content="The policy improves CVR",
        )
        assert bc.comment == "Hypothesis is vague"
        assert bc.target_section == "hypothesis_statement"
        assert bc.target_content == "The policy improves CVR"

    def test_target_section_optional(self) -> None:
        """FR-11: target_section is None by default."""
        bc = BatchComment(comment="General comment")
        assert bc.target_section is None

    def test_target_content_optional_when_no_section(self) -> None:
        """FR-11: target_section=None allows target_content=None."""
        bc = BatchComment(comment="No anchor")
        assert bc.target_section is None
        assert bc.target_content is None

    def test_target_section_requires_target_content(self) -> None:
        """FR-11: target_section set + target_content=None raises ValidationError."""
        with pytest.raises(ValidationError, match="target_content"):
            BatchComment(
                comment="Has section but no content",
                target_section="metrics",
            )

    def test_target_content_preserves_text(self) -> None:
        """FR-11: text-type target_content is preserved."""
        bc = BatchComment(
            comment="Check this",
            target_section="hypothesis_statement",
            target_content="CVR will improve by 10%",
        )
        assert bc.target_content == "CVR will improve by 10%"

    def test_target_content_preserves_json(self) -> None:
        """FR-11: json-type target_content (dict/list) is preserved."""
        content = {"kpi_name": "CVR", "current_value": "2.5%", "values": [1, 2, 3]}
        bc = BatchComment(
            comment="Check metrics",
            target_section="metrics",
            target_content=content,
        )
        assert bc.target_content == content

    @pytest.mark.parametrize("bad_value", [datetime(2026, 1, 1), object()])
    def test_target_content_rejects_non_json_values(self, bad_value: object) -> None:
        """JsonValue: non-JSON-compatible values (datetime, arbitrary objects) are rejected."""
        with pytest.raises(ValidationError):
            BatchComment(
                comment="Bad content",
                target_section="metrics",
                target_content=bad_value,
            )

    def test_empty_comment_rejected(self) -> None:
        """Empty string comment is rejected."""
        with pytest.raises(ValidationError):
            BatchComment(comment="")

    def test_whitespace_only_comment_rejected(self) -> None:
        """Whitespace-only comment is rejected."""
        with pytest.raises(ValidationError):
            BatchComment(comment="   ")

    def test_comment_max_length_boundary(self) -> None:
        """2000 characters is allowed."""
        bc = BatchComment(comment="a" * 2000)
        assert len(bc.comment) == 2000

    def test_comment_over_max_length_rejected(self) -> None:
        """2001 characters is rejected."""
        with pytest.raises(ValidationError):
            BatchComment(comment="a" * 2001)

    def test_empty_string_target_section_rejected(self) -> None:
        """target_section="" is rejected (only None allowed for no section)."""
        with pytest.raises(ValidationError):
            BatchComment(
                comment="Has empty section",
                target_section="",
                target_content="something",
            )

    def test_extra_field_rejected(self) -> None:
        """extra='forbid': unknown fields raise ValidationError."""
        with pytest.raises(ValidationError):
            BatchComment(
                comment="Extra field test",
                unknown_field="should fail",
            )


class TestReviewBatch:
    """Unit tests for ReviewBatch model (FR-10)."""

    def test_valid_review_batch(self) -> None:
        """FR-10: all fields construct successfully."""
        batch = ReviewBatch(
            id="RB-a1b2c3d4",
            design_id="DES-001",
            status_after=DesignStatus.supported,
            reviewer="analyst",
            comments=[
                BatchComment(
                    comment="Good hypothesis",
                    target_section="hypothesis_statement",
                    target_content="Test hypothesis",
                )
            ],
        )
        assert batch.id == "RB-a1b2c3d4"
        assert batch.design_id == "DES-001"
        assert batch.status_after == DesignStatus.supported
        assert batch.reviewer == "analyst"
        assert len(batch.comments) == 1

    def test_id_format(self) -> None:
        """FR-10: id is 'RB-' prefix + 8 hex chars."""
        batch = ReviewBatch(
            id="RB-a1b2c3d4",
            design_id="DES-001",
            status_after=DesignStatus.supported,
            comments=[BatchComment(comment="Test")],
        )
        assert re.match(r"^RB-[0-9a-f]{8}$", batch.id)

    def test_status_after_must_be_valid(self) -> None:
        """FR-10: invalid status_after is rejected."""
        with pytest.raises(ValidationError):
            ReviewBatch(
                id="RB-a1b2c3d4",
                design_id="DES-001",
                status_after="invalid_status",
                comments=[BatchComment(comment="Test")],
            )

    def test_comments_must_not_be_empty(self) -> None:
        """FR-10: empty comments list is rejected."""
        with pytest.raises(ValidationError):
            ReviewBatch(
                id="RB-a1b2c3d4",
                design_id="DES-001",
                status_after=DesignStatus.supported,
                comments=[],
            )

    def test_created_at_defaults_to_jst(self) -> None:
        """FR-10: default timestamp is JST."""
        batch = ReviewBatch(
            id="RB-a1b2c3d4",
            design_id="DES-001",
            status_after=DesignStatus.supported,
            comments=[BatchComment(comment="Test")],
        )
        assert isinstance(batch.created_at, datetime)
        assert batch.created_at.tzinfo is not None
        assert str(batch.created_at.tzinfo) == "Asia/Tokyo"

    def test_reviewer_defaults_to_analyst(self) -> None:
        """FR-10: reviewer defaults to 'analyst'."""
        batch = ReviewBatch(
            id="RB-a1b2c3d4",
            design_id="DES-001",
            status_after=DesignStatus.supported,
            comments=[BatchComment(comment="Test")],
        )
        assert batch.reviewer == "analyst"

    def test_json_round_trip(self) -> None:
        """Serialize + deserialize produces equivalent model (with target_content)."""
        batch = ReviewBatch(
            id="RB-a1b2c3d4",
            design_id="DES-001",
            status_after=DesignStatus.revision_requested,
            reviewer="senior",
            comments=[
                BatchComment(
                    comment="Check metrics",
                    target_section="metrics",
                    target_content={"kpi": "CVR", "value": 2.5},
                ),
                BatchComment(comment="General note"),
            ],
        )
        data = batch.model_dump(mode="json")
        restored = ReviewBatch(**data)
        assert restored.id == batch.id
        assert restored.design_id == batch.design_id
        assert restored.status_after == batch.status_after
        assert restored.reviewer == batch.reviewer
        assert len(restored.comments) == 2
        assert restored.comments[0].target_content == {"kpi": "CVR", "value": 2.5}
        assert restored.comments[1].target_section is None

    def test_extra_field_rejected(self) -> None:
        """extra='forbid': unknown fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewBatch(
                id="RB-a1b2c3d4",
                design_id="DES-001",
                status_after=DesignStatus.supported,
                comments=[BatchComment(comment="Test")],
                unknown_field="should fail",
            )


class TestReviewBatchAfterAnalysisStarted:
    """Epic 33 US-4 AC 1: a batch holds whether it came after the analysis started."""

    def _batch(self, **over: object) -> ReviewBatch:
        data: dict = {
            "id": "RB-a1b2c3d4",
            "design_id": "DES-001",
            "status_after": "revision_requested",
            "comments": [{"comment": "The verdict misreads the comparison"}],
            "created_at": "2026-11-25T10:00:00+09:00",
        }
        data.update(over)
        return ReviewBatch(**data)

    def test_a_batch_saved_before_the_field_existed_reads_without_it(self) -> None:
        assert self._batch().after_analysis_started is None

    @pytest.mark.parametrize("after", [True, False])
    def test_a_batch_keeps_the_value_it_was_written_with(self, after: bool) -> None:
        restored = ReviewBatch(
            **self._batch(after_analysis_started=after).model_dump(mode="json")
        )
        assert restored.after_analysis_started is after
