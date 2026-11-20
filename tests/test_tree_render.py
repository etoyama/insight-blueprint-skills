"""Tests for tree_render, the pure HTML view of a question tree (Epic 18, Story 18.6).

The page is read the way a reader reads it, so the tests parse it with
``html.parser`` and ask what text sits in which element. Synthetic data only
(public-library holds, theme LIB).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from html.parser import HTMLParser

import pytest

from insight_blueprint.models.tree import (
    AimKind,
    Progress,
    QuestionTree,
    StatementKind,
    TreeDecisionKind,
)
from insight_blueprint.validate import validate_tree_schema
from skills._shared import tree_render
from skills._shared.tree_render import CitedEvent, DesignSummary, render_tree_html

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


def make_designs() -> dict[str, DesignSummary]:
    return {
        "LIB-H01": DesignSummary("LIB-H01", "取消を除く数え方", "supported", None),
        "LIB-H02": DesignSummary("LIB-H02", "通知の遅れを測る", "analyzing", "LIB-H01"),
        "LIB-H04": DesignSummary("LIB-H04", "貸出の季節差", "in_review", "LIB-H99"),
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
) -> str:
    return render_tree_html(
        build(tree),
        make_designs() if designs is None else designs,
        make_events() if events is None else events,
    )


def page(
    tree: dict | None = None,
    designs: dict[str, DesignSummary] | None = None,
    events: dict[str, CitedEvent] | None = None,
) -> Element:
    return parse(render(tree, designs, events))


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
        for word in ("この回で変わった", "根の変更前の答え", "この回で初めて答えた"):
            assert word in legend
        assert "根拠を開く" in legend
        assert "論点の親子" in legend
        assert "分析設計の派生" in legend


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


class TestMarks:
    def test_an_answer_that_differs_in_the_latest_round_is_marked_as_changed(
        self,
    ) -> None:
        shown = node_text(page(), "LIB-Q02")

        assert "この回で変わった" in shown
        assert "この回で初めて答えた" not in shown

    def test_the_previous_answer_is_shown_behind_a_changed_answer(self) -> None:
        folded = details_text(page(), "LIB-Q02")

        assert "取消を含めると期限切れは 400 件" in folded
        assert "前の回の答え" in folded

    def test_an_answer_first_written_in_the_latest_round_is_marked_as_first(
        self,
    ) -> None:
        shown = node_text(page(), "LIB-Q04")

        assert "この回で初めて答えた" in shown
        assert "この回で変わった" not in shown

    def test_an_answer_from_an_earlier_round_carries_no_changed_mark(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert "この回で変わった" not in shown
        assert "この回で初めて答えた" not in shown

    def test_an_answer_rewritten_with_identical_statements_carries_no_mark(
        self,
    ) -> None:
        tree = make_tree()
        answers = tree["nodes"][1]["answers"]
        answers[0]["statements"] = answers[1]["statements"]

        shown = node_text(page(tree=tree), "LIB-Q02")

        assert "この回で変わった" not in shown
        assert "この回で初めて答えた" not in shown

    def test_an_answer_written_against_an_older_root_revision_is_marked(self) -> None:
        shown = node_text(page(), "LIB-Q05")

        assert "根の変更前の答え（根の版 1 への答え）" in shown

    def test_an_answer_of_the_current_root_revision_is_not_marked_stale(self) -> None:
        assert "根の変更前の答え" not in node_text(page(), "LIB-Q02")


class TestEvidence:
    def test_the_details_hold_each_cited_event_with_its_design_and_direction(
        self,
    ) -> None:
        folded = details_text(page(), "LIB-Q02")

        assert "根拠を開く" in folded
        assert "LIB-H01-E01" in folded
        assert "期限切れは取消除外で 346 件" in folded
        assert "design: LIB-H01" in folded
        assert "direction: supports（仮説を支持する）" in folded
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

    def test_the_details_list_the_linked_designs_with_title_and_status(self) -> None:
        folded = details_text(page(), "LIB-Q03")

        assert "結んだ分析設計" in folded
        assert "LIB-H02" in folded
        assert "通知の遅れを測る" in folded
        assert "analyzing" in folded


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
            "LIB-H01": DesignSummary("LIB-H01", "a", "analyzing", "LIB-H02"),
            "LIB-H02": DesignSummary("LIB-H02", "b", "analyzing", "LIB-H01"),
        }
        tree = make_tree()
        tree["nodes"][1]["answers"] = []
        tree["nodes"][3]["answers"] = []
        tree["nodes"][3]["origin_event_id"] = None
        tree["nodes"][2]["design_ids"] = ["LIB-H02"]

        root = page(tree=tree, designs=designs)

        assert by_id(root, "design-LIB-H01") is not None
        assert by_id(root, "design-LIB-H02") is not None


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
        designs = make_designs()
        designs["LIB-H01"] = DesignSummary("LIB-H01", "題" + HOSTILE, "supported", None)
        designs["LIB-H04"] = DesignSummary(
            "LIB-H04", "t", "in_review" + HOSTILE, "LIB-H99" + HOSTILE
        )
        events = make_events()
        events["LIB-H01-E01"] = CitedEvent(
            "LIB-H01-E01", "evidence" + HOSTILE, "supports" + HOSTILE, "本文" + HOSTILE
        )

        html = render(tree=tree, designs=designs, events=events)

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
            (tree_render._PROGRESS_WORDS, Progress),
            (tree_render._KIND_WORDS, StatementKind),
            (tree_render._MARK_WORDS, tree_render.Mark),
            (tree_render._DECISION_LABELS, TreeDecisionKind),
            (tree_render._AIM_LABELS, AimKind),
        ],
    )
    def test_the_table_covers_the_enum(self, words: dict, kinds: type) -> None:
        assert set(words) == set(kinds)
