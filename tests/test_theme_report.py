"""Tests of skills/_shared/theme_report.py (Epic 29): the final report of a theme, as Markdown."""

from __future__ import annotations

import importlib.util
import re
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from insight_blueprint.models.design import AnalysisDesign, DesignForm, DesignStatus
from insight_blueprint.models.tree import (
    Aim,
    Answer,
    AnswerStatement,
    NextCandidate,
    Progress,
    TreeDecision,
)
from skills._shared.design_note import (
    FORM_WORDS,
    Conclusion,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    NoteVerdict,
)
from skills._shared.design_note_read import load_design_note
from skills._shared.theme_report import (
    READER_WORDS,
    ReportDesign,
    ReportNode,
    ThemeReport,
    escape_source_text,
    render_report,
)
from skills._shared.tree_render import CitedEvent
from skills._shared.verdict_table import (
    CONFIDENCE,
    MetricGroup,
    ValueInterval,
    VerdictMetric,
)
from tests._saved_verdicts import SAVED_VERDICTS, save_design_with_verdict

REPO_ROOT = Path(__file__).resolve().parents[1]
# The glossary's own reader, as the documents' tests use it.
_spec = importlib.util.spec_from_file_location(
    "export_yomiyasu_words", REPO_ROOT / "scripts/export_yomiyasu_words.py"
)
assert _spec and _spec.loader
_glossary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_glossary)

BUSINESS_AIM = Aim.model_validate(
    {
        "kind": "business",
        "decision_maker": "図書館員",
        "decision": "取り置き期限を延ばす試行を始めるか",
    }
)
RESEARCH_AIM = Aim.model_validate(
    {"kind": "research", "audience": "査読者", "claim_scope": "都内の公共図書館"}
)

_RECORD_IDS = [f"LIB-H0{d}-E0{e}" for d in (1, 2, 3) for e in range(1, 10)]
RECORDS = {
    i: CitedEvent(id=i, type="evidence", direction=None, content=f"{i} の本文")
    for i in _RECORD_IDS
}


def _statement(kind: str, text: str, *cites: str) -> AnswerStatement:
    return AnswerStatement(kind=kind, text=text, cites=list(cites) or ["LIB-H01-E01"])


def _answer(*statements: AnswerStatement, root_revision: int = 1) -> Answer:
    return Answer(
        round=2,
        root_revision=root_revision,
        statements=list(statements) or [_statement("claim", "期限切れは152件")],
        created_at=datetime(2026, 11, 1, 9, 30),
    )


def _event(event_id: str, content: str, type_: str = "evidence") -> NoteEvent:
    return NoteEvent(
        id=event_id, type=type_, direction=None, content=content, created_at=""
    )


def _node(node_id: str = "LIB-Q02", **over: object) -> ReportNode:
    fields: dict = {
        "id": node_id,
        "question": f"{node_id} の問い",
        "parent": "LIB-Q01",
        "contribution": f"{node_id} に答えると分かること",
        "progress": Progress.analyzed,
        "answer": None,
        "design_ids": (),
        "next_candidate": None,
    }
    fields.update(over)
    return ReportNode(**fields)


def _design(design_id: str = "LIB-H01", **over: object) -> ReportDesign:
    fields: dict = {
        "id": design_id,
        "title": f"{design_id} の題",
        "form": DesignForm.confirmation,
        "intent": "検証",
        "statement": f"{design_id} の仮説",
        "method": "2群の割合の比較",
        "package": "scipy",
        "method_reason": "2群の期限切れ率を比べるため",
        "status": DesignStatus.supported,
        "conclude_events": (),
        "contradicting_evidence": (),
        "metrics": (),
        "figures": (),
    }
    fields.update(over)
    return ReportDesign(**fields)


def _metric(name: str, value: str | None, **over: object) -> VerdictMetric:
    fields: dict = {
        "name": name,
        "value": value,
        "threshold": None,
        "p": None,
        "passed": None,
        "effect_size": None,
        "interval": None,
        "sample_size": None,
    }
    fields.update(over)
    return VerdictMetric(**fields)


def _figure(file: str, title: str = "図の題") -> NoteFigure:
    return NoteFigure(
        file=file,
        title=title,
        axes="x = 群、y = 率",
        how_to_read="高いほど多い",
        png=b"",
    )


def _report(
    *statements: AnswerStatement,
    aim: Aim = BUSINESS_AIM,
    nodes: tuple[ReportNode, ...] = (),
    designs: tuple[ReportDesign, ...] = (),
    sources: tuple[NoteSource, ...] = (),
    decision: TreeDecision | None = None,
    root_revision: int = 1,
) -> ThemeReport:
    return ThemeReport(
        theme_id="LIB",
        root_id="LIB-Q01",
        root_question="取り置き期限を延ばす試行をするか",
        aim=aim,
        round=2,
        root_revision=root_revision,
        answer=_answer(*statements, root_revision=root_revision),
        nodes=nodes,
        designs=designs,
        sources=sources,
        decision=decision,
        records=RECORDS,
    )


def _headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]


def _level(line: str) -> int:
    return len(line) - len(line.lstrip("#")) if line.startswith("#") else 0


def _section(markdown: str, heading: str) -> str:
    """The text under *heading*, up to the next heading of the same or a higher level."""
    lines = markdown.splitlines()
    start = lines.index(heading) + 1
    level = _level(heading)
    end = next(
        (i for i in range(start, len(lines)) if 0 < _level(lines[i]) <= level),
        len(lines),
    )
    return "\n".join(lines[start:end])


APA_HEADINGS = [
    "# 取り置き期限を延ばす試行をするか",
    "## Abstract",
    "## Introduction",
    "## Method",
    "## Results",
    "## Discussion",
    "### Limitations",
    "### Future Directions",
    "## Appendix",
]


