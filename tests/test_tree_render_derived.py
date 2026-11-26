"""Tests for the sections of a tree page that show derived values (Epic 34).

What an answer changed since the answer before it, the top of the page that
leads with the subject, the results the answers below rest on and an answer
leaves out, and the answers above that rest on a result (ADR-0056).
Synthetic data only (theme LIB).
"""

from __future__ import annotations

import pytest

from skills._shared import tree_words
from skills._shared.tree_check import Violation
from skills._shared.tree_render import (
    CitedEvent,
)
from tests.test_tree_render import (
    Element,
    by_id,
    has_class,
    make_events,
    make_tree,
    node_card,
    node_text,
    page,
    parse,
    render,
    squash,
    stale,
)


def changed_root(tree: dict | None = None) -> dict:
    """The tree with a root answered in rounds 1 and 2.

    Round 2 keeps citing LIB-H01-E01 in other words, cites LIB-H01-E02 for the
    first time, stops citing LIB-H03-E01 and says the same of LIB-H01-E03.
    """
    tree = make_tree() if tree is None else tree
    tree["nodes"][0]["answers"] = [
        {
            "round": 1,
            "root_revision": 1,
            "statements": [
                {
                    "kind": "claim",
                    "text": "期限切れは 400 件",
                    "cites": ["LIB-H01-E01"],
                },
                {"kind": "claim", "text": "予約は減らない", "cites": ["LIB-H03-E01"]},
                {"kind": "weakening", "text": "1年度だけ", "cites": ["LIB-H01-E03"]},
            ],
        },
        {
            "round": 2,
            "root_revision": 2,
            "statements": [
                {
                    "kind": "claim",
                    "text": "期限切れは 346 件",
                    "cites": ["LIB-H01-E01"],
                },
                {
                    "kind": "undetermined",
                    "text": "取消の理由は分からない",
                    "cites": ["LIB-H01-E02"],
                },
                {"kind": "weakening", "text": "1年度だけ", "cites": ["LIB-H01-E03"]},
            ],
        },
    ]
    return tree


def later_round(tree: dict) -> dict:
    """*tree* after a round 3 in which only LIB-Q05 was answered again."""
    tree["nodes"][4]["answers"].append(
        {
            "round": 3,
            "root_revision": 2,
            "statements": [
                {
                    "kind": "claim",
                    "text": "延長しても予約は減らない",
                    "cites": ["LIB-H03-E01"],
                }
            ],
        }
    )
    return tree


def changes_of(inside: Element) -> Element:
    (found,) = [e for e in inside.walk() if has_class(e, "changes")]
    return found


def is_folded(element: Element, within: Element) -> bool:
    return any(
        d.tag == "details" and "open" not in d.attrs and element.is_inside(d)
        for d in within.walk()
    )


def rows_of(section: Element, *, folded: bool = True) -> list[list[str]]:
    """The cells of each row of the tables in *section*; ``folded=False`` skips folded rows."""
    return [
        [squash(cell.text()) for cell in row.children]
        for row in section.walk()
        if row.tag == "tr"
        and row.parent is not None
        and row.parent.tag == "tbody"
        and (folded or not is_folded(row, section))
    ]


def row_of(section: Element, event_id: str) -> list[str]:
    (row,) = [r for r in rows_of(section) if event_id in r[1]]
    return row


