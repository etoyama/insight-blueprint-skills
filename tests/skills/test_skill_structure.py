"""Structural validation tests for SKILL.md files.

Validates that all 7 bundled skills (analysis-framing, analysis-design,
analysis-journal, analysis-reflection, analysis-revision,
catalog-register, data-lineage) have correct structure, chaining tables,
and inter-skill consistency.

Test groups:
  Unit-01: TestSkillStructure — required sections, format, versions
  Unit-02: TestForwardingGraph — forwarding edge consistency
  Unit-03: TestFramingBrief — Framing Brief output format
  Unit-04: TestDesignFramingBriefIntegration — analysis-design Step 1.5
  Unit-05: TestExternalSkillConnectivity — external skill handling
  Unit-06: TestSkillDeployment — deployment verification
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

ALL_SKILLS: list[str] = [
    "analysis-framing",
    "analysis-design",
    "analysis-journal",
    "analysis-reflection",
    "analysis-review",
    "analysis-revision",
    "catalog-register",
    "knowledge-extract",
    "data-lineage",
]

REQUIRED_SECTIONS: list[str] = [
    "When to Use",
    "When NOT to Use",
    "Workflow",
    "Chaining",
    "Language Rules",
]

# External skill name that should be excluded from bidirectional checks
_EXTERNAL_SKILL = "development-partner"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _read_skill(skill_name: str) -> str:
    """Read the SKILL.md content for a given skill name."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter between ``---`` delimiters and return as dict.

    Returns an empty dict if no valid frontmatter is found.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def split_sections(text: str, level: int = 2) -> dict[str, str]:
    """Split Markdown by heading *level* and return ``{heading_text: content}``.

    The heading prefix (e.g. ``## ``) is stripped from keys.
    Content between headings includes everything up to the next same-level heading.
    """
    prefix = "#" * level
    # Pattern: start of line, exact heading level, space, then heading text
    pattern = re.compile(rf"^{re.escape(prefix)}\s+(.+?)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = text[start:end]
    return sections


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (``` ... ```) from text."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def parse_chaining_table(section_text: str) -> list[dict[str, str]]:
    """Parse a Chaining section and extract ``| From | To | When |`` rows.

    Returns a list of dicts with keys ``from``, ``to``, ``when``.
    Content inside fenced code blocks is excluded before parsing.
    """
    cleaned = _strip_code_blocks(section_text)
    rows: list[dict[str, str]] = []
    # Match table rows: | value | value | value |
    # Skip header row and separator row
    in_table = False
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in stripped.split("|")]
        # Split by | gives empty first and last elements
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        # Detect header row
        if cells[0].lower() == "from" and cells[1].lower() == "to":
            in_table = True
            continue
        # Detect separator row (e.g. |------|-----|------|)
        if all(re.match(r"^[-:]+$", c) for c in cells):
            continue
        if in_table:
            rows.append(
                {
                    "from": cells[0],
                    "to": cells[1],
                    "when": cells[2] if len(cells) > 2 else "",
                }
            )
    return rows


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    - Strip leading/trailing whitespace
    - Normalize full-width spaces to half-width
    - Strip arrow variants (``->`` and unicode ``→``)
    - Strip leading slashes from skill names
    - Exclude content inside fenced code blocks
    """
    result = _strip_code_blocks(text)
    # Full-width space -> half-width
    result = result.replace("\u3000", " ")
    # Arrow variants
    result = result.replace("→", "").replace("->", "")
    # Leading slashes on skill names
    result = re.sub(r"(?<![a-zA-Z])/(?=[a-zA-Z])", "", result)
    # Collapse whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _normalize_skill_name(name: str) -> str:
    """Normalize a skill name by stripping leading ``/``, arrows, and whitespace."""
    result = name.strip()
    # Strip arrow variants that appear in "To" column
    result = result.replace("→", "").replace("->", "")
    result = result.strip().lstrip("/")
    return result


def _extract_chaining_edges(skill_name: str) -> list[tuple[str, str]]:
    """Extract all (from_skill, to_skill) edges from a skill's Chaining table."""
    text = _read_skill(skill_name)
    sections = split_sections(text, level=2)
    chaining_content = sections.get("Chaining", "")
    rows = parse_chaining_table(chaining_content)
    edges: list[tuple[str, str]] = []
    for row in rows:
        from_name = _normalize_skill_name(row["from"].replace("*", "").strip())
        to_name = _normalize_skill_name(row["to"].replace("*", "").strip())
        edges.append((from_name, to_name))
    return edges


