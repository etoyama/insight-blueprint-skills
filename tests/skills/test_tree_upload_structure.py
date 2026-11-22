"""Structure tests for the /tree-upload skill's prose contract (Epic 18 US-6, Story 18.7).

The upload runs through the host's Artifact feature, so no Python test can drive it.
These tests guard the parts of SKILL.md that keep the analyst safe: nothing leaves
`.insight/` before the approval (ADR-0016), the skill stops where the host has no
Artifact (ADR-0015), and what is sent is the file `tree_io render` wrote (ADR-0024).

Since Epic 28 (US-6, Story 28.6) that file carries the analysis note of every design
of the theme, so the gate names what the page carries, a page over the Artifact limit
stops before the gate, and the docs that describe the upload say the same (ADR-0037).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from skills._shared import tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import (
    REQUIRED_SECTIONS,
    SKILLS_DIR,
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
        assert "- 論点ツリーの HTML（分析ノートを含む）: {path}" in _step(3)

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


REPO_ROOT = SKILLS_DIR.parent

# Artifact allows a page of 16MB. Decimal megabytes are the smaller reading, so a
# page under this never meets a host that counts in MiB and refuses it.
LIMIT_BYTES = "16,000,000"


def _doc(relative: str) -> str:
    return (REPO_ROOT / relative).read_text("utf-8")


class TestTheNotesGoAsOneFile:
    """US-6 AC 1 and AC 4: the one rendered file goes as it is, with nothing beside it."""

    def test_the_publish_attaches_no_other_file(self) -> None:
        step = _step(4)
        assert "attach no other file" in step
        assert "the page links to" in step

    @pytest.mark.parametrize(
        "kept",
        [
            "the notebook's `.py`",
            "the verdict",
            "the Markdown report",
            "the notebook's HTML",
        ],
    )
    def test_the_files_behind_the_notes_are_never_sent(self, kept: str) -> None:
        # The sentence names `.py`, so it is cut at its colon, not at a period.
        never = re.search(r"Never send [^:]*:", _step(4))
        assert never, "no sentence names the files that stay on this machine"
        assert kept in never.group(0)

    def test_the_publish_step_gives_the_reason_the_files_stay(self) -> None:
        assert "ADR-0022" in _step(4)

    def test_making_the_html_does_not_repeat_the_rule(self) -> None:
        """#143: the rule lives in Step 4, and the gate tells the analyst."""
        assert "Never send" not in _step(1)

    def test_the_gate_says_the_local_files_stay(self) -> None:
        step = _step(3)
        assert (
            "notebook の .py・verdict・Markdown のレポート・notebook の HTML は送らない"
            in step
        )
        assert "「手元のファイル」のリンクは Artifact では開けない" in step


class TestTheGateNamesWhatThePageCarries:
    """US-6 AC 2: the approval is given knowing the notes go with the tree."""

    @pytest.mark.parametrize(
        "item",
        [
            "手法",
            "指標の定義と値",
            "図",
            "journal のすべての出来事",
            "分析コード",
            "結論の後は結論と振り返りの本文",
        ],
    )
    def test_names_what_each_note_carries(self, item: str) -> None:
        notes = re.search(r"分析ノートには、[^。]*。", _step(3))
        assert notes, "the gate does not say what a note carries"
        assert item in notes.group(0)

    def test_every_design_of_the_theme_has_a_note_on_the_page(self) -> None:
        assert "テーマの分析設計ごとの分析ノート" in _step(3)

    def test_says_the_tree_cannot_go_without_the_notes(self) -> None:
        assert "分析ノートを含まない論点ツリーだけを送る手段は無い" in _step(3)

    def test_asks_to_read_the_notes_before_sending(self) -> None:
        assert "分析ノートまで確かめてほしい" in _step(3)

    def test_the_description_says_the_notes_go_too(self) -> None:
        description = parse_frontmatter(_skill())["description"]
        assert "analysis note of every design" in unwrap(description)


