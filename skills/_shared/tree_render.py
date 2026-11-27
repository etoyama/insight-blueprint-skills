"""Render a question tree as one self-contained HTML page (Epic 18, ADR-0024).

Pure: no I/O. ``tree_read.render`` (CLI: ``tree_io render``) reads the files
and hands the data in here.
The page has no script, no external resource and no timestamp, so the same
inputs give the same bytes. Interaction is ``<details>`` only.

Every string that reaches the page comes from analysts or models, so none of it
is trusted: see ``_html`` for how markup is told from text.

The page is built in five modules: this one lays out the sections,
``tree_render_parts`` holds the context of a page and the parts the sections
share, ``tree_render_derived`` shows what ``tree_changes`` derives,
``tree_render_stage`` shows where each analysis stands, and ``tree_words``
holds the words and the legend.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from insight_blueprint.models.analysis_stage import SETTLED, AnalysisStage
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
from skills._shared.design_note import (
    FORM_WORDS,
    NOTE_CSS,
    direction_gloss,
    note_anchor,
)
from skills._shared.design_note_reviews import AFTER_ANALYSIS
from skills._shared.tree_check import CitedEvent, Violation
from skills._shared.tree_render_derived import (
    changes_section,
    left_out_sections,
    pointers_to_the_top,
    used_above_section,
)
from skills._shared.tree_render_parts import (
    CheckFailed,
    Context,
    DesignSummary,
    Shown,
    answer_lines,
    current_round_meta,
    id_key,
    join_links,
    join_parts,
    link_to,
    mark_line,
    result_lines,
    statement_item,
    word_of,
)
from skills._shared.tree_render_stage import (
    STAGE_CSS,
    asks_section,
    stage_notes,
    stage_parts,
)
from skills._shared.tree_words import (
    AIM_LABELS,
    BACK_TO_TREE,
    COUNTS_HEADING,
    CURRENT_ANSWER_HEADING,
    DECISION_LABELS,
    DESIGN_TAG,
    GROUNDS_WORDS,
    LINKED_NODES,
    MARK_WORDS,
    NEXT_CANDIDATES_HEADING,
    NEXT_QUESTION_HEADING,
    NO_GROUNDS_WORDS,
    NOTE_LABELS,
    OPEN_EVIDENCE,
    OPEN_NOTE,
    PROGRESS_WORDS,
    RESULT_WORD,
    SHARED_ID_WORDS,
    STAGE_LABEL,
    SUBJECT,
    VIOLATION_WORDS,
    Mark,
    before_revision,
    below_text,
    legend,
    reflection,
    revision_name,
    when_decided,
)

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
.uncited { border-left: 4px solid var(--investigating); padding: .1rem .7rem; margin: .6rem 0; }
.uncited-before, .cited-above {
  border-left: 4px solid var(--line); padding: .1rem .7rem; margin: .6rem 0;
}
.uncited h3, .uncited h4, .cited-above h4 { margin: .3rem 0; font-size: 1rem; }
.uncited-before summary { color: var(--muted); }
.closed { border-left: 4px solid var(--investigating); padding: .1rem .7rem; margin: .6rem 0; }
.grounds ul { margin: .2rem 0; }
.grounds blockquote { margin: .2rem 0; padding-left: .6rem; border-left: 3px solid var(--line); }
.uncited li, .uncited-before li, .cited-above li { margin: .4rem 0; }
.uncited blockquote, .uncited-before blockquote {
  margin: .2rem 0; padding-left: .6rem; border-left: 3px solid var(--line);
}
"""


def render_tree_html(
    tree: QuestionTree,
    designs: Mapping[str, DesignSummary],
    events: Mapping[str, CitedEvent],
    violations: Sequence[Violation] | CheckFailed,
    design_notes: Mapping[str, Html],
    *,
    shared: frozenset[str],
) -> str:
    """The page. *design_notes* maps a design id to the markup ``render_note`` returned.

    *shared* holds the cited ids two journal events share; a decision citing one
    shows neither text.
    """
    context = Context.of(tree, designs, events, violations, design_notes, shared)
    body = join(
        [
            _header(tree),
            _check_notice(violations),
            asks_section(context),
            _subject_answer(context),
            _next_question(context),
            legend(),
            _counts(context),
            _decisions(context),
            _next_candidates(context),
            _question_tree(context),
            _derivation(context),
            _design_notes(context),
        ]
    )
    return page(
        f"論点ツリー {tree.theme_id}", BASE_CSS + _TREE_CSS + STAGE_CSS + NOTE_CSS, body
    )


