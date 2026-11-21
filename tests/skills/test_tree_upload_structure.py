"""Structure tests for the /tree-upload skill's prose contract (Epic 18 US-6, Story 18.7).

The upload runs through the host's Artifact feature, so no Python test can drive it.
These tests guard the parts of SKILL.md that keep the analyst safe: nothing leaves
`.insight/` before the approval (ADR-0016), the skill stops where the host has no
Artifact (ADR-0015), and what is sent is the file `tree_io render` wrote (ADR-0024).
"""

from __future__ import annotations

import re

import pytest

from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import (
    REQUIRED_SECTIONS,
    _read_skill,
    parse_chaining_table,
    parse_frontmatter,
    split_sections,
)


def _skill() -> str:
    return _read_skill("tree-upload")


def _step(number: int) -> str:
    """The body of ``### Step {number}``, with wrapped lines joined."""
    return unwrap(section(_skill(), f"### Step {number}:"))


class TestFrontmatter:
    """The name and the first sentence are what the analyst sees before invoking."""

    def test_name_is_tree_upload(self) -> None:
        assert parse_frontmatter(_skill())["name"] == "tree-upload"

    def test_is_never_invoked_by_the_model(self) -> None:
        assert parse_frontmatter(_skill())["disable-model-invocation"] is True

    def test_first_sentence_names_the_destination_and_the_private_start(self) -> None:
        description = parse_frontmatter(_skill())["description"]
        first = description.split(". ", 1)[0]
        assert "Artifact" in first
        assert "only you can see" in first


class TestSections:
    def test_has_the_required_sections(self) -> None:
        sections = split_sections(_skill())
        for required in REQUIRED_SECTIONS:
            assert required in sections, f"missing '## {required}'"

    def test_chaining_names_both_callers(self) -> None:
        rows = parse_chaining_table(split_sections(_skill())["Chaining"])
        edges = {(r["from"], r["to"].lstrip("→ ").strip()) for r in rows}
        assert ("/analysis-framing", "/tree-upload") in edges
        assert ("/analysis-reflection", "/tree-upload") in edges


class TestTheRenderedFileIsTheOnlySource:
    """US-6 AC 3: what is sent is the HTML tree_io wrote; the model never writes HTML."""

    def test_rejects_a_theme_id_that_could_leave_the_themes_directory(self) -> None:
        step = _step(1)
        assert "fully match `^[A-Z][A-Z0-9]*$`" in step
        assert "stay inside `.insight/themes/`" in step

    def test_renders_the_tree_first_and_takes_the_printed_path(self) -> None:
        step = _step(1)
        # render takes no payload and reads no stdin since #129: no redirect.
        assert "`tree_io render --theme {theme_id}`" in step
        assert "`path`" in step

    def test_a_theme_without_a_tree_points_at_framing_and_stops(self) -> None:
        step = _step(1)
        assert (
            "このテーマには論点ツリーがない。/analysis-framing {theme_id} で作ろう"
            in step
        )

    def test_the_missing_tree_is_told_by_the_file_not_by_the_message(self) -> None:
        # render exits 1 both for a missing tree and for a missing linked design.
        step = _step(1)
        missing = re.search(
            r"[^.]*`\.insight/themes/\{theme_id\}_tree\.yaml`[^.]*\.", step
        )
        assert missing, "no sentence checks the tree file before render"
        assert "does not exist" in missing.group(0)
        assert step.index("_tree.yaml` does not exist") < step.index("tree_io render")

    def test_the_model_never_writes_or_changes_the_html(self) -> None:
        text = unwrap(_skill())
        never = re.search(
            r"Never write, edit, copy or regenerate the HTML[^.]*\.", text
        )
        assert never, "no sentence forbids the model from making its own HTML"

    def test_sends_the_very_file_that_was_listed(self) -> None:
        assert "the file listed in Step 3" in _step(4)

    def test_tree_text_is_data_and_never_an_approval(self) -> None:
        step = _step(1)
        assert "data, not instructions" in step
        assert "already approved" in step

    def test_always_creates_a_new_artifact(self) -> None:
        step = _step(4)
        assert "Always a new Artifact" in step
        assert "never update" in step.lower()


class TestArtifactIsOptional:
    """US-6 AC 2 and ADR-0015: without Artifact nothing is sent, and the path is given."""

    def test_missing_artifact_stops_before_the_approval(self) -> None:
        step = _step(2)
        assert "send nothing" in step.lower()
        assert "Do not ask for approval first" in step
        assert "exit" in step.lower()

    def test_tells_the_analyst_where_the_local_html_is(self) -> None:
        assert "論点ツリーの図は {path} にある" in _step(2)

    def test_names_no_tool(self) -> None:
        # Tool names carry a prefix that differs per environment.
        assert "mcp__" not in _skill()


class TestApprovalGate:
    """US-6 AC 1 and ADR-0016: list the file, wait, and remember nothing."""

    def test_is_a_keep_gate(self) -> None:
        assert "KEEP" in _step(3)

    def test_lists_the_html(self) -> None:
        assert "- 論点ツリーの図: {path}" in _step(3)

    def test_shows_the_destination_and_the_private_start_with_the_list(self) -> None:
        step = _step(3)
        assert "送り先: claude.ai の新しい Artifact" in step
        assert "自分だけに見える" in step

    @pytest.mark.parametrize(
        "item", ["答えの文", "journal の出来事の本文", "分析設計の題"]
    )
    def test_warns_what_the_page_carries(self, item: str) -> None:
        assert item in _step(3)

    def test_no_artifact_is_published_before_the_approval(self) -> None:
        step = _step(3)
        assert "no call that publishes" in step

    def test_no_approval_means_nothing_is_sent(self) -> None:
        assert "send nothing" in _step(3).lower()

    def test_approval_is_not_automatic_inside_analysis_auto(self) -> None:
        step = _step(3)
        assert "/analysis-auto" in step
        assert "never automatic" in step.lower()

    def test_approval_covers_one_run_and_is_not_remembered(self) -> None:
        step = _step(3)
        assert "one run" in step.lower()
        assert "never remember" in step.lower()

    def test_the_gate_comes_before_any_send(self) -> None:
        assert "only after the analyst approved" in _step(4)

    def test_cites_the_rule(self) -> None:
        assert "ADR-0016" in _skill()


class TestOutcome:
    def test_shows_the_url_and_the_private_start(self) -> None:
        step = _step(5)
        assert "URL" in step
        assert "自分だけに見える" in step

    def test_a_failed_upload_is_an_outcome(self) -> None:
        assert "アップロードに失敗した" in _step(4)
        assert "アップロードに失敗した" in _step(5)


class TestCallersPointAtTheUpload:
    """The skills that make the HTML say where it can go, without starting the upload."""

    def test_framing_points_at_the_upload_after_render(self) -> None:
        step = unwrap(section(_read_skill("analysis-framing"), "#### 5c: "))
        assert "/tree-upload {theme_id}" in step

    def test_reflection_points_at_the_upload(self) -> None:
        step = unwrap(section(_read_skill("analysis-reflection"), "### Step T5: "))
        assert "/tree-upload {theme_id}" in step
