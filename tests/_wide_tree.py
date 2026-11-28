"""A synthetic tree as wide as a real theme, for the list an answer leaves out (Epic 36).

The scenarios of the handoff trial list one or two results under the subject; a
real theme listed about forty, close to half of them listed the round before
too. Only that shape is copied here: seven nodes, six designs, two rounds. Every
name and sentence is made up (a gym that wants fewer members to leave).

``build`` leaves the tree after round 1. ``round_2_drafts`` are the answers of
round 2 before the analyst chose anything for the subject; ``round_2_answers``
are the ones written after, with one statement that is the analyst's view.

    PYTHONPATH=. python -m tests._wide_tree OUT   # writes OUT and prints the HTML
"""

from __future__ import annotations

import sys
from pathlib import Path

from skills._shared import design_io, tree_io

THEME = "GYM"
ROOT = "GYM-Q01"
# What the subject cites in both rounds, and what the analyst takes in round 2.
ROOT_CITES = ("GYM-H01-E01", "GYM-H02-E01", "GYM-H03-E01", "GYM-H05-E01")
LISTED_BEFORE, NEW_IN_ROUND_2, CHOSEN = 17, 24, 13
ANALYST_VIEW = "入会直後の利用が続かないことが退会の主な理由だと見る。\n料金より先に、最初のひと月の声かけを試したい"

_AIM = {
    "kind": "business",
    "decision_maker": "店長",
    "decision": "退会を減らす施策のどれを先に試すか",
}
# node id -> (question, parent, design id, topic of the design)
_NODES = {
    "GYM-Q02": ("退会は入会後のいつに多いか", ROOT, "GYM-H01", "入会からの月数と退会"),
    "GYM-Q03": (
        "利用の頻度は退会に効くか",
        ROOT,
        "GYM-H02",
        "週あたりの利用回数と退会",
    ),
    "GYM-Q04": (
        "平日夜の混雑は利用を減らすか",
        "GYM-Q03",
        "GYM-H03",
        "平日夜の混雑と利用",
    ),
    "GYM-Q05": (
        "スタッフの声かけは利用を保つか",
        "GYM-Q03",
        "GYM-H04",
        "声かけと翌月の利用",
    ),
    "GYM-Q06": ("料金プランは退会に効くか", ROOT, "GYM-H05", "料金プランと退会"),
    "GYM-Q07": ("休会の制度は退会を減らすか", "GYM-Q06", "GYM-H06", "休会の制度と退会"),
}
# design id -> the types of its events, in journal order: (written before round 1, before round 2)
_EVENTS = {
    "GYM-H01": (("evidence", "question", "observe", "evidence", "question", "conclude"),
                ("evidence", "evidence", "question", "question")),
    "GYM-H02": (("evidence", "evidence", "question", "observe", "conclude"),
                ("evidence", "evidence", "question", "conclude")),
    "GYM-H03": (("evidence", "question", "evidence", "observe", "question"),
                ("evidence", "question", "question", "conclude")),
    "GYM-H04": ((), ("evidence", "evidence", "question", "question")),
    "GYM-H05": (("evidence", "question", "evidence", "question", "conclude"),
                ("evidence", "evidence", "question", "question")),
    "GYM-H06": ((), ("evidence", "evidence", "question", "observe")),
}  # fmt: skip
_SAID = {
    "evidence": "を数えた結果",
    "question": "について次に確かめたいこと",
    "observe": "を見て気づいたこと",
    "conclude": "の分析を終えて言えること",
}


def _append_events(base_dir: Path, design_id: str, types: tuple[str, ...]) -> list[str]:
    topic = next(n[3] for n in _NODES.values() if n[2] == design_id)
    ids = []
    for kind in types:
        nth = len(design_io.journal_events(design_id, base_dir)) + 1
        event = design_io.append_journal_event(
            design_id,
            {"type": kind, "content": f"{topic}{_SAID[kind]}（記録の{nth}件目）"},
            base_dir,
        )
        ids.append(event["id"])
    return ids


