"""Tests of skills/_shared/design_note.py (Epic 28, Stories 28.1 to 28.3): the analysis note page."""

from __future__ import annotations

import base64
import re

import pytest

from insight_blueprint.models.design import AnalysisDesign, DesignStatus
from skills._shared.design_note import (
    CONFIDENCE,
    CodeCell,
    Conclusion,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    NoteVerdict,
    ValueInterval,
    VerdictMetric,
    note_anchor,
    render_note,
    render_note_page,
)

PNG = b"\x89PNG\r\n\x1a\nnot-really-a-png"
EVIL = '<script>alert(1)</script>"'


def _design(**over: object) -> AnalysisDesign:
    data: dict = {
        "id": "LIB-H01",
        "theme_id": "LIB",
        "title": "取り置き期限と期限切れ率",
        "hypothesis_statement": "期限を延ばすと期限切れが減る",
        "hypothesis_background": "取り置き7日で期限切れが多い",
        "status": "analyzing",
        "metrics": [],
        "explanatory": [],
        "chart": [],
        "source_ids": [],
        "created_at": "2026-11-01T09:00:00+09:00",
        "updated_at": "2026-11-01T09:00:00+09:00",
    }
    data.update(over)
    return AnalysisDesign.model_validate(data)


def _note(**over: object) -> DesignNote:
    """A note; ``metrics`` or ``verdict_conclusion`` stands for a verdict that holds them."""
    fields: dict = {
        "design": _design(),
        "sources": (),
        "events": (),
        "verdict": None,
        "figures": (),
        "cells": None,
        "lineage": None,
        "local_files": (),
        "conclusion": None,
    }
    if "metrics" in over or "verdict_conclusion" in over:
        fields["verdict"] = NoteVerdict(
            metrics=over.pop("metrics", ()),  # type: ignore[arg-type]
            conclusion=over.pop("verdict_conclusion", None),  # type: ignore[arg-type]
        )
    fields.update(over)
    return DesignNote(**fields)


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


def _event(
    id_: str, type_: str, content: str, direction: str | None = None, at: str = ""
) -> NoteEvent:
    return NoteEvent(
        id=id_, type=type_, direction=direction, content=content, created_at=at
    )


def _rich_design() -> AnalysisDesign:
    return _design(
        decision_context={"decision_maker": "図書館員", "decision": "延長を試すか"},
        methodology={
            "method": "ロジスティック回帰",
            "package": "statsmodels",
            "reason": "二値の結果だから",
            "steps": ["取消を除く", "回帰を当てる"],
        },
        metrics=[
            {
                "target": "期限切れ率",
                "tier": "primary",
                "aggregation": "mean",
                "grouping": ["branch", "week"],
                "filter": "取消を除く",
                "comparison": "延長前後",
            }
        ],
        explanatory=[
            {
                "name": "取り置き日数",
                "role": "treatment",
                "description": "延長の有無",
                "time_points": "予約時",
            }
        ],
    )


def _position(html: str, marker: str) -> int:
    found = html.find(marker)
    assert found >= 0, marker
    return found


