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

from tests.docs._changelog import changelog_entry
from tests.skills._markdown import section, table_rows, unwrap

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


def _without_link_targets(text: str) -> str:
    """Drop link targets, so citing an ADR whose file name holds a banned word stays allowed."""
    return re.sub(r"\]\([^)]*\)", "]", text)


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
    "docs/design/epic-28-tree-entry-point.md",
    "docs/design/epic-29-theme-report-export.md",
    "docs/design/epic-30-plain-python-notebook.md",
    "docs/design/epic-32-exploration-and-confirmation.md",
    *(str(p.relative_to(REPO_ROOT)) for p in _new_format_adrs()),
]


# Epic 29 removed the old report. The DesignDocs of closed Epics are frozen, so their
# links into it stay as history; no living document may link there.
REMOVED_BY_EPIC_29 = (
    "skills/analysis-report/",
    "skills/report-upload/",
    "skills/_shared/report_check.py",
)
FROZEN_DESIGN_DOCS = {
    "docs/design/epic-12-decision-ready-report.md",
    "docs/design/epic-13-report-source-text.md",
    "docs/design/epic-14-report-template-gaps.md",
}


def _is_removed_history(rel: str, target: Path) -> bool:
    inside = target.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    return rel in FROZEN_DESIGN_DOCS and inside.startswith(REMOVED_BY_EPIC_29)