def _header(tree: QuestionTree) -> Html:
    revision = tree.current_revision()
    parts = [
        el("h1", f"論点ツリー {tree.theme_id}"),
        el("p", el("strong", f"{SUBJECT}: "), revision.question),
        *(el("p", line) for line in _aim_lines(revision.aim)),
    ]
    # A subject never revised says nothing of revisions (the analyst never reads 版).
    if len(tree.root_revisions) > 1:
        revised = len(tree.root_revisions) - 1
        parts += [
            el(
                "p",
                link_to("root-history", f"{SUBJECT}を{revised}回見直した"),
                class_="meta",
            ),
            _root_history(tree),
        ]
    return el("header", join(parts), id="header")


def _aim_lines(aim: Aim) -> list[str]:
    return [f"{label}: {getattr(aim, field)}" for label, field in AIM_LABELS[aim.kind]]


def _root_history(tree: QuestionTree) -> Html:
    rows = []
    for revision in tree.root_revisions:
        aim = "、".join(_aim_lines(revision.aim))
        rows.append(
            el(
                "li",
                f"{revision_name(revision.revision)}: {revision.question}（{aim}）",
                f" 理由: {revision.reason}" if revision.reason else "",
            )
        )
    return el(
        "details",
        el("summary", f"{SUBJECT}を見直した履歴"),
        el("ul", join(rows)),
        id="root-history",
    )


def _newest_first(group: list[DesignSummary]) -> list[DesignSummary]:
    naive = [d for d in group if d.created_at.tzinfo is None]
    if naive and len(naive) != len(group):
        aware = next(d for d in group if d.created_at.tzinfo is not None)
        # Which zone a bare time means is unknowable, so no order is guessed.
        raise ValueError(
            f"created_at of '{naive[0].id}' has no time zone but that of "
            f"'{aware.id}' has one: they cannot be ordered"
        )
    return sorted(group, key=lambda d: (d.created_at, id_key(d.id)), reverse=True)


def _card_order(designs: list[DesignSummary]) -> list[DesignSummary]:
    """Unfinished designs, then finished ones, then stopped ones; the newest first in each.

    A stopped analysis is never resumed (ADR-0064), so it is read last.
    """
    groups = (
        [d for d in designs if d.stage not in SETTLED],
        [d for d in designs if d.stage is AnalysisStage.finished],
        [d for d in designs if d.stage is AnalysisStage.stopped],
    )
    return [d for group in groups for d in _newest_first(group)]


def _note_link(design_id: str) -> Html:
    return link_to(note_anchor(design_id), OPEN_NOTE)


def _counts(context: Context) -> Html:
    found = Counter(context.progress.values())
    return el(
        "section",
        el("h2", COUNTS_HEADING),
        el(
            "p",
            join(
                el("span", f"{PROGRESS_WORDS[p][0]} {found[p]}", class_="count")
                for p in Progress
            ),
        ),
        id="counts",
    )


def _decision_kind(decision: TreeDecision) -> str:
    """The kind of a decision and when it was taken."""
    when = (
        ""
        if decision.kind is TreeDecisionKind.start
        else f"（{when_decided(decision.round)}）"
    )
    return f"{DECISION_LABELS[decision.kind]}{when}: "


def _decision_head(decision: TreeDecision) -> list[Html | str]:
    """The kind of a decision, when it was taken, and every node it names (ADR-0061)."""
    return [_decision_kind(decision), *join_links(decision.node_ids())]


def _grounds(context: Context, decision: TreeDecision) -> Html | None:
    """What the reason of *decision* rests on, or that it names nothing (ADR-0058).

    The first decision comes before any analysis, so it is not told to cite.
    """
    if not decision.cites:
        if decision.kind is TreeDecisionKind.start:
            return None
        return el("p", NO_GROUNDS_WORDS, class_="meta")
    # The event kept for a shared id may not be the one cited, so it names no word.
    words = list(
        dict.fromkeys(
            RESULT_WORD if c in context.shared else word_of(context, c)
            for c in decision.cites
        )
    )
    rows = [
        el("li", SHARED_ID_WORDS.format(event_id=c))
        if c in context.shared
        else el("li", *result_lines(context, c))
        for c in decision.cites
    ]
    return el(
        "div",
        el("p", GROUNDS_WORDS.format(word="と".join(words)), class_="meta"),
        el("ul", join(rows)),
        class_="grounds",
    )


def _decisions(context: Context) -> Html:
    rows = [
        el("li", *_decision_head(d), f" {d.reason}", _grounds(context, d))
        for d in context.tree.decisions
    ]
    body = el("ul", join(rows)) if rows else el("p", "まだ決めていない。")
    return el("section", el("h2", "論点ツリーの決定"), body, id="decisions")