class TestSections:
    def test_sections_come_in_the_order_of_the_report_template(self) -> None:
        html = str(render_note(_note(design=_rich_design())))

        ids = [
            f'id="note-LIB-H01-{name}"'
            for name in (
                "status",
                "hypothesis",
                "decision",
                "method",
                "metrics",
                "explanatory",
                "sources",
                "results",
                "code",
                "lineage",
                "progress",
                "files",
            )
        ]
        positions = [_position(html, i) for i in ids]
        assert positions == sorted(positions)

    def test_the_note_is_one_section_with_the_note_anchor_as_its_id(self) -> None:
        html = str(render_note(_note()))

        assert note_anchor("LIB-H01") == "note-LIB-H01"
        assert html.startswith('<section class="design-note" id="note-LIB-H01">')
        assert html.count('<section class="design-note"') == 1

    def test_the_title_carries_the_design_id_and_title(self) -> None:
        html = str(render_note(_note()))

        assert "分析ノート LIB-H01 取り置き期限と期限切れ率" in html

    def test_hypothesis_and_background_are_shown_verbatim(self) -> None:
        html = str(render_note(_note()))

        assert "期限を延ばすと期限切れが減る" in html
        assert "取り置き7日で期限切れが多い" in html

    def test_decision_context_shows_who_decides_what(self) -> None:
        html = str(render_note(_note(design=_rich_design())))

        assert "決める人: 図書館員" in html
        assert "決めること: 延長を試すか" in html

    def test_a_missing_decision_context_says_it_is_not_written(self) -> None:
        html = str(render_note(_note()))

        assert "決定の文脈は書かれていない。" in html

    def test_method_shows_package_reason_and_steps(self) -> None:
        html = str(render_note(_note(design=_rich_design())))

        assert "ロジスティック回帰" in html
        assert "statsmodels" in html
        assert "二値の結果だから" in html
        assert html.index("取消を除く</li>") < html.index("回帰を当てる</li>")

    def test_a_missing_methodology_says_it_is_not_written(self) -> None:
        html = str(render_note(_note()))

        assert "手法は書かれていない。" in html

    def test_metric_definitions_come_as_a_table_with_grouping_joined(self) -> None:
        html = str(render_note(_note(design=_rich_design())))

        for cell in (
            "期限切れ率",
            "primary",
            "mean",
            "branch, week",
            "取消を除く",
            "延長前後",
        ):
            assert f"<td>{cell}</td>" in html

    def test_no_metric_definition_says_none_is_defined(self) -> None:
        html = str(render_note(_note()))

        assert "指標の定義は無い。" in html

    def test_explanatory_variables_come_as_a_table(self) -> None:
        html = str(render_note(_note(design=_rich_design())))

        for cell in ("取り置き日数", "treatment", "延長の有無", "予約時"):
            assert f"<td>{cell}</td>" in html

    def test_no_explanatory_variable_says_none(self) -> None:
        html = str(render_note(_note()))

        assert "説明変数は無い。" in html

    def test_sources_show_name_type_and_description(self) -> None:
        source = NoteSource(name="予約台帳", type="csv", description="予約の一覧")
        html = str(render_note(_note(sources=(source,))))

        for cell in ("予約台帳", "csv", "予約の一覧"):
            assert f"<td>{cell}</td>" in html

    def test_no_source_says_none(self) -> None:
        html = str(render_note(_note()))

        assert "データソースは宣言していない。" in html


class TestStatusBlock:
    def test_it_shows_the_status_the_last_event_time_and_that_a_verdict_exists(
        self,
    ) -> None:
        note = _note(
            events=(
                _event("E01", "observe", "a", at="2026-11-02T10:00:00+09:00"),
                _event("E02", "observe", "b", at="2026-11-03T11:30:00+09:00"),
            ),
            metrics=(),
        )

        html = _section_of(str(render_note(note)), "status")

        assert "状態: 分析中（analyzing）" in html
        assert "2026-11-03T11:30:00+09:00" in html
        assert "2026-11-02T10:00:00+09:00" not in html
        assert "notebook の結果（verdict）: あり" in html

    def test_a_design_without_journal_or_verdict_says_so(self) -> None:
        html = str(render_note(_note()))

        assert "journal にまだ出来事が無い。" in html
        assert "notebook の結果（verdict）: まだ無い" in html

    def test_it_lists_in_page_anchors_to_the_sections(self) -> None:
        html = str(render_note(_note()))

        for name in ("hypothesis", "method", "results"):
            assert f'href="#note-LIB-H01-{name}"' in html


