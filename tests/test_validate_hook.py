"""Tests for the pre-write design-validation hook (Epic 02, Story 2.2).

The hook is the I/O shell around ``insight_blueprint.validate``. Pure helpers
(path matching, edit reconstruction) are unit-tested by importing the hook
module directly; the end-to-end contract (stdin JSON -> exit code) is tested by
running the hook as a subprocess, the way Claude Code invokes it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / "hooks" / "validate-design.py"


def load_hook_module() -> ModuleType:
    """Import the hook script as a module for unit-testing its pure helpers."""
    spec = importlib.util.spec_from_file_location("validate_design_hook", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load_hook_module()


def design_dict(**overrides: object) -> dict:
    base: dict = {
        "id": "FP-H01",
        "title": "Test design",
        "hypothesis_statement": "X improves Y",
        "hypothesis_background": "Because Z",
        "status": "in_review",
    }
    base.update(overrides)
    return base


CRITERION = "supported at 2.0 days or more, rejected under 1.0 day"
MARK = "2026-11-25T10:00:00+09:00"


def started_design(**overrides: object) -> dict:
    """A confirmation with its criterion, as one whose analysis may start."""
    metrics = [{"target": "lead time", "tier": "primary", "comparison": CRITERION}]
    return design_dict(metrics=metrics) | overrides


def edit(path: Path, old: str, new: str) -> subprocess.CompletedProcess[str]:
    return run_hook(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(path),
                "old_string": old,
                "new_string": new,
            },
        }
    )


def dump_yaml(data: dict) -> str:
    from io import StringIO

    yaml = YAML()
    buf = StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()


def write_design(tmp_path: Path, design_id: str, data: dict) -> Path:
    """Write a design YAML to a temp project's .insight/designs/ and return path."""
    designs = tmp_path / ".insight" / "designs"
    designs.mkdir(parents=True, exist_ok=True)
    path = designs / f"{design_id}_hypothesis.yaml"
    path.write_text(dump_yaml(data), encoding="utf-8")
    return path


