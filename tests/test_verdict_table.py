"""Tests of skills/_shared/verdict_table.py: the rules of the metric tables (Epic 33).

The analysis note and the theme report draw the same tables, each escaping in
its own way; the rules are tested here once (US-1 AC 3, US-2 AC 2, AC 4,
ADR-0050, ADR-0052 8, 9). What the two renderers add is tested beside them.
"""

from __future__ import annotations

import pytest

from insight_blueprint.models.design import DesignForm
from skills._shared.verdict_table import (
    CONFIDENCE,
    Fixed,
    MetricGroup,
    MetricJudgment,
    Text,
    TextTable,
    ValueInterval,
    VerdictMetric,
    interval_text,
    metric_tables,
)


def _metric(**over: object) -> VerdictMetric:
    fields: dict = {
        "name": "期限切れ率の差",
        "value": "0.346",
        "threshold": None,
        "p": None,
        "passed": None,
        "effect_size": None,
        "interval": None,
        "sample_size": None,
    }
    fields.update(over)
    return VerdictMetric(**fields)


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


def _joined(text: Text) -> str:
    return "".join(text)


def _plain(table: TextTable) -> tuple[str | None, list[list[str]]]:
    """(title, [headings, *rows]) with each text joined; "" where nothing is written."""
    title = None if table.title is None else _joined(table.title)
    return title, [
        [_joined(h) for h in table.headings],
        *([_joined(c) for c in row] for row in table.rows),
    ]


def _tables(
    *metrics: VerdictMetric, form: DesignForm = DesignForm.confirmation
) -> list[tuple[str | None, list[list[str]]]]:
    return [_plain(t) for t in metric_tables(metrics, form, sample_size="N", p="p")]


def _main(*metrics: VerdictMetric, form: DesignForm = DesignForm.confirmation):
    (title, rows), *_ = _tables(*metrics, form=form)
    assert title is None
    return rows


class TestLinesAndJudgment:
    def test_the_lines_and_the_judgment_come_in_their_own_columns(self) -> None:
        primary = _metric(
            name="待ち日数の差",
            value="1.4",
            support_line="2.0",
            reject_line="1.0",
            judgment=MetricJudgment.inconclusive,
        )
        guardrail = _metric(name="欠損率", value="0.02", threshold="0.05", passed=True)

        assert _main(primary, guardrail) == [
            ["指標", "値", "支持の線", "棄却の線", "判定", "しきい値", "合否"],
            ["待ち日数の差", "1.4", "2.0", "1.0", "結論しない", "", ""],
            ["欠損率", "0.02", "", "", "", "0.05", "✓"],
        ]

    @pytest.mark.parametrize(
        ("judgment", "word"),
        [
            (MetricJudgment.supported, "支持"),
            (MetricJudgment.rejected, "棄却"),
            (MetricJudgment.inconclusive, "結論しない"),
        ],
    )
    def test_each_judgment_reads_as_its_word(
        self, judgment: MetricJudgment, word: str
    ) -> None:
        rows = _main(_metric(judgment=judgment))

        assert rows[1][rows[0].index("判定")] == word

    def test_one_line_alone_leaves_the_other_line_out(self) -> None:
        metric = _metric(support_line="2.0", judgment=MetricJudgment.supported)

        assert _main(metric)[0] == ["指標", "値", "支持の線", "判定"]

    def test_a_failed_metric_is_a_cross(self) -> None:
        assert _main(_metric(passed=False))[1] == ["期限切れ率の差", "0.346", "✗"]

    def test_an_exploration_drops_every_judging_column(self) -> None:
        metric = _metric(
            support_line="2.0",
            reject_line="1.0",
            judgment=MetricJudgment.supported,
            threshold="0.05",
            passed=True,
            p="0.01",
        )

        rows = _main(metric, form=DesignForm.exploration)

        assert rows == [["指標", "値", "p"], ["期限切れ率の差", "0.346", "0.01"]]


