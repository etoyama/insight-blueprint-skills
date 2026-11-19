"""Unit tests for skills/_shared/report_check.py (Epic 13, Story 85).

report_check reads a finished report and lists what would still be active markup:
an image that is not a figure, a tag start, and, in a mermaid fence, a tag other
than <br/> or a line the lineage export never writes. It never rewrites the report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from insight_blueprint.lineage.exporter import export_lineage_as_mermaid
from insight_blueprint.lineage.tracker import LineageSession, StepRecord
from skills._shared import report_check
from skills._shared.report_check import find_violations

FIGURE = "![Figure 1](../notebooks/FP-H01_fig01.png)"


def _kinds(markdown: str) -> list[str]:
    return [v.kind for v in find_violations(markdown)]


def _lines_and_kinds(markdown: str) -> list[tuple[int, str]]:
    return [(v.line, v.kind) for v in find_violations(markdown)]


# --- images -----------------------------------------------------------------


def test_figure_pointing_into_notebooks_is_not_a_violation() -> None:
    assert find_violations(FIGURE) == []


@pytest.mark.parametrize(
    "construct",
    [
        "![x](http://evil.example/a.png)",
        "![x](/etc/passwd.png)",
        "![x](../other/a.png)",
        "![x](../notebooks/sub/a.png)",
        "![x](../notebooks/../a.png)",
        "![x](../notebooks/a.jpg)",
        "![x][ref]",
        "![x](../notebooks/a.png",
    ],
)
def test_image_that_is_not_a_figure_is_a_violation(construct: str) -> None:
    assert _lines_and_kinds(f"see {construct}") == [(1, "image")]


@pytest.mark.parametrize(
    "file",
    ["%2e%2e%2fsecret.png", "a%20b.png", "a b.png", "図.png", "a..b.png"],
)
def test_figure_file_outside_the_plain_charset_is_a_violation(file: str) -> None:
    assert _kinds(f"![Figure 1](../notebooks/{file})") == ["image"]


def test_image_violation_text_is_the_whole_construct() -> None:
    [v] = find_violations("before ![x](http://e/a.png) after")
    assert v.text == "![x](http://e/a.png)"


def test_unclosed_image_text_runs_to_the_end_of_the_line() -> None:
    [v] = find_violations("![x](http://e/a.png and more")
    assert v.text == "![x](http://e/a.png and more"


def test_escaped_brackets_in_a_figure_alt_are_allowed() -> None:
    assert find_violations(r"![a \[b\]](../notebooks/f.png)") == []


def test_tag_in_a_figure_alt_is_a_violation() -> None:
    assert _kinds("![<b>](../notebooks/f.png)") == ["html"]


# --- tag starts -------------------------------------------------------------


@pytest.mark.parametrize(
    "markup",
    [
        "<img src=x>",
        "<b>",
        "<br/>",
        "<div class='a'>",
        "</div>",
        "<!-- hidden -->",
        "<!DOCTYPE html>",
        "<?php echo 1 ?>",
        "<![CDATA[x]]>",
        "<http://example.com>",
        "<mailto:a@b.example>",
        '<a title="x>y" onclick="alert(1)">',
        "<img",
        "</div",
        "a<b",
    ],
)
def test_any_unescaped_tag_start_is_a_violation(markup: str) -> None:
    # Fail closed: a tag grammar that misses one shape lets that shape through.
    assert _kinds(f"text {markup} text") == ["html"]


def test_html_violation_text_runs_to_the_first_closing_bracket() -> None:
    [v] = find_violations("前 <b class=x>太字 後")
    assert v.text == "<b class=x>"


def test_tag_left_open_at_the_end_of_a_line_is_a_violation() -> None:
    # CommonMark lets an inline tag continue on the next line.
    [v] = find_violations("説明 <img\nsrc=x onerror=alert(1)>\n")
    assert (v.line, v.kind, v.text) == (1, "html", "<img")


@pytest.mark.parametrize("indent", ["", " ", "   ", "    "])
def test_tag_start_is_a_violation_at_any_indent(indent: str) -> None:
    assert _kinds(f"{indent}<script src=http://evil.example/x.js") == ["html"]


# --- text that only looks like markup ---------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "x < y and y > z",
        "p<0.05",
        "n <5",
        "a <- b",
        r"\<img src=x>",
        r"\\\<img src=x>",
        "[text](http://example.com)",
        "see http://example.com/a.png",
        r"!\[x\](http://e/a.png)",
        r"\![x](http://e/a.png)",
        r"a \| b",
        "`.insight/notebooks/FP-H01.py`",
    ],
)
def test_text_that_is_not_active_markup_is_not_a_violation(line: str) -> None:
    assert find_violations(line) == []


def test_even_backslashes_do_not_escape_the_next_character() -> None:
    assert _kinds(r"\\<img src=x>") == ["html"]


# --- code spans and other fences are not safe places ------------------------
# A renderer ends them where a line scanner would not, so they are checked as text.


def test_tag_inside_a_code_span_is_a_violation() -> None:
    assert _kinds("`<div>`") == ["html"]


def test_code_span_across_a_table_cell_border_hides_nothing() -> None:
    # GFM splits cells on "|" before it reads code spans.
    table = "| a | b |\n|---|---|\n| `x | <img src=x onerror=alert(1)> | y` |\n"
    assert _lines_and_kinds(table) == [(3, "html")]


@pytest.mark.parametrize(
    "line",
    [
        "[a](`) <img src=x onerror=alert(1)> `",
        "[a](<`>) <img src=x onerror=alert(1)> `",
        '[a](/u "`") <img src=x onerror=alert(1)> `',
        "[a](`) ![x](http://evil.example/t.png) `",
    ],
)
def test_backtick_inside_a_link_destination_hides_nothing(line: str) -> None:
    # CommonMark reads the destination first, so the backtick opens no code span.
    assert len(find_violations(line)) >= 1


def test_fence_other_than_mermaid_hides_nothing() -> None:
    assert _lines_and_kinds(
        "```python\n<div>\n```\n~~~\n![x](http://e/a.png)\n~~~"
    ) == [
        (2, "html"),
        (5, "image"),
    ]


def test_fence_inside_a_list_item_hides_nothing() -> None:
    # The list item, and the fence with it, ends at the next line with less indent.
    markdown = "- a\n  ```\n<img src=x onerror=alert(1)>\n```\n"
    assert _lines_and_kinds(markdown) == [(3, "html")]


# --- mermaid fences ---------------------------------------------------------


def _mermaid(*lines: str) -> str:
    return "```mermaid\n" + "\n".join(lines) + "\n```\n"


@pytest.mark.parametrize("br", ["<br>", "<br/>", "<br />", "<BR/>"])
def test_br_inside_a_mermaid_fence_is_not_a_violation(br: str) -> None:
    assert find_violations(_mermaid(f'    Step0["a{br}b"]')) == []


def test_other_tag_inside_a_mermaid_fence_is_a_mermaid_html_violation() -> None:
    [v] = find_violations(_mermaid('    Step0["<img src=x>"]'))
    assert (v.line, v.kind, v.text) == (2, "mermaid-html", "<img src=x>")


def test_closing_tag_inside_a_mermaid_fence_is_a_violation() -> None:
    assert _kinds('```Mermaid\n    Step0["x</b>"]\n```') == ["mermaid-html"]


def test_tag_left_open_inside_a_mermaid_fence_is_a_violation() -> None:
    assert _lines_and_kinds(_mermaid('    Step0["a <img src=x"]')) == [
        (2, "mermaid-html")
    ]


def test_backslash_escapes_nothing_inside_a_mermaid_fence() -> None:
    # Mermaid reads no Markdown escape, so "\<img>" is still a tag in a label.
    assert _kinds(_mermaid('    Step0["\\<img src=x>"]')) == ["mermaid-html"]


def test_less_than_before_a_digit_in_a_mermaid_label_is_not_a_tag() -> None:
    edge = '    Step0 -->|"x<0.5 を除く<br/>-1 rows"| Step1'
    assert find_violations(_mermaid(edge)) == []


@pytest.mark.parametrize(
    "statement",
    [
        'click Step0 href "http://evil.example"',
        '%%{init: {"securityLevel": "loose"}}%%',
        "    Step0 --> Step1",
        "subgraph x",
        'Step0["a<br/>b"]',
        '  Step0["a<br/>b"]',
    ],
)
def test_mermaid_line_the_lineage_export_never_writes_is_a_violation(
    statement: str,
) -> None:
    markdown = _mermaid("graph LR", '    Step0["a<br/>1 rows"]', statement)
    assert _lines_and_kinds(markdown) == [(4, "mermaid-statement")]


def test_the_shapes_of_the_lineage_export_and_blank_lines_are_not_violations() -> None:
    markdown = _mermaid(
        "graph LR",
        '    Step0["sales<br/>12000 rows"]',
        '    Step1["Step 1<br/>11800 rows"]',
        '    Step0 -->|"欠損を除く &#124; 2025年<br/>-200 rows"| Step1',
        "",
    )
    assert find_violations(markdown) == []


def test_a_diagram_the_lineage_export_writes_is_not_a_violation() -> None:
    # The allowed shapes are the export's output; this ties the two together, so a
    # change to the export that the check does not know fails here.
    session = LineageSession(name='月次 "売上" | 2025\n速報')
    for rows_before, rows_after, reason in (
        (12000, 11800, 'p<0.5 の行を除く\n"外れ値" | 店舗'),
        (11800, 11900, "補完した行を足す"),
    ):
        session.record(
            StepRecord(
                step_number=session.next_step_number(),
                reason=reason,
                rows_before=rows_before,
                rows_after=rows_after,
                rows_delta=rows_after - rows_before,
                timestamp=datetime.now(UTC),
                function_name="fn",
            )
        )
    diagram = export_lineage_as_mermaid(session)

    assert find_violations(f"```mermaid\n{diagram}```\n") == []


def test_mermaid_fence_counts_only_at_the_left_margin() -> None:
    # Indented, it may sit inside a list item, so it is checked as text.
    markdown = '  ```mermaid\n    Step0["a<br/>b"]\n  ```\n'
    assert _kinds(markdown) == ["html"]


def test_mermaid_fence_closes_only_at_the_left_margin() -> None:
    markdown = "```mermaid\ngraph LR\n  ```\n<b>\n"
    assert _lines_and_kinds(markdown) == [
        (3, "mermaid-statement"),
        (4, "mermaid-statement"),
    ]


def test_mermaid_fence_closes_only_on_a_fence_at_least_as_long() -> None:
    markdown = "````mermaid\ngraph LR\n```\n````\n<b>"
    assert _lines_and_kinds(markdown) == [(3, "mermaid-statement"), (5, "html")]


def test_closing_fence_with_an_info_string_does_not_close() -> None:
    markdown = "```mermaid\ngraph LR\n``` text\n```\n"
    assert _lines_and_kinds(markdown) == [(3, "mermaid-statement")]


def test_unclosed_mermaid_fence_keeps_its_rules_to_the_end() -> None:
    assert _lines_and_kinds("```mermaid\ngraph LR\n<b>") == [(3, "mermaid-statement")]


def test_text_after_a_closed_mermaid_fence_is_checked_again() -> None:
    assert _lines_and_kinds(_mermaid("graph LR") + "<b>x") == [(4, "html")]


# --- lines, positions, and text ---------------------------------------------


def test_line_numbers_are_one_based_and_count_every_line() -> None:
    assert [
        v.line for v in find_violations("# Title\n\n" + FIGURE + "\n\nok <b>x")
    ] == [5]


def test_crlf_line_endings_keep_line_numbers() -> None:
    assert [v.line for v in find_violations("a\r\nb\r\n<b>")] == [3]


def test_a_lone_carriage_return_ends_a_line() -> None:
    # CommonMark ends a line at "\r", so the fence closes before "<img".
    markdown = "```mermaid\ngraph LR\n```\r<img src=x>\n"
    assert _lines_and_kinds(markdown) == [(4, "html")]


def test_violations_on_one_line_come_in_reading_order() -> None:
    assert _kinds("<b> ![x](http://e/a.png) <i>") == ["html", "image", "html"]


def test_violation_text_is_cut_to_120_characters() -> None:
    [v] = find_violations("<div " + "a" * 300 + ">")
    assert len(v.text) == 120


# --- a report laid out as the template says ---------------------------------

CLEAN_REPORT = f"""\
# 値引き施策と売上 \\<u>速報\\</u> \\[要確認\\]

