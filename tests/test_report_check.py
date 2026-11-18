"""Unit tests for skills/_shared/report_check.py (Epic 13, Story 85).

report_check reads a finished report and lists the constructs that would be
active markup: images that are not a figure, raw HTML, and tags inside a
mermaid fence. It never rewrites the report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills._shared import report_check
from skills._shared.report_check import Violation, find_violations

FIGURE = "![Figure 1](../notebooks/FP-H01_fig01.png)"


def _kinds(markdown: str) -> list[str]:
    return [v.kind for v in find_violations(markdown)]


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
        "![x](../notebooks/a b.png)",
        "![x][ref]",
        "![x](../notebooks/a.png",
    ],
)
def test_image_that_is_not_a_figure_is_a_violation(construct: str) -> None:
    violations = find_violations(f"see {construct}")
    assert [v.kind for v in violations] == ["image"]
    assert violations[0].line == 1


def test_image_violation_text_is_the_whole_construct() -> None:
    [v] = find_violations("before ![x](http://e/a.png) after")
    assert v.text == "![x](http://e/a.png)"


def test_unclosed_image_text_runs_to_the_end_of_the_line() -> None:
    [v] = find_violations("![x](http://e/a.png and more")
    assert v.text == "![x](http://e/a.png and more"


def test_escaped_brackets_in_a_figure_alt_are_allowed() -> None:
    assert find_violations(r"![a \[b\]](../notebooks/f.png)") == []


# --- raw html ---------------------------------------------------------------


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
    ],
)
def test_raw_html_in_prose_is_a_violation(markup: str) -> None:
    violations = find_violations(f"text {markup} text")
    assert [v.kind for v in violations] == ["html"]
    assert violations[0].text.startswith(markup[:3])


def test_unclosed_html_block_start_is_a_violation() -> None:
    [v] = find_violations("<script src=http://evil.example/x.js")
    assert (v.kind, v.line) == ("html", 1)
    assert v.text == "<script src=http://evil.example/x.js"


def test_html_block_start_allows_up_to_three_spaces_of_indent() -> None:
    assert _kinds("   <div") == ["html"]


def test_complete_tag_at_line_start_is_reported_once() -> None:
    assert _kinds("<div>hello") == ["html"]


# --- things that merely look like markup ------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "x < y and y > z",
        "p<0.05",
        "a <- b",
        r"\<img src=x>",
        r"\\\<img src=x>",
        "`<div>`",
        "``a ` <div> ``",
        "[text](http://example.com)",
        "see http://example.com/a.png",
        r"!\[x\](http://e/a.png)",
        r"\![x](http://e/a.png)",
        r"a \| b",
    ],
)
def test_text_that_is_not_active_markup_is_not_a_violation(line: str) -> None:
    assert find_violations(line) == []


def test_even_backslashes_do_not_escape_the_next_character() -> None:
    assert _kinds(r"\\<img src=x>") == ["html"]


def test_escaped_backtick_does_not_open_a_code_span() -> None:
    assert _kinds(r"\`<div>`") == ["html"]


def test_unclosed_backtick_run_is_literal_text() -> None:
    assert _kinds("`<div>") == ["html"]


def test_code_span_closes_only_on_a_run_of_the_same_length() -> None:
    assert find_violations("``a ` <div> b``") == []


# --- fences -----------------------------------------------------------------


def test_html_inside_a_non_mermaid_fence_is_not_a_violation() -> None:
    assert find_violations("```python\n<div>\n![x](http://e/a.png)\n```") == []


def test_tilde_fence_hides_its_contents() -> None:
    assert find_violations("~~~\n<div>\n~~~") == []


def test_fence_closes_only_on_a_fence_at_least_as_long() -> None:
    md = "````\n```\n<div>\n````\n<b>"
    assert [(v.line, v.kind) for v in find_violations(md)] == [(5, "html")]


def test_closing_fence_with_an_info_string_does_not_close() -> None:
    md = "```\n``` text\n<div>\n```"
    assert find_violations(md) == []


def test_unclosed_fence_hides_the_rest_of_the_document() -> None:
    assert find_violations("```\n<div>") == []


def test_prose_after_a_closed_fence_is_checked_again() -> None:
    md = "```\n<div>\n```\n<b>x"
    assert [v.line for v in find_violations(md)] == [4]


def test_fence_may_be_indented_by_up_to_three_spaces() -> None:
    assert find_violations("   ```\n<div>\n   ```") == []


# --- mermaid ----------------------------------------------------------------


@pytest.mark.parametrize("br", ["<br>", "<br/>", "<br />", "<BR/>"])
def test_br_inside_a_mermaid_fence_is_not_a_violation(br: str) -> None:
    assert find_violations(f"```mermaid\nA[a{br}b] --> B\n```") == []


def test_other_tag_inside_a_mermaid_fence_is_a_mermaid_html_violation() -> None:
    [v] = find_violations("```mermaid\nA[<img src=x>] --> B\n```")
    assert (v.line, v.kind, v.text) == (2, "mermaid-html", "<img src=x>")


def test_closing_tag_inside_a_mermaid_fence_is_a_violation() -> None:
    assert _kinds("```Mermaid\nA[x</b>] --> B\n```") == ["mermaid-html"]


def test_mermaid_arrows_are_not_tags() -> None:
    assert find_violations("```mermaid\nA <--> B\nA -->|x<0.5| B\n```") == []


def test_mermaid_fence_content_is_not_treated_as_prose() -> None:
    assert _kinds("```mermaid\nA[`<br/>`]\n```") == []


# --- positions and text -----------------------------------------------------


def test_line_numbers_are_one_based_and_count_every_line() -> None:
    md = "# Title\n\n```\ncode\n```\n\nok <b>x"
    assert [v.line for v in find_violations(md)] == [7]


def test_crlf_line_endings_keep_line_numbers() -> None:
    assert [v.line for v in find_violations("a\r\nb\r\n<b>")] == [3]


def test_violations_on_one_line_come_in_reading_order() -> None:
    assert _kinds("<b> ![x](http://e/a.png) <i>") == ["html", "image", "html"]


def test_violation_text_is_cut_to_120_characters() -> None:
    [v] = find_violations("<div " + "a" * 300 + ">")
    assert len(v.text) == 120


def test_violation_is_a_frozen_value() -> None:
    v = Violation(line=1, kind="html", text="<b>")
    with pytest.raises(AttributeError):
        v.line = 2  # type: ignore[misc]


# --- a realistic clean report -----------------------------------------------

CLEAN_REPORT = f"""\
# FP-H01: 家賃と人口の関係

## Method

Source: `.insight/notebooks/FP-H01.py`

| 指標 | 値 |
|---|---|
| a \\| b | p < 0.05 |

## Results

{FIGURE}

Figure 1. caption with \\<script\\> and \\[link\\]\\(http://e\\) escaped.

```mermaid
flowchart LR
    A[source<br/>table] --> B[result<br />view]
```

```python
print("<div>")
```

See [docs](http://example.com) and http://example.com/a.png.
"""


def test_a_report_that_follows_the_rules_has_no_violation() -> None:
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


def test_tag_left_open_at_the_end_of_a_line_is_a_violation() -> None:
    # CommonMark lets an inline tag continue on the next line.
    markdown = "説明 <img\nsrc=x onerror=alert(1)>\n"
    assert [(v.line, v.kind) for v in find_violations(markdown)] == [(1, "html")]


def test_less_than_before_a_word_that_ends_the_line_without_a_tag_shape() -> None:
    assert find_violations("n <5\n次の行\n") == []
