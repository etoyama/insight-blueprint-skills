"""Tests of skills/_shared/design_note.py (Epic 28, Stories 28.1 and 28.2): the analysis note page."""

from __future__ import annotations

import base64
import re

from insight_blueprint.models.design import AnalysisDesign
from skills._shared.design_note import (
    CodeCell,
    DesignNote,
    NoteEvent,
    NoteFigure,
    NoteSource,
    NoteVerdict,
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
    """A note; ``metrics`` or ``conclusion`` stands for a verdict that holds them."""
    fields: dict = {
        "design": _design(),
        "sources": (),
        "events": (),
        "verdict": None,
        "figures": (),
        "cells": None,
        "lineage": None,
        "local_files": (),
    }
    if "metrics" in over or "conclusion" in over:
        fields["verdict"] = NoteVerdict(
            metrics=over.pop("metrics", ()),  # type: ignore[arg-type]
            conclusion=over.pop("conclusion", None),  # type: ignore[arg-type]
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
        "confidence_interval": None,
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

        assert "状態: analyzing" in html
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

        support = html.index("仮説を支持する証拠")
        against = html.index("仮説に反する証拠")
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
            confidence_interval=("0.95", "0.10", "0.50"),
        )

        html = str(render_note(_note(metrics=(metric,))))

        assert "<td>0.30（cohens_d）</td>" in html
        assert "<td>水準 0.95: [0.10, 0.50]</td>" in html

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
                title="図の題その1", axes="x=週", how_to_read="右上がりを見る", png=PNG
            ),
            NoteFigure(
                title="図の題その2", axes="x=支店", how_to_read="差を見る", png=b"two"
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
            figures=(NoteFigure(title=EVIL, axes=EVIL, how_to_read=EVIL, png=PNG),),
        )

    def test_text_from_the_design_journal_verdict_and_catalog_is_escaped(self) -> None:
        html = render_note_page(self._evil_note())

        assert "<script" not in html
        assert "alert(1)" in html  # shown as text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;&quot;" in html

    def test_the_page_loads_nothing_from_outside(self) -> None:
        figures = (NoteFigure(title="t", axes="a", how_to_read="h", png=PNG),)

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
        figures = (NoteFigure(title="t", axes="a", how_to_read="h", png=PNG),)
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
    CodeCell(position=1, source="@app.cell\ndef _():\n    import pandas as pd"),
    CodeCell(position=3, source="@app.cell\ndef _(raw_df):\n    df = raw_df"),
)


class TestCode:
    def test_each_cell_is_folded_with_its_position_and_source_as_written(
        self,
    ) -> None:
        html = _section_of(str(render_note(_note(cells=CELLS))), "code")

        assert html.count("<details>") == 2
        assert "<summary>cell 1</summary>" in html
        assert "<summary>cell 3</summary>" in html
        assert (
            "<pre><code>@app.cell\ndef _():\n    import pandas as pd</code></pre>"
            in (html)
        )
        assert _position(html, "cell 1") < _position(html, "cell 3")

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
            str(render_note(_note(conclusion="期限切れは減った"))), "progress"
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
            "reports/LIB-H01.md",
        )

        html = _section_of(str(render_note(_note(local_files=files))), "files")

        hrefs = re.findall(r'href="([^"]*)"', html)
        assert hrefs == [f"../{f}" for f in files]
        for label in (
            "notebook の .py",
            "verdict",
            "lineage",
            "notebook の HTML",
            "レポート",
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


def test_code_lineage_and_conclusion_text_is_escaped() -> None:
    note = _note(
        cells=(CodeCell(position=1, source=EVIL),),
        lineage=EVIL,
        conclusion=EVIL,
        events=(_event("E01", EVIL, EVIL),),
    )

    html = render_note_page(note)

    assert "<script" not in html
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;&quot;") >= 5


def test_the_status_block_links_to_the_new_sections() -> None:
    html = _section_of(str(render_note(_note())), "status")

    for name in ("code", "lineage", "progress", "files"):
        assert f'href="#note-LIB-H01-{name}"' in html