class TestRenderReport:
    def test_the_headings_are_the_apa_ones_in_english_in_order(self) -> None:
        markdown = render_report(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(_design(),),
            )
        )

        headings = _headings(markdown)
        assert [h for h in headings if h in APA_HEADINGS] == APA_HEADINGS
        # Every other heading sits inside Results or the Appendix.
        assert all(h.startswith("### ") for h in headings if h not in APA_HEADINGS), (
            headings
        )

    def test_the_title_is_the_root_question_and_the_line_below_names_the_theme_and_the_round(
        self,
    ) -> None:
        lines = render_report(_report()).splitlines()

        assert lines[0] == "# 取り置き期限を延ばす試行をするか"
        assert lines[1] == ""
        assert (
            lines[2] == "テーマ LIB のレポート。2回目の振り返りの時点の記録にもとづく。"
        )

    def test_a_business_aim_names_who_decides_what(self) -> None:
        markdown = render_report(_report(aim=BUSINESS_AIM))

        assert (
            "図書館員が、取り置き期限を延ばす試行を始めるかを決めるための分析である。"
            in markdown
        )

    def test_a_research_aim_names_the_audience_and_the_claim_scope(self) -> None:
        markdown = render_report(_report(aim=RESEARCH_AIM))

        assert (
            "査読者が、主張を吟味するための分析である。主張の範囲は「都内の公共図書館」である。"
            in markdown
        )

    def test_statements_are_grouped_by_kind_in_the_fixed_order(self) -> None:
        markdown = render_report(
            _report(
                _statement("undetermined", "季節差は分からない"),
                _statement("claim", "期限切れは152件"),
                _statement("weakening", "取消の混入は除けていない"),
            )
        )

        assert markdown.index("**これまでわかっていること**") < markdown.index(
            "**注意すべきこと**"
        )
        assert markdown.index("**注意すべきこと**") < markdown.index(
            "**まだ決められないこと**"
        )

    def test_a_kind_with_no_statement_has_no_heading(self) -> None:
        markdown = render_report(_report(_statement("claim", "期限切れは152件")))

        assert "**これまでわかっていること**" in markdown
        assert "**注意すべきこと**" not in markdown
        assert "**まだ決められないこと**" not in markdown

    def test_the_order_within_a_kind_is_kept(self) -> None:
        markdown = render_report(
            _report(
                _statement("claim", "二つ目より前"),
                _statement("weakening", "留保"),
                _statement("claim", "二つ目"),
            )
        )

        assert markdown.index("二つ目より前") < markdown.index("- 二つ目（")

    def test_each_statement_ends_with_the_ids_of_the_events_it_cites(self) -> None:
        markdown = render_report(
            _report(
                _statement("claim", "期限切れは152件", "LIB-H01-E01", "LIB-H02-E03")
            )
        )

        assert "- 期限切れは152件（LIB-H01-E01、LIB-H02-E03）" in markdown.splitlines()

    def test_the_same_report_gives_the_same_markdown(self) -> None:
        report = _report()

        assert render_report(report) == render_report(report)

    def test_a_value_comes_out_as_written(self) -> None:
        markdown = render_report(_report(_statement("claim", "差は0.090で、割合は18%")))

        assert "差は0.090で、割合は18%" in markdown

    def test_the_time_the_answer_was_written_is_not_in_the_text(self) -> None:
        markdown = render_report(_report())

        assert "2026" not in markdown

    def test_the_text_ends_with_one_newline(self) -> None:
        markdown = render_report(_report())

        assert markdown.endswith("\n")
        assert not markdown.endswith("\n\n")


class TestIntroduction:
    def test_it_names_the_root_question_and_who_decides_what(self) -> None:
        intro = _section(render_report(_report()), "## Introduction")

        assert "- 主題: 取り置き期限を延ばす試行をするか" in intro.splitlines()
        assert "- 決める人: 図書館員" in intro.splitlines()
        assert "- 決めること: 取り置き期限を延ばす試行を始めるか" in intro.splitlines()

    def test_a_research_aim_names_the_audience_and_the_claim_scope(self) -> None:
        intro = _section(render_report(_report(aim=RESEARCH_AIM)), "## Introduction")

        assert "- 想定読者: 査読者" in intro.splitlines()
        assert "- 主張の範囲: 都内の公共図書館" in intro.splitlines()
        assert "決める人" not in intro

    def test_the_table_of_questions_holds_question_parent_contribution_and_progress(
        self,
    ) -> None:
        intro = _section(
            render_report(
                _report(
                    nodes=(
                        _node("LIB-Q02", progress=Progress.analyzed),
                        _node("LIB-Q03", progress=Progress.investigating),
                        _node(
                            "LIB-Q04", parent="LIB-Q03", progress=Progress.not_started
                        ),
                    )
                )
            ),
            "## Introduction",
        )

        lines = intro.splitlines()
        assert "| 論点 | 問い | 上位の論点 | 答えると分かること | 進捗 |" in lines
        rows = [line for line in lines if line.startswith("| LIB-Q")]
        assert rows == [
            "| LIB-Q02 | LIB-Q02 の問い | LIB-Q01 | LIB-Q02 に答えると分かること | 分析済み |",
            "| LIB-Q03 | LIB-Q03 の問い | LIB-Q01 | LIB-Q03 に答えると分かること | 検証中 |",
            "| LIB-Q04 | LIB-Q04 の問い | LIB-Q03 | LIB-Q04 に答えると分かること | 未着手 |",
        ]

    def test_a_root_with_no_question_below_it_says_so_instead_of_a_table(
        self,
    ) -> None:
        intro = _section(render_report(_report()), "## Introduction")

        assert "主題を論点に分けていない。" in intro
        assert "| 論点 |" not in intro


class TestMethod:
    def test_each_linked_design_has_its_hypothesis_method_and_reason(self) -> None:
        method = _section(
            render_report(
                _report(
                    nodes=(_node("LIB-Q02", design_ids=("LIB-H01",)),),
                    designs=(_design("LIB-H01"),),
                )
            ),
            "## Method",
        )

        lines = method.splitlines()
        assert (
            "| 分析 | 答える論点 | 意図 | 探索の問い / 検証仮説 | 手法 | 手法を選んだ理由 |"
        ) in lines
        assert (
            "| LIB-H01 LIB-H01 の題 | LIB-Q02 | 検証 | LIB-H01 の仮説 "
            "| 2群の割合の比較（scipy） "
            "| 2群の期限切れ率を比べるため |"
        ) in lines

    def test_a_design_linked_to_two_questions_names_both_on_one_row(self) -> None:
        method = _section(
            render_report(
                _report(
                    nodes=(
                        _node("LIB-Q02", design_ids=("LIB-H01",)),
                        _node("LIB-Q03", design_ids=("LIB-H01",)),
                    ),
                    designs=(_design("LIB-H01"),),
                )
            ),
            "## Method",
        )

        rows = [line for line in method.splitlines() if line.startswith("| LIB-H01")]
        assert len(rows) == 1
        assert "| LIB-Q02、LIB-Q03 |" in rows[0]

    def test_a_design_without_a_method_shows_a_dash(self) -> None:
        method = _section(
            render_report(
                _report(designs=(_design(method="", package="", method_reason=""),))
            ),
            "## Method",
        )

        row = next(line for line in method.splitlines() if line.startswith("| LIB-H01"))
        assert row.endswith("| — | — |")

    def test_the_data_sources_show_name_type_and_description(self) -> None:
        method = _section(
            render_report(
                _report(
                    designs=(_design(),),
                    sources=(NoteSource("予約の履歴", "csv", "予約ごとの状態の履歴"),),
                )
            ),
            "## Method",
        )

        lines = method.splitlines()
        assert "| 名前 | 種類 | 説明 |" in lines
        assert "| 予約の履歴 | csv | 予約ごとの状態の履歴 |" in lines

    def test_no_design_and_no_source_each_say_so(self) -> None:
        method = _section(render_report(_report()), "## Method")

        assert "論点に結んだ分析は無い。" in method
        assert "データソースは宣言していない。" in method


