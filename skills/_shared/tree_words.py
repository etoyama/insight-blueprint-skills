"""The words a question tree shows the analyst, and what the legend says of them.

The page (``tree_render``) and the report (``theme_report``) read every word
they share from here, so a word is changed in one place (ADR-0055). Each table
holds the word next to what the legend says it means, and the legend is built
here, so neither can drift from the page.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum

from insight_blueprint.models.design import DesignForm, DesignStatus
from insight_blueprint.models.tree import (
    AimKind,
    Answer,
    Progress,
    QuestionTree,
    StatementKind,
    TreeDecisionKind,
)
from skills._shared._html import Html, el, join
from skills._shared.design_note import intent_words_of, status_word
from skills._shared.tree_changes import ChangeKind

# The words the page says of the subject (ADR-0055); YAML and code say root.
SUBJECT = "主題"


# A reflection round and a revision of the subject, as the analyst counts them:
# the page never says 回 N. "{round}" is a number on a page and "N" in the legend.
_NTH = "{round}回目"
_REFLECTION = f"{_NTH}の振り返り"
_BEFORE_REVISION = f"見直す前の{SUBJECT}への答え"
_THIS_QUESTION = "この論点"

CHANGES_HEADING = "前の振り返りから変わったこと"


def reflection(round: int) -> str:
    """A reflection round as the analyst counts it."""
    return _REFLECTION.format(round=round)


def changes_title(before: int, now: int) -> str:
    """The heading of what an answer changed, with the two rounds it compares."""
    return f"{CHANGES_HEADING}（{_NTH.format(round=before)} → {reflection(now)}）"


def left_as_written(latest: int, round: int) -> str:
    """That the rounds after *round*, up to *latest*, left an answer as it is."""
    return (
        f"　最新の振り返りは{_NTH.format(round=latest)}で、"
        f"{_NTH.format(round=round)}より後の振り返りでは、"
        "この答えを書き直していない。"
    )


def when_decided(round: int) -> str:
    """When a decision was taken: before any reflection, or after one."""
    return "振り返りの前" if round == 0 else f"{reflection(round)}の後"


def whose_answer(subject: bool) -> str:
    """Whose answer a section speaks of: the subject's, or this question's."""
    return f"{SUBJECT}への" if subject else f"{_THIS_QUESTION}の"


def revision_name(revision: int) -> str:
    """Which subject a revision is, counted by the times the subject was revised."""
    if revision == 1:
        return f"最初の{SUBJECT}"
    return f"{_NTH.format(round=revision - 1)}の見直しの後の{SUBJECT}"


def before_revision(tree: QuestionTree, revision: int) -> str | None:
    """What an answer to *revision* of the subject is, when the subject was revised since.

    The page names no revision by number: the analyst counts the times the
    subject was revised, and hears of it only once it was.
    """
    if revision >= tree.current_revision().revision:
        return None
    if len(tree.root_revisions) == 2:
        return _BEFORE_REVISION
    return f"{_NTH.format(round=revision)}の見直しの前の{SUBJECT}への答え"


AIM_LABELS = {
    AimKind.business: (
        ("決める人", "decision_maker"),
        ("決めること", "decision"),
    ),
    AimKind.research: (
        ("想定読者", "audience"),
        ("主張の範囲", "claim_scope"),
    ),
}


class Mark(StrEnum):
    """What a reader must notice about the current answer of a node."""

    changed = "changed"
    first = "first"
    before_root_change = "before_root_change"
    violating = "violating"


# Each table holds the word shown on the page and what the legend says it means,
# so the legend cannot drift from the page.
PROGRESS_WORDS = {
    Progress.not_started: ("未着手", "分析設計を結んでいない。"),
    Progress.investigating: ("検証中", "結んだ分析設計に、終わっていないものがある。"),
    Progress.analyzed: ("分析済み", "結んだ分析設計がすべて終わっている。"),
}


# The words shown to the analyst are not the glossary's terms (ADR-0055): the
# kinds keep their YAML values, the page says what each one tells the analyst.
KIND_WORDS = {
    StatementKind.claim: (
        "これまでわかっていること",
        "根拠にした分析結果から言えること。",
    ),
    StatementKind.undetermined: (
        "まだ決められないこと",
        "分析をしても、分析結果からは決められないこと。",
    ),
    StatementKind.weakening: (
        "注意すべきこと",
        "これまでわかっていることを弱める分析結果や、言える範囲を狭める条件。",
    ),
}


MARK_WORDS = {
    Mark.changed: (
        f"{_REFLECTION}で変わったこと",
        "最も新しい振り返り（N回目）で、前の振り返りから書き換わった答え。",
    ),
    Mark.first: (
        f"{_REFLECTION}で初めて答えたこと",
        "最も新しい振り返り（N回目）で、初めて書いた答え。",
    ),
    Mark.before_root_change: (
        _BEFORE_REVISION,
        f"{SUBJECT}か到達点を見直す前の{SUBJECT}に対して書いた答え。"
        f"2回以上見直したときは、この言葉の代わりに、何回目の見直しの前の{SUBJECT}"
        "への答えかを言う。",
    ),
    Mark.violating: (
        "記録と合わない答え",
        "引用した出来事が journal に無い、結んでいない分析設計の出来事を引いている、"
        "引用に無い数字を書いている、のどれかの答え。答えの文は閉じた中に畳む。",
    ),
}


# How the last answer of a node uses an analysis result, next to the answer
# before it. The page says only what the cites show (ADR-0056): it never says
# that a result moved the answer or that a claim was withdrawn.
CHANGE_WORDS = {
    ChangeKind.newly_cited: (
        "新しく根拠にした",
        "前の回の答えでは根拠にしていなかった分析結果を、この答えで根拠にした。",
    ),
    ChangeKind.dropped: (
        "根拠から外した",
        "前の回の答えでは根拠にしていた分析結果を、この答えでは根拠にしていない。",
    ),
    ChangeKind.reworded: (
        "言っていることが変わった",
        "同じ分析結果を根拠にしたまま、その分析結果について言っている文か、"
        "文の種類が変わった。"
        "言い回しを変えただけでも、ここに出る。",
    ),
    ChangeKind.unchanged: (
        "変わっていない",
        "同じ分析結果について、同じ文を言っている。表では畳んで出す。",
    ),
}


# The results an answer leaves out, and the answers above that rest on a
# result (ADR-0056). "{whose}" names the answer: the subject's, this node's, or
# none in the legend. The analyst never reads "below", "cite" or "event" (US-5).
NOT_YET_WORDS = "まだ{whose}答えに入れていない分析結果"
NO_LONGER_WORDS = "前は{whose}答えの根拠にしていて、今は外している分析結果"
USED_ABOVE_WORDS = "この論点の分析結果を根拠にしている答え"

# What an answer rests on, in the analyst's words: an event of the data, or what
# a person said (a hearing event is not called an analysis result, US-5 AC 5).
RESULT_WORD = "分析結果"


HEARD_RESULT_WORD = "人に聞いた答え"


HEARD_WORD = f"（{HEARD_RESULT_WORD}による）"


VIOLATION_WORDS = {
    "missing-event": "journal に無い出来事",
    "unlinked-design": "この論点に結んでいない分析設計の出来事",
    "number-not-cited": "引用した出来事に無い数字",
}


DECISION_LABELS = {
    TreeDecisionKind.start: "最初の論点を選ぶ",
    TreeDecisionKind.deepen: "深める",
    TreeDecisionKind.return_: "親に戻る",
    TreeDecisionKind.close: "区切る",
}


# How far the questions under a question have come (ADR-0057). "{whose}" is
# the subject or this question; the analyst never reads "below" alone (US-5).
BELOW_WORDS = "{whose}の下に置いた論点 {count} つ: "


def below_text(subject: bool, found: Counter[Progress]) -> str:
    """The progress below a node in words, as the page and the report say it."""
    whose = SUBJECT if subject else _THIS_QUESTION
    # The furthest first, as in the sample the analyst read (分析済み 3、未着手 1).
    counts = "、".join(
        f"{PROGRESS_WORDS[p][0]} {found[p]}" for p in reversed(Progress) if found[p]
    )
    return BELOW_WORDS.format(whose=whose, count=found.total()) + counts


# What a decision's reason rests on (ADR-0058). "{word}" is the word for what it
# cites: an analysis result, what a person said, or both.
GROUNDS_WORDS = "この理由の根拠にした{word}"
NO_GROUNDS_WORDS = "この理由は、根拠にした分析結果を挙げていない。"
SHARED_ID_WORDS = "{event_id} は記録に2つあり、どちらを根拠にしたかは分からない。"


NOTE_LABELS = (
    ("ask", "人に聞く問い"),
    ("changes_if", "その答えで変わる判断"),
    ("known", "分かっていること"),
)


def mark_text(tree: QuestionTree, mark: Mark, answer: Answer) -> str:
    if mark is Mark.before_root_change:
        before = before_revision(tree, answer.root_revision)
        assert before is not None  # the mark is given to such an answer only
        return before
    return MARK_WORDS[mark][0].format(round=answer.round)


def _word_list(words: Iterable[tuple[str, str]]) -> Html:
    return el("ul", join(el("li", f"{word}: {meaning}") for word, meaning in words))


def legend() -> Html:
    return el(
        "details",
        el("summary", "読み方"),
        el(
            "p",
            f"ページの冒頭には、{SUBJECT}への現時点の答え、前の回から変わったこと、"
            "次に調べる論点を出す。その下に、論点ごとのカードを並べる。",
        ),
        el(
            "p",
            f"「{CHANGES_HEADING}」は、答えと、その1つ前の答えを比べて、根拠にした"
            "分析結果ごとに1行で出す。分け方は、根拠にしたかどうかと、文が同じか"
            "どうかだけで決まる。なぜ変えたかは記録に無いので、出さない。",
        ),
        el(
            "p",
            "記録と照らして確かめるのは、それぞれの論点の今の答えだけである。"
            "表に並べる前の振り返りの文は、今の記録と照らし直していない。",
        ),
        _word_list(CHANGE_WORDS.values()),
        el(
            "p",
            f"「{NOT_YET_WORDS.format(whose='')}」は、論点の答えが一度も根拠にして"
            "いない分析結果を、その分析結果を根拠にした論点の答えと並べて出す。"
            "差が出なかった分析の結果も、ここに出る。"
            f"「{NO_LONGER_WORDS.format(whose='')}」は、最後に根拠にした振り返りと、"
            "その次の答えで新しく根拠にした分析結果を添えて、畳んで出す。"
            "外した理由は記録に無いので、出さない。",
        ),
        el(
            "p",
            f"「{USED_ABOVE_WORDS}」は、論点の分析結果を、上の論点の答えが"
            "どう使っているかを出す。上の論点が、この論点の答えより後の振り返りで、"
            "その分析結果について言っていることを変えていれば、変えた振り返りを書く。",
        ),
        el(
            "p",
            "進捗は、論点に結んだ分析設計の状態から導いた言葉。色は添えただけで、"
            "意味は言葉が持つ。",
        ),
        _word_list(PROGRESS_WORDS.values()),
        el(
            "p",
            "自分にも、下に置いた論点にも、分析設計を結んでいない論点は「未着手」と出し、"
            "「進捗の数」にも数える。自分には分析設計を結ばず、下に置いた論点のどれかに"
            "結んでいる論点は、進捗の言葉を出さず、下に置いた論点の進捗を、言葉ごとの数で"
            "出す。「進捗の数」は、その論点を数えない。分析設計を結んだ論点の下に論点を"
            "置いたときは、進捗の言葉の後ろに、下に置いた論点の数を添える。",
        ),
        el(
            "p",
            "ツリーの決定の理由の下には、理由の根拠にした分析結果を出す。"
            "根拠を挙げていない理由は、そのことを書く。区切った論点のカードには、"
            "区切った回と理由を出す。",
        ),
        el("p", "現時点の答えは、文ごとに種類の言葉を付けて並べる。"),
        _word_list(KIND_WORDS.values()),
        el("p", "答えの上に出す印。"),
        _word_list(
            (word.format(round="N"), meaning) for word, meaning in MARK_WORDS.values()
        ),
        el(
            "p",
            "振り返りは、テーマの答えを書き直したひと区切り。1回目、2回目と数える。",
        ),
        el(
            "p",
            f"文の後ろの「{HEARD_WORD}」は、引用した出来事がすべて{HEARD_RESULT_WORD}"
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
            "各論点の「根拠を開く」を押すと、引用した journal の出来事と、前の振り返りの答えが開く。",
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