@pytest.mark.parametrize("rel", LIVING_DOCS)
def test_relative_links_resolve(rel: str) -> None:
    base = (REPO_ROOT / rel).parent
    dead = [
        target
        for target in _LINK.findall(_read(rel))
        if not target.startswith(("http://", "https://", "mailto:", "#"))
        and not (path := base / target.split("#", 1)[0]).exists()
        and not _is_removed_history(rel, path)
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


class TestEpicBranchTrial:
    """#217 retrospective: trying an Epic branch's plugin in another project is written down."""

    HEADING = "### Trying an Epic branch in another project"

    def _trial(self) -> str:
        return unwrap(section(_read("CONTRIBUTING.md"), self.HEADING))

    def test_marketplace_and_plugin_are_both_added_in_the_local_scope(self) -> None:
        """Editing settings.local.json alone did not load the plugin in Epic 32."""
        trial = self._trial()
        assert "claude plugin marketplace add" in trial
        assert (
            "claude plugin install insight-blueprint@insight-blueprint-epic<N> --scope local"
            in trial
        )

    def test_the_released_plugin_is_disabled_while_trying(self) -> None:
        trial = self._trial()
        assert "enabledPlugins" in trial
        assert "insight-blueprint@insight-blueprint-marketplace" in trial

    def test_loading_is_checked_by_the_bin_path_not_the_skill_list(self) -> None:
        """Every skill sets disable-model-invocation, so the skill list never shows them."""
        trial = self._trial()
        assert "which design_io" in trial
        assert "disable-model-invocation: true" in trial

    def test_every_step_of_the_setup_is_undone(self) -> None:
        raw = section(_read("CONTRIBUTING.md"), self.HEADING)
        undo = unwrap(section(raw, "#### Undo"))
        assert "claude plugin uninstall" in undo
        assert "claude plugin marketplace remove insight-blueprint-epic<N>" in undo
        assert "~/.claude/plugins/cache/insight-blueprint-epic<N>" in undo


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
        # Epic 29 (ADR-0040): the report is exported, so the upload is /tree-upload alone.
        assert rows["アップロード"][words.CODE_NAME] == "`/tree-upload`"
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

    def test_readme_workflow_shows_the_export(self) -> None:
        # Epic 29 (ADR-0040): /report-export replaced /report-upload.
        assert "/report-export" in words.section(
            _read("README.md"), "Analysis Workflow"
        )

    def test_prd_functional_requirements_carry_the_report_and_the_export(self) -> None:
        requirements = section(_read("docs/PRD.md"), "### 機能要件")
        assert "レポート" in requirements
        assert "export" in requirements

    def test_ubiquitous_language_has_the_terms_of_epic_12(self) -> None:
        terms = {
            r[words.TERM]
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        added = {"決定の文脈", "効果量", "信頼区間", "標本サイズ", "アップロード"}
        assert added - terms == set()

    def test_ubiquitous_language_has_the_verdict_terms_of_epic_33(self) -> None:
        """Story 33.1 (ADR-0052 の10): the words of the lines, the judgment and the rows."""
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        added = {
            "支持の線": "support_line",
            "棄却の線": "reject_line",
            "結論しない範囲": None,
            "指標の判定": "judgment",
            "値の区間": "interval",
            "群の行": "groups",
        }
        assert set(added) - set(rows) == set()
        for term, code_name in added.items():
            assert "adr/0052-" in rows[term]["初出"], term
            if code_name:
                assert f"`{code_name}`" in rows[term][words.CODE_NAME], term

    def test_a_confidence_interval_is_one_kind_of_interval(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "値の区間の種類の1つ" in rows["信頼区間"][words.DEFINITION]
        assert "`confidence_interval`" in rows["信頼区間"][words.DEFINITION]
        assert "adr/0052-" in rows["信頼区間"]["初出"]

    def test_the_verdict_holds_the_judgment_apart_from_the_pass(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        definition = rows["verdict"][words.DEFINITION]
        assert "支持の線・棄却の線・指標の判定" in definition
        assert "adr/0052-" in rows["verdict"]["初出"]

    def test_ubiquitous_language_has_the_review_terms_of_epic_33(self) -> None:
        """Story 33.5 (ADR-0053, ADR-0054): the mark, and the review of the result."""
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        mark = rows["分析の印"]
        assert "`analysis_started_at`" in mark[words.CODE_NAME]
        assert "adr/0053-" in mark["初出"]
        assert "notebook・verdict・図" in rows["review"][words.DEFINITION]
        assert "adr/0054-" in rows["review"]["初出"]
        for target in ("`notebook`", "`verdict`", "`figures`"):
            assert target in rows["review コメント"][words.DEFINITION]
        batch = rows["review batch"]
        assert "`after_analysis_started`" in batch[words.CODE_NAME]
        assert "分析を始めた後" in batch[words.DEFINITION]
        assert "分析の印" in rows["検証仮説"][words.DEFINITION]
        assert "分析の印" in rows["分析の意図"][words.DEFINITION]
        assert "adr/0053-" in rows["分析の意図"]["初出"]

    def test_keep_gate_covers_the_external_send(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "外部へ送る" in rows["KEEP ゲート"][words.DEFINITION]
        assert "adr/0016-" in rows["KEEP ゲート"]["初出"]

    def test_architecture_workflow_sequence_includes_the_export(self) -> None:
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        assert "/report-export" in sequence
        assert "Claude Docs" in sequence

    def test_architecture_autopilot_sequence_only_names_the_export(self) -> None:
        # Epic 29 (ADR-0040): the driver names /report-export and never starts it.
        sequence = section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        assert "/report-export" in sequence
        assert "Claude Docs" not in sequence

    def test_autopilot_sequence_asks_about_the_upload_once_from_the_skill(self) -> None:
        sequence = section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        asks = [
            line.strip()
            for line in sequence.splitlines()
            if "【KEEP】" in line and ("送る" in line or "アップロード" in line)
        ]
        # Epic 29 removed /report-upload; the send left in the walk is /tree-upload's.
        assert [line.split(":")[0] for line in asks] == ["TU->>U"], asks

    def test_architecture_epic_mapping_covers_every_roadmap_epic(self) -> None:
        roadmap = _first_cells(words.section(_read("docs/PRD.md"), "ロードマップ"))
        mapped = _first_cells(
            words.section(_read("docs/ARCHITECTURE.md"), "Epic マッピング")
        )
        assert [epic for epic in roadmap if epic not in mapped] == []


# The DesignDoc of each Epic since 28, with the ADRs its first edition cites.
FIRST_EDITIONS = {
    "docs/design/epic-28-tree-entry-point.md": ("0036", "0037"),
    "docs/design/epic-29-theme-report-export.md": ("0039", "0040"),
    "docs/design/epic-30-plain-python-notebook.md": ("0045", "0046"),
    "docs/design/epic-32-exploration-and-confirmation.md": (
        "0048",
        "0049",
        "0050",
        "0051",
    ),
    "docs/design/epic-33-verdict-on-record.md": ("0052", "0053", "0054"),
}


@pytest.mark.parametrize("doc", sorted(FIRST_EDITIONS))
class TestDesignDocFirstEdition:
    """WORKFLOW §4: the DesignDoc has what its first edition needs before any Story starts."""

    FIRST_EDITION_DIAGRAMS = {
        "Architecture": "flowchart",
        "Domain Model": "classDiagram",
        "Sequence Diagram": "sequenceDiagram",
    }

    @staticmethod
    def _story_rows(doc: str) -> list[list[str]]:
        rows = table_rows(section(_read(doc), "## Stories"))[2:]
        assert rows, "the Stories table is empty"
        return rows

    @pytest.mark.parametrize("title", sorted(FIRST_EDITION_DIAGRAMS))
    def test_first_edition_diagram_is_drawn_in_mermaid(
        self, doc: str, title: str
    ) -> None:
        body = section(_read(doc), f"## {title}")
        assert re.search(
            rf"```mermaid\s*\n{self.FIRST_EDITION_DIAGRAMS[title]}\b", body
        ), title

    def test_every_story_handles_at_most_five_criteria(self, doc: str) -> None:
        for story, _user_story, criteria, *_ in self._story_rows(doc):
            assert len(re.findall(r"AC \d+", criteria)) <= 5, story

    def test_every_user_story_is_handled_by_a_story(self, doc: str) -> None:
        user_stories = re.findall(r"^### (US-\d+):", _read(doc), flags=re.M)
        handled = {
            us
            for _story, cell, *_ in self._story_rows(doc)
            for us in re.findall(r"US-\d+", cell)
        }
        assert user_stories
        assert [us for us in user_stories if us not in handled] == []

    def test_cross_epic_decisions_are_linked(self, doc: str) -> None:
        decisions = section(_read(doc), "## Decisions")
        missing = [
            adr for adr in FIRST_EDITIONS[doc] if f"../adr/{adr}-" not in decisions
        ]
        assert missing == []


class TestTreeEntryPointDocs:
    """Epic 28, first edition: what only this Epic's terms carry."""

    def test_design_note_is_a_term_from_its_adr(self) -> None:
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "adr/0036-" in rows["分析ノート"]["初出"]
        # 「ノートブック」 is the avoided word for notebook; the note must not be read as one.
        assert "notebook" in rows["分析ノート"][words.DEFINITION]


class TestThemeReportDocs:
    """Epic 29, first edition: what only this Epic's terms carry."""

    def test_the_terms_follow_the_removal_of_the_old_report(self) -> None:
        """US-5 AC 4: the report is the theme's, and the report check is no longer a term."""
        rows = {
            r[words.TERM]: r
            for r in words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        }
        assert "レポートの検査" not in rows
        assert "`tree_io report`" in rows["レポート"][words.CODE_NAME]
        assert "テーマ" in rows["レポート"][words.DEFINITION]
        assert "レポート" not in rows["違反"][words.DEFINITION]
        assert "検査" not in rows["データ由来の文"][words.DEFINITION]


class TestPlainPythonNotebookDocs:
    """Epic 30, first edition: what only this Epic's DesignDoc carries."""

    def test_the_core_value_revision_is_proposed(self) -> None:
        # The PRD itself is revised by a Story; the first edition carries the wording.
        scope = section(
            _read("docs/design/epic-30-plain-python-notebook.md"), "## Scope"
        )
        assert "notebook 契約 & lineage" in scope


class TestExplorationAndConfirmationDocs:
    """Epic 32, first edition: what only this Epic's DesignDoc carries."""

    def test_the_state_of_a_design_is_drawn(self) -> None:
        # A design ends differently by its intent, so the first edition draws the states.
        model = section(
            _read("docs/design/epic-32-exploration-and-confirmation.md"),
            "## Domain Model",
        )
        assert re.search(r"```mermaid\s*\nstateDiagram-v2\b", model)


class TestCanonicalDocsPointAtPlainPythonNotebook:
    """Epic 30 US-4 and US-3 AC 3: the canonical docs describe the `# %%` notebook, not marimo."""

    # ADR-0045 replaced the run line of 0006 and the cell form of 0036;
    # ADR-0046 replaced what the default allowlist of 0021 and 0027 holds.
    AMENDED_ADRS = {
        "0006": "ADR-0045",
        "0021": "ADR-0046",
        "0027": "ADR-0046",
        "0036": "ADR-0045",
    }

    @staticmethod
    def _term(name: str) -> dict[str, str]:
        rows = words.terms_rows(_read("docs/UBIQUITOUS_LANGUAGE.md"))
        return next(row for row in rows if row[words.TERM] == name)

    def test_prd_core_value_is_the_notebook_contract(self) -> None:
        core = words.section(_read("docs/PRD.md"), "コアバリュー（温存すべき核）")
        assert "notebook 契約 & lineage" in core
        assert "marimo" not in core

    def test_notebook_term_is_cut_into_percent_cells(self) -> None:
        definition = self._term("notebook")["定義"]
        assert "`# %%" in definition
        assert "marimo" not in definition

    def test_data_load_cell_term_is_told_apart_by_its_name(self) -> None:
        definition = self._term("データ取得の cell")["定義"]
        assert definition.startswith("`data_load` という名前の cell")
        assert "接続情報の値はこの cell にだけ書く" in definition

    def test_cell_is_a_term(self) -> None:
        assert "`# %%" in self._term("cell")["定義"]

    def test_architecture_outside_the_epic_mapping_has_no_marimo(self) -> None:
        text = _read("docs/ARCHITECTURE.md")
        body = text.replace(section(text, "## Epic マッピング"), "")
        assert "marimo" not in _without_link_targets(body)
        assert "_flat.py" not in body

    def test_architecture_maps_epic_30(self) -> None:
        mapping = section(_read("docs/ARCHITECTURE.md"), "## Epic マッピング")
        assert re.search(r"^\| Epic 30 \|", mapping, re.MULTILINE)

    @pytest.mark.parametrize("path", ["README.md", "CLAUDE.md"])
    def test_entry_docs_do_not_mention_marimo(self, path: str) -> None:
        assert "marimo" not in _without_link_targets(_read(path))

    @pytest.mark.parametrize("adr", sorted(AMENDED_ADRS))
    def test_adr_index_status_names_the_amending_adr(self, adr: str) -> None:
        row = next(
            line
            for line in _read("docs/adr/README.md").splitlines()
            if line.startswith(f"| [{adr}](")
        )
        status = row.strip("|").split("|")[-1]
        assert self.AMENDED_ADRS[adr] in status, adr

    def test_changelog_tells_how_to_run_an_old_notebook_by_hand(self) -> None:
        release = changelog_entry(_read("CHANGELOG.md"), "marimo: marimo")
        assert "marimo: marimo" in release
        assert "--with marimo" in release
        # The other half of US-3 AC 3, written by Story 30.2.
        assert "running `/analysis-notebook` again" in release


class TestYomiyasuWords:
    """WORKFLOW §8: .yomiyasu-words/ is exported from UBIQUITOUS_LANGUAGE, never edited by hand."""

    def test_word_lists_match_the_ubiquitous_language(self) -> None:
        for name, content in words.render(_read("docs/UBIQUITOUS_LANGUAGE.md")).items():
            assert _read(f".yomiyasu-words/{name}") == content, (
                f"{name} is stale: run uv run python scripts/export_yomiyasu_words.py"
            )

    @staticmethod
    def _glossary(*rows: str) -> str:
        header = "| 用語 | コード上の名前 | 定義 | 使わない言い換え | 初出 |\n|---|---|---|---|---|\n"
        return "## Terms\n\n" + header + "\n".join(rows) + "\n"

    def test_a_qualified_variant_becomes_a_pattern_and_not_a_flag(self) -> None:
        # A variant wrong only in some contexts cannot be a flag.txt word, which matches
        # everywhere; a pattern can skip the terms that contain it.
        out = words.render(
            self._glossary(
                "| 検証仮説 | — | d | 仮説（分析設計の項目を指すとき） | x |",
                "| 仮説の背景 | — | d | — | x |",
            )
        )
        assert "仮説\t" not in out["flag.txt"]
        assert (
            "仮説（分析設計の項目を指すとき）は検証仮説\t(?<!検証)仮説(?!の背景)\n"
            in out["flag-patterns.txt"]
        )

    def test_a_pattern_skips_every_term_that_ends_with_the_variant(self) -> None:
        out = words.render(
            self._glossary(
                "| 探索の問い | — | d | 問い（分析設計の項目を指すとき） | x |",
                "| 根の問い | — | d | — | x |",
                "| 未解決の問い | — | d | — | x |",
            )
        )
        assert "\t(?<!探索の)(?<!根の)(?<!未解決の)問い\n" in out["flag-patterns.txt"]

    def test_a_pattern_word_is_not_allowed(self) -> None:
        # yomiyasu drops a pattern's hit when the matched text is in allow.txt, so a word
        # in both lists is never flagged.
        out = words.render(
            self._glossary(
                "| 仮説 | — | d | — | x |",
                "| 検証仮説 | — | d | 仮説（分析設計の項目を指すとき） | x |",
            )
        )
        assert "仮説" not in out["allow.txt"].splitlines()
        assert "検証仮説" in out["allow.txt"].splitlines()

    @staticmethod
    def _english_pattern() -> re.Pattern[str]:
        out = words.render(
            TestYomiyasuWords._glossary(
                "| 分析設計 | — | d | hypothesis（分析設計を指すとき） | x |"
            )
        )
        return re.compile(out["flag-patterns.txt"].splitlines()[-1].split("\t")[1])

    @pytest.mark.parametrize(
        "text", ["the hypothesis is", "このhypothesisは", "hypothesis。"]
    )
    def test_an_english_word_is_matched_next_to_japanese(self, text: str) -> None:
        # Python re counts kana and kanji as word characters, so \b finds no edge there.
        assert self._english_pattern().search(text), text

    @pytest.mark.parametrize(
        "text", ["hypothesis_statement", "hypotheses", "xhypothesis"]
    )
    def test_an_english_word_is_not_matched_inside_another(self, text: str) -> None:
        assert not self._english_pattern().search(text), text

    def test_a_variant_without_a_word_is_refused(self) -> None:
        # A pattern with no literal character stops every yomiyasu run with exit code 2.
        with pytest.raises(ValueError, match="no word"):
            words.render(self._glossary("| 分析設計 | — | d | （…のとき） | x |"))

    def test_every_pattern_fits_the_limits_of_yomiyasu(self) -> None:
        # yomiyasu stops with exit code 2 on a name over 40 characters or a regex over 200.
        lines = words.render(_read("docs/UBIQUITOUS_LANGUAGE.md"))["flag-patterns.txt"]
        patterns = [line.split("\t") for line in lines.splitlines()[1:]]
        assert patterns
        for name, regex in patterns:
            assert len(name) <= 40, name
            assert len(regex) <= 200, regex


class TestPluginVariables:
    """The host fills in plugin variables in skill text, not in the Bash tool's environment."""

    def test_architecture_path_resolution_cites_the_adr(self) -> None:
        paths = section(_read("docs/ARCHITECTURE.md"), "### パス解決機構")
        assert "Bash ツールの環境" in paths
        assert "adr/0017-" in paths

    def test_adr_0006_stays_frozen(self) -> None:
        assert "0017" not in _read("docs/adr/0006-plugin-execution-model.md")


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
            "主題",
            "到達点",
            "主題の版",
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
            "主題の版": "RootRevision",
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
            "主題",
            "最初に調べる論点",
            "ツリーの決定",
            "主題の版",
        ):
            assert any(gate in line for line in keeps), gate

    def test_architecture_autopilot_writes_no_report(self) -> None:
        """Epic 29 US-5 AC 2: the walk writes no report; the decision shows the tree's HTML."""
        sequence = section(_read("docs/ARCHITECTURE.md"), self.AUTOPILOT)
        assert "/analysis-report" not in sequence
        assert "reports/" not in sequence
        assert "論点ツリーの HTML のパスを示し" in sequence

    def test_architecture_invocation_model_lists_the_gates_of_the_walk(self) -> None:
        model = section(_read("docs/ARCHITECTURE.md"), "### Skill invocation model")
        assert "adr/0026-analysis-auto-walks-the-question-tree.md" in model
        assert "ツリーの決定" in model
        assert "レポートの生成 /" not in model

    def test_architecture_workflow_names_the_autopilot_as_the_entry(self) -> None:
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        assert "入口" in sequence
        assert "巡回" in sequence
        # Epic 29: the report is the theme's, so the export follows the theme reflection.
        export = sequence.index("U->>CC: /report-export")
        assert export > sequence.index("/analysis-reflection {theme_id}")

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


class TestDesignDocFirstDraftChecks:
    """FLOW-0005: the first draft is checked as a whole, then shown as a mock-up, before approval."""

    @pytest.mark.parametrize(
        "rel",
        ["docs/WORKFLOW.md", ".claude/rules/design-doc-template.md"],
    )
    def test_the_first_draft_steps_name_both_checks(self, rel: str) -> None:
        text = _read(rel)
        body = section(text, "## 4.") if rel == "docs/WORKFLOW.md" else text
        assert "全体の整合" in body
        assert "見本" in body
        assert "FLOW-0005" in body
        assert "省いたら" in body

    def test_the_lifecycle_diagram_puts_the_checks_between_draft_and_split(
        self,
    ) -> None:
        lifecycle = re.search(
            r"```mermaid\s*\nflowchart LR\n(.*?)```",
            section(_read("docs/WORKFLOW.md"), "## 4."),
            re.DOTALL,
        )
        assert lifecycle is not None
        edges = lifecycle.group(1)
        checks = re.search(r'(\w+)\["全体の整合 / 見本<br/>→ 人間の承認"\]', edges)
        assert checks is not None
        node = checks.group(1)
        # The draft leads to the checks and only the checks lead to the split,
        # so the diagram cannot show a split that skips the human's approval.
        assert re.search(rf"\bB --> {node}\b", edges)
        assert re.search(rf'\b{node} --> C\["Story 分割', edges)
        assert not re.search(r"\bB --> C\b", edges)

    def test_the_template_timeline_shows_how_to_record_a_skipped_mockup(self) -> None:
        timeline = section(
            _read(".claude/rules/design-doc-template.md"), "## Story Timeline"
        )
        assert "初版: 見本を省いた（" in timeline


class TestPmSessionFlow:
    """FLOW-0006〜0008: the PM session, the Story done criteria and the narrowing rule."""

    def test_the_pm_session_skill_and_its_board_are_kept(self) -> None:
        skill = REPO_ROOT / ".claude/skills/pm-session"
        assert (skill / "SKILL.md").is_file()
        assert (skill / "board.html").is_file()
        assert "FLOW-0006" in (skill / "SKILL.md").read_text(encoding="utf-8")

    def test_claude_md_points_to_the_pm_session_skill(self) -> None:
        body = section(_read("CLAUDE.md"), "## 4.")
        assert ".claude/skills/pm-session/SKILL.md" in body
        assert "FLOW-0006" in body

    def test_a_story_is_done_with_a_release_note_and_a_bug_review(self) -> None:
        body = section(_read("docs/WORKFLOW.md"), "## 4.")
        assert "FLOW-0007" in body
        assert "[Unreleased]" in body
        assert "バグ・セキュリティの観点のレビュー" in body

    def test_narrowing_what_worked_is_asked_to_the_human(self) -> None:
        body = section(_read("docs/WORKFLOW.md"), "## 6.")
        assert "FLOW-0008" in body
        assert "失敗に変わる" in body


class TestRetrospectiveFlow:
    """FLOW-0009・0010: the order of first-draft decisions and the retrospective."""

    FLOWS = (
        "0009-designdoc-decisions-scope-first.md",
        "0010-retrospective-after-epic.md",
    )

    @pytest.mark.parametrize("name", FLOWS)
    def test_the_flow_copy_is_kept_and_indexed(self, name: str) -> None:
        assert (REPO_ROOT / "docs/adr/flow" / name).is_file()
        assert f"]({name})" in _read("docs/adr/flow/README.md")

    def test_first_draft_decisions_ask_scope_before_content(self) -> None:
        body = unwrap(section(_read("docs/WORKFLOW.md"), "## 4."))
        assert "FLOW-0009" in body
        assert "成果物の単位と範囲を決める判断" in body
        assert "案ごとの見本を見比べてもらう" in body

    def test_an_epic_ends_with_a_retrospective(self) -> None:
        body = unwrap(section(_read("docs/WORKFLOW.md"), "## 4."))
        assert "振り返り<br/>→ 反映の束を人間が選ぶ" in body
        assert "FLOW-0010" in body
        assert "前回の振り返りで反映したことが効いたか" in body
        assert "Epic issue のコメントに残し" in body

    def test_claude_md_names_the_retrospective(self) -> None:
        body = section(_read("CLAUDE.md"), "## 4.")
        assert "振り返りを1回回し" in body
        assert "FLOW-0010" in body

    def test_the_pm_session_skill_runs_the_retrospective(self) -> None:
        skill = REPO_ROOT / ".claude/skills/pm-session/SKILL.md"
        body = section(skill.read_text(encoding="utf-8"), "## 9. 振り返り")
        assert "FLOW-0010" in body
        targets = _LINK.findall(body)
        assert targets
        assert all((skill.parent / t).is_file() for t in targets)

    def test_the_pm_session_skill_starts_waiting_stories_early(self) -> None:
        skill = _read(".claude/skills/pm-session/SKILL.md")
        assert "前提待ちの Story を前もって立てる" in section(skill, "## 5.")


class TestWaveOneNotesAndBriefFlow:
    """FLOW-0011〜0013: wave 1 started early, the shared notes path, rules and helpers in docs."""

    FLOWS = (
        "0011-start-wave-one-before-designdoc-approval.md",
        "0012-shared-notes-in-app-folder-checked-by-path.md",
        "0013-write-rules-reasons-and-helpers-into-designdoc-and-brief.md",
    )

    @pytest.mark.parametrize("name", FLOWS)
    def test_the_flow_copy_is_kept_and_indexed(self, name: str) -> None:
        copy = (REPO_ROOT / "docs/adr/flow" / name).read_text(encoding="utf-8")
        assert copy.startswith(f"# FLOW-{name[:4]}: ")
        assert "ADR-00" not in copy
        assert f"]({name})" in _read("docs/adr/flow/README.md")

    def test_the_pm_session_skill_starts_wave_one_with_the_first_draft(self) -> None:
        skill = _read(".claude/skills/pm-session/SKILL.md")
        assert "波 1 の子を待機の指示で立てておく" in unwrap(section(skill, "## 1."))
        body = unwrap(section(skill, "## 5."))
        assert "波 1 の子を前もって立てる" in body
        assert "FLOW-0011" in body

    def test_the_pm_session_skill_checks_the_shared_notes_path(self) -> None:
        skill = _read(".claude/skills/pm-session/SKILL.md")
        assert "`notes_dir`" in section(skill, "## 2.")
        assert "Shared notes folder" in section(skill, "## 4.")
        body = unwrap(section(skill, "## 5."))
        assert "共有ノートの置き場を確かめる" in body
        assert "FLOW-0012" in body

    def test_the_brief_names_the_existing_helpers(self) -> None:
        body = unwrap(section(_read(".claude/skills/pm-session/SKILL.md"), "## 4."))
        assert "使う既存の helper とテストの道具の場所" in body
        assert "FLOW-0013" in body

    def test_the_pm_session_skill_links_resolve(self) -> None:
        skill = REPO_ROOT / ".claude/skills/pm-session/SKILL.md"
        targets = _LINK.findall(skill.read_text(encoding="utf-8"))
        assert all((skill.parent / t).is_file() for t in targets if "://" not in t)

    def test_the_designdoc_template_asks_for_rules_and_reasons(self) -> None:
        text = _read(".claude/rules/design-doc-template.md")
        stories = unwrap(section(text, "## User Stories"))
        assert "守りたい規則で書く（FLOW-0013）" in stories
        scope = unwrap(section(text, "## Scope"))
        assert "触らない所" in scope
        assert "必ず理由を書く（FLOW-0013）" in scope


class TestExplorationAndConfirmationTerms:
    """Epic 32 US-8: the glossary and the canonical docs tell exploration from confirmation."""

    GLOSSARY = "docs/UBIQUITOUS_LANGUAGE.md"
    # ADR-0048: these definitions must hold for an exploration as well as a confirmation.
    BOTH_FORMS = (
        "分析設計",
        "指標",
        "手法",
        "派生",
        "terminal status",
        "分析の意図",
        "notebook",
        "verdict",
        "reflection",
        "仮説の背景",
    )
    # A bare 仮説 names the design's field only in the old wording; 検証仮説 is the field.
    BARE_HYPOTHESIS = re.compile(r"(?<!検証)仮説")

    def _rows(self) -> dict[str, dict[str, str]]:
        return {r[words.TERM]: r for r in words.terms_rows(_read(self.GLOSSARY))}

    @pytest.mark.parametrize(
        ("term", "code"),
        [
            ("検証仮説", "`hypothesis_statement`"),
            ("探索の問い", "`exploration_question`"),
            ("探索の問いの背景", "`exploration_background`"),
            ("旧形式の探索", "`legacy_exploration`"),
            ("分析設計の形", "`DesignForm`"),
        ],
    )
    def test_the_terms_of_the_two_forms_are_in_the_glossary(
        self, term: str, code: str
    ) -> None:
        assert code in self._rows()[term][words.CODE_NAME]

    def test_a_hypothesis_is_the_answer_put_before_a_question(self) -> None:
        row = self._rows()["仮説"]
        assert "`hypothesize`" in row[words.CODE_NAME]
        assert "hypothesis_statement" not in row[words.CODE_NAME]
        assert "問いに先に置く仮の答え" in row[words.DEFINITION]

    @pytest.mark.parametrize("term", BOTH_FORMS)
    def test_a_shared_definition_does_not_assume_a_hypothesis(self, term: str) -> None:
        definition = self._rows()[term][words.DEFINITION]
        assert not self.BARE_HYPOTHESIS.search(definition), definition

    def test_explored_is_a_terminal_status(self) -> None:
        assert "`explored`" in self._rows()["terminal status"][words.CODE_NAME]

    def test_mixed_cannot_be_created(self) -> None:
        definition = self._rows()["分析の意図"][words.DEFINITION]
        assert "`mixed`" in definition
        assert "新しく作れない" in definition

    def test_the_h_of_a_design_id_is_its_serial_number(self) -> None:
        assert "通し番号の記号" in self._rows()["分析設計"][words.DEFINITION]

    def test_the_context_names_both_forms(self) -> None:
        context = unwrap(words.section(_read(self.GLOSSARY), "Context"))
        assert "探索" in context
        assert "検証仮説" in context
        assert "分析者が仮説を立て" not in context

    @pytest.mark.parametrize(
        ("term", "variant"),
        [
            ("検証仮説", "仮説（分析設計の項目を指すとき）"),
            ("探索の問い", "問い（分析設計の項目を指すとき）"),
        ],
    )
    def test_a_bare_word_for_a_field_is_flagged(self, term: str, variant: str) -> None:
        assert variant in self._rows()[term][words.AVOID].split("、")
        assert f"{variant}は{term}\t" in _read(".yomiyasu-words/flag-patterns.txt")

    def test_prd_vision_tells_the_two_forms_apart(self) -> None:
        vision = unwrap(words.section(_read("docs/PRD.md"), "ビジョン / 解く課題"))
        assert "仮説 → 設計 → 検証 → 結論" not in vision
        assert "探索" in vision
        assert "検証仮説" in vision

    def test_prd_core_value_names_both_fields_of_a_design(self) -> None:
        core = words.section(_read("docs/PRD.md"), "コアバリュー（温存すべき核）")
        line = next(ln for ln in core.splitlines() if "分析設計" in ln)
        assert "探索の問い" in line
        assert "検証仮説" in line

    def test_architecture_validation_has_the_two_checks(self) -> None:
        components = unwrap(
            section(_read("docs/ARCHITECTURE.md"), "## コンポーネントと責務")
        )
        assert "validate_creation" in components
        assert "DesignForm" in components

    def test_architecture_invocation_model_asks_the_intent_first(self) -> None:
        model = unwrap(
            section(_read("docs/ARCHITECTURE.md"), "### Skill invocation model")
        )
        assert "① 分析の意図と、探索の問いか検証仮説" in model

    def test_architecture_workflow_ends_an_exploration_as_explored(self) -> None:
        sequence = section(_read("docs/ARCHITECTURE.md"), "### 分析ワークフロー全体")
        line = next(ln for ln in sequence.splitlines() if "CC->>IO: transition" in ln)
        assert "explored" in line
        assert "supported" in line

    def test_architecture_autopilot_asks_the_intent_at_the_first_beat(self) -> None:
        sequence = section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        first = next(ln for ln in sequence.splitlines() if "【KEEP①】" in ln)
        for word in ("分析の意図", "探索の問い", "検証仮説"):
            assert word in first, word
        second = next(ln for ln in sequence.splitlines() if "【KEEP②】" in ln)
        assert "intent" not in second

    def test_architecture_autopilot_ends_a_design_by_its_form(self) -> None:
        sequence = section(
            _read("docs/ARCHITECTURE.md"), "### guided autopilot（`/analysis-auto`）"
        )
        end = next(
            ln
            for ln in sequence.splitlines()
            if "/analysis-reflection {design_id}" in ln
        )
        # Story 32.7: a refined hypothesis goes into a derived design, not a rewrite.
        for word in ("`explored`", "判定", "派生の分析設計"):
            assert word in end, word
        assert "refine" not in end

    @pytest.mark.parametrize(
        "phrase",
        [
            "探索（旧形式）",
            "design_io update --id <id>",
            "`mixed` can no longer be created",
        ],
    )
    def test_changelog_upgrade_note_tells_how_to_handle_old_designs(
        self, phrase: str
    ) -> None:
        entry = changelog_entry(_read("CHANGELOG.md"), "探索（旧形式）")
        assert phrase in unwrap(section(entry, "### Upgrade note"))


class TestWordsShownToTheAnalyst:
    """Epic 34 US-5 AC 4: the glossary names the subject and copies the words to show."""

    GLOSSARY = "docs/UBIQUITOUS_LANGUAGE.md"
    DESIGN_DOC = "docs/design/epic-34-what-moved-the-answer.md"
    SECTION = "Words shown to the analyst"

    def _rows(self) -> dict[str, dict[str, str]]:
        return {r[words.TERM]: r for r in words.terms_rows(_read(self.GLOSSARY))}

    @pytest.mark.parametrize(
        ("term", "old"), [("主題", "根の問い"), ("主題の版", "根の版")]
    )
    def test_the_old_name_is_a_variant_of_the_subject_and_is_flagged(
        self, term: str, old: str
    ) -> None:
        assert old in self._rows()[term][words.AVOID].split("、")
        assert f"{old}\t{term}" in _read(".yomiyasu-words/flag.txt")

    def test_a_flagged_old_word_suggests_the_word_shown_for_it(self) -> None:
        shown = {
            row[0]: row[1]
            for row in table_rows(words.section(_read(self.GLOSSARY), self.SECTION))[2:]
        }
        for line in _read(".yomiyasu-words/flag.txt").splitlines():
            old, _, suggested = line.partition("\t")
            if old in shown:
                assert suggested == shown[old], line

    def test_the_answer_is_defined_by_the_words_of_its_kinds(self) -> None:
        definition = self._rows()["現時点の答え"][words.DEFINITION]
        for word in (
            "これまでわかっていること",
            "注意すべきこと",
            "まだ決められないこと",
        ):
            assert word in definition
        for value in ("`claim`", "`weakening`", "`undetermined`"):
            assert value in definition

    def test_the_glossary_copies_the_table_of_the_design_doc(self) -> None:
        def rows(markdown: str) -> list[list[str]]:
            return table_rows(markdown)[2:]

        us5 = section(_read(self.DESIGN_DOC), "### US-5:")
        glossary = words.section(_read(self.GLOSSARY), self.SECTION)
        assert rows(glossary) == rows(us5)
        assert rows(glossary)

    def test_prd_requires_the_tree_to_start_from_the_subject(self) -> None:
        requirements = section(_read("docs/PRD.md"), "### 機能要件")
        assert "着手時には、主題、暫定の第一階層" in requirements
        assert "論点ツリーの主題に到達点を持てる" in requirements

    def test_architecture_tells_the_check_of_the_subject_and_its_revisions(
        self,
    ) -> None:
        architecture = unwrap(_read("docs/ARCHITECTURE.md"))
        assert "主題がちょうど1つあること" in architecture
        assert "主題の版が1から1ずつ増えること" in architecture
