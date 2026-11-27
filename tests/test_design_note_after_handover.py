"""The analysis note of a design that was handed over (Story 35.7, US-4 AC 3).

An answered confirmation is not an open question (ADR-0064 9), and the note of
a stopped design says so under its status, which stays as the YAML holds it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insight_blueprint.models.analysis_stage import AnalysisStage
from skills._shared import design_io
from skills._shared.design_note_read import load_design_note, render_design_note
from skills._shared.tree_words import STAGE_WORDS, note_stage_line

ASKED = "予約の記録が2025年10月より前に無い。対象を変えてよいか"
WHY = "通知の時刻が記録されていなかった"


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    return base


def _running(insight: Path) -> str:
    design_id = design_io.create_design(
        theme_id="LIB",
        title="館ごとの期限切れ",
        analysis_intent="exploratory",
        exploration_question="期限切れはどの館で多いか",
        exploration_background="館ごとの差をまだ見ていない",
        base_dir=insight,
    )["id"]
    design_io.transition_status(design_id, "analyzing", base_dir=insight)
    return design_id


def _open_questions(insight: Path, design_id: str) -> list[str]:
    conclusion = load_design_note(design_id, base_dir=insight).conclusion
    assert conclusion is not None
    return [e.content for e in conclusion.open_questions]


class TestAnAnsweredConfirmationIsNotAnOpenQuestion:
    def test_the_answered_confirmation_is_left_out(self, insight: Path) -> None:
        design_id = _running(insight)
        asked = design_io.ask_analyst(design_id, ASKED, insight)
        design_io.answer_analyst(
            design_id, asked["id"], "2025年10月からでよい", insight
        )
        design_io.append_journal_events(
            design_id, [{"type": "question", "content": "冬も同じか"}], insight
        )
        design_io.transition_status(design_id, "explored", base_dir=insight)

        assert _open_questions(insight, design_id) == ["冬も同じか"]

    def test_a_question_nobody_resolved_stays_open(self, insight: Path) -> None:
        design_id = _running(insight)
        design_io.append_journal_events(
            design_id, [{"type": "question", "content": "冬も同じか"}], insight
        )
        design_io.transition_status(design_id, "explored", base_dir=insight)

        assert _open_questions(insight, design_id) == ["冬も同じか"]

    def test_the_answered_confirmation_still_shows_in_the_progress(
        self, insight: Path
    ) -> None:
        """The record stays readable: only the count of open questions leaves it out."""
        design_id = _running(insight)
        asked = design_io.ask_analyst(design_id, ASKED, insight)
        design_io.answer_analyst(
            design_id, asked["id"], "2025年10月からでよい", insight
        )

        html = Path(render_design_note(design_id, insight)["path"]).read_text("utf-8")

        assert ASKED in html
        assert "2025年10月からでよい" in html


class TestTheNoteOfAStoppedDesignSaysSo:
    def test_the_line_names_the_stage_and_the_reason(self) -> None:
        line = note_stage_line(AnalysisStage.stopped, WHY)

        assert line == f"段階: {STAGE_WORDS[AnalysisStage.stopped][0]}（{WHY}）"

    @pytest.mark.parametrize(
        "stage", sorted(set(AnalysisStage) - {AnalysisStage.stopped})
    )
    def test_only_a_stopped_design_gets_the_line(self, stage: AnalysisStage) -> None:
        assert note_stage_line(stage, None) is None

    def test_the_note_page_adds_the_line_under_the_status(self, insight: Path) -> None:
        design_id = _running(insight)
        design_io.stop_analysis(design_id, WHY, insight)

        html = Path(render_design_note(design_id, insight)["path"]).read_text("utf-8")

        status = "<p>状態: 分析中（analyzing）</p>"
        line = f"<p>{note_stage_line(AnalysisStage.stopped, WHY)}</p>"
        assert status + line in html

    def test_a_running_design_has_no_such_line(self, insight: Path) -> None:
        design_id = _running(insight)

        html = Path(render_design_note(design_id, insight)["path"]).read_text("utf-8")

        assert "状態: 分析中（analyzing）" in html
        assert "段階:" not in html
