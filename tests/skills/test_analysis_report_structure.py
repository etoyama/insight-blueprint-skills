"""Structural validation for the /analysis-report skill's prose contract (Epic 10).

The report skill is Claude-native (assembly logic lives in prose, not Python), so these
tests guard the load-bearing contract in SKILL.md + apa-template.md the same way
TestFramingBrief guards analysis-framing's output template: the mandatory figure captions
(ADR-0008), the graceful-degrade branch, the English APA headings, and the terminal-status
precondition. Without these, a heading or caption field could silently rot.
"""

from __future__ import annotations

import re
from pathlib import Path

from skills._shared.report_check import find_violations
from tests.skills._markdown import section as _section
from tests.skills._markdown import table_row, table_rows, unwrap

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "analysis-report"
NOTEBOOK_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "analysis-notebook"
    / "references"
    / "notebook-contract.md"
)

# The optional per-metric items of ADR-0013, and the Results table column each one fills.
OPTIONAL_METRIC_COLUMNS = {
    "effect_size": "Effect size",
    "confidence_interval": "CI",
    "sample_size": "N",
}


def _skill() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def _template() -> str:
    return (SKILL_DIR / "references" / "apa-template.md").read_text(encoding="utf-8")


class TestApaTemplate:
    """apa-template.md is the canonical report contract."""

    def test_has_english_imrad_headings(self) -> None:
        t = _template()
        for h in (
            "## Abstract",
            "## Introduction",
            "## Method",
            "## Results",
            "## Discussion",
            "### Limitations",
            "### Future Directions",
            "## References",
        ):
            assert h in t, f"apa-template.md missing APA heading '{h}'"

    def test_mandates_axes_and_how_to_read_captions(self) -> None:
        t = _template()
        assert "軸の説明" in t and "図の読み方" in t, (
            "figure captions must be documented"
        )
        assert "figures[N].axes" in t and "figures[N].how_to_read" in t, (
            "figure caption placeholders must map to the manifest fields"
        )

    def test_documents_graceful_degrade(self) -> None:
        t = _template()
        assert "Graceful degrade" in t
        # the degrade trigger the SKILL.md Step 2 relies on
        assert "figures == []" in t