## Introduction

この分析は、販売企画部長 \\| 代理: \\*営業\\* 課長 が 値引きを全店舗に広げるか \\<b>否か\\</b> を決めるための材料である。

## Method

### Data

| Data source | Type | Description |
|---|---|---|
| 月次売上 !\\[logo\\](https://evil.example/logo.png) | csv | 列は store\\_id \\| month。\\<script>alert(1)\\</script> |

| Step | Reason | Rows | Change |
|---|---|---|---|
| 0 | (loaded) | 12000 | — |
| 1 | 欠損のある行を除く \\<img src=x> \\*必ず\\* | 11800 | -200 |
| 2 | 対象期間に絞る &#124; 2025年 | 9400 | -2400 |

## Results

| Metric | Value | Effect size | CI | N | Threshold | p | Pass |
|---|---|---|---|---|---|---|---|
| ATT\\_\\[primary\\] | 1676.9 | 0.42 (cohens\\_d \\<i>) | 95% [1200.3, 2153.5] | 1200 | 0 | 0.0001 | ✓ |

**Figure 1.** 施策前後の売上推移 \\`rm -rf\\`

- **Axes（軸の説明）**: 横軸=年月, 縦軸=売上(円) \\| 単位\\_千円
- **How to read（図の読み方）**: 線が上にあるほど売上が高い。!\\[x\\](http://evil.example/a.png) \\<a href="http://evil.example">詳細\\</a>

{FIGURE}

> 図はこのレポートには含まれていない（notebook が図を生成していない）。図を載せるには
> /analysis-notebook で再実行する。

## Discussion

### Recommendation

販売企画部長へ。結論は広げる方向を指している（p < 0.05、Limitations を参照）。

## Appendix

### Data Lineage

```mermaid
graph LR
    Step0["sales<br/>12000 rows"]
    Step1["Step 1<br/>11800 rows"]
    Step0 -->|"欠損のある行を除く<br/>-200 rows"| Step1
```

### Notebook

`.insight/notebooks/SY-H01.py`
"""


def test_a_report_laid_out_as_the_template_says_has_no_violation() -> None:
    assert find_violations(CLEAN_REPORT) == []


# --- CLI --------------------------------------------------------------------


def _write_report(base: Path, design_id: str, text: str) -> Path:
    path = base / "reports" / f"{design_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_main_exits_0_and_prints_no_violations_for_a_clean_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_report(tmp_path, "FP-H01", CLEAN_REPORT)

    code = report_check._main(["--id", "FP-H01", "--base-dir", str(tmp_path)])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {
        "report": str(path),
        "violations": [],
    }


def test_main_exits_1_and_prints_each_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_report(tmp_path, "FP-H01", "ok\n![x](http://e/a.png)\n日本語<b>\n")

    code = report_check._main(["--id", "FP-H01", "--base-dir", str(tmp_path)])

    assert code == 1
    assert json.loads(capsys.readouterr().out) == {
        "report": str(path),
        "violations": [
            {"line": 2, "kind": "image", "text": "![x](http://e/a.png)"},
            {"line": 3, "kind": "html", "text": "<b>"},
        ],
    }


def test_main_keeps_non_ascii_text_unescaped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_report(tmp_path, "X", "![日本語](http://e/a.png)")

    report_check._main(["--id", "X", "--base-dir", str(tmp_path)])

    assert "![日本語](http://e/a.png)" in capsys.readouterr().out


@pytest.mark.parametrize("bad_id", ["../x", "a b", "a/b", "", "ok\n", "a.b"])
def test_main_exits_2_for_an_id_outside_the_safe_pattern(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], bad_id: str
) -> None:
    code = report_check._main(["--id", bad_id, "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "[a-zA-Z0-9_-]+" in captured.err


def test_main_exits_2_when_the_report_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = report_check._main(["--id", "FP-H01", "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "FP-H01.md" in captured.err


def test_main_exits_2_when_the_report_is_not_utf8(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "reports" / "X.md"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe<b>")

    assert report_check._main(["--id", "X", "--base-dir", str(tmp_path)]) == 2
    assert capsys.readouterr().out == ""


def test_main_requires_an_id() -> None:
    with pytest.raises(SystemExit) as exc:
        report_check._main([])
    assert exc.value.code == 2


def test_main_only_reads(tmp_path: Path) -> None:
    path = _write_report(tmp_path, "X", "<b>")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    content = path.read_bytes()

    report_check._main(["--id", "X", "--base-dir", str(tmp_path)])
    report_check._main(["--id", "missing", "--base-dir", str(tmp_path)])

    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before
    assert path.read_bytes() == content


def test_main_creates_nothing_when_the_base_dir_is_empty(tmp_path: Path) -> None:
    base = tmp_path / ".insight"

    assert report_check._main(["--id", "X", "--base-dir", str(base)]) == 2
    assert not base.exists()
