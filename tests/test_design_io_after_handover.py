"""What design_io holds to once an analysis is handed over (Story 35.7, US-4).

A stopped analysis keeps its status and takes no new result (ADR-0064 7), the
stage and the open confirmations are read by one command, and an execution agent
records its results through a command that takes the write lock (ADR-0062 2).
"""

from __future__ import annotations

import json
import multiprocessing
import subprocess
import sys
import time
from pathlib import Path

import pytest

from skills._shared import design_io
from tests import _concurrent_writers

REPO_ROOT = Path(__file__).resolve().parents[1]
STOPPED_REFUSAL = "is stopped"


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    return base


def _design(insight: Path, status: str = "analyzing") -> str:
    design_id = design_io.create_design(
        theme_id="FP",
        title="Test",
        analysis_intent="exploratory",
        exploration_question="How far apart are the regions?",
        exploration_background="Nobody has measured the spread",
        methodology={"method": "describe"},
        base_dir=insight,
    )["id"]
    if status == "analyzing":
        design_io.transition_status(design_id, "analyzing", insight)
    return design_id


def _status(insight: Path, design_id: str) -> str:
    return design_io.load_design(design_id, insight)["status"]


def _cli(*args: str, payload: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "skills._shared.design_io", *args],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestAStoppedAnalysisKeepsItsStatus:
    """ADR-0064 7: neither a transition, an update nor a review moves a stopped design."""

    def test_a_stopped_analysis_is_not_ended_by_a_transition(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match=STOPPED_REFUSAL):
            design_io.transition_status(design_id, "explored", insight)

        assert _status(insight, design_id) == "analyzing"
        assert design_io.stage_of(design_id, insight).value == "stopped"

    def test_a_design_stopped_before_its_run_is_not_moved_into_the_analysis(
        self, insight: Path
    ) -> None:
        design_id = _design(insight, "in_review")
        design_io.stop_analysis(design_id, "今回は任せない", insight)

        with pytest.raises(ValueError, match=STOPPED_REFUSAL):
            design_io.transition_status(design_id, "analyzing", insight)

        assert _status(insight, design_id) == "in_review"

    def test_the_refusal_says_to_derive_another_design(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match="derive another design"):
            design_io.transition_status(design_id, "explored", insight)

    def test_an_update_does_not_change_the_status_of_a_stopped_analysis(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match=STOPPED_REFUSAL):
            design_io.update_design(design_id, {"status": "explored"}, insight)

        assert _status(insight, design_id) == "analyzing"

    def test_an_update_that_keeps_the_status_still_goes_through(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        design_io.update_design(design_id, {"title": "Renamed"}, insight)

        assert design_io.load_design(design_id, insight)["title"] == "Renamed"

    def test_a_review_does_not_move_a_stopped_design(self, insight: Path) -> None:
        design_id = _design(insight, "in_review")
        design_io.stop_analysis(design_id, "今回は任せない", insight)

        with pytest.raises(ValueError, match=STOPPED_REFUSAL):
            design_io.append_review_batch(
                design_id, "revision_requested", [{"comment": "粒度"}], base_dir=insight
            )

        assert _status(insight, design_id) == "in_review"
        assert design_io.list_review_batches(design_id, insight) == []

    def test_an_analysis_that_is_not_stopped_still_moves(self, insight: Path) -> None:
        design_id = _design(insight)

        design_io.transition_status(design_id, "explored", insight)

        assert _status(insight, design_id) == "explored"


class TestStageCommand:
    """One command reads the stage, so a skill never works it out from the journal."""

    def test_it_names_the_stage(self, insight: Path) -> None:
        design_id = _design(insight)

        report = design_io.stage_report(design_id, insight)

        assert report["design_id"] == design_id
        assert report["stage"] == "running"

    def test_a_running_analysis_has_no_result_on_record(self, insight: Path) -> None:
        design_id = _design(insight)

        assert design_io.stage_report(design_id, insight)["result_on_record"] is False

    def test_a_result_is_on_record_once_the_run_wrote_one(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.append_journal_event(
            design_id, {"type": "observe", "content": "seen"}, insight
        )

        report = design_io.stage_report(design_id, insight)

        assert report["stage"] == "awaiting_reflection"
        assert report["result_on_record"] is True

    def test_a_result_stays_on_record_while_its_review_holds_the_design(
        self, insight: Path
    ) -> None:
        """A review of the result takes the design back to in_review (ADR-0054)."""
        design_id = _design(insight)
        design_io.append_journal_event(
            design_id, {"type": "evidence", "content": "measured"}, insight
        )
        design_io.transition_status(design_id, "in_review", insight)

        report = design_io.stage_report(design_id, insight)

        assert report["stage"] == "before_run"
        assert report["result_on_record"] is True

    def test_a_hearing_and_a_confirmation_are_not_results(self, insight: Path) -> None:
        design_id = _design(insight)
        design_io.append_journal_event(
            design_id, {"type": "hearing", "content": "聞いた答え"}, insight
        )
        design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        assert design_io.stage_report(design_id, insight)["result_on_record"] is False

    def test_it_lists_what_the_analysis_asks_with_the_id_to_answer(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)

        report = design_io.stage_report(design_id, insight)

        assert report["stage"] == "awaiting_confirmation"
        assert report["asks"] == [
            {"id": asked["id"], "content": "分母を変えないと進めない"}
        ]

    def test_an_answered_confirmation_is_no_longer_asked(self, insight: Path) -> None:
        design_id = _design(insight)
        asked = design_io.ask_analyst(design_id, "分母を変えないと進めない", insight)
        design_io.answer_analyst(design_id, asked["id"], "そのまま", insight)

        report = design_io.stage_report(design_id, insight)

        assert report["stage"] == "running"
        assert report["asks"] == []

    def test_it_runs_from_the_command_line(self, insight: Path) -> None:
        design_id = _design(insight)

        ran = _cli("stage", "--base-dir", str(insight), "--id", design_id)

        assert ran.returncode == 0, ran.stderr
        assert json.loads(ran.stdout) == {
            "design_id": design_id,
            "stage": "running",
            "result_on_record": False,
            "asks": [],
        }


class TestJournalAppend:
    """ADR-0062 2: an execution agent records its results under the write lock."""

    def test_it_appends_the_events_in_order_with_ids_and_times(
        self, insight: Path
    ) -> None:
        design_id = _design(insight)

        written = design_io.append_journal_events(
            design_id,
            [
                {"type": "observe", "content": "12か月ぶんある"},
                {
                    "type": "evidence",
                    "content": "差は3ポイント",
                    "metadata": {"direction": "supports"},
                },
            ],
            insight,
        )

        assert [e["id"] for e in written] == [f"{design_id}-E01", f"{design_id}-E02"]
        assert all(e["created_at"] for e in written)
        assert written[1]["metadata"] == {"direction": "supports"}
        assert design_io.journal_events(design_id, insight) == written

    def test_the_events_already_in_the_journal_stay(self, insight: Path) -> None:
        design_id = _design(insight)
        first = design_io.append_journal_event(
            design_id, {"type": "hearing", "content": "聞いた答え"}, insight
        )

        written = design_io.append_journal_events(
            design_id, [{"type": "observe", "content": "seen"}], insight
        )

        assert design_io.journal_events(design_id, insight) == [first, *written]
        assert written[0]["id"] == f"{design_id}-E02"

    def test_a_stopped_analysis_takes_no_new_result(self, insight: Path) -> None:
        design_id = _design(insight)
        stop = design_io.stop_analysis(design_id, "先に別の論点を見る", insight)

        with pytest.raises(ValueError, match=STOPPED_REFUSAL):
            design_io.append_journal_events(
                design_id, [{"type": "observe", "content": "seen"}], insight
            )

        assert design_io.journal_events(design_id, insight) == [stop]

    @pytest.mark.parametrize(
        "events",
        [
            [],
            None,
            "observe",
            [{"type": "observe"}],
            [{"content": "seen"}],
            [{"type": "observe", "content": "  "}],
            ["observe"],
        ],
    )
    def test_events_without_a_type_and_a_text_are_refused(
        self, insight: Path, events: object
    ) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError):
            design_io.append_journal_events(design_id, events, insight)  # type: ignore[arg-type]

        assert design_io.journal_events(design_id, insight) == []

    def test_one_bad_event_leaves_the_journal_as_it_was(self, insight: Path) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError):
            design_io.append_journal_events(
                design_id,
                [{"type": "observe", "content": "seen"}, {"type": "evidence"}],
                insight,
            )

        assert design_io.journal_events(design_id, insight) == []

    def test_a_mark_is_still_written_only_by_its_command(self, insight: Path) -> None:
        design_id = _design(insight)

        with pytest.raises(ValueError, match="answer-analyst and stop"):
            design_io.append_journal_events(
                design_id,
                [{"type": "decide", "content": "x", "metadata": {"stopped": True}}],
                insight,
            )

        assert design_io.journal_events(design_id, insight) == []

    def test_a_missing_design_is_refused(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            design_io.append_journal_events(
                "FP-H09", [{"type": "observe", "content": "seen"}], insight
            )

    def test_it_runs_from_the_command_line(self, insight: Path) -> None:
        design_id = _design(insight)

        ran = _cli(
            "journal-append",
            "--base-dir",
            str(insight),
            "--id",
            design_id,
            payload={"events": [{"type": "observe", "content": "seen"}]},
        )

        assert ran.returncode == 0, ran.stderr
        assert [e["id"] for e in json.loads(ran.stdout)] == [f"{design_id}-E01"]

    def test_a_stop_and_a_result_written_at_once_leave_exactly_one_of_them(
        self, insight: Path
    ) -> None:
        """M3 of Story 35.2: the dialogue agent stops while the execution agent records.

        Whichever takes the lock first wins: a stopped analysis takes no result,
        and an analysis with a result waits for its reflection instead of a stop.
        """
        design_ids = [_design(insight) for _ in range(10)]
        start_at = time.time() + 1.0
        context = multiprocessing.get_context("spawn")
        with context.Pool(2) as pool:
            recording = pool.apply_async(
                _concurrent_writers.record_results, (str(insight), design_ids, start_at)
            )
            stopping = pool.apply_async(
                _concurrent_writers.stop_analyses, (str(insight), design_ids, start_at)
            )
            recorded = dict(recording.get(timeout=60))
            stopped = dict(stopping.get(timeout=60))

        for design_id in design_ids:
            kinds = [e["type"] for e in design_io.journal_events(design_id, insight)]
            assert recorded[design_id] != stopped[design_id], design_id
            assert kinds == (["observe"] if recorded[design_id] else ["decide"])