class TestResults:
    def test_an_unrun_design_says_the_notebook_has_not_been_run(self) -> None:
        html = str(render_note(_note()))

        assert "notebook をまだ実行していない（verdict が無い）。" in html
        assert "journal に観察も証拠もまだ記録されていない。" in html
        assert "図はまだ無い。" in html

    def test_a_design_with_a_verdict_does_not_say_it_has_not_been_run(self) -> None:
        html = str(render_note(_note(metrics=(_metric(),))))

        assert "まだ実行していない" not in html

    def test_observations_keep_journal_order_and_content(self) -> None:
        events = (
            _event("E01", "observe", "最初の観察"),
            _event("E02", "observe", "次の観察 34.6%"),
        )

        html = str(render_note(_note(events=events)))

        assert html.index("最初の観察") < html.index("次の観察 34.6%")
        assert "journal に観察も証拠もまだ記録されていない。" not in html

    def test_evidence_is_grouped_by_direction(self) -> None:
        events = (
            _event("E01", "evidence", "支持その1", "supports"),
            _event("E02", "evidence", "反対その1", "contradicts"),
            _event("E03", "evidence", "向き無しその1", None),
            _event("E04", "evidence", "向きが変なもの", "sideways"),
            _event("E05", "evidence", "支持その2", "supports"),
        )

        html = str(render_note(_note(events=events)))

        support = html.index("検証仮説を支持する証拠")
        against = html.index("検証仮説に反する証拠")
        neutral = html.index("向きの無い証拠")
        assert support < against < neutral
        assert support < html.index("支持その1") < html.index("支持その2") < against
        assert against < html.index("反対その1") < neutral
        assert html.index("向き無しその1") > neutral
        assert html.index("向きが変なもの") > neutral

    def test_an_empty_evidence_group_is_left_out(self) -> None:
        events = (_event("E01", "evidence", "支持だけ", "supports"),)

        html = str(render_note(_note(events=events)))

        assert "仮説を支持する証拠" in html
        assert "仮説に反する証拠" not in html
        assert "向きの無い証拠" not in html

    def test_other_event_types_are_not_listed_in_results(self) -> None:
        events = (_event("E01", "question", "未解決の問い"),)

        html = _section_of(str(render_note(_note(events=events))), "results")

        assert "未解決の問い" not in html
        assert "journal に観察も証拠もまだ記録されていない。" in html

    def test_metric_values_are_printed_as_literal_text(self) -> None:
        metric = _metric(
            value="0.00010",
            threshold="0.050",
            p="1e-05",
            passed=True,
            sample_size="1520",
        )

        html = str(render_note(_note(metrics=(metric,))))

        for cell in ("0.00010", "0.050", "1e-05", "1520", "✓"):
            assert f"<td>{cell}</td>" in html

    def test_effect_size_and_interval_are_formatted_with_their_labels(self) -> None:
        metric = _metric(
            effect_size=("cohens_d", "0.30"),
            interval=ValueInterval(CONFIDENCE, "0.95", "0.10", "0.50"),
        )

        html = str(render_note(_note(metrics=(metric,))))

        assert "<td>0.30（cohens_d）</td>" in html
        assert "<td>水準 0.95: [0.10, 0.50]</td>" in html

    def test_an_interval_of_another_kind_is_not_called_a_confidence_interval(
        self,
    ) -> None:
        """Until Story 33.2 names the kind, an HDI stays out of the 信頼区間 column."""
        metric = _metric(interval=ValueInterval("hdi", "0.95", "0.10", "0.50"))

        html = str(render_note(_note(metrics=(metric,))))

        assert "水準 0.95" not in html

    def test_a_missing_item_is_a_dash_and_a_failed_metric_is_a_cross(self) -> None:
        metric = _metric(passed=False)

        html = str(render_note(_note(metrics=(metric,))))

        assert "<td>✗</td>" in html
        assert html.count("<td>—</td>") == 5

    def test_a_metric_with_no_pass_verdict_is_a_dash(self) -> None:
        html = str(render_note(_note(metrics=(_metric(passed=None),))))

        assert "<td>✓</td>" not in html
        assert "<td>✗</td>" not in html

    def test_a_verdict_without_metric_values_says_so(self) -> None:
        html = str(render_note(_note(metrics=())))

        assert "verdict に指標の値は無い。" in html
        assert "まだ実行していない" not in html

    def test_figures_are_embedded_in_order_with_their_captions(self) -> None:
        figures = (
            NoteFigure(
                file="a.png",
                title="図の題その1",
                axes="x=週",
                how_to_read="右上がりを見る",
                png=PNG,
            ),
            NoteFigure(
                file="b.png",
                title="図の題その2",
                axes="x=支店",
                how_to_read="差を見る",
                png=b"two",
            ),
        )

        html = str(render_note(_note(figures=figures)))

        first = f'src="data:image/png;base64,{base64.b64encode(PNG).decode()}"'
        second = f'src="data:image/png;base64,{base64.b64encode(b"two").decode()}"'
        assert html.index(first) < html.index("図の題その1") < html.index(second)
        assert html.index(second) < html.index("図の題その2")
        assert 'alt="図 1"' in html
        assert 'alt="図 2"' in html
        assert "軸の説明: x=週" in html
        assert "図の読み方: 右上がりを見る" in html
        assert "図はまだ無い。" not in html


