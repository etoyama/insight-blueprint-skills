"""Tests of skills/_shared/theme_report.py (Epic 29): the final report of a theme, as Markdown."""

from __future__ import annotations

from datetime import datetime

from insight_blueprint.models.tree import Aim, Answer, AnswerStatement
from skills._shared.theme_report import ThemeReport, render_report

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


def _statement(kind: str, text: str, *cites: str) -> AnswerStatement:
    return AnswerStatement(kind=kind, text=text, cites=list(cites) or ["LIB-H01-E01"])


def _report(*statements: AnswerStatement, aim: Aim = BUSINESS_AIM) -> ThemeReport:
    return ThemeReport(
        theme_id="LIB",
        root_question="取り置き期限を延ばす試行をするか",
        aim=aim,
        round=2,
        answer=Answer(
            round=2,
            root_revision=1,
            statements=list(statements) or [_statement("claim", "期限切れは152件")],
            created_at=datetime(2026, 11, 1, 9, 30),
        ),
    )


def _headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]


class TestRenderReport:
    def test_the_headings_are_the_apa_ones_in_english_in_order(self) -> None:
        assert _headings(render_report(_report())) == [
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

        assert markdown.index("**言えること**") < markdown.index("**留保すべきこと**")
        assert markdown.index("**留保すべきこと**") < markdown.index(
            "**まだ分からないこと**"
        )

    def test_a_kind_with_no_statement_has_no_heading(self) -> None:
        markdown = render_report(_report(_statement("claim", "期限切れは152件")))

        assert "**言えること**" in markdown
        assert "**留保すべきこと**" not in markdown
        assert "**まだ分からないこと**" not in markdown

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

        assert markdown.endswith("## Appendix\n")
        assert not markdown.endswith("\n\n")