# =========================================================================
# Unit-01: TestSkillStructure
# =========================================================================


class TestSkillStructure:
    """Validate structural correctness of all 7 SKILL.md files."""

    def test_all_skills_have_required_sections(self) -> None:
        """All 6 skills must have frontmatter + 5 required sections."""
        for skill_name in ALL_SKILLS:
            text = _read_skill(skill_name)

            # Frontmatter check
            fm = parse_frontmatter(text)
            assert fm, f"{skill_name}: missing or empty frontmatter"

            # Section checks
            sections = split_sections(text, level=2)
            for required in REQUIRED_SECTIONS:
                assert required in sections, (
                    f"{skill_name}: missing required section '## {required}'"
                )

    def test_chaining_table_format(self) -> None:
        """All Chaining sections must have ``| From | To | When |`` header."""
        for skill_name in ALL_SKILLS:
            text = _read_skill(skill_name)
            sections = split_sections(text, level=2)
            chaining = sections.get("Chaining", "")
            assert chaining, f"{skill_name}: Chaining section is empty"

            # Check for table header
            cleaned = _strip_code_blocks(chaining)
            header_pattern = re.compile(
                r"^\|\s*From\s*\|\s*To\s*\|\s*When\s*\|", re.MULTILINE
            )
            assert header_pattern.search(cleaned), (
                f"{skill_name}: Chaining section missing '| From | To | When |' header"
            )

    def test_analysis_framing_version(self) -> None:
        """analysis-framing must have version == '1.0.0'."""
        text = _read_skill("analysis-framing")
        fm = parse_frontmatter(text)
        assert fm.get("version") == "1.0.0", (
            f"analysis-framing version should be '1.0.0', got {fm.get('version')!r}"
        )

    def test_analysis_framing_has_five_workflow_steps(self) -> None:
        """analysis-framing must have Step 1 through Step 5 in Workflow."""
        text = _read_skill("analysis-framing")
        for step_num in range(1, 6):
            assert re.search(rf"###\s+Step\s+{step_num}", text, re.MULTILINE), (
                f"analysis-framing missing '### Step {step_num}' in Workflow"
            )

    def test_existing_skills_version_bump(self) -> None:
        """Existing skills have correct versions per their release history."""
        # Expected versions per skill:
        # - analysis-framing: 1.0.0 (initial, tested separately)
        # - analysis-revision: 1.0.0 (initial, added in Issue #44)
        # - analysis-design, catalog-register: 1.2.0 (rules integrated into SKILL.md)
        # - analysis-journal, analysis-reflection, data-lineage: 1.1.0
        expected_versions: dict[str, str] = {
            "analysis-design": "1.2.0",
            "catalog-register": "1.2.0",
            "analysis-journal": "1.1.0",
            "analysis-reflection": "1.1.0",
            "analysis-revision": "1.0.0",
            "data-lineage": "1.1.0",
        }
        for skill_name, expected in expected_versions.items():
            text = _read_skill(skill_name)
            fm = parse_frontmatter(text)
            assert fm.get("version") == expected, (
                f"{skill_name} version should be '{expected}', got {fm.get('version')!r}"
            )


# =========================================================================
# Unit-02: TestForwardingGraph
# =========================================================================