def _results(report: ThemeReport) -> str:
    return _section(render_report(report), "## Results")


class TestResults:
    def test_only_answered_questions_have_a_part_with_their_answer_by_kind(
        self,
    ) -> None:
        results = _results(
            _report(
                nodes=(
                    _node(
                        "LIB-Q02",
                        answer=_answer(
                            _statement("claim", "期限切れは152件", "LIB-H01-E01"),
                            _statement("weakening", "取消の混入が残る", "LIB-H01-E02"),
                        ),
                    ),
                    _node("LIB-Q03"),
                )
            )
        )

        assert "### LIB-Q02 LIB-Q02 の問い" in results.splitlines()
        assert "LIB-Q03" not in results
        assert "- 期限切れは152件（LIB-H01-E01）" in results.splitlines()
        assert results.index("**これまでわかっていること**") < results.index(
            "**注意すべきこと**"
        )

    def test_a_finished_design_gives_its_lead_sentence_and_conclude_text(
        self,
    ) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(
                    _design(
                        status=DesignStatus.inconclusive,
                        conclude_events=(
                            _event("LIB-H01-E04", "見分けられなかった", "conclude"),
                        ),
                    ),
                ),
            )
        )

        lines = results.splitlines()
        assert "**根拠となる分析: LIB-H01 LIB-H01 の題**" in lines
        assert (
            "検証仮説を支持するとも棄却するとも結論できなかった。"
            "見分けられなかった（LIB-H01-E04）" in lines
        )

    def test_a_design_not_finished_says_it_has_no_conclusion_yet(self) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(_design(status=DesignStatus.analyzing),),
            )
        )

        assert "この分析は、まだ結論が出ていない。" in results
        assert "仮説は" not in results

    def test_the_metrics_show_the_values_as_written_with_only_the_columns_in_use(
        self,
    ) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(
                    _design(
                        metrics=(
                            _metric("期限切れ率（当日）", "0.090", sample_size="1210"),
                            _metric(
                                "期限切れ率（翌日以降）",
                                "0.18",
                                sample_size="640",
                                p="1e-05",
                            ),
                        )
                    ),
                ),
            )
        )

        lines = results.splitlines()
        assert "| 指標 | 値 | 標本サイズ | p 値 |" in lines
        assert "| 期限切れ率（当日） | 0.090 | 1210 | — |" in lines
        assert "| 期限切れ率（翌日以降） | 0.18 | 640 | 1e-05 |" in lines

    def test_every_kind_of_metric_value_has_its_column(self) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(
                    _design(
                        metrics=(
                            _metric(
                                "差",
                                "0.1",
                                threshold="0.05",
                                p="0.01",
                                passed=False,
                                effect_size=("cohens_d", "0.30"),
                                interval=ValueInterval(
                                    CONFIDENCE, "0.95", "0.10", "0.50"
                                ),
                                sample_size="1520",
                            ),
                        )
                    ),
                ),
            )
        )

        lines = results.splitlines()
        assert (
            "| 指標 | 値 | 効果量 | 区間 | 標本サイズ | しきい値 | p 値 | 合否 |"
            in lines
        )
        assert (
            "| 差 | 0.1 | 0.30（cohens\\_d） | 信頼区間 水準 0.95: [0.10, 0.50] "
            "| 1520 | 0.05 | 0.01 | ✗ |" in lines
        )

    def test_figures_come_as_numbered_image_links_with_title_axes_and_how_to_read(
        self,
    ) -> None:
        results = _results(
            _report(
                nodes=(
                    _node("LIB-Q02", answer=_answer(), design_ids=("LIB-H01",)),
                    _node("LIB-Q03", answer=_answer(), design_ids=("LIB-H02",)),
                ),
                designs=(
                    _design(
                        "LIB-H01", figures=(_figure("LIB-H01_fig01.png", "一つ目"),)
                    ),
                    _design(
                        "LIB-H02", figures=(_figure("LIB-H02_fig01.png", "二つ目"),)
                    ),
                ),
            )
        )

        lines = results.splitlines()
        assert "![図 1](../notebooks/LIB-H01_fig01.png)" in lines
        assert "図 1: 一つ目。軸: x = 群、y = 率。読み方: 高いほど多い" in lines
        assert "![図 2](../notebooks/LIB-H02_fig01.png)" in lines
        assert results.index("図 1:") < results.index("![図 2]")

    def test_an_answer_given_before_the_root_was_revised_says_so(self) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(root_revision=1)),),
                root_revision=2,
            )
        )

        assert "この答えは、主題を今の形に見直す前に書いた。" in results

    def test_an_answer_given_under_the_current_root_says_nothing_of_the_sort(
        self,
    ) -> None:
        results = _results(_report(nodes=(_node(answer=_answer()),)))

        assert "見直す前" not in results


class TestFigures:
    def test_the_figures_are_the_file_names_in_the_order_of_the_report_each_once(
        self,
    ) -> None:
        report = _report(
            nodes=(
                _node("LIB-Q02", answer=_answer(), design_ids=("LIB-H02", "LIB-H01")),
                _node("LIB-Q03", answer=_answer(), design_ids=("LIB-H01",)),
                _node("LIB-Q04", design_ids=("LIB-H03",)),
            ),
            designs=(
                _design("LIB-H01", figures=(_figure("LIB-H01_fig01.png"),)),
                _design(
                    "LIB-H02",
                    figures=(
                        _figure("LIB-H02_fig02.png"),
                        _figure("LIB-H02_fig01.png"),
                    ),
                ),
                _design("LIB-H03", figures=(_figure("LIB-H03_fig01.png"),)),
            ),
        )

        assert report.figures() == [
            "LIB-H02_fig02.png",
            "LIB-H02_fig01.png",
            "LIB-H01_fig01.png",
        ]


