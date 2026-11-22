"""Tests of skills/_shared/tree_io.py (Epic 29): ``report``: the final report of a theme.

The report is written by code from the records, and refused when it could not
be trusted. tree_io is the only writer of ``.insight/reports/{theme_id}.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import catalog_io, design_io, tree_io
from tests.tree_io._support import _entry, _finish, _run_cli
from tests.tree_io.test_render_design import (
    CONNECTION_PATH,
    _figure,
    _write_verdict,
)
from tests.tree_io.test_render_design import _entry as _figure_entry


@pytest.fixture
def answered(world: Path) -> Path:
    """The LIB tree whose root has an answer under the current root revision."""
    result = tree_io.answer(
        "LIB", answers=[_entry("LIB-Q01", "期限切れは152件")], base_dir=world
    )
    assert result["written"], result
    return world


def _blank_the_number(base: Path) -> None:
    """Rewrite the journal an answer cites so the number it states is gone."""
    design_io.write_journal(
        "LIB-H01",
        {"events": [{"id": "LIB-H01-E01", "type": "observe", "content": "件数なし"}]},
        base_dir=base,
    )


def _report_path(base: Path) -> Path:
    return base / "reports" / "LIB.md"


def _kinds(result: dict) -> list[str]:
    return [reason["kind"] for reason in result["reasons"]]


class TestReportWritten:
    def test_it_writes_the_report_file_and_returns_its_path_and_the_round(
        self, answered: Path
    ) -> None:
        result = tree_io.report("LIB", base_dir=answered)

        assert result == {
            "written": True,
            "path": str(answered / "reports" / "LIB.md"),
            "figures": [],
            "round": 1,
            "root_answer_round": 1,
            "unfinished_designs": ["LIB-H01", "LIB-H02"],
        }
        text = _report_path(answered).read_text("utf-8")
        assert text.startswith("# 取り置き期限を延ばす試行をするか\n")
        assert "- 期限切れは152件（LIB-H01-E01）" in text

    def test_it_gives_the_same_bytes_twice_and_never_names_the_base_dir(
        self, answered: Path
    ) -> None:
        tree_io.report("LIB", base_dir=answered)
        first = _report_path(answered).read_bytes()

        tree_io.report("LIB", base_dir=answered)

        assert _report_path(answered).read_bytes() == first
        assert str(answered) not in first.decode("utf-8")

    def test_the_round_of_the_root_answer_is_told_apart_from_the_last_round(
        self, answered: Path
    ) -> None:
        later = tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=answered
        )
        assert later["written"], later

        result = tree_io.report("LIB", base_dir=answered)

        assert (result["round"], result["root_answer_round"]) == (2, 1)
        assert "2回目の振り返りの時点" in _report_path(answered).read_text("utf-8")

    def test_a_linked_design_that_is_not_finished_does_not_stop_the_report(
        self, answered: Path
    ) -> None:
        _finish(answered, "LIB-H01")

        result = tree_io.report("LIB", base_dir=answered)

        assert result["written"] is True
        assert result["unfinished_designs"] == ["LIB-H02"]

    def test_a_design_linked_to_two_nodes_is_listed_once(self, answered: Path) -> None:
        tree_io.link_design("LIB", "LIB-Q03", "LIB-H01", base_dir=answered)

        result = tree_io.report("LIB", base_dir=answered)

        assert result["unfinished_designs"] == ["LIB-H01", "LIB-H02"]

    def test_a_linked_design_that_no_longer_exists_is_an_error(
        self, answered: Path
    ) -> None:
        (answered / "designs" / "LIB-H02_hypothesis.yaml").unlink()

        with pytest.raises(ValueError, match="LIB-H02"):
            tree_io.report("LIB", base_dir=answered)

        assert not _report_path(answered).exists()

    def test_a_theme_id_that_is_not_a_theme_id_never_reaches_a_path(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="Invalid theme_id"):
            tree_io.report("../x", base_dir=tmp_path)


def _concluded(base: Path, design_id: str = "LIB-H01") -> None:
    """*design_id* concluded: supported, with a conclude event and evidence against it."""
    design_io.write_journal(
        design_id,
        {
            "events": [
                {
                    "id": f"{design_id}-E01",
                    "type": "observe",
                    "content": f"{design_id} は期限切れ152件、取消除外後34.6%",
                },
                {
                    "id": f"{design_id}-E02",
                    "type": "evidence",
                    "content": "金曜に確保した本は16%のまま",
                    "metadata": {"direction": "contradicts"},
                },
                {
                    "id": f"{design_id}-E03",
                    "type": "observe",
                    "content": "どこにも引用しない観察",
                },
                {
                    "id": f"{design_id}-E04",
                    "type": "conclude",
                    "content": "対象期間の期限切れは152件だった",
                },
            ]
        },
        base_dir=base,
    )
    _finish(base, design_id)


def _written(base: Path) -> tuple[dict, str]:
    result = tree_io.report("LIB", base_dir=base)
    assert result["written"], result
    return result, _report_path(base).read_text("utf-8")


class TestReportContents:
    def test_the_answered_question_comes_with_the_analysis_behind_it(
        self, answered: Path
    ) -> None:
        _concluded(answered)
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=answered
        )

        _, text = _written(answered)

        assert "| LIB-Q02 | LIB-Q02 の問い | LIB-Q01 |" in text
        assert "| LIB-H01 Test | LIB-Q02 | X improves Y | OLS | — |" in text
        assert "### LIB-Q02 LIB-Q02 の問い" in text
        assert "**根拠となる分析: LIB-H01 Test**" in text
        assert (
            "仮説は支持された。対象期間の期限切れは152件だった（LIB-H01-E04）" in text
        )
        assert "- 金曜に確保した本は16%のまま（LIB-H01-E02）" in text
        assert "### LIB-Q03 " not in text

    def test_the_appendix_lists_the_cited_records_and_no_other(
        self, answered: Path
    ) -> None:
        _concluded(answered)
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=answered
        )

        _, text = _written(answered)

        appendix = text[text.index("## Appendix") :]
        assert (
            "| LIB-H01-E01 | 観察 | LIB-H01 は期限切れ152件、取消除外後34.6% |"
            in appendix
        )
        assert "| LIB-H01-E04 | 結論 | 対象期間の期限切れは152件だった |" in appendix
        assert "| LIB-H01-E02 |" in appendix
        assert "LIB-H01-E03" not in text

    def test_the_figures_of_the_answered_questions_are_returned_and_linked(
        self, answered: Path
    ) -> None:
        for design_id in ("LIB-H01", "LIB-H02"):
            _figure(answered, f"{design_id}_fig01.png")
            _write_verdict(
                answered,
                design_id,
                {"figures": [_figure_entry(f"{design_id}_fig01.png")]},
            )
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=answered
        )

        result, text = _written(answered)

        assert result["figures"] == ["LIB-H01_fig01.png"]
        assert "![図 1](../notebooks/LIB-H01_fig01.png)" in text
        assert "LIB-H02_fig01.png" not in text

    def test_neither_a_connection_nor_code_nor_lineage_reaches_the_report(
        self, answered: Path
    ) -> None:
        catalog_io.create_source(
            id="reservations",
            name="予約台帳",
            type="csv",
            description="予約の一覧",
            connection={"path": CONNECTION_PATH},
            base_dir=answered,
        )
        design_io.update_design(
            "LIB-H01", {"source_ids": ["reservations"]}, base_dir=answered
        )
        notebooks = answered / "notebooks"
        notebooks.mkdir(parents=True, exist_ok=True)
        (notebooks / "LIB-H01.py").write_text(
            "import marimo\napp = marimo.App()\n\n@app.cell\ndef _():\n"
            f'    raw_df = pd.read_csv("{CONNECTION_PATH}")\n    return (raw_df,)\n\n'
            "@app.cell\ndef _(raw_df):\n    shown_cell_marker = 1\n    return\n",
            encoding="utf-8",
        )
        (answered / "lineage").mkdir()
        (answered / "lineage" / "LIB-H01.mmd").write_text(
            "flowchart TD\n  lineage_marker\n", encoding="utf-8"
        )

        _, text = _written(answered)

        assert "| 予約台帳 | csv | 予約の一覧 |" in text
        assert CONNECTION_PATH not in text
        assert "shown_cell_marker" not in text
        assert "lineage_marker" not in text

    def test_the_last_tree_decision_is_the_future_direction(
        self, answered: Path
    ) -> None:
        tree_io.decide(
            "LIB", kind="start", node_id="LIB-Q01", reason="始める", base_dir=answered
        )
        tree_io.decide(
            "LIB",
            kind="deepen",
            node_id="LIB-Q03",
            reason="通知の遅れを先に確かめる",
            base_dir=answered,
        )

        _, text = _written(answered)

        future = text[text.index("### Future Directions") : text.index("## Appendix")]
        assert "- 次に調べる論点: LIB-Q03 LIB-Q03 の問い" in future
        assert "- 理由: 通知の遅れを先に確かめる" in future


class TestReportRecordsOfTheDesigns:
    def test_a_conclude_event_whose_id_names_another_design_is_shown_as_its_journal_holds_it(
        self, answered: Path
    ) -> None:
        _concluded(answered)
        journal = design_io.load_journal("LIB-H01", base_dir=answered)
        journal["events"][3]["id"] = "LIB-H09-E05"
        design_io.write_journal("LIB-H01", journal, base_dir=answered)
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=answered
        )

        _, text = _written(answered)

        assert "| LIB-H09-E05 | 結論 | 対象期間の期限切れは152件だった |" in text

    def test_a_design_event_that_reuses_a_cited_id_for_another_text_is_an_error(
        self, answered: Path
    ) -> None:
        _concluded(answered)
        journal = design_io.load_journal("LIB-H02", base_dir=answered)
        journal["events"].append(
            {
                "id": "LIB-H01-E01",
                "type": "evidence",
                "content": "別の本文",
                "metadata": {"direction": "contradicts"},
            }
        )
        design_io.write_journal("LIB-H02", journal, base_dir=answered)

        with pytest.raises(ValueError, match="LIB-H01-E01"):
            tree_io.report("LIB", base_dir=answered)

        assert not _report_path(answered).exists()

    def test_a_linked_design_whose_note_cannot_be_built_is_named(
        self, answered: Path
    ) -> None:
        _write_verdict(answered, "LIB-H02", "{not json")

        with pytest.raises(ValueError, match="analysis note of 'LIB-H02'"):
            tree_io.report("LIB", base_dir=answered)


class TestReportRefused:
    def test_a_theme_without_a_tree_is_not_written_and_says_so(
        self, insight: Path
    ) -> None:
        result = tree_io.report("LIB", base_dir=insight)

        assert result["written"] is False
        assert _kinds(result) == ["no_tree"]
        assert not _report_path(insight).exists()

    def test_a_root_without_an_answer_is_not_written(self, world: Path) -> None:
        result = tree_io.report("LIB", base_dir=world)

        assert result["written"] is False
        assert _kinds(result) == ["no_root_answer"]
        assert "LIB" in result["reasons"][0]["message"]
        assert not _report_path(world).exists()

    def test_a_root_answer_given_before_the_root_was_revised_is_not_written(
        self, answered: Path
    ) -> None:
        tree_io.revise_root(
            "LIB",
            question="延長の試行を全館で始めるか",
            bump=True,
            reason="範囲を広げた",
            base_dir=answered,
        )

        result = tree_io.report("LIB", base_dir=answered)

        assert _kinds(result) == ["no_root_answer"]
        assert "revision 2" in result["reasons"][0]["message"]
        assert not _report_path(answered).exists()

    def test_a_violation_on_any_node_stops_the_report_and_leaves_an_older_file(
        self, answered: Path
    ) -> None:
        tree_io.answer(
            "LIB",
            answers=[_entry("LIB-Q02", "期限切れは152件", "LIB-H01-E01")],
            base_dir=answered,
        )
        tree_io.report("LIB", base_dir=answered)
        older = _report_path(answered).read_bytes()
        _blank_the_number(answered)

        result = tree_io.report("LIB", base_dir=answered)

        assert result["written"] is False
        assert _kinds(result) == ["violations"]
        found = result["reasons"][0]["violations"]
        assert {v["node_id"] for v in found} == {"LIB-Q01", "LIB-Q02"}
        assert {v["kind"] for v in found} == {"number-not-cited"}
        assert _report_path(answered).read_bytes() == older

    def test_no_root_answer_and_violations_are_both_given_in_that_order(
        self, world: Path
    ) -> None:
        tree_io.answer(
            "LIB", answers=[_entry("LIB-Q02", "期限切れは152件")], base_dir=world
        )
        _blank_the_number(world)

        result = tree_io.report("LIB", base_dir=world)

        assert _kinds(result) == ["no_root_answer", "violations"]

    def test_a_tree_that_fails_its_schema_is_an_error_not_a_reason(
        self, insight: Path
    ) -> None:
        (insight / "themes").mkdir(parents=True)
        (insight / "themes" / "LIB_tree.yaml").write_text(
            "theme_id: LIB\n", encoding="utf-8"
        )

        with pytest.raises(ValueError):
            tree_io.report("LIB", base_dir=insight)


class TestReportCli:
    def test_it_exits_0_with_the_path_when_the_report_is_written(
        self, answered: Path
    ) -> None:
        done = _run_cli(answered, "report", "--theme", "LIB")

        assert done.returncode == 0, done.stderr
        assert json.loads(done.stdout)["path"] == str(answered / "reports" / "LIB.md")
        assert _report_path(answered).exists()

    def test_it_exits_3_with_the_reasons_when_the_root_has_no_answer(
        self, world: Path
    ) -> None:
        done = _run_cli(world, "report", "--theme", "LIB")

        assert done.returncode == 3
        assert _kinds(json.loads(done.stdout)) == ["no_root_answer"]
        assert done.stderr == ""

    def test_it_exits_3_and_says_where_it_looked_when_there_is_no_tree(
        self, insight: Path
    ) -> None:
        done = _run_cli(insight, "report", "--theme", "LIB")

        assert done.returncode == 3
        assert _kinds(json.loads(done.stdout)) == ["no_tree"]
        looked = str(insight.resolve() / "themes" / "LIB_tree.yaml")
        assert done.stderr.strip() == f"tree_io: no tree at {looked}"

    def test_it_needs_a_theme(self, insight: Path) -> None:
        done = _run_cli(insight, "report")

        assert done.returncode == 1
        assert "--theme is required" in done.stderr

    def test_a_tree_that_fails_its_schema_exits_1_without_a_traceback(
        self, insight: Path
    ) -> None:
        (insight / "themes").mkdir(parents=True)
        (insight / "themes" / "LIB_tree.yaml").write_text(
            "theme_id: LIB\n", encoding="utf-8"
        )

        done = _run_cli(insight, "report", "--theme", "LIB")

        assert done.returncode == 1
        assert done.stderr.startswith("tree_io: ")
        assert "Traceback" not in done.stderr


# Marks that would work as Markdown if copied raw, with a break and a block mark.
_MARKS = "> 152件 <b>x</b> | y | `z` ![i](http://example.invalid/a.png)\n# w"
_MARKS_ESCAPED = (
    r"\> 152件 \<b>x\</b> \| y \| \`z\` !\[i\](http://example.invalid/a.png) # w"
)


class TestReportSourceText:
    def test_texts_from_the_tree_and_the_journal_are_escaped_in_the_file(
        self, answered: Path
    ) -> None:
        design_io.write_journal(
            "LIB-H01",
            {"events": [{"id": "LIB-H01-E01", "type": "conclude", "content": _MARKS}]},
            base_dir=answered,
        )
        _finish(answered, "LIB-H01")
        tree_io.answer("LIB", answers=[_entry("LIB-Q02", _MARKS)], base_dir=answered)

        _, text = _written(answered)

        assert f"- {_MARKS_ESCAPED}（LIB-H01-E01）" in text.splitlines()
        assert f"仮説は支持された。{_MARKS_ESCAPED}（LIB-H01-E01）" in text
        assert f"| LIB-H01-E01 | 結論 | {_MARKS_ESCAPED} |" in text
        assert "<b>" not in text.replace(r"\<b>", "")
        assert "\n# w" not in text
