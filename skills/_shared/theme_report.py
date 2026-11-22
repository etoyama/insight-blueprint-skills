"""The final report of a theme, written by code from its records (Epic 29).

Pure: no I/O. Every sentence is a fixed template or a text copied verbatim from
the tree, so a model's wording cannot enter the report. Nothing is computed,
reformatted or trimmed, and no time or path goes into the text: the same records
give the same bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from insight_blueprint.models.tree import Aim, AimKind, Answer, StatementKind

# The sections no Story has filled yet; the Abstract sits before them.
_OTHER_HEADINGS = (
    "## Introduction",
    "## Method",
    "## Results",
    "## Discussion",
    "### Limitations",
    "### Future Directions",
    "## Appendix",
)

# The order of this table is the order of the groups in the report.
_KIND_HEADINGS: dict[StatementKind, str] = {
    StatementKind.claim: "言えること",
    StatementKind.weakening: "留保すべきこと",
    StatementKind.undetermined: "まだ分からないこと",
}

_AIM_SENTENCES: dict[AimKind, str] = {
    AimKind.business: "{decision_maker}が、{decision}を決めるための分析である。",
    AimKind.research: (
        "{audience}が、主張を吟味するための分析である。主張の範囲は「{claim_scope}」である。"
    ),
}

_ABSTRACT_LEAD = (
    "主題への現時点の答えは次のとおり。"
    "文の後ろの括弧は根拠にした記録の番号で、本文は Appendix にある。"
)


@dataclass(frozen=True)
class ThemeReport:
    """The final report of a theme, as read from its records. Never stored."""

    theme_id: str
    root_question: str
    aim: Aim
    round: int
    answer: Answer


def _aim_sentence(aim: Aim) -> str:
    return _AIM_SENTENCES[aim.kind].format(**aim.model_dump())


def _abstract(report: ThemeReport) -> list[str]:
    blocks = [f"## Abstract\n\n{_aim_sentence(report.aim)}{_ABSTRACT_LEAD}"]
    for kind, heading in _KIND_HEADINGS.items():
        lines = [
            f"- {s.text}（{'、'.join(s.cites)}）"
            for s in report.answer.statements
            if s.kind is kind
        ]
        if lines:
            blocks.append("\n".join([f"**{heading}**", "", *lines]))
    return blocks


def render_report(report: ThemeReport) -> str:
    """The Markdown of *report*."""
    blocks = [
        f"# {report.root_question}",
        f"テーマ {report.theme_id} のレポート。"
        f"{report.round}回目の振り返りの時点の記録にもとづく。",
        *_abstract(report),
        *_OTHER_HEADINGS,
    ]
    return "\n\n".join(blocks) + "\n"