def _next_question(context: Context) -> Html:
    """The last decision: it names the question to look into next, and why."""
    tree = context.tree
    lines: list[Html | None]
    if not tree.decisions:
        lines = [el("p", "まだ決めていない。")]
    else:
        decision = tree.decisions[-1]
        latest = tree.current_round()
        # A reflection round written after the last decision still waits for its own.
        waiting = (
            f"{reflection(latest)}の後は、まだ決めていない。最後に決めたこと: "
            if decision.round < latest
            else None
        )
        named = join_parts(
            [link_to(n, n), f" {tree.node(n).question}"] for n in decision.node_ids()
        )
        lines = [
            el("p", waiting, _decision_kind(decision), *named),
            el("p", f"理由: {decision.reason}"),
        ]
        lines.append(_grounds(context, decision))
        if decision.kind is TreeDecisionKind.close:
            lines.append(
                el("p", f"区切ったので、{NEXT_QUESTION_HEADING}は決まっていない。")
            )
    return el(
        "section", join([el("h2", NEXT_QUESTION_HEADING), *lines]), id="next-question"
    )


def _checked_in_its_card(node: QuestionNode) -> Html:
    """In place of an answer that failed the check: its mark and its card."""
    return el(
        "p",
        el("span", MARK_WORDS[Mark.violating][0], class_="mark"),
        " ",
        link_to(node.id, f"{node.id} のカードで確かめる"),
    )


def _subject_answer(context: Context) -> Html:
    """The current answer to the subject and what it changed, ahead of everything else."""
    root = context.tree.root()
    answer = root.current_answer()
    parts: list[Html | None] = [el("h2", f"{SUBJECT}への{CURRENT_ANSWER_HEADING}")]
    match context.shown(root):
        case Shown.unanswered:
            parts.append(el("p", f"{SUBJECT}にはまだ答えていない。"))
        case Shown.violating:
            parts.append(_checked_in_its_card(root))
        case Shown.sound:
            assert answer is not None  # an answered node
            parts += answer_lines(context, root, answer)
            parts.append(changes_section(context, root, "h3"))
    parts += left_out_sections(context, root, "h3")
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
        for field, label in NOTE_LABELS
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


def _next_candidates(context: Context) -> Html:
    items = [
        el(
            "li",
            el("strong", link_to(node.id, node.id)),
            f" {node.question}",
            _notes(node) or el("p", "まだメモは無い。", class_="note"),
        )
        for node in context.tree.untouched_nodes()
    ]
    return el(
        "section",
        el("h2", NEXT_CANDIDATES_HEADING),
        el(
            "p",
            "分析設計をまだ結んでいない論点。人に聞く問いと、聞いてきた答えを添える。",
            class_="note",
        ),
        el("ul", join(items)) if items else el("p", "着手していない論点は無い。"),
        id="next-candidates",
    )


def _question_tree(context: Context) -> Html:
    tree = context.tree

    def branch(node: QuestionNode) -> Html:
        designs = [
            el("li", _design_card(context, node, design))
            for design in _card_order([context.designs[d] for d in node.design_ids])
        ]
        below = [branch(c) for c in tree.children(node.id)]
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


def _design_card(context: Context, node: QuestionNode, design: DesignSummary) -> Html:
    """The full card under the first node on the page; a short row under the others."""
    first = context.linked_by[design.id][0]
    if first != node.id:
        return el(
            "div",
            el(
                "p",
                el("strong", design.id),
                "　",
                *stage_parts(design),
                "　",
                link_to(first, f"{first} の下に出ている"),
                class_="meta",
            ),
            class_=f"branch form-{design.form.value}",
        )
    statement = FORM_WORDS[design.form].statement
    return el(
        "div",
        el(
            "p",
            el("span", f"{DESIGN_TAG}{design.intent}", class_="form-tag"),
            el("strong", link_to(f"design-{design.id}", design.id)),
            f" {design.title}",
        ),
        el("p", f"{statement}: {design.statement}") if design.statement else None,
        el(
            "p",
            f"{STAGE_LABEL}: ",
            *stage_parts(design),
            "　",
            *_comments_after_analysis(design.comments_after_analysis),
            _note_link(design.id),
            class_="meta",
        ),
        join(stage_notes(design)),
        class_=f"branch form-{design.form.value}",
    )


def _progress_meta(context: Context, node: QuestionNode) -> list[Html | str]:
    """The progress word, the counts of the nodes under *node*, or both (ADR-0057)."""
    parts: list[Html | str] = []
    progress = context.progress.get(node.id)
    if progress is not None:
        parts += ["進捗: ", el("span", PROGRESS_WORDS[progress][0], class_="progress")]
    found = context.below[node.id]
    if found:
        parts += [
            "　" if parts else "",
            el(
                "span",
                below_text(node.is_root, found),
                class_="below",
            ),
        ]
    return parts


def _closed(context: Context, node: QuestionNode) -> Html | None:
    """The round a question was closed after, and why (ADR-0057)."""
    decision = context.closed_by(node)
    if decision is None:
        return None
    return el(
        "div",
        el("p", f"{when_decided(decision.round)}に区切った。理由: {decision.reason}"),
        _grounds(context, decision),
        class_="closed",
    )


