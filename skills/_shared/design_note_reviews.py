"""The review batches of a design, as the analysis note shows them (Epic 33, ADR-0054 5).

Pure: no I/O. ``design_note_read`` reads ``{id}_reviews.yaml`` into
``NoteReviewBatch`` values; ``design_note`` places one block per batch in its
"レビュー" section, and the question tree counts the comments written after the
analysis started.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from skills._shared._html import Html, el, join, table


@dataclass(frozen=True)
class NoteReviewComment:
    """One review comment of a batch, as written: the analyst's own text."""

    comment: str
    target_section: str | None
    target_content: str | None  # a JSON value: a string bare, anything else as JSON


@dataclass(frozen=True)
class NoteReviewBatch:
    """One review batch of ``{id}_reviews.yaml``, as written (ADR-0054 5)."""

    id: str
    created_at: str
    # None: a batch saved before Epic 33, which does not tell (ADR-0054 4).
    after_analysis_started: bool | None
    status_after: str
    reviewer: str
    comments: tuple[NoteReviewComment, ...]


def comments_after_analysis(reviews: Iterable[NoteReviewBatch]) -> int:
    """The review comments of the batches written after the analysis started.

    A batch that does not tell is not counted: the count says only what the
    records hold (ADR-0054 6).
    """
    return sum(len(b.comments) for b in reviews if b.after_analysis_started is True)


# The note marks a batch with it and the tree counts its comments under it, so
# the two say the same words.
AFTER_ANALYSIS = "分析を始めた後の review"
_BEFORE_ANALYSIS = "分析を始める前の review"

_DASH = "—"


def review_batch(batch: NoteReviewBatch, status_after: str) -> Html:
    """One batch: its time and id, when it came, *status_after*, the reviewer, the comments."""
    after = batch.after_analysis_started
    return join(
        [
            el("h4", f"{batch.created_at} {batch.id}"),
            # A batch saved before Epic 33 does not tell, so nothing is said.
            None
            if after is None
            else el("p", AFTER_ANALYSIS if after else _BEFORE_ANALYSIS),
            el("p", f"review の後の状態: {status_after}"),
            el("p", f"reviewer: {batch.reviewer}"),
            table(
                ("review コメント", "対象", "対象の中身"),
                (
                    (c.comment, c.target_section or _DASH, c.target_content or _DASH)
                    for c in batch.comments
                ),
            ),
        ]
    )
