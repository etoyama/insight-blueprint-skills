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


def link_designs(
    base_dir: str, node_id: str, design_ids: list[str], start_at: float
) -> None:
    from skills._shared import tree_io

    _wait_until(start_at)
    for design_id in design_ids:
        tree_io.link_design("LIB", node_id, design_id, base_dir=Path(base_dir))


def copy_hearings(
    base_dir: str, node_id: str, design_id: str, count: int, start_at: float
) -> list[bool]:
    from skills._shared import tree_io

    _wait_until(start_at)
    copied: list[bool] = []
    for _ in range(count):
        result = tree_io.copy_hearing(
            "LIB", node_id, design_id, base_dir=Path(base_dir)
        )
        copied.append(result["copied"])
    return copied


def _each_taken(design_ids: list[str], write) -> list[tuple[str, bool]]:
    """Whether *write* went through for each design; a refusal is a ValueError."""
    taken: list[tuple[str, bool]] = []
    for design_id in design_ids:
        try:
            write(design_id)
        except ValueError:
            taken.append((design_id, False))
        else:
            taken.append((design_id, True))
    return taken


def record_results(
    base_dir: str, design_ids: list[str], start_at: float
) -> list[tuple[str, bool]]:
    _wait_until(start_at)
    return _each_taken(
        design_ids,
        lambda design_id: design_io.append_journal_events(
            design_id, [{"type": "observe", "content": "seen"}], Path(base_dir)
        ),
    )


def stop_analyses(
    base_dir: str, design_ids: list[str], start_at: float
) -> list[tuple[str, bool]]:
    _wait_until(start_at)
    return _each_taken(
        design_ids,
        lambda design_id: design_io.stop_analysis(
            design_id, "先に別の論点を見る", Path(base_dir)
        ),
    )