class TestColumnsNoMetricFills:
    def test_only_the_columns_some_metric_fills_come_out(self) -> None:
        rows = _main(_metric(), _metric(name="件数", value="12"))

        assert rows == [["指標", "値"], ["期限切れ率の差", "0.346"], ["件数", "12"]]

    def test_a_column_one_metric_fills_is_empty_for_the_others(self) -> None:
        rows = _main(_metric(sample_size="840"), _metric(name="件数"))

        assert rows[0] == ["指標", "値", "N"]
        assert rows[2] == ["件数", "0.346", ""]

    def test_a_value_written_empty_keeps_its_column(self) -> None:
        assert _main(_metric(sample_size=""))[0] == ["指標", "値", "N"]

    def test_the_renderer_names_the_sample_size_and_p_columns(self) -> None:
        metric = _metric(sample_size="840", p="0.01")

        (table,) = metric_tables(
            (metric,), DesignForm.confirmation, sample_size="標本サイズ", p="p 値"
        )

        assert _plain(table)[1][0] == ["指標", "値", "標本サイズ", "p 値"]


class TestInterval:
    @pytest.mark.parametrize(
        ("kind", "shown"),
        [
            (CONFIDENCE, "信頼区間 水準 0.95: [0.10, 0.50]"),
            ("hdi", "HDI 水準 0.95: [0.10, 0.50]"),
            ("eti", "等裾信用区間 水準 0.95: [0.10, 0.50]"),
            ("bootstrap_percentile", "bootstrap_percentile 水準 0.95: [0.10, 0.50]"),
            ("", "— 水準 0.95: [0.10, 0.50]"),
        ],
    )
    def test_the_kind_is_named_beside_the_level_and_the_bounds(
        self, kind: str, shown: str
    ) -> None:
        assert _joined(interval_text(ValueInterval(kind, "0.95", "0.10", "0.50"))) == (
            shown
        )

    def test_only_the_written_parts_are_left_unfixed(self) -> None:
        """A renderer escapes the parts the notebook wrote, never the template."""
        text = interval_text(ValueInterval("bayes", "0.9", "1", "2"))

        assert [p for p in text if not isinstance(p, Fixed)] == [
            "bayes",
            "0.9",
            "1",
            "2",
        ]

    def test_a_named_or_empty_kind_is_a_word_of_the_table(self) -> None:
        for kind in ("hdi", ""):
            assert isinstance(
                interval_text(ValueInterval(kind, "1", "2", "3"))[0], Fixed
            )

    def test_the_effect_size_is_its_value_then_its_kind(self) -> None:
        rows = _main(_metric(effect_size=("cohens_d", "0.30")))

        assert rows == [
            ["指標", "値", "効果量"],
            ["期限切れ率の差", "0.346", "0.30（cohens_d）"],
        ]