class TestAPageOverTheLimitStopsBeforeTheGate:
    """US-6 AC 3: over the Artifact limit, say so before asking and send nothing."""

    def test_the_limit_is_checked_in_step_2_before_the_gate(self) -> None:
        step = _step(2)
        assert f"{LIMIT_BYTES} bytes" in step
        assert "wc -c < {path}" in step

    def test_over_the_limit_tells_the_size_and_sends_nothing(self) -> None:
        step = _step(2)
        assert (
            "論点ツリーの HTML は {bytes} バイトあり、Artifact の上限（16MB）を超えるので、"
            "アップロードできない。何も送っていない。"
        ) in step
        over = step[step.index(f"{LIMIT_BYTES} bytes") :]
        assert "Do not ask for approval" in over

    def test_over_the_limit_is_an_outcome_for_the_caller(self) -> None:
        assert "大きすぎて送れない" in _step(5)

    def test_the_shown_size_command_counts_the_bytes_of_the_page(
        self, tmp_path: Path
    ) -> None:
        insight = tmp_path / ".insight"
        tree_io.create_tree(
            theme_id="LIB",
            question="取り置き期限を延ばす試行をするか",
            aim={
                "kind": "business",
                "decision_maker": "図書館員",
                "decision": "試行を始めるか",
            },
            base_dir=insight,
        )
        path = tree_io.render("LIB", base_dir=insight)["path"]
        shown = re.search(r"`(wc -c < \{path\})`", _step(2))
        assert shown, "no size command is shown"

        counted = subprocess.run(
            shown[1].replace("{path}", path),
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert int(counted) == Path(path).stat().st_size


class TestTheDocsDescribeTheSameUpload:
    """US-6 AC 5: README, ARCHITECTURE, the glossary and the autopilot agree."""

    def test_readme_says_the_notes_go_with_the_tree(self) -> None:
        line = next(
            line for line in _doc("README.md").splitlines() if "`/tree-upload`" in line
        )
        assert "analysis note of every design" in line

    def test_architecture_layout_has_the_notes(self) -> None:
        layout = _doc("docs/ARCHITECTURE.md")
        tree_html = next(
            line for line in layout.splitlines() if "{theme_id}_tree.html  " in line
        )
        assert "分析ノート" in tree_html
        assert re.search(r"notes/\s*\n\s*│?\s*└── \{design_id\}\.html", layout)

    def test_architecture_gate_list_names_the_one_file(self) -> None:
        gate = next(
            line
            for line in _doc("docs/ARCHITECTURE.md").splitlines()
            if line.startswith("- 外部へ送る前:")
        )
        assert "分析ノートを含む論点ツリーの HTML" in gate

    def test_architecture_sequence_lists_the_notes_and_the_limit(self) -> None:
        lines = _doc("docs/ARCHITECTURE.md").splitlines()
        asked = next(line for line in lines if "TU->>U: 【KEEP】" in line)
        assert "分析ノートを含む" in asked
        assert any("TU-->>U:" in line and "上限" in line for line in lines)

    def test_architecture_no_longer_calls_epic_28_planned(self) -> None:
        row = next(
            line
            for line in _doc("docs/ARCHITECTURE.md").splitlines()
            if line.startswith("| Epic 28 |")
        )
        assert "計画中" not in row

    def test_the_glossary_upload_sends_the_notes_in_one_file(self) -> None:
        row = table_row(_doc("docs/UBIQUITOUS_LANGUAGE.md"), "アップロード")
        assert "分析ノートを含む論点ツリーの HTML" in row[2]
        assert "添えるファイルは送らない" in row[2]
        assert "ADR-0037" in row[4]

    def test_the_glossary_code_name_of_the_note_is_the_code(self) -> None:
        row = table_row(_doc("docs/UBIQUITOUS_LANGUAGE.md"), "分析ノート")
        code = (SKILLS_DIR / "_shared" / "design_note.py").read_text("utf-8")
        assert "`design_note`" in row[1]
        assert "`DesignNote`" in row[1]
        assert "class DesignNote" in code

    def test_the_autopilot_row_leaves_what_is_sent_to_tree_upload(self) -> None:
        gates = split_sections(_read_skill("analysis-auto"))["Gate policy"]
        row = table_row(gates, "tree-upload")
        assert "the tree's HTML" not in row[1]
        assert "no question of its own" in row[1]
