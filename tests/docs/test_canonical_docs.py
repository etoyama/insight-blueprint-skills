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


def _h3_section(markdown: str, heading: str) -> str:
    rest = markdown[markdown.index(heading) :]
    following = re.search(r"^#{1,3} ", rest[len(heading) :], re.MULTILINE)
    return rest[: len(heading) + following.start()] if following else rest


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
        requirements = _h3_section(_read("docs/PRD.md"), "### 機能要件")
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
        sequence = _h3_section(_read("docs/ARCHITECTURE.md"), heading)
        assert "/report-upload" in sequence
        assert "Claude Docs" in sequence

    def test_autopilot_sequence_asks_about_the_upload_once_from_the_skill(self) -> None:
        sequence = _h3_section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        asks = [
            line.strip()
            for line in sequence.splitlines()
            if "【KEEP】" in line and ("送る" in line or "アップロード" in line)
        ]
        assert len(asks) == 1, asks
        assert asks[0].startswith("P->>U:"), "the gate belongs to /report-upload"

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