def _statement(event_id: str, kind: str = "claim") -> dict:
    return {
        "kind": kind,
        "text": f"{event_id} の記録から言えること",
        "cites": [event_id],
    }


def _own_events(base_dir: Path, design_id: str) -> list[str]:
    return [e["id"] for e in design_io.journal_events(design_id, base_dir)]


def _below_answers(base_dir: Path) -> list[dict]:
    """Each node under the subject says one thing from each event of its own design."""
    return [
        {"node_id": node_id, "statements": [_statement(e) for e in events]}
        for node_id, (_, _, design_id, _) in _NODES.items()
        if (events := _own_events(base_dir, design_id))
    ]


def _root_answer(*more: dict) -> dict:
    return {"node_id": ROOT, "statements": [*map(_statement, ROOT_CITES), *more]}


def _answer(base_dir: Path, answers: list[dict]) -> None:
    result = tree_io.answer(THEME, answers=answers, base_dir=base_dir)
    if result["violations"]:
        raise ValueError(f"the wide tree's answers fail the tree check: {result}")


def build(base_dir: Path) -> None:
    """Write the tree, its designs and journals, and the answers of round 1."""
    tree_io.create_tree(
        theme_id=THEME,
        question="退会を減らす施策を先に試すか",
        aim=_AIM,
        base_dir=base_dir,
    )
    for question, parent, _, topic in _NODES.values():
        tree_io.add_node(
            THEME,
            question=question,
            parent_question_id=parent,
            contribution=f"{topic}が分かると、先に試す施策が変わる",
            base_dir=base_dir,
        )
    for node_id, (question, _, design_id, topic) in _NODES.items():
        created = design_io.create_design(
            theme_id=THEME,
            title=topic,
            analysis_intent="exploratory",
            exploration_question=question,
            exploration_background=f"{topic}はまだ数えていない",
            base_dir=base_dir,
        )
        assert created["id"] == design_id, created["id"]
        tree_io.link_design(THEME, node_id, design_id, base_dir=base_dir)
    for design_id, (first, _) in _EVENTS.items():
        _append_events(base_dir, design_id, first)
    _answer(base_dir, [*_below_answers(base_dir), _root_answer()])


def add_round_2_events(base_dir: Path) -> list[str]:
    """Append what the analyses found after round 1; return the ids, design by design."""
    return [
        event_id
        for design_id, (_, second) in _EVENTS.items()
        for event_id in _append_events(base_dir, design_id, second)
    ]


def round_2_drafts(base_dir: Path) -> list[dict]:
    """Round 2 before the analyst chose: the nodes below cite the new events, the subject none."""
    return [*_below_answers(base_dir), _root_answer()]


def round_2_answers(base_dir: Path, new_events: list[str]) -> list[dict]:
    """Round 2 as written: the subject takes ``CHOSEN`` new events, two under the analyst's view."""
    first, second, *others = (
        [e for e in new_events if e.startswith("GYM-H01")][:1]
        + [e for e in new_events if e.startswith("GYM-H04")][:1]
        + [e for e in new_events if not e.startswith(("GYM-H01", "GYM-H04"))]
    )[:CHOSEN]
    view = {
        "kind": "claim",
        "text": ANALYST_VIEW,
        "cites": [first, second],
        "analyst_view": True,
    }
    return [
        *_below_answers(base_dir),
        _root_answer(view, *(_statement(e, "weakening") for e in others)),
    ]


def build_through_round_2(base_dir: Path) -> None:
    build(base_dir)
    _answer(base_dir, round_2_answers(base_dir, add_round_2_events(base_dir)))


if __name__ == "__main__":
    out = Path(sys.argv[1])
    build_through_round_2(out)
    print(tree_io.render(THEME, base_dir=out)["path"])
