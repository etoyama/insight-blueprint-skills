"""The check of the computation in the analysis note (Epic 36, Story 36.7).

US-5 AC 4: the note shows the result of the check before the values of the
results. Its section says, before its table, what was compared with what, who
compared them, and what the check did not look at. The note reads the check
from ``design_check.check_reading`` only (ADR-0070). Synthetic data only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from insight_blueprint.models.check import (
    CheckedBy,
    CheckItem,
    CheckResult,
    CheckSubject,
    verdict_digest,
)
from insight_blueprint.models.design import AnalysisDesign
from skills._shared import design_check, design_io
from skills._shared.design_note import CodeCell, DesignNote, NoteVerdict, render_note
from skills._shared.design_note_check import (
    CHECK_HEADING,
    CHECK_RESULT_WORDS,
    CHECK_SUBJECT_WORDS,
    NoteCheck,
    check_summary,
)
from skills._shared.design_note_read import load_design_note, render_design_note
from tests._stages import stage_of_status
from tests._tree_page import Element, by_id, parse, squash

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    REPO_ROOT / "tests" / "integration" / "fixtures" / "sample_notebook.py"
).read_text(encoding="utf-8")
EVIL = '<script>alert(1)</script>"'
METRIC_NOTE = "分析コードの出した結果の指標「mean_by_group」が、分析設計に無い。"
GRAIN_NOTE = "分析設計は利用者ごとに数えるが、分析コードは予約ごとに数えている。"
CELLS = (
    CodeCell(position=1, name="imports", source="# %% imports\nimport polars"),
    CodeCell(position=3, name="data_prep", source="# %% data_prep\ndf = raw_df"),
    CodeCell(position=4, name="analysis", source="# %% analysis\nresults = {}"),
)


def _design() -> AnalysisDesign:
    return AnalysisDesign.model_validate(
        {
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
    )


def _item(subject: str, result: str = "agrees", **over: str) -> CheckItem:
    return CheckItem.model_validate({"subject": subject, "result": result, **over})


def _all_agree(**differ: CheckItem) -> tuple[CheckItem, ...]:
    return tuple(differ.get(s.value, _item(s.value)) for s in CheckSubject)


def _check(
    *items: CheckItem, checked_by: CheckedBy = CheckedBy.check_agent
) -> NoteCheck:
    return NoteCheck(checked=True, checked_by=checked_by, items=items or _all_agree())


TWO_DIFFERENCES = _check(
    *_all_agree(
        grain=_item("grain", "differs", note=GRAIN_NOTE, cell="data_prep"),
        metrics=_item("metrics", "differs", note=METRIC_NOTE, cell="analysis"),
        extraction=_item(
            "extraction", "not_checkable", note="抽出のクエリが分析設計に無い"
        ),
    )
)


def _note(
    check: NoteCheck | None = None,
    *,
    verdict: bool = True,
    cells: tuple[CodeCell, ...] | None = CELLS,
) -> DesignNote:
    design = _design()
    fields: dict = {
        "design": design,
        "sources": (),
        "events": (),
        "verdict": NoteVerdict(metrics=(), conclusion=None) if verdict else None,
        "figures": (),
        "cells": cells,
        "lineage": None,
        "local_files": (),
        "conclusion": None,
        "stage": stage_of_status(design.status),
    }
    if check is not None:
        fields["check"] = check
    return DesignNote(**fields)


def _root(note: DesignNote) -> Element:
    return parse(str(render_note(note)))


def _section(note: DesignNote) -> Element:
    return by_id(_root(note), "note-LIB-H01-check")


def _paragraphs_before_the_table(section: Element) -> list[str]:
    texts: list[str] = []
    for element in section.walk():
        if element.tag in ("table", "div") and element is not section:
            break
        if element.tag == "p":
            texts.append(squash(element.text()))
    return texts


def _rows(section: Element) -> list[list[str]]:
    (body,) = [e for e in section.walk() if e.tag == "tbody"]
    return [
        [squash(c.text()) for c in row.children]
        for row in body.children
        if row.tag == "tr"
    ]


class TestTheSectionOfTheCheck:
    def test_it_comes_before_the_results(self) -> None:
        ids = [e.attrs.get("id") for e in _root(_note(_check())).walk()]

        assert ids.index("note-LIB-H01-check") < ids.index("note-LIB-H01-results")

    def test_its_heading_names_the_check_in_the_words_of_the_analyst(self) -> None:
        (heading,) = [e for e in _section(_note(_check())).walk() if e.tag == "h3"]

        assert (
            squash(heading.text())
            == CHECK_HEADING
            == "分析設計どおりに計算したかの点検"
        )

    def test_it_says_what_was_compared_with_what_before_its_table(self) -> None:
        lead = " ".join(_paragraphs_before_the_table(_section(_note(_check()))))

        assert "分析設計に書いたこと" in lead
        assert "分析コードがしている計算" in lead
        assert "読み比べ" in lead

    def test_it_says_what_the_check_did_not_look_at_before_its_table(self) -> None:
        lead = " ".join(_paragraphs_before_the_table(_section(_note(_check()))))

        for unchecked in (
            "数が正しいか",
            "分析設計そのものが妥当か",
            "結果の解釈が妥当か",
        ):
            assert unchecked in lead

    @pytest.mark.parametrize(
        ("checked_by", "said"),
        [
            (CheckedBy.check_agent, "分析コードを書いていないエージェント"),
            (CheckedBy.same_session, "分析コードを書いたのと同じエージェント"),
        ],
    )
    def test_it_says_who_compared_them_before_its_table(
        self, checked_by: CheckedBy, said: str
    ) -> None:
        lead = " ".join(
            _paragraphs_before_the_table(_section(_note(_check(checked_by=checked_by))))
        )

        assert said in lead

    def test_it_counts_the_differences_before_its_table(self) -> None:
        lead = " ".join(_paragraphs_before_the_table(_section(_note(TWO_DIFFERENCES))))

        assert "分析設計と違う所が 2 つある" in lead
        assert "確かめられなかった: 抽出" in lead

    def test_a_check_with_no_difference_says_so(self) -> None:
        lead = " ".join(_paragraphs_before_the_table(_section(_note(_check()))))

        assert "分析設計と違う所は無い" in lead


class TestTheTableOfTheCheck:
    def test_it_has_a_row_for_every_subject_in_the_words_of_the_analyst(self) -> None:
        rows = _rows(_section(_note(TWO_DIFFERENCES)))

        assert sorted(r[0] for r in rows) == sorted(CHECK_SUBJECT_WORDS.values())
        assert len(rows) == len(CheckSubject)

    def test_the_differences_come_first_then_what_could_not_be_checked(self) -> None:
        rows = _rows(_section(_note(TWO_DIFFERENCES)))

        assert [r[1] for r in rows[:3]] == [
            CHECK_RESULT_WORDS[CheckResult.differs],
            CHECK_RESULT_WORDS[CheckResult.differs],
            CHECK_RESULT_WORDS[CheckResult.not_checkable],
        ]
        assert {r[1] for r in rows[3:]} == {CHECK_RESULT_WORDS[CheckResult.agrees]}
        # Among the differences, the order of the subjects is kept.
        assert [r[0] for r in rows[:2]] == [
            CHECK_SUBJECT_WORDS[CheckSubject.grain],
            CHECK_SUBJECT_WORDS[CheckSubject.metrics],
        ]

    def test_a_difference_shows_its_sentence_as_the_check_wrote_it(self) -> None:
        rows = _rows(_section(_note(TWO_DIFFERENCES)))

        assert rows[1][2] == METRIC_NOTE

    def test_a_sentence_is_escaped(self) -> None:
        check = _check(
            *_all_agree(grain=_item("grain", "differs", note=EVIL, cell="data_prep"))
        )
        html = str(render_note(_note(check)))

        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_a_difference_links_the_cell_it_was_read_in(self) -> None:
        root = _root(_note(TWO_DIFFERENCES))
        section = by_id(root, "note-LIB-H01-check")
        (link,) = [
            e for e in section.walk() if e.tag == "a" and squash(e.text()) == "analysis"
        ]

        assert link.attrs["href"] == "#note-LIB-H01-cell-analysis"
        # The target sits inside the folded cell, so a browser opens the cell on the link.
        cell = by_id(root, "note-LIB-H01-cell-analysis")
        assert cell.tag == "pre"
        assert cell.parent is not None and cell.parent.tag == "details"
        assert cell.is_inside(by_id(root, "note-LIB-H01-code"))

    def test_a_difference_read_in_the_data_load_cell_names_it_without_a_link(
        self,
    ) -> None:
        check = _check(
            *_all_agree(
                extraction=_item(
                    "extraction", "differs", note=GRAIN_NOTE, cell="data_load"
                )
            )
        )
        section = _section(_note(check))
        (row,) = [r for r in _rows(section) if r[1] == "分析設計と違う"]

        assert row[3].startswith("data_load")
        assert "載せていない" in row[3]
        assert "手元の notebook の .py" in row[3]
        assert not [e for e in section.walk() if e.tag == "a"]

    def test_a_difference_in_a_note_that_shows_no_code_names_its_cell_without_a_link(
        self,
    ) -> None:
        section = _section(_note(TWO_DIFFERENCES, cells=None))
        cells = [r[3] for r in _rows(section) if r[1] == "分析設計と違う"]

        assert all("手元の notebook の .py" in c for c in cells)
        assert not [e for e in section.walk() if e.tag == "a"]

    def test_a_subject_with_no_cell_shows_a_dash(self) -> None:
        rows = _rows(_section(_note(_check())))

        assert {r[3] for r in rows} == {"—"}


class TestACheckNotDone:
    def test_a_check_not_done_says_so_and_shows_no_result(self) -> None:
        section = _section(_note(NoteCheck()))
        text = squash(section.text())

        assert "まだ済んでいない" in text
        assert not [e for e in section.walk() if e.tag == "table"]

    def test_a_check_not_done_says_what_the_check_is(self) -> None:
        text = squash(_section(_note(NoteCheck())).text())

        assert "分析設計に書いたこと" in text

    def test_a_design_without_a_verdict_has_nothing_to_check(self) -> None:
        text = squash(_section(_note(NoteCheck(), verdict=False)).text())

        assert "点検するものが無い" in text
        assert "まだ済んでいない" not in text

    def test_a_note_built_without_a_check_reads_as_one_not_done(self) -> None:
        assert "まだ済んでいない" in squash(_section(_note()).text())


class TestAReadingThatDoesNotRead:
    """A reading that says done but names no reader is no check, as a record that does not read."""

    @pytest.mark.parametrize(
        "reading",
        [
            {"checked": True, "items": []},
            {"checked": True, "checked_by": "someone", "items": []},
            {"checked": True, "checked_by": "check_agent", "items": [{"subject": "x"}]},
            {"checked": True, "checked_by": "check_agent", "items": "not a list"},
        ],
    )
    def test_it_reads_as_a_check_not_done(self, reading: dict) -> None:
        assert NoteCheck.of(reading) == NoteCheck()


class TestTheStatusOfTheNote:
    def test_the_status_says_how_the_check_stands(self) -> None:
        status = squash(
            by_id(_root(_note(TWO_DIFFERENCES)), "note-LIB-H01-status").text()
        )

        assert check_summary(True, TWO_DIFFERENCES) in status

    def test_the_status_links_the_section_of_the_check(self) -> None:
        status = by_id(_root(_note(_check())), "note-LIB-H01-status")
        hrefs = [e.attrs.get("href") for e in status.walk() if e.tag == "a"]

        assert "#note-LIB-H01-check" in hrefs

    @pytest.mark.parametrize(
        ("has_verdict", "check", "said"),
        [
            (False, NoteCheck(), None),
            (True, NoteCheck(), "分析設計どおりに計算したかの点検: まだ済んでいない。"),
            (
                True,
                _check(),
                "分析設計どおりに計算したかの点検: 済んだ。分析設計と違う所は無い。",
            ),
            (
                True,
                TWO_DIFFERENCES,
                "分析設計どおりに計算したかの点検: 済んだ。分析設計と違う所が 2 つある。"
                "確かめられなかった: 抽出。",
            ),
        ],
    )
    def test_the_summary_of_the_check_is_one_line(
        self, has_verdict: bool, check: NoteCheck, said: str | None
    ) -> None:
        assert check_summary(has_verdict, check) == said


# The note reads the check from check_reading, and from nowhere else (ADR-0070).

VERDICT = {
    "conclusion": "the gap is two days",
    "metrics": {"mean_diff": {"value": 2.1, "support_line": 2.0}},
    "figures": [],
}
READ_BY_THE_AGENT = (
    "population",
    "grain",
    "denominator",
    "extraction",
    "compared_against",
    "criterion",
)


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    (base / "notebooks").mkdir()
    return base


def _checked_design(insight: Path) -> str:
    design_id = design_io.create_design(
        theme_id="LIB",
        title="Holding books longer",
        hypothesis_statement="A longer hold shortens the wait",
        hypothesis_background="Seven days leave many unclaimed",
        methodology={"method": "difference of means"},
        metrics=[{"target": "mean_diff", "tier": "primary", "comparison": "2 days"}],
        base_dir=insight,
    )["id"]
    design_io.transition_status(design_id, "analyzing", insight)
    (insight / "notebooks" / f"{design_id}.py").write_text(NOTEBOOK, "utf-8")
    verdict = json.dumps(VERDICT)
    (insight / "notebooks" / f"{design_id}_verdict.json").write_text(verdict, "utf-8")
    design_check.record_check(
        design_id,
        {
            "checked_by": "same_session",
            "verdict_digest": verdict_digest(verdict.encode()),
            "items": [
                {"subject": s, "result": "agrees"}
                | (
                    {"result": "differs", "note": GRAIN_NOTE, "cell": "data_prep"}
                    if s == "grain"
                    else {}
                )
                for s in READ_BY_THE_AGENT
            ],
        },
        insight,
    )
    return design_id


class TestTheNoteReadsTheCheck:
    def test_the_note_holds_the_reading_of_the_check(self, insight: Path) -> None:
        design_id = _checked_design(insight)
        reading = design_check.check_reading(design_id, insight)

        check = load_design_note(design_id, insight).check

        assert check.checked is True
        assert check.checked_by is CheckedBy.same_session
        assert [
            i.model_dump(mode="json", exclude_defaults=True) for i in check.items
        ] == (reading["items"])

    def test_a_verdict_written_again_reads_as_a_check_not_done(
        self, insight: Path
    ) -> None:
        design_id = _checked_design(insight)
        (insight / "notebooks" / f"{design_id}_verdict.json").write_text(
            json.dumps(VERDICT | {"conclusion": "the gap is one day"}), "utf-8"
        )

        assert load_design_note(design_id, insight).check == NoteCheck()

    def test_the_rendered_note_shows_the_difference_of_the_record(
        self, insight: Path
    ) -> None:
        design_id = _checked_design(insight)
        html = Path(render_design_note(design_id, insight)["path"]).read_text("utf-8")

        section = by_id(parse(html), f"note-{design_id}-check")
        assert GRAIN_NOTE in squash(section.text())


def test_the_screen_reads_the_check_only_through_check_reading() -> None:
    """No module of the screens reads the record of a check or its digests itself."""
    screens = [
        "design_note.py",
        "design_note_check.py",
        "design_note_read.py",
        "tree_render.py",
        "tree_render_parts.py",
        "tree_render_stage.py",
        "tree_render_derived.py",
        "theme_report.py",
        "tree_words.py",
    ]
    shared = REPO_ROOT / "skills" / "_shared"
    for name in screens:
        text = (shared / name).read_text(encoding="utf-8")
        assert "_check.yaml" not in text, name
        assert not re.search(r"\b(verdict_digest|design_digest|is_current)\(", text), (
            name
        )


def _shown_words_table() -> str:
    """The right column of the table of the words shown to the analyst, in the DesignDoc."""
    doc = (
        REPO_ROOT / "docs" / "design" / "epic-36-before-the-analyst-answers.md"
    ).read_text(encoding="utf-8")
    section = doc.split("### 分析者に見せる言葉", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ")]
    return "\n".join(row.split(" | ", 1)[1] for row in rows[2:])


@pytest.mark.parametrize(
    "word",
    [
        CHECK_HEADING,
        *CHECK_SUBJECT_WORDS.values(),
        *CHECK_RESULT_WORDS.values(),
        "この分析コードを書いていないエージェント",
        "この分析コードを書いたのと同じエージェント",
        "まだ済んでいない",
        "点検するものが無い",
        "分析設計と違う所が N つある",
        "分析設計と違う所は無い",
        "確かめられなかった: （項目の言葉）",
        "点検の結果を開く",
        "（分析者の見立て）",
    ],
)
def test_the_designdoc_lists_each_word_the_screens_show(word: str) -> None:
    """A word the screens add is in the DesignDoc's table, for the human who reads them."""
    assert word in _shown_words_table()


def test_the_screens_name_the_subjects_and_the_results_as_the_chat_does() -> None:
    """The chat (reflection Step 2) and the screens say one check in the same words."""
    skill = (REPO_ROOT / "skills" / "analysis-reflection" / "SKILL.md").read_text(
        "utf-8"
    )
    shown = {
        **{s.value: w for s, w in CHECK_SUBJECT_WORDS.items()},
        **{r.value: w for r, w in CHECK_RESULT_WORDS.items()},
    }

    for name, word in shown.items():
        assert f"| `{name}` | {word} |" in skill, name
