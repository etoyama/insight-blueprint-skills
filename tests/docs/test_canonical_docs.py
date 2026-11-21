"""Structure tests for the canonical documents (Epic 11, docs/design/epic-11-repo-template-compliance.md).

docs/WORKFLOW.md §2 says each piece of information has one canonical home and
CLAUDE.md only points at them. These tests catch the drift that rule cannot:
dead links, a canonical body copied back into CLAUDE.md, and names that no longer
exist in the code.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest

from tests.skills._markdown import section

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "export_yomiyasu_words", REPO_ROOT / "scripts/export_yomiyasu_words.py"
)
assert _spec and _spec.loader
words = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(words)

_LINK = re.compile(r"\]\(([^)\s]+)\)")

ADR_DIR = REPO_ROOT / "docs/adr"
# ADR-0009 onward use the repo-template format (ADR-0009, Decision D2・D3).
NEW_FORMAT_FROM = 9
NEW_FORMAT_SECTIONS = [
    "Status",
    "Context",
    "Problem",
    "Decision Analysis",
    "Decision",
    "Consequences",
    "Alternatives considered",
    "Related",
]
MODEL_FILES = [
    *sorted((REPO_ROOT / "src/insight_blueprint/models").glob("*.py")),
    REPO_ROOT / "skills/_shared/models.py",
]
EPIC_DOCS = sorted((REPO_ROOT / "docs/design").glob("epic-*.md"))
REMOVED_FEATURE_TERMS = (
    "WebUI",
    "REST API",
    "MCP server",
    "MCP サーバ",
    "SQLite",
    "batch-analysis",
)


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _h2_titles(text: str) -> list[str]:
    return [
        re.sub(r"^\d+\.\s*", "", line[3:].strip())
        for line in words.strip_code_fences(text).splitlines()
        if line.startswith("## ")
    ]


def _adr_files() -> list[Path]:
    return sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


def _new_format_adrs() -> list[Path]:
    return [p for p in _adr_files() if int(p.name[:4]) >= NEW_FORMAT_FROM]


LIVING_DOCS = [
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "docs/PRD.md",
    "docs/ARCHITECTURE.md",
    "docs/UBIQUITOUS_LANGUAGE.md",
    "docs/adr/README.md",
    "docs/design/epic-11-repo-template-compliance.md",
    "docs/design/epic-12-decision-ready-report.md",
    "docs/design/epic-13-report-source-text.md",
    "docs/design/epic-14-report-template-gaps.md",
    "docs/design/epic-18-question-tree.md",
    *(str(p.relative_to(REPO_ROOT)) for p in _new_format_adrs()),
]


@pytest.mark.parametrize("rel", LIVING_DOCS)
def test_relative_links_resolve(rel: str) -> None:
    base = (REPO_ROOT / rel).parent
    dead = [
        target
        for target in _LINK.findall(_read(rel))
        if not target.startswith(("http://", "https://", "mailto:", "#"))
        and not (base / target.split("#", 1)[0]).exists()
    ]
    assert dead == []


class TestClaudeMd:
    """US-1: CLAUDE.md holds only a summary and pointers."""

    def test_has_the_repo_template_sections(self) -> None:
        titles = _h2_titles(_read("CLAUDE.md"))
        for expected in (
            "Documents",
            "Development Workflow",
            "ADR",
            "Coding Principles",
            "Rules and Templates",
            "Language",
        ):
            assert any(t.startswith(expected) for t in titles), expected

    def test_does_not_hold_canonical_bodies(self) -> None:
        text = _read("CLAUDE.md")
        titles = _h2_titles(text)
        assert not any(
            t.startswith(("Skills", "Skill-Managed Data", "Validation Guard"))
            for t in titles
        )
        assert not re.search(r"^\|\s*`/[a-z-]+`\s*\|", text, re.MULTILINE), (
            "Skills table belongs to README"
        )

    def test_code_review_does_not_name_the_removed_tool(self) -> None:
        assert "orchestra:team-review" not in _read("CLAUDE.md")


class TestContributing:
    """US-1 AC 4: CONTRIBUTING.md keeps only the repo-specific sections."""

    def test_has_only_the_four_sections(self) -> None:
        titles = _h2_titles(_read("CONTRIBUTING.md"))
        assert titles == ["Setup", "Common Commands", "Testing", "Security Checklist"]


class TestRoadmap:
    """US-2 AC 1, AC 2: the PRD roadmap is the one list of Epics; ARCHITECTURE has a context map."""

    def test_prd_roadmap_links_every_epic(self) -> None:
        roadmap = words.section(_read("docs/PRD.md"), "ロードマップ")
        missing = [p.name for p in EPIC_DOCS if f"design/{p.name}" not in roadmap]
        assert missing == []

    def test_architecture_has_a_context_map(self) -> None:
        assert "コンテキストマップ" in _h2_titles(_read("docs/ARCHITECTURE.md"))


def _model_classes() -> dict[str, ast.ClassDef]:
    classes: dict[str, ast.ClassDef] = {}
    for path in MODEL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes |= {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    return classes


def _enum_members(node: ast.ClassDef) -> list[str] | None:
    if not any(isinstance(b, ast.Name) and b.id == "StrEnum" for b in node.bases):
        return None
    return [
        target.id
        for stmt in node.body
        if isinstance(stmt, ast.Assign)
        for target in stmt.targets
        if isinstance(target, ast.Name)
    ]


def _diagram_classes() -> dict[str, list[str]]:
    section = words.section(_read("docs/ARCHITECTURE.md"), "Domain Model")
    diagram = re.search(r"```mermaid\s*\nclassDiagram\n(.*?)```", section, re.DOTALL)
    assert diagram, "classDiagram block not found"
    boxes = re.findall(
        r"^\s*class (\w+) \{\n(.*?)^\s*\}", diagram.group(1), re.MULTILINE | re.DOTALL
    )
    return {
        name: [line.strip() for line in body.splitlines() if line.strip()]
        for name, body in boxes
    }


class TestDomainModelDiagram:
    """US-2 AC 3: the overall classDiagram matches the model classes in the code."""

    def test_class_diagram_lists_exactly_the_model_classes(self) -> None:
        assert set(_diagram_classes()) == set(_model_classes())

    def test_enum_boxes_list_exactly_the_enum_members(self) -> None:
        drawn = _diagram_classes()
        for name, node in _model_classes().items():
            members = _enum_members(node)
            if members is None:
                continue
            assert drawn[name][0] == "<<enumeration>>", name
            assert drawn[name][1:] == members, name


def _code_corpus() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for root in ("src", "skills")
        for p in (REPO_ROOT / root).rglob("*")
        if p.is_file() and p.suffix in {".py", ".md"}
    )


class TestUbiquitousLanguage:
    """US-2 AC 4, AC 5: the first edition holds domain terms whose code names exist."""

    def test_context_is_filled_in(self) -> None:
        assert "<コンテキスト名>" not in _read("docs/UBIQUITOUS_LANGUAGE.md")

    def test_code_names_exist_in_the_code(self) -> None:
        corpus = _code_corpus()
        rows = words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        missing = [
            name
            for row in rows
            for name in re.findall(r"`([^`]+)`", row[words.CODE_NAME])
            if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", corpus)
        ]
        assert missing == []

    def test_has_no_removed_feature_terms(self) -> None:
        for row in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md")):
            text = " ".join(
                (row[words.TERM], row[words.CODE_NAME], row[words.DEFINITION])
            )
            for term in REMOVED_FEATURE_TERMS:
                assert term not in text, (term, row[words.TERM])

    def test_analysis_design_is_the_canonical_term(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "設計書" in rows["分析設計"][words.AVOID]


class TestAdrs:
    """US-3: the interpretations are ADRs in the new format, all indexed and referenced."""

    def test_every_adr_is_in_the_index(self) -> None:
        index = _read("docs/adr/README.md")
        missing = [p.name for p in _adr_files() if f"]({p.name})" not in index]
        assert missing == []

    @pytest.mark.parametrize("path", _new_format_adrs(), ids=lambda p: p.name[:4])
    def test_new_format_adr_has_every_section(self, path: Path) -> None:
        assert _h2_titles(path.read_text(encoding="utf-8")) == NEW_FORMAT_SECTIONS

    def test_claude_md_points_at_the_single_pr_rule(self) -> None:
        assert "docs/adr/0012-" in _read("CLAUDE.md")

    def test_architecture_domain_model_cites_its_adr(self) -> None:
        assert "adr/0011-" in words.section(
            _read("docs/ARCHITECTURE.md"), "Domain Model"
        )


class TestExternalSendRules:
    """Epic 12 US-4 AC 5: the invariant and the approval rule sit where the next author reads."""

    INVARIANT = (
        "plugin は常駐プロセス・MCP サーバ・SQLite を同梱しない。"
        "ホストが持つコネクタは、無くても核が動く任意の機能に限って使ってよい。"
    )

    def test_architecture_states_the_invariant_with_its_condition(self) -> None:
        invariants = words.section(
            _read("docs/ARCHITECTURE.md"), "不変条件（invariants）"
        )
        assert self.INVARIANT in invariants
        assert "adr/0015-" in invariants

    def test_architecture_lists_the_external_send_gate(self) -> None:
        text = _read("docs/ARCHITECTURE.md")
        model = text[text.index("### Skill invocation model") :].split("\n## ", 1)[0]
        assert "`.insight/` の中身を外部へ送る" in model
        assert "adr/0016-" in model

    def test_adr_0001_stays_frozen(self) -> None:
        assert "コネクタ" not in _read(
            "docs/adr/0001-drop-mcp-server-embed-validation.md"
        )

    def test_upload_is_a_term(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "`/report-upload`" in rows["アップロード"][words.CODE_NAME]
        for avoided in ("公開", "共有"):
            assert avoided in rows["アップロード"][words.AVOID]

    def test_design_doc_links_both_adrs(self) -> None:
        doc = _read("docs/design/epic-12-decision-ready-report.md")
        assert "../adr/0015-" in doc and "../adr/0016-" in doc


def _first_cells(table_section: str) -> list[str]:
    rows = [
        line.strip("|").split("|")[0].strip()
        for line in table_section.splitlines()
        if line.startswith("|")
    ]
    return rows[2:]


class TestReportAndUploadDocs:
    """Epic 12 US-5 AC 3, AC 4: the documents carry the report and the upload."""

    def test_readme_lists_every_bundled_skill(self) -> None:
        listed = words.section(_read("README.md"), "Skills")
        bundled = sorted(
            p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")
        )
        assert [name for name in bundled if f"`/{name}`" not in listed] == []

    def test_readme_workflow_shows_the_upload(self) -> None:
        assert "/report-upload" in words.section(
            _read("README.md"), "Analysis Workflow"
        )

    def test_prd_functional_requirements_carry_the_report_and_the_upload(self) -> None:
        requirements = section(_read("docs/PRD.md"), "### 機能要件")
        assert "レポート" in requirements
        assert "アップロード" in requirements

    def test_ubiquitous_language_has_the_terms_of_epic_12(self) -> None:
        terms = {
            r[words.TERM]
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        added = {"決定の文脈", "効果量", "信頼区間", "標本サイズ", "アップロード"}
        assert added - terms == set()

    def test_keep_gate_covers_the_external_send(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "外部へ送る" in rows["KEEP ゲート"][words.DEFINITION]
        assert "adr/0016-" in rows["KEEP ゲート"]["初出"]

    @pytest.mark.parametrize(
        "heading",
        ["### 分析ワークフロー全体", "### guided autopilot（`/analysis-auto`）"],
    )
    def test_architecture_sequences_include_the_upload(self, heading: str) -> None:
        sequence = section(_read("docs/ARCHITECTURE.md"), heading)
        assert "/report-upload" in sequence
        assert "Claude Docs" in sequence

    def test_autopilot_sequence_asks_about_the_upload_once_from_the_skill(self) -> None:
        sequence = section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        asks = [
            line.strip()
            for line in sequence.splitlines()
            if "【KEEP】" in line and ("送る" in line or "アップロード" in line)
        ]
        # Story 18.9 adds the gate of /tree-upload; each send is asked once, by its skill.
        assert [line.split(":")[0] for line in asks] == ["P->>U", "TU->>U"], asks

    def test_architecture_epic_mapping_covers_every_roadmap_epic(self) -> None:
        roadmap = _first_cells(words.section(_read("docs/PRD.md"), "ロードマップ"))
        mapped = _first_cells(
            words.section(_read("docs/ARCHITECTURE.md"), "Epic マッピング")
        )
        assert [epic for epic in roadmap if epic not in mapped] == []


class TestYomiyasuWords:
    """WORKFLOW §8: .yomiyasu-words/ is exported from UBIQUITOUS_LANGUAGE, never edited by hand."""

    def test_word_lists_match_the_ubiquitous_language(self) -> None:
        for name, content in words.render(_read("docs/UBIQUITOUS_LANGUAGE.md")).items():
            assert _read(f".yomiyasu-words/{name}") == content, (
                f"{name} is stale: run uv run python scripts/export_yomiyasu_words.py"
            )


class TestPluginVariables:
    """The host fills in plugin variables in skill text, not in the Bash tool's environment."""

    def test_architecture_path_resolution_cites_the_adr(self) -> None:
        paths = section(_read("docs/ARCHITECTURE.md"), "### パス解決機構")
        assert "Bash ツールの環境" in paths
        assert "adr/0017-" in paths

    def test_adr_0006_stays_frozen(self) -> None:
        assert "0017" not in _read("docs/adr/0006-plugin-execution-model.md")