class TestGroupTables:
    def test_two_axes_of_values_only_lay_one_axis_down_and_one_across(self) -> None:
        metric = _metric(
            name="予約の割合",
            value=None,
            by=("branch", "wait_band"),
            groups=(
                _group("中央館", "3日以内", value="0.42"),
                _group("中央館", "8日以上", value="0.20"),
                _group("北分館", "3日以内", value="0.25"),
                _group("北分館", "8日以上", value="0.35"),
            ),
        )

        assert _tables(metric) == [
            (
                "予約の割合（branch × wait_band）",
                [
                    ["branch", "3日以内", "8日以上"],
                    ["中央館", "0.42", "0.20"],
                    ["北分館", "0.25", "0.35"],
                ],
            )
        ]

    def test_the_names_keep_the_order_they_were_first_written_in(self) -> None:
        """Sorting would put "10" before "9"; nothing is sorted."""
        metric = _metric(
            value=None,
            by=("月", "区分"),
            groups=(
                _group("9", "b", value="1"),
                _group("10", "a", value="2"),
                _group("9", "a", value="3"),
            ),
        )

        ((_, rows),) = _tables(metric)

        assert rows == [["月", "b", "a"], ["9", "1", "3"], ["10", "", "2"]]

    def test_one_axis_is_a_tall_table_with_a_column_for_the_group(self) -> None:
        metric = _metric(
            name="待ち日数",
            value=None,
            by=("branch",),
            groups=(
                _group("中央館", value="4.0", sample_size="1200"),
                _group("北分館", value="7.0", sample_size="310"),
            ),
        )

        assert _tables(metric) == [
            (
                "待ち日数（branch）",
                [
                    ["branch", "値", "N"],
                    ["中央館", "4.0", "1200"],
                    ["北分館", "7.0", "310"],
                ],
            )
        ]

    def test_two_axes_with_more_than_a_value_are_a_tall_table(self) -> None:
        metric = _metric(
            value=None,
            by=("x", "y"),
            groups=(
                _group(
                    "p",
                    "q",
                    value="1",
                    interval=ValueInterval("hdi", "0.9", "0.5", "1.5"),
                ),
                _group("p", "r", value="2", p="0.03"),
            ),
        )

        ((_, rows),) = _tables(metric)

        assert rows == [
            ["x", "y", "値", "区間", "p"],
            ["p", "q", "1", "HDI 水準 0.9: [0.5, 1.5]", ""],
            ["p", "r", "2", "", "0.03"],
        ]

    def test_three_axes_are_a_tall_table(self) -> None:
        metric = _metric(
            value=None, by=("a", "b", "c"), groups=(_group("1", "2", "3", value="4"),)
        )

        ((_, rows),) = _tables(metric)

        assert rows == [["a", "b", "c", "値"], ["1", "2", "3", "4"]]

    def test_a_pair_written_twice_is_a_tall_table_so_no_value_is_hidden(self) -> None:
        metric = _metric(
            value=None,
            by=("x", "y"),
            groups=(_group("p", "q", value="1"), _group("p", "q", value="2")),
        )

        ((_, rows),) = _tables(metric)

        assert rows == [["x", "y", "値"], ["p", "q", "1"], ["p", "q", "2"]]

    def test_a_group_table_never_shows_a_judging_column(self) -> None:
        metric = _metric(value=None, by=("x",), groups=(_group("p", value="1"),))

        ((_, rows),) = _tables(metric, form=DesignForm.exploration)

        assert rows == [["x", "値"], ["p", "1"]]

    def test_a_metric_with_only_groups_has_no_row_in_the_main_table(self) -> None:
        grouped = _metric(
            name="群だけ", value=None, by=("x",), groups=(_group("p", value="1"),)
        )

        tables = _tables(_metric(), grouped)

        assert [title for title, _ in tables] == [None, "群だけ（x）"]
        assert tables[0][1] == [["指標", "値"], ["期限切れ率の差", "0.346"]]

    def test_a_metric_whose_only_cells_are_dropped_is_not_listed(self) -> None:
        grouped = _metric(
            name="群だけ",
            value=None,
            threshold="1.0",
            by=("x",),
            groups=(_group("p", value="1"),),
        )

        assert _tables(grouped, form=DesignForm.exploration) == [
            ("群だけ（x）", [["x", "値"], ["p", "1"]])
        ]

    def test_a_metric_with_a_value_and_groups_shows_both(self) -> None:
        metric = _metric(
            name="両方", value="9", by=("x",), groups=(_group("p", value="1"),)
        )

        assert _tables(metric) == [
            (None, [["指標", "値"], ["両方", "9"]]),
            ("両方（x）", [["x", "値"], ["p", "1"]]),
        ]

    def test_each_metric_of_groups_has_its_own_table_in_order(self) -> None:
        tables = _tables(
            _metric(name="A", value=None, by=("x",), groups=(_group("a", value="1"),)),
            _metric(name="B", value=None, by=("y",), groups=(_group("b", value="2"),)),
        )

        assert [title for title, _ in tables] == ["A（x）", "B（y）"]

    def test_the_names_in_a_title_are_text_from_the_verdict(self) -> None:
        metric = _metric(
            name="m", value=None, by=("a", "b"), groups=(_group("p", "q", value="1"),)
        )

        (table,) = metric_tables(
            (metric,), DesignForm.confirmation, sample_size="N", p="p"
        )

        assert table.title is not None
        assert [p for p in table.title if not isinstance(p, Fixed)] == ["m", "a", "b"]


def test_no_metric_gives_no_table() -> None:
    assert _tables() == []
