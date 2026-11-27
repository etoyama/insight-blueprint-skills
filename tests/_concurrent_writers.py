"""Writers that tests start in separate processes, all at one moment (ADR-0062).

They live in their own module so a spawned process can import them by name.
Each waits until *start_at* so the writers overlap instead of running one after
another while the other processes are still starting.
"""

from __future__ import annotations

import time
from pathlib import Path

from skills._shared import design_io


def _wait_until(start_at: float) -> None:
    time.sleep(max(0.0, start_at - time.time()))


def create_designs(base_dir: str, count: int, start_at: float) -> list[str]:
    _wait_until(start_at)
    return [
        design_io.create_design(
            theme_id="FP",
            title="Concurrent",
            analysis_intent="exploratory",
            exploration_question="How far apart are the regions?",
            exploration_background="Nobody has measured the spread",
            methodology={"method": "describe"},
            base_dir=Path(base_dir),
        )["id"]
        for _ in range(count)
    ]


def append_events(
    base_dir: str, design_id: str, count: int, start_at: float
) -> list[str]:
    _wait_until(start_at)
    return [
        design_io.append_journal_event(
            design_id, {"type": "observe", "content": "seen"}, Path(base_dir)
        )["id"]
        for _ in range(count)
    ]
