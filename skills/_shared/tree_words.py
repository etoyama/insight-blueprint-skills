"""The words a question tree shows the analyst, and what the legend says of them.

A word belongs here when it is said in two places or more: on the page
(``tree_render``) and in the report (``theme_report``), in two sections of the
page, or on the page and in the legend that explains it. So does every phrasing
that counts a reflection round or a revision of the subject. A sentence only
one section says stays with that section and takes its words from here. A word
is then changed in one place (ADR-0055).

Each table holds the word next to what the legend says it means, and the legend
is built here from the same names, so it cannot drift from the page.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from enum import StrEnum

from insight_blueprint.models.analysis_stage import AnalysisStage
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
from skills._shared.design_note import EVENT_WORDS, intent_words_of, status_word
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

# The headings and link texts of the page that the legend names.
COUNTS_HEADING = "進捗の数"
NEXT_QUESTION_HEADING = "次に調べる論点"
NEXT_CANDIDATES_HEADING = "次の候補"
CURRENT_ANSWER_HEADING = "現時点の答え"
DESIGN_TAG = "分析設計・"
OPEN_EVIDENCE = "根拠を開く"
OPEN_NOTE = "分析ノートを開く"
BACK_TO_TREE = "論点ツリーへ戻る"


def reflection(round: int) -> str:
    """A reflection round as the analyst counts it."""
    return _REFLECTION.format(round=round)


def _reflection_named() -> re.Pattern[str]:
    head, tail = _REFLECTION.split("{round}")
    return re.compile(rf"{re.escape(head)}(?<![0-9])(?P<n>\d+){re.escape(tail)}")


# A reflection round named in a sentence in the words of ``reflection``, its N
# as ``n``: the tree check does not count that N as a number (ADR-0065).
REFLECTION_NAMED = _reflection_named()
REFLECTION_OF_N = _REFLECTION.format(round="N")


def changes_title(before: int, now: int) -> str:
    """The heading of what an answer changed, with the two rounds it compares."""
    return f"{CHANGES_HEADING}（{_NTH.format(round=before)} → {reflection(now)}）"


def left_as_written(latest: int, round: int) -> str:
    """That the rounds after *round*, up to *latest*, left an answer as it is."""
    return (
        f"最新の振り返りは{_NTH.format(round=latest)}で、"
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


# Which marks an answer gets is decided by the page context; the enum lives
# here because the table of its words is keyed by it.
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
    Progress.stopped: ("止めた", "結んだ分析設計をすべて止めた。"),
    Progress.analyzed: (
        "分析済み",
        "結んだ分析設計が、止めたものを除いてすべて終わっている。",
    ),
}


# Where each analysis stands (ADR-0061 6), in the words the analyst read in the
# sample of Epic 35. The words are first drafts: a person reads them on the real
# page before 35.5 (FLOW-0019).
STAGE_WORDS = {
    AnalysisStage.before_run: (
        "任せる前",
        "分析をエージェントに任せる前で、まだデータに触っていない。",
    ),
    AnalysisStage.running: ("進行中", "エージェントが分析を進めている。"),
    AnalysisStage.awaiting_confirmation: (
        "あなたの確認待ち",
        "エージェントが、あなたに確認したいことを書いて止まっている。"
        "あなたが答えるまで、この分析は進まない。",
    ),
    AnalysisStage.stopped: (
        "止めた",
        "分析を止めた。再開はしない。やり直すときは、別の分析設計を作る。",
    ),
    AnalysisStage.awaiting_reflection: (
        "計算が終わり、振り返りを待っている",
        "notebook の計算が終わり、結果を振り返るのを待っている。",
    ),
    AnalysisStage.finished: ("終わった", "振り返りで、分析設計の結論を出した。"),
}

STAGE_LABEL = "分析の段階"
STOP_REASON = "止めた理由: "
WHAT_IS_ASKED = "確認したいこと: "
ASKS_LEAD = (
    "次の分析は、あなたの答えを待って止まっている。"
    "答えは、チャットでエージェントに伝える。"
)


def asks_heading(count: int) -> str:
    """The heading of the analyses that wait for the analyst, with how many."""
    return f"{STAGE_WORDS[AnalysisStage.awaiting_confirmation][0]}（{count}件）"


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
USED_ABOVE_WORDS = f"{_THIS_QUESTION}の分析結果を根拠にしている答え"

# What an answer rests on, in the analyst's words: an event of the data, or what
# a person said (a hearing event is not called an analysis result, US-5 AC 5).
RESULT_WORD = "分析結果"


HEARD_RESULT_WORD = EVENT_WORDS["hearing"]


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
            f"ページの冒頭には、{SUBJECT}への{CURRENT_ANSWER_HEADING}、前の回から変わったこと、"
            f"{NEXT_QUESTION_HEADING}を出す。あなたの確認を待つ分析があれば、"
            "それらより前に抜き出す。その下に、論点ごとのカードを並べる。",
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
            "進捗は、論点に結んだ分析設計がどこまで進んだかから導いた言葉。色は添えただけで、"
            "意味は言葉が持つ。",
        ),
        _word_list(PROGRESS_WORDS.values()),
        el(
            "p",
            "自分にも、下に置いた論点にも、分析設計を結んでいない論点は"
            f"「{PROGRESS_WORDS[Progress.not_started][0]}」と出し、"
            f"「{COUNTS_HEADING}」にも数える。自分には分析設計を結ばず、下に置いた論点のどれかに"
            "結んでいる論点は、進捗の言葉を出さず、下に置いた論点の進捗を、言葉ごとの数で"
            f"出す。「{COUNTS_HEADING}」は、その論点を数えない。分析設計を結んだ論点の下に論点を"
            "置いたときは、進捗の言葉の後ろに、下に置いた論点の数を添える。",
        ),
        el(
            "p",
            f"{STAGE_LABEL}は、論点に結んだ分析設計ごとに、分析設計の状態と journal "
            "から導いた言葉。進捗は論点ごとに、分析の段階は分析設計ごとに出す。"
            "色は添えただけで、意味は言葉が持つ。",
        ),
        _word_list(STAGE_WORDS.values()),
        el(
            "p",
            f"「{STAGE_WORDS[AnalysisStage.awaiting_confirmation][0]}」の分析は、"
            "ページの冒頭にも抜き出す。止めた分析には止めた理由を、確認待ちの分析には"
            "確認したいことを添える。分析設計の状態の言葉は、任せる前と終わった"
            "分析設計にだけ添える。",
        ),
        el(
            "p",
            "論点ツリーの決定の理由の下には、理由の根拠にした分析結果を出す。"
            "根拠を挙げていない理由は、そのことを書く。区切った論点のカードには、"
            "区切った回と理由を出す。",
        ),
        el("p", f"{CURRENT_ANSWER_HEADING}は、文ごとに種類の言葉を付けて並べる。"),
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
        el(
            "p",
            f"まだ分析設計を結んでいない論点は「{NEXT_CANDIDATES_HEADING}」に並べる。",
        ),
        el(
            "p",
            "論点の下には、その論点に結んだ分析設計を、子の論点より先に並べる。"
            f"分析設計のカードは破線の枠で、「{DESIGN_TAG}」と意図の言葉で始まる。"
            "同じ分析設計を2つ目の論点からは、id、状態の言葉、最初に出た論点への"
            "リンクだけの短い行で出す。",
        ),
        el(
            "p",
            "分析設計の状態は、次の言葉で出す。判定は分析設計の検証仮説（旧形式では"
            "仮説）に対するもので、論点の答えではない。論点の答えは、論点のカードの"
            f"「{CURRENT_ANSWER_HEADING}」に書く。",
        ),
        _status_table(),
        el(
            "p",
            f"各論点の「{OPEN_EVIDENCE}」を押すと、引用した journal の出来事と、"
            "前の振り返りの答えが開く。",
        ),
        el("p", "論点の親子と分析設計の派生は別の構造なので、2つの節に分けて並べる。"),
        el(
            "p",
            f"「{OPEN_NOTE}」は、その分析設計の分析ノートへ飛ぶ。分析ノートはこの"
            "ページの下に、分析設計ごとに並べてある。分析ノートの冒頭と末尾の"
            f"「{BACK_TO_TREE}」で、論点ツリーの節へ戻る。",
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
