"""Structure tests for where a data source's `connection` may enter a model's context (Epic 17).

Only /analysis-notebook reads `connection`, through `catalog_io get --with-connection`
(ADR-0018). These tests close the paths around that command: a skill reading the
source YAML itself (US-1), and a design carrying `connection` values in
`methodology.steps` (US-2).
"""

from __future__ import annotations

import re

import pytest

from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _prose_files, _read_skill

# Each one points a reader at the source YAML, which holds the connection. The first
# two are how /analysis-framing used to reach it (issue #102).
_READS_THE_SOURCE_FILES = (
    "`.insight/catalog/*",
    "all of `.insight/`",
    "catalog/sources",
)


class TestFramingReadsSourcesThroughCatalogIo:
    """US-1: /analysis-framing finds data sources without reading `connection`."""

    def test_catalog_exploration_lists_the_sources_with_catalog_io(self) -> None:
        step = unwrap(section(_read_skill("analysis-framing"), "#### 2b: "))
        assert "`catalog_io list`" in step

    def test_cross_search_names_its_directories(self) -> None:
        step = unwrap(section(_read_skill("analysis-framing"), "#### 2d: "))
        assert "`.insight/designs/`" in step
        assert "`.insight/catalog/knowledge/`" in step

    @pytest.mark.parametrize("pattern", _READS_THE_SOURCE_FILES)
    def test_no_skill_but_catalog_register_points_at_the_source_files(
        self, pattern: str
    ) -> None:
        # /catalog-register says where a source is stored; it is the one exception.
        files = _prose_files()
        assert files
        mentions = {
            path.relative_to(SKILLS_DIR).parts[0]
            for path in files
            if pattern in path.read_text()
        }
        allowed = {"catalog-register"}
        assert (
            mentions == allowed if pattern == "catalog/sources" else mentions <= allowed
        )


_REF = "`{source:ID}`"


class TestDesignPointsAtSourcesById:
    """US-2: a design names its data sources by id and never carries `connection` values."""

    def test_code_patterns_name_a_source_by_reference(self) -> None:
        step = unwrap(section(_read_skill("analysis-design"), "### Step 2.6: "))
        assert _REF in step
        assert "an id in `source_ids`" in step
        assert "Never write a path, host, project id or table name" in step

    def test_the_sample_carries_no_one_users_environment(self) -> None:
        step = section(_read_skill("analysis-design"), "### Step 2.6: ")
        assert "lmi-datau-prod" not in step
        assert "lib.accessor" not in step
        assert "FROM {source:" in step

    def test_the_notebook_resolves_the_reference_in_cell_2(self) -> None:
        generate = unwrap(section(_read_skill("analysis-notebook"), "### Step 3: "))
        cell_2 = generate.split("- cell 2 (data_load):", 1)[1].split("- cell 3", 1)[0]
        assert _REF in cell_2
        assert "`connection`" in cell_2
        # A file path goes into Python code, a table into a SQL query: a quoted string
        # in the query would be a value, not a table.
        assert "string literal" in cell_2
        assert "quoted identifier" in cell_2

    def test_the_notebook_contract_states_the_reference(self) -> None:
        contract = unwrap(
            (
                SKILLS_DIR / "analysis-notebook/references/notebook-contract.md"
            ).read_text()
        )
        assert f"Each {_REF} in `methodology.steps`" in contract

    @pytest.mark.parametrize("skill", ["analysis-auto", "analysis-design"])
    def test_the_data_extraction_beat_shows_ids_not_files(self, skill: str) -> None:
        text = unwrap(_read_skill(skill))
        assert "the data source id + " in text
        assert "the file + " not in text


class TestCatalogRegisterKeepsCredentialsOut:
    """US-3 AC 5: /catalog-register never puts a credential in `connection`."""

    def test_building_the_registration_says_connection_holds_no_credential(
        self,
    ) -> None:
        step = unwrap(section(_read_skill("catalog-register"), "### Step 3: "))
        assert "`connection` never holds a credential" in step
        assert "a key ending in `_env`" in step

    def test_the_api_sample_names_the_environment_variable(self) -> None:
        text = _read_skill("catalog-register")
        assert '"api_key_env": "ESTAT_API_KEY"' in text

    def test_the_reference_says_create_and_update_refuse_credential_keys(
        self,
    ) -> None:
        reference = unwrap(
            section(_read_skill("catalog-register"), "## catalog_io Reference")
        )
        assert "refuse a `connection` key that names a credential" in reference
        assert "ADR-0023" in reference

    def test_a_stored_credential_is_fixed_by_hand_and_never_read(self) -> None:
        reference = unwrap(
            section(_read_skill("catalog-register"), "## catalog_io Reference")
        )
        assert "the analyst edits its YAML by hand" in reference
        assert "never read it with `--with-connection`" in reference

    def test_a_password_inside_a_url_is_named_as_unchecked(self) -> None:
        step = unwrap(section(_read_skill("catalog-register"), "### Step 3: "))
        assert "`user:password@`" in step


class TestCatalogRegisterNeverCallsTheApi:
    """Issue #136: the analysis repository's fetch script calls the API, not Claude."""

    def _api_workflow(self) -> str:
        return unwrap(
            section(_read_skill("catalog-register"), "## API Source Workflow")
        )

    def test_no_skill_builds_a_url_with_a_credential_variable(self) -> None:
        files = _prose_files()
        assert files
        builds = [
            path.relative_to(SKILLS_DIR).as_posix()
            for path in files
            if re.search(r"[?&][A-Za-z_]+=\$\{?[A-Z_]", path.read_text())
        ]
        assert builds == []

    def test_the_api_workflow_says_claude_never_calls_the_api(self) -> None:
        workflow = self._api_workflow()
        assert "Claude never calls the API" in workflow
        assert "fetch script" in workflow

    def test_the_api_workflow_reads_a_saved_response_or_a_pasted_sample(
        self,
    ) -> None:
        workflow = self._api_workflow()
        assert "getMetaInfo" not in workflow
        assert "Fetch the response" not in workflow
        assert "paste" in workflow


class TestArchitectureFollowsTheBoundary:
    """ADR-0022 in the canonical architecture: the auto sequence matches the skills."""

    _ARCHITECTURE = SKILLS_DIR.parent / "docs" / "ARCHITECTURE.md"

    def test_the_data_extraction_gate_shows_ids_not_files(self) -> None:
        text = self._ARCHITECTURE.read_text()
        assert "file+columns+filter" not in text
        assert "データソースの id + columns + filter" in text

    def test_auto_framing_reads_the_sources_with_catalog_io_list(self) -> None:
        assert "catalog_io list" in self._ARCHITECTURE.read_text()
