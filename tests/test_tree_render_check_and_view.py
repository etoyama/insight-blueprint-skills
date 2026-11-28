"""The check of the computation and the analyst's view on the tree page and the report.

Epic 36, Story 36.7. US-1 AC 5: the tree page and the report mark a statement
that is the analyst's view. US-5: the card of a design says how its check
stands, and the difference it found, in the sentence the check wrote. A
statement that only gained the mark is unchanged, on the card as in the table
(36.2 left the two apart). Synthetic data only.
"""

from __future__ import annotations

import copy
from dataclasses import replace

from insight_blueprint.models.check import CheckedBy, CheckItem, CheckSubject
from insight_blueprint.models.tree import StatementKind
from skills._shared.design_note_check import NoteCheck, check_summary
from skills._shared.tree_changes import ChangeKind
from skills._shared.tree_words import (
    CHANGE_WORDS,
    KIND_WORDS,
    MARK_WORDS,
    VIEW_WORD,
    Mark,
    legend,
)
from tests._tree_page import (
    branch_cards,
    by_id,
    card_text,
    has_class,
    make_designs,
    make_tree,
    marks_text,
    node_card,
    page,
    parse,
    squash,
)

GRAIN_NOTE = "分析設計は利用者ごとに数えるが、分析コードは予約ごとに数えている。"
METRIC_NOTE = "分析コードの出した結果の指標「mean_by_group」が、分析設計に無い。"
VIEW_TEXT = "取消を除いた数え方なら、延長を試す価値はあると見る"


def _items(**differ: CheckItem) -> tuple[CheckItem, ...]:
    return tuple(
        differ.get(
            s.value, CheckItem.model_validate({"subject": s.value, "result": "agrees"})
        )
        for s in CheckSubject
    )


def _differs(subject: str, note: str, cell: str) -> CheckItem:
    return CheckItem.model_validate(
        {"subject": subject, "result": "differs", "note": note, "cell": cell}
    )


TWO_DIFFERENCES = NoteCheck(
    checked=True,
    checked_by=CheckedBy.check_agent,
    items=_items(
        grain=_differs("grain", GRAIN_NOTE, "data_prep"),
        metrics=_differs("metrics", METRIC_NOTE, "analysis"),
    ),
)
NO_DIFFERENCE = NoteCheck(
    checked=True, checked_by=CheckedBy.check_agent, items=_items()
)


def _designs(check: NoteCheck, *, has_verdict: bool = True) -> dict:
    designs = make_designs()
    designs["LIB-H01"] = replace(
        designs["LIB-H01"], check=check, has_verdict=has_verdict
    )
    return designs


def _card_of_h01(check: NoteCheck, *, has_verdict: bool = True) -> str:
    root = page(designs=_designs(check, has_verdict=has_verdict))
    (card,) = branch_cards(root, "LIB-Q02")
    return card_text(card)


class TestTheCheckOnTheCardOfADesign:
    def test_the_card_says_how_the_check_stands(self) -> None:
        text = _card_of_h01(TWO_DIFFERENCES)

        assert check_summary(True, TWO_DIFFERENCES) in text

    def test_the_card_shows_each_difference_in_the_sentence_the_check_wrote(
        self,
    ) -> None:
        text = _card_of_h01(TWO_DIFFERENCES)

        assert GRAIN_NOTE in text
        assert METRIC_NOTE in text
        assert text.index(GRAIN_NOTE) < text.index(METRIC_NOTE)

    def test_the_card_links_the_section_of_the_check_in_the_note(self) -> None:
        root = page(designs=_designs(TWO_DIFFERENCES))
        (card,) = branch_cards(root, "LIB-Q02")
        hrefs = [e.attrs.get("href") for e in card.walk() if e.tag == "a"]

        assert "#note-LIB-H01-check" in hrefs

    def test_a_check_with_no_difference_is_one_line(self) -> None:
        text = _card_of_h01(NO_DIFFERENCE)

        assert check_summary(True, NO_DIFFERENCE) in text
        assert "分析設計と違う点は無い" in text

    def test_a_check_not_done_says_so(self) -> None:
        assert "まだ済んでいない" in _card_of_h01(NoteCheck())

    def test_a_check_not_done_links_no_result(self) -> None:
        root = page(designs=_designs(NoteCheck()))
        (card,) = branch_cards(root, "LIB-Q02")
        hrefs = [e.attrs.get("href") for e in card.walk() if e.tag == "a"]

        assert "#note-LIB-H01-check" not in hrefs

    def test_a_design_without_a_verdict_says_nothing_of_a_check(self) -> None:
        assert "点検" not in _card_of_h01(NoteCheck(), has_verdict=False)

    def test_the_short_row_under_a_second_node_does_not_repeat_the_check(
        self,
    ) -> None:
        tree = make_tree()
        tree["nodes"][2]["design_ids"] = ["LIB-H02", "LIB-H01"]
        root = page(tree=tree, designs=_designs(TWO_DIFFERENCES))
        short = [c for c in branch_cards(root, "LIB-Q03") if "LIB-H01" in card_text(c)]

        assert short
        assert GRAIN_NOTE not in card_text(short[0])

    def test_the_legend_says_what_the_line_of_the_check_is(self) -> None:
        text = squash(parse(str(legend())).text())

        assert "分析設計どおりに計算したかの点検" in text
        assert "数が正しいか" in text


