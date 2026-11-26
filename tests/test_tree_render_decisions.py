"""Tests for how far a tree has come and what its decisions rest on (Epic 34, Story 34.6).

A question with no design of its own shows the progress of the questions under
it (ADR-0057). A question closed by its latest decision says so on its card. A
decision shows the analysis results its reason rests on, or that it names none
(ADR-0058). Synthetic data only (theme LIB).
"""

from __future__ import annotations

from skills._shared.tree_render import CitedEvent
from tests.test_tree_render import (
    Element,
    by_id,
    make_events,
    make_tree,
    node_card,
    node_text,
    page,
    squash,
)


def _decision(kind: str, node_id: str, round: int = 2, **over: object) -> dict:
    return {
        "round": round,
        "kind": kind,
        "node_id": node_id,
        "reason": "答えを見た",
    } | over


def _with(*decisions: dict, tree: dict | None = None) -> dict:
    tree = make_tree() if tree is None else tree
    tree["decisions"] += list(decisions)
    return tree


def _meta(root: Element, node_id: str) -> str:
    """The line under the question of a card: progress, contribution, origin."""
    (meta,) = [
        e
        for e in node_card(root, node_id).children
        if e.tag == "p" and "meta" in (e.attrs.get("class") or "")
    ]
    return squash(meta.text())