def _discussion(report: ThemeReport, heading: str) -> str:
    return _section(render_report(report), heading)


class TestLimitations:
    def test_each_design_lists_the_evidence_against_its_hypothesis(self) -> None:
        limitations = _discussion(
            _report(
                designs=(
                    _design(
                        "LIB-H02",
                        contradicting_evidence=(
                            _event("LIB-H02-E02", "金曜は16%のまま"),
                        ),
                    ),
                    _design("LIB-H01"),
                )
            ),
            "### Limitations",
        )

        lines = limitations.splitlines()
        assert "LIB-H02 LIB-H02 の題 の検証仮説に反する証拠:" in lines
        assert "- 金曜は16%のまま（LIB-H02-E02）" in lines
        assert "LIB-H01" not in limitations

    def test_no_evidence_against_any_hypothesis_says_so(self) -> None:
        limitations = _discussion(_report(designs=(_design(),)), "### Limitations")

        assert "検証仮説に反する証拠は記録されていない。" in limitations

    def test_the_questions_not_answered_yet_are_in_a_table(self) -> None:
        limitations = _discussion(
            _report(nodes=(_node("LIB-Q02", answer=_answer()), _node("LIB-Q04"))),
            "### Limitations",
        )

        lines = limitations.splitlines()
        assert "次の論点には、まだ答えていない。" in lines
        assert "| 論点 | 問い | 答えると分かること |" in lines
        assert "| LIB-Q04 | LIB-Q04 の問い | LIB-Q04 に答えると分かること |" in lines
        assert "| LIB-Q02 |" not in limitations

    def test_every_question_answered_says_so(self) -> None:
        limitations = _discussion(
            _report(nodes=(_node(answer=_answer()),)), "### Limitations"
        )

        assert "まだ答えていない論点は無い。" in limitations


class TestFutureDirections:
    def test_the_last_tree_decision_names_the_next_question_and_why(self) -> None:
        future = _discussion(
            _report(
                nodes=(_node("LIB-Q06"),),
                decision=TreeDecision(
                    round=2,
                    kind="deepen",
                    node_id="LIB-Q06",
                    reason="開館日を先に確かめる",
                ),
            ),
            "### Future Directions",
        )

        lines = future.splitlines()
        assert "- 次に調べる論点: LIB-Q06 LIB-Q06 の問い" in lines
        assert "- 理由: 開館日を先に確かめる" in lines

    def test_a_decision_on_the_root_names_the_root_question(self) -> None:
        future = _discussion(
            _report(
                decision=TreeDecision(
                    round=0, kind="start", node_id="LIB-Q01", reason="始める"
                ),
            ),
            "### Future Directions",
        )

        assert "- 次に調べる論点: LIB-Q01 取り置き期限を延ばす試行をするか" in future

    def test_a_decision_on_a_node_the_report_does_not_hold_is_an_error(
        self,
    ) -> None:
        # Labelled with the root question, it would send the reader to the root.
        report = _report(
            nodes=(_node("LIB-Q02"),),
            decision=TreeDecision(
                round=2, kind="deepen", node_id="LIB-Q09", reason="先に確かめる"
            ),
        )

        with pytest.raises(ValueError, match="LIB-Q09"):
            render_report(report)

    def test_a_close_names_where_the_investigation_stopped(self) -> None:
        future = _discussion(
            _report(
                nodes=(_node("LIB-Q02"),),
                decision=TreeDecision(
                    round=2, kind="close", node_id="LIB-Q02", reason="十分に答えた"
                ),
            ),
            "### Future Directions",
        )

        assert "- 調べるのを止めた論点: LIB-Q02 LIB-Q02 の問い" in future
        assert "次に調べる論点" not in future

    def test_an_answer_heard_about_a_next_candidate_is_given_with_who_and_when(
        self,
    ) -> None:
        future = _discussion(
            _report(
                nodes=(
                    _node(
                        "LIB-Q06",
                        next_candidate=NextCandidate(
                            ask="金曜の通知はいつか",
                            answer="月曜の朝にまとめて通知している",
                            answered_by="予約担当の図書館員",
                            answered_at=date(2026, 11, 20),
                        ),
                    ),
                    _node(
                        "LIB-Q05", next_candidate=NextCandidate(ask="まだ聞いていない")
                    ),
                ),
            ),
            "### Future Directions",
        )

        assert (
            "- LIB-Q06 について聞いた答え（予約担当の図書館員、2026-11-20）: "
            "月曜の朝にまとめて通知している"
        ) in future.splitlines()
        assert "LIB-Q05" not in future

    def test_no_decision_says_so(self) -> None:
        future = _discussion(_report(), "### Future Directions")

        assert "ツリーの決定はまだ無い。" in future

    def test_there_is_no_section_of_recommendations(self) -> None:
        markdown = render_report(_report())

        assert "Recommendation" not in markdown
        assert "勧め" not in markdown


class TestAppendix:
    def test_every_record_the_report_cites_is_listed_once_in_the_order_cited(
        self,
    ) -> None:
        appendix = _section(
            render_report(
                _report(
                    _statement("claim", "根の答え", "LIB-H02-E01"),
                    nodes=(
                        _node(
                            answer=_answer(
                                _statement(
                                    "claim", "論点の答え", "LIB-H01-E01", "LIB-H02-E01"
                                )
                            ),
                            design_ids=("LIB-H01",),
                        ),
                    ),
                    designs=(
                        _design(
                            conclude_events=(
                                _event("LIB-H01-E04", "結論", "conclude"),
                            ),
                            contradicting_evidence=(_event("LIB-H01-E02", "反する"),),
                        ),
                    ),
                )
            ),
            "## Appendix",
        )

        lines = appendix.splitlines()
        assert "### 根拠にした記録" in lines
        assert "| 記録の番号 | 種類 | 本文 |" in lines
        rows = [line.split(" | ")[0] for line in lines if line.startswith("| LIB-")]
        assert rows == [
            "| LIB-H02-E01",
            "| LIB-H01-E01",
            "| LIB-H01-E04",
            "| LIB-H01-E02",
        ]
        assert "| LIB-H02-E01 | 証拠 | LIB-H02-E01 の本文 |" in lines

    def test_a_record_the_report_does_not_cite_is_not_listed(self) -> None:
        appendix = _section(render_report(_report()), "## Appendix")

        assert "LIB-H01-E01" in appendix
        assert "LIB-H01-E02" not in appendix

    def test_the_kind_of_a_record_is_the_word_of_the_glossary(self) -> None:
        report = replace(
            _report(),
            records={
                "LIB-H01-E01": CitedEvent(
                    id="LIB-H01-E01", type="hearing", direction=None, content="聞いた"
                )
            },
        )

        appendix = _section(render_report(report), "## Appendix")

        assert "| LIB-H01-E01 | 人に聞いた答え | 聞いた |" in appendix.splitlines()