class TestNumbersTable:
    """US-1 (Epic 12): the Results numbers table shows effect size, CI and sample size."""

    def test_notebook_contract_defines_the_three_optional_items(self) -> None:
        contract = NOTEBOOK_CONTRACT.read_text(encoding="utf-8")
        section = _section(contract, "## Optional metric items")
        for key in OPTIONAL_METRIC_COLUMNS:
            assert f"`{key}`" in section, f"notebook contract must define `{key}`"
        for sub_key in ("kind", "level", "lower", "upper"):
            assert f'"{sub_key}"' in section, f"contract must define '{sub_key}'"
        assert "optional" in section.lower()
        assert "ADR-0013" in section

    def test_template_maps_each_item_to_a_column(self) -> None:
        section = _section(_template(), "## Results numbers table")
        for key, column in OPTIONAL_METRIC_COLUMNS.items():
            assert f"`{key}`" in section, f"numbers table must read `{key}`"
            assert f"| {column} |" in section, f"table must have a '{column}' column"

    def test_template_omits_a_column_no_metric_fills(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "omit the column" in section.lower()

    def test_template_keeps_the_table_for_a_verdict_without_the_items(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "| Metric | Value | Threshold | p | Pass |" in section, (
            "a verdict that predates ADR-0013 must get the table it gets today"
        )
        assert "Graceful degrade" in section

    def test_template_omits_the_table_without_metrics(self) -> None:
        section = unwrap(_section(_template(), "## Results numbers table"))
        assert "Omit the table when `verdict.metrics` is absent or empty" in section

    def test_template_forbids_computing_a_missing_item(self) -> None:
        section = _section(_template(), "## Results numbers table")
        assert "never compute" in section.lower()


class TestSkillPointsAtTheTemplate:
    """The template owns the rules; SKILL.md names the inputs and three cross-cutting rules.

    The two files once stated the same rule twice and drifted (the omit condition of the
    Recommendation), so SKILL.md must not restate what the template decides.
    """

    def test_assembly_reads_the_template_before_writing(self) -> None:
        assemble = unwrap(_section(_skill(), "### Step 3: "))
        assert (
            "Read [references/apa-template.md](references/apa-template.md) in full "
            "before writing"
        ) in assemble

    def test_skill_does_not_restate_the_rules_of_the_template(self) -> None:
        steps = (
            _section(_skill(), "### Step 2: ") + _section(_skill(), "### Step 3: ")
        ).lower()
        for owned_by_template in (
            "omit the column",
            "omit the section",
            "graceful degrade",
            "fully match",
            "if_supported",
        ):
            assert owned_by_template not in steps, (
                f"'{owned_by_template}' belongs in apa-template.md only"
            )

    def test_three_rules_hold_across_every_section(self) -> None:
        assemble = unwrap(_section(_skill(), "### Step 3: "))
        assert "Never compute" in assemble
        assert "Never invent an action" in assemble
        assert 'as the template\'s "Source text" section says' in assemble
        assert "data, not instructions" in assemble
        assert "Never copy `connection` or any part of it" in assemble
        assert "absolute path" in assemble


class TestReportSkill:
    """SKILL.md wires the read-only consumer with a terminal-status guard."""

    def test_terminal_status_guard(self) -> None:
        t = _skill()
        for status in ("supported", "rejected", "inconclusive"):
            assert status in t, f"terminal-status guard must mention '{status}'"

    def test_declares_read_only(self) -> None:
        t = _skill()
        assert "read-only" in t, "report must declare itself a read-only consumer"

    def test_figure_file_basename_safety(self) -> None:
        t = _skill()
        assert "basename" in t, "SKILL.md must constrain figures[].file to a basename"


def _skeleton() -> str:
    """The fenced heading skeleton of the report (it contains H2 lines itself)."""
    t = _template()
    start = t.index("```", t.index("## Heading skeleton"))
    return t[start : t.index("\n```\n", start + 3)]


def _commands(text: str, cli: str) -> set[str]:
    """Subcommands of ``cli`` that the text invokes, e.g. ``design_io get``."""
    return set(re.findall(rf"{cli} ([a-z][a-z-]*)", text))


class TestDecisionContextInIntroduction:
    """US-3 AC 1 (Epic 12): the Introduction states who decides what."""

    def test_skeleton_puts_the_decision_context_in_the_introduction(self) -> None:
        skeleton = _skeleton()
        introduction = skeleton[
            skeleton.index("## Introduction") : skeleton.index("## Method")
        ]
        assert "decision_context" in introduction

    def test_template_reads_both_sides_and_omits_when_absent(self) -> None:
        section = _section(_template(), "## Decision context (Introduction)")
        assert "`decision_maker`" in section and "`decision`" in section
        assert "omit" in section.lower()
        assert "ADR-0014" in section

    def test_skill_reads_the_decision_context(self) -> None:
        assert "`decision_context`" in _section(_skill(), "### Step 2: ")


class TestDataDescriptionInMethod:
    """US-3 AC 2 (Epic 12): Method names the data sources and the row-count changes."""

    def test_skeleton_has_a_data_subsection_under_method(self) -> None:
        skeleton = _skeleton()
        method = skeleton[skeleton.index("## Method") : skeleton.index("## Results")]
        assert "### Data" in method

    def test_template_lists_name_type_and_description_from_the_catalog(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert "catalog_io get" in section
        assert "| Data source | Type | Description |" in section
        for field in ("`name`", "`type`", "`description`"):
            assert field in section, f"data source table must read {field}"

    def test_template_never_transcribes_the_connection(self) -> None:
        # The ban itself, not any "never" that happens to follow in the section.
        section = unwrap(_section(_template(), "## Data description (Method)"))
        assert "**never** put `connection` or any part of it in the report" in section

    def test_template_reads_the_row_counts_from_the_lineage_file(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert ".insight/lineage/{id}.mmd" in section
        assert "| Step | Reason | Rows | Change |" in section
        assert "never compute" in section.lower()

    def test_template_omits_what_has_no_material(self) -> None:
        section = _section(_template(), "## Data description (Method)")
        assert "Graceful degrade" in section
        assert "omit" in section.lower()

    def test_skill_reads_the_catalog_and_the_lineage(self) -> None:
        gather = _section(_skill(), "### Step 2: ")
        assert "catalog_io get --id" in gather
        assert ".insight/lineage/{design_id}.mmd" in gather

    def test_source_id_must_match_as_a_whole(self) -> None:
        # Anchored, so "match" cannot be read as "contains a matching part" — the
        # same wording /report-upload uses for the design id.
        assert "fully match `^[a-zA-Z0-9_-]+$`" in _section(
            _template(), "## Data description (Method)"
        )
        # The skill runs the command, so it must send the reader to that rule first.
        gather = unwrap(_section(_skill(), "### Step 2: "))
        assert "filter the ids as it says before calling" in gather


class TestImplicationsAndRecommendation:
    """US-3 AC 3 (Epic 12): the Discussion says what the result means and what to do."""

    def test_discussion_headings_come_in_reading_order(self) -> None:
        skeleton = _skeleton()
        order = [
            skeleton.index(h)
            for h in (
                "## Discussion",
                "### Implications",
                "### Recommendation",
                "### Limitations",
                "### Future Directions",
                "## References",
            )
        ]
        assert order == sorted(order)

    def test_recommendation_is_written_from_next_action_and_decision_context(
        self,
    ) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "`next_action`" in section and "`decision_context`" in section
        for branch in ("if_supported", "if_rejected"):
            assert branch in section, f"Recommendation must map '{branch}'"

    def test_recommendation_is_omitted_when_both_inputs_are_absent(self) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "omit the section" in section.lower()

    def test_recommendation_table_covers_every_combination_of_inputs(self) -> None:
        # One row per combination, so a missing case shows as a missing row.
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        table = section[section.index("| `decision_context` | Branch") :]
        rows = [r for r in table_rows(table)[2:] if r[0] in ("present", "absent")]
        assert [(r[0], r[1]) for r in rows] == [
            ("present", "present"),
            ("present", "absent"),
            ("absent", "present"),
            ("absent", "absent"),
        ]
        assert "Omit the section" in rows[3][2]
        assert "`inconclusive`" in rows[1][2]

    def test_a_branch_counts_as_absent_in_three_cases(self) -> None:
        section = unwrap(
            _section(_template(), "## Implications and Recommendation (Discussion)")
        )
        assert (
            "the design has no `next_action`, the status is `inconclusive`, "
            "or the design states no branch for the status"
        ) in section

    def test_recommendation_never_invents_an_action(self) -> None:
        section = _section(
            _template(), "## Implications and Recommendation (Discussion)"
        )
        assert "never invent" in section.lower()

    def test_skill_reads_next_action(self) -> None:
        assert "`next_action`" in _section(_skill(), "### Step 2: ")


class TestAppendix:
    """US-3 AC 4 (Epic 12): the Appendix carries the lineage diagram and the notebook."""

    def test_skeleton_ends_with_the_appendix(self) -> None:
        skeleton = _skeleton()
        assert skeleton.index("## References") < skeleton.index("## Appendix")

    def test_template_embeds_the_lineage_diagram_as_mermaid(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert ".insight/lineage/{id}.mmd" in section
        assert "```mermaid" in section

    def test_template_gives_the_notebook_path(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert ".insight/notebooks/{id}.py" in section

    def test_template_omits_what_is_missing(self) -> None:
        section = _section(_template(), "## Appendix contents")
        assert "Graceful degrade" in section
        assert "omit" in section.lower()

    def test_skill_checks_that_the_notebook_exists(self) -> None:
        assert ".insight/notebooks/{design_id}.py" in _section(_skill(), "### Step 2: ")


class TestReadOnlyConsumer:
    """US-3 AC 5 (Epic 12): the skill only reads, and never computes a number."""

    def test_only_reading_commands_are_invoked(self) -> None:
        for text in (_skill(), _template()):
            assert _commands(text, "design_io") <= {"get"}
            assert _commands(text, "catalog_io") <= {"get"}

    def test_references_list_only_the_reading_commands(self) -> None:
        t = _skill()
        assert "`get --id ID`" in _section(t, "## design_io Reference")
        assert "`get --id SOURCE`" in _section(t, "## catalog_io Reference")

    def test_the_report_is_the_only_file_written(self) -> None:
        handoff = _section(_skill(), "### Step 4: ")
        assert ".insight/reports/{design_id}.md" in handoff
        assert "only file this skill writes" in handoff

    def test_every_new_input_is_mapped_to_asection(self) -> None:
        mapping = _section(_template(), "## Input → section mapping")
        for source in (
            "`decision_context`",
            "`next_action`",
            "catalog_io get",
            ".insight/lineage/{id}.mmd",
            ".insight/notebooks/{id}.py",
        ):
            assert source in mapping, f"mapping must name {source}"

    def test_numbers_are_transcribed_not_computed(self) -> None:
        assert "never compute" in _section(_skill(), "### Step 3: ").lower()
        assert "Read, do not write" in _section(_skill(), "### Step 2: ")


SOURCE_TEXT = "## Source text (transcribe, never render)"

# Every input the report copies into a fixed slot (Epic 13, US-1 AC 1).
TRANSCRIBED_INPUTS = (
    "`figures[].title`",
    "`figures[].axes`",
    "`figures[].how_to_read`",
    "`name`",
    "`type`",
    "`description`",
    "the reason of a lineage step",
    "the name of a metric",
    "`effect_size.kind`",
    "`decision_maker`",
    "`decision`",
    "`title`",
    "items of `metrics` and `explanatory`",
)

# Sections that place a transcribed input, so each must send the reader to the one rule.
SECTIONS_WITH_TRANSCRIBED_INPUTS = (
    "## Decision context (Introduction)",
    "## Data description (Method)",
    "## Results numbers table",
    "## Figure presentation format",
    "## Method tables (Method)",
    "## Implications and Recommendation (Discussion)",
)


def _source_text() -> str:
    return _section(_template(), SOURCE_TEXT)


def _transcribe(text: str) -> str:
    """The three steps of the Source text section, as code (steps 1 and 2, then 3)."""
    one_line = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r"([\\`*_\[\]<|])", r"\\\1", one_line)


class TestSourceText:
    """US-1 (Epic 13): one way to write text that came from the inputs."""

    def test_every_transcribed_input_is_listed(self) -> None:
        section = _source_text()
        listed = " ".join(row[0] for row in table_rows(section))
        for source in TRANSCRIBED_INPUTS:
            assert source in listed, f"Source text must list {source}"

    def test_transcribing_keeps_every_word(self) -> None:
        section = unwrap(_source_text())
        assert "**Keep every word.**" in section
        assert "Never delete, reorder, translate, shorten, or correct" in section

    def test_transcribing_makes_the_text_one_line(self) -> None:
        section = unwrap(_source_text())
        assert "Replace each run of line breaks and tabs with one space" in section

    def test_transcribing_escapes_exactly_eight_characters(self) -> None:
        section = _source_text()
        assert "these eight characters" in section
        fence = section[section.index("these eight characters") :]
        listed = fence.split("```")[1].split()
        assert listed == ["\\", "`", "*", "_", "[", "]", "<", "|"]

    def test_transcribing_changes_nothing_else(self) -> None:
        section = unwrap(_source_text())
        assert (
            "do not strip a tag, wrap the text in a code span, or add a note" in section
        )

    def test_example_follows_the_three_steps_and_passes_the_check(self) -> None:
        # Ties the rule, its example, and report_check together: an example that
        # drifts from the steps, or a step the check rejects, fails here.
        block = _source_text().split("```")[3]
        pairs = re.findall(r"input: +(.*)\nwritten: +(.*)", block)
        assert len(pairs) == 2
        for given, written in pairs:
            assert _transcribe(given) == written
            assert find_violations(written) == []
        assert find_violations(pairs[0][0]) != []

    def test_example_shows_markup_escaped_and_words_kept(self) -> None:
        section = _source_text()
        assert "![x](http://evil.example/a.png) <b>必読</b>" in section
        assert "!\\[x\\](http://evil.example/a.png) \\<b>必読\\</b>" in section

    def test_other_sections_point_at_the_rule_instead_of_restating_it(self) -> None:
        template = _template()
        for heading in SECTIONS_WITH_TRANSCRIBED_INPUTS:
            section = _section(template, heading)
            assert "[Source text](#source-text-transcribe-never-render)" in section, (
                f"'{heading}' must point at the Source text section"
            )
        outside = template.replace(_source_text(), "")
        assert "plain text" not in outside.lower()
        assert "verbatim" not in _section(template, "## Figure presentation format")

    def test_retold_inputs_carry_no_markup(self) -> None:
        section = unwrap(_source_text())
        assert "**Retold inputs**" in section
        assert "journal" in section
        assert "Carry no markup over from them" in section
        assert "transcribe the phrase with the three steps" in section

    def test_lineage_reason_reads_a_br_as_a_line_break(self) -> None:
        assert "a `<br/>` is a line break" in unwrap(_source_text())
        data = unwrap(_section(_template(), "## Data description (Method)"))
        assert "up to its last `<br/>`" in data

    def test_appendix_skips_a_diagram_with_a_tag_other_than_br(self) -> None:
        appendix = unwrap(_section(_template(), "## Appendix contents"))
        assert "carries any tag other than `<br/>`" in appendix

    def test_skill_sends_the_reader_to_the_rule(self) -> None:
        assemble = unwrap(_section(_skill(), "### Step 3: "))
        assert 'as the template\'s "Source text" section says' in assemble
        # "plain text" was the word whose meaning the two files disagreed on.
        assert "plain text" not in _skill().lower()

    def test_appendix_embeds_only_the_shapes_the_lineage_export_writes(self) -> None:
        # A click or a directive in a hand-edited file never rides in.
        appendix = unwrap(_section(_template(), "## Appendix contents"))
        assert "any line that is not one of the three shapes" in appendix


class TestInstructionsInSourceText:
    """US-3 (Epic 13): an instruction inside source text stays text, and the analyst hears."""

    def test_template_keeps_the_sentence_and_notes_where_it_sits(self) -> None:
        section = unwrap(_source_text())
        assert "changes nothing you do" in section
        assert "Keep it in the report as the text it is" in section
        assert "note where it sits" in section
        assert "Add no note to the report itself" in section

    def test_skill_lists_the_places_for_the_analyst(self) -> None:
        handoff = unwrap(_section(_skill(), "### Step 4: "))
        # The noting is the template's rule, not a step of SKILL.md's own list.
        assert (
            'If you noted an instruction (template, "Instructions in source text")'
            in (handoff)
        )
        assert "データ由来の文に、指示の形をした文があった" in handoff
        assert "If there is none, say nothing about it" in handoff


class TestReportCheck:
    """US-2 AC 5 (Epic 13): the skill checks the written report before handing it off."""

    def test_check_runs_after_the_report_is_written(self) -> None:
        handoff = _section(_skill(), "### Step 4: ")
        assert handoff.index(".insight/reports/{design_id}.md") < handoff.index(
            "report_check --id {design_id}"
        )

    def test_violations_are_fixed_before_the_hand_off(self) -> None:
        handoff = unwrap(_section(_skill(), "### Step 4: "))
        assert "re-run until it reports none" in handoff
        assert "Never hand off a report that still has a violation" in handoff

    def test_a_check_that_could_not_run_is_said_so(self) -> None:
        handoff = unwrap(_section(_skill(), "### Step 4: "))
        assert "do not claim the report was checked" in handoff

    def test_template_says_how_to_fix_each_kind_of_violation(self) -> None:
        # Escaping fixes only some kinds; a figure or a diagram is left out instead.
        section = _section(_template(), "## Violations of report_check")
        fixes = {row[0]: row[1] for row in table_rows(section)[2:]}
        assert set(fixes) == {
            "`image`",
            "`html`",
            "`mermaid-html`",
            "`mermaid-statement`",
        }
        assert "skip that figure" in fixes["`image`"]
        assert "[Source text](#source-text-transcribe-never-render)" in fixes["`html`"]
        for kind in ("`mermaid-html`", "`mermaid-statement`"):
            assert "leave out `### Data Lineage`" in fixes[kind]

    def test_skill_sends_each_violation_to_the_template(self) -> None:
        handoff = unwrap(_section(_skill(), "### Step 4: "))
        assert (
            'fix it as the template\'s "Violations of report_check" section says'
        ) in handoff
        # The template owns the kinds (Epic 12, template-owns-the-report-rules).
        assert "raw HTML" not in handoff

    def test_reference_names_every_outcome_of_the_check(self) -> None:
        # Only 1 with JSON means violations: a crash before the check also exits 1.
        reference = unwrap(_section(_skill(), "## report_check Reference"))
        assert "exit 0 = none" in reference
        assert "1 with JSON on stdout = violations" in reference
        assert "anything else = could not check" in reference

    def test_template_skips_a_figure_file_the_check_rejects(self) -> None:
        figure = unwrap(_section(_template(), "## Figure presentation format"))
        assert (
            "contains `..` or any character other than ASCII letters, digits, `_`, "
            "`.`, and `-`"
        ) in figure


JOURNAL_EVENTS = "## Journal events"
DISCUSSION_TAIL = "## Limitations and Future Directions (Discussion)"


class TestSourceOfEachPart:
    """US-1 (Epic 14): each part of the report comes from one named input."""

    def test_open_questions_follow_the_journal_definition(self) -> None:
        section = unwrap(_section(_template(), JOURNAL_EVENTS))
        assert (
            "[Open Questions](../../analysis-journal/SKILL.md#open-questions-inquiry-board)"
        ) in section
        assert "`metadata.resolves`" in section
        assert "one event id or a list of event ids" in section

    def test_verdict_summary_lists_are_not_read(self) -> None:
        gather = _section(_skill(), "### Step 2: ")
        for key in ("evidence_summary", "open_questions"):
            assert key not in gather, f"Step 2 must not read `{key}`"
        section = unwrap(_section(_template(), JOURNAL_EVENTS))
        assert (
            "`verdict.evidence_summary` and `verdict.open_questions` reach the report "
            "as the journal's `evidence` and `question` events"
        ) in section

    def test_the_title_has_a_row_in_the_mapping(self) -> None:
        mapping = _section(_template(), "## Input → section mapping")
        assert table_row(mapping, "Title")[1] == "the design's `title`"

    def test_future_directions_come_from_open_questions_only(self) -> None:
        skeleton = _skeleton()
        assert "次工程" not in skeleton
        mapping = _section(_template(), "## Input → section mapping")
        assert table_row(mapping, "Future Directions")[1] == "open `question`s"

    def test_the_no_figure_line_names_its_cause(self) -> None:
        degrade = _section(_template(), "## Graceful degrade (no figures)")
        lines = [ln for ln in degrade.splitlines() if ln.startswith("> 図は")]
        assert len(lines) == 2, "one line per cause"
        missing_verdict = next(ln for ln in lines if "verdict.json" in ln)
        assert "notebook が図を生成していない" not in missing_verdict


METHOD_TABLES = "## Method tables (Method)"
RESULTS_NARRATIVE = "## Results narrative"


class TestFormatOfTablesAndNumbers:
    """US-2 (Epic 14): tables and numbers have one format."""

    def test_method_tables_show_every_item_but_the_data_source(self) -> None:
        section = _section(_template(), METHOD_TABLES)
        assert (
            "| Metric | Tier | Aggregation | Grouping | Filter | Comparison |"
            in section
        )
        assert "| Variable | Role | Description | Time points |" in section
        assert "| Data source |" not in section

    def test_method_tables_omit_what_has_no_value(self) -> None:
        section = unwrap(_section(_template(), METHOD_TABLES))
        assert "Omit a column that no row fills" in section
        assert "write `—` in the cells without a value" in section
        assert "Omit the table when the list is empty" in section
        assert "No note is added" in section

    def test_method_table_cells_are_source_text(self) -> None:
        assert METHOD_TABLES in SECTIONS_WITH_TRANSCRIBED_INPUTS
        assert "items of `metrics` and `explanatory`" in unwrap(_source_text())

    def test_a_ci_level_as_a_percent_is_a_display_form(self) -> None:
        section = unwrap(_section(_template(), "## Results numbers table"))
        assert "is a display form, not a computation" in section

    def test_pass_has_one_mark_per_value(self) -> None:
        section = unwrap(_section(_template(), "## Results numbers table"))
        assert "`pass` is `true`: `✓`; `false`: `✗`; absent: `—`" in section

    def test_change_is_the_signed_number_without_rows(self) -> None:
        section = unwrap(_section(_template(), "## Data description (Method)"))
        assert "`Change` is the signed number alone, without `rows`" in section

    def test_evidence_is_grouped_by_direction(self) -> None:
        section = unwrap(_section(_template(), RESULTS_NARRATIVE))
        assert "**仮説を支持する証拠**" in section
        assert "**仮説に反する証拠**" in section
        assert "Never write the value of `direction`" in section
        assert "Omit a group that has no event" in section
        assert "An `evidence` event without a `direction`" in section


ABSTRACT = "## Abstract (lead sentence)"
RECOMMENDATION = "## Implications and Recommendation (Discussion)"

# The fixed first sentence of the Abstract for each terminal status (US-3 AC 1).
ABSTRACT_LEADS = {
    "supported": "仮説は支持された。",
    "rejected": "仮説は棄却された。",
    "inconclusive": "仮説を支持するとも棄却するとも結論できなかった。",
}


class TestLeadSentencesAndDiscussion:
    """US-3 (Epic 14): the sentences that state the result, and the Discussion, do not drift."""

    def test_abstract_opens_with_one_sentence_per_status(self) -> None:
        section = _section(_template(), ABSTRACT)
        for status, lead in ABSTRACT_LEADS.items():
            assert table_row(section, f"`{status}`")[1] == lead

    def test_a_lead_sentence_keeps_its_meaning_in_another_language(self) -> None:
        for heading in (ABSTRACT, RECOMMENDATION):
            section = unwrap(_section(_template(), heading))
            assert "When the narrative is not Japanese" in section, heading

    def test_recommendation_opens_with_one_sentence_per_case(self) -> None:
        section = _section(_template(), RECOMMENDATION)
        leads = {
            "both present": "{decision_maker}には、{decision}について次を推奨する。",
            "`decision_context` only, status `supported` or `rejected`": (
                "{decision}について、この分析の設計は取る行動を定めていない。"
            ),
            "`decision_context` only, status `inconclusive`": (
                "この分析の証拠では、{decision}は決まらない。"
            ),
            "branch of `next_action` only": "次を推奨する。",
        }
        for case, lead in leads.items():
            assert table_row(section, case)[1] == f"`{lead}`"
        assert RECOMMENDATION in SECTIONS_WITH_TRANSCRIBED_INPUTS

    def test_limitations_come_from_limits_and_evidence_against_the_conclusion(
        self,
    ) -> None:
        section = unwrap(_section(_template(), DISCUSSION_TAIL))
        assert "`conclude` and `reflect` events" in section
        assert "`contradicts` when the status is `supported`" in section
        assert "`supports` when it is `rejected`" in section
        assert "Never repeat a sentence the Abstract already states" in section

    def test_an_empty_section_is_omitted_without_a_note(self) -> None:
        section = unwrap(_section(_template(), DISCUSSION_TAIL))
        assert "Omit `### Limitations` when it has nothing" in section
        assert "Omit `### Future Directions` when no question is open" in section
        assert "Never write that a section is empty" in section

    def test_dropped_markup_is_not_reported_to_the_analyst(self) -> None:
        section = unwrap(_source_text())
        assert "Say nothing to the analyst about markup you left out" in section


class TestGapsFoundByFreshReaders:
    """Epic 14 manual check: two fresh readers wrote the same report differently here."""

    def test_fixed_sentences_put_no_space_around_a_field(self) -> None:
        template = _template()
        assert (
            "この分析は、{decision_maker}が{decision}を決めるための材料である。"
            in template
        )
        leads = _section(template, RECOMMENDATION)
        assert "`{decision_maker}には、{decision}について次を推奨する。`" in leads
        assert "`{decision}について、この分析の設計は取る行動を定めていない。`" in leads
        assert "No space goes around a field" in unwrap(_section(template, ABSTRACT))

    def test_a_limit_goes_in_limitations_only(self) -> None:
        abstract = unwrap(_section(_template(), ABSTRACT))
        assert "A limit goes in Limitations only" in abstract

    def test_no_evidence_runs_against_an_inconclusive_conclusion(self) -> None:
        section = unwrap(_section(_template(), DISCUSSION_TAIL))
        assert "none when it is `inconclusive`" in section

    def test_evidence_without_a_direction_follows_the_observe_events(self) -> None:
        section = unwrap(_section(_template(), RESULTS_NARRATIVE))
        assert (
            "An `evidence` event without a `direction` is retold after the `observe` "
            "events, in journal order"
        ) in section
