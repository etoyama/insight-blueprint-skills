"""Render a question tree as one self-contained HTML page (Epic 18, ADR-0024).

Pure: no I/O. ``tree_read.render`` (CLI: ``tree_io render``) reads the files
and hands the data in here.
The page has no script, no external resource and no timestamp, so the same
inputs give the same bytes. Interaction is ``<details>`` only.

Every string that reaches the page comes from analysts or models, so none of it
is trusted: see ``_html`` for how markup is told from text.

The page is built in three modules: this one lays out the sections,
``tree_render_parts`` holds the context of a page, the words and the parts the
sections share, and ``tree_render_derived`` shows what ``tree_changes`` derives.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from insight_blueprint.models.design import TERMINAL_STATUSES, DesignForm, DesignStatus
from insight_blueprint.models.tree import (
    Aim,
    Answer,
    Progress,
    QuestionNode,
    QuestionTree,
    TreeDecision,
    TreeDecisionKind,
    design_id_of,
)
from skills._shared._html import BASE_CSS, Html, el, join, page
from skills._shared.design_io import design_number
from skills._shared.design_note import (
    FORM_WORDS,
    NOTE_CSS,
    direction_gloss,
    intent_words_of,
    note_anchor,
    status_word,
)
from skills._shared.design_note_reviews import AFTER_ANALYSIS
from skills._shared.tree_render_derived import _changes, _changes_on_the_card
from skills._shared.tree_render_parts import (
    _AIM_LABELS,
    _CHANGE_WORDS,
    _DECISION_LABELS,
    _HEARD_RESULT_WORD,
    _HEARD_WORD,
    _MARK_WORDS,
    _NOTE_LABELS,
    _SUBJECT,
    _SUBJECT_REVISION,
    _VIOLATION_WORDS,
    KIND_WORDS,
    PROGRESS_WORDS,
    CheckFailed,
    CitedEvent,
    DesignSummary,
    Shown,
    _answer_lines,
    _checked_in_its_card,
    _Context,
    _current_round_meta,
    _join_links,
    _link,
    _marks,
    _round_meta,
    _statement,
)

# Each table of words is read from here by the tests that pair it with its enum.
from skills._shared.tree_render_parts import Mark as Mark

if TYPE_CHECKING:  # tree_check imports this module (CitedEvent)
    from skills._shared.tree_check import Violation


_TREE_CSS = """.legend { background: var(--panel); border: 1px solid var(--line); padding: .5rem 1rem; }
.tree, .tree ul, .derivation, .derivation ul {
  list-style: none; margin: 0; padding-left: 1.25rem;
  border-left: 1px solid var(--line);
}
.tree { padding-left: 0; border-left: 0; }
.derivation { padding-left: 0; border-left: 0; }
.tree li, .derivation li { margin: .6rem 0; }
.node, .design {
  background: var(--panel); border: 1px solid var(--line); border-left-width: 6px;
  padding: .4rem .7rem; overflow-wrap: anywhere;
}
.progress-not_started { border-left-color: var(--not-started); }
.progress-investigating { border-left-color: var(--investigating); }
.progress-analyzed { border-left-color: var(--analyzed); }
.progress { font-weight: 700; }
.mark { color: var(--mark); font-weight: 700; margin-right: .6rem; }
.statements { margin: .3rem 0; padding-left: 1.2rem; }
.kind { font-weight: 700; }
.notice { border: 1px solid var(--investigating); padding: .4rem .8rem; }
.notes { margin: .3rem 0; padding-left: 1.2rem; }
.design-note { scroll-margin-top: 4rem; }
.branch {
  background: var(--panel); border: 1px dashed var(--line);
  padding: .4rem .7rem; overflow-wrap: anywhere;
}
.form-tag { font-weight: 700; margin-right: .4rem; }
.answer-heading { color: var(--muted); font-size: .9rem; margin-bottom: 0; }
.legend table { border-collapse: collapse; margin: .3rem 0; }
.legend th, .legend td { border: 1px solid var(--line); padding: .2rem .5rem; text-align: left; }
.now { background: var(--panel); border: 1px solid var(--line); padding: .2rem 1rem .6rem; }
.now h2 { margin-top: .6rem; }
.changes { border-left: 4px solid var(--mark); padding: .1rem .7rem; margin: .6rem 0; }
.changes h3, .changes h4 { margin: .3rem 0; font-size: 1rem; }
.changes .scroll { overflow-x: auto; }
.changes table { border-collapse: collapse; width: 100%; min-width: 38rem; margin: .4rem 0; }
.changes th, .changes td {
  border: 1px solid var(--line); padding: .3rem .5rem; text-align: left; vertical-align: top;
}
.changes tbody th { color: var(--mark); width: 7.5em; }
.changes td:nth-child(2) { width: 27%; }
.changes td ul { list-style: none; margin: 0; padding: 0; }
.changes blockquote { margin: .2rem 0 0; padding-left: .6rem; border-left: 3px solid var(--line); }
.changes .none { color: var(--muted); }
"""


def render_tree_html(
    tree: QuestionTree,
    designs: Mapping[str, DesignSummary],
    events: Mapping[str, CitedEvent],
    violations: Sequence[Violation] | CheckFailed,
    design_notes: Mapping[str, Html],
) -> str:
    """The page. *design_notes* maps a design id to the markup ``render_note`` returned."""
    context = _Context.of(tree, designs, events, violations, design_notes)
    body = join(
        [
            _header(tree),
            _check_notice(violations),
            _subject_answer(context),
            _next_question(tree),
            _legend(),
            _counts(context),
            _decisions(tree),
            _next_candidates(context),
            _question_tree(context),
            _derivation(context),
            _design_notes(context),
        ]
    )
    return page(f"論点ツリー {tree.theme_id}", BASE_CSS + _TREE_CSS + NOTE_CSS, body)


def _header(tree: QuestionTree) -> Html:
    revision = tree.current_revision()
    parts = [
        el("h1", f"論点ツリー {tree.theme_id}"),
        el("p", el("strong", f"{_SUBJECT}: "), revision.question),
        *(el("p", line) for line in _aim_lines(revision.aim)),
        el("p", f"{_SUBJECT_REVISION} {revision.revision}", class_="meta"),
    ]
    if len(tree.root_revisions) > 1:
        parts.append(_root_history(tree))
    return el("header", join(parts), id="header")


def _aim_lines(aim: Aim) -> list[str]:
    return [f"{label}: {getattr(aim, field)}" for label, field in _AIM_LABELS[aim.kind]]


def _root_history(tree: QuestionTree) -> Html:
    rows = []
    for revision in tree.root_revisions:
        aim = "、".join(_aim_lines(revision.aim))
        rows.append(
            el(
                "li",
                f"{_SUBJECT_REVISION} {revision.revision}: {revision.question}（{aim}）",
                f" 理由: {revision.reason}" if revision.reason else "",
            )
        )
    return el(
        "details",
        el("summary", f"{_SUBJECT_REVISION}の履歴"),
        el("ul", join(rows)),
        id="root-history",
    )


def _word_list(words: Iterable[tuple[str, str]]) -> Html:
    return el("ul", join(el("li", f"{word}: {meaning}") for word, meaning in words))


def _legend() -> Html:
    return el(
        "details",
        el("summary", "読み方"),
        el(
            "p",
            f"ページの冒頭には、{_SUBJECT}への現時点の答え、前の回から変わったこと、"
            "次に調べる論点を出す。その下に、論点ごとのカードを並べる。",
        ),
        el(
            "p",
            "「前の回から変わったこと」は、答えと、その1つ前の答えを比べて、根拠にした"
            "分析結果ごとに1行で出す。分け方は、根拠にしたかどうかと、文が同じか"
            "どうかだけで決まる。なぜ変えたかは記録に無いので、出さない。",
        ),
        el(
            "p",
            "記録と照らして確かめるのは、それぞれの論点の今の答えだけである。"
            "表に並べる前の回の文は、今の記録と照らし直していない。",
        ),
        _word_list(_CHANGE_WORDS.values()),
        el(
            "p",
            "進捗は、論点に結んだ分析設計の状態から導いた言葉。色は添えただけで、"
            "意味は言葉が持つ。",
        ),
        _word_list(PROGRESS_WORDS.values()),
        el("p", "現時点の答えは、文ごとに種類の言葉を付けて並べる。"),
        _word_list(KIND_WORDS.values()),
        el("p", "答えの上に出す印。"),
        _word_list(
            (word.format(round="N"), meaning) for word, meaning in _MARK_WORDS.values()
        ),
        el(
            "p",
            f"文の後ろの「{_HEARD_WORD}」は、引用した出来事がすべて{_HEARD_RESULT_WORD}"
            "（hearing）で、データの出来事が1つも無い文に付ける。",
        ),
        el("p", "まだ分析設計を結んでいない論点は「次の候補」に並べる。"),
        el(
            "p",
            "論点の下には、その論点に結んだ分析設計を、子の論点より先に並べる。"
            "分析設計のカードは破線の枠で、「分析設計・」と意図の言葉で始まる。"
            "同じ分析設計を2つ目の論点からは、id、状態の言葉、最初に出た論点への"
            "リンクだけの短い行で出す。",
        ),
        el(
            "p",
            "分析設計の状態は、次の言葉で出す。判定は分析設計の検証仮説（旧形式では"
            "仮説）に対するもので、論点の答えではない。論点の答えは、論点のカードの"
            "「現時点の答え」に書く。",
        ),
        _status_table(),
        el(
            "p",
            "各論点の「根拠を開く」を押すと、引用した journal の出来事と、前の回の答えが開く。",
        ),
        el("p", "論点の親子と分析設計の派生は別の構造なので、2つの節に分けて並べる。"),
        el(
            "p",
            "「分析ノートを開く」は、その分析設計の分析ノートへ飛ぶ。分析ノートはこの"
            "ページの下に、分析設計ごとに並べてある。分析ノートの冒頭と末尾の"
            "「論点ツリーへ戻る」で、論点ツリーの節へ戻る。",
        ),
        class_="legend",
        id="legend",
    )


def _status_rows() -> list[tuple[str, DesignStatus, list[str]]]:
    """(word, YAML value, intent words) for each status a form can take."""
    rows: dict[str, tuple[DesignStatus, list[str]]] = {}
    for status in DesignStatus:
        for form in DesignForm:
            if not form.allows(status):
                continue
            word = status_word(form, status)
            rows.setdefault(word, (status, []))[1].extend(intent_words_of(form))
    return [(word, status, intents) for word, (status, intents) in rows.items()]


def _status_table() -> Html:
    head = el("tr", join(el("th", h) for h in ("表示の言葉", "YAML の status", "意図")))
    body = join(
        el("tr", el("td", word), el("td", status.value), el("td", "、".join(intents)))
        for word, status, intents in _status_rows()
    )
    return el("table", el("thead", head), el("tbody", body), id="status-words")


def _id_key(design_id: str) -> tuple[int, str]:
    """Order by the number after ``-H``: ``H10`` follows ``H9``."""
    number = design_number(design_id)
    return (-1 if number is None else number, design_id)


def _newest_first(group: list[DesignSummary]) -> list[DesignSummary]:
    naive = [d for d in group if d.created_at.tzinfo is None]
    if naive and len(naive) != len(group):
        aware = next(d for d in group if d.created_at.tzinfo is not None)
        # Which zone a bare time means is unknowable, so no order is guessed.
        raise ValueError(
            f"created_at of '{naive[0].id}' has no time zone but that of "
            f"'{aware.id}' has one: they cannot be ordered"
        )
    return sorted(group, key=lambda d: (d.created_at, _id_key(d.id)), reverse=True)


def _card_order(designs: list[DesignSummary]) -> list[DesignSummary]:
    """Unfinished designs first, then finished ones; the newest first in each."""
    finished = [d for d in designs if d.status in TERMINAL_STATUSES]
    unfinished = [d for d in designs if d not in finished]
    return _newest_first(unfinished) + _newest_first(finished)


def _note_link(design_id: str) -> Html:
    return _link(note_anchor(design_id), "分析ノートを開く")


def _counts(context: _Context) -> Html:
    found = Counter(context.progress.values())
    return el(
        "section",
        el("h2", "進捗の数"),
        el(
            "p",
            join(
                el("span", f"{PROGRESS_WORDS[p][0]} {found[p]}", class_="count")
                for p in Progress
            ),
        ),
        id="counts",
    )


def _decision_head(decision: TreeDecision) -> list[Html | str]:
    """The kind of a decision, when it was taken, and the node it names."""
    when = (
        ""
        if decision.kind is TreeDecisionKind.start
        else "（振り返りの前）"
        if decision.round == 0
        else f"（回 {decision.round} の振り返りの後）"
    )
    return [
        f"{_DECISION_LABELS[decision.kind]}{when}: ",
        _link(decision.node_id, decision.node_id),
    ]


def _decisions(tree: QuestionTree) -> Html:
    rows = [el("li", *_decision_head(d), f" {d.reason}") for d in tree.decisions]
    body = el("ul", join(rows)) if rows else el("p", "まだ決めていない。")
    return el("section", el("h2", "ツリーの決定"), body, id="decisions")


def _next_question(tree: QuestionTree) -> Html:
    """The last decision: it names the question to look into next, and why."""
    lines: list[Html]
    if not tree.decisions:
        lines = [el("p", "まだ決めていない。")]
    else:
        decision = tree.decisions[-1]
        latest = tree.current_round()
        # A reflection round written after the last decision still waits for its own.
        waiting = (
            f"回 {latest} の振り返りの後は、まだ決めていない。最後に決めたこと: "
            if decision.round < latest
            else None
        )
        lines = [
            el(
                "p",
                waiting,
                *_decision_head(decision),
                f" {tree.node(decision.node_id).question}",
            ),
            el("p", f"理由: {decision.reason}"),
        ]
        if decision.kind is TreeDecisionKind.close:
            lines.append(el("p", "区切ったので、次に調べる論点は決まっていない。"))
    return el("section", join([el("h2", "次に調べる論点"), *lines]), id="next-question")


def _subject_answer(context: _Context) -> Html:
    """The current answer to the subject and what it changed, ahead of everything else."""
    root = context.tree.root()
    answer = root.current_answer()
    parts: list[Html | None] = [el("h2", f"{_SUBJECT}への現時点の答え")]
    match context.shown(root):
        case Shown.unanswered:
            parts.append(el("p", f"{_SUBJECT}にはまだ答えていない。"))
        case Shown.violating:
            parts.append(_checked_in_its_card(root))
        case Shown.sound:
            assert answer is not None  # an answered node
            parts += _answer_lines(context, root, answer)
            parts.append(_changes(context, root, "h3"))
    return el("section", join(parts), class_="now", id="subject-answer")


def _check_notice(violations: Sequence[Violation] | CheckFailed) -> Html | None:
    if not isinstance(violations, CheckFailed):
        return None
    return el(
        "p",
        f"答えを記録と照らして確かめられなかった（{violations.message}）。"
        "答えが記録と合うかは確かめていない。",
        class_="notice",
        id="check-notice",
    )


def _notes(node: QuestionNode) -> Html | None:
    note = node.next_candidate
    if note is None:
        return None
    rows = [
        el("li", f"{label}: {getattr(note, field)}")
        for field, label in _NOTE_LABELS
        if getattr(note, field)
    ]
    if note.answer:
        rows.append(
            el(
                "li",
                f"聞いてきた答え: {note.answer}"
                f"（{note.answered_by}、{note.answered_at}）",
            )
        )
    return el("ul", join(rows), class_="notes")


def _next_candidates(context: _Context) -> Html:
    items = [
        el(
            "li",
            el("strong", _link(node.id, node.id)),
            f" {node.question}",
            _notes(node) or el("p", "まだメモは無い。", class_="note"),
        )
        for node in context.tree.untouched_nodes()
    ]
    return el(
        "section",
        el("h2", "次の候補"),
        el(
            "p",
            "分析設計をまだ結んでいない論点。人に聞く問いと、聞いてきた答えを添える。",
            class_="note",
        ),
        el("ul", join(items)) if items else el("p", "着手していない論点は無い。"),
        id="next-candidates",
    )


def _question_tree(context: _Context) -> Html:
    tree = context.tree

    def branch(node: QuestionNode) -> Html:
        designs = [
            el("li", _design_card(context, node, design))
            for design in _card_order([context.designs[d] for d in node.design_ids])
        ]
        below = [branch(c) for c in context.children.get(node.id, [])]
        items = designs + below
        return el(
            "li",
            _node_card(context, node),
            el("ul", join(items)) if items else None,
            id=node.id,
        )

    return el(
        "section",
        el("h2", "論点ツリー"),
        el("ul", branch(tree.root()), class_="tree"),
        id="question-tree",
    )


def _comments_after_analysis(count: int) -> list[str]:
    """The count of the result review's comments; nothing when there is none."""
    return [f"{AFTER_ANALYSIS} コメント: {count} 件", "　"] if count else []