class TestEscapeSourceText:
    def test_each_of_the_eight_characters_gets_a_backslash(self) -> None:
        assert escape_source_text("\\`*_[]<|") == r"\\\`\*\_\[\]\<\|"

    def test_a_tilde_and_an_ampersand_get_a_backslash_too(self) -> None:
        # GFM strikes through ~x~, and &lt; would show as <.
        assert escape_source_text("2019~2023年、~~削除~~、&lt;b&gt;") == (
            r"2019\~2023年、\~\~削除\~\~、\&lt;b\&gt;"
        )

    def test_a_run_of_line_breaks_and_tabs_becomes_one_space(self) -> None:
        assert escape_source_text("a\r\n\tb\n\nc d") == "a b c d"

    def test_other_text_is_kept_as_written(self) -> None:
        assert escape_source_text("期限切れは152件 (n=3) a>b、2.5%") == (
            "期限切れは152件 (n=3) a>b、2.5%"
        )

    @pytest.mark.parametrize(
        ("text", "escaped"),
        [
            ("# 見出し", r"\# 見出し"),
            ("> 引用", r"\> 引用"),
            ("- 項目", r"\- 項目"),
            ("+ 項目", r"\+ 項目"),
            ("1. 番号", r"1\. 番号"),
            ("12) 番号", r"12\) 番号"),
        ],
    )
    def test_a_mark_that_starts_a_block_at_the_head_gets_a_backslash(
        self, text: str, escaped: str
    ) -> None:
        assert escape_source_text(text) == escaped

    @pytest.mark.parametrize(
        "text",
        # Digits open only an ordered list: "3# x" is no heading, "12- x" no item.
        [
            "2019-2023 年",
            "1.5 倍",
            "-1.2",
            "+3%",
            "#タグ",
            "C#",
            "3# x",
            "12- x",
            "3> x",
        ],
    )
    def test_a_mark_that_opens_no_block_is_kept(self, text: str) -> None:
        assert escape_source_text(text) == text

    def test_a_hash_that_would_close_a_heading_gets_a_backslash(self) -> None:
        assert escape_source_text("C の問い ##") == r"C の問い \##"

    def test_a_text_of_hashes_alone_gets_a_backslash(self) -> None:
        assert escape_source_text("#######") == r"\#######"

    def test_spaces_at_the_ends_are_dropped(self) -> None:
        assert escape_source_text("   # 見出し  ") == r"\# 見出し"


# Every Markdown mark AC 5 names, in one text; it starts with a block mark.
POISON = (
    "> 引用 <b>太字</b> *強調* _下線_ | セル | `コード`\n```\n"
    "![画像](http://example.invalid/a.png) [リンク](http://example.invalid/)"
    " \\ 終わり\n~~~\n# 見出し\t- 項目 #"
)
POISON_ESCAPED = (
    r"\> 引用 \<b>太字\</b> \*強調\* \_下線\_ \| セル \| \`コード\` \`\`\` "
    r"!\[画像\](http://example.invalid/a.png) \[リンク\](http://example.invalid/)"
    r" \\ 終わり \~\~\~ # 見出し - 項目 \#"
)


def _poisoned_report(aim: Aim) -> ThemeReport:
    """A report whose every text taken from the records is POISON."""
    p = POISON
    cited = ("LIB-H01-E01", "LIB-H01-E02", "LIB-H01-E03")
    answer = _answer(
        _statement("claim", p, cited[0]),
        _statement("weakening", p, cited[0]),
        _statement("undetermined", p, cited[0]),
    )
    design = _design(
        title=p,
        statement=p,
        method=p,
        package=p,
        method_reason=p,
        conclude_events=(_event(cited[1], p, "conclude"),),
        contradicting_evidence=(_event(cited[2], p),),
        metrics=(
            _metric(
                p,
                p,
                threshold=p,
                p=p,
                passed=True,
                effect_size=(p, p),
                interval=ValueInterval(p, p, p, p),
                sample_size=p,
                support_line=p,
                reject_line=p,
            ),
            # Two axes of values alone, and one axis with more: both group tables.
            _metric(p, None, by=(p, p), groups=(_group(p, p, value=p),)),
            _metric(
                p,
                None,
                by=(p,),
                groups=(
                    _group(
                        p,
                        value=p,
                        p=p,
                        effect_size=(p, p),
                        interval=ValueInterval(p, p, p, p),
                        sample_size=p,
                    ),
                ),
            ),
        ),
        figures=(NoteFigure(file="a_b.png", title=p, axes=p, how_to_read=p, png=b""),),
    )
    candidate = NextCandidate(
        ask=p, answer=p, answered_by=p, answered_at=date(2026, 11, 1)
    )
    return ThemeReport(
        theme_id="LIB",
        root_id="LIB-Q01",
        root_question=p,
        aim=aim,
        round=2,
        root_revision=1,
        answer=answer,
        nodes=(
            _node(
                question=p,
                contribution=p,
                answer=answer,
                design_ids=("LIB-H01",),
            ),
            _node("LIB-Q03", question=p, contribution=p, next_candidate=candidate),
        ),
        designs=(design,),
        sources=(NoteSource(name=p, type=p, description=p),),
        decision=TreeDecision.model_validate(
            {"round": 2, "kind": "deepen", "node_id": "LIB-Q03", "reason": p}
        ),
        records={
            i: CitedEvent(id=i, type="evidence", direction=None, content=p)
            for i in cited
        },
    )


POISON_AIMS = [
    Aim.model_validate(
        {"kind": "business", "decision_maker": POISON, "decision": POISON}
    ),
    Aim.model_validate({"kind": "research", "audience": POISON, "claim_scope": POISON}),
]