class TestForwardingGraph:
    """Validate forwarding edges across the 6-skill graph."""

    def test_reflection_to_framing_entry(self) -> None:
        """analysis-reflection Chaining must have -> analysis-framing entry."""
        edges = _extract_chaining_edges("analysis-reflection")
        to_skills = [to for (frm, to) in edges if frm == "analysis-reflection"]
        assert "analysis-framing" in to_skills, (
            "analysis-reflection Chaining missing -> analysis-framing entry"
        )

    def test_design_to_framing_entry(self) -> None:
        """analysis-design Chaining must have -> analysis-framing entry."""
        edges = _extract_chaining_edges("analysis-design")
        to_skills = [to for (frm, to) in edges if frm == "analysis-design"]
        assert "analysis-framing" in to_skills, (
            "analysis-design Chaining missing -> analysis-framing entry"
        )

    def test_catalog_register_return_entries(self) -> None:
        """catalog-register Chaining must have -> analysis-framing AND -> analysis-design."""
        edges = _extract_chaining_edges("catalog-register")
        to_skills = [to for (frm, to) in edges if frm == "catalog-register"]
        assert "analysis-framing" in to_skills, (
            "catalog-register Chaining missing -> analysis-framing entry"
        )
        assert "analysis-design" in to_skills, (
            "catalog-register Chaining missing -> analysis-design entry"
        )

    def test_data_lineage_to_journal_entry(self) -> None:
        """data-lineage Chaining must have -> analysis-journal entry."""
        edges = _extract_chaining_edges("data-lineage")
        to_skills = [to for (frm, to) in edges if frm == "data-lineage"]
        assert "analysis-journal" in to_skills, (
            "data-lineage Chaining missing -> analysis-journal entry"
        )

    def test_bidirectional_consistency(self) -> None:
        """For every edge From->To (excluding external skills), both skills must reference it."""
        all_edges: list[tuple[str, str]] = []
        for skill_name in ALL_SKILLS:
            edges = _extract_chaining_edges(skill_name)
            all_edges.extend(edges)

        # Build sets of edges per skill (what each skill's Chaining table mentions)
        skill_edges: dict[str, set[tuple[str, str]]] = {}
        for skill_name in ALL_SKILLS:
            skill_edges[skill_name] = set(_extract_chaining_edges(skill_name))

        # For each edge, verify both From and To skills contain it
        # (excluding external skill edges)
        bundled_names = set(ALL_SKILLS)
        errors: list[str] = []
        checked: set[tuple[str, str]] = set()

        for frm, to in all_edges:
            if frm == _EXTERNAL_SKILL or to == _EXTERNAL_SKILL:
                continue
            if (frm, to) in checked:
                continue
            checked.add((frm, to))

            # The From skill's Chaining table should contain this edge
            if frm in bundled_names and (frm, to) not in skill_edges.get(frm, set()):
                errors.append(f"{frm} Chaining missing outbound edge -> {to}")

            # The To skill's Chaining table should also reference this edge
            if to in bundled_names and (frm, to) not in skill_edges.get(to, set()):
                errors.append(f"{to} Chaining missing inbound edge {frm} ->")

        assert not errors, "Bidirectional consistency errors:\n" + "\n".join(errors)


# =========================================================================
# Unit-03: TestFramingBrief
# =========================================================================