class TestSafety:
    def _evil_note(self) -> DesignNote:
        return _note(
            design=_design(title=EVIL, hypothesis_statement=EVIL),
            sources=(NoteSource(name=EVIL, type=EVIL, description=EVIL),),
            events=(
                _event("E01", "observe", EVIL),
                _event("E02", "evidence", EVIL, "supports"),
            ),
            metrics=(_metric(name=EVIL, value=EVIL),),
            figures=(
                NoteFigure(
                    file="f.png", title=EVIL, axes=EVIL, how_to_read=EVIL, png=PNG
                ),
            ),
        )

    def test_text_from_the_design_journal_verdict_and_catalog_is_escaped(self) -> None:
        html = render_note_page(self._evil_note())

        assert "<script" not in html
        assert "alert(1)" in html  # shown as text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;&quot;" in html

    def test_the_page_loads_nothing_from_outside(self) -> None:
        figures = (
            NoteFigure(file="f.png", title="t", axes="a", how_to_read="h", png=PNG),
        )

        html = render_note_page(_note(figures=figures))

        assert "http://" not in html
        assert "https://" not in html
        sources = re.findall(r'src="([^"]*)"', html)
        assert sources
        assert all(src.startswith("data:image/png;base64,") for src in sources)
        assert "<link" not in html
        assert "<script" not in html

    def test_render_note_is_a_fragment_to_embed(self) -> None:
        html = str(render_note(_note()))

        for tag in ("<html", "<head", "<style", "<body"):
            assert tag not in html

    def test_every_id_inside_the_note_starts_with_the_note_anchor(self) -> None:
        events = (
            _event("E01", "observe", "o"),
            _event("E02", "evidence", "e", "supports"),
        )
        figures = (
            NoteFigure(file="f.png", title="t", axes="a", how_to_read="h", png=PNG),
        )
        html = str(
            render_note(
                _note(
                    design=_rich_design(),
                    events=events,
                    metrics=(_metric(),),
                    figures=figures,
                )
            )
        )

        ids = re.findall(r'\bid="([^"]*)"', html)
        assert ids
        assert all(i.startswith("note-LIB-H01") for i in ids)
        hrefs = re.findall(r'href="#([^"]*)"', html)
        assert all(h in ids for h in hrefs)

    def test_the_standalone_page_wraps_the_note_with_its_own_css(self) -> None:
        html = render_note_page(_note())

        assert html.startswith('<!doctype html>\n<html lang="ja">')
        assert "<title>分析ノート LIB-H01</title>" in html
        assert "overflow-x: auto" in html
        assert "max-width: 100%" in html
        assert str(render_note(_note())) in html

    def test_the_same_note_gives_the_same_page(self) -> None:
        note = _note(design=_rich_design(), metrics=(_metric(),))

        assert render_note_page(note) == render_note_page(note)

    def test_the_page_carries_no_date_the_inputs_did_not_give(self) -> None:
        html = render_note_page(_note())

        assert not re.search(r"\d{4}-\d{2}-\d{2}", html)


def test_a_metric_without_effect_size_or_interval_shows_no_label_for_them() -> None:
    html = _section_of(str(render_note(_note(metrics=(_metric(),)))), "results")

    assert "（" not in html.split("指標の値")[1]
    assert "水準" not in html


def _section_of(html: str, name: str) -> str:
    """The markup of the note section *name*, up to the next section."""
    start = _position(html, f'id="note-LIB-H01-{name}"')
    end = html.find("<section", start)
    return html[start:] if end < 0 else html[start:end]


CELLS = (
    CodeCell(position=1, name="imports", source="import pandas as pd\n\nimport numpy"),
    CodeCell(position=3, name="data_prep", source="df_clean = raw_df.dropna()"),
)


class TestCode:
    def test_each_cell_is_folded_with_its_position_name_and_source_as_written(
        self,
    ) -> None:
        html = _section_of(str(render_note(_note(cells=CELLS))), "code")

        assert html.count("<details>") == 2
        assert "<summary>cell 1 · imports</summary>" in html
        assert "<summary>cell 3 · data_prep</summary>" in html
        assert "<pre><code>import pandas as pd\n\nimport numpy</code></pre>" in html
        assert _position(html, "cell 1") < _position(html, "cell 3")

    def test_a_cell_without_a_name_shows_its_position_alone(self) -> None:
        cells = (CodeCell(position=2, name="", source="x = 1"),)

        html = _section_of(str(render_note(_note(cells=cells))), "code")

        assert "<summary>cell 2</summary>" in html

    def test_the_name_of_a_cell_is_escaped(self) -> None:
        cells = (CodeCell(position=2, name="<b>x</b>", source="x = 1"),)

        html = _section_of(str(render_note(_note(cells=cells))), "code")

        assert "<summary>cell 2 · &lt;b&gt;x&lt;/b&gt;</summary>" in html

    def test_it_says_the_data_load_cell_is_left_out_and_read_in_the_local_file(
        self,
    ) -> None:
        html = _section_of(str(render_note(_note(cells=CELLS))), "code")

        assert "データ取得の cell は載せない" in html
        assert "手元の notebook の .py で読む" in html

    def test_a_notebook_not_in_the_contract_shape_shows_no_code(self) -> None:
        html = _section_of(
            str(render_note(_note(cells=None, local_files=("notebooks/LIB-H01.py",)))),
            "code",
        )

        assert "<pre" not in html
        assert "<details" not in html
        assert "契約の形でなく、データ取得の cell を特定できない" in html
        assert "/analysis-notebook で作り直すと載る" in html
        assert "手元の notebook の .py で読む" in html

    def test_a_design_without_a_notebook_says_there_is_none_yet(self) -> None:
        html = _section_of(str(render_note(_note())), "code")

        assert "notebook の .py はまだ無い。" in html
        assert "<pre" not in html