def _design_card(context: _Context, node: QuestionNode, design: DesignSummary) -> Html:
    """The full card under the first node on the page; a short row under the others."""
    word = status_word(design.form, design.status)
    first = context.linked_by[design.id][0]
    if first != node.id:
        return el(
            "div",
            el(
                "p",
                el("strong", design.id),
                f"　{word}　",
                _link(first, f"{first} の下に出ている"),
                class_="meta",
            ),
            class_=f"branch form-{design.form.value}",
        )
    statement = FORM_WORDS[design.form].statement
    return el(
        "div",
        el(
            "p",
            el("span", f"分析設計・{design.intent}", class_="form-tag"),
            el("strong", _link(f"design-{design.id}", design.id)),
            f" {design.title}",
        ),
        el("p", f"{statement}: {design.statement}") if design.statement else None,
        el(
            "p",
            word,
            "　",
            *_comments_after_analysis(design.comments_after_analysis),
            _note_link(design.id),
            class_="meta",
        ),
        class_=f"branch form-{design.form.value}",
    )


def _node_card(context: _Context, node: QuestionNode) -> Html:
    progress = context.progress[node.id]
    meta: list[Html | str] = [
        "進捗: ",
        el("span", PROGRESS_WORDS[progress][0], class_="progress"),
    ]
    if node.parent_question_id is not None:
        meta.append(f"　寄与: {node.contribution}")
    if node.origin_event_id is not None:
        meta.append(f"　発見元: {node.origin_event_id}")
    answer = node.current_answer()
    violated = context.violations.get(node.id, ())
    parts: list[Html | None] = [
        el("p", el("strong", node.id), f" {node.question}"),
        el("p", *meta, class_="meta"),
    ]
    match context.shown(node):
        case Shown.unanswered:
            parts.append(el("p", "まだ答えていない"))
        case Shown.violating:
            assert answer is not None  # an answered node
            parts += [
                _marks(context, node, answer),
                _current_round_meta(context, answer),
            ]
        case Shown.sound:
            assert answer is not None  # an answered node
            parts += _answer_lines(context, node, answer, heading="現時点の答え")
            parts.append(_changes_on_the_card(context, node))
    parts += [_notes(node), _evidence(context, node, violated)]
    return el("div", join(parts), class_=f"node progress-{progress.value}")