class TestFramingBrief:
    """Validate the Framing Brief output format in analysis-framing."""

    def test_framing_brief_has_five_sections(self) -> None:
        """analysis-framing Step 5 must contain ## Framing Brief + 5 subsections."""
        text = _read_skill("analysis-framing")
        # Must contain an actual L2 heading (not just substring match)
        assert re.search(r"^##\s+Framing Brief", text, re.MULTILINE), (
            "analysis-framing must contain '## Framing Brief' heading"
        )

        required_subsections = [
            "テーマ",
            "利用可能データ",
            "既存分析",
            "ギャップ",
            "推奨方向",
        ]

        # Look for ### level subsections within the Framing Brief context
        # The Brief template should appear in Step 5
        for sub in required_subsections:
            # Match ### subsection headings within the skill text
            pattern = re.compile(rf"###\s+{re.escape(sub)}", re.MULTILINE)
            assert pattern.search(text), (
                f"analysis-framing missing Framing Brief subsection '### {sub}'"
            )

    def test_framing_brief_recommended_direction_fields(self) -> None:
        """推奨方向 section must contain theme_id, parent_id, analysis_intent, 推奨手法."""
        text = _read_skill("analysis-framing")

        # Find the 推奨方向 section content
        # Look for content after ### 推奨方向
        match = re.search(
            r"###\s+推奨方向\s*\n(.*?)(?=\n###|\n##|\Z)",
            text,
            re.DOTALL,
        )
        assert match, "analysis-framing missing '### 推奨方向' section"
        direction_content = match.group(1)

        required_fields = ["theme_id", "parent_id", "analysis_intent", "推奨手法"]
        for field in required_fields:
            assert field in direction_content, (
                f"analysis-framing 推奨方向 section missing field '{field}'"
            )

    def test_framing_brief_detection_rules_match_output(self) -> None:
        """analysis-design Step 1.5 detection conditions must be satisfiable by analysis-framing output.

        Detection conditions from design.md:
        1. ``## Framing Brief`` heading exists
        2. ``### テーマ`` subsection exists under Framing Brief
        3. ``### 推奨方向`` subsection exists under Framing Brief
        4. ``theme_id:`` exists under 推奨方向

        All four must be present in analysis-framing's Step 5 output template.
        """
        framing_text = _read_skill("analysis-framing")

        # Condition 1: ## Framing Brief heading
        assert re.search(r"^##\s+Framing Brief", framing_text, re.MULTILINE), (
            "analysis-framing output must contain '## Framing Brief' heading"
        )

        # Condition 2: ### テーマ under Framing Brief
        # Find ## Framing Brief, then look for ### テーマ before next ## heading
        brief_match = re.search(
            r"^##\s+Framing Brief\s*\n(.*?)(?=\n##\s[^#]|\Z)",
            framing_text,
            re.MULTILINE | re.DOTALL,
        )
        assert brief_match, "Could not extract Framing Brief section content"
        brief_content = brief_match.group(1)

        assert re.search(r"###\s+テーマ", brief_content), (
            "Framing Brief must contain '### テーマ' subsection"
        )

        # Condition 3: ### 推奨方向 under Framing Brief
        assert re.search(r"###\s+推奨方向", brief_content), (
            "Framing Brief must contain '### 推奨方向' subsection"
        )

        # Condition 4: theme_id: under 推奨方向
        direction_match = re.search(
            r"###\s+推奨方向\s*\n(.*?)(?=\n###|\n##|\Z)",
            brief_content,
            re.DOTALL,
        )
        assert direction_match, "Could not extract 推奨方向 subsection"
        assert "theme_id:" in direction_match.group(1), (
            "推奨方向 must contain 'theme_id:' for detection rule"
        )


# =========================================================================
# Unit-04: TestDesignFramingBriefIntegration
# =========================================================================


class TestDesignFramingBriefIntegration:
    """Validate analysis-design Step 1.5 for Framing Brief integration."""

    def test_design_has_step_1_5(self) -> None:
        """analysis-design must have a ``### Step 1.5`` section."""
        text = _read_skill("analysis-design")
        assert re.search(r"###\s+Step\s+1\.5", text), (
            "analysis-design missing '### Step 1.5' section"
        )

    def test_design_step_1_5_has_mapping_table(self) -> None:
        """Step 1.5 must contain a mapping table."""
        text = _read_skill("analysis-design")
        # Extract Step 1.5 content
        match = re.search(
            r"###\s+Step\s+1\.5.*?\n(.*?)(?=\n###\s|\Z)",
            text,
            re.DOTALL,
        )
        assert match, "Could not extract Step 1.5 content"
        content = match.group(1)
        # A mapping table should have pipe-delimited rows
        assert "|" in content, "Step 1.5 must contain a mapping table (pipe characters)"
        # Should have at least a header and some data rows
        table_rows = [
            line
            for line in content.splitlines()
            if line.strip().startswith("|") and not re.match(r"^\s*\|[-:|\s]+\|$", line)
        ]
        assert len(table_rows) >= 2, (
            "Step 1.5 mapping table must have header + data rows"
        )

    def test_design_step_1_5_maps_methodology(self) -> None:
        """Step 1.5 mapping table must have 推奨手法 -> methodology entry."""
        text = _read_skill("analysis-design")
        match = re.search(
            r"###\s+Step\s+1\.5.*?\n(.*?)(?=\n###\s|\Z)",
            text,
            re.DOTALL,
        )
        assert match, "Could not extract Step 1.5 content"
        content = match.group(1)
        # Look for a row containing both 推奨手法 and methodology
        assert "推奨手法" in content and "methodology" in content, (
            "Step 1.5 mapping table must map 推奨手法 to methodology"
        )

    def test_design_step_1_5_mapping_completeness(self) -> None:
        """Step 1.5 mapping table must include all 5 mandatory fields."""
        text = _read_skill("analysis-design")
        match = re.search(
            r"###\s+Step\s+1\.5.*?\n(.*?)(?=\n###\s|\Z)",
            text,
            re.DOTALL,
        )
        assert match, "Could not extract Step 1.5 content"
        content = match.group(1)

        mandatory_fields = [
            "theme_id",
            "parent_id",
            "analysis_intent",
            "title",
            "methodology",
        ]
        for field in mandatory_fields:
            assert field in content, (
                f"Step 1.5 mapping table missing mandatory field '{field}'"
            )

    def test_design_step_1_5_fallback(self) -> None:
        """Step 1.5 must contain fallback text for when Framing Brief is missing."""
        text = _read_skill("analysis-design")
        match = re.search(
            r"###\s+Step\s+1\.5.*?\n(.*?)(?=\n###\s|\Z)",
            text,
            re.DOTALL,
        )
        assert match, "Could not extract Step 1.5 content"
        content = match.group(1)
        # Fallback should mention proceeding without Brief or normal flow
        normalized = normalize_text(content)
        has_fallback = any(
            keyword in normalized
            for keyword in [
                "fallback",
                "framing brief",
                "step 2",
                "通常フロー",
                "不完全",
                "インタビュー",
            ]
        )
        assert has_fallback, (
            "Step 1.5 must describe fallback behavior when Framing Brief is absent"
        )