class TestLineage:
    def test_the_mermaid_text_is_folded_as_text_not_drawn(self) -> None:
        text = "flowchart TD\n    A[raw_df 1520 rows] --> B[df_clean]"

        html = _section_of(str(render_note(_note(lineage=text))), "lineage")

        assert "<details>" in html
        assert (
            "<pre><code>flowchart TD\n    A[raw_df 1520 rows] --&gt; B[df_clean]"
            "</code></pre>"
        ) in html
        assert 'class="mermaid"' not in html

    def test_a_design_without_lineage_says_there_is_none_yet(self) -> None:
        html = _section_of(str(render_note(_note())), "lineage")

        assert "lineage はまだ無い。" in html
        assert "<pre" not in html


EVENTS = (
    _event("LIB-H01-E01", "observe", "1520 件", at="2026-11-01T10:00:00+09:00"),
    _event("LIB-H01-E02", "evidence", "差が出た", "supports", at="2026-11-02T10:00:00"),
    _event("LIB-H01-E03", "question", "季節は?", at="2026-11-03T10:00:00+09:00"),
    _event("LIB-H01-E04", "hearing", "窓口に聞いた", at="2026-11-04T10:00:00+09:00"),
    _event("LIB-H01-E05", "custom", "手で書いた", at=""),
)


class TestProgress:
    def test_it_opens_with_what_the_section_records(self) -> None:
        html = _section_of(str(render_note(_note())), "progress")

        assert "分析中の判断と解釈の記録である" in html

    def test_it_shows_the_verdict_conclusion_as_written(self) -> None:
        html = _section_of(
            str(render_note(_note(verdict_conclusion="期限切れは減った"))), "progress"
        )

        assert "notebook の結論（verdict の conclusion）: 期限切れは減った" in html

    def test_a_verdict_without_a_conclusion_says_so(self) -> None:
        html = _section_of(str(render_note(_note(metrics=()))), "progress")

        assert "verdict に conclusion は無い。" in html

    def test_an_unrun_design_says_there_is_no_verdict_conclusion(self) -> None:
        html = _section_of(str(render_note(_note())), "progress")

        assert "notebook をまだ実行していない" in html
        assert "verdict の conclusion）:" not in html

    def test_every_event_is_folded_in_journal_order_with_its_kind_word(
        self,
    ) -> None:
        html = _section_of(str(render_note(_note(events=EVENTS))), "progress")

        assert "<details>" in html
        assert "<summary>journal のすべての出来事（5 件）</summary>" in html
        markers = [
            "2026-11-01T10:00:00+09:00 観察 LIB-H01-E01",
            "2026-11-02T10:00:00 証拠 LIB-H01-E02",
            "2026-11-03T10:00:00+09:00 問い LIB-H01-E03",
            "2026-11-04T10:00:00+09:00 人に聞いた答え LIB-H01-E04",
            "（時刻の記載なし） custom LIB-H01-E05",
        ]
        positions = [_position(html, m) for m in markers]
        assert positions == sorted(positions)
        for content in ("1520 件", "差が出た", "季節は?", "窓口に聞いた", "手で書いた"):
            assert content in html

    def test_no_event_says_the_journal_is_empty(self) -> None:
        html = _section_of(str(render_note(_note())), "progress")

        assert "journal にまだ出来事が無い。" in html
        assert "<details" not in html


class TestLocalFiles:
    def test_it_links_the_files_that_exist_relative_to_the_note(self) -> None:
        files = (
            "notebooks/LIB-H01.py",
            "notebooks/LIB-H01_verdict.json",
            "lineage/LIB-H01.mmd",
            "notebooks/LIB-H01.html",
        )

        html = _section_of(str(render_note(_note(local_files=files))), "files")

        hrefs = re.findall(r'href="([^"]*)"', html)
        assert hrefs == [f"../{f}" for f in files]
        for label in (
            "notebook の .py",
            "verdict",
            "lineage",
            "notebook の HTML",
        ):
            assert label in html

    def test_it_says_the_links_open_only_on_the_local_machine(self) -> None:
        html = _section_of(
            str(render_note(_note(local_files=("notebooks/LIB-H01.py",)))), "files"
        )

        assert "手元で開いたときだけ開ける" in html

    def test_no_local_file_says_there_is_none_yet(self) -> None:
        html = _section_of(str(render_note(_note())), "files")

        assert "手元のファイルはまだ無い。" in html
        assert "href" not in html


def test_code_lineage_verdict_conclusion_and_journal_text_are_escaped() -> None:
    note = _note(
        cells=(CodeCell(position=1, name=EVIL, source=EVIL),),
        lineage=EVIL,
        verdict_conclusion=EVIL,
        events=(_event("E01", EVIL, EVIL),),
    )

    html = render_note_page(note)

    assert "<script" not in html
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;&quot;") >= 5


