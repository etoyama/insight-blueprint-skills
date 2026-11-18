"""Structure tests for who may read a data source's `connection` (ADR-0018).

`catalog_io get` prints no `connection` unless the caller passes `--with-connection`.
Only `/analysis-notebook` loads data, so it is the only skill that may ask for it.
`/analysis-report` builds a document that leaves the machine, so it must never ask.
"""

from __future__ import annotations

from pathlib import Path

from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill

_SKILLS = Path(__file__).resolve().parents[2] / "skills"
_FLAG = "--with-connection"


def _prose_files() -> list[Path]:
    return sorted(_SKILLS.glob("*/SKILL.md")) + sorted(
        _SKILLS.glob("*/references/*.md")
    )


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

    def test_no_other_skill_runs_get_with_the_flag(self) -> None:
        askers = {
            path.relative_to(_SKILLS).parts[0]
            for path in _prose_files()
            if f"catalog_io get --id {{source_id}} {_FLAG}" in unwrap(path.read_text())
        }
        assert askers == {"analysis-notebook"}

    def test_the_report_never_mentions_the_flag(self) -> None:
        for path in _prose_files():
            if path.relative_to(_SKILLS).parts[0] == "analysis-report":
                assert _FLAG not in path.read_text(), f"{path} must not name {_FLAG}"


class TestCatalogRegisterDescribesTheDefault:
    def test_get_is_no_longer_described_as_the_full_source(self) -> None:
        reference = section(_read_skill("catalog-register"), "## catalog_io Reference")
        purpose = table_row(reference, "`get --id ID`")[1]
        assert "without `connection`" in purpose
        assert _FLAG in purpose
