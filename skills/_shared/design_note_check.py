"""The check of the computation as the analysis note and the tree page show it (Epic 36).

Pure: no I/O. ``design_note_read`` reads the check through
``design_check.check_reading`` (ADR-0070), the one reader of the record, and
hands it in here as a ``NoteCheck``. Whether a check is done, and what differs,
is decided there; this module only lays it out. The sentence of a difference is
the one the check wrote, shown as written.

The words of the subjects live here and not in ``design_note``: the note's
method section, the check and the check before a hand-over name what a design
counts in the same words, and this module imports nothing of the note.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from insight_blueprint.models.check import (
    CheckedBy,
    CheckItem,
    CheckResult,
    CheckSubject,
)
from skills._shared._html import Html, el, join, table

CHECK_HEADING = "分析設計どおりに計算したかの点検"

# The order of the words is the order of the subjects of a check.
CHECK_SUBJECT_WORDS: Mapping[CheckSubject, str] = {
    CheckSubject.population: "対象",
    CheckSubject.grain: "粒度",
    CheckSubject.denominator: "分母",
    CheckSubject.extraction: "抽出・加工条件",
    CheckSubject.metrics: "指標",
    CheckSubject.compared_against: "比べ先",
    CheckSubject.figures: "図",
    CheckSubject.criterion: "判定の基準",
    CheckSubject.cells: "分析コードの区切り",
}

CHECK_RESULT_WORDS: Mapping[CheckResult, str] = {
    CheckResult.agrees: "分析設計どおり",
    CheckResult.differs: "分析設計と違う",
    CheckResult.not_checkable: "確かめられなかった",
}

# What the check is, said the first time the analyst meets it (DesignDoc of Epic 36).
_COMPARED = (
    "分析設計に書いたことと、分析コードがしている計算が同じかを、エージェントが読み比べ"
)
CHECK_WHAT = f"{CHECK_HEADING}は、{_COMPARED}ることである。"
_CHECK_DONE = f"この節は、{_COMPARED}た結果である。"
CHECKED_BY_WORDS: Mapping[CheckedBy, str] = {
    CheckedBy.check_agent: "読み比べたのは、この分析コードを書いていないエージェントである。",
    CheckedBy.same_session: (
        "読み比べたのは、この分析コードを書いたのと同じエージェントで、"
        "ほかのエージェントは読んでいない。"
    ),
}
CHECK_LEAVES = (
    "この点検は、数が正しいか（計算し直していない）、分析設計そのものが妥当か、"
    "結果の解釈が妥当かは確かめていない。"
)
CHECK_NOT_DONE = (
    "いまの分析コードの結果への点検は、まだ済んでいない。"
    "点検の後に分析コードの結果か分析設計を書き換えたときも、済んでいないと読む。"
)
NOTHING_TO_CHECK = "notebook をまだ実行していないので、点検するものが無い。"
_DASH = "—"
# What the note says of a cell it cannot link: the code is read in the file then.
_IN_THE_FILE = "手元の notebook の .py で読む"
_DATA_LOAD = "data_load"


@dataclass(frozen=True)
class NoteCheck:
    """``check_reading`` as the screens show it. The default is a check not done."""

    checked: bool = False
    checked_by: CheckedBy | None = None
    items: tuple[CheckItem, ...] = ()  # in the order of the subjects

    @classmethod
    def of(cls, reading: Mapping[str, object]) -> NoteCheck:
        """A reading that does not read is no check, as a record that does not read.

        ``check_reading`` always fills these when the check is done; a page is
        not stopped for a reading built otherwise.
        """
        items = reading.get("items")
        if not reading.get("checked") or not isinstance(items, list):
            return cls()
        try:
            return cls(
                checked=True,
                checked_by=CheckedBy(reading.get("checked_by")),
                items=tuple(CheckItem.model_validate(item) for item in items),
            )
        except ValueError:  # a pydantic ValidationError is a ValueError
            return cls()

    def of_result(self, result: CheckResult) -> tuple[CheckItem, ...]:
        return tuple(i for i in self.items if i.result is result)


def check_summary(has_verdict: bool, check: NoteCheck) -> str | None:
    """How the check of a design stands, in one line; None when there is nothing to check."""
    if not has_verdict:
        return None
    return f"{CHECK_HEADING}: {_standing(check)}"


def _standing(check: NoteCheck) -> str:
    if not check.checked:
        return "まだ済んでいない。"
    differ = len(check.of_result(CheckResult.differs))
    unknown = len(check.of_result(CheckResult.not_checkable))
    said = "済んだ。"
    said += (
        f"分析設計と違う点が {differ} つある。"
        if differ
        else "分析設計と違う点は無い。"
    )
    if unknown:
        said += f"確かめられなかった点が {unknown} つある。"
    return said


def check_anchor(note_anchor: str) -> str:
    return f"{note_anchor}-check"


def cell_anchor(note_anchor: str, name: str) -> str:
    """The id of a cell of the code in a note, which a difference links."""
    return f"{note_anchor}-cell-{name}"


def _cell(
    item: CheckItem, note_anchor: str, shown: Collection[str] | None
) -> str | Html:
    cell = item.cell
    if not cell:
        return _DASH
    if shown is not None and cell in shown:
        return el("a", cell, href=f"#{cell_anchor(note_anchor, cell)}")
    if shown is None:
        why = "分析コードをこの分析ノートに載せていない"
    elif cell == _DATA_LOAD:
        why = "接続情報が入るので、この分析ノートには載せていない"
    else:
        why = "この名前の区切りは、この分析ノートの分析コードに無い"
    return f"{cell}（{why}。{_IN_THE_FILE}）"


_ROW_ORDER = (CheckResult.differs, CheckResult.not_checkable, CheckResult.agrees)


def check_section(
    check: NoteCheck,
    has_verdict: bool,
    note_anchor: str,
    shown_cells: Collection[str] | None,
) -> Html:
    """The section of the check in a note, ahead of its results (US-5 AC 4).

    *shown_cells* names the cells the note shows; None when it shows no code.
    """
    if not has_verdict:
        body = [el("p", NOTHING_TO_CHECK)]
    elif not check.checked:
        body = [el("p", CHECK_WHAT), el("p", CHECK_NOT_DONE)]
    else:
        rows = [i for result in _ROW_ORDER for i in check.of_result(result)]
        body = [
            el("p", _CHECK_DONE),
            el("p", CHECKED_BY_WORDS[check.checked_by])
            if check.checked_by is not None
            else None,
            el("p", CHECK_LEAVES),
            el("p", _standing(check)),
            table(
                ("項目", "点検の結果", "内容", "読んだ分析コードの区切り"),
                (
                    (
                        CHECK_SUBJECT_WORDS[i.subject],
                        CHECK_RESULT_WORDS[i.result],
                        i.note or _DASH,
                        _cell(i, note_anchor, shown_cells),
                    )
                    for i in rows
                ),
            ),
        ]
    return el(
        "section",
        el("h3", CHECK_HEADING),
        join(body),
        id=check_anchor(note_anchor),
    )


def difference_lines(check: NoteCheck) -> list[Html]:
    """Each difference in the sentence the check wrote, named by its subject."""
    return [
        el("li", f"{CHECK_SUBJECT_WORDS[i.subject]}: {i.note}")
        for i in check.of_result(CheckResult.differs)
    ]
