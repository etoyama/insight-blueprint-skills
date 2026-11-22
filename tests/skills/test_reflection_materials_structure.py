"""Structure tests for what /analysis-reflection shows before it asks for a conclusion.

Epic 26 (Story #159) listed the figures, the verdict, the notebook and the metric
definitions in the chat. Epic 28 (US-5, ADR-0036) moves all of that into the design
note: Step 2 renders the note right before it shows the block, and the block says
which file to open, where the note is in it, and which questions link the design.
The block is prose, so the tests check it against what it names: its placeholders
are the keys ``tree_io render --design`` returns.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skills._shared import tree_io
from tests.skills._markdown import section, table_row, unwrap
from tests.skills.test_skill_structure import _read_skill
from tests.tree_io._support import AIM, ROOT_QUESTION, _add, _design

_HEADER = "── 読むもの ──"
_RENDER = "`tree_io render --design {design_id}`"


def _step() -> str:
    return section(_read_skill("analysis-reflection"), "### Step 2")


def _block() -> str:
    """The lines of the block, from its header to the end of the fence it is in."""
    step = _step()
    assert _HEADER in step, "Step 2 shows no block of files to read"
    return step.split(_HEADER, 1)[1].split("```", 1)[0]


def _rules() -> str:
    return unwrap(section(_read_skill("analysis-reflection"), "#### 読むもの"))


def _returned_keys(tmp_path: Path) -> set[str]:
    """The keys of ``render --design`` for a design a question of a tree links."""
    insight = tmp_path / ".insight"
    tree_io.create_tree(
        theme_id="LIB", question=ROOT_QUESTION, aim=AIM, base_dir=insight
    )
    _add(insight)
    design_id = _design(insight)
    tree_io.link_design("LIB", "LIB-Q02", design_id, base_dir=insight)
    return set(tree_io.render_design(design_id, base_dir=insight))


class TestStep2RendersTheNoteFirst:
    """US-5 AC 1: one render, right before the block, the same with or without a tree."""

    def test_its_rules_are_part_of_step_2(self) -> None:
        assert "#### 読むもの" in _step()

    def test_it_comes_after_the_journal_summary(self) -> None:
        step = _step()
        assert step.index("── Branches ──") < step.index(_HEADER)

    def test_it_renders_the_design_right_before_the_block(self) -> None:
        rules = _rules()
        assert rules.count(_RENDER) == 1
        assert "Right before you show the block" in rules

    def test_the_render_does_not_branch_on_the_tree(self) -> None:
        assert "whether or not the theme has a question tree" in _rules()

    def test_the_render_is_in_the_tree_io_reference(self) -> None:
        reference = section(
            _read_skill("analysis-reflection"), "## tree_io / tree_check"
        )
        assert table_row(reference, "`tree_io render --design D`")

    def test_a_failed_render_shows_no_path(self) -> None:
        rules = _rules()
        assert "exits non-zero" in rules
        assert "show no path" in rules


class TestTheBlockSaysWhereTheNoteIs:
    """US-5 AC 2: the file, the place of the note, the questions; nothing else."""

    def test_its_placeholders_are_the_keys_render_returns(self, tmp_path: Path) -> None:
        shown = set(re.findall(r"\{(\w+)\}", _block()))
        assert shown == _returned_keys(tmp_path)

    def test_without_an_anchor_or_a_question_it_shows_the_note_path_only(
        self,
    ) -> None:
        rules = _rules()
        assert "When `anchor` is not there" in rules
        assert "When `node_ids` is empty" in rules
        assert "only the `分析ノート:` line" in rules

    def test_it_lists_no_output_of_the_notebook_and_no_metric(self) -> None:
        block = _block()
        assert ".insight/notebooks/" not in block
        assert "{metric." not in block
        assert "{figure." not in block

    @pytest.mark.parametrize("named", ["figures", "verdict", "notebook", "metrics"])
    def test_it_says_the_note_holds_what_the_chat_no_longer_lists(
        self, named: str
    ) -> None:
        sentence = re.search(r"Do not list the [^.]*\.", _rules())
        assert sentence, "no sentence keeps the notebook outputs out of the chat"
        assert named in sentence[0]

    def test_it_copies_no_value_and_embeds_no_figure(self) -> None:
        rules = _rules()
        assert "Do not copy the values of the verdict" in rules
        assert "embed no figure" in rules


class TestTheNotebookRendersAfterTheJournal:
    """US-5 AC 3: /analysis-notebook renders once its events are in the journal."""

    def _notebook(self) -> str:
        return _read_skill("analysis-notebook")

    def test_it_renders_after_recording_to_the_journal(self) -> None:
        text = self._notebook()
        journal = text.index("### Step 6: Record to the journal")
        render = text.index(_RENDER)
        assert journal < render

    def test_it_renders_once(self) -> None:
        assert self._notebook().count(_RENDER) == 1

    def test_it_reads_the_output_by_the_reflection_rules_instead_of_a_copy(
        self,
    ) -> None:
        """#143: the rules for the output live in one place, the reflection Step 2."""
        step = unwrap(section(self._notebook(), "### Step 7"))
        assert "`#### 読むもの` of /analysis-reflection" in step
        assert "`node_ids`" not in step

    def test_it_is_not_a_gate(self) -> None:
        step = unwrap(section(self._notebook(), "### Step 7"))
        assert "ask nothing" in step


class TestRepliesGoToTheJournal:
    """US-5 AC 4: the block says a reply in the chat is kept in the journal."""

    def test_the_block_says_a_reply_is_kept(self) -> None:
        assert "チャットで返せば、journal に残す" in _block()

    def test_a_reply_becomes_an_event_of_a_type_the_journal_has(self) -> None:
        rules = _rules()
        assert "`reflect`" in rules
        assert "`/analysis-journal`" in rules
        assert "Add no new type of event" in rules


class TestAutoAgreesWithTheReflection:
    """US-5 AC 5: /analysis-auto shows what reflection shows and reads the sources."""

    def _auto(self) -> str:
        return _read_skill("analysis-auto")

    def test_the_reflection_row_presents_the_design_note(self) -> None:
        row = table_row(self._auto(), "reflection")
        assert "the place of the design note" in row[2]

    def test_the_reflection_item_adds_no_file_list(self) -> None:
        workflow = unwrap(section(self._auto(), "## Workflow"))
        item = re.search(r"7\. \*\*reflection\*\*.*?(?= 8\. )", workflow)
        assert item, "no reflection item in Step 3"
        assert "Step 2" in item[0]
        assert "adds no list of files" in item[0]

    @pytest.mark.parametrize("skill", ["analysis-reflection", "analysis-auto"])
    def test_the_skill_never_reads_the_design_note(self, skill: str) -> None:
        text = unwrap(_read_skill(skill))
        assert re.search(r"never reads? the design note", text)
        assert "the design, the journal and the verdict" in text

    def test_the_theme_reflection_row_is_unchanged(self) -> None:
        row = table_row(self._auto(), "theme reflection")
        assert row[1] == "**`/analysis-reflection {theme_id}` T7**"