def test_the_status_block_links_to_the_new_sections() -> None:
    html = _section_of(str(render_note(_note())), "status")

    for name in ("code", "lineage", "progress", "files"):
        assert f'href="#note-LIB-H01-{name}"' in html


def _conclusion(**over: object) -> Conclusion:
    fields: dict = {
        "status": DesignStatus.supported,
        "conclude_events": (),
        "next_action": (),
        "contradicting_evidence": (),
        "reflect_events": (),
        "open_questions": (),
    }
    fields.update(over)
    return Conclusion(**fields)


def _concluded(
    conclusion: Conclusion, design: AnalysisDesign | None = None
) -> DesignNote:
    """A note in the conclusion's status."""
    design = design or _design()
    return _note(
        design=design.model_copy(update={"status": conclusion.status}),
        conclusion=conclusion,
    )


def _texts(markup: str) -> list[str]:
    """The text runs between tags, stripped; empty runs dropped."""
    return [t.strip() for t in re.findall(r">([^<]+)<", markup) if t.strip()]


FULL = _conclusion(
    conclude_events=(_event("LIB-H01-E05", "conclude", "期限切れは減った"),),
    next_action=(("if_supported", "全館で延長を試す"),),
    contradicting_evidence=(
        _event("LIB-H01-E02", "evidence", "雨の週は増えた", "contradicts"),
    ),
    reflect_events=(_event("LIB-H01-E06", "reflect", "季節を見ていない"),),
    open_questions=(_event("LIB-H01-E03", "question", "冬も同じか"),),
)


class TestConclusion:
    @pytest.mark.parametrize(
        ("status", "lead"),
        [
            (DesignStatus.supported, "検証仮説は支持された。"),
            (DesignStatus.rejected, "検証仮説は棄却された。"),
            (
                DesignStatus.inconclusive,
                "検証仮説を支持するとも棄却するとも結論できなかった。",
            ),
        ],
    )
    def test_the_section_opens_with_the_fixed_sentence_of_the_status(
        self, status: DesignStatus, lead: str
    ) -> None:
        html = _section_of(
            str(render_note(_concluded(_conclusion(status=status)))), "conclusion"
        )

        assert _texts(html)[:2] == ["結論", lead]

    def test_it_comes_after_the_results_and_before_the_code(self) -> None:
        html = str(render_note(_concluded(FULL)))

        results = _position(html, 'id="note-LIB-H01-results"')
        conclusion = _position(html, 'id="note-LIB-H01-conclusion"')
        assert results < conclusion < _position(html, 'id="note-LIB-H01-code"')

    def test_it_shows_each_record_as_written(self) -> None:
        html = _section_of(str(render_note(_concluded(FULL))), "conclusion")

        for text in (
            "期限切れは減った",
            "全館で延長を試す",
            "雨の週は増えた",
            "季節を見ていない",
            "冬も同じか",
        ):
            assert text in html
        for heading in (
            "conclude の本文",
            "勧めの元",
            "検証仮説に反する証拠",
            "reflect の本文",
            "未解決の問い",
        ):
            assert f"<h4>{heading}</h4>" in html

    def test_the_recommendation_sources_are_the_decision_context_and_the_branch(
        self,
    ) -> None:
        note = _concluded(
            _conclusion(
                status=DesignStatus.rejected,
                next_action=(
                    ("if_rejected.reason", "差が無い"),
                    ("if_rejected.pivot", "督促の時期を変える"),
                ),
            ),
            _rich_design(),
        )

        html = _section_of(str(render_note(note)), "conclusion")

        assert "決める人: 図書館員" in html
        assert "決めること: 延長を試すか" in html
        assert "next_action の if_rejected.reason: 差が無い" in html
        assert "next_action の if_rejected.pivot: 督促の時期を変える" in html

    def test_a_missing_record_is_left_out(self) -> None:
        html = _section_of(str(render_note(_concluded(_conclusion()))), "conclusion")

        assert "<h4>" not in html
        assert _texts(html)[:2] == ["結論", "検証仮説は支持された。"]

    def test_only_records_and_fixed_labels_appear(self) -> None:
        html = _section_of(str(render_note(_concluded(FULL))), "conclusion")
        events = (
            *FULL.conclude_events,
            *FULL.contradicting_evidence,
            *FULL.reflect_events,
            *FULL.open_questions,
        )
        records = {e.content for e in events} | {e.id for e in events}
        labels = {
            "結論",
            "検証仮説は支持された。",
            "この節は journal と分析設計の記録を書かれたとおりに写す。"
            "conclude と reflect の本文は「分析の経過」にも在る。",
            "conclude の本文",
            "勧めの元",
            "next_action の if_supported: 全館で延長を試す",
            "検証仮説に反する証拠",
            "reflect の本文",
            "未解決の問い",
        }

        assert set(_texts(html)) <= records | labels

    def test_the_status_block_links_to_the_section(self) -> None:
        html = _section_of(str(render_note(_concluded(FULL))), "status")

        assert 'href="#note-LIB-H01-conclusion"' in html
        assert "結論はまだ出ていない" not in html

    def test_a_design_without_a_conclusion_has_no_section(self) -> None:
        html = str(render_note(_note()))

        assert 'id="note-LIB-H01-conclusion"' not in html
        assert "#note-LIB-H01-conclusion" not in html
        assert "結論はまだ出ていない（分析設計が terminal status でない）。" in (
            _section_of(html, "status")
        )

    def test_its_text_is_escaped(self) -> None:
        evil = _event(EVIL, "conclude", EVIL)
        note = _concluded(
            _conclusion(
                conclude_events=(evil,),
                next_action=(("if_supported", EVIL),),
                contradicting_evidence=(evil,),
                reflect_events=(evil,),
                open_questions=(evil,),
            )
        )

        html = _section_of(render_note_page(note), "conclusion")

        assert "<script" not in html
        assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;&quot;") >= 9


