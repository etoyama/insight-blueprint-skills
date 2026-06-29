"""Tests for core/reviews.py (SPEC-3 Tasks 2.1 + 2.2)."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from insight_blueprint.core.designs import DesignService
from insight_blueprint.core.reviews import ALLOWED_TARGET_SECTIONS, ReviewService
from insight_blueprint.models.catalog import (
    DomainKnowledgeEntry,
    KnowledgeCategory,
)
from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.models.review import ReviewBatch
from insight_blueprint.storage.yaml_store import read_yaml, write_yaml


class TestTransitionStatus:
    """Unit-03: transition_status valid/invalid transitions."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("in_review", "revision_requested"),
            ("in_review", "analyzing"),
            ("in_review", "supported"),
            ("in_review", "rejected"),
            ("in_review", "inconclusive"),
            ("revision_requested", "in_review"),
            ("analyzing", "in_review"),
        ],
    )
    def test_valid_transitions(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Valid transitions succeed and update the design status."""
        design = design_service.create_design(
            title="Trans", hypothesis_statement="s", hypothesis_background="b"
        )
        design_service.update_design(design.id, status=DesignStatus(from_status))
        result = review_service.transition_status(design.id, to_status)
        assert result is not None
        assert result.status == DesignStatus(to_status)

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("supported", "in_review"),
            ("rejected", "in_review"),
            ("inconclusive", "in_review"),
            ("analyzing", "supported"),
        ],
    )
    def test_invalid_transitions(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Invalid transitions raise ValueError."""
        design = design_service.create_design(
            title="Trans", hypothesis_statement="s", hypothesis_background="b"
        )
        design_service.update_design(design.id, status=DesignStatus(from_status))
        with pytest.raises(ValueError, match="Cannot transition"):
            review_service.transition_status(design.id, to_status)

    def test_invalid_transition_error_message(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """Error message includes current status and valid targets."""
        design = design_service.create_design(
            title="Trans", hypothesis_statement="s", hypothesis_background="b"
        )
        design_service.update_design(design.id, status=DesignStatus.supported)
        with pytest.raises(ValueError, match="Valid targets: none"):
            review_service.transition_status(design.id, "in_review")

    def test_transition_missing_design_returns_none(
        self,
        review_service: ReviewService,
    ) -> None:
        """Nonexistent design returns None."""
        result = review_service.transition_status("NONEXISTENT-H99", "in_review")
        assert result is None


class TestSaveReviewComment:
    def test_save_review_comment_sets_status_supported(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
    ) -> None:
        """R2-AC4: save comment with status supported transitions design."""
        comment = review_service.save_review_comment(
            pending_design.id, "Good analysis", "supported"
        )
        assert comment is not None
        assert comment.status_after == DesignStatus.supported
        assert comment.design_id == pending_design.id
        assert comment.id.startswith("RC-")
        reloaded = design_service.get_design(pending_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.supported

    def test_save_review_comment_sets_status_revision_requested(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
    ) -> None:
        """R2-AC5: save comment with status revision_requested (request changes)."""
        comment = review_service.save_review_comment(
            pending_design.id, "Needs more data", "revision_requested"
        )
        assert comment is not None
        assert comment.status_after == DesignStatus.revision_requested
        reloaded = design_service.get_design(pending_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.revision_requested

    def test_save_review_comment_sets_status_rejected(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
    ) -> None:
        """Extra: rejected status works."""
        comment = review_service.save_review_comment(
            pending_design.id, "Hypothesis disproved", "rejected"
        )
        assert comment is not None
        assert comment.status_after == DesignStatus.rejected

    def test_save_review_comment_sets_status_inconclusive(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
    ) -> None:
        """Extra: inconclusive status works."""
        comment = review_service.save_review_comment(
            pending_design.id, "Not enough evidence", "inconclusive"
        )
        assert comment is not None
        assert comment.status_after == DesignStatus.inconclusive

    def test_save_review_comment_on_revision_requested_succeeds(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """#82: commenting on a revision_requested design succeeds."""
        # First review: in_review -> revision_requested
        review_service.save_review_comment(
            active_design.id, "Needs more data", "revision_requested"
        )
        # Re-review directly from revision_requested (no manual transition)
        comment = review_service.save_review_comment(
            active_design.id, "Looks good now", "supported"
        )
        assert comment is not None
        assert comment.status_after == DesignStatus.supported
        reloaded = design_service.get_design(active_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.supported

    def test_save_review_comment_on_terminal_raises_value_error(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """R2-AC6: commenting on a terminal design raises ValueError."""
        design = design_service.create_design(
            title="Terminal",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.supported)
        with pytest.raises(ValueError, match="reviewable"):
            review_service.save_review_comment(design.id, "comment", "supported")

    def test_save_review_comment_on_analyzing_raises_value_error(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """#82 review: analyzing state is not reviewable."""
        design = design_service.create_design(
            title="Analyzing",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.analyzing)
        with pytest.raises(ValueError, match="reviewable"):
            review_service.save_review_comment(design.id, "comment", "supported")

    def test_save_review_comment_invalid_status_value(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """R2-AC7: invalid status value is rejected."""
        with pytest.raises(ValueError, match="Invalid post-review status"):
            review_service.save_review_comment(
                pending_design.id, "comment", "nonexistent_status"
            )

    def test_save_review_comment_preserves_existing_batches(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        pending_design: AnalysisDesign,
    ) -> None:
        """Fix #94: save_review_comment must not drop existing batches key."""
        # First: add a batch review
        review_service.save_review_batch(
            pending_design.id,
            "revision_requested",
            [
                {
                    "target_section": "hypothesis_statement",
                    "target_content": "Test",
                    "comment": "Batch comment",
                }
            ],
        )
        # Re-open for next review cycle
        design_service.update_design(pending_design.id, status=DesignStatus.in_review)

        # Second: add a single comment — this must NOT drop batches
        review_service.save_review_comment(
            pending_design.id, "Single comment", "supported"
        )

        # Verify both keys survive in the reviews YAML
        reviews_path = review_service._designs_dir / f"{pending_design.id}_reviews.yaml"
        data = read_yaml(reviews_path)
        assert "batches" in data, "batches key was dropped by save_review_comment"
        assert len(data["batches"]) == 1
        assert "comments" in data
        assert len(data["comments"]) == 1

    def test_save_review_comment_missing_returns_none(
        self,
        review_service: ReviewService,
    ) -> None:
        """Extra: commenting on nonexistent design returns None."""
        result = review_service.save_review_comment(
            "NONEXISTENT-H99", "comment", "supported"
        )
        assert result is None


class TestListComments:
    def test_list_comments_returns_both_in_order(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R2-AC8: two comments listed in chronological order."""
        # First review cycle: in_review -> revision_requested
        review_service.save_review_comment(
            active_design.id, "First comment", "revision_requested"
        )
        # Second review cycle: transition back to in_review, then to supported
        design_service.update_design(active_design.id, status=DesignStatus.in_review)
        review_service.save_review_comment(
            active_design.id, "Second comment", "supported"
        )

        comments = review_service.list_comments(active_design.id)
        assert len(comments) == 2
        assert comments[0].comment == "First comment"
        assert comments[1].comment == "Second comment"

    def test_list_comments_nonexistent_returns_empty(
        self,
        review_service: ReviewService,
    ) -> None:
        """R2-AC9: nonexistent design returns empty list."""
        comments = review_service.list_comments("NONEXISTENT-H99")
        assert comments == []

    def test_list_comments_no_reviews_file_returns_empty(
        self,
        review_service: ReviewService,
        active_design: AnalysisDesign,
    ) -> None:
        """Extra: design with no reviews file returns empty list."""
        comments = review_service.list_comments(active_design.id)
        assert comments == []


class TestExtractDomainKnowledge:
    def test_extract_caution_from_comment(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC1: caution prefix extracts as caution category."""
        review_service.save_review_comment(
            active_design.id,
            "caution: watch for nulls in column X",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].category == "caution"
        assert "nulls" in entries[0].content

    def test_extract_definition_from_comment(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC2: definition prefix extracts as definition category."""
        review_service.save_review_comment(
            active_design.id,
            "definition: MAU = Monthly Active Users",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].category == "definition"
        assert "MAU" in entries[0].content

    def test_extract_returns_preview_not_persisted(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """R3-AC3: extract returns preview, NOT persisted to YAML."""
        review_service.save_review_comment(
            active_design.id,
            "caution: check data quality",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        # Verify the extracted preview entry is NOT among persisted entries.
        # (Note: a finding entry IS auto-persisted via terminal transition,
        #  but the caution preview from extract_domain_knowledge is not.)
        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        persisted_entries = data.get("entries", []) if data else []
        persisted_keys = {e["key"] for e in persisted_entries}
        assert entries[0].key not in persisted_keys

    def test_extract_no_comments_returns_empty(
        self,
        review_service: ReviewService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC6: design with no comments returns empty list."""
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert entries == []

    def test_extract_no_prefix_defaults_to_context(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC7: lines without prefix default to context category."""
        review_service.save_review_comment(
            active_design.id,
            "This analysis targets Q3 planning",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].category == "context"

    def test_extract_table_annotation_sets_scope(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC8: table: annotation sets affects_columns."""
        review_service.save_review_comment(
            active_design.id,
            "table: population_stats\ncaution: data changed in 2015",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].affects_columns == ["population_stats"]

    def test_extract_design_source_ids_default_scope(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC9: design.source_ids used as default scope."""
        design_service.update_design(active_design.id, source_ids=["src-A", "src-B"])
        review_service.save_review_comment(
            active_design.id,
            "caution: handle missing values",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].affects_columns == ["src-A", "src-B"]

    def test_extract_no_scope_defaults_to_empty(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """R3-AC10: no annotation + no source_ids = unscoped."""
        review_service.save_review_comment(
            active_design.id,
            "caution: general data warning",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 1
        assert entries[0].affects_columns == []


class TestSaveExtractedKnowledge:
    def test_save_extracted_persists_to_yaml(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """R3-AC4: save persists entries to extracted_knowledge.yaml."""
        review_service.save_review_comment(
            active_design.id,
            "caution: check nulls",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        saved = review_service.save_extracted_knowledge(active_design.id, entries)
        assert len(saved) == 1

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        # 2 entries: 1 auto-extracted finding + 1 manually saved caution
        assert len(data["entries"]) == 2
        assert data["source_id"] == "review"

    def test_save_extracted_duplicate_keys_skipped(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """R3-AC5: duplicate keys are skipped on re-save."""
        review_service.save_review_comment(
            active_design.id,
            "caution: check nulls",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        review_service.save_extracted_knowledge(active_design.id, entries)
        # Save again with same entries
        saved = review_service.save_extracted_knowledge(active_design.id, entries)
        assert len(saved) == 0  # All duplicates skipped

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        # 2 entries: 1 auto-extracted finding + 1 manually saved caution
        assert len(data["entries"]) == 2

    def test_save_extracted_updates_comment_extracted_knowledge(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """Extra: save updates ReviewComment.extracted_knowledge with saved keys."""
        review_service.save_review_comment(
            active_design.id,
            "caution: check nulls",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        review_service.save_extracted_knowledge(active_design.id, entries)

        comments = review_service.list_comments(active_design.id)
        assert len(comments) == 1
        assert len(comments[0].extracted_knowledge) > 0
        assert comments[0].extracted_knowledge[0] == entries[0].key

    def test_save_extracted_assigns_keys_to_correct_comment(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """Regression: keys must only be added to originating comment, not all."""
        # Comment 1: request changes (returns to revision_requested)
        review_service.save_review_comment(
            active_design.id,
            "caution: null check needed",
            "revision_requested",
        )
        # Reset to in_review for second comment
        design_service.update_design(active_design.id, status=DesignStatus.in_review)
        # Comment 2: supported
        review_service.save_review_comment(
            active_design.id,
            "definition: MAU means monthly active users",
            "supported",
        )

        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) == 2

        review_service.save_extracted_knowledge(active_design.id, entries)

        comments = review_service.list_comments(active_design.id)
        assert len(comments) == 2

        # Comment 1 should only have the key from its own entry
        assert len(comments[0].extracted_knowledge) == 1
        assert comments[0].extracted_knowledge[0] == entries[0].key

        # Comment 2 should only have the key from its own entry
        assert len(comments[1].extracted_knowledge) == 1
        assert comments[1].extracted_knowledge[0] == entries[1].key


_BAD_IDS = [
    "../etc/passwd",
    "foo/bar",
    "id with spaces",
    "",
    "valid-id\n",
    "back\\slash",
]


class TestIdValidation:
    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_transition_status_invalid_id_raises_error(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            review_service.transition_status(bad_id, "in_review")

    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_save_review_comment_invalid_id_raises_error(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            review_service.save_review_comment(bad_id, "comment", "supported")

    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_list_comments_invalid_id_raises_error(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            review_service.list_comments(bad_id)

    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_extract_domain_knowledge_invalid_id_raises_error(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            review_service.extract_domain_knowledge(bad_id)

    @pytest.mark.parametrize("bad_id", _BAD_IDS)
    def test_save_extracted_knowledge_invalid_id_raises_error(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            review_service.save_extracted_knowledge(bad_id, [])


class TestImmutability:
    def test_save_extracted_knowledge_does_not_mutate_existing_data(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """Verify save_extracted_knowledge does not mutate existing entries list."""
        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        # Write initial data
        initial_entry = {
            "key": "existing-key",
            "title": "Existing",
            "content": "Existing knowledge entry",
            "category": "context",
            "source": "manual",
            "affects_columns": [],
        }
        initial_data = {"source_id": "review", "entries": [initial_entry]}
        write_yaml(ek_path, initial_data)

        # Read back to get reference to the dict
        data_before = read_yaml(ek_path)
        entries_before = list(data_before["entries"])  # shallow copy for comparison

        # Save new entries
        new_entry = DomainKnowledgeEntry(
            key="new-key",
            title="New",
            content="New knowledge entry",
            category="caution",
            source=f"review:RC-abc@{active_design.id}",
            affects_columns=[],
        )
        review_service.save_extracted_knowledge(active_design.id, [new_entry])

        # Verify data_before dict was not mutated
        assert len(entries_before) == 1
        assert entries_before[0]["key"] == "existing-key"

        # Verify file now has both entries
        data_after = read_yaml(ek_path)
        assert len(data_after["entries"]) == 2


# ---------------------------------------------------------------------------
# Inline Review Comments — save_review_batch tests (P2)
# ---------------------------------------------------------------------------

_BAD_DESIGN_IDS = [
    "../etc/passwd",
    "foo/bar",
    "id with spaces",
    "",
    "valid-id\n",
    "back\\slash",
]


class TestSaveReviewBatch:
    """Tests for ReviewService.save_review_batch (FR-8, FR-12, FR-14, NFR-8)."""

    def test_save_batch_with_valid_data(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        review_batch_data: dict,
    ) -> None:
        """FR-8, FR-12: Valid batch is saved and returns ReviewBatch."""
        result = review_service.save_review_batch(
            pending_design.id,
            review_batch_data["status_after"],
            review_batch_data["comments"],
            review_batch_data["reviewer"],
        )
        assert result is not None
        assert isinstance(result, ReviewBatch)
        assert result.id.startswith("RB-")
        assert result.design_id == pending_design.id
        assert len(result.comments) == 2

    def test_save_batch_transitions_design_status(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
    ) -> None:
        """FR-8: Design status transitions to status_after."""
        review_service.save_review_batch(
            pending_design.id,
            "supported",
            [{"comment": "Good"}],
        )
        reloaded = design_service.get_design(pending_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.supported

    def test_save_batch_persists_to_yaml(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """FR-14: Batch is persisted to YAML file."""
        review_service.save_review_batch(
            pending_design.id,
            "supported",
            [{"comment": "Persisted"}],
        )
        reviews_path = (
            tmp_path / ".insight" / "designs" / f"{pending_design.id}_reviews.yaml"
        )
        data = read_yaml(reviews_path)
        assert "batches" in data
        assert len(data["batches"]) == 1

    def test_save_batch_preserves_target_section(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """FR-4: target_section is preserved in saved batch."""
        result = review_service.save_review_batch(
            pending_design.id,
            "supported",
            [
                {
                    "comment": "Check this",
                    "target_section": "hypothesis_statement",
                    "target_content": "Test",
                }
            ],
        )
        assert result is not None
        assert result.comments[0].target_section == "hypothesis_statement"

    def test_save_batch_preserves_target_content_text(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """FR-11: Text target_content is preserved."""
        result = review_service.save_review_batch(
            pending_design.id,
            "supported",
            [
                {
                    "comment": "Note",
                    "target_section": "hypothesis_statement",
                    "target_content": "CVR will improve by 10%",
                }
            ],
        )
        assert result is not None
        assert result.comments[0].target_content == "CVR will improve by 10%"

    def test_save_batch_preserves_target_content_json(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """FR-11: JSON target_content (dict) is preserved."""
        content = {"kpi_name": "CVR", "current_value": "2.5%"}
        result = review_service.save_review_batch(
            pending_design.id,
            "supported",
            [
                {
                    "comment": "Metrics",
                    "target_section": "metrics",
                    "target_content": content,
                }
            ],
        )
        assert result is not None
        assert result.comments[0].target_content == content

    def test_save_batch_on_revision_requested_succeeds(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """#82: batch review on a revision_requested design succeeds."""
        # First batch: in_review -> revision_requested
        review_service.save_review_batch(
            active_design.id,
            "revision_requested",
            [{"comment": "Needs revision"}],
        )
        # Re-review directly from revision_requested (no manual transition)
        result = review_service.save_review_batch(
            active_design.id,
            "supported",
            [{"comment": "Approved after revision"}],
        )
        assert result is not None
        assert result.status_after == DesignStatus.supported
        reloaded = design_service.get_design(active_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.supported

    def test_save_batch_rejects_terminal_design(
        self,
        review_service: ReviewService,
        non_pending_design: AnalysisDesign,
    ) -> None:
        """AC: Terminal design raises ValueError."""
        with pytest.raises(ValueError, match="reviewable"):
            review_service.save_review_batch(
                non_pending_design.id,
                "supported",
                [{"comment": "Should fail"}],
            )

    def test_save_batch_rejects_analyzing_design(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """#82 review: analyzing state is not reviewable for batches."""
        design = design_service.create_design(
            title="Analyzing",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.analyzing)
        with pytest.raises(ValueError, match="reviewable"):
            review_service.save_review_batch(
                design.id,
                "supported",
                [{"comment": "Should fail"}],
            )

    def test_save_batch_rejects_invalid_status(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """Invalid status_after is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            review_service.save_review_batch(
                pending_design.id,
                "nonexistent_status",
                [{"comment": "Bad status"}],
            )

    def test_save_batch_rejects_empty_comments(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """Empty comments list is rejected."""
        with pytest.raises((ValueError, Exception)):
            review_service.save_review_batch(
                pending_design.id,
                "supported",
                [],
            )

    @pytest.mark.parametrize("bad_id", _BAD_DESIGN_IDS)
    def test_save_batch_rejects_invalid_design_id(
        self,
        review_service: ReviewService,
        bad_id: str,
    ) -> None:
        """Path traversal and invalid IDs are rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            review_service.save_review_batch(
                bad_id,
                "supported",
                [{"comment": "Bad ID"}],
            )

    def test_save_batch_missing_design(
        self,
        review_service: ReviewService,
    ) -> None:
        """Nonexistent design_id returns None."""
        result = review_service.save_review_batch(
            "NONEXIST-H99",
            "supported",
            [{"comment": "Ghost"}],
        )
        assert result is None

    def test_save_batch_yaml_write_failure_no_status_change(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        design_service: DesignService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NFR-8: YAML write failure prevents status transition."""
        monkeypatch.setattr(
            "insight_blueprint.core.reviews.write_yaml",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("Disk full")),
        )
        with pytest.raises(OSError):
            review_service.save_review_batch(
                pending_design.id,
                "supported",
                [{"comment": "Fail write"}],
            )
        reloaded = design_service.get_design(pending_design.id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.in_review

    def test_save_batch_status_update_failure_keeps_batch(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        status_update_failure: None,
        tmp_path: Path,
    ) -> None:
        """NFR-8: YAML succeeds but status update fails — batch is preserved."""
        with pytest.raises(RuntimeError, match="Simulated"):
            review_service.save_review_batch(
                pending_design.id,
                "supported",
                [{"comment": "Batch saved, status not"}],
            )
        # Batch should be persisted even though status update failed
        reviews_path = (
            tmp_path / ".insight" / "designs" / f"{pending_design.id}_reviews.yaml"
        )
        data = read_yaml(reviews_path)
        assert "batches" in data
        assert len(data["batches"]) == 1

    @pytest.mark.parametrize(
        "status",
        [
            "supported",
            "rejected",
            "inconclusive",
            "revision_requested",
            "analyzing",
        ],
    )
    def test_save_batch_all_status_transitions(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        status: str,
    ) -> None:
        """FR-7: All 5 post-review status transitions work."""
        result = review_service.save_review_batch(
            active_design.id,
            status,
            [{"comment": f"Setting to {status}"}],
        )
        assert result is not None
        assert result.status_after.value == status
        reloaded = design_service.get_design(active_design.id)
        assert reloaded is not None
        assert reloaded.status.value == status
        # Reset for next iteration
        design_service.update_design(active_design.id, status=DesignStatus.in_review)

    def test_save_batch_appends_to_existing_batches(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """Appends to existing batches in the YAML file."""
        # First batch: in_review -> revision_requested
        review_service.save_review_batch(
            active_design.id,
            "revision_requested",
            [{"comment": "First batch"}],
        )
        # Reset to in_review for second batch
        design_service.update_design(active_design.id, status=DesignStatus.in_review)
        # Second batch: in_review -> supported
        result = review_service.save_review_batch(
            active_design.id,
            "supported",
            [{"comment": "Second batch"}],
        )
        assert result is not None
        batches = review_service.list_review_batches(active_design.id)
        assert len(batches) == 2

    def test_save_batch_preserves_existing_comments(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """Fix #94 symmetric: save_review_batch must not drop existing comments key."""
        # First: add a single comment -> revision_requested
        review_service.save_review_comment(
            active_design.id, "Single comment", "revision_requested"
        )
        # Re-open for batch review
        design_service.update_design(active_design.id, status=DesignStatus.in_review)

        # Second: add a batch review — this must NOT drop comments
        review_service.save_review_batch(
            active_design.id,
            "supported",
            [
                {
                    "target_section": "hypothesis_statement",
                    "target_content": "Test",
                    "comment": "Batch comment",
                }
            ],
        )

        # Verify both keys survive
        reviews_path = review_service._designs_dir / f"{active_design.id}_reviews.yaml"
        data = read_yaml(reviews_path)
        assert "comments" in data, "comments key was dropped by save_review_batch"
        assert len(data["comments"]) == 1
        assert "batches" in data
        assert len(data["batches"]) == 1

    def test_save_batch_creates_new_file(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """Creates reviews.yaml if it doesn't exist."""
        reviews_path = (
            tmp_path / ".insight" / "designs" / f"{pending_design.id}_reviews.yaml"
        )
        assert not reviews_path.exists()
        review_service.save_review_batch(
            pending_design.id,
            "supported",
            [{"comment": "Creates file"}],
        )
        assert reviews_path.exists()


class TestSaveReviewBatchTargetSectionValidation:
    """Tests for target_section validation against ALLOWED_TARGET_SECTIONS (NFR-7)."""

    @pytest.mark.parametrize(
        "section",
        [
            "hypothesis_statement",
            "hypothesis_background",
            "metrics",
            "explanatory",
            "chart",
            "next_action",
            "referenced_knowledge",
            "methodology",
            "analysis_intent",
        ],
    )
    def test_valid_target_sections_accepted(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        section: str,
    ) -> None:
        """NFR-7: All 9 valid sections are accepted."""
        result = review_service.save_review_batch(
            pending_design.id,
            "supported",
            [
                {
                    "comment": "Valid section",
                    "target_section": section,
                    "target_content": "x",
                }
            ],
        )
        assert result is not None

    def test_invalid_target_section_rejected(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """NFR-7: Invalid section name is rejected."""
        with pytest.raises(ValueError, match="target_section"):
            review_service.save_review_batch(
                pending_design.id,
                "supported",
                [
                    {
                        "comment": "Bad section",
                        "target_section": "nonexistent_section",
                        "target_content": "x",
                    }
                ],
            )

    def test_null_target_section_accepted(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """NFR-7: None target_section is allowed (no anchor)."""
        result = review_service.save_review_batch(
            pending_design.id,
            "supported",
            [{"comment": "No anchor"}],
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Inline Review Comments — list_review_batches tests (P3)
# ---------------------------------------------------------------------------


class TestListReviewBatches:
    """Tests for ReviewService.list_review_batches (FR-13)."""

    def test_list_batches_returns_all(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """FR-13: Returns all batches for a design."""
        # Create two batches
        review_service.save_review_batch(
            active_design.id, "revision_requested", [{"comment": "First"}]
        )
        design_service.update_design(active_design.id, status=DesignStatus.in_review)
        review_service.save_review_batch(
            active_design.id, "supported", [{"comment": "Second"}]
        )
        batches = review_service.list_review_batches(active_design.id)
        assert len(batches) == 2

    def test_list_batches_descending_order(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """FR-13: Batches are sorted by created_at descending."""
        review_service.save_review_batch(
            active_design.id, "revision_requested", [{"comment": "Earlier"}]
        )
        design_service.update_design(active_design.id, status=DesignStatus.in_review)
        review_service.save_review_batch(
            active_design.id, "supported", [{"comment": "Later"}]
        )
        batches = review_service.list_review_batches(active_design.id)
        assert len(batches) == 2
        assert batches[0].created_at >= batches[1].created_at

    def test_list_batches_empty(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """No batches returns empty list."""
        batches = review_service.list_review_batches(pending_design.id)
        assert batches == []

    def test_list_batches_nonexistent_design(
        self,
        review_service: ReviewService,
    ) -> None:
        """Nonexistent design_id returns empty list."""
        batches = review_service.list_review_batches("NONEXIST-H99")
        assert batches == []

    def test_list_batches_no_file(
        self,
        review_service: ReviewService,
        active_design: AnalysisDesign,
    ) -> None:
        """No reviews file returns empty list."""
        batches = review_service.list_review_batches(active_design.id)
        assert batches == []

    def test_list_batches_no_batches_key(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """YAML without 'batches' key returns empty list + warning."""
        reviews_path = (
            tmp_path / ".insight" / "designs" / f"{pending_design.id}_reviews.yaml"
        )
        write_yaml(reviews_path, {"comments": [{"old": "format"}]})
        with caplog.at_level(logging.WARNING):
            batches = review_service.list_review_batches(pending_design.id)
        assert batches == []
        assert (
            any(
                "batches" in r.message.lower() or "warning" in r.message.lower()
                for r in caplog.records
            )
            or len(caplog.records) > 0
        )

    def test_list_batches_preserves_target_content(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """target_content is preserved through save + list round-trip."""
        content = {"kpi": "CVR", "value": 2.5}
        review_service.save_review_batch(
            pending_design.id,
            "supported",
            [
                {
                    "comment": "With content",
                    "target_section": "metrics",
                    "target_content": content,
                }
            ],
        )
        batches = review_service.list_review_batches(pending_design.id)
        assert len(batches) == 1
        assert batches[0].comments[0].target_content == content

    def test_list_batches_corrupted_yaml(
        self,
        review_service: ReviewService,
        corrupted_reviews_yaml: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Error#7: Corrupted YAML returns empty list + warning."""
        with caplog.at_level(logging.WARNING):
            batches = review_service.list_review_batches("DES-corrupt")
        assert batches == []
        assert len(caplog.records) > 0


# ---------------------------------------------------------------------------
# Task 2.1: Finding Auto-Extraction (_build_finding + _extract_finding_if_terminal)
# ---------------------------------------------------------------------------


class TestBuildFinding:
    """T-2.7, T-2.8, T-2.12: _build_finding field values and truncation."""

    def test_finding_field_values(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """T-2.7: finding field values match spec (key, title, content, source, etc)."""
        design = design_service.create_design(
            title="Churn Hypothesis",
            hypothesis_statement="Churn increases in Q4",
            hypothesis_background="bg",
        )
        design = design_service.update_design(design.id, source_ids=["orders"])

        finding = review_service._build_finding(design, DesignStatus.supported)

        assert finding.key == f"{design.id}-finding"
        assert finding.title == "[SUPPORTED] Churn Hypothesis"
        assert finding.content == "Churn increases in Q4"
        assert finding.category == KnowledgeCategory.finding
        assert finding.source == f"design:{design.id}"
        assert finding.affects_columns == ["orders"]

    @pytest.mark.parametrize(
        "title_len,expected_len",
        [
            (67, 79),  # "[SUPPORTED] " (12) + 67 = 79 -> no truncation
            (68, 80),  # "[SUPPORTED] " (12) + 68 = 80 -> no truncation
            (69, 80),  # "[SUPPORTED] " (12) + 69 = 81 -> truncated to 80
        ],
    )
    def test_finding_title_80char_truncation_boundary(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        title_len: int,
        expected_len: int,
    ) -> None:
        """T-2.8: title truncation boundary at 79/80/81 chars."""
        title = "A" * title_len
        design = design_service.create_design(
            title=title,
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        finding = review_service._build_finding(design, DesignStatus.supported)
        assert len(finding.title) == expected_len

    def test_finding_title_uses_target_status_not_current(
        self,
        review_service: ReviewService,
        design_service: DesignService,
    ) -> None:
        """T-2.12: finding title STATUS uses target_status argument."""
        design = design_service.create_design(
            title="Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        # Current status is in_review, but target is rejected
        finding = review_service._build_finding(design, DesignStatus.rejected)
        assert finding.title.startswith("[REJECTED]")
        assert "[IN_REVIEW]" not in finding.title


class TestExtractFindingIfTerminal:
    """T-2.9, T-2.10, T-2.11: persistence, dedup, fire-and-forget."""

    def test_finding_persisted_to_extracted_knowledge(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.9: finding is saved to extracted_knowledge.yaml."""
        design = design_service.create_design(
            title="Persist Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        review_service._extract_finding_if_terminal(design.id, DesignStatus.supported)

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        assert data is not None
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1
        assert finding_entries[0]["key"] == f"{design.id}-finding"

    def test_duplicate_finding_not_generated(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.10: duplicate finding key is not re-created."""
        design = design_service.create_design(
            title="Dup Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        # First extraction
        review_service._extract_finding_if_terminal(design.id, DesignStatus.supported)
        # Second extraction (same design)
        review_service._extract_finding_if_terminal(design.id, DesignStatus.supported)

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_extraction_failure_does_not_block_transition(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """T-2.11: I/O failure in extraction logs warning but does not raise."""
        design = design_service.create_design(
            title="Fail Test",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        # Mock write_yaml to fail
        with patch(
            "insight_blueprint.core.reviews.write_yaml",
            side_effect=OSError("Disk full"),
        ):
            with caplog.at_level(logging.WARNING):
                # Should NOT raise
                review_service._extract_finding_if_terminal(
                    design.id, DesignStatus.supported
                )

        # Should have logged a warning
        assert any("finding" in r.message.lower() for r in caplog.records)

    def test_non_terminal_status_does_nothing(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """Non-terminal status skips extraction entirely."""
        design = design_service.create_design(
            title="Non-terminal",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        review_service._extract_finding_if_terminal(
            design.id, DesignStatus.revision_requested
        )

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", []) if data else []
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Task 2.2: Hook All Transition Routes
# ---------------------------------------------------------------------------


class TestFindingExtractionHooks:
    """T-2.1 to T-2.6c: finding extraction via all 3 transition methods."""

    def test_supported_transition_generates_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.1: transition_status to supported generates finding."""
        design = design_service.create_design(
            title="Supported",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        review_service.transition_status(design.id, "supported")

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_rejected_transition_generates_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.2: transition_status to rejected generates finding."""
        design = design_service.create_design(
            title="Rejected",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        review_service.transition_status(design.id, "rejected")

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_inconclusive_transition_generates_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.3: transition_status to inconclusive generates finding."""
        design = design_service.create_design(
            title="Inconclusive",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        review_service.transition_status(design.id, "inconclusive")

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_save_review_comment_terminal_generates_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """T-2.4: save_review_comment with terminal status generates finding."""
        review_service.save_review_comment(active_design.id, "Good work", "supported")

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_save_review_batch_terminal_generates_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """T-2.5: save_review_batch with terminal status generates finding."""
        review_service.save_review_batch(
            active_design.id,
            "rejected",
            [{"comment": "Disproved"}],
        )

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", [])
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 1

    def test_non_terminal_transition_status_no_finding(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        tmp_path: Path,
    ) -> None:
        """T-2.6: non-terminal transition_status does NOT generate finding."""
        design = design_service.create_design(
            title="NonTerminal",
            hypothesis_statement="stmt",
            hypothesis_background="bg",
        )
        design_service.update_design(design.id, status=DesignStatus.in_review)

        review_service.transition_status(design.id, "revision_requested")

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", []) if data else []
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 0

    def test_non_terminal_save_review_comment_no_finding(
        self,
        review_service: ReviewService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """T-2.6b: non-terminal save_review_comment does NOT generate finding."""
        review_service.save_review_comment(
            active_design.id, "Needs revision", "revision_requested"
        )

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", []) if data else []
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 0

    def test_non_terminal_save_review_batch_no_finding(
        self,
        review_service: ReviewService,
        active_design: AnalysisDesign,
        tmp_path: Path,
    ) -> None:
        """T-2.6c: non-terminal save_review_batch does NOT generate finding."""
        review_service.save_review_batch(
            active_design.id,
            "analyzing",
            [{"comment": "Continue"}],
        )

        ek_path = tmp_path / ".insight" / "rules" / "extracted_knowledge.yaml"
        data = read_yaml(ek_path)
        entries = data.get("entries", []) if data else []
        finding_entries = [e for e in entries if e.get("category") == "finding"]
        assert len(finding_entries) == 0


# ---------------------------------------------------------------------------
# Task 3.1: ALLOWED_TARGET_SECTIONS + COMMENTABLE_SECTIONS
# ---------------------------------------------------------------------------


class TestReferencedKnowledgeSection:
    """T-5.1 to T-5.4: referenced_knowledge as a reviewable section."""

    def test_referenced_knowledge_in_allowed_sections(self) -> None:
        """T-5.1: referenced_knowledge is in ALLOWED_TARGET_SECTIONS."""
        assert "referenced_knowledge" in ALLOWED_TARGET_SECTIONS

    def test_save_review_batch_with_referenced_knowledge_section(
        self,
        review_service: ReviewService,
        pending_design: AnalysisDesign,
    ) -> None:
        """T-5.2: save_review_batch accepts referenced_knowledge section."""
        result = review_service.save_review_batch(
            pending_design.id,
            "revision_requested",
            [
                {
                    "comment": "Missing relevant findings",
                    "target_section": "referenced_knowledge",
                    "target_content": {"hypothesis_statement": ["K-001"]},
                }
            ],
        )
        assert result is not None
        assert result.comments[0].target_section == "referenced_knowledge"

    def test_referenced_knowledge_comment_extractable(
        self,
        review_service: ReviewService,
        design_service: DesignService,
        active_design: AnalysisDesign,
    ) -> None:
        """T-5.3: referenced_knowledge comment is extractable as knowledge."""
        review_service.save_review_comment(
            active_design.id,
            "caution: referenced knowledge is incomplete",
            "supported",
        )
        entries = review_service.extract_domain_knowledge(active_design.id)
        assert len(entries) >= 1
        assert any(e.category == KnowledgeCategory.caution for e in entries)