# A `|` that splits a table row: not preceded by an odd run of backslashes.
_CELL_BAR = re.compile(r"(?<!\\)(?:\\\\)*\|")


class TestSourceTextInTheReport:
    @pytest.mark.parametrize("aim", POISON_AIMS, ids=["business", "research"])
    def test_every_text_from_the_records_is_escaped_wherever_it_goes(
        self, aim: Aim
    ) -> None:
        markdown = render_report(_poisoned_report(aim))

        # Each copy of the text is whole and escaped: no part of it went in raw.
        assert markdown.count("太字") == markdown.count(POISON_ESCAPED) > 0

    @pytest.mark.parametrize("aim", POISON_AIMS, ids=["business", "research"])
    def test_no_mark_in_the_text_works_as_markdown(self, aim: Aim) -> None:
        markdown = render_report(_poisoned_report(aim))

        assert not re.search(r"(?<!\\)</?b>", markdown)
        for raw in ("*強調*", "_下線_", "`コード`", "![画像]", "[リンク]", "```"):
            assert raw not in markdown
        assert "\t" not in markdown
        for line in markdown.splitlines():
            assert not line.startswith(("~~~", "```", "> ", "# 見出し"))
            assert not re.match(r"- (?:[#>+=~-]|\d+[.)])", line)

    @pytest.mark.parametrize("aim", POISON_AIMS, ids=["business", "research"])
    def test_every_table_row_keeps_the_columns_of_its_header(self, aim: Aim) -> None:
        markdown = render_report(_poisoned_report(aim))

        for table in re.findall(r"(?:^\|.*\n)+", markdown, flags=re.MULTILINE):
            widths = {len(_CELL_BAR.findall(row)) for row in table.splitlines()}
            assert len(widths) == 1, table

    def test_the_figure_link_keeps_its_file_name_as_written(self) -> None:
        markdown = render_report(_poisoned_report(BUSINESS_AIM))

        assert "](../notebooks/a_b.png)" in markdown


class TestReaderWords:
    def test_every_word_rewritten_is_a_term_of_the_glossary(self) -> None:
        glossary = (REPO_ROOT / "docs/UBIQUITOUS_LANGUAGE.md").read_text("utf-8")
        terms = {row["用語"] for row in _glossary.terms_rows(glossary)}

        assert set(READER_WORDS) <= terms

    def test_the_report_says_none_of_the_terms_it_rewrites(self) -> None:
        markdown = render_report(
            _report(
                aim=RESEARCH_AIM,
                nodes=(
                    _node(answer=_answer(), design_ids=("LIB-H01", "LIB-H02")),
                    _node("LIB-Q03"),
                ),
                designs=(
                    _design(
                        conclude_events=(_event("LIB-H01-E02", "差", "conclude"),),
                        contradicting_evidence=(_event("LIB-H01-E03", "反"),),
                    ),
                    _design("LIB-H02", status=DesignStatus.analyzing),
                ),
                decision=TreeDecision.model_validate(
                    {"round": 2, "kind": "deepen", "node_id": "LIB-Q03", "reason": "次"}
                ),
            )
        )

        for term, word in READER_WORDS.items():
            assert term not in markdown
            assert word in markdown

    def test_the_lead_sentence_of_a_finished_design_is_the_one_of_the_analysis_note(
        self,
    ) -> None:
        for form, words in FORM_WORDS.items():
            for status, sentence in words.lead_sentences.items():
                assert _design(form=form, status=status).lead_sentence is sentence


class TestJournalIdsInTheReport:
    def test_an_event_id_the_tree_did_not_check_is_escaped_where_it_is_cited(
        self,
    ) -> None:
        # The ids of conclude events and evidence against come from the journal
        # unchecked; an answer's cites are checked by the tree.
        odd = "LIB-H01-E9 | x | <img src=x>\n# 注入"
        report = replace(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(
                    _design(
                        conclude_events=(_event(odd, "結論", "conclude"),),
                        contradicting_evidence=(_event(odd, "反"),),
                    ),
                ),
            ),
            records={**RECORDS, odd: CitedEvent(odd, "conclude", None, "結論")},
        )

        markdown = render_report(report)

        escaped = r"LIB-H01-E9 \| x \| \<img src=x> # 注入"
        assert f"結論（{escaped}）" in markdown
        assert f"| {escaped} | 結論 | 結論 |" in markdown
        assert "<img" not in markdown.replace(r"\<img", "")
        assert "\n# 注入" not in markdown

    def test_a_blank_title_leaves_the_bold_line_closed(self) -> None:
        results = _results(
            _report(
                nodes=(_node(answer=_answer(), design_ids=("LIB-H01",)),),
                designs=(_design(title="   "),),
            )
        )

        assert "**根拠となる分析: LIB-H01**" in results.splitlines()


# Story 32.5 (Epic 32 US-5): the report words an exploration, a confirmation and a
# legacy exploration apart, with the words of the analysis note (ADR-0051).


def _exploration_design(design_id: str = "LIB-H01", **over: object) -> ReportDesign:
    fields: dict = {
        "form": DesignForm.exploration,
        "intent": "探索",
        "statement": "期限切れはどの館で多いか",
        "status": DesignStatus.explored,
    }
    fields.update(over)
    return _design(design_id, **fields)


def _legacy_design(design_id: str = "LIB-H01", **over: object) -> ReportDesign:
    fields: dict = {
        "form": DesignForm.legacy_exploration,
        "intent": "探索（旧形式）",
    }
    fields.update(over)
    return _design(design_id, **fields)


def _answered(*designs: ReportDesign) -> ThemeReport:
    return _report(
        nodes=(_node(answer=_answer(), design_ids=tuple(d.id for d in designs)),),
        designs=designs,
    )


# Words that judge a hypothesis; the part of an exploration holds none of them.
_JUDGING = ("仮説", "支持", "棄却", "しきい値", "合否")


