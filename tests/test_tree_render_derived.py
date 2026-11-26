"""Tests for the sections of a tree page that show derived values (Epic 34).

What an answer changed since the answer before it, and the top of the page
that leads with the subject (ADR-0056). Synthetic data only (theme LIB).
"""

from __future__ import annotations

from skills._shared import tree_render
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

        assert heading.startswith("前の回から変わったこと（回 1 → 回 2）")

    def test_the_section_opens_by_telling_who_read_the_answer_before_what_to_reread(
        self,
    ) -> None:
        (lead,) = [
            squash(p.text())
            for p in self.section().walk()
            if p.tag == "p" and "読み直せばよい" in p.text()
        ]

        assert lead.startswith("回 1 の答えを読んだ人は、")

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
        assert "前の回から変わったこと" not in node_text(page(), "LIB-Q04")

    def test_an_answer_that_only_reorders_its_statements_says_nothing_changed(
        self,
    ) -> None:
        tree = make_tree()
        answers = tree["nodes"][1]["answers"]
        answers[0]["statements"] = list(reversed(answers[1]["statements"]))

        section = squash(self.section(tree).text())

        assert "回 1 から変わっていない" in section
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

        assert "回 1（主題の版 1 への答え）で、ここから言っていたこと" in head
        assert "回 2（主題の版 2 への答え）で、ここから言っていること" in head

    def test_two_answers_to_the_same_subject_name_no_revision(self) -> None:
        tree = make_tree()
        tree["nodes"][1]["answers"][0]["root_revision"] = 2

        head = [squash(h.text()) for h in self.section(tree).walk() if h.tag == "th"]

        assert "回 1 で、ここから言っていたこと" in head
        assert "回 2 で、ここから言っていること" in head

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

        assert "前の回から変わったこと" not in node_text(root, "LIB-Q02")

    def test_the_legend_explains_each_way_an_event_changed(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        for word, meaning in tree_render._CHANGE_WORDS.values():
            assert f"{word}: {meaning}" in legend
        assert "言い回しを変えただけでも" in legend


class TestAnAnswerOfAnEarlierRound:
    """Epic 34 US-1 AC 5: a round that passes does not hide what an answer changed."""

    def test_the_card_names_the_round_of_the_answer_and_the_latest_round(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert (
            "振り返りの回 1（主題の版 1） 最新の振り返りは回 2 で、"
            "回 1 より後の回では、この答えを書き直していない。" in shown
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
            "前の回から変わったこと（回 1 → 回 2） 最新の回の変化ではないので畳んである"
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
        assert "振り返りの回 2（主題の版 2）" in visible

    def test_a_subject_without_an_answer_says_so(self) -> None:
        top = squash(by_id(page(), "subject-answer").text())

        assert top == "主題への現時点の答え 主題にはまだ答えていない。"

    def test_the_top_shows_what_the_answer_to_the_subject_changed(self) -> None:
        root = page(tree=changed_root())
        section = changes_of(by_id(root, "subject-answer"))

        assert squash(section.text()).startswith(
            "前の回から変わったこと（回 1 → 回 2）"
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
        (link,) = [a for a in own.walk() if a.attrs.get("href") == "#subject-answer"]
        assert (
            squash(link.text()) == "前の回から変わったことは、ページの冒頭に出している"
        )

    def test_an_answer_to_the_subject_of_an_earlier_round_says_so_at_the_top(
        self,
    ) -> None:
        root = page(tree=later_round(changed_root()))
        top = by_id(root, "subject-answer")

        assert "振り返りの回 2（主題の版 2） 最新の振り返りは回 3 で" in squash(
            top.text()
        )
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

        assert "見直す前の主題への答え（主題の版 1 への答え）" in top


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
            "次に調べる論点 深める（回 2 の振り返りの後）: LIB-Q04 "
            "取消の理由に偏りはあるか 理由: 理由の偏りを先に見る"
        )
        assert [a.attrs["href"] for a in section.walk() if a.tag == "a"] == ["#LIB-Q04"]

    def test_only_the_last_decision_is_shown(self) -> None:
        tree = deciding(START, (2, "return", "LIB-Q03", "通知を見る"))

        assert "最初に数え方を固める" not in self.next_question(tree)

    def test_a_close_says_no_next_question_is_decided(self) -> None:
        tree = deciding(START, (2, "close", "LIB-Q02", "数え方は固まった"))

        shown = self.next_question(tree)

        assert "区切る（回 2 の振り返りの後）: LIB-Q02" in shown
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
            "次に調べる論点 回 2 の振り返りの後は、まだ決めていない。"
            "最後に決めたこと: 最初の論点を選ぶ: LIB-Q02"
        )


class TestTheWayAnEventChangedHasItsWord:
    def test_the_table_covers_the_enum(self) -> None:
        from skills._shared.tree_changes import ChangeKind

        assert set(tree_render._CHANGE_WORDS) == set(ChangeKind)