# Story 32.5 (Epic 32 US-5): the note words an exploration, a confirmation and a
# legacy exploration apart, so an exploration never reads as a verdict (ADR-0051).

QUESTION_TEXT = "取り置きの期限切れは、どの館で多いか"
QUESTION_BACKGROUND = "館ごとの差をまだ見ていない"


def _exploration(**over: object) -> AnalysisDesign:
    fields: dict = {
        "analysis_intent": "exploratory",
        "exploration_question": QUESTION_TEXT,
        "exploration_background": QUESTION_BACKGROUND,
        "hypothesis_statement": None,
        "hypothesis_background": None,
    }
    fields.update(over)
    return _design(**fields)


def _legacy(**over: object) -> AnalysisDesign:
    return _design(analysis_intent="exploratory", **over)


# Words that judge a hypothesis; an exploration's note holds none of them.
VERDICT_WORDS = ("仮説", "支持", "棄却", "合否", "しきい値", "判定:")


def _explored(design: AnalysisDesign | None = None, **over: object) -> DesignNote:
    return _concluded(
        _conclusion(status=DesignStatus.explored, **over), design or _exploration()
    )


def _without_lead(html: str) -> str:
    """*html* without the one sentence that says no verdict was made."""
    return html.replace("探索を終えた。判定はしていない。", "")


class TestOpeningSectionByForm:
    def test_an_exploration_opens_with_its_question_and_background(self) -> None:
        html = _section_of(str(render_note(_note(design=_exploration()))), "hypothesis")

        assert _texts(html) == ["探索の問いと背景", QUESTION_TEXT, QUESTION_BACKGROUND]

    def test_a_confirmation_opens_with_its_hypothesis_and_background(self) -> None:
        html = _section_of(str(render_note(_note())), "hypothesis")

        assert _texts(html) == [
            "検証仮説と背景",
            "期限を延ばすと期限切れが減る",
            "取り置き7日で期限切れが多い",
        ]

    def test_a_legacy_exploration_opens_with_its_hypothesis_as_written(self) -> None:
        html = _section_of(str(render_note(_note(design=_legacy()))), "hypothesis")

        assert _texts(html)[:2] == ["仮説と背景", "期限を延ばすと期限切れが減る"]

    def test_the_status_block_links_the_opening_section_by_its_heading(self) -> None:
        html = _section_of(str(render_note(_note(design=_exploration()))), "status")

        assert '<a href="#note-LIB-H01-hypothesis">探索の問いと背景</a>' in html

    def test_the_question_of_an_exploration_is_escaped(self) -> None:
        html = str(render_note(_note(design=_exploration(exploration_question=EVIL))))

        assert "<script" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;&quot;" in html


class TestEvidenceByForm:
    EVENTS = (
        _event("E01", "evidence", "本館で多い"),
        _event("E02", "evidence", "分館で少ない", "contradicts"),
    )

    def test_an_exploration_shows_its_evidence_as_one_group(self) -> None:
        html = _section_of(
            str(render_note(_note(design=_exploration(), events=self.EVENTS))),
            "results",
        )

        assert "<h4>証拠</h4>" in html
        assert html.index("本館で多い") < html.index("分館で少ない")
        for word in VERDICT_WORDS:
            assert word not in html

    def test_a_confirmation_splits_its_evidence_by_the_hypothesis(self) -> None:
        events = (
            _event("E01", "evidence", "支持", "supports"),
            _event("E02", "evidence", "反対", "contradicts"),
        )

        html = str(render_note(_note(events=events)))

        assert "<h4>検証仮説を支持する証拠</h4>" in html
        assert "<h4>検証仮説に反する証拠</h4>" in html

    def test_a_legacy_exploration_keeps_the_old_headings(self) -> None:
        events = (
            _event("E01", "evidence", "支持", "supports"),
            _event("E02", "evidence", "反対", "contradicts"),
        )

        html = str(render_note(_note(design=_legacy(), events=events)))

        assert "<h4>仮説を支持する証拠</h4>" in html
        assert "<h4>仮説に反する証拠</h4>" in html
        assert "検証仮説" not in html