class TestExplorationInTheReport:
    def test_the_method_table_names_the_intent_and_the_question(self) -> None:
        method = _section(render_report(_answered(_exploration_design())), "## Method")

        assert (
            "| LIB-H01 LIB-H01 の題 | LIB-Q02 | 探索 | 期限切れはどの館で多いか "
            "| 2群の割合の比較（scipy） | 2群の期限切れ率を比べるため |"
        ) in method.splitlines()

    def test_the_question_is_escaped_as_text_from_the_records(self) -> None:
        method = _section(
            render_report(_answered(_exploration_design(statement=POISON))),
            "## Method",
        )

        assert POISON_ESCAPED in method

    def test_its_part_of_the_results_opens_without_a_verdict(self) -> None:
        results = _results(
            _answered(
                _exploration_design(
                    conclude_events=(_event("LIB-H01-E04", "本館が多い", "conclude"),),
                    metrics=(_metric("館の差", "0.12", threshold="0.05", passed=True),),
                )
            )
        )

        lines = results.splitlines()
        assert "探索を終えた。判定はしていない。本館が多い（LIB-H01-E04）" in lines
        assert "| 指標 | 値 |" in lines
        assert "| 館の差 | 0.12 |" in lines
        rest = results.replace("探索を終えた。判定はしていない。", "")
        for word in _JUDGING:
            assert word not in rest, word

    def test_it_has_no_evidence_against_a_hypothesis(self) -> None:
        limitations = _discussion(
            _report(
                designs=(
                    _exploration_design(
                        contradicting_evidence=(_event("LIB-H01-E02", "分館は少ない"),),
                    ),
                )
            ),
            "### Limitations",
        )

        assert "仮説" not in limitations
        assert "分館は少ない" not in limitations

    def test_a_report_of_explorations_holds_no_judging_word(self) -> None:
        markdown = render_report(
            _answered(
                _exploration_design(
                    conclude_events=(_event("LIB-H01-E04", "本館が多い", "conclude"),),
                    metrics=(_metric("館の差", "0.12"),),
                ),
            )
        )
        # The fixed sentence and the column heading AC 4 names are the only exceptions.
        for allowed in ("探索を終えた。判定はしていない。", "探索の問い / 検証仮説"):
            markdown = markdown.replace(allowed, "")

        for word in _JUDGING:
            assert word not in markdown, word


class TestLegacyExplorationInTheReport:
    def test_it_keeps_the_old_sentence_and_its_intent_is_marked(self) -> None:
        markdown = render_report(
            _answered(_legacy_design(status=DesignStatus.supported))
        )

        method = _section(markdown, "## Method")
        assert (
            "| LIB-H01 LIB-H01 の題 | LIB-Q02 | 探索（旧形式） | LIB-H01 の仮説 "
            in method
        )
        assert (
            "LIB-H01: 旧形式の探索: 探索の分析設計に、仮説と判定が書かれている。"
            in method.splitlines()
        )
        assert (
            "仮説は支持された。"
            in _results(
                _answered(_legacy_design(status=DesignStatus.supported))
            ).splitlines()
        )

    def test_only_a_legacy_exploration_carries_the_note(self) -> None:
        markdown = render_report(_answered(_design(), _exploration_design("LIB-H02")))

        assert "旧形式の探索" not in markdown

    def test_its_evidence_against_keeps_the_old_word(self) -> None:
        limitations = _discussion(
            _report(
                designs=(
                    _legacy_design(
                        contradicting_evidence=(_event("LIB-H01-E02", "雨の週は多い"),),
                    ),
                )
            ),
            "### Limitations",
        )

        assert "LIB-H01 LIB-H01 の題 の仮説に反する証拠:" in limitations.splitlines()


def _analysis_design(**over: object) -> AnalysisDesign:
    data: dict = {
        "id": "LIB-H01",
        "theme_id": "LIB",
        "title": "館ごとの期限切れ",
        "status": "analyzing",
        "created_at": "2026-11-01T09:00:00+09:00",
        "updated_at": "2026-11-01T09:00:00+09:00",
    }
    data.update(over)
    return AnalysisDesign.model_validate(data)


def _from_note(
    design: AnalysisDesign, events: tuple[NoteEvent, ...] = ()
) -> ReportDesign:
    conclusion = Conclusion(
        status=design.status,
        conclude_events=(),
        next_action=(),
        contradicting_evidence=(),
        reflect_events=(),
        open_questions=(),
    )
    return ReportDesign.of(
        DesignNote(
            design=design,
            sources=(),
            events=events,
            verdict=NoteVerdict(metrics=(), conclusion=None),
            figures=(),
            cells=None,
            lineage=None,
            local_files=(),
            conclusion=conclusion,
        )
    )


class TestReportDesignOfANote:
    def test_an_exploration_takes_its_question_and_no_evidence_against(self) -> None:
        design = _analysis_design(
            analysis_intent="exploratory",
            exploration_question="期限切れはどの館で多いか",
            exploration_background="館ごとの差をまだ見ていない",
            status="explored",
        )
        against = NoteEvent(
            id="LIB-H01-E02",
            type="evidence",
            direction="contradicts",
            content="分館は少ない",
            created_at="",
        )

        report_design = _from_note(design, (against,))

        assert report_design.form is DesignForm.exploration
        assert report_design.intent == "探索"
        assert report_design.statement == "期限切れはどの館で多いか"
        assert report_design.contradicting_evidence == ()
        assert report_design.lead_sentence == "探索を終えた。判定はしていない。"

    @pytest.mark.parametrize(
        ("intent", "word", "form"),
        [
            ("confirmatory", "検証", DesignForm.confirmation),
            ("exploratory", "探索（旧形式）", DesignForm.legacy_exploration),
            ("mixed", "探索と検証（旧形式）", DesignForm.confirmation),
        ],
    )
    def test_a_design_with_a_hypothesis_takes_it_and_its_intent_word(
        self, intent: str, word: str, form: DesignForm
    ) -> None:
        design = _analysis_design(
            analysis_intent=intent,
            hypothesis_statement="延ばすと減る",
            hypothesis_background="7日で多い",
        )

        report_design = _from_note(design)

        assert (report_design.form, report_design.intent, report_design.statement) == (
            form,
            word,
            "延ばすと減る",
        )