class TestReleaseProcedure:
    """Existing plugin installs update only when plugin.json's version changes."""

    def test_intro_ties_plugin_updates_to_the_manifest_version(self) -> None:
        intro = _read("docs/RELEASE.md").split("\n## ", 1)[0]
        assert ".claude-plugin/plugin.json" in intro

    def test_version_bump_names_both_files(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 1")
        assert "pyproject.toml" in step
        assert ".claude-plugin/plugin.json" in step

    def test_version_bump_names_the_marketplace_ref(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 1")
        assert ".claude-plugin/marketplace.json" in step
        assert "adr/0032-" in step

    def test_tag_step_says_installs_wait_for_the_tag(self) -> None:
        """Between the merge and the tag, the marketplace points at a tag that does not exist."""
        step = section(_read("docs/RELEASE.md"), "## Step 3")
        assert "marketplace" in step

    def test_preflight_covers_the_publish_action(self) -> None:
        """A local twine check does not run the twine bundled in the publish action."""
        step = section(_read("docs/RELEASE.md"), "## Step 2")
        assert "gh-action-pypi-publish" in step
        assert "Dependabot" in step

    def test_troubleshooting_covers_a_rejected_metadata_version(self) -> None:
        trouble = section(_read("docs/RELEASE.md"), "## Troubleshooting")
        assert "not a valid metadata version" in trouble


class TestQuestionTreeDocs:
    """Epic 18 first edition: the PRD carries the question tree, and the DesignDoc has its diagrams."""

    DESIGN_DOC = "docs/design/epic-18-question-tree.md"

    def test_prd_core_values_carry_the_question_tree(self) -> None:
        assert "論点ツリー" in section(_read("docs/PRD.md"), "## コアバリュー")

    def test_prd_functional_requirements_carry_the_question_tree(self) -> None:
        requirements = section(_read("docs/PRD.md"), "### 機能要件")
        for phrase in ("論点ツリー", "到達点", "現時点の答え", "Artifact"):
            assert phrase in requirements, phrase

    def test_prd_requires_checked_answers_and_generated_display(self) -> None:
        requirements = section(_read("docs/PRD.md"), "### 非機能要件")
        assert "ツリーの検査" in requirements
        assert "決定的に生成" in requirements

    def test_prd_success_criteria_separate_the_product_from_the_migration(self) -> None:
        criteria = section(_read("docs/PRD.md"), "## 成功基準")
        assert "### 製品" in criteria
        assert "### 移行期（達成済み）" in criteria
        assert "引き継ぎの試行" in criteria

    def test_ubiquitous_language_has_the_terms_of_epic_18(self) -> None:
        terms = {
            r[words.TERM]
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        added = {
            "論点ツリー",
            "論点",
            "根の問い",
            "到達点",
            "根の版",
            "寄与",
            "発見元",
            "進捗",
            "現時点の答え",
            "振り返りの回",
            "ツリーの決定",
            "次の候補",
            "ツリーの検査",
            "Artifact",
            "合成シナリオ",
            "引き継ぎの試行",
            "巡回",
        }
        assert added - terms == set()

    @pytest.mark.parametrize(
        ("heading", "diagram"),
        [
            ("## Architecture", "flowchart"),
            ("## Domain Model", "classDiagram"),
            ("## Sequence Diagram", "sequenceDiagram"),
        ],
    )
    def test_design_doc_has_the_first_edition_diagram(
        self, heading: str, diagram: str
    ) -> None:
        assert f"```mermaid\n{diagram}" in section(_read(self.DESIGN_DOC), heading)

    def test_design_doc_links_both_adrs(self) -> None:
        doc = _read(self.DESIGN_DOC)
        assert "adr/0024-question-tree-yaml-and-generated-html.md" in doc
        assert "adr/0025-cited-answers-checked-after-writing.md" in doc

    def test_design_doc_makes_analysis_auto_the_entry(self) -> None:
        doc = _read(self.DESIGN_DOC)
        assert "adr/0026-analysis-auto-walks-the-question-tree.md" in doc
        assert "### US-8" in section(doc, "## User Stories")
        assert "/analysis-auto" in section(doc, "## Architecture")
        scope = section(doc, "## Scope")
        in_scope = scope.split("- Epic 範囲外:")[0]
        assert "/analysis-auto" in in_scope
        assert "/analysis-auto" not in scope.split("- Epic 範囲外:")[1]

    def test_design_doc_records_the_two_decisions_made_after_the_first_edition(
        self,
    ) -> None:
        decisions = section(_read(self.DESIGN_DOC), "## Decisions")
        assert "### Decision: inquiry-answer-copied-to-journal" in decisions
        assert "### Decision: ask-once-for-treeless-design" in decisions

    def test_design_doc_uses_the_type_names_the_human_chose(self) -> None:
        """Story 18.1: NextCandidate, Answer and Aim replace the first proposal."""
        model = section(_read(self.DESIGN_DOC), "## Domain Model")
        for name in ("NextCandidate", "Answer", "Aim"):
            assert f"class {name} {{" in model, name
        for name in ("Inquiry", "CurrentAnswer", "Destination"):
            assert name not in model, name

    def test_ubiquitous_language_names_the_tree_classes_that_exist(self) -> None:
        rows = {
            r[words.TERM]: r[words.CODE_NAME]
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        expected = {
            "論点ツリー": "QuestionTree",
            "論点": "QuestionNode",
            "到達点": "Aim",
            "根の版": "RootRevision",
            "寄与": "contribution",
            "発見元": "origin_event_id",
            "進捗": "Progress",
            "ツリーの決定": "TreeDecision",
        }
        for term, name in expected.items():
            assert f"`{name}`" in rows[term], term

    def test_design_doc_records_the_decisions_of_story_18_2(self) -> None:
        decisions = section(_read(self.DESIGN_DOC), "## Decisions")
        for slug in (
            "start-is-the-only-decision-kind-for-now",
            "decisions-are-append-only",
            "framing-brief-carries-node-id",
            "meaning-change-raises-the-root-revision",
        ):
            assert f"### Decision: {slug}" in decisions, slug

    def test_architecture_workflow_shows_the_tree_being_written_and_linked(
        self,
    ) -> None:
        """Story 18.2: framing writes the tree and design links itself to a node."""
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        assert "tree_io create / add-node / decide" in sequence
        assert "tree_io link" in sequence

    def test_architecture_workflow_shows_the_answers_being_checked_and_written(
        self,
    ) -> None:
        """Story 18.4: the theme reflection writes answers only through the check."""
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        assert "tree_io answer" in sequence
        assert "tree_check" in sequence

    def test_design_doc_records_how_answers_are_written(self) -> None:
        decisions = section(
            _read("docs/design/epic-18-question-tree.md"), "## Decisions"
        )
        for slug in (
            "answers-are-checked-before-they-land",
            "one-answer-call-is-one-round",
        ):
            assert f"### Decision: {slug}" in decisions, slug

    AUTOPILOT = "### guided autopilot（`/analysis-auto`）"

    def test_architecture_autopilot_reads_the_position_and_walks_node_by_node(
        self,
    ) -> None:
        """Story 18.9 (US-8 AC 1, AC 2, AC 5): resume from the position, loop over nodes."""
        sequence = section(_read("docs/ARCHITECTURE.md"), self.AUTOPILOT)
        assert "tree_io position" in sequence
        for state in ("no_tree", "not_started", "in_progress", "concluded", "closed"):
            assert state in sequence, state
        assert "loop 論点ごとの巡回" in sequence
        assert "/rq-problematization" in sequence

    def test_architecture_autopilot_shows_the_five_new_gates(self) -> None:
        """US-8 AC 3."""
        sequence = section(_read("docs/ARCHITECTURE.md"), self.AUTOPILOT)
        keeps = [line for line in sequence.splitlines() if "【KEEP" in line]
        for gate in (
            "ツリーを作って巡回に入るか",
            "根の問い",
            "最初に調べる論点",
            "ツリーの決定",
            "根の版",
        ):
            assert any(gate in line for line in keeps), gate

    def test_architecture_autopilot_writes_the_report_without_asking(self) -> None:
        """US-8 AC 4: the report is AUTO and comes before the tree decision."""
        sequence = section(_read("docs/ARCHITECTURE.md"), self.AUTOPILOT)
        report = next(
            line for line in sequence.splitlines() if "/analysis-report" in line
        )
        assert "AUTO" in report and "【KEEP" not in report
        assert sequence.index(report) < sequence.index("ツリーの決定（深める")
        assert "レポートのパスと論点ツリーの HTML のパス" in sequence

    def test_architecture_invocation_model_lists_the_gates_of_the_walk(self) -> None:
        model = section(_read("docs/ARCHITECTURE.md"), "### Skill invocation model")
        assert "adr/0026-analysis-auto-walks-the-question-tree.md" in model
        assert "ツリーの決定" in model
        assert "レポートの生成 /" not in model

    def test_architecture_workflow_names_the_autopilot_as_the_entry(self) -> None:
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        assert "入口" in sequence
        assert "巡回" in sequence
        report = sequence.index("/analysis-report")
        assert report < sequence.index("/analysis-reflection {theme_id}")

    def test_design_doc_records_the_decisions_of_the_walk(self) -> None:
        decisions = section(
            _read("docs/design/epic-18-question-tree.md"), "## Decisions"
        )
        for slug in (
            "position-is-derived-by-tree-io",
            "auto-does-not-ask-twice-for-a-decided-node",
            "framing-places-existing-designs",
        ):
            assert f"### Decision: {slug}" in decisions, slug

    def test_architecture_carries_the_tree_file_and_its_guard(self) -> None:
        """ADR-0024: the .insight layout and the hook target change with Story 18.1."""
        doc = _read("docs/ARCHITECTURE.md")
        layout = section(doc, "### 2. plugin 利用者視点の構成")
        assert "themes/" in layout
        assert "{theme_id}_tree.yaml" in layout
        components = section(doc, "## コンポーネントと責務")
        assert "*_tree.yaml" in components
        assert "validate_tree" in components
        assert "tree_io" in section(doc, "### パス解決機構")
