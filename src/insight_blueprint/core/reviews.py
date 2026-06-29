"""Review workflow business logic (SPEC-3)."""

import logging
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from insight_blueprint.core.designs import DesignService
from insight_blueprint.core.validation import validate_id as _validate_id
from insight_blueprint.models.catalog import DomainKnowledgeEntry, KnowledgeCategory
from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from insight_blueprint.models.review import BatchComment, ReviewBatch, ReviewComment
from insight_blueprint.storage.yaml_store import read_yaml, write_yaml
from insight_blueprint.validate import VALID_TRANSITIONS
from insight_blueprint.validate import validate_transition as _validate_transition

logger = logging.getLogger(__name__)

# Regex patterns for keyword-based extraction (case-insensitive)
_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], KnowledgeCategory]] = [
    (re.compile(r"^(caution|注意)\s*:\s*", re.IGNORECASE), KnowledgeCategory.caution),
    (
        re.compile(r"^(definition|定義)\s*:\s*", re.IGNORECASE),
        KnowledgeCategory.definition,
    ),
    (
        re.compile(r"^(methodology|手法)\s*:\s*", re.IGNORECASE),
        KnowledgeCategory.methodology,
    ),
    (
        re.compile(r"^(context|背景)\s*:\s*", re.IGNORECASE),
        KnowledgeCategory.context,
    ),
]

_TABLE_PATTERN = re.compile(r"^(table|テーブル)\s*:\s*", re.IGNORECASE)

_TITLE_MAX_LENGTH = 80


ALLOWED_TARGET_SECTIONS: set[str] = {
    "hypothesis_statement",
    "hypothesis_background",
    "metrics",
    "explanatory",
    "chart",
    "next_action",
    "referenced_knowledge",
    "methodology",
    "analysis_intent",
}

# VALID_TRANSITIONS and validate_transition are imported from
# insight_blueprint.validate (the single source of truth, ADR-0001 / Epic 02).
# They are re-imported above so existing call sites keep their names.


def _parse_knowledge_line(line: str) -> tuple[KnowledgeCategory, str]:
    """Parse a single line for category prefix and return (category, content)."""
    for pattern, cat in _CATEGORY_PATTERNS:
        match = pattern.match(line)
        if match:
            return cat, line[match.end() :].strip()
    return KnowledgeCategory.context, line


def _validate_post_review_status(status: str) -> DesignStatus:
    """Parse and validate a post-review status string.

    Raises ValueError if status is not a valid post-review transition target.
    """
    valid_targets = VALID_TRANSITIONS[DesignStatus.in_review]
    valid_str = ", ".join(s.value for s in valid_targets)

    try:
        target_status = DesignStatus(status)
    except ValueError:
        raise ValueError(
            f"Invalid post-review status '{status}'. Valid: {valid_str}"
        ) from None

    if target_status not in valid_targets:
        raise ValueError(f"Invalid post-review status '{status}'. Valid: {valid_str}")

    return target_status


REVIEWABLE_STATUSES: set[DesignStatus] = {
    DesignStatus.in_review,
    DesignStatus.revision_requested,
}


def _ensure_reviewable(design: AnalysisDesign | None, operation: str) -> None:
    """Raise ValueError if design is not in a reviewable status."""
    if design is not None and design.status not in REVIEWABLE_STATUSES:
        raise ValueError(
            f"Design must be in reviewable status to {operation}, "
            f"current status: '{design.status}'"
        )