def _evidence(
    context: _Context, node: QuestionNode, violated: Sequence[Violation]
) -> Html:
    answer = node.current_answer()
    sections: list[Html] = []
    if answer is not None:
        if violated:
            sections += [
                el("h4", "記録と合わない点"),
                el(
                    "ul",
                    join(_violation(v) for v in violated),
                ),
                el(
                    "details",
                    el("summary", "記録と合わなかった答えの文"),
                    _cited_statements(context, answer),
                ),
            ]
        else:
            sections += [
                el("h4", "現時点の答えの根拠"),
                _cited_statements(context, answer),
            ]
        earlier = list(reversed(node.answers[:-1]))
        if earlier:
            sections.append(el("h4", "前の回の答え"))
            sections += [_earlier_answer(a) for a in earlier]
    if not sections:
        sections.append(el("p", "まだ根拠は無い。"))
    return el("details", el("summary", f"{node.id} の根拠を開く"), join(sections))


def _violation(violation: Violation) -> Html:
    word = _VIOLATION_WORDS[violation.kind]
    return el(
        "li",
        f"文 {violation.statement}: {word}（{violation.kind}）",
        el("blockquote", violation.text),
    )


def _cited_statements(context: _Context, answer: Answer) -> Html:
    return el(
        "ul",
        join(
            _statement(s, el("ul", join(_cited_event(context, c) for c in s.cites)))
            for s in answer.statements
        ),
    )