class TestWhatAnAnswerChanged:
    """Epic 34 US-1 AC 1, AC 2: one row per cited event, the two rounds side by side."""

    def section(self, tree: dict | None = None, node_id: str = "LIB-Q02") -> Element:
        return changes_of(node_card(page(tree=tree), node_id))

    def test_a_node_with_an_answer_before_its_last_one_says_what_changed(self) -> None:
        heading = squash(self.section().text())

        assert heading.startswith(
            "前の振り返りから変わったこと（1回目 → 2回目の振り返り）"
        )

    def test_the_section_opens_by_telling_who_read_the_answer_before_what_to_reread(
        self,
    ) -> None:
        (lead,) = [
            squash(p.text())
            for p in self.section().walk()
            if p.tag == "p" and "読み直せばよい" in p.text()
        ]

        assert lead.startswith("1回目の振り返りの答えを読んだ人は、")

    def test_each_cited_event_is_one_row_with_its_content_and_both_rounds(self) -> None:
        section = self.section()

        assert len(rows_of(section, folded=False)) == 2
        kind, event, before, after = row_of(section, "LIB-H01-E01")
        assert kind == "言っていることが変わった"
        assert "期限切れは取消除外で 346 件" in event
        assert before == "これまでわかっていること 取消を含めると期限切れは 400 件"
        assert after == "これまでわかっていること 取消を除くと期限切れは 346 件"

    def test_a_newly_cited_event_says_it_was_no_ground_before(self) -> None:
        kind, event, before, after = row_of(self.section(), "LIB-H01-E02")

        assert kind == "新しく根拠にした"
        assert "取消の理由列は空欄が多い" in event
        assert before == "根拠にしていなかった"
        assert after == "注意すべきこと 1館の1年度だけの数である"

    def test_a_dropped_event_says_it_is_no_ground_now(self) -> None:
        root = page(tree=changed_root())
        section = changes_of(by_id(root, "subject-answer"))

        row = row_of(section, "LIB-H03-E01")
        assert row[0] == "根拠から外した"
        assert row[2] == "これまでわかっていること 予約は減らない"
        assert row[3] == "根拠にしていない"

    def test_the_unchanged_events_are_folded_with_their_count(self) -> None:
        root = page(tree=changed_root())
        section = changes_of(by_id(root, "subject-answer"))

        (folded,) = [d for d in section.walk() if d.tag == "details"]
        assert squash(folded.children[0].text()) == "変わっていない根拠 1 件"
        assert "LIB-H01-E03" in folded.text()
        assert "open" not in folded.attrs

    def test_the_section_counts_the_events_of_each_kind(self) -> None:
        root = page(tree=changed_root())
        section = squash(changes_of(by_id(root, "subject-answer")).text())

        assert (
            "新しく根拠にした 1、根拠から外した 1、言っていることが変わった 1、"
            "変わっていない 1" in section
        )

    def test_an_event_names_the_question_and_the_design_it_comes_from(self) -> None:
        section = self.section()

        (cell,) = [
            c for c in section.walk() if c.tag == "td" and "LIB-H01-E02" in c.text()
        ]
        links = {a.attrs["href"] for a in cell.walk() if a.tag == "a"}
        assert links == {"#LIB-Q02", "#design-LIB-H01"}

    def test_a_node_answered_once_has_no_such_section(self) -> None:
        assert "前の振り返りから変わったこと" not in node_text(page(), "LIB-Q04")

    def test_an_answer_that_only_reorders_its_statements_says_nothing_changed(
        self,
    ) -> None:
        tree = make_tree()
        answers = tree["nodes"][1]["answers"]
        answers[0]["statements"] = list(reversed(answers[1]["statements"]))

        section = squash(self.section(tree).text())

        assert "1回目の振り返りから変わっていない" in section
        assert "読み直せばよい" not in section

    def test_what_a_person_said_is_not_called_an_analysis_result(self) -> None:
        events = make_events() | {
            "LIB-H01-E02": CitedEvent(
                "LIB-H01-E02", "hearing", None, "館長は延長に賛成"
            )
        }
        root = page(events=events)
        section = changes_of(node_card(root, "LIB-Q02"))

        (cell,) = [
            c for c in section.walk() if c.tag == "td" and "LIB-H01-E02" in c.text()
        ]
        assert squash(cell.text()).startswith("人に聞いた答え LIB-H01-E02")
        head = [squash(h.text()) for h in section.walk() if h.tag == "th"]
        assert "分析結果、人に聞いた答え" in head

    def test_the_words_around_the_table_do_not_call_a_hearing_an_analysis_result(
        self,
    ) -> None:
        root = page(tree=changed_root())
        section = changes_of(by_id(root, "subject-answer"))

        outside = squash(
            " ".join(e.text() for e in section.walk() if e.tag in ("p", "summary"))
        )
        assert "分析結果" not in outside

    def test_a_change_of_the_subject_between_the_two_answers_is_named(self) -> None:
        head = [squash(h.text()) for h in self.section().walk() if h.tag == "th"]

        assert "1回目の振り返り（見直す前の主題への答え）で言っていたこと" in head
        assert "2回目の振り返り（今の主題への答え）で言っていること" in head

    def test_two_answers_to_the_same_subject_name_no_revision(self) -> None:
        tree = make_tree()
        tree["nodes"][1]["answers"][0]["root_revision"] = 2

        head = [squash(h.text()) for h in self.section(tree).walk() if h.tag == "th"]

        assert "1回目の振り返りで言っていたこと" in head
        assert "2回目の振り返りで言っていること" in head

    def test_the_legend_says_the_earlier_answer_is_not_checked_again(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        assert "記録と照らして確かめるのは、それぞれの論点の今の答えだけ" in legend

    def test_an_event_missing_from_the_record_is_said_to_be_missing(self) -> None:
        root = page(events={})
        section = changes_of(node_card(root, "LIB-Q02"))

        assert "記録に見つからない LIB-H01-E01" in squash(section.text())

    def test_the_section_speaks_the_analysts_words(self) -> None:
        section = self.section().text()

        for inner in ("引用", "出来事", "下の論点", "journal"):
            assert inner not in section

    def test_an_answer_that_fails_the_check_keeps_its_statements_folded(self) -> None:
        root = parse(render(violations=stale()))

        assert "前の振り返りから変わったこと" not in node_text(root, "LIB-Q02")

    def test_the_legend_explains_each_way_an_event_changed(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        for word, meaning in tree_words.CHANGE_WORDS.values():
            assert f"{word}: {meaning}" in legend
        assert "言い回しを変えただけでも" in legend


class TestAnAnswerOfAnEarlierRound:
    """Epic 34 US-1 AC 5: a round that passes does not hide what an answer changed."""

    def test_the_card_names_the_round_of_the_answer_and_the_latest_round(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert (
            "1回目の振り返り 最新の振り返りは2回目で、"
            "1回目より後の振り返りでは、この答えを書き直していない。" in shown
        )

    def test_an_answer_of_the_latest_round_carries_no_such_line(self) -> None:
        assert "書き直していない" not in node_text(page(), "LIB-Q02")

    def test_the_change_of_an_earlier_round_stays_on_the_card_folded(self) -> None:
        root = page(tree=later_round(make_tree()))
        section = changes_of(node_card(root, "LIB-Q02"))

        assert section.tag == "details"
        assert "open" not in section.attrs
        summary = squash(section.children[0].text())
        assert summary == (
            "前の振り返りから変わったこと（1回目 → 2回目の振り返り） 最新の振り返りの変化ではないので畳んである"
        )
        assert "取消を含めると期限切れは 400 件" in section.text()

    def test_the_change_of_the_latest_round_is_not_folded(self) -> None:
        root = page()
        section = changes_of(node_card(root, "LIB-Q02"))

        assert section.tag != "details"
        (row, *_) = [r for r in section.walk() if r.tag == "tr"]
        assert not is_folded(row, node_card(root, "LIB-Q02"))


class TestTheTopOfThePage:
    """Epic 34 US-1 AC 4: the answer, its change and the next question come first."""

    def test_the_answer_and_the_next_question_come_before_the_legend_and_the_tree(
        self,
    ) -> None:
        body = next(e for e in page().walk() if e.tag == "body")

        order = [e.attrs.get("id") for e in body.children if e.attrs.get("id")]
        assert order[:4] == ["header", "subject-answer", "next-question", "legend"]
        assert order.index("legend") < order.index("question-tree")

    def test_the_legend_is_folded(self) -> None:
        legend = by_id(page(), "legend")

        assert legend.tag == "details"
        assert "open" not in legend.attrs
        assert squash(legend.children[0].text()) == "読み方"

    def test_the_top_shows_the_current_answer_to_the_subject(self) -> None:
        top = by_id(page(tree=changed_root()), "subject-answer")
        visible = squash(
            " ".join(e.text() for e in top.children if not has_class(e, "changes"))
        )

        assert visible.startswith("主題への現時点の答え")
        assert "これまでわかっていること 期限切れは 346 件" in visible
        assert "まだ決められないこと 取消の理由は分からない" in visible
        assert "2回目の振り返り" in visible

    def test_a_subject_without_an_answer_says_so(self) -> None:
        top = squash(by_id(page(), "subject-answer").text())

        assert top.startswith("主題への現時点の答え 主題にはまだ答えていない。")

    def test_the_top_shows_what_the_answer_to_the_subject_changed(self) -> None:
        root = page(tree=changed_root())
        section = changes_of(by_id(root, "subject-answer"))

        assert squash(section.text()).startswith(
            "前の振り返りから変わったこと（1回目 → 2回目の振り返り）"
        )
        assert {r[0] for r in rows_of(section)} == {
            "言っていることが変わった",
            "新しく根拠にした",
            "根拠から外した",
            "変わっていない",
        }

    def test_the_card_of_the_subject_points_at_the_top_instead_of_repeating_it(
        self,
    ) -> None:
        root = page(tree=changed_root())
        own = node_card(root, "LIB-Q01")

        assert not [e for e in own.walk() if e.tag == "table"]
        links = [a for a in own.walk() if a.attrs.get("href") == "#subject-answer"]
        assert "前の振り返りから変わったことは、ページの冒頭に出している" in [
            squash(a.text()) for a in links
        ]

    def test_an_answer_to_the_subject_of_an_earlier_round_says_so_at_the_top(
        self,
    ) -> None:
        root = page(tree=later_round(changed_root()))
        top = by_id(root, "subject-answer")

        assert "2回目の振り返り 最新の振り返りは3回目で" in squash(top.text())
        assert changes_of(top).tag == "details"

    def test_an_answer_to_the_subject_that_fails_the_check_is_not_shown_at_the_top(
        self,
    ) -> None:
        violation = Violation("LIB-Q01", 2, 1, "missing-event", "LIB-H01-E99")
        root = parse(render(tree=changed_root(), violations=[violation]))
        top = by_id(root, "subject-answer")

        assert "期限切れは 346 件" not in top.text()
        assert "記録と合わない答え LIB-Q01 のカードで確かめる" in squash(top.text())
        assert [a.attrs["href"] for a in top.walk() if a.tag == "a"] == ["#LIB-Q01"]

    def test_the_answer_to_an_earlier_subject_is_marked_at_the_top(self) -> None:
        tree = changed_root()
        tree["nodes"][0]["answers"].pop()

        top = squash(by_id(page(tree=tree), "subject-answer").text())

        assert "見直す前の主題への答え" in top
        assert "版" not in top


def deciding(*decisions: tuple[int, str, str, str]) -> dict:
    tree = make_tree()
    tree["decisions"] = [
        {"round": round, "kind": kind, "node_id": node_id, "reason": reason}
        for round, kind, node_id, reason in decisions
    ]
    return tree


START = (0, "start", "LIB-Q02", "件数が変わるので、最初に数え方を固める")


class TestTheNextQuestion:
    """Epic 34 US-1 AC 4: the question to look into next, and why."""

    def next_question(self, tree: dict) -> str:
        return squash(by_id(page(tree=tree), "next-question").text())

    def test_the_last_decision_names_the_question_and_the_reason(self) -> None:
        tree = deciding(START, (2, "deepen", "LIB-Q04", "理由の偏りを先に見る"))
        root = page(tree=tree)
        section = by_id(root, "next-question")

        assert squash(section.text()) == (
            "次に調べる論点 深める（2回目の振り返りの後）: LIB-Q04 "
            "取消の理由に偏りはあるか 理由: 理由の偏りを先に見る "
            "この理由は、根拠にした分析結果を挙げていない。"
        )
        assert [a.attrs["href"] for a in section.walk() if a.tag == "a"] == ["#LIB-Q04"]

    def test_only_the_last_decision_is_shown(self) -> None:
        tree = deciding(START, (2, "return", "LIB-Q03", "通知を見る"))

        assert "最初に数え方を固める" not in self.next_question(tree)

    def test_a_close_says_no_next_question_is_decided(self) -> None:
        tree = deciding(START, (2, "close", "LIB-Q02", "数え方は固まった"))

        shown = self.next_question(tree)

        assert "区切る（2回目の振り返りの後）: LIB-Q02" in shown
        assert shown.endswith("区切ったので、次に調べる論点は決まっていない。")

    def test_a_tree_without_a_decision_says_so(self) -> None:
        assert self.next_question(make_tree(decisions=[])) == (
            "次に調べる論点 まだ決めていない。"
        )

    def test_a_decision_older_than_the_latest_round_says_the_round_is_undecided(
        self,
    ) -> None:
        shown = self.next_question(make_tree())

        assert shown.startswith(
            "次に調べる論点 2回目の振り返りの後は、まだ決めていない。"
            "最後に決めたこと: 最初の論点を選ぶ: LIB-Q02"
        )


# --- What the answers below cite and the answer does not, and the answers above ---

NULL_RESULT = "通知を3日早めても、期限切れの数に差は見られなかった"


def results() -> dict[str, CitedEvent]:
    """The events of make_events, a null result of LIB-H02 and what LIB-H03 found."""
    return {
        **make_events(),
        "LIB-H01-E03": CitedEvent("LIB-H01-E03", "observe", None, "1年度だけの記録"),
        "LIB-H02-E01": CitedEvent("LIB-H02-E01", "evidence", "refutes", NULL_RESULT),
        "LIB-H03-E01": CitedEvent(
            "LIB-H03-E01", "evidence", "refutes", "延長した館でも予約は減らなかった"
        ),
    }


def null_round(tree: dict | None = None) -> dict:
    """changed_root, and LIB-Q03 answered in round 2 with a result the root leaves out.

    The root cited LIB-H03-E01 (of LIB-Q05) in round 1 and dropped it in round 2,
    in which it newly cited LIB-H01-E02.
    """
    tree = changed_root(tree)
    tree["nodes"][2]["answers"] = [
        {
            "round": 2,
            "root_revision": 2,
            "statements": [
                {
                    "kind": "claim",
                    "text": "通知の日は効かない",
                    "cites": ["LIB-H02-E01"],
                }
            ],
        }
    ]
    return tree


def null_page(tree: dict | None = None, **over: object) -> Element:
    return page(null_round(tree), events=results(), **over)  # type: ignore[arg-type]


def of_class(inside: Element, name: str) -> list[Element]:
    return [e for e in inside.walk() if has_class(e, name)]


def one_of_class(inside: Element, name: str) -> Element:
    (found,) = of_class(inside, name)
    return found


class TestResultsNotYetInTheSubjectAnswer:
    """US-3 AC 1: the top of the page lists what the subject's answer leaves out."""

    def block(self, root: Element) -> str:
        return squash(one_of_class(by_id(root, "subject-answer"), "uncited").text())

    def test_a_result_never_cited_is_listed_with_its_node_round_and_statement(
        self,
    ) -> None:
        shown = self.block(null_page())

        assert shown.startswith("まだ主題への答えに入れていない分析結果")
        assert "分析結果 LIB-H02-E01" in shown
        assert NULL_RESULT in shown
        assert (
            "論点 LIB-Q03 の2回目の振り返りの答えが、この分析結果について言っていること:"
            in shown
        )
        assert "これまでわかっていること 通知の日は効かない" in shown

    def test_it_says_a_result_without_a_difference_lands_here(self) -> None:
        assert "差が出なかった分析の結果も、ここに出る。" in self.block(null_page())

    def test_the_block_is_open(self) -> None:
        root = null_page()
        top = by_id(root, "subject-answer")

        assert not is_folded(one_of_class(top, "uncited"), top)

    def test_a_result_cited_before_is_not_in_this_block(self) -> None:
        assert "LIB-H03-E01" not in self.block(null_page())

    def test_it_follows_the_changes_and_comes_before_the_next_question(self) -> None:
        text = squash(null_page().text())

        assert (
            text.index("前の振り返りから変わったこと")
            < text.index("まだ主題への答えに入れていない分析結果")
            < text.index("次に調べる論点")
        )

    def test_a_subject_without_an_answer_lists_every_result_cited_below(self) -> None:
        shown = self.block(page(events=results()))

        for event_id in ("LIB-H01-E01", "LIB-H01-E02", "LIB-H03-E01"):
            assert event_id in shown

    def test_nothing_left_out_shows_no_block(self) -> None:
        tree = changed_root()
        for node in tree["nodes"][1:]:
            node.pop("answers", None)

        assert of_class(by_id(page(tree), "subject-answer"), "uncited") == []

    def test_a_statement_that_failed_the_check_stays_in_its_card(self) -> None:
        failed = [Violation("LIB-Q03", 2, 1, "number-not-cited", "3")]

        shown = self.block(null_page(violations=failed))

        assert "通知の日は効かない" not in shown
        assert (
            "論点 LIB-Q03 の答えは記録と合わない。文は LIB-Q03 のカードで確かめる"
            in shown
        )
        assert NULL_RESULT in shown

    def test_what_a_person_said_is_not_called_an_analysis_result(self) -> None:
        events = results()
        events["LIB-H02-E01"] = CitedEvent("LIB-H02-E01", "hearing", None, "効かない")

        shown = self.block(page(null_round(), events=events))

        assert "人に聞いた答え LIB-H02-E01" in shown
        assert "分析結果 LIB-H02-E01" not in shown


class TestResultsTheSubjectAnswerNoLongerRestsOn:
    """US-3 AC 1: a result cited before is set apart, quietly, with its rounds."""

    def block(self, root: Element) -> Element:
        return one_of_class(by_id(root, "subject-answer"), "uncited-before")

    def test_it_is_folded_under_its_own_heading_with_a_count(self) -> None:
        root = null_page()
        block = self.block(root)

        assert block.tag == "details"
        assert squash(block.children[0].text()) == (
            "前は主題への答えの根拠にしていて、今は外している分析結果 1 件"
        )

    def test_it_gives_the_last_round_that_cited_it_and_what_came_in_instead(
        self,
    ) -> None:
        shown = squash(self.block(null_page()).text())

        assert "分析結果 LIB-H03-E01" in shown
        assert "1回目の振り返りの答えまでは根拠にしていた。" in shown
        assert "その次の答えで新しく根拠にした分析結果: LIB-H01-E02" in shown
        assert (
            "論点 LIB-Q05 の1回目の振り返りの答えが、この分析結果について言っていること:"
            in shown
        )

    def test_the_never_cited_block_does_not_hold_it(self) -> None:
        root = null_page()

        assert "LIB-H02-E01" not in squash(self.block(root).text())


def reworded_round(tree: dict | None = None) -> dict:
    """null_round, and a round 3 in which the root says another thing of LIB-H01-E01."""
    tree = null_round(tree)
    tree["nodes"][0]["answers"].append(
        {
            "round": 3,
            "root_revision": 2,
            "statements": [
                {
                    "kind": "weakening",
                    "text": "346 件は1館だけの数",
                    "cites": ["LIB-H01-E01"],
                },
                {
                    "kind": "undetermined",
                    "text": "取消の理由は分からない",
                    "cites": ["LIB-H01-E02"],
                },
                {"kind": "weakening", "text": "1年度だけ", "cites": ["LIB-H01-E03"]},
            ],
        }
    )
    return tree


class TestTheAnswersAboveThatRestOnTheResult:
    """US-2 AC 1, AC 2, AC 4: the card of an earlier node shows how it is used above."""

    def above(self, root: Element, node_id: str) -> Element:
        return one_of_class(node_card(root, node_id), "cited-above")

    def test_the_card_names_the_answer_above_its_round_and_statements(self) -> None:
        shown = squash(self.above(null_page(), "LIB-Q02").text())

        assert shown.startswith("この論点の分析結果を根拠にしている答え")
        assert (
            "分析結果 LIB-H01-E01 を、論点 LIB-Q01（主題）の2回目の振り返りの答えが根拠にしている:"
            in shown
        )
        assert "これまでわかっていること 期限切れは 346 件" in shown

    def test_the_subject_links_to_the_top_of_the_page(self) -> None:
        links = [
            a.attrs["href"]
            for a in self.above(null_page(), "LIB-Q02").walk()
            if a.tag == "a"
        ]

        assert "#subject-answer" in links

    def test_an_answer_that_did_not_change_says_nothing_about_a_change(self) -> None:
        assert "変えた" not in squash(self.above(null_page(), "LIB-Q02").text())

    def test_a_later_change_above_gives_its_round_and_that_this_answer_stayed(
        self,
    ) -> None:
        shown = squash(
            self.above(page(reworded_round(), events=results()), "LIB-Q02").text()
        )

        assert "論点 LIB-Q01（主題）の3回目の振り返りの答えが根拠にしている:" in shown
        assert (
            "論点 LIB-Q01 の答えは3回目の振り返りから、この分析結果について言っていることを変えた。"
            "この論点の答えは2回目の振り返りのままで、変わっていない。"
        ) in shown

    def test_an_answer_further_above_is_listed_after_the_parent(self) -> None:
        shown = squash(self.above(null_page(), "LIB-Q04").text())

        parent = shown.index("論点 LIB-Q02 の2回目の振り返りの答え")
        subject = shown.index("論点 LIB-Q01（主題）の2回目の振り返りの答え")
        assert parent < subject

    def test_a_parent_that_is_not_the_subject_links_to_its_card(self) -> None:
        links = [
            a.attrs["href"]
            for a in self.above(null_page(), "LIB-Q04").walk()
            if a.tag == "a"
        ]

        assert "#LIB-Q02" in links

    def test_an_answer_above_that_failed_the_check_stays_in_its_card(self) -> None:
        failed = [Violation("LIB-Q01", 2, 1, "number-not-cited", "346")]

        shown = squash(self.above(null_page(violations=failed), "LIB-Q02").text())

        assert "期限切れは 346 件" not in shown
        assert (
            "論点 LIB-Q01 の答えは記録と合わない。文は LIB-Q01 のカードで確かめる"
            in shown
        )

    def test_a_card_whose_answer_nobody_above_cites_has_no_such_block(self) -> None:
        assert of_class(node_card(null_page(), "LIB-Q03"), "cited-above") == []


class TestTheCardOfANodeWithResultsBelow:
    """US-3 AC 1 on the cards: each node lists what its own answer leaves out."""

    def test_a_node_lists_the_results_below_its_answer_leaves_out(self) -> None:
        tree = null_round()
        tree["nodes"][1]["answers"][-1]["statements"].pop()  # LIB-H01-E02 left out

        shown = squash(
            one_of_class(
                node_card(page(tree, events=results()), "LIB-Q02"), "uncited"
            ).text()
        )

        assert shown.startswith("まだこの論点の答えに入れていない分析結果")
        assert (
            "論点 LIB-Q04 の2回目の振り返りの答えが、この分析結果について言っていること:"
            in shown
        )

    def test_the_card_of_the_subject_links_to_the_top_of_the_page(self) -> None:
        card = node_card(null_page(), "LIB-Q01")

        assert of_class(card, "uncited") == []
        assert "まだ答えに入れていない分析結果は、ページの冒頭に出している" in squash(
            card.text()
        )


class TestTheNewSectionsSpeakTheAnalystsWords:
    """US-5 AC 5: no internal word reaches the analyst in the sections this Story adds."""

    @pytest.mark.parametrize("word", ["下の論点", "引用", "出来事"])
    def test_no_internal_word(self, word: str) -> None:
        root = page(reworded_round(), events=results())
        sections = [
            *of_class(root, "uncited"),
            *of_class(root, "uncited-before"),
            *of_class(root, "cited-above"),
        ]

        assert sections
        for section in sections:
            assert word not in squash(section.text())

    def test_the_legend_explains_the_new_sections(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        assert "「まだ答えに入れていない分析結果」" in legend
        assert "「前は答えの根拠にしていて、今は外している分析結果」" in legend
        assert "「この論点の分析結果を根拠にしている答え」" in legend
        assert "外した理由は記録に無いので、出さない。" in legend