class ReviewService:
    """Service for managing the review workflow on analysis designs."""

    def __init__(self, project_path: Path, design_service: DesignService) -> None:
        self._project_path = project_path
        self._designs_dir = project_path / ".insight" / "designs"
        self._rules_dir = project_path / ".insight" / "rules"
        self._design_service = design_service

    def transition_status(
        self, design_id: str, target_status: str
    ) -> AnalysisDesign | None:
        """Transition a design to the given target status.

        Returns None if design not found.
        Raises ValueError if the transition is invalid.
        """
        _validate_id(design_id, "design_id")
        design = self._design_service.get_design(design_id)
        if design is None:
            return None

        try:
            target = DesignStatus(target_status)
        except ValueError:
            raise ValueError(f"Invalid status '{target_status}'") from None

        _validate_transition(design.status, target)

        result = self._design_service.update_design(design_id, status=target)
        self._extract_finding_if_terminal(design_id, target)
        return result

    def save_review_comment(
        self,
        design_id: str,
        comment: str,
        status: str,
        reviewer: str = "analyst",
    ) -> ReviewComment | None:
        """Save a review comment and transition the design status.

        Returns None if design not found.
        Raises ValueError if design is not in reviewable status
        (in_review or revision_requested)
        or if status is not a valid post-review status.
        """
        _validate_id(design_id, "design_id")
        target_status = _validate_post_review_status(status)

        design = self._design_service.get_design(design_id)
        if design is None:
            return None
        _ensure_reviewable(design, "save review comment")

        # Create comment
        comment_id = f"RC-{uuid.uuid4().hex[:8]}"
        review_comment = ReviewComment(
            id=comment_id,
            design_id=design_id,
            comment=comment,
            reviewer=reviewer,
            status_after=target_status,
        )

        # Persist comment
        reviews_path = self._designs_dir / f"{design_id}_reviews.yaml"
        existing = read_yaml(reviews_path)
        comments_list = [
            *existing.get("comments", []),
            review_comment.model_dump(mode="json"),
        ]
        write_yaml(reviews_path, {**existing, "comments": comments_list})

        # Transition design status
        self._design_service.update_design(design_id, status=target_status)
        self._extract_finding_if_terminal(design_id, target_status)

        return review_comment

    def save_review_batch(
        self,
        design_id: str,
        status: str,
        comments: list[dict[str, Any]],
        reviewer: str = "analyst",
    ) -> ReviewBatch | None:
        """Save a batch of review comments and transition the design status.

        Returns None if design not found.
        Raises ValueError if design is not in reviewable status
        (in_review or revision_requested),
        status is invalid, or target_section is not in ALLOWED_TARGET_SECTIONS.
        """
        _validate_id(design_id, "design_id")
        target_status = _validate_post_review_status(status)

        # Validate comments not empty
        if not comments:
            raise ValueError("comments must not be empty")

        # Validate target_section values
        for c in comments:
            section = c.get("target_section")
            if section is not None and section not in ALLOWED_TARGET_SECTIONS:
                raise ValueError(
                    f"Invalid target_section '{section}'. "
                    f"Allowed: {sorted(ALLOWED_TARGET_SECTIONS)}"
                )

        design = self._design_service.get_design(design_id)
        if design is None:
            return None
        _ensure_reviewable(design, "save review batch")

        # Create batch
        batch_id = f"RB-{uuid.uuid4().hex[:8]}"
        batch_comments = [BatchComment(**c) for c in comments]
        batch = ReviewBatch(
            id=batch_id,
            design_id=design_id,
            status_after=target_status,
            reviewer=reviewer,
            comments=batch_comments,
        )

        # Persist batch to YAML (atomic write first)
        reviews_path = self._designs_dir / f"{design_id}_reviews.yaml"
        existing = read_yaml(reviews_path)
        batches_list = [*existing.get("batches", []), batch.model_dump(mode="json")]
        write_yaml(reviews_path, {**existing, "batches": batches_list})

        # Transition design status (after YAML write succeeds)
        self._design_service.update_design(design_id, status=target_status)
        self._extract_finding_if_terminal(design_id, target_status)

        return batch

    def list_review_batches(self, design_id: str) -> list[ReviewBatch]:
        """Read all review batches for a design.

        Returns empty list if no file, no 'batches' key, or corrupted YAML.
        Sorted by created_at descending (newest first).
        """
        _validate_id(design_id, "design_id")
        reviews_path = self._designs_dir / f"{design_id}_reviews.yaml"

        raw_batches = self._read_raw_batches(reviews_path, design_id)
        if raw_batches is None:
            return []

        try:
            batches = [ReviewBatch(**b) for b in raw_batches]
        except Exception:
            logger.warning("Failed to parse review batches for %s", design_id)
            return []

        batches.sort(key=lambda b: b.created_at, reverse=True)
        return batches

    @staticmethod
    def _read_raw_batches(
        reviews_path: Path, design_id: str
    ) -> list[dict[str, Any]] | None:
        """Read and validate raw batch data from YAML. Returns None on failure."""
        try:
            data = read_yaml(reviews_path)
        except Exception:
            logger.warning("Failed to read reviews YAML for %s", design_id)
            return None

        if not data:
            return None

        if "batches" not in data:
            if "comments" in data:
                logger.warning(
                    "Old format (comments key) found for %s, "
                    "batches key missing — returning empty list",
                    design_id,
                )
            else:
                logger.warning("No batches key found in reviews YAML for %s", design_id)
            return None

        raw_batches = data["batches"]
        if not isinstance(raw_batches, list):
            logger.warning("Batches key is not a list for %s", design_id)
            return None

        return raw_batches

    def list_comments(self, design_id: str) -> list[ReviewComment]:
        """Read all review comments for a design.

        Returns empty list if no reviews file exists.
        """
        _validate_id(design_id, "design_id")
        reviews_path = self._designs_dir / f"{design_id}_reviews.yaml"
        data = read_yaml(reviews_path)
        if not data or "comments" not in data:
            return []
        return [ReviewComment(**c) for c in data["comments"]]

    def extract_domain_knowledge(self, design_id: str) -> list[DomainKnowledgeEntry]:
        """Extract domain knowledge entries from review comments as preview.

        Returns a list of DomainKnowledgeEntry items (NOT persisted).
        Scope priority: table: annotation > design.source_ids > [].
        """
        _validate_id(design_id, "design_id")
        comments = self.list_comments(design_id)
        if not comments:
            return []

        # Get default scope from design.source_ids
        design = self._design_service.get_design(design_id)
        default_scope: list[str] = (
            list(design.source_ids) if design and design.source_ids else []
        )

        entries: list[DomainKnowledgeEntry] = []
        index = 0

        for comment in comments:
            current_scope: list[str] | None = None  # None = use default

            for raw_line in comment.comment.split("\n"):
                line = unicodedata.normalize("NFKC", raw_line).strip()
                if not line:
                    continue

                # Check for table: annotation
                table_match = _TABLE_PATTERN.match(line)
                if table_match:
                    table_name = line[table_match.end() :].strip()
                    current_scope = [table_name] if table_name else []
                    continue

                category, content = _parse_knowledge_line(line)
                if not content:
                    continue

                scope = current_scope if current_scope is not None else default_scope

                entry = DomainKnowledgeEntry(
                    key=f"{design_id}-{index}",
                    title=content[:_TITLE_MAX_LENGTH],
                    content=content,
                    category=category,
                    source=f"review:{comment.id}@{design_id}",
                    affects_columns=list(scope),
                )
                entries.append(entry)
                index += 1

        return entries

    _TERMINAL_STATUSES = {
        DesignStatus.supported,
        DesignStatus.rejected,
        DesignStatus.inconclusive,
    }

    def _build_finding(
        self, design: AnalysisDesign, target_status: DesignStatus
    ) -> DomainKnowledgeEntry:
        """Build a finding entry from a design and its target terminal status."""
        raw_title = f"[{target_status.value.upper()}] {design.title}"
        return DomainKnowledgeEntry(
            key=f"{design.id}-finding",
            title=raw_title[:_TITLE_MAX_LENGTH],
            content=design.hypothesis_statement,
            category=KnowledgeCategory.finding,
            source=f"design:{design.id}",
            affects_columns=list(design.source_ids),
        )

    def _extract_finding_if_terminal(
        self, design_id: str, target_status: DesignStatus
    ) -> None:
        """Extract a finding entry if target_status is terminal (fire-and-forget)."""
        if target_status not in self._TERMINAL_STATUSES:
            return
        try:
            design = self._design_service.get_design(design_id)
            if design is None:
                return
            finding = self._build_finding(design, target_status)
            self.save_extracted_knowledge(design_id, [finding])
        except Exception:
            logger.warning(
                "Failed to extract finding for design %s",
                design_id,
                exc_info=True,
            )

    def save_extracted_knowledge(
        self,
        design_id: str,
        entries: list[DomainKnowledgeEntry],
    ) -> list[DomainKnowledgeEntry]:
        """Persist user-confirmed knowledge entries to extracted_knowledge.yaml.

        Duplicate keys are skipped (not overwritten).
        Updates ReviewComment.extracted_knowledge with saved keys.
        Returns the list of newly saved entries.
        """
        _validate_id(design_id, "design_id")
        ek_path = self._rules_dir / "extracted_knowledge.yaml"
        data: dict[str, Any] = read_yaml(ek_path)
        if not data:
            data = {"source_id": "review", "entries": []}

        existing_entries: list[dict[str, Any]] = data.get("entries", [])
        existing_keys = {e["key"] for e in existing_entries}
        saved: list[DomainKnowledgeEntry] = []
        new_entries: list[dict[str, Any]] = []

        for entry in entries:
            if entry.key in existing_keys:
                continue
            new_entries.append(entry.model_dump(mode="json"))
            existing_keys.add(entry.key)
            saved.append(entry)

        data = {**data, "entries": [*existing_entries, *new_entries]}
        write_yaml(ek_path, data)

        if saved:
            self._update_comment_extracted_keys(design_id, saved)

        return saved

    def _update_comment_extracted_keys(
        self, design_id: str, saved: list[DomainKnowledgeEntry]
    ) -> None:
        """Update ReviewComment.extracted_knowledge with saved entry keys."""
        # Build comment_id -> [keys] mapping from entry source field
        comment_keys: dict[str, list[str]] = {}
        for entry in saved:
            # source format: "review:{comment_id}@{design_id}"
            if (
                entry.source
                and entry.source.startswith("review:")
                and "@" in entry.source
            ):
                comment_id = entry.source[len("review:") : entry.source.index("@")]
                comment_keys.setdefault(comment_id, []).append(entry.key)

        if not comment_keys:
            return

        reviews_path = self._designs_dir / f"{design_id}_reviews.yaml"
        reviews_data = read_yaml(reviews_path)
        if not reviews_data or "comments" not in reviews_data:
            return

        for comment_data in reviews_data["comments"]:
            keys_for_comment = comment_keys.get(comment_data.get("id", ""), [])
            if keys_for_comment:
                ek_list = comment_data.get("extracted_knowledge", [])
                comment_data["extracted_knowledge"] = [*ek_list, *keys_for_comment]
        write_yaml(reviews_path, reviews_data)