# =========================================================================
# Unit-05: TestExternalSkillConnectivity
# =========================================================================


class TestExternalSkillConnectivity:
    """Validate external skill (development-partner) handling."""

    def test_framing_handles_vague_theme_independently(self) -> None:
        """analysis-framing Step 1 must handle vague themes without dev-partner dependency."""
        text = _read_skill("analysis-framing")
        # Step 1 should contain language about presenting candidate directions
        # when the theme is vague, independent of development-partner
        normalized = normalize_text(text)
        # Look for evidence of independent vague theme handling
        has_vague_handling = any(
            keyword in normalized
            for keyword in [
                "候補",
                "candidate",
                "方向",
                "direction",
                "絞り込",
                "narrow",
            ]
        )
        assert has_vague_handling, (
            "analysis-framing must handle vague themes independently "
            "(present candidate directions)"
        )

    def test_framing_chaining_has_optional_dev_partner(self) -> None:
        """analysis-framing Chaining must have dev-partner entry with optional notation."""
        text = _read_skill("analysis-framing")
        sections = split_sections(text, level=2)
        chaining = sections.get("Chaining", "")
        assert chaining, "analysis-framing missing Chaining section"

        # Must contain development-partner reference
        assert "development-partner" in chaining, (
            "analysis-framing Chaining must reference development-partner"
        )

        # Must have optional notation
        has_optional = any(
            marker in chaining
            for marker in ["外部スキル", "存在時のみ", "optional", "*"]
        )
        assert has_optional, (
            "analysis-framing Chaining must mark development-partner as optional "
            "('外部スキル' or '存在時のみ')"
        )

    def test_framing_chaining_has_inbound_dev_partner(self) -> None:
        """analysis-framing Chaining must have development-partner -> analysis-framing entry."""
        text = _read_skill("analysis-framing")
        sections = split_sections(text, level=2)
        chaining = sections.get("Chaining", "")
        rows = parse_chaining_table(chaining)

        inbound = [
            row
            for row in rows
            if _normalize_skill_name(row["from"].replace("*", "").strip())
            == "development-partner"
            and "analysis-framing"
            in _normalize_skill_name(row["to"].replace("*", "").strip())
        ]
        assert inbound, (
            "analysis-framing Chaining must have "
            "development-partner -> analysis-framing inbound entry"
        )


# =========================================================================
# Unit-06: TestSkillDeployment
# =========================================================================


class TestSkillDeployment:
    """Validate that analysis-framing is deployable."""

    def test_analysis_framing_source_exists(self) -> None:
        """Source directory for analysis-framing SKILL.md must exist."""
        path = SKILLS_DIR / "analysis-framing" / "SKILL.md"
        assert path.exists(), f"analysis-framing SKILL.md not found at {path}"

    def test_all_skills_have_skill_md(self) -> None:
        """All 7 bundled skills have a SKILL.md file at repo root skills/ dir."""
        for skill_name in ALL_SKILLS:
            path = SKILLS_DIR / skill_name / "SKILL.md"
            assert path.exists(), f"{skill_name}/SKILL.md not found at {path}"
