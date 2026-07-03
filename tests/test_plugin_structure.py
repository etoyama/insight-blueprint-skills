"""Plugin structure validation tests.

Verifies that the Claude Code Plugin format is correctly configured:
plugin.json, .mcp.json, skills directory, legacy removal, and README.

Test IDs Unit-01 through Unit-10 map to test-design.md specification.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

ALL_SKILLS = [
    "analysis-design",
    "analysis-framing",
    "analysis-auto",
    "analysis-notebook",
    "analysis-journal",
    "analysis-reflection",
    "analysis-review",
    "analysis-revision",
    "catalog-register",
    "knowledge-extract",
    "data-lineage",
]

# ===========================================================================
# Unit-01: plugin.json validation
# ===========================================================================


class TestPluginJson:
    """Unit-01: plugin.json exists and has correct metadata."""

    def test_plugin_json_exists(self) -> None:
        """plugin.json exists under .claude-plugin/."""
        assert (REPO_ROOT / ".claude-plugin" / "plugin.json").is_file()

    def test_plugin_json_name(self) -> None:
        """plugin.json name is 'insight-blueprint'."""
        data = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        assert data["name"] == "insight-blueprint"

    def test_plugin_json_version_matches_pyproject(self) -> None:
        """plugin.json version matches pyproject.toml version."""
        plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        with (REPO_ROOT / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)
        assert plugin["version"] == pyproject["project"]["version"]

    def test_plugin_json_has_required_metadata(self) -> None:
        """plugin.json has description, author, and repository."""
        data = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        assert "description" in data
        assert "author" in data
        assert "repository" in data


# ===========================================================================
# Unit-02: .mcp.json validation
# ===========================================================================


class TestMcpJson:
    """Unit-02: .mcp.json no longer registers the (removed) insight-blueprint server."""

    def test_mcp_json_exists(self) -> None:
        """.mcp.json exists at repo root."""
        assert (REPO_ROOT / ".mcp.json").is_file()

    def test_no_insight_blueprint_server(self) -> None:
        """The MCP server was removed in Epic 4; it must not be registered."""
        data = json.loads((REPO_ROOT / ".mcp.json").read_text())
        assert "insight-blueprint" not in data.get("mcpServers", {})


# ===========================================================================
# Unit-03: Skills directory structure
# ===========================================================================


class TestSkillsDirectory:
    """Unit-03: All 7 skills exist with correct SKILL.md structure."""

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_all_skills_exist(self, skill_name: str) -> None:
        """Each skill has a SKILL.md file."""
        skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"Missing: skills/{skill_name}/SKILL.md"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_md_has_frontmatter(self, skill_name: str) -> None:
        """Each SKILL.md has name and description in frontmatter."""
        content = (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match, f"No frontmatter in skills/{skill_name}/SKILL.md"
        frontmatter = match.group(1)
        assert re.search(r"^name:", frontmatter, re.MULTILINE), (
            f"Missing 'name' in frontmatter of {skill_name}"
        )
        assert re.search(r"^description:", frontmatter, re.MULTILINE), (
            f"Missing 'description' in frontmatter of {skill_name}"
        )

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_md_has_version(self, skill_name: str) -> None:
        """Each SKILL.md has a version field in frontmatter."""
        content = (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match, f"No frontmatter in skills/{skill_name}/SKILL.md"
        frontmatter = match.group(1)
        assert re.search(r"^version:", frontmatter, re.MULTILINE), (
            f"Missing 'version' in frontmatter of {skill_name}"
        )


# ===========================================================================
# Unit-04: Legacy directory removal
# ===========================================================================


class TestLegacyRemoval:
    """Unit-04: Old _skills/ and _rules/ directories are removed."""

    def test_old_skills_dir_removed(self) -> None:
        """src/insight_blueprint/_skills/ does not exist."""
        assert not (REPO_ROOT / "src" / "insight_blueprint" / "_skills").exists()

    def test_old_rules_dir_removed(self) -> None:
        """src/insight_blueprint/_rules/ does not exist."""
        assert not (REPO_ROOT / "src" / "insight_blueprint" / "_rules").exists()


# ===========================================================================
# Unit-06: Rules integration into SKILL.md
# ===========================================================================


class TestRulesIntegration:
    """Unit-06: Rules content is integrated into corresponding SKILL.md."""

    def test_analysis_design_has_workflow_rules(self) -> None:
        """analysis-design/SKILL.md contains 'Workflow Rules' section."""
        content = (REPO_ROOT / "skills" / "analysis-design" / "SKILL.md").read_text()
        assert "## Workflow Rules" in content

    def test_analysis_design_has_yaml_reference(self) -> None:
        """analysis-design/SKILL.md contains 'YAML Format' content."""
        content = (REPO_ROOT / "skills" / "analysis-design" / "SKILL.md").read_text()
        assert "YAML Format" in content

    def test_catalog_register_has_workflow_rules(self) -> None:
        """catalog-register/SKILL.md contains 'Workflow Rules' section."""
        content = (REPO_ROOT / "skills" / "catalog-register" / "SKILL.md").read_text()
        assert "## Workflow Rules" in content


# ===========================================================================
# Unit-08: Test file structure
# ===========================================================================


class TestTestStructure:
    """Unit-08: Test files are properly organized."""

    def test_plugin_structure_test_exists(self) -> None:
        """test_plugin_structure.py exists."""
        assert (REPO_ROOT / "tests" / "test_plugin_structure.py").is_file()

    def test_old_skill_copy_tests_removed(self) -> None:
        """No test file contains _copy_skills_template test code."""
        tests_dir = REPO_ROOT / "tests"
        for test_file in tests_dir.glob("test_*.py"):
            if test_file.name == "test_plugin_structure.py":
                continue
            content = test_file.read_text()
            assert "_copy_skills_template" not in content, (
                f"Legacy test code '_copy_skills_template' found in {test_file.name}"
            )


# ===========================================================================
# Unit-09: data-lineage prerequisites
# ===========================================================================


class TestDataLineagePrerequisites:
    """Unit-09: data-lineage SKILL.md has prerequisites check."""

    def test_data_lineage_has_prerequisites_check(self) -> None:
        """data-lineage/SKILL.md has 'Prerequisites Check' section."""
        content = (REPO_ROOT / "skills" / "data-lineage" / "SKILL.md").read_text()
        assert "Prerequisites Check" in content

    def test_data_lineage_mentions_uv_add(self) -> None:
        """data-lineage/SKILL.md mentions 'uv add insight-blueprint-lineage'."""
        content = (REPO_ROOT / "skills" / "data-lineage" / "SKILL.md").read_text()
        assert "uv add insight-blueprint-lineage" in content


# ===========================================================================
# Unit-10: README content
# ===========================================================================


class TestReadme:
    """Unit-10: README covers plugin install and the optional lineage package."""

    def test_readme_has_plugin_install(self) -> None:
        """README documents the real plugin-install flow (marketplace + install)."""
        content = (REPO_ROOT / "README.md").read_text()
        content_lower = content.lower()
        # Claude Code has no `claude plugin install owner/repo`; installation is
        # `/plugin marketplace add <owner/repo>` then `/plugin install <plugin>@<marketplace>`.
        assert "/plugin marketplace add" in content_lower
        assert "/plugin install" in content_lower

    def test_readme_has_optional_python_package(self) -> None:
        """README mentions the optional Python package (for lineage)."""
        content = (REPO_ROOT / "README.md").read_text()
        content_lower = content.lower()
        assert "optional" in content_lower
        assert (
            "python package" in content_lower
            or "uv add insight-blueprint-lineage" in content
        )

    def test_readme_has_no_mcp_server_framing(self) -> None:
        """Post-E4: README must not describe an MCP server / server launch."""
        content = (REPO_ROOT / "README.md").read_text().lower()
        assert "mcp server" not in content
        assert "uvx insight-blueprint" not in content