# Epic 33 US-1 AC 5: a verdict saved before the Epic, as the report tabulates it.
# The columns and values are the ones before the Epic, except that the interval
# column is headed 区間 and names its kind (US-2 AC 2). None: no metric table.
_PRIMARY_AND_GUARDRAIL_TABLE = [
    "| 指標 | 値 | 区間 | 標本サイズ | しきい値 | 合否 |",
    "| --- | --- | --- | --- | --- | --- |",
    "| rho | 0.62 | 信頼区間 水準 0.95: [0.51, 0.69] | 412 | 0.70 | ✓ |",
    "| 欠損の検査 | — | — | — | — | ✓ |",
]
REPORT_TABLES: dict[str, list[str] | None] = {
    "no_metrics": None,
    "p_and_p_value": [
        "| 指標 | 値 | p 値 |",
        "| --- | --- | --- |",
        "| 旧い p | 1.80 | 0.040 |",
        "| 契約の p\\_value | 1.80 | 0.030 |",
        "| 両方 | 1.80 | 0.040 |",
    ],
    "optional_items": [
        "| 指標 | 値 | 効果量 | 区間 | 標本サイズ | しきい値 | p 値 | 合否 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| 任意の項目なし | 0.346 | — | — | — | 0.050 | — | ✓ |",
        "| 欠けた項目 | 1 | — | — | — | — | — | — |",
        "| そろった項目 | 0.00010 | 0.30（cohens\\_d） | 信頼区間 水準 0.95: [0.10, 0.50] "
        "| 1520 | 0.050 | 1e-05 | ✓ |",
    ],
    "exploration_with_a_pass": [
        "| 指標 | 値 | 区間 | 標本サイズ | しきい値 | 合否 |",
        "| --- | --- | --- | --- | --- | --- |",
        "| 待ち日数の差 | 1.80 | 信頼区間 水準 0.95: [0.40, 3.20] | 840 | 1.0 | ✓ |",
    ],
    "threshold_kinds": [
        "| 指標 | 値 | しきい値 | 合否 |",
        "| --- | --- | --- | --- |",
        "| 数 | 2.10 | 2.0 | ✓ |",
        "| 文字 | 2.10 | 2.0 日以上 | ✓ |",
        '| その他の JSON | 2.10 | {"min": 1.0, "max": \\[2.0, NaN\\]} | — |',
    ],
    "pass_not_a_boolean": [
        "| 指標 | 値 | しきい値 |",
        "| --- | --- | --- |",
        "| 文字の合否 | 2.10 | 2.0 |",
        "| 数の合否 | 2.10 | 2.0 |",
        "| null の合否 | 2.10 | 2.0 |",
    ],
    "mixed_design": _PRIMARY_AND_GUARDRAIL_TABLE,
    "design_without_an_intent": _PRIMARY_AND_GUARDRAIL_TABLE,
}


def _tables(markdown: str) -> list[list[str]]:
    """The lines of each table in *markdown*, in order."""
    return [
        table.splitlines()
        for table in re.findall(r"(?:^\|.*\n?)+", markdown, flags=re.MULTILINE)
    ]


@pytest.mark.parametrize("name", SAVED_VERDICTS)
def test_the_report_tabulates_a_saved_verdict_as_before(
    tmp_path: Path, name: str
) -> None:
    insight = tmp_path / ".insight"
    design_id = save_design_with_verdict(insight, *SAVED_VERDICTS[name])
    design = replace(
        ReportDesign.of(load_design_note(design_id, base_dir=insight)), id="LIB-H01"
    )

    tables = _tables(_results(_answered(design)))

    assert tables == ([] if REPORT_TABLES[name] is None else [REPORT_TABLES[name]])


# Story 33.3 (Epic 33 US-1 AC 4, US-2 AC 2 and AC 5): how the report draws the
# metric tables. The rules of the tables are tested once in
# tests/test_verdict_table.py; here, only what the report adds: its headings,
# its dashes and its escaping.


def _group(*names: str, value: str | None = None, **over: object) -> MetricGroup:
    fields: dict = {
        "group": names,
        "value": value,
        "p": None,
        "effect_size": None,
        "interval": None,
        "sample_size": None,
    }
    fields.update(over)
    return MetricGroup(**fields)


def _metric_tables(*metrics: VerdictMetric, design: ReportDesign | None = None) -> str:
    """The Results of a report whose one design holds *metrics*."""
    return _results(_answered(replace(design or _design(), metrics=metrics)))


class TestIntervalInTheReport:
    def test_a_kind_the_report_has_no_word_for_is_escaped(self) -> None:
        lines = _metric_tables(
            _metric(
                "差",
                "0.1",
                interval=ValueInterval("bootstrap_percentile", "0.95", "0.10", "0.50"),
            ),
        ).splitlines()

        assert "| 指標 | 値 | 区間 |" in lines
        assert "| 差 | 0.1 | bootstrap\\_percentile 水準 0.95: [0.10, 0.50] |" in lines

    def test_an_empty_kind_reads_as_a_dash_as_in_the_note(self) -> None:
        lines = _metric_tables(
            _metric("差", "0.1", interval=ValueInterval("", "0.95", "0.10", "0.50")),
        ).splitlines()

        assert "| 差 | 0.1 | — 水準 0.95: [0.10, 0.50] |" in lines


class TestGroupsInTheReport:
    def test_two_axes_of_values_alone_make_a_table_of_rows_and_columns(
        self,
    ) -> None:
        results = _metric_tables(
            _metric(
                "待ちの割合",
                None,
                by=("branch", "wait_band"),
                groups=(
                    _group("中央館", "3日以内", value="0.42"),
                    _group("中央館", "8日以上", value="0.20"),
                    _group("北分館", "3日以内", value="0.25"),
                    _group("北分館", "8日以上", value="0.35"),
                ),
            ),
        )

        assert "待ちの割合（branch × wait\\_band）" in results.splitlines()
        assert _tables(results) == [
            [
                "| branch | 3日以内 | 8日以上 |",
                "| --- | --- | --- |",
                "| 中央館 | 0.42 | 0.20 |",
                "| 北分館 | 0.25 | 0.35 |",
            ]
        ]

    def test_one_axis_makes_a_table_with_a_column_of_groups(self) -> None:
        results = _metric_tables(
            _metric(
                "待ち日数",
                None,
                by=("branch",),
                groups=(
                    _group(
                        "中央館",
                        value="4.0",
                        interval=ValueInterval(CONFIDENCE, "0.95", "3.5", "4.5"),
                        sample_size="1200",
                    ),
                    _group("北分館", value="7.0", sample_size="310"),
                ),
            ),
        )

        assert "待ち日数（branch）" in results.splitlines()
        assert _tables(results) == [
            [
                "| branch | 値 | 区間 | 標本サイズ |",
                "| --- | --- | --- | --- |",
                "| 中央館 | 4.0 | 信頼区間 水準 0.95: [3.5, 4.5] | 1200 |",
                "| 北分館 | 7.0 | — | 310 |",
            ]
        ]
