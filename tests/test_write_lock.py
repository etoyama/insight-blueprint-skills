"""The lock from reading to writing back (ADR-0062, Story 35.2, US-5 AC 1).

Before Epic 35 only the moment of the write was locked: two processes that
created a design at once read the same highest id, and one design silently
replaced the other (20 of 20 tries). The tests start two real processes at one
moment, as the trial did.
"""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from skills._shared import design_io
from skills._shared._atomic import write_lock
from tests import _concurrent_writers

ROUNDS = 10


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    return base


def _in_two_processes(target, *args: object) -> list[str]:
    start_at = time.time() + 1.0
    context = multiprocessing.get_context("spawn")
    with context.Pool(2) as pool:
        results = [pool.apply_async(target, (*args, start_at)) for _ in range(2)]
        return [item for result in results for item in result.get(timeout=60)]


class TestWriteLock:
    def test_the_lock_can_be_taken_again_inside_itself(self, insight: Path) -> None:
        with write_lock(insight), write_lock(insight):
            pass

    def test_the_lock_creates_the_directory_it_lives_in(self, tmp_path: Path) -> None:
        with write_lock(tmp_path / "new" / ".insight"):
            pass

    def test_two_processes_creating_designs_at_once_get_different_ids(
        self, insight: Path
    ) -> None:
        ids = _in_two_processes(
            _concurrent_writers.create_designs, str(insight), ROUNDS
        )

        assert len(set(ids)) == 2 * ROUNDS
        on_disk = sorted((insight / "designs").glob("FP-H*_hypothesis.yaml"))
        assert len(on_disk) == 2 * ROUNDS

    def test_two_processes_appending_events_at_once_keep_every_event(
        self, insight: Path
    ) -> None:
        design_id = _concurrent_writers.create_designs(str(insight), 1, 0.0)[0]

        ids = _in_two_processes(
            _concurrent_writers.append_events, str(insight), design_id, ROUNDS
        )

        assert len(set(ids)) == 2 * ROUNDS
        written = [e["id"] for e in design_io.journal_events(design_id, insight)]
        assert sorted(written) == sorted(ids)


def test_threads_meeting_a_new_base_dir_share_one_lock(tmp_path: Path) -> None:
    import threading

    base = tmp_path / ".insight"
    barrier = threading.Barrier(8)
    done: list[bool] = []

    def take() -> None:
        barrier.wait()
        with write_lock(base), write_lock(base):
            done.append(True)

    threads = [threading.Thread(target=take, daemon=True) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(done) == 8
