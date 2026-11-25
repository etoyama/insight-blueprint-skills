"""Tests for tree_render, the pure HTML view of a question tree (Epic 18, Story 18.6).

The page is read the way a reader reads it, so the tests parse it with
``html.parser`` and ask what text sits in which element. Synthetic data only
(public-library holds, theme LIB).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import get_args

import pytest

from insight_blueprint.models.design import (
    CONCLUSIONS_OF,
    TERMINAL_STATUSES,
    DesignForm,
    DesignStatus,
)
from insight_blueprint.models.tree import (
    AimKind,
    Progress,
    QuestionTree,
    StatementKind,
    TreeDecisionKind,
)
from insight_blueprint.validate import validate_tree_schema
from skills._shared import tree_render
from skills._shared._html import Html
from skills._shared.design_note import intent_words_of, status_word
from skills._shared.tree_check import Violation, ViolationKind
from skills._shared.tree_render import (
    CheckFailed,
    CitedEvent,
    DesignSummary,
    render_tree_html,
)

BUSINESS_AIM = {
    "kind": "business",
    "decision_maker": "図書館員",
    "decision": "取り置き期限を延ばす試行を始めるか",
}
RESEARCH_AIM = {
    "kind": "research",
    "audience": "司書",
    "claim_scope": "1館の2024年度",
}
OLD_QUESTION = "取り置き期限を延ばすと予約は減るか"
ROOT_QUESTION = "取り置き期限を延ばす試行をするか"

HOSTILE = '<script>alert(1)</script>" onmouseover="x'


class Element:
    def __init__(
        self, tag: str, attrs: dict[str, str | None], parent: Element | None
    ) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[Element] = []
        self.parts: list[str | Element] = []

    def text(self) -> str:
        return "".join(p if isinstance(p, str) else p.text() for p in self.parts)

    def walk(self) -> Iterator[Element]:
        yield self
        for child in self.children:
            yield from child.walk()

    def is_inside(self, other: Element) -> bool:
        node = self.parent
        while node is not None:
            if node is other:
                return True
            node = node.parent
        return False


class _Builder(HTMLParser):
    VOID = {"meta", "br", "hr", "img", "input", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#root", {}, None)
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(tag, dict(attrs), self.current)
        self.current.children.append(element)
        self.current.parts.append(element)
        if tag not in self.VOID:
            self.current = element

    def handle_endtag(self, tag: str) -> None:
        node = self.current
        while node.parent is not None and node.tag != tag:
            node = node.parent
        if node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        self.current.parts.append(data)


def parse(page: str) -> Element:
    builder = _Builder()
    builder.feed(page)
    return builder.root


def by_id(root: Element, element_id: str) -> Element:
    found = [e for e in root.walk() if e.attrs.get("id") == element_id]
    assert len(found) == 1, f"expected one element with id {element_id}: {len(found)}"
    return found[0]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def make_tree(**over: object) -> dict:
    """Four questions under the root, answered in two reflection rounds.

    LIB-Q02: two answers, the second (round 2) differs from the first.
    LIB-Q03: linked to a design still analyzing, no answer.
    LIB-Q04: first answered in round 2, nested under LIB-Q02.
    LIB-Q05: answered once, in round 1, against root revision 1.
    """
    tree: dict = {
        "theme_id": "LIB",
        "root_revisions": [
            {"revision": 1, "question": OLD_QUESTION, "aim": BUSINESS_AIM},
            {
                "revision": 2,
                "question": ROOT_QUESTION,
                "aim": BUSINESS_AIM,
                "reason": "到達点が、減るかどうかから、試行をするかどうかに変わった",
            },
        ],
        "nodes": [
            {"id": "LIB-Q01", "question": ROOT_QUESTION},
            {
                "id": "LIB-Q02",
                "question": "期限切れを一貫して数えられるか",
                "parent_question_id": "LIB-Q01",
                "contribution": "予約取消が混ざると、延長で改善しうる件数が変わる",
                "design_ids": ["LIB-H01"],
                "answers": [
                    {
                        "round": 1,
                        "root_revision": 1,
                        "statements": [
                            {
                                "kind": "claim",
                                "text": "取消を含めると期限切れは 400 件",
                                "cites": ["LIB-H01-E01"],
                            }
                        ],
                    },
                    {
                        "round": 2,
                        "root_revision": 2,
                        "statements": [
                            {
                                "kind": "claim",
                                "text": "取消を除くと期限切れは 346 件",
                                "cites": ["LIB-H01-E01"],
                            },
                            {
                                "kind": "weakening",
                                "text": "1館の1年度だけの数である",
                                "cites": ["LIB-H01-E02"],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "LIB-Q03",
                "question": "通知は期限の何日前に届くか",
                "parent_question_id": "LIB-Q01",
                "contribution": "通知が遅いと、延長の効果が見えない",
                "design_ids": ["LIB-H02"],
            },
            {
                "id": "LIB-Q04",
                "question": "取消の理由に偏りはあるか",
                "parent_question_id": "LIB-Q02",
                "contribution": "偏りがあれば、取消を除く根拠が変わる",
                "origin_event_id": "LIB-H01-E02",
                "answers": [
                    {
                        "round": 2,
                        "root_revision": 2,
                        "statements": [
                            {
                                "kind": "undetermined",
                                "text": "理由の記録が無く、偏りは判別できない",
                                "cites": ["LIB-H01-E02"],
                            }
                        ],
                    }
                ],
            },
            {
                "id": "LIB-Q05",
                "question": "延長で予約は減るか",
                "parent_question_id": "LIB-Q01",
                "contribution": "減らないなら、試行の意味が薄い",
                "answers": [
                    {
                        "round": 1,
                        "root_revision": 1,
                        "statements": [
                            {
                                "kind": "claim",
                                "text": "延長で予約が減るとは言えない",
                                "cites": ["LIB-H03-E01"],
                            }
                        ],
                    }
                ],
            },
        ],
        "decisions": [
            {
                "round": 0,
                "kind": "start",
                "node_id": "LIB-Q02",
                "reason": "件数が変わるので、最初に数え方を固める",
            }
        ],
    }
    tree.update(over)
    return tree


def build(tree: dict | None = None) -> QuestionTree:
    return validate_tree_schema(
        copy.deepcopy(tree if tree is not None else make_tree())
    )


JST = timezone(timedelta(hours=9))
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=JST)


def summary(
    id: str,
    title: str,
    status: str,
    parent_id: str | None,
    created_at: datetime = T0,
    *,
    form: DesignForm | None = None,
    intent: str | None = None,
    statement: str = "",
    comments_after_analysis: int = 0,
) -> DesignSummary:
    """A design as the page sees it. An explored design is an exploration unless told."""
    if form is None:
        form = (
            DesignForm.exploration if status == "explored" else DesignForm.confirmation
        )
    return DesignSummary(
        id,
        title,
        DesignStatus(status),
        parent_id,
        created_at,
        form=form,
        intent=intent_words_of(form)[0] if intent is None else intent,
        statement=statement,
        comments_after_analysis=comments_after_analysis,
    )


def stub_design_notes(designs: dict[str, DesignSummary]) -> dict[str, Html]:
    """What render_note returns, reduced to the section the page needs."""
    return {
        d: Html(
            f'<section class="design-note" id="note-{d}"><h2>分析ノート {d}</h2></section>'
        )
        for d in designs
    }


def make_designs() -> dict[str, DesignSummary]:
    return {
        "LIB-H01": summary("LIB-H01", "取消を除く数え方", "supported", None),
        "LIB-H02": summary("LIB-H02", "通知の遅れを測る", "analyzing", "LIB-H01"),
        "LIB-H04": summary("LIB-H04", "貸出の季節差", "in_review", "LIB-H99"),
    }


def make_events() -> dict[str, CitedEvent]:
    return {
        "LIB-H01-E01": CitedEvent(
            "LIB-H01-E01", "evidence", "supports", "期限切れは取消除外で 346 件"
        ),
        "LIB-H01-E02": CitedEvent(
            "LIB-H01-E02", "observe", None, "取消の理由列は空欄が多い"
        ),
    }


def render(
    tree: dict | None = None,
    designs: dict[str, DesignSummary] | None = None,
    events: dict[str, CitedEvent] | None = None,
    violations: list[Violation] | CheckFailed | None = None,
    design_notes: dict[str, Html] | None = None,
) -> str:
    shown = make_designs() if designs is None else designs
    return render_tree_html(
        build(tree),
        shown,
        make_events() if events is None else events,
        [] if violations is None else violations,
        stub_design_notes(shown) if design_notes is None else design_notes,
    )


def page(
    tree: dict | None = None,
    designs: dict[str, DesignSummary] | None = None,
    events: dict[str, CitedEvent] | None = None,
    violations: list[Violation] | CheckFailed | None = None,
    design_notes: dict[str, Html] | None = None,
) -> Element:
    return parse(render(tree, designs, events, violations, design_notes))


class TestSelfContained:
    @pytest.mark.parametrize(
        "forbidden",
        [
            "<script",
            "<link",
            "<img",
            "<iframe",
            "@import",
            "url(",
            "http://",
            "https://",
        ],
    )
    def test_the_page_names_no_script_stylesheet_link_image_import_or_url(
        self, forbidden: str
    ) -> None:
        assert forbidden not in render().lower()

    def test_the_page_is_a_japanese_document_with_its_title(self) -> None:
        html = render()
        root = parse(html)

        assert html.startswith("<!doctype html>")
        (document,) = [e for e in root.walk() if e.tag == "html"]
        assert document.attrs["lang"] == "ja"
        (title,) = [e for e in root.walk() if e.tag == "title"]
        assert title.text() == "論点ツリー LIB"
        assert any(
            e.tag == "meta" and e.attrs.get("charset") == "utf-8" for e in root.walk()
        )

    def test_the_same_inputs_give_the_same_page_whatever_the_insertion_order(
        self,
    ) -> None:
        designs, events = make_designs(), make_events()
        forward = render(designs=designs, events=events)
        backward = render(
            designs=dict(reversed(list(designs.items()))),
            events=dict(reversed(list(events.items()))),
        )

        assert forward == backward
        assert forward == render(designs=designs, events=events)


class TestHeader:
    def test_the_root_question_and_the_business_aim_carry_their_labels(self) -> None:
        header = by_id(page(), "header").text()

        assert ROOT_QUESTION in header
        assert "決める人: 図書館員" in squash(header)
        assert "決めること: 取り置き期限を延ばす試行を始めるか" in squash(header)
        assert "根の版 2" in squash(header)

    def test_a_research_aim_carries_its_own_labels(self) -> None:
        tree = make_tree()
        for revision in tree["root_revisions"]:
            revision["aim"] = RESEARCH_AIM

        header = squash(by_id(page(tree=tree), "header").text())

        assert "想定読者: 司書" in header
        assert "主張の範囲: 1館の2024年度" in header
        assert "決める人" not in header

    def test_the_history_of_root_revisions_keeps_the_earlier_question_and_reason(
        self,
    ) -> None:
        history = squash(by_id(page(), "root-history").text())

        assert OLD_QUESTION in history
        assert "到達点が、減るかどうかから、試行をするかどうかに変わった" in history

    def test_a_single_root_revision_shows_no_history(self) -> None:
        tree = make_tree()
        tree["root_revisions"] = tree["root_revisions"][1:]
        tree["root_revisions"][0].update(revision=1, reason="")
        for node in tree["nodes"]:
            for answer in node.get("answers", []):
                answer["root_revision"] = 1

        html = render(tree=tree)

        assert "root-history" not in html
        assert "根の変更前の答え" not in by_id(parse(html), "question-tree").text()


class TestLegend:
    def test_the_legend_explains_how_to_read_the_page(self) -> None:
        legend = squash(by_id(page(), "legend").text())

        for word in ("未着手", "検証中", "分析済み"):
            assert word in legend
        for word in ("言えること", "未判別", "弱める証拠と留保"):
            assert word in legend
        for word in (
            "回 N で変わった",
            "根の変更前の答え",
            "回 N で初めて答えた",
            "記録と合わない答え",
        ):
            assert word in legend
        assert "根拠を開く" in legend
        assert "論点の親子" in legend
        assert "分析設計の派生" in legend

    def test_the_legend_explains_the_jump_to_a_note_and_the_way_back(self) -> None:
        paragraphs = [
            squash(e.text()) for e in by_id(page(), "legend").walk() if e.tag == "p"
        ]

        (explained,) = [p for p in paragraphs if "分析ノートを開く" in p]
        assert "このページの下" in explained
        assert "論点ツリーへ戻る" in explained


def node_text(root: Element, node_id: str) -> str:
    """Text of the always-visible part of a node, without its folded details."""
    node = by_id(root, node_id)
    folded = {id(e) for d in node.walk() if d.tag == "details" for e in d.walk()}
    nested = {
        id(e) for child in node.children if child.tag == "ul" for e in child.walk()
    }
    parts: list[str] = []

    def collect(element: Element) -> None:
        for part in element.parts:
            if isinstance(part, str):
                parts.append(part)
            elif id(part) not in folded and id(part) not in nested:
                collect(part)

    collect(node)
    return squash(" ".join(parts))


def details_text(root: Element, node_id: str) -> str:
    node = by_id(root, node_id)
    nested = [e for e in node.children if e.tag == "ul"]
    (details,) = [
        e
        for e in node.walk()
        if e.tag == "details" and not any(e.is_inside(n) for n in nested)
    ]
    return squash(details.text())


class TestProgress:
    def test_each_node_says_its_progress_in_a_word(self) -> None:
        root = page()

        assert "進捗: 分析済み" in node_text(root, "LIB-Q02")
        assert "進捗: 検証中" in node_text(root, "LIB-Q03")
        assert "進捗: 未着手" in node_text(root, "LIB-Q04")

    def test_the_counts_of_nodes_per_progress_word_are_shown(self) -> None:
        counts = squash(by_id(page(), "counts").text())

        assert "未着手 3" in counts
        assert "検証中 1" in counts
        assert "分析済み 1" in counts

    def test_a_linked_design_missing_from_the_designs_is_an_error(self) -> None:
        designs = make_designs()
        del designs["LIB-H01"]

        with pytest.raises(ValueError, match="LIB-H01"):
            render(designs=designs)


class TestCurrentAnswer:
    def test_the_current_answer_is_text_with_the_word_for_each_kind(self) -> None:
        shown = node_text(page(), "LIB-Q02")

        assert "言えること 取消を除くと期限切れは 346 件" in shown
        assert "弱める証拠と留保 1館の1年度だけの数である" in shown
        assert "振り返りの回 2" in shown
        assert "400 件" not in shown

    def test_an_undetermined_statement_carries_its_word(self) -> None:
        assert "未判別 理由の記録が無く、偏りは判別できない" in node_text(
            page(), "LIB-Q04"
        )

    def test_a_node_without_an_answer_says_so(self) -> None:
        assert "まだ答えていない" in node_text(page(), "LIB-Q03")


class TestHeardStatements:
    """ADR-0028: a statement that rests only on what a person said is told apart."""

    def _heard(self, *event_ids: str) -> dict[str, CitedEvent]:
        events = make_events()
        for event_id in event_ids:
            events[event_id] = CitedEvent(
                event_id, "hearing", None, "集計は年度ごとに別の館が行う"
            )
        return events

    def test_a_statement_citing_only_hearing_events_says_so(self) -> None:
        shown = node_text(page(events=self._heard("LIB-H01-E02")), "LIB-Q02")

        assert "1館の1年度だけの数である （人に聞いた答えによる）" in shown

    def test_a_statement_citing_an_event_of_the_data_carries_no_such_word(
        self,
    ) -> None:
        shown = node_text(page(events=self._heard("LIB-H01-E02")), "LIB-Q02")

        assert "取消を除くと期限切れは 346 件 （人に聞いた答えによる）" not in shown
        assert shown.count("（人に聞いた答えによる）") == 1

    def test_a_statement_citing_a_hearing_and_the_data_carries_no_such_word(
        self,
    ) -> None:
        tree = make_tree()
        statement = tree["nodes"][1]["answers"][-1]["statements"][1]
        statement["cites"] = ["LIB-H01-E01", "LIB-H01-E02"]

        shown = node_text(page(tree=tree, events=self._heard("LIB-H01-E02")), "LIB-Q02")

        assert "（人に聞いた答えによる）" not in shown

    def test_a_cited_event_that_is_missing_is_not_taken_for_a_hearing(self) -> None:
        events = make_events()
        del events["LIB-H01-E02"]

        assert "（人に聞いた答えによる）" not in node_text(
            page(events=events), "LIB-Q02"
        )

    def test_the_legend_explains_the_word(self) -> None:
        assert "人に聞いた答えによる" in squash(by_id(page(), "legend").text())


class TestDecisions:
    def test_a_decision_shows_its_kind_node_and_reason(self) -> None:
        root = page()
        decisions = by_id(root, "decisions")

        assert "件数が変わるので、最初に数え方を固める" in decisions.text()
        assert "LIB-Q02" in decisions.text()
        link = next(e for e in decisions.walk() if e.tag == "a")
        assert link.attrs["href"] == "#LIB-Q02"
        assert "最初の論点を選ぶ" in decisions.text()

    def test_a_tree_without_decisions_still_renders(self) -> None:
        tree = make_tree()
        del tree["decisions"]

        assert "まだ決めていない" in by_id(page(tree=tree), "decisions").text()


class TestDecisionRounds:
    @staticmethod
    def _with(*decisions: dict) -> dict:
        tree = make_tree()
        tree["decisions"] += list(decisions)
        return tree

    @staticmethod
    def _decision(kind: str, node_id: str, round: int = 2) -> dict:
        return {
            "round": round,
            "kind": kind,
            "node_id": node_id,
            "reason": "答えを見た",
        }

    @pytest.mark.parametrize(
        ("kind", "node_id", "label"),
        [
            ("deepen", "LIB-Q04", "深める"),
            ("return", "LIB-Q05", "親に戻る"),
            ("close", "LIB-Q02", "区切る"),
        ],
    )
    def test_each_kind_shows_its_word_and_the_round_it_was_taken_at(
        self, kind: str, node_id: str, label: str
    ) -> None:
        tree = self._with(self._decision(kind, node_id))
        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert f"{label}（回 2 の振り返りの後）: {node_id} 答えを見た" in shown

    def test_a_decision_taken_before_any_reflection_says_so_instead_of_naming_round_0(
        self,
    ) -> None:
        tree = self._with(self._decision("deepen", "LIB-Q02", round=0))
        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert "深める（振り返りの前）: LIB-Q02 答えを見た" in shown
        assert "回 0" not in shown

    def test_the_start_decision_names_no_round(self) -> None:
        shown = squash(by_id(page(), "decisions").text())

        assert "最初の論点を選ぶ: LIB-Q02" in shown
        assert "答えを見て" not in shown

    def test_decisions_come_in_the_order_they_were_taken(self) -> None:
        tree = self._with(
            self._decision("deepen", "LIB-Q04"), self._decision("close", "LIB-Q04")
        )
        shown = squash(by_id(page(tree=tree), "decisions").text())

        assert shown.index("最初の論点を選ぶ") < shown.index("深める")
        assert shown.index("深める") < shown.index("区切る")


class TestMarks:
    def test_an_answer_that_differs_in_the_latest_round_is_marked_as_changed(
        self,
    ) -> None:
        shown = node_text(page(), "LIB-Q02")

        assert "回 2 で変わった" in shown
        assert "初めて答えた" not in shown

    def test_the_previous_answer_is_shown_behind_a_changed_answer(self) -> None:
        folded = details_text(page(), "LIB-Q02")

        assert "取消を含めると期限切れは 400 件" in folded
        assert "前の回の答え" in folded

    def test_an_answer_first_written_in_the_latest_round_is_marked_as_first(
        self,
    ) -> None:
        shown = node_text(page(), "LIB-Q04")

        assert "回 2 で初めて答えた" in shown
        assert "変わった" not in shown

    def test_an_answer_from_an_earlier_round_carries_no_changed_mark(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert "変わった" not in shown
        assert "初めて答えた" not in shown

    def test_an_answer_rewritten_with_identical_statements_carries_no_mark(
        self,
    ) -> None:
        tree = make_tree()
        answers = tree["nodes"][1]["answers"]
        answers[0]["statements"] = answers[1]["statements"]

        shown = node_text(page(tree=tree), "LIB-Q02")

        assert "変わった" not in shown
        assert "初めて答えた" not in shown

    def test_an_answer_written_against_an_older_root_revision_is_marked(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert "根の変更前の答え（根の版 1 への答え）" in shown

    def test_an_answer_of_the_current_root_revision_is_not_marked_stale(self) -> None:
        assert "根の変更前の答え" not in node_text(page(), "LIB-Q02")


def with_note(tree: dict, node_id: str, **note: object) -> dict:
    next(n for n in tree["nodes"] if n["id"] == node_id)["next_candidate"] = note
    return tree


HEARD = {
    "ask": "予約取消は、窓口でどれくらい起きますか",
    "changes_if": "取消が多ければ延長を見送る",
    "known": "カタログに取消フラグがある",
    "answer": "月に十数件で、ほとんどが電話での取消",
    "answered_by": "窓口の職員",
    "answered_at": "2026-11-21",
}


class TestNextCandidates:
    def test_the_untouched_nodes_are_listed_in_tree_order_with_their_question(
        self,
    ) -> None:
        section = by_id(page(), "next-candidates")
        items = [e for e in section.walk() if e.tag == "li"]

        shown = [squash(i.text()) for i in items]
        assert len(shown) == 2
        assert shown[0].startswith("LIB-Q04 取消の理由に偏りはあるか")
        assert shown[1].startswith("LIB-Q05 延長で予約は減るか")

    def test_a_node_with_a_linked_design_is_not_a_candidate(self) -> None:
        shown = squash(by_id(page(), "next-candidates").text())

        assert "LIB-Q02" not in shown
        assert "LIB-Q03" not in shown

    def test_the_notes_are_shown_with_who_answered_and_when(self) -> None:
        tree = with_note(make_tree(), "LIB-Q05", **HEARD)
        section = squash(by_id(page(tree=tree), "next-candidates").text())

        assert "人に聞く問い: 予約取消は、窓口でどれくらい起きますか" in section
        assert "その答えで変わる判断: 取消が多ければ延長を見送る" in section
        assert "分かっていること: カタログに取消フラグがある" in section
        assert (
            "聞いてきた答え: 月に十数件で、ほとんどが電話での取消（窓口の職員、2026-11-21）"
            in section
        )

    def test_a_node_without_notes_says_it_has_none(self) -> None:
        assert "まだメモは無い" in squash(by_id(page(), "next-candidates").text())

    def test_unanswered_notes_show_no_heard_line(self) -> None:
        tree = with_note(make_tree(), "LIB-Q05", ask=HEARD["ask"])
        section = squash(by_id(page(tree=tree), "next-candidates").text())

        assert "人に聞く問い" in section
        assert "聞いてきた答え:" not in section

    def test_the_notes_also_sit_in_the_card_of_the_node(self) -> None:
        tree = with_note(make_tree(), "LIB-Q05", **HEARD)

        assert "聞いてきた答え: 月に十数件" in node_text(page(tree=tree), "LIB-Q05")

    def test_a_started_node_keeps_its_notes_in_its_card_and_leaves_the_list(
        self,
    ) -> None:
        tree = with_note(make_tree(), "LIB-Q03", **HEARD)
        root = page(tree=tree)

        assert "人に聞く問い" in node_text(root, "LIB-Q03")
        assert "LIB-Q03" not in squash(by_id(root, "next-candidates").text())

    def test_a_tree_where_every_node_is_started_says_so(self) -> None:
        tree = make_tree()
        for node in tree["nodes"][1:]:
            node["design_ids"] = ["LIB-H01"]

        assert (
            "着手していない論点は無い"
            in by_id(page(tree=tree), "next-candidates").text()
        )

    def test_the_legend_points_at_the_section(self) -> None:
        assert "次の候補" in by_id(page(), "legend").text()


def stale() -> list[Violation]:
    return [
        Violation("LIB-Q02", 2, 1, "number-not-cited", "346"),
        Violation("LIB-Q02", 2, 2, "missing-event", "LIB-H01-E99"),
    ]


def violation_page() -> Element:
    return page(violations=stale())


class TestViolatingAnswers:
    def test_the_node_carries_the_mark_instead_of_the_answer_marks(self) -> None:
        shown = node_text(violation_page(), "LIB-Q02")

        assert "記録と合わない答え" in shown
        assert "変わった" not in shown

    def test_the_text_of_the_answer_is_not_shown_as_the_current_answer(self) -> None:
        shown = node_text(violation_page(), "LIB-Q02")

        assert "取消を除くと期限切れは 346 件" not in shown
        assert "1館の1年度だけの数である" not in shown

    def test_the_opened_node_lists_each_violation_with_its_kind_and_text(self) -> None:
        node = by_id(violation_page(), "LIB-Q02")
        folded = squash(next(e for e in node.walk() if e.tag == "details").text())

        assert "文 1: 引用した出来事に無い数字（number-not-cited）" in folded
        assert "346" in folded
        assert "文 2: journal に無い出来事（missing-event）" in folded
        assert "LIB-H01-E99" in folded

    def test_the_statements_stay_inside_a_closed_details(self) -> None:
        node = by_id(violation_page(), "LIB-Q02")
        inner = [
            e
            for e in node.walk()
            if e.tag == "details" and e.parent is not None and e.parent.tag == "details"
        ]

        (statements,) = inner
        assert "open" not in statements.attrs
        assert "取消を除くと期限切れは 346 件" in squash(statements.text())

    def test_other_nodes_are_unmarked(self) -> None:
        shown = node_text(violation_page(), "LIB-Q04")

        assert "記録と合わない答え" not in shown
        assert "回 2 で初めて答えた" in shown

    def test_a_violation_does_not_hide_the_stale_root_mark(self) -> None:
        violations = [Violation("LIB-Q05", 1, 1, "missing-event", "LIB-H03-E01")]
        shown = node_text(page(violations=violations), "LIB-Q05")

        assert "記録と合わない答え" in shown
        assert "根の変更前の答え" in shown

    def test_no_violation_means_no_mark_and_no_notice(self) -> None:
        root = page()

        assert "記録と合わない答え" not in squash(by_id(root, "question-tree").text())
        assert not [e for e in root.walk() if e.attrs.get("id") == "check-notice"]

    def test_every_violation_kind_has_its_word(self) -> None:
        assert set(tree_render._VIOLATION_WORDS) == set(get_args(ViolationKind))


class TestCheckCouldNotRun:
    def test_the_page_says_the_answers_were_not_checked_against_the_record(
        self,
    ) -> None:
        root = page(violations=CheckFailed("journal event 'LIB-H01-E01' appears twice"))
        notice = squash(by_id(root, "check-notice").text())

        assert "確かめられなかった" in notice
        assert "appears twice" in notice

    def test_the_answers_are_still_shown_without_a_mark(self) -> None:
        root = page(violations=CheckFailed("x"))

        assert "取消を除くと期限切れは 346 件" in node_text(root, "LIB-Q02")
        assert "記録と合わない答え" not in node_text(root, "LIB-Q02")


class TestEvidence:
    def test_the_details_hold_each_cited_event_with_its_design_and_direction(
        self,
    ) -> None:
        folded = details_text(page(), "LIB-Q02")

        assert "根拠を開く" in folded
        assert "LIB-H01-E01" in folded
        assert "期限切れは取消除外で 346 件" in folded
        assert "design: LIB-H01" in folded
        assert "direction: supports（検証仮説を支持する）" in folded
        assert "type: evidence" in folded

    def test_the_cited_design_is_an_in_page_link(self) -> None:
        details = next(e for e in by_id(page(), "LIB-Q02").walk() if e.tag == "details")

        hrefs = {e.attrs["href"] for e in details.walk() if e.tag == "a"}
        assert "#design-LIB-H01" in hrefs

    def test_an_event_that_is_not_evidence_shows_its_type_and_no_direction(
        self,
    ) -> None:
        folded = details_text(page(), "LIB-Q04")

        assert "type: observe" in folded
        assert "取消の理由列は空欄が多い" in folded
        assert "direction" not in folded

    def test_a_cited_event_that_does_not_exist_is_said_to_be_missing(self) -> None:
        folded = details_text(page(), "LIB-Q05")

        assert "journal に見つからない出来事" in folded
        assert "LIB-H03-E01" in folded

    def test_an_unknown_direction_is_shown_as_written(self) -> None:
        events = make_events()
        events["LIB-H01-E01"] = CitedEvent("LIB-H01-E01", "evidence", "mixed", "本文")

        assert "direction: mixed" in details_text(page(events=events), "LIB-Q02")

    def test_a_legacy_exploration_glosses_the_direction_with_its_hypothesis(
        self,
    ) -> None:
        designs = make_designs()
        designs["LIB-H01"] = summary(
            "LIB-H01", "t", "supported", None, form=DesignForm.legacy_exploration
        )

        folded = details_text(page(designs=designs), "LIB-Q02")

        assert "direction: supports（仮説を支持する）" in folded

    def test_an_exploration_shows_no_direction_even_when_its_event_has_one(
        self,
    ) -> None:
        designs = make_designs()
        designs["LIB-H01"] = summary("LIB-H01", "t", "explored", None)
        events = make_events()
        events["LIB-H01-E01"] = CitedEvent(
            "LIB-H01-E01", "evidence", "contradicts", "期限切れは取消除外で 346 件"
        )

        folded = details_text(page(designs=designs, events=events), "LIB-Q02")

        assert "type: evidence" in folded
        assert "direction" not in folded
        assert "反する" not in folded

    def test_the_details_no_longer_list_the_linked_designs(self) -> None:
        folded = details_text(page(), "LIB-Q03")

        assert "結んだ分析設計" not in folded
        assert "LIB-H02" not in folded


class TestStructure:
    def test_a_child_is_nested_in_its_parent_and_shows_its_contribution(self) -> None:
        root = page()

        assert by_id(root, "LIB-Q02").is_inside(by_id(root, "LIB-Q01"))
        assert by_id(root, "LIB-Q04").is_inside(by_id(root, "LIB-Q02"))
        assert not by_id(root, "LIB-Q03").is_inside(by_id(root, "LIB-Q02"))
        assert "寄与: 予約取消が混ざると、延長で改善しうる件数が変わる" in node_text(
            root, "LIB-Q02"
        )
        assert "寄与" not in node_text(root, "LIB-Q01")

    def test_a_node_found_in_a_journal_event_names_its_origin(self) -> None:
        assert "発見元: LIB-H01-E02" in node_text(page(), "LIB-Q04")

    def test_a_derived_design_is_nested_under_its_parent_design(self) -> None:
        root = page()
        derivation = by_id(root, "derivation")

        assert by_id(root, "design-LIB-H02").is_inside(by_id(root, "design-LIB-H01"))
        assert by_id(root, "design-LIB-H02").is_inside(derivation)
        assert not by_id(root, "design-LIB-H02").is_inside(by_id(root, "question-tree"))
        assert not by_id(root, "LIB-Q02").is_inside(derivation)

    def test_each_design_names_the_nodes_that_link_it(self) -> None:
        root = page()
        design = by_id(root, "design-LIB-H01")
        links = [e for e in design.walk() if e.tag == "a"]

        assert any(e.attrs["href"] == "#LIB-Q02" for e in links)
        assert "論点に結んでいない" in by_id(root, "design-LIB-H04").text()
        assert "論点に結んでいない" not in design.text()

    def test_a_design_whose_parent_is_outside_the_theme_sits_at_the_top(self) -> None:
        root = page()
        derivation = by_id(root, "derivation")
        orphan = by_id(root, "design-LIB-H04")

        assert "派生元: LIB-H99" in squash(orphan.text())
        (listing,) = [e for e in derivation.children if e.tag == "ul"]
        top_level = [e for e in listing.children if e.tag == "li"]
        assert orphan in top_level

    def test_designs_that_derive_from_each_other_in_a_cycle_are_still_shown(
        self,
    ) -> None:
        designs = {
            "LIB-H01": summary("LIB-H01", "a", "analyzing", "LIB-H02"),
            "LIB-H02": summary("LIB-H02", "b", "analyzing", "LIB-H01"),
        }
        tree = make_tree()
        tree["nodes"][1]["answers"] = []
        tree["nodes"][3]["answers"] = []
        tree["nodes"][3]["origin_event_id"] = None
        tree["nodes"][2]["design_ids"] = ["LIB-H02"]

        root = page(tree=tree, designs=designs)

        assert by_id(root, "design-LIB-H01") is not None
        assert by_id(root, "design-LIB-H02") is not None


def branch_cards(root: Element, node_id: str) -> list[Element]:
    """The cards of the designs shown under a node, in page order (ADR-0051)."""
    node = by_id(root, node_id)
    nested = [e for e in node.children if e.tag == "ul"]
    return [
        card
        for listing in nested
        for item in listing.children
        if item.tag == "li" and "id" not in item.attrs
        for card in item.children
        if card.tag == "div"
    ]


def card_text(card: Element) -> str:
    return squash(card.text())


def card_of(root: Element, node_id: str, design_id: str) -> str:
    (text,) = [
        card_text(c) for c in branch_cards(root, node_id) if design_id in card_text(c)
    ]
    return text


def forms_page() -> Element:
    """LIB-Q02 links an exploration and LIB-Q03 a confirmation and a legacy one.

    LIB-H03 is linked to LIB-Q03 and LIB-Q05, so LIB-Q05 shows it as a short row.
    """
    tree = make_tree()
    tree["nodes"][2]["design_ids"] = ["LIB-H02", "LIB-H03"]
    tree["nodes"][4]["design_ids"] = ["LIB-H03"]
    designs = {
        "LIB-H01": summary(
            "LIB-H01",
            "期限切れの数え方",
            "explored",
            None,
            statement="取消を除くと、期限切れは何件か",
        ),
        "LIB-H02": summary(
            "LIB-H02",
            "通知の遅れと期限切れ",
            "supported",
            None,
            statement="通知が翌日以降の予約は期限切れが多い",
        ),
        "LIB-H03": summary(
            "LIB-H03",
            "曜日の差",
            "rejected",
            "LIB-H02",
            form=DesignForm.legacy_exploration,
            statement="金曜に確保した本は期限切れが多い",
        ),
        "LIB-H04": summary("LIB-H04", "貸出の季節差", "in_review", "LIB-H99"),
    }
    return page(tree=tree, designs=designs)


class TestDesignsUnderTheirNode:
    """US-4 AC 1, 3, 4: a design is a branch of the node that links it."""

    def test_a_linked_design_is_a_card_under_its_node_not_inside_the_node_card(
        self,
    ) -> None:
        root = forms_page()

        (card,) = branch_cards(root, "LIB-Q02")
        assert card.is_inside(by_id(root, "LIB-Q02"))
        assert card.is_inside(by_id(root, "question-tree"))
        assert "LIB-H01" not in node_text(root, "LIB-Q02")
        node_card = next(e for e in by_id(root, "LIB-Q02").children if e.tag == "div")
        assert card.attrs["class"] != node_card.attrs["class"]

    def test_the_designs_come_before_the_child_nodes(self) -> None:
        root = forms_page()
        (listing,) = [e for e in by_id(root, "LIB-Q02").children if e.tag == "ul"]

        items = [e for e in listing.children if e.tag == "li"]
        assert "id" not in items[0].attrs
        assert items[1].attrs["id"] == "LIB-Q04"

    def test_an_exploration_card_holds_id_title_intent_question_status_and_note(
        self,
    ) -> None:
        (card,) = branch_cards(forms_page(), "LIB-Q02")
        text = card_text(card)

        assert "LIB-H01" in text
        assert "期限切れの数え方" in text
        assert "分析設計・探索" in text
        assert "探索の問い: 取消を除くと、期限切れは何件か" in text
        assert "探索済み（判定はしない）" in text
        assert "分析ノートを開く" in text
        assert "判定:" not in text
        assert "支持" not in text

    def test_a_confirmation_card_names_whose_verdict_it_is(self) -> None:
        text = card_of(forms_page(), "LIB-Q03", "LIB-H02")

        assert "分析設計・検証" in text
        assert "検証仮説: 通知が翌日以降の予約は期限切れが多い" in text
        assert "検証仮説の判定: 支持" in text

    def test_a_legacy_exploration_shows_its_hypothesis_and_verdict_as_written(
        self,
    ) -> None:
        text = card_of(forms_page(), "LIB-Q03", "LIB-H03")

        assert "分析設計・探索（旧形式）" in text
        assert "仮説: 金曜に確保した本は期限切れが多い" in text
        assert "仮説の判定: 棄却" in text
        assert "検証仮説" not in text

    def test_a_saved_mixed_design_reads_as_exploration_and_confirmation(
        self,
    ) -> None:
        designs = make_designs()
        designs["LIB-H01"] = summary(
            "LIB-H01", "t", "supported", None, intent="探索と検証（旧形式）"
        )

        (card,) = branch_cards(page(designs=designs), "LIB-Q02")

        assert "分析設計・探索と検証（旧形式）" in card_text(card)
        assert "検証仮説の判定: 支持" in card_text(card)

    @pytest.mark.parametrize(
        ("status", "word"),
        [
            ("in_review", "レビュー中"),
            ("revision_requested", "修正待ち"),
            ("analyzing", "分析中"),
        ],
    )
    def test_a_design_before_its_conclusion_says_where_it_is(
        self, status: str, word: str
    ) -> None:
        designs = make_designs()
        designs["LIB-H01"] = summary("LIB-H01", "t", status, None)

        (card,) = branch_cards(page(designs=designs), "LIB-Q02")

        assert word in card_text(card)
        assert status not in card_text(card)

    def test_a_design_linked_to_a_second_node_is_a_short_row_there(self) -> None:
        root = forms_page()

        (row,) = branch_cards(root, "LIB-Q05")
        assert card_text(row) == "LIB-H03 仮説の判定: 棄却 LIB-Q03 の下に出ている"
        assert [e.attrs["href"] for e in row.walk() if e.tag == "a"] == ["#LIB-Q03"]

    def test_the_first_node_is_the_first_on_the_page_not_in_the_file(self) -> None:
        tree = make_tree()
        # LIB-Q04 sits under LIB-Q02, so it comes before LIB-Q03 on the page.
        tree["nodes"][2]["design_ids"] = ["LIB-H02"]
        tree["nodes"][3]["design_ids"] = ["LIB-H02"]
        assert [n["id"] for n in tree["nodes"]].index("LIB-Q03") < 3

        root = page(tree=tree)

        assert len(branch_cards(root, "LIB-Q04")[0].children) > 1
        (row,) = branch_cards(root, "LIB-Q03")
        assert card_text(row).endswith("LIB-Q04 の下に出ている")

    def test_a_node_without_designs_has_no_design_card(self) -> None:
        assert branch_cards(forms_page(), "LIB-Q04") == []


class TestStatusWords:
    """US-4 AC 2: the status is worded by its role, with the YAML value in the legend."""

    def test_the_legend_maps_each_word_to_its_yaml_value_and_form(self) -> None:
        legend = by_id(page(), "legend")
        rows = [
            [squash(c.text()) for c in row.children if c.tag == "td"]
            for row in legend.walk()
            if row.tag == "tr"
        ]
        rows = [r for r in rows if r]

        expected = {
            ("レビュー中", "in_review"),
            ("修正待ち", "revision_requested"),
            ("分析中", "analyzing"),
            ("探索済み（判定はしない）", "explored"),
            ("検証仮説の判定: 支持", "supported"),
            ("検証仮説の判定: 棄却", "rejected"),
            ("検証仮説の判定: 結論できず", "inconclusive"),
            ("仮説の判定: 支持", "supported"),
            ("仮説の判定: 棄却", "rejected"),
            ("仮説の判定: 結論できず", "inconclusive"),
        }
        assert {(r[0], r[1]) for r in rows} == expected
        forms = {r[0]: r[2] for r in rows}
        assert forms["探索済み（判定はしない）"] == "探索"
        assert forms["検証仮説の判定: 支持"] == "検証、探索と検証（旧形式）"
        assert forms["仮説の判定: 支持"] == "探索（旧形式）"
        assert forms["分析中"] == "探索、検証、探索と検証（旧形式）、探索（旧形式）"

    @pytest.mark.parametrize("form", list(DesignForm))
    def test_every_status_a_form_can_take_has_a_row(self, form: DesignForm) -> None:
        legend = squash(by_id(page(), "legend").text())

        reachable = (set(DesignStatus) - TERMINAL_STATUSES) | CONCLUSIONS_OF[form]
        for status in reachable:
            assert status_word(form, status) in legend

    def test_the_derivation_words_the_status_by_its_role(self) -> None:
        root = forms_page()

        assert "探索済み（判定はしない）" in squash(
            by_id(root, "design-LIB-H01").text()
        )
        derived = squash(by_id(root, "design-LIB-H03").text())
        assert "仮説の判定: 棄却" in derived
        assert "rejected" not in squash(by_id(root, "derivation").text())

    def test_a_node_card_heads_its_answer_with_the_current_answer(self) -> None:
        root = page()
        card = next(e for e in by_id(root, "LIB-Q02").children if e.tag == "div")
        paragraphs = [squash(e.text()) for e in card.children if e.tag in ("p", "ul")]

        heading = paragraphs.index("現時点の答え")
        assert paragraphs[heading + 1].startswith("言えること")

    def test_a_node_without_an_answer_has_no_heading(self) -> None:
        assert "現時点の答え" not in node_text(page(), "LIB-Q03")


def linking(design_ids: list[str]) -> dict:
    """The tree where only LIB-Q03 links designs, so a test names every design it uses."""
    tree = make_tree()
    for node in tree["nodes"]:
        node.pop("design_ids", None)
    tree["nodes"][2]["design_ids"] = design_ids
    return tree


class TestOrderOfLinkedDesigns:
    """The card puts the designs still being worked on first, then the finished ones."""

    DAY = timedelta(days=1)

    def _shown(self, specs: list[tuple[str, str, datetime]]) -> list[str]:
        """The ids on the card of LIB-Q03, in the order the card lists them."""
        designs = {i: summary(i, "t", status, None, at) for i, status, at in specs}
        root = page(tree=linking([i for i, _, _ in specs]), designs=designs)
        return [
            e.attrs["href"].removeprefix("#design-")  # type: ignore[union-attr]
            for card in branch_cards(root, "LIB-Q03")
            for e in card.walk()
            if e.tag == "a" and str(e.attrs["href"]).startswith("#design-")
        ]

    def test_an_unfinished_design_comes_before_a_finished_one_whatever_the_date(
        self,
    ) -> None:
        shown = self._shown(
            [
                ("LIB-H01", "analyzing", T0),
                ("LIB-H02", "supported", T0 + self.DAY),
                ("LIB-H03", "analyzing", T0 - self.DAY),
            ]
        )

        assert shown == ["LIB-H01", "LIB-H03", "LIB-H02"]

    @pytest.mark.parametrize("status", list(DesignStatus))
    def test_a_status_is_finished_exactly_when_it_is_terminal(
        self, status: DesignStatus
    ) -> None:
        shown = self._shown(
            [("LIB-H01", status.value, T0 + self.DAY), ("LIB-H02", "analyzing", T0)]
        )

        finished = status in TERMINAL_STATUSES
        assert shown == (["LIB-H02", "LIB-H01"] if finished else ["LIB-H01", "LIB-H02"])

    def test_inside_a_group_the_newer_design_comes_first(self) -> None:
        shown = self._shown(
            [
                ("LIB-H03", "analyzing", T0),
                ("LIB-H01", "analyzing", T0 + self.DAY),
                ("LIB-H02", "supported", T0),
                ("LIB-H04", "rejected", T0 + self.DAY),
            ]
        )

        assert shown == ["LIB-H01", "LIB-H03", "LIB-H04", "LIB-H02"]

    def test_the_same_time_puts_the_larger_id_first(self) -> None:
        shown = self._shown([(f"LIB-H0{n}", "analyzing", T0) for n in (1, 3, 2)])

        assert shown == ["LIB-H03", "LIB-H02", "LIB-H01"]

    def test_ids_are_compared_by_their_number_not_as_strings(self) -> None:
        shown = self._shown([("LIB-H9", "analyzing", T0), ("LIB-H10", "analyzing", T0)])

        assert shown == ["LIB-H10", "LIB-H9"]

    def test_times_are_compared_as_times_not_as_text(self) -> None:
        later_in_utc = datetime(2026, 11, 1, 2, 0, tzinfo=UTC)  # 11:00 JST
        shown = self._shown(
            [("LIB-H01", "analyzing", later_in_utc), ("LIB-H02", "analyzing", T0)]
        )

        assert shown == ["LIB-H01", "LIB-H02"]

    def test_a_time_without_a_zone_next_to_one_with_a_zone_is_an_error_naming_both(
        self,
    ) -> None:
        with pytest.raises(ValueError, match=r"LIB-H01.*LIB-H02|LIB-H02.*LIB-H01"):
            self._shown(
                [
                    ("LIB-H01", "analyzing", T0.replace(tzinfo=None)),
                    ("LIB-H02", "analyzing", T0),
                ]
            )

    def test_the_derivation_and_the_design_notes_stay_in_id_order(self) -> None:
        designs = {
            "LIB-H10": summary("LIB-H10", "t", "analyzing", None, T0 + self.DAY),
            "LIB-H9": summary("LIB-H9", "t", "supported", None, T0),
        }

        root = page(tree=linking([]), designs=designs)

        derivation = [
            e.attrs["id"]
            for e in by_id(root, "derivation").walk()
            if str(e.attrs.get("id", "")).startswith("design-")
        ]
        design_notes = [
            e.attrs["id"]
            for e in by_id(root, "design-notes").children
            if e.tag == "section"
        ]
        assert derivation == ["design-LIB-H9", "design-LIB-H10"]
        assert design_notes == ["note-LIB-H9", "note-LIB-H10"]


class TestAnchorsToTheNotes:
    OPEN = "分析ノートを開く"

    def _hrefs(self, element: Element) -> list[str]:
        return [e.attrs["href"] for e in element.walk() if e.tag == "a"]  # type: ignore[misc]

    def test_each_design_under_a_node_links_its_derivation_and_its_note(
        self,
    ) -> None:
        (card,) = branch_cards(page(), "LIB-Q02")

        assert self._hrefs(card) == ["#design-LIB-H01", "#note-LIB-H01"]
        open_link = [e for e in card.walk() if e.tag == "a"][1]
        assert open_link.text() == self.OPEN

    def test_each_design_in_the_derivation_has_a_link_to_its_note(self) -> None:
        root = page()

        for design_id in ("LIB-H01", "LIB-H02", "LIB-H04"):
            (design,) = [
                e for e in by_id(root, f"design-{design_id}").children if e.tag == "div"
            ]
            assert f"#note-{design_id}" in self._hrefs(design)
            assert self.OPEN in design.text()

    def test_the_tree_side_names_no_link_that_leaves_the_page(self) -> None:
        root = page()

        hrefs = [e.attrs["href"] for e in root.walk() if e.tag == "a"]
        assert hrefs
        assert all(h.startswith("#") for h in hrefs)
        ids = {e.attrs["id"] for e in root.walk() if "id" in e.attrs}
        assert {h[1:] for h in hrefs} <= ids


class TestDesignNotes:
    def _sections(self) -> list[Element]:
        return [e for e in by_id(page(), "design-notes").children]

    def test_the_design_notes_come_after_the_derivation_in_one_section(self) -> None:
        html = render()

        assert html.index('id="derivation"') < html.index('id="design-notes"')
        section = by_id(parse(html), "design-notes")
        assert section.children[0].tag == "h2"
        assert section.children[0].text() == "分析設計ごとの分析ノート"

    def test_each_design_has_a_back_link_a_note_and_a_back_link_in_id_order(
        self,
    ) -> None:
        children = self._sections()[1:]

        shapes = [(c.tag, c.attrs.get("id")) for c in children]
        assert shapes == [
            ("p", None), ("section", "note-LIB-H01"), ("p", None),
            ("p", None), ("section", "note-LIB-H02"), ("p", None),
            ("p", None), ("section", "note-LIB-H04"), ("p", None),
        ]  # fmt: skip

    def test_the_back_link_returns_to_the_tree_and_names_the_nodes_that_link_the_design(
        self,
    ) -> None:
        before, _, after = self._sections()[1:4]

        for paragraph in (before, after):
            links = [e.attrs["href"] for e in paragraph.walk() if e.tag == "a"]
            assert links == ["#question-tree", "#LIB-Q02"]
            assert squash(paragraph.text()) == "論点ツリーへ戻る 結んだ論点: LIB-Q02"

    def test_a_design_no_node_links_has_only_the_link_back_to_the_tree(self) -> None:
        before, _, after = self._sections()[7:10]

        for paragraph in (before, after):
            assert [e.attrs["href"] for e in paragraph.walk() if e.tag == "a"] == [
                "#question-tree"
            ]
            assert "結んだ論点" not in paragraph.text()

    def test_note_markup_is_placed_as_markup_not_escaped_again(self) -> None:
        designs = make_designs()
        design_notes = stub_design_notes(designs)
        design_notes["LIB-H01"] = Html(
            '<section id="note-LIB-H01"><b>太い</b> &amp; 本文</section>'
        )

        root = page(designs=designs, design_notes=design_notes)

        note = by_id(root, "note-LIB-H01")
        assert [e.tag for e in note.children] == ["b"]
        assert squash(note.text()) == "太い & 本文"

    def test_a_design_without_a_note_is_an_error_naming_it(self) -> None:
        designs = make_designs()
        design_notes = stub_design_notes(designs)
        del design_notes["LIB-H02"]

        with pytest.raises(ValueError, match="LIB-H02"):
            render(designs=designs, design_notes=design_notes)

    def test_a_page_without_designs_says_there_is_no_note(self) -> None:
        tree = make_tree()
        for node in tree["nodes"]:
            node.pop("design_ids", None)
            node["answers"] = []
            node.pop("origin_event_id", None)

        root = page(tree=tree, designs={})

        assert "分析ノートはまだ無い。" in by_id(root, "design-notes").text()

    def test_the_page_carries_the_css_of_the_note(self) -> None:
        from skills._shared.design_note import NOTE_CSS

        assert NOTE_CSS in render()


class TestEscaping:
    def test_markup_in_untrusted_text_never_reaches_the_page_as_markup(self) -> None:
        tree = make_tree()
        tree["root_revisions"][1]["question"] = ROOT_QUESTION + HOSTILE
        tree["root_revisions"][1]["aim"] = {
            **BUSINESS_AIM,
            "decision": "決める" + HOSTILE,
        }
        tree["root_revisions"][0]["reason"] = HOSTILE
        tree["root_revisions"][1]["reason"] = "理由" + HOSTILE
        tree["nodes"][0]["question"] = ROOT_QUESTION + HOSTILE
        tree["nodes"][1]["contribution"] = "寄与" + HOSTILE
        tree["nodes"][1]["answers"][1]["statements"][0]["text"] = "文" + HOSTILE
        tree["decisions"][0]["reason"] = "決定" + HOSTILE
        with_note(tree, "LIB-Q05", **{**HEARD, "ask": "問い" + HOSTILE})
        designs = make_designs()
        designs["LIB-H01"] = summary("LIB-H01", "題" + HOSTILE, "supported", None)
        # The status is a DesignStatus, so no text of the analyst reaches it.
        designs["LIB-H04"] = summary("LIB-H04", "t", "in_review", "LIB-H99" + HOSTILE)
        events = make_events()
        events["LIB-H01-E01"] = CitedEvent(
            "LIB-H01-E01", "evidence" + HOSTILE, "supports" + HOSTILE, "本文" + HOSTILE
        )

        html = render(
            tree=tree,
            designs=designs,
            events=events,
            violations=[Violation("LIB-Q02", 2, 1, "number-not-cited", "数" + HOSTILE)],
        )

        assert "<script" not in html.lower()
        assert 'onmouseover="x' not in html
        root = parse(html)
        assert not [e for e in root.walk() if e.tag == "script"]
        assert not any("onmouseover" in e.attrs for e in root.walk())
        assert "<script>alert(1)</script>" in squash(root.text())


class TestEveryKindHasItsWord:
    """A kind added to the model without a word would stop the page."""

    @pytest.mark.parametrize(
        ("words", "kinds"),
        [
            (tree_render.PROGRESS_WORDS, Progress),
            (tree_render._KIND_WORDS, StatementKind),
            (tree_render._MARK_WORDS, tree_render.Mark),
            (tree_render._DECISION_LABELS, TreeDecisionKind),
            (tree_render._AIM_LABELS, AimKind),
        ],
    )
    def test_the_table_covers_the_enum(self, words: dict, kinds: type) -> None:
        assert set(words) == set(kinds)


class TestReviewCommentsAfterTheAnalysis:
    """Story 33.6, US-4 AC 5: the row of a design counts the comments of its result review."""

    @staticmethod
    def _card(count: int) -> str:
        designs = make_designs()
        designs["LIB-H01"] = summary(
            "LIB-H01",
            "取消を除く数え方",
            "supported",
            None,
            comments_after_analysis=count,
        )
        root = page(designs=designs)
        (node_id,) = {
            n["id"]
            for n in make_tree()["nodes"]
            if "LIB-H01" in n.get("design_ids", [])
        }
        return card_of(root, node_id, "LIB-H01")

    def test_the_row_shows_how_many_comments_came_after_the_analysis(self) -> None:
        assert "分析を始めた後の review コメント: 3 件" in self._card(3)

    def test_the_row_shows_no_count_when_there_is_none(self) -> None:
        assert "review コメント" not in self._card(0)


class TestReviewCommentsInTheDerivation:
    """US-4 AC 5: a design linked to no node shows its count in the derivation.

    A design no node links appears only in the derivation, so a count on the card
    alone never reaches it (the trial finding G08).
    """

    @staticmethod
    def _row(design_id: str, count: int) -> str:
        designs = make_designs()
        old = designs[design_id]
        designs[design_id] = summary(
            old.id,
            old.title,
            old.status.value,
            old.parent_id,
            comments_after_analysis=count,
        )
        (row,) = [
            e
            for e in by_id(page(designs=designs), f"design-{design_id}").children
            if e.tag == "div"
        ]
        return row.text()

    def test_a_design_linked_to_no_node_shows_the_count(self) -> None:
        row = self._row("LIB-H04", 4)

        assert "論点に結んでいない" in row
        assert "分析を始めた後の review コメント: 4 件" in row

    def test_a_linked_design_shows_the_count_in_its_derivation_row_too(self) -> None:
        assert "分析を始めた後の review コメント: 3 件" in self._row("LIB-H01", 3)

    def test_the_derivation_row_shows_no_count_when_there_is_none(self) -> None:
        assert "review コメント" not in self._row("LIB-H04", 0)
