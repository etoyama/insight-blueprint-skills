"""Tests for scripts/handoff_trial.py, the handoff trial of a question tree (Epic 18, Story 18.8).

The trial hands the tree HTML of a synthetic scenario to a reader with no other
context and scores the five questions of the PRD success criteria by the
judgments the reader names (node, event and design ids), not by wording.
Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from insight_blueprint.models.tree import Progress, QuestionTree, StatementKind
from scripts import handoff_trial
from scripts.handoff_trial import (
    QUESTIONS,
    Answers,
    Record,
    build,
    load_key,
    load_scenario,
    parse_answers,
    prompt_for,
    score,
)
from skills._shared import tree_io
from skills._shared.tree_check import check_theme

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = "lib"
RECORDS = sorted((REPO_ROOT / "docs/handoff-trials").glob("*.yaml"))


@pytest.fixture(scope="module")
def scenario() -> handoff_trial.Scenario:
    return load_scenario(SCENARIO)


@pytest.fixture(scope="module")
def key() -> handoff_trial.Key:
    return load_key(SCENARIO)


@pytest.fixture
def built(tmp_path: Path, scenario: handoff_trial.Scenario) -> Path:
    build(scenario, tmp_path)
    return tmp_path


def _key_answers(key: handoff_trial.Key) -> dict:
    return key.answers.model_dump(mode="json")


class TestStages:
    """AC 1: what was known at the start, then the observations, stage by stage."""

    def test_the_first_stage_is_what_was_known_at_the_start(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        build(scenario, tmp_path, through=scenario.stages[0].id)
        tree = tree_io.load_tree_model(scenario.theme_id, tmp_path)
        assert [d.kind.value for d in tree.decisions] == ["start"]
        assert all(not n.answers and not n.design_ids for n in tree.nodes)
        assert len(tree.nodes) > 1
        assert all(n.parent_question_id in (None, tree.root().id) for n in tree.nodes)
        assert not list(tmp_path.glob("designs/*"))

    def test_each_later_stage_is_one_reflection_round(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        for n, stage in enumerate(scenario.stages):
            out = tmp_path / stage.id
            build(scenario, out, through=stage.id)
            tree = tree_io.load_tree_model(scenario.theme_id, out)
            assert tree.current_round() == n

    def test_a_later_stage_only_adds_to_the_earlier_one(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        earlier, later = tmp_path / "earlier", tmp_path / "later"
        build(scenario, earlier, through=scenario.stages[1].id)
        build(scenario, later)
        before = tree_io.load_tree_model(scenario.theme_id, earlier)
        after = tree_io.load_tree_model(scenario.theme_id, later)

        def decisions(tree: QuestionTree) -> list[tuple]:
            return [(d.round, d.kind, d.node_id, d.reason) for d in tree.decisions]

        def answers(tree: QuestionTree) -> dict[str, list]:
            return {n.id: [a.statements for a in n.answers] for n in tree.nodes}

        assert decisions(after)[: len(before.decisions)] == decisions(before)
        assert [n.id for n in after.nodes][: len(before.nodes)] == [
            n.id for n in before.nodes
        ]
        for node_id, earlier_answers in answers(before).items():
            assert answers(after)[node_id][: len(earlier_answers)] == earlier_answers

    def test_every_stage_has_a_summary_for_the_human_reader(
        self, scenario: handoff_trial.Scenario
    ) -> None:
        assert all(stage.summary.strip() for stage in scenario.stages)

    def test_an_unknown_stage_is_refused(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        with pytest.raises(ValueError, match="no-such-stage"):
            build(scenario, tmp_path, through="no-such-stage")

    def test_a_wrong_argument_names_the_stage_and_the_step(
        self, tmp_path: Path
    ) -> None:
        scenario = handoff_trial.Scenario.model_validate(
            {
                "theme_id": "LIB",
                "stages": [
                    {
                        "id": "start",
                        "summary": "x",
                        "steps": [{"create_tree": {"q": 1}}],
                    }
                ],
            }
        )
        with pytest.raises(ValueError, match="start.*create_tree"):
            build(scenario, tmp_path)

    def test_an_unknown_step_is_refused_before_anything_is_written(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValidationError):
            handoff_trial.Scenario.model_validate(
                {
                    "theme_id": "LIB",
                    "stages": [
                        {"id": "start", "summary": "x", "steps": [{"rm_rf": {}}]}
                    ],
                }
            )


class TestTheBuiltTree:
    def test_the_last_stage_passes_the_tree_check(
        self, built: Path, scenario: handoff_trial.Scenario
    ) -> None:
        assert check_theme(scenario.theme_id, built) == []

    def test_the_html_is_the_same_bytes_every_time(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        first = build(scenario, tmp_path / "a").read_bytes()
        second = build(scenario, tmp_path / "b").read_bytes()
        assert first == second

    def test_a_directory_it_did_not_build_is_never_removed(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="not built by"):
            build(scenario, tmp_path)
        assert (tmp_path / "keep.txt").exists()

    def test_an_empty_directory_may_be_built_into(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        assert build(scenario, tmp_path).exists()

    def test_building_again_into_the_same_directory_starts_over(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        build(scenario, tmp_path)
        html = build(scenario, tmp_path)
        assert html == tmp_path / "themes" / f"{scenario.theme_id}_tree.html"


class TestTheKeyHoldsForTheTree:
    """The key is checked against the built tree, so it cannot drift from the fixture."""

    def test_the_key_is_for_the_last_stage(
        self, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        assert key.stage == scenario.stages[-1].id

    def test_q1_is_the_verdict_of_the_root_answer(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        root = tree_io.load_tree_model(scenario.theme_id, built).root()
        answer = root.current_answer()
        assert answer is not None
        kinds = {s.kind for s in answer.statements}
        expected = "undetermined" if StatementKind.undetermined in kinds else "claim"
        assert key.answers.q1.verdict == expected

    def test_q2_splits_untouched_nodes_from_analyzed_but_undetermined(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        tree = tree_io.load_tree_model(scenario.theme_id, built)
        progress = tree_io.progress(scenario.theme_id, built)
        undetermined = {
            n.id
            for n in tree.nodes
            if n.parent_question_id is not None
            and progress[n.id] == Progress.analyzed.value
            and (a := n.current_answer()) is not None
            and any(s.kind is StatementKind.undetermined for s in a.statements)
        }
        assert set(key.answers.q2.not_started) == {n.id for n in tree.untouched_nodes()}
        assert set(key.answers.q2.analyzed_undetermined) == undetermined
        assert undetermined, "the scenario needs an analyzed but undetermined node"

    def test_q3_names_the_events_the_root_answer_cites_by_direction(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        root = tree_io.load_tree_model(scenario.theme_id, built).root()
        answer = root.current_answer()
        assert answer is not None
        cited = {e for s in answer.statements for e in s.cites}
        by_direction: dict[str, set[tuple[str, str]]] = {}
        for event in tree_io.cited_journal_events(cited, built):
            pair = (event["id"], tree_io.design_id_of(event["id"]))
            by_direction.setdefault(event["metadata"]["direction"], set()).add(pair)
        q3 = key.answers.q3
        assert {(r.event_id, r.design_id) for r in q3.supports} == by_direction[
            "supports"
        ]
        assert {(r.event_id, r.design_id) for r in q3.weakens} == by_direction[
            "contradicts"
        ]

    def test_q4_names_the_answers_rewritten_in_the_last_round(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        tree = tree_io.load_tree_model(scenario.theme_id, built)
        last = tree.current_round()
        changed = {
            n.id
            for n in tree.nodes
            if len(n.answers) > 1
            and n.answers[-1].round == last
            and n.answers[-1].statements != n.answers[-2].statements
        }
        assert set(key.answers.q4.changed_nodes) == changed
        new_cites = {
            e
            for n in tree.nodes
            if n.id in changed
            for e in {c for s in n.answers[-1].statements for c in s.cites}
            - {c for s in n.answers[-2].statements for c in s.cites}
        }
        assert set(key.answers.q4.evidence) == new_cites
        first_answered = [
            n.id
            for n in tree.nodes
            if len(n.answers) == 1 and n.answers[0].round == last
        ]
        assert first_answered, "the scenario needs a node answered for the first time"

    def test_q5_is_the_node_of_the_last_decision(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        tree = tree_io.load_tree_model(scenario.theme_id, built)
        assert key.answers.q5.node_id == tree.decisions[-1].node_id
        assert key.answers.q5.reason_events


class TestTheKey:
    def test_a_key_that_leaves_a_question_out_is_refused_when_read(
        self, key: handoff_trial.Key
    ) -> None:
        partial = key.model_dump(mode="json")
        del partial["answers"]["q5"]
        with pytest.raises(ValidationError, match="q5"):
            handoff_trial.Key.model_validate(partial)


class TestScore:
    """AC 2: scored by the judgment, never by the wording."""

    def test_the_key_itself_is_right_on_every_question(
        self, key: handoff_trial.Key
    ) -> None:
        assert score(key.answers, key) == dict.fromkeys(QUESTIONS, True)

    def test_one_wrong_judgment_marks_only_its_question(
        self, key: handoff_trial.Key
    ) -> None:
        wrong = _key_answers(key)
        wrong["q5"]["node_id"] = "LIB-Q04"
        result = score(Answers.model_validate(wrong), key)
        assert result == {"q1": True, "q2": True, "q3": True, "q4": True, "q5": False}

    def test_the_order_and_the_note_do_not_count(self, key: handoff_trial.Key) -> None:
        reworded = _key_answers(key)
        for q in reworded.values():
            q["note"] = "まったく違う言い回しの説明"
        reworded["q2"]["not_started"].reverse()
        assert all(score(Answers.model_validate(reworded), key).values())

    def test_a_missing_question_is_wrong(self, key: handoff_trial.Key) -> None:
        partial = _key_answers(key)
        del partial["q3"]
        assert score(Answers.model_validate(partial), key)["q3"] is False

    def test_a_reason_may_name_more_events_than_the_key(
        self, key: handoff_trial.Key
    ) -> None:
        more = _key_answers(key)
        more["q5"]["reason_events"].append("LIB-H02-E03")
        assert score(Answers.model_validate(more), key)["q5"] is True

    def test_a_reason_without_the_key_events_is_wrong(
        self, key: handoff_trial.Key
    ) -> None:
        other = _key_answers(key)
        other["q5"]["reason_events"] = ["LIB-H01-E01"]
        assert score(Answers.model_validate(other), key)["q5"] is False

    def test_a_node_too_many_is_wrong(self, key: handoff_trial.Key) -> None:
        extra = _key_answers(key)
        extra["q2"]["not_started"].append("LIB-Q02")
        assert score(Answers.model_validate(extra), key)["q2"] is False


class TestParseAnswers:
    def test_a_fenced_json_reply_is_read(self, key: handoff_trial.Key) -> None:
        text = "```json\n" + json.dumps(_key_answers(key), ensure_ascii=False) + "\n```"
        assert parse_answers(text).model_dump() == key.answers.model_dump()

    @pytest.mark.parametrize("fence", ["```", "```JSON", "```jsonc"])
    def test_any_fence_label_is_read(self, key: handoff_trial.Key, fence: str) -> None:
        text = fence + "\n" + json.dumps(_key_answers(key)) + "\n```"
        assert parse_answers(text).model_dump() == key.answers.model_dump()

    def test_prose_around_the_fence_is_ignored(self, key: handoff_trial.Key) -> None:
        body = json.dumps(_key_answers(key))
        text = f"答えは次のとおり。\n```json\n{body}\n```\n以上。"
        assert parse_answers(text).model_dump() == key.answers.model_dump()

    def test_a_reply_that_is_not_json_is_refused(self) -> None:
        with pytest.raises(ValueError):
            parse_answers("分かりません")


class TestPrompt:
    def test_the_prompt_asks_the_five_questions_then_gives_only_the_html(self) -> None:
        html = "<!doctype html><p>tree</p>"
        prompt = prompt_for(html)
        assert prompt.endswith(html)
        head = prompt[: -len(html)]
        for n in range(1, 6):
            assert f"\n{n}. " in head
        for question, info in handoff_trial.KeyAnswers.model_fields.items():
            assert f'"{question}"' in head
            assert info.annotation is not None
            for field in info.annotation.model_fields:
                assert f'"{field}"' in head, f"{question}.{field}"
        for field in handoff_trial.EventRef.model_fields:
            assert f'"{field}"' in head


class TestRecord:
    """AC 3: the record keeps the five answers, right or wrong, and the time taken."""

    def _record(self, key: handoff_trial.Key, **over: object) -> dict:
        return {
            "date": "2026-11-21",
            "scenario": SCENARIO,
            "stage": key.stage,
            "reader": {"kind": "human", "name": "開発者"},
            "minutes": {"confirm": 4, "reconstruct": 6},
            "answers": _key_answers(key),
            "score": dict.fromkeys(QUESTIONS, True),
        } | over

    def test_a_human_record_needs_both_times(self, key: handoff_trial.Key) -> None:
        with pytest.raises(ValidationError, match="minutes"):
            Record.model_validate(
                self._record(key, minutes={"confirm": 4, "reconstruct": None})
            )

    def test_a_claude_record_has_no_times(self, key: handoff_trial.Key) -> None:
        record = Record.model_validate(
            self._record(
                key,
                reader={"kind": "claude", "name": "sonnet"},
                minutes={"confirm": None, "reconstruct": None},
            )
        )
        assert record.minutes.confirm is None

    def test_a_claude_record_with_a_time_is_refused(
        self, key: handoff_trial.Key
    ) -> None:
        with pytest.raises(ValidationError, match="minutes"):
            Record.model_validate(
                self._record(key, reader={"kind": "claude", "name": "sonnet"})
            )

    def test_an_unknown_field_is_refused(self, key: handoff_trial.Key) -> None:
        with pytest.raises(ValidationError):
            Record.model_validate(self._record(key, comment="x"))

    def test_a_record_for_another_stage_than_the_key_is_refused(
        self, key: handoff_trial.Key
    ) -> None:
        record = Record.model_validate(self._record(key, stage="start"))
        with pytest.raises(ValueError, match="stage"):
            handoff_trial.rescore(record)

    @pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.name)
    def test_every_kept_record_has_the_score_its_answers_get(self, path: Path) -> None:
        record = Record.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert record.score == handoff_trial.rescore(record)

    def test_at_least_one_record_is_kept(self) -> None:
        assert RECORDS


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.handoff_trial", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def _record_cli(reply: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return _cli(
        "record",
        "--scenario",
        SCENARIO,
        "--answers",
        str(reply),
        "--reader-kind",
        "claude",
        "--reader-name",
        "sonnet",
        "--date",
        "2026-11-21",
        "--out",
        str(out),
    )


class TestCli:
    def test_build_writes_the_html_and_prints_its_path(self, tmp_path: Path) -> None:
        done = _cli("build", "--scenario", SCENARIO, "--out", str(tmp_path))
        assert done.returncode == 0, done.stderr
        assert (
            Path(done.stdout.strip())
            .read_text(encoding="utf-8")
            .startswith("<!doctype html>")
        )

    def test_a_missing_scenario_is_an_error_not_a_traceback(
        self, tmp_path: Path
    ) -> None:
        done = _cli(
            "build", "--scenario", "../../tmp/none", "--out", str(tmp_path / "o")
        )
        assert done.returncode == 1
        assert "Traceback" not in done.stderr

    def test_prompt_prints_the_prompt_for_a_file(self, tmp_path: Path) -> None:
        page = tmp_path / "t.html"
        page.write_text("<!doctype html><p>x</p>", encoding="utf-8")
        done = _cli("prompt", "--html", str(page))
        assert done.returncode == 0, done.stderr
        assert done.stdout == prompt_for(page.read_text(encoding="utf-8"))

    def test_record_scores_a_reply_and_writes_the_record(
        self, tmp_path: Path, key: handoff_trial.Key
    ) -> None:
        reply = tmp_path / "reply.txt"
        wrong = _key_answers(key)
        wrong["q1"]["verdict"] = "claim"
        reply.write_text("```json\n" + json.dumps(wrong) + "\n```", encoding="utf-8")
        out = tmp_path / "record.yaml"
        done = _record_cli(reply, out)
        assert done.returncode == 0, done.stderr
        record = Record.model_validate(yaml.safe_load(out.read_text(encoding="utf-8")))
        assert record.score["q1"] is False
        assert sum(record.score.values()) == 4
        assert "q1" in done.stdout

    def test_record_refuses_a_reply_that_is_not_json(self, tmp_path: Path) -> None:
        reply = tmp_path / "reply.txt"
        reply.write_text("分かりません", encoding="utf-8")
        out = tmp_path / "record.yaml"
        done = _record_cli(reply, out)
        assert done.returncode == 1
        assert not out.exists()
