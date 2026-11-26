"""What the tests of the tree page share: a synthetic tree, a page read as a reader reads it,
and the word of a mark.

The page is parsed with ``html.parser`` so a test asks what text sits in which
element. Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from insight_blueprint.models.design import DesignForm, DesignStatus
from insight_blueprint.models.tree import QuestionTree
from insight_blueprint.validate import validate_tree_schema
from skills._shared._html import Html
from skills._shared.design_note import intent_words_of
from skills._shared.tree_check import CitedEvent, Violation
from skills._shared.tree_render import CheckFailed, DesignSummary, render_tree_html
from skills._shared.tree_words import MARK_WORDS, Mark

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
    shared: list[str] | None = None,
) -> str:
    shown = make_designs() if designs is None else designs
    return render_tree_html(
        build(tree),
        shown,
        make_events() if events is None else events,
        [] if violations is None else violations,
        stub_design_notes(shown) if design_notes is None else design_notes,
        shared=frozenset(shared or ()),
    )


def page(
    tree: dict | None = None,
    designs: dict[str, DesignSummary] | None = None,
    events: dict[str, CitedEvent] | None = None,
    violations: list[Violation] | CheckFailed | None = None,
    design_notes: dict[str, Html] | None = None,
    shared: list[str] | None = None,
) -> Element:
    return parse(render(tree, designs, events, violations, design_notes, shared))


def has_class(element: Element, name: str) -> bool:
    return name in (element.attrs.get("class") or "").split()


def node_card(root: Element, node_id: str) -> Element:
    """The card of a node, without the cards nested under it."""
    return next(e for e in by_id(root, node_id).children if e.tag == "div")


def answer_text(root: Element, node_id: str) -> str:
    """The statements of the current answer on the card of a node."""
    (statements,) = [
        e for e in node_card(root, node_id).children if has_class(e, "statements")
    ]
    return squash(statements.text())


def marks_text(root: Element, node_id: str) -> str:
    card = node_card(root, node_id)
    return squash(" ".join(e.text() for e in card.walk() if has_class(e, "mark")))


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


def stale() -> list[Violation]:
    return [
        Violation("LIB-Q02", 2, 1, "number-not-cited", "346"),
        Violation("LIB-Q02", 2, 2, "missing-event", "LIB-H01-E99"),
    ]


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


def mark_word(mark: Mark, round: int | None = None) -> str:
    """The mark as the page shows it. A mark that names a round fails without *round*."""
    return MARK_WORDS[mark][0].format(**({} if round is None else {"round": round}))


def never_revised() -> dict:
    tree = make_tree()
    tree["root_revisions"] = tree["root_revisions"][1:]
    tree["root_revisions"][0].update(revision=1, reason="")
    for node in tree["nodes"]:
        for answer in node.get("answers", []):
            answer["root_revision"] = 1
    return tree