def _node_card(context: Context, node: QuestionNode) -> Html:
    meta = _progress_meta(context, node)
    if not node.is_root:
        meta.append(f"　寄与: {node.contribution}")
    if node.origin_event_id is not None:
        meta.append(f"　発見元: {node.origin_event_id}")
    answer = node.current_answer()
    violated = context.violations.get(node.id, ())
    # The subject's answer, what it changed and what it leaves out lead the page.
    subject = node.is_root
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
                mark_line(context, node, answer),
                current_round_meta(context, answer),
            ]
        case Shown.sound:
            assert answer is not None  # an answered node
            parts += answer_lines(context, node, answer, heading=CURRENT_ANSWER_HEADING)
            if not subject:
                parts.append(changes_section(context, node, "h4"))
            parts.append(used_above_section(context, node, answer))
    parts.append(_closed(context, node))
    if subject:
        parts += pointers_to_the_top(context, node)
    else:
        parts += left_out_sections(context, node, "h4")
    parts += [_notes(node), _evidence(context, node, violated)]
    # The border colour is a progress word's: a node shown by its counts has none.
    progress = context.progress.get(node.id)
    colour = "" if progress is None else f" progress-{progress.value}"
    return el("div", join(parts), class_=f"node{colour}")


def _evidence(
    context: Context, node: QuestionNode, violated: Sequence[Violation]
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
                el("h4", f"{CURRENT_ANSWER_HEADING}の根拠"),
                _cited_statements(context, answer),
            ]
        earlier = list(reversed(node.answers[:-1]))
        if earlier:
            sections.append(el("h4", "前の振り返りの答え"))
            sections += [_earlier_answer(context.tree, a) for a in earlier]
    if not sections:
        sections.append(el("p", "まだ根拠は無い。"))
    return el("details", el("summary", f"{node.id} の{OPEN_EVIDENCE}"), join(sections))


def _violation(violation: Violation) -> Html:
    word = VIOLATION_WORDS[violation.kind]
    return el(
        "li",
        f"文 {violation.statement}: {word}（{violation.kind}）",
        el("blockquote", violation.text),
    )


def _cited_statements(context: Context, answer: Answer) -> Html:
    return el(
        "ul",
        join(
            statement_item(s, el("ul", join(_cited_event(context, c) for c in s.cites)))
            for s in answer.statements
        ),
    )


def _cited_event(context: Context, event_id: str) -> Html:
    event = context.events.get(event_id)
    if event is None:
        return el("li", f"journal に見つからない出来事 {event_id}")
    design_id = design_id_of(event_id)
    parts: list[Html | str] = [
        el("strong", event_id),
        " design: ",
        link_to(f"design-{design_id}", design_id),
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


def _round_meta(tree: QuestionTree, answer: Answer) -> Html:
    """The round of an earlier answer: it carries no mark, so it says its subject."""
    before = before_revision(tree, answer.root_revision)
    tail = f"（{before}）" if before else ""
    return el("p", f"{reflection(answer.round)}{tail}", class_="meta")


def _earlier_answer(tree: QuestionTree, answer: Answer) -> Html:
    return el(
        "div",
        _round_meta(tree, answer),
        el(
            "ul",
            join(
                statement_item(s, f"（引用: {', '.join(s.cites)}）")
                for s in answer.statements
            ),
        ),
    )


def _derivation(context: Context) -> Html:
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
            *stage_parts(design),
            "　",
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
            [f"{LINKED_NODES}: ", *(join_links(nodes))]
            if nodes
            else ["論点に結んでいない"]
        )
        if design.parent_id is not None and design.parent_id not in designs:
            facts.append(f"　派生元: {design.parent_id}")
        below = [
            c for c in sorted(children.get(design_id, []), key=id_key) if c not in shown
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
        d for d in sorted(designs, key=id_key) if designs[d].parent_id not in designs
    ]
    items = [branch(d) for d in top]
    # A cycle of parents has no top-level design; show its members anyway.
    items += [branch(d) for d in sorted(designs, key=id_key) if d not in shown]
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


def _back_links(context: Context, design_id: str) -> Html:
    nodes = context.linked_by.get(design_id, [])
    parts: list[Html | str] = [link_to("question-tree", BACK_TO_TREE)]
    if nodes:
        parts += [f"　{LINKED_NODES}: ", *join_links(nodes)]
    return el("p", *parts, class_="meta")


def _design_notes(context: Context) -> Html:
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
        for design_id in sorted(context.designs, key=id_key)
    ]
    return el(
        "section",
        el("h2", "分析設計ごとの分析ノート"),
        join(blocks) if blocks else el("p", "分析ノートはまだ無い。"),
        id="design-notes",
    )
