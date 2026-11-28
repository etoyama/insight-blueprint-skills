"""Structure tests for the narrowed review of the result (Epic 36, Story 36.8).

The check of the computation reads the criterion a notebook copied and its cells
against the design before the analyst reads (ADR-0070). A review of the result that
read them again would put the same comment in two places, so it reads what the
check does not: the value against its judgment, the figures, the guardrails, and
the interpretation with its confounders (ADR-0071 6). It is suggested on two
grounds only (ADR-0071 7).

The lenses and the grounds are fixed as ordered lists, not by the absence of the
old words: a lens that came back under another name would change the list.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.skills._markdown import section, table_rows, unwrap
from tests.skills._reflection import reflection_section
from tests.skills.test_skill_structure import _read_skill

LENSES = (
    "The value and the judgment",
    "The figures",
    "The guardrails",
    "The interpretation and its confounders",
)
_LENS = re.compile(r"^- \*\*(.+?)\*\* — ")
_LENSES_START = "Then read the result with these lenses, one comment per issue:"
_GUIDE = "**The guide to a review of the result.**"
_GLOSSARY = Path(__file__).resolve().parents[2] / "docs" / "UBIQUITOUS_LANGUAGE.md"


def _step_3b() -> str:
    return section(_read_skill("analysis-review"), "### Step 3b: ")


def _lens_items() -> list[str]:
    """Every top-level item of the list of lenses, whatever its form."""
    step = _step_3b()
    lines = step[step.index(_LENSES_START) :].splitlines()[1:]
    start = next(i for i, line in enumerate(lines) if line.strip())
    items: list[str] = []
    for line in lines[start:]:
        if not line.strip() or not (line.startswith(("- ", "* ", "  "))):
            break
        if not line.startswith("  "):
            items.append(line)
    return items


def _guide() -> str:
    """The guide, unwrapped, up to the sentence that leaves the choice to the analyst."""
    step = unwrap(reflection_section("### Step 4:"))
    guide = step[step.index(_GUIDE) :]
    return guide[: guide.index("The analyst decides")]


def _guide_grounds() -> list[str]:
    """The items of the first list under the guide, each unwrapped."""
    step = reflection_section("### Step 4:")
    lines = step[step.index(_GUIDE) :].splitlines()
    start = next(i for i, line in enumerate(lines) if line.lstrip().startswith("- "))
    indent = len(lines[start]) - len(lines[start].lstrip())
    items: list[str] = []
    for line in lines[start:]:
        depth = len(line) - len(line.lstrip())
        if not line.strip() or depth < indent:
            break
        if depth == indent:
            if not line.lstrip().startswith("- "):
                break
            items.append(line.strip()[2:])
        else:
            assert not line.lstrip().startswith(("- ", "* ")), "a ground has a sub-item"
            items[-1] += " " + line.strip()
    return items


class TestTheReviewReadsWhatTheCheckDoesNot:
    """US-6 AC 1: the lenses are the value and the judgment, the figures, the guardrails,
    and the interpretation with its confounders."""

    def test_the_lenses_are_these_four_in_this_order(self) -> None:
        items = _lens_items()
        names = tuple(m.group(1) for m in map(_LENS.match, items) if m)
        assert len(names) == len(items), "a lens is not written as - **Name** — …"
        assert names == LENSES

    def test_the_interpretation_names_another_explanation_and_how_far(self) -> None:
        lens = unwrap(_step_3b())
        lens = lens[lens.index("**The interpretation and its confounders**") :]
        assert re.search(r"another explanation", lens)
        assert re.search(r"how far", lens)

    def test_it_says_the_check_reads_the_copied_line_and_the_cells(self) -> None:
        step = unwrap(_step_3b())
        assert re.search(
            r"line[^.]*order of its cells[^.]*check of the computation[^.]*Step 2", step
        ), (
            "Step 3b does not hand the copied line and the order of the cells to the check"
        )
        assert "Leave both to it" in step

    def test_the_line_is_read_here_while_the_check_is_not_done(self) -> None:
        """Without a check on record, nothing else reads the copied line."""
        step = unwrap(_step_3b())
        assert "`design_io checked --id {design_id}`" in step
        assert re.search(
            r"does not say `checked: true`[^.]*read the line the notebook copied[^.]*`comparison`",
            step,
        )

    def test_the_example_of_a_contradiction_holds_for_either_direction(self) -> None:
        """A line points the way its comparison says; the line keeps only the number."""
        lens = unwrap(_step_3b())
        lens = lens[lens.index("**The value and the judgment**") :]
        lens = lens[: lens.index("**The figures**")]
        assert "the way the `comparison` says" in lens
        assert "above the" not in lens and "below the" not in lens

    def test_the_scope_says_what_a_review_of_the_result_reads(self) -> None:
        scope = unwrap(section(_read_skill("analysis-review"), "## Scope"))
        assert "check of the computation" in scope
        assert "interpretation" in scope and "Step 3b" in scope


class TestTheReviewIsSuggestedOnTwoGrounds:
    """US-6 AC 2: a verdict to end on, or numbers checked only within the data."""

    def test_the_guide_lists_exactly_two_grounds(self) -> None:
        grounds = _guide_grounds()
        assert len(grounds) == 2, grounds
        assert re.search(r"verdict[^.]*confirmation[^.]*legacy exploration", grounds[0])
        assert re.search(r"adds up[^.]*within the data", grounds[1])

    def test_the_guide_says_there_is_no_other_ground(self) -> None:
        assert re.search(r"two grounds[^.]*no other", _guide())

    def test_no_ground_comes_back_in_the_prose_after_the_list(self) -> None:
        """The ground ADR-0071 7 dropped stays out, however it is worded."""
        guide = _guide()
        assert not re.search(r"\badded\b|does not have|design lacks", guide)
        assert not re.search(r"\b(unless|except|or when)\b", guide)

    def test_a_difference_of_the_check_is_not_a_ground(self) -> None:
        assert re.search(r"difference[^.]*check[^.]*not a ground", _guide())

    def test_the_analyst_is_told_what_the_review_reads(self) -> None:
        step = unwrap(reflection_section("### Step 4:"))
        said = re.sub(
            r"\s", "", step[step.index("「結果のレビューでは") : step.index("」")]
        )
        for words in (
            "分析設計と、判定と合わない値、図、",
            "guardrail",
            "ほかの説明がつかないか",
            "どこまで言えるか",
            "分析設計どおりに計算したかは、レビューでなく点検が見る",
        ):
            assert re.sub(r"\s", "", words) in said, words


class TestTheGlossarySaysTheSame:
    """The glossary holds the one definition the skills say."""

    def _row(self) -> str:
        rows = table_rows(_GLOSSARY.read_text(encoding="utf-8"))
        return next(" | ".join(r) for r in rows if r[0] == "結果のレビュー")

    def test_the_definition_names_the_four_lenses_and_the_two_grounds(self) -> None:
        row = self._row()
        for words in (
            "値と判定の矛盾",
            "図",
            "guardrail",
            "解釈と交絡",
            "計算の点検",
            "判定で終わる",
            "データの中の足し上げだけ",
        ):
            assert words in row, words

    def test_it_links_the_decision(self) -> None:
        assert "adr/0071-" in self._row()