class TestProgressOfAQuestionWithoutADesign:
    """US-3 AC 2: a question with nodes under it and no design shows their progress."""

    def test_the_subject_shows_the_progress_below_it_instead_of_a_word(self) -> None:
        meta = _meta(page(), "LIB-Q01")

        assert "主題の下に置いた論点 4 つ: 分析済み 1、検証中 1、未着手 2" in meta
        assert "進捗:" not in meta

    def test_a_question_with_a_design_keeps_its_word_and_adds_the_counts_below(
        self,
    ) -> None:
        meta = _meta(page(), "LIB-Q02")

        assert "進捗: 分析済み" in meta
        assert "この論点の下に置いた論点 1 つ: 未着手 1" in meta

    def test_a_question_with_nothing_under_it_keeps_its_word_alone(self) -> None:
        meta = _meta(page(), "LIB-Q05")

        assert "進捗: 未着手" in meta
        assert "下に置いた論点" not in meta

    def test_the_counts_reach_every_depth_and_skip_a_question_shown_by_its_counts(
        self,
    ) -> None:
        tree = make_tree()
        # LIB-Q05 gets a question under it, so it too is shown by its counts.
        tree["nodes"].append(
            {
                "id": "LIB-Q06",
                "question": "延長した館で予約は減ったか",
                "parent_question_id": "LIB-Q05",
                "contribution": "減らないなら、試行の意味が薄い",
            }
        )
        root = page(tree=tree)

        assert "この論点の下に置いた論点 1 つ: 未着手 1" in _meta(root, "LIB-Q05")
        assert "主題の下に置いた論点 4 つ: 分析済み 1、検証中 1、未着手 2" in _meta(
            root, "LIB-Q01"
        )

    def test_the_counts_of_the_page_leave_out_a_question_shown_by_its_counts(
        self,
    ) -> None:
        counts = squash(by_id(page(), "counts").text())

        assert "未着手 2" in counts
        assert "検証中 1" in counts
        assert "分析済み 1" in counts

    def test_the_legend_says_how_such_a_question_shows_its_progress(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        assert "下に置いた論点の進捗を、言葉ごとの数で出す" in legend


def _closed(*after: dict, round: int = 2, **over: object) -> dict:
    """LIB-Q03 gone to from the start, then closed; *after* follow the close."""
    return _with(
        _decision("return", "LIB-Q03", round=round),
        _decision("close", "LIB-Q03", round=round, **over),
        *after,
    )


class TestAClosedQuestion:
    """US-3 AC 3: the latest decision naming a question closed it."""

    def test_the_card_says_the_round_it_was_closed_after_and_why(self) -> None:
        tree = _closed(reason="比べられる館が足りないので止める")

        shown = node_text(page(tree=tree), "LIB-Q03")

        assert (
            "回 2 の振り返りの後に区切った。理由: 比べられる館が足りないので止める"
            in (shown)
        )

    def test_a_question_named_again_after_it_was_closed_no_longer_says_so(
        self,
    ) -> None:
        tree = _closed(_decision("deepen", "LIB-Q03"))

        assert "区切った" not in node_text(page(tree=tree), "LIB-Q03")

    def test_a_question_never_closed_says_nothing_of_it(self) -> None:
        assert "区切った" not in node_text(page(), "LIB-Q03")

    def test_a_close_taken_before_any_reflection_says_so(self) -> None:
        tree = _closed(round=0)

        assert "振り返りの前に区切った" in node_text(page(tree=tree), "LIB-Q03")

    def test_the_reason_shows_what_it_rests_on(self) -> None:
        tree = _closed(cites=["LIB-H01-E02"])

        shown = node_text(page(tree=tree), "LIB-Q03")

        assert "この理由の根拠にした分析結果" in shown
        assert "取消の理由列は空欄が多い" in shown


class TestWhatADecisionRestsOn:
    """US-4 AC 3: the cited results under the reason, or that it names none."""

    def test_each_cited_result_shows_its_id_design_and_text(self) -> None:
        tree = _with(_decision("deepen", "LIB-Q04", cites=["LIB-H01-E02"]))

        (row,) = [
            squash(li.text())
            for li in by_id(page(tree=tree), "decisions").children[1].children
            if "深める" in li.text()
        ]

        assert row.index("答えを見た") < row.index("この理由の根拠にした分析結果")
        assert "LIB-H01-E02" in row
        assert "分析設計 LIB-H01" in row
        assert "取消の理由列は空欄が多い" in row

    def test_the_results_come_in_the_order_the_decision_cites_them(self) -> None:
        tree = _with(
            _decision("deepen", "LIB-Q04", cites=["LIB-H01-E02", "LIB-H01-E01"])
        )

        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert shown.index("取消の理由列は空欄が多い") < shown.index(
            "期限切れは取消除外で 346 件"
        )

    def test_a_decision_that_cites_nothing_says_so(self) -> None:
        tree = _with(_decision("deepen", "LIB-Q04"))

        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert shown.endswith(
            "答えを見たこの理由は、根拠にした分析結果を挙げていない。"
        )

    def test_the_first_decision_does_not_say_it_cites_nothing(self) -> None:
        assert "挙げていない" not in by_id(page(), "decisions").text()

    def test_the_next_question_shows_the_same_under_its_reason(self) -> None:
        tree = _with(_decision("return", "LIB-Q05", cites=["LIB-H01-E01"]))

        shown = squash(by_id(page(tree=tree), "next-question").text())

        assert shown.index("理由: 答えを見た") < shown.index(
            "この理由の根拠にした分析結果"
        )
        assert "期限切れは取消除外で 346 件" in shown

    def test_the_next_question_says_when_its_reason_cites_nothing(self) -> None:
        tree = _with(_decision("return", "LIB-Q05"))

        shown = squash(by_id(page(tree=tree), "next-question").text())

        assert "この理由は、根拠にした分析結果を挙げていない。" in shown

    def test_what_a_person_said_is_not_called_an_analysis_result(self) -> None:
        events = make_events()
        events["LIB-H01-E03"] = CitedEvent(
            "LIB-H01-E03", "hearing", None, "金曜は月曜にまとめて通知する"
        )
        tree = _with(_decision("deepen", "LIB-Q04", cites=["LIB-H01-E03"]))

        shown = squash(by_id(page(tree=tree, events=events), "decisions").text())

        assert "この理由の根拠にした人に聞いた答え" in shown
        assert "この理由の根拠にした分析結果" not in shown

    def test_both_words_are_named_when_the_reason_rests_on_both(self) -> None:
        events = make_events()
        events["LIB-H01-E03"] = CitedEvent(
            "LIB-H01-E03", "hearing", None, "金曜は月曜にまとめて通知する"
        )
        tree = _with(
            _decision("deepen", "LIB-Q04", cites=["LIB-H01-E01", "LIB-H01-E03"])
        )

        shown = squash(by_id(page(tree=tree, events=events), "decisions").text())

        assert "この理由の根拠にした分析結果と人に聞いた答え" in shown

    def test_a_cited_result_missing_from_the_record_says_so(self) -> None:
        tree = _with(_decision("deepen", "LIB-Q04", cites=["LIB-H01-E09"]))

        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert "記録に見つからない LIB-H01-E09" in shown

    def test_an_id_two_records_share_shows_neither_text(self) -> None:
        tree = _with(_decision("deepen", "LIB-Q04", cites=["LIB-H01-E02"]))

        shown = squash(
            by_id(page(tree=tree, shared=["LIB-H01-E02"]), "decisions").text()
        )

        assert "LIB-H01-E02 は記録に2つあり、どちらを根拠にしたかは分からない" in shown
        assert "取消の理由列は空欄が多い" not in shown

    def test_an_id_two_records_share_takes_no_word_from_the_one_kept(self) -> None:
        """The event kept for a shared id may not be the one the decision cites."""
        events = make_events()
        events["LIB-H01-E02"] = CitedEvent(
            "LIB-H01-E02", "hearing", None, "金曜は月曜にまとめて通知する"
        )
        tree = _with(_decision("deepen", "LIB-Q04", cites=["LIB-H01-E02"]))

        shown = squash(
            by_id(
                page(tree=tree, events=events, shared=["LIB-H01-E02"]), "decisions"
            ).text()
        )

        assert "この理由の根拠にした分析結果" in shown
        assert "人に聞いた答え" not in shown
