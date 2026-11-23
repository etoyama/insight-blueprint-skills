"""Structure tests for the lineage calls the notebook contract shows (data_load to analysis).

The contract once said only "every transform via ``tracked_pipe(...)``". A generator
guessed ``tracked_pipe(df, session, fn, name=...)`` and the notebook died in the data_prep cell with
a ``TypeError``. These tests hold the contract's examples to the real signatures, so the
examples cannot drift from ``insight_blueprint.lineage``.
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Callable

import pandas as pd
import pytest

from insight_blueprint.lineage import LineageSession, tracked_pipe
from tests.skills._markdown import section
from tests.skills.test_skill_structure import SKILLS_DIR

CONTRACT = SKILLS_DIR / "analysis-notebook" / "references" / "notebook-contract.md"
HEADING = "## Lineage calls"


def _example() -> str:
    block = section(CONTRACT.read_text(encoding="utf-8"), HEADING)
    fenced = re.search(r"```python\n(.*?)```", block, re.DOTALL)
    assert fenced, f"{HEADING} holds a python block"
    return fenced.group(1)


def _calls(name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(_example()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


@pytest.mark.parametrize(
    ("name", "target"),
    [("LineageSession", LineageSession), ("tracked_pipe", tracked_pipe)],
)
def test_each_example_call_binds_to_the_real_signature(
    name: str, target: Callable[..., object]
) -> None:
    calls = _calls(name)
    assert calls, f"the example calls {name}"
    signature = inspect.signature(target)
    for call in calls:
        args = [object() for _ in call.args]
        kwargs = {kw.arg: object() for kw in call.keywords if kw.arg}
        signature.bind(*args, **kwargs)


def test_the_example_runs_and_records_each_step() -> None:
    namespace: dict[str, object] = {
        "pd": pd,
        "LineageSession": LineageSession,
        "tracked_pipe": tracked_pipe,
        "raw_df": pd.DataFrame({"x": [1.0, None, 3.0]}),
    }
    exec(_example(), namespace)  # noqa: S102 — the contract's own example, not input
    session = namespace["session"]
    assert isinstance(session, LineageSession)
    assert len(session.steps) == len(_calls("tracked_pipe"))
    assert isinstance(namespace["df_clean"], pd.DataFrame)