def _with_view(tree: dict, node: int, answer: int, statement: int) -> dict:
    tree = copy.deepcopy(tree)
    said = tree["nodes"][node]["answers"][answer]["statements"][statement]
    said["analyst_view"] = True
    return tree


class TestTheViewOnThePage:
    def test_a_statement_of_the_analysts_view_carries_its_mark(self) -> None:
        tree = _with_view(make_tree(), 1, 1, 0)
        root = page(tree=tree)
        (statements,) = [
            e for e in node_card(root, "LIB-Q02").children if has_class(e, "statements")
        ]
        items = [squash(li.text()) for li in statements.children if li.tag == "li"]

        kind = KIND_WORDS[StatementKind.claim][0]
        assert items[0].startswith(f"{kind}（{VIEW_WORD}）")
        assert VIEW_WORD not in items[1]

    def test_the_mark_is_said_in_the_words_of_the_page(self) -> None:
        assert VIEW_WORD == "分析者の見立て"

    def test_the_mark_follows_the_statement_into_its_evidence(self) -> None:
        tree = _with_view(make_tree(), 1, 1, 0)
        root = page(tree=tree)
        evidence = [e for e in by_id(root, "LIB-Q02").walk() if e.tag == "details"]

        assert any(VIEW_WORD in squash(d.text()) for d in evidence)

    def test_the_legend_says_what_the_mark_means(self) -> None:
        text = squash(parse(str(legend())).text())

        assert f"（{VIEW_WORD}）" in text
        assert "言い換えていない" in text


class TestAMarkAddedToTheSameWords:
    """An answer that says the same, now as the analyst's view, did not change."""

    def _tree(self) -> dict:
        tree = make_tree()
        q02 = tree["nodes"][1]
        again = copy.deepcopy(q02["answers"][1])
        again["round"] = 3
        again["statements"][0]["analyst_view"] = True
        q02["answers"].append(again)
        # Round 3 is the latest round of the tree: the root answers it too.
        tree["nodes"][0]["answers"] = [
            {
                "round": 3,
                "root_revision": 2,
                "statements": [
                    {"kind": "claim", "text": VIEW_TEXT, "cites": ["LIB-H01-E01"]}
                ],
            }
        ]
        return tree

    def test_the_card_has_no_mark_of_a_change(self) -> None:
        marks = marks_text(page(tree=self._tree()), "LIB-Q02")

        changed = MARK_WORDS[Mark.changed][0].format(round=3)
        assert changed not in marks

    def test_the_table_of_changes_says_unchanged(self) -> None:
        text = squash(node_card(page(tree=self._tree()), "LIB-Q02").text())

        assert "根拠も、根拠について言っていることも" in text
        assert f"{CHANGE_WORDS[ChangeKind.reworded][0]} 0" in text
        assert f"{CHANGE_WORDS[ChangeKind.unchanged][0]} 2" in text

    def test_new_words_still_carry_the_mark_of_a_change(self) -> None:
        tree = self._tree()
        tree["nodes"][1]["answers"][2]["statements"][0]["text"] = VIEW_TEXT
        marks = marks_text(page(tree=tree), "LIB-Q02")

        assert MARK_WORDS[Mark.changed][0].format(round=3) in marks