def _cited_event(context: _Context, event_id: str) -> Html:
    event = context.events.get(event_id)
    if event is None:
        return el("li", f"journal に見つからない出来事 {event_id}")
    design_id = design_id_of(event_id)
    parts: list[Html | str] = [
        el("strong", event_id),
        " design: ",
        _link(f"design-{design_id}", design_id),
    ]
    if event.type:
        parts.append(f" type: {event.type}")
    design = context.designs.get(design_id)
    form = None if design is None else design.form
    # An exploration holds no hypothesis, so no direction leans on one (ADR-0051).
    if event.direction and (form is None or form.judges):
        gloss = None if form is None else direction_gloss(form, event.direction)
        parts.append(
            f" direction: {event.direction}" + (f"（{gloss}）" if gloss else "")
        )
    parts.append(el("blockquote", event.content))
    return el("li", *parts)


def _earlier_answer(answer: Answer) -> Html:
    return el(
        "div",
        _round_meta(answer),
        el(
            "ul",
            join(
                _statement(s, f"（引用: {', '.join(s.cites)}）")
                for s in answer.statements
            ),
        ),
    )


def _derivation(context: _Context) -> Html:
    designs = context.designs
    children: dict[str, list[str]] = {}
    for design in designs.values():
        if design.parent_id in designs:
            children.setdefault(design.parent_id, []).append(design.id)
    shown: set[str] = set()

    def branch(design_id: str) -> Html:
        shown.add(design_id)
        design = designs[design_id]
        nodes = context.linked_by.get(design_id, [])
        facts: list[Html | str] = [
            f"{status_word(design.form, design.status)}　",
            # A linked design shows its count on its card; one linked to no node has
            # no card, so its count goes here. Each count is on the page once.
            *(
                []
                if nodes
                else _comments_after_analysis(design.comments_after_analysis)
            ),
            _note_link(design_id),
            "　",
        ]
        facts += (
            ["結んだ論点: ", *(_join_links(nodes))] if nodes else ["論点に結んでいない"]
        )
        if design.parent_id is not None and design.parent_id not in designs:
            facts.append(f"　派生元: {design.parent_id}")
        below = [
            c
            for c in sorted(children.get(design_id, []), key=_id_key)
            if c not in shown
        ]
        return el(
            "li",
            el(
                "div",
                el("p", el("strong", design.id), f" {design.title}"),
                el("p", *facts, class_="meta"),
                class_="design",
            ),
            el("ul", join(branch(c) for c in below)) if below else None,
            id=f"design-{design_id}",
        )

    top = [
        d for d in sorted(designs, key=_id_key) if designs[d].parent_id not in designs
    ]
    items = [branch(d) for d in top]
    # A cycle of parents has no top-level design; show its members anyway.
    items += [branch(d) for d in sorted(designs, key=_id_key) if d not in shown]
    body = (
        el("ul", join(items), class_="derivation")
        if items
        else el("p", "分析設計はまだ無い。")
    )
    return el(
        "section",
        el("h2", "分析設計の派生"),
        el(
            "p",
            "分析設計の parent_id で辿る親子。論点の親子とは別の構造。",
            class_="note",
        ),
        body,
        id="derivation",
    )


def _back_links(context: _Context, design_id: str) -> Html:
    nodes = context.linked_by.get(design_id, [])
    parts: list[Html | str] = [_link("question-tree", "論点ツリーへ戻る")]
    if nodes:
        parts += ["　結んだ論点: ", *_join_links(nodes)]
    return el("p", *parts, class_="meta")


def _design_notes(context: _Context) -> Html:
    # The back link sits above and below a note: the note is long, so the way
    # back must be in reach from both ends.
    blocks = [
        join(
            [
                _back_links(context, design_id),
                context.design_notes[design_id],
                _back_links(context, design_id),
            ]
        )
        for design_id in sorted(context.designs, key=_id_key)
    ]
    return el(
        "section",
        el("h2", "分析設計ごとの分析ノート"),
        join(blocks) if blocks else el("p", "分析ノートはまだ無い。"),
        id="design-notes",
    )
