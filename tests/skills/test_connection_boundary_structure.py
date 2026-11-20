"""Structure tests for where a data source's `connection` may enter a model's context (Epic 16).

Only /analysis-notebook reads `connection`, through `catalog_io get --with-connection`
(ADR-0018). These tests close the paths around that command: a skill reading the
source YAML itself (US-1), and a design carrying `connection` values in
`methodology.steps` (US-2).
"""

from __future__ import annotations

from pathlib import Path

from tests.skills._markdown import section, unwrap
from tests.skills.test_skill_structure import SKILLS_DIR, _read_skill

_SOURCES_DIR = "catalog/sources"


def _prose_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md")) + sorted(
        SKILLS_DIR.glob("*/references/*.md")
    )


class TestFramingReadsSourcesThroughCatalogIo:
    """US-1: /analysis-framing finds data sources without reading `connection`."""

    def test_catalog_exploration_lists_the_sources_with_catalog_io(self) -> None:
        step = unwrap(section(_read_skill("analysis-framing"), "#### 2b: "))
        assert "`catalog_io list`" in step
        assert "Glob" not in step
        assert "Read " not in step

    def test_cross_search_names_its_directories_instead_of_all_of_insight(
        self,
    ) -> None:
        step = unwrap(section(_read_skill("analysis-framing"), "#### 2d: "))
        assert "all of `.insight/`" not in step
        assert "`.insight/designs/`" in step
        assert "`.insight/catalog/knowledge/`" in step

    def test_framing_never_globs_the_whole_catalog(self) -> None:
        assert "`.insight/catalog/*" not in _read_skill("analysis-framing")

    def test_only_catalog_register_names_the_source_files(self) -> None:
        # /catalog-register says where a source is stored; no other skill may point
        # a reader at those files, since the YAML holds the connection.
        mentions = {
            path.relative_to(SKILLS_DIR).parts[0]
            for path in _prose_files()
            if _SOURCES_DIR in path.read_text()
        }
        assert mentions == {"catalog-register"}