class TestMetricValuesByForm:
    def test_an_exploration_shows_measured_values_without_threshold_or_pass(
        self,
    ) -> None:
        metric = _metric(value="0.346", p="0.01", threshold="0.05", passed=True)

        html = str(render_note(_note(design=_exploration(), metrics=(metric,))))

        assert "<td>0.346</td>" in html
        assert "<td>0.01</td>" in html
        assert "しきい値" not in html
        assert "合否" not in html
        assert "<td>0.05</td>" not in html
        assert "✓" not in html

    def test_a_confirmation_keeps_threshold_and_pass(self) -> None:
        metric = _metric(threshold="0.05", passed=True)

        html = str(render_note(_note(metrics=(metric,))))

        assert "<th>しきい値</th>" in html
        assert "<th>合否</th>" in html


class TestConclusionByForm:
    def test_an_exploration_concludes_without_a_verdict(self) -> None:
        html = _section_of(
            str(
                render_note(
                    _explored(
                        conclude_events=(_event("E05", "conclude", "本館が多かった"),),
                        contradicting_evidence=(
                            _event("E02", "evidence", "分館は少ない", "contradicts"),
                        ),
                    )
                )
            ),
            "conclusion",
        )

        assert _texts(html)[:2] == ["結論", "探索を終えた。判定はしていない。"]
        assert "本館が多かった" in html
        for word in VERDICT_WORDS:
            assert word not in _without_lead(html)

    @pytest.mark.parametrize(
        ("status", "lead"),
        [
            (DesignStatus.supported, "仮説は支持された。"),
            (DesignStatus.rejected, "仮説は棄却された。"),
            (
                DesignStatus.inconclusive,
                "仮説を支持するとも棄却するとも結論できなかった。",
            ),
        ],
    )
    def test_a_legacy_exploration_keeps_the_old_sentence(
        self, status: DesignStatus, lead: str
    ) -> None:
        html = _section_of(
            str(render_note(_concluded(_conclusion(status=status), _legacy()))),
            "conclusion",
        )

        assert _texts(html)[:2] == ["結論", lead]

    def test_a_confirmation_names_the_evidence_against_its_hypothesis(self) -> None:
        html = _section_of(str(render_note(_concluded(FULL))), "conclusion")

        assert "<h4>検証仮説に反する証拠</h4>" in html


class TestStatusByForm:
    def test_an_exploration_shows_its_intent_and_state_in_words(self) -> None:
        html = _section_of(str(render_note(_explored())), "status")

        assert "意図: 探索" in html
        assert "状態: 探索済み（判定はしない）（explored）" in html

    def test_a_confirmation_shows_its_verdict_with_the_hypothesis_word(self) -> None:
        html = _section_of(
            str(render_note(_concluded(_conclusion(status=DesignStatus.rejected)))),
            "status",
        )

        assert "意図: 検証" in html
        assert "状態: 検証仮説の判定: 棄却（rejected）" in html

    def test_a_legacy_exploration_is_marked_as_such(self) -> None:
        html = _section_of(str(render_note(_note(design=_legacy()))), "status")

        assert "意図: 探索（旧形式）" in html
        assert "旧形式の探索: 探索の分析設計に、仮説と判定が書かれている。" in html

    def test_a_saved_mixed_design_reads_as_a_confirmation_marked_legacy(
        self,
    ) -> None:
        html = _section_of(
            str(render_note(_note(design=_design(analysis_intent="mixed")))), "status"
        )

        assert "意図: 探索と検証（旧形式）" in html

    def test_only_a_legacy_exploration_carries_the_legacy_note(self) -> None:
        for design in (_design(), _exploration()):
            assert "旧形式の探索:" not in str(render_note(_note(design=design)))

    def test_an_exploration_note_has_no_verdict_word_anywhere(self) -> None:
        note = _explored(
            conclude_events=(_event("E05", "conclude", "本館が多かった"),),
        )
        note = DesignNote(
            **{
                **note.__dict__,
                "events": (
                    _event("E01", "evidence", "本館で多い"),
                    _event("E05", "conclude", "本館が多かった"),
                ),
                "verdict": NoteVerdict(metrics=(_metric(),), conclusion=None),
            }
        )

        html = _without_lead(str(render_note(note)))

        for word in VERDICT_WORDS:
            assert word not in html, word