def run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    """Invoke the hook as a subprocess with a PreToolUse JSON payload on stdin."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Pure helpers: path matching
# ---------------------------------------------------------------------------


class TestIsDesignFile:
    def test_matches_hypothesis_yaml_in_designs(self) -> None:
        assert hook.is_design_file("/p/.insight/designs/FP-H01_hypothesis.yaml")

    def test_rejects_journal_yaml(self) -> None:
        assert not hook.is_design_file("/p/.insight/designs/FP-H01_journal.yaml")

    def test_rejects_outside_designs_dir(self) -> None:
        assert not hook.is_design_file("/p/elsewhere/FP-H01_hypothesis.yaml")

    def test_rejects_none(self) -> None:
        assert not hook.is_design_file(None)


# ---------------------------------------------------------------------------
# Pure helpers: edit reconstruction
# ---------------------------------------------------------------------------


class TestReconstructContent:
    def test_write_returns_content(self) -> None:
        out = hook.reconstruct_content("Write", {"content": "a: 1\n"}, "old")
        assert out == "a: 1\n"

    def test_edit_replaces_first_occurrence(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "in_review", "new_string": "analyzing"},
            "status: in_review\n",
        )
        assert out == "status: analyzing\n"

    def test_edit_replace_all(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "x", "new_string": "y", "replace_all": True},
            "x x x",
        )
        assert out == "y y y"

    def test_edit_missing_old_string_is_noop(self) -> None:
        out = hook.reconstruct_content(
            "Edit",
            {"old_string": "absent", "new_string": "z"},
            "status: in_review\n",
        )
        assert out == "status: in_review\n"

    def test_multiedit_applies_in_sequence(self) -> None:
        out = hook.reconstruct_content(
            "MultiEdit",
            {
                "edits": [
                    {"old_string": "a", "new_string": "b"},
                    {"old_string": "b", "new_string": "c"},
                ]
            },
            "a",
        )
        assert out == "c"


# ---------------------------------------------------------------------------
# End-to-end: subprocess invocation
# ---------------------------------------------------------------------------


class TestHookSubprocessAllow:
    def test_non_design_file_is_ignored(self, tmp_path: Path) -> None:
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(tmp_path / "notes.md"),
                    "content": "hello",
                },
            }
        )
        assert result.returncode == 0

    def test_write_new_valid_design_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(design_dict()),
                },
            }
        )
        assert result.returncode == 0, result.stderr

    def test_valid_transition_via_write_allowed(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", started_design(status="in_review"))
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(started_design(status="analyzing")),
                },
            }
        )
        assert result.returncode == 0, result.stderr

    def test_body_only_edit_on_terminal_design_allowed(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="supported"))
        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "title: Test design",
                    "new_string": "title: Edited design",
                },
            }
        )
        assert result.returncode == 0, result.stderr


class TestHookSubprocessBlock:
    def test_schema_violation_blocks(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        bad = design_dict(methodology={"method": ""})
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(path), "content": dump_yaml(bad)},
            }
        )
        assert result.returncode == 2
        assert "validation failed" in result.stderr.lower()

    def test_invalid_transition_via_write_blocks(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(design_dict(status="revision_requested")),
                },
            }
        )
        assert result.returncode == 2
        assert "transition" in result.stderr.lower()

    def test_rewriting_an_analyzing_confirmation_as_an_exploration_blocks(
        self, tmp_path: Path
    ) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        exploration = {
            "id": "FP-H01",
            "title": "Test design",
            "analysis_intent": "exploratory",
            "exploration_question": "How far apart are the regions?",
            "exploration_background": "Nobody has measured the spread",
            "status": "explored",
        }
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": dump_yaml(exploration),
                },
            }
        )
        assert result.returncode == 2
        assert "derive a new design" in result.stderr

    def test_invalid_transition_via_inplace_edit_blocks(self, tmp_path: Path) -> None:
        """The headline guard: editing status: in place to a move the table refuses."""
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "status: analyzing",
                    "new_string": "status: revision_requested",
                },
            }
        )
        assert result.returncode == 2
        assert "transition" in result.stderr.lower()

    def test_conclusion_from_analyzing_via_inplace_edit_passes(
        self, tmp_path: Path
    ) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict(status="analyzing"))
        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "status: analyzing",
                    "new_string": "status: inconclusive",
                },
            }
        )
        assert result.returncode == 0, result.stderr

    def test_malformed_yaml_blocks(self, tmp_path: Path) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(path),
                    "content": "status: [unclosed",
                },
            }
        )
        assert result.returncode == 2


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "MultiEdit"])
def test_hook_handles_all_three_tools(tmp_path: Path, tool_name: str) -> None:
    """All three intercepted tools reach a clean allow on a valid no-op change."""
    path = write_design(tmp_path, "FP-H01", design_dict(status="in_review"))
    if tool_name == "Write":
        tool_input = {"file_path": str(path), "content": dump_yaml(design_dict())}
    elif tool_name == "Edit":
        tool_input = {
            "file_path": str(path),
            "old_string": "title: Test design",
            "new_string": "title: Renamed",
        }
    else:
        tool_input = {
            "file_path": str(path),
            "edits": [{"old_string": "title: Test design", "new_string": "title: R"}],
        }
    result = run_hook({"tool_name": tool_name, "tool_input": tool_input})
    assert result.returncode == 0, result.stderr


class TestHookKeepsAStartedAnalysis:
    """Epic 33 US-3 AC 5: a direct write meets the checks design_io meets."""

    @pytest.fixture(params=["analyzing", "in_review", "revision_requested"])
    def started(self, tmp_path: Path, request: pytest.FixtureRequest) -> Path:
        design = started_design(status=request.param, analysis_started_at=MARK)
        return write_design(tmp_path, "FP-H01", design)

    def test_the_hypothesis_is_not_rewritten(self, started: Path) -> None:
        result = edit(started, "X improves Y", "X improves Y a little")
        assert result.returncode == 2
        assert "hypothesis_statement" in result.stderr
        assert "derive a new design" in result.stderr

    def test_the_criterion_is_not_rewritten(self, started: Path) -> None:
        result = edit(started, "2.0 days", "0.5 days")
        assert result.returncode == 2
        assert "metrics" in result.stderr
        assert "derive a new design" in result.stderr

    def test_the_mark_is_not_taken_away(self, started: Path) -> None:
        result = edit(started, f"analysis_started_at: '{MARK}'\n", "")
        assert result.returncode == 2
        assert "analysis_started_at" in result.stderr

    def test_the_background_is_still_edited(self, started: Path) -> None:
        result = edit(started, "Because Z", "Because Z, as surveyed")
        assert result.returncode == 0, result.stderr

    def test_a_saved_design_does_not_leave_the_analysis_without_the_mark(
        self, tmp_path: Path
    ) -> None:
        path = write_design(tmp_path, "FP-H01", started_design(status="analyzing"))
        result = edit(path, "status: analyzing", "status: in_review")
        assert result.returncode == 2
        assert "analysis_started_at" in result.stderr

    def test_a_design_without_a_criterion_is_not_moved_into_the_analysis(
        self, tmp_path: Path
    ) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict())
        result = edit(path, "status: in_review", "status: analyzing")
        assert result.returncode == 2
        assert "comparison" in result.stderr

    @pytest.mark.parametrize("verdict", ["supported", "rejected"])
    def test_a_design_without_a_criterion_takes_no_verdict_of_its_hypothesis(
        self, tmp_path: Path, verdict: str
    ) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict())
        result = edit(path, "status: in_review", f"status: {verdict}")
        assert result.returncode == 2
        assert "comparison" in result.stderr and "inconclusive" in result.stderr

    def test_a_design_without_a_criterion_is_closed_as_inconclusive(
        self, tmp_path: Path
    ) -> None:
        path = write_design(tmp_path, "FP-H01", design_dict())
        result = edit(path, "status: in_review", "status: inconclusive")
        assert result.returncode == 0, result.stderr

    def test_a_design_with_a_criterion_takes_its_verdict(self, tmp_path: Path) -> None:
        path = write_design(tmp_path, "FP-H01", started_design())
        result = edit(path, "status: in_review", "status: supported")
        assert result.returncode == 0, result.stderr


BROKEN = started_design(
    status="in_review", analysis_started_at=MARK, methodology={"method": ""}
)


def repair(path: Path, **changes: object) -> subprocess.CompletedProcess[str]:
    """Write the broken design back repaired, with *changes* in the same write."""
    data = BROKEN | {"methodology": {"method": "OLS"}} | changes
    return run_hook(write_tool(path, {k: v for k, v in data.items() if v is not None}))


class TestHookKeepsAStartedAnalysisOnABrokenRecord:
    """US-3 AC 5: a write over a broken record does not lift what is held."""

    @pytest.fixture
    def broken(self, tmp_path: Path) -> Path:
        return write_design(tmp_path, "FP-H01", BROKEN)

    def test_a_repair_alone_still_goes_through(self, broken: Path) -> None:
        result = repair(broken)
        assert result.returncode == 0, result.stderr

    def test_the_hypothesis_is_not_rewritten(self, broken: Path) -> None:
        result = repair(broken, hypothesis_statement="X improves Y a little")
        assert result.returncode == 2
        assert "hypothesis_statement" in result.stderr
        assert "derive a new design" in result.stderr

    def test_the_criterion_is_not_rewritten(self, broken: Path) -> None:
        looser = [{"target": "lead time", "comparison": "supported at 0.5 days"}]
        result = repair(broken, metrics=looser)
        assert result.returncode == 2
        assert "metrics" in result.stderr

    def test_the_primary_metric_is_not_lowered(self, broken: Path) -> None:
        lowered = [
            {"target": "lead time", "tier": "secondary", "comparison": CRITERION}
        ]
        result = repair(broken, metrics=lowered)
        assert result.returncode == 2
        assert "metrics" in result.stderr

    def test_the_mark_is_not_taken_away(self, broken: Path) -> None:
        result = repair(broken, analysis_started_at=None)
        assert result.returncode == 2
        assert "analysis_started_at" in result.stderr

    def test_a_primary_tier_left_out_is_the_same_criterion(self, broken: Path) -> None:
        result = repair(
            broken, metrics=[{"target": "lead time", "comparison": CRITERION}]
        )
        assert result.returncode == 0, result.stderr


class TestFailClosed:
    """On an internal error, design writes fail CLOSED; others fail open (M2)."""

    def _run_main_with_broken_evaluate(
        self, monkeypatch: pytest.MonkeyPatch, file_path: str
    ) -> int:
        from io import StringIO

        def boom(*_a: object, **_k: object) -> list[str]:
            raise RuntimeError("simulated hook bug")

        monkeypatch.setattr(hook, "evaluate", boom)
        payload = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": file_path}}
        )
        monkeypatch.setattr(hook.sys, "stdin", StringIO(payload))
        return hook.main()

    def test_design_write_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / ".insight" / "designs" / "FP-H01_hypothesis.yaml"
        assert self._run_main_with_broken_evaluate(monkeypatch, str(path)) == 2

    def test_non_design_write_fails_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "notes.md"
        assert self._run_main_with_broken_evaluate(monkeypatch, str(path)) == 0


# ---------------------------------------------------------------------------
# Question tree files (Epic 18, Story 18.1, US-2 AC 4)
# ---------------------------------------------------------------------------


def tree_dict() -> dict:
    question = "取り置き期限を延ばす試行をするか"
    return {
        "theme_id": "LIB",
        "root_revisions": [
            {
                "revision": 1,
                "question": question,
                "aim": {
                    "kind": "business",
                    "decision_maker": "図書館員",
                    "decision": "取り置き期限を延ばす試行を始めるか",
                },
            }
        ],
        "nodes": [{"id": "LIB-Q01", "question": question}],
    }


def tree_path(tmp_path: Path, theme_id: str = "LIB") -> Path:
    themes = tmp_path / ".insight" / "themes"
    themes.mkdir(parents=True, exist_ok=True)
    return themes / f"{theme_id}_tree.yaml"


def write_tool(path: Path, data: dict) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": dump_yaml(data)},
    }


class TestTreeThemeId:
    def test_reads_the_theme_from_a_tree_file_in_themes(self) -> None:
        assert hook.tree_theme_id("/p/.insight/themes/LIB_tree.yaml") == "LIB"

    def test_ignores_the_generated_html(self) -> None:
        assert hook.tree_theme_id("/p/.insight/themes/LIB_tree.html") is None

    def test_ignores_a_tree_file_outside_themes(self) -> None:
        assert hook.tree_theme_id("/p/.insight/designs/LIB_tree.yaml") is None

    def test_ignores_none(self) -> None:
        assert hook.tree_theme_id(None) is None


class TestHookSubprocessTree:
    def test_a_valid_tree_is_allowed(self, tmp_path: Path) -> None:
        result = run_hook(write_tool(tree_path(tmp_path), tree_dict()))
        assert result.returncode == 0, result.stderr

    def test_a_tree_that_stores_progress_is_blocked(self, tmp_path: Path) -> None:
        data = tree_dict()
        data["nodes"][0]["progress"] = "analyzed"

        result = run_hook(write_tool(tree_path(tmp_path), data))

        assert result.returncode == 2
        assert "progress" in result.stderr

    def test_a_theme_that_differs_from_the_file_name_is_blocked(
        self, tmp_path: Path
    ) -> None:
        result = run_hook(write_tool(tree_path(tmp_path, "FP"), tree_dict()))

        assert result.returncode == 2
        assert "does not match the file name" in result.stderr

    def test_an_edit_that_breaks_the_tree_is_blocked(self, tmp_path: Path) -> None:
        path = tree_path(tmp_path)
        path.write_text(dump_yaml(tree_dict()), encoding="utf-8")

        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "id: LIB-Q01",
                    "new_string": "id: LIB-Q01\n  parent_question_id: LIB-Q01",
                },
            }
        )

        assert result.returncode == 2
        assert "contribution" in result.stderr

    def test_a_write_that_drops_a_root_revision_is_blocked(
        self, tmp_path: Path
    ) -> None:
        path = tree_path(tmp_path)
        on_disk = tree_dict()
        second = {**on_disk["root_revisions"][0], "revision": 2, "reason": "x"}
        on_disk["root_revisions"].append(second)
        path.write_text(dump_yaml(on_disk), encoding="utf-8")

        result = run_hook(write_tool(path, tree_dict()))

        assert result.returncode == 2
        assert "cannot be removed" in result.stderr

    def test_a_write_that_drops_a_decision_is_blocked(self, tmp_path: Path) -> None:
        path = tree_path(tmp_path)
        on_disk = tree_dict()
        on_disk["decisions"] = [
            {"round": 0, "kind": "start", "node_id": "LIB-Q01", "reason": "根から"}
        ]
        path.write_text(dump_yaml(on_disk), encoding="utf-8")

        result = run_hook(write_tool(path, tree_dict()))

        assert result.returncode == 2
        assert "decision" in result.stderr

    def test_an_edit_that_rewrites_an_answer_is_blocked(self, tmp_path: Path) -> None:
        path = tree_path(tmp_path)
        on_disk = tree_dict()
        on_disk["nodes"].append(
            {
                "id": "LIB-Q02",
                "question": "期限切れを数えられるか",
                "parent_question_id": "LIB-Q01",
                "contribution": "件数が変わる",
                "answers": [
                    {
                        "round": 1,
                        "root_revision": 1,
                        "statements": [
                            {
                                "kind": "claim",
                                "text": "取消を除いて比べられた",
                                "cites": ["LIB-H01-E01"],
                            }
                        ],
                    }
                ],
            }
        )
        path.write_text(dump_yaml(on_disk), encoding="utf-8")

        result = run_hook(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "取消を除いて比べられた",
                    "new_string": "後から書き換えた",
                },
            }
        )

        assert result.returncode == 2
        assert "the answer of round 1 is history" in result.stderr

    def test_malformed_yaml_is_blocked(self, tmp_path: Path) -> None:
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(tree_path(tmp_path)),
                    "content": "nodes: [unclosed",
                },
            }
        )
        assert result.returncode == 2

    def test_a_tree_write_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = TestFailClosed()._run_main_with_broken_evaluate
        assert run(monkeypatch, str(tree_path(tmp_path))) == 2
