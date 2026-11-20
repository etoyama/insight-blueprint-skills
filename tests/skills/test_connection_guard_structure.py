"""Structure tests for who may read a data source's `connection` (ADR-0018).

`catalog_io get` prints no `connection` unless the caller passes `--with-connection`.
Only `/analysis-notebook` loads data, so it is the only skill that may ask for it.
`/analysis-report` builds a document that leaves the machine, so it must never ask.
"""

from __future__ import annotations

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _prose_files, _read_skill

_FLAG = "--with-connection"


class TestOnlyTheNotebookAsksForTheConnection:
    def test_the_notebook_asks_for_the_connection_when_it_gathers_the_source(
        self,
    ) -> None:
        gather = unwrap(section(_read_skill("analysis-notebook"), "### Step 2: "))
        assert f"catalog_io get --id {{source_id}} {_FLAG}" in gather

    def test_the_notebook_reference_names_the_flag(self) -> None:
        reference = section(
            _read_skill("analysis-notebook"), "## design_io / catalog_io Reference"
        )
        assert table_row(reference, f"`catalog_io get --id SOURCE {_FLAG}`")

    def test_only_the_notebook_and_the_catalog_reference_name_the_flag(self) -> None:
        # Any spelling of the flag counts, so a new skill cannot slip past with
        # another placeholder or with `list`. /catalog-register only documents it.
        mentions = {
            path.relative_to(SKILLS_DIR).parts[0]
            for path in _prose_files()
            if _FLAG in path.read_text()
        }
        assert mentions == {"analysis-notebook", "catalog-register"}

    def test_catalog_register_never_runs_a_command_with_the_flag(self) -> None:
        text = _read_skill("catalog-register")
        reference = section(text, "## catalog_io Reference")
        assert _FLAG not in text.replace(reference, "")


class TestCatalogRegisterDescribesTheDefault:
    def test_get_is_no_longer_described_as_the_full_source(self) -> None:
        reference = section(_read_skill("catalog-register"), "## catalog_io Reference")
        purpose = table_row(reference, "`get --id ID`")[1]
        assert "without `connection`" in purpose
        assert _FLAG in purpose

    def test_the_reference_says_create_and_update_print_no_connection(self) -> None:
        reference = unwrap(
            section(_read_skill("catalog-register"), "## catalog_io Reference")
        )
        assert "`create` and `update` also print the source without `connection`" in (
            reference
        )
