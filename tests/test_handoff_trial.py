"""Tests for scripts/handoff_trial.py, the handoff trial of a question tree (Epic 18, Story 18.8).

The trial hands the tree HTML of a synthetic scenario to a reader with no other
context and scores the six questions by the judgments the reader names (node,
event and design ids), not by wording. Synthetic data only: public-library
holds (theme LIB) and psychological safety (theme PSY, Epic 34, ADR-0059).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import NoneType
from typing import get_args

import pytest
import yaml
from pydantic import ValidationError

from insight_blueprint.models.design import (
    TERMINAL_STATUSES,
    AnalysisDesign,
    DesignForm,
    DesignStatus,
)
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
from skills._shared import design_io, tree_io
from skills._shared.tree_check import check_theme

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = "lib"
SCENARIOS = ("lib", "psy")


@pytest.fixture(scope="module", params=SCENARIOS)
def name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(scope="module")
def scenario(name: str) -> handoff_trial.Scenario:
    return load_scenario(name)


@pytest.fixture(scope="module")
def key(name: str) -> handoff_trial.Key:
    return load_key(name)


@pytest.fixture
def built(tmp_path: Path, scenario: handoff_trial.Scenario) -> Path:
    build(scenario, tmp_path)
    return tmp_path


def _key_answers(key: handoff_trial.Key) -> dict:
    """The key as a reader would answer it: the allowed extras are the key's own."""
    return key.answers.model_dump(mode="json", exclude={"q5": {"also_allowed"}})


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

    def test_a_decision_the_check_refuses_stops_the_build(
        self, tmp_path: Path, scenario: handoff_trial.Scenario
    ) -> None:
        """tree_io.decide writes nothing and returns the violations; build must not
        carry on as if the decision were written."""
        broken = scenario.model_copy(deep=True)
        last = broken.stages[-1].steps[-1]["decide"]
        last["cites"] = [f"{scenario.theme_id}-H09-E09"]

        with pytest.raises(ValueError, match="missing-event"):
            build(broken, tmp_path)

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
        self,
        tmp_path: Path,
        scenario: handoff_trial.Scenario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The page shows when the last journal event was written, so the time
        # is an input of the page (ADR-0036): two builds agree once it is fixed.
        fixed = datetime(2026, 11, 1, 10, 0, tzinfo=timezone(timedelta(hours=9)))
        monkeypatch.setattr("skills._shared.design_io.now_jst", lambda: fixed)
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

    def test_q3_splits_the_cited_events_by_the_kind_of_the_citing_statement(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        """Not by the journal direction: an exploration's evidence has none (ADR-0050)."""
        root = tree_io.load_tree_model(scenario.theme_id, built).root()
        answer = root.current_answer()
        assert answer is not None
        by_kind: dict[StatementKind, set[tuple[str, str]]] = {}
        for statement in answer.statements:
            for cite in statement.cites:
                by_kind.setdefault(statement.kind, set()).add(
                    (cite, tree_io.design_id_of(cite))
                )
        q3 = key.answers.q3
        assert {(r.event_id, r.design_id) for r in q3.supports} == by_kind[
            StatementKind.claim
        ]
        assert {(r.event_id, r.design_id) for r in q3.weakens} == by_kind[
            StatementKind.weakening
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

    def test_q5_reason_is_what_the_last_decision_cites(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        """ADR-0058: the reason's events come from the tree, not from whoever
        writes the key. The event the node was promoted from may be named too."""
        tree = tree_io.load_tree_model(scenario.theme_id, built)
        last = tree.decisions[-1]
        origin = tree.node(last.node_id).origin_event_id
        assert last.cites, "the scenario's last decision cites its reason"
        assert set(key.answers.q5.reason_events) == set(last.cites)
        assert set(key.answers.q5.also_allowed) == {origin} - set(last.cites) - {None}

    def test_q6_names_the_evidence_an_answer_above_now_cites_in_other_words(
        self, built: Path, scenario: handoff_trial.Scenario, key: handoff_trial.Key
    ) -> None:
        found = _q6_of(tree_io.load_tree_model(scenario.theme_id, built))
        assert set(key.answers.q6.nodes) == {n for n, _ in found}
        assert set(key.answers.q6.evidence) == {e for _, e in found}


def _q6_of(tree: QuestionTree) -> set[tuple[str, str]]:
    """A node left as it was, whose cited event an answer above it rewrote in the
    last round: cited before and now, by different statements (ADR-0056's
    reworded). An event the answer above stopped citing, or first cites in the
    last round, is not one.

    Written apart from ``tree_changes.cited_above`` on purpose: the page shows
    that one, so a key derived from it would agree with the page even when the
    rule itself is wrong (ADR-0059's Negative).
    """
    last = tree.current_round()
    parents = {n.id: n.parent_question_id for n in tree.nodes}
    by_id = {n.id: n for n in tree.nodes}

    def citing(statements: list, event: str) -> set[tuple]:
        return {(s.kind, s.text) for s in statements if event in s.cites}

    found: set[tuple[str, str]] = set()
    for node in tree.nodes:
        if not node.answers or node.answers[-1].round == last:
            continue
        events = {c for s in node.answers[-1].statements for c in s.cites}
        above = parents[node.id]
        while above is not None:
            answers = by_id[above].answers
            if len(answers) > 1 and answers[-1].round == last:
                for event in events:
                    before = citing(answers[-2].statements, event)
                    after = citing(answers[-1].statements, event)
                    if before and after and before != after:
                        found.add((node.id, event))
            above = parents[above]
    return found


class TestTheQ6Rule:
    """The shapes of q6 the two scenarios do not hold (34.2's review): the rule
    is the one the key test derives with, so a shape it misses is caught here."""

    @staticmethod
    def _tree(root_before: list[dict], root_now: list[dict]) -> QuestionTree:
        def answer(round: int, statements: list[dict]) -> dict:
            return {"round": round, "root_revision": 1, "statements": statements}

        said = {"kind": "claim", "text": "相関は0.41", "cites": ["PSY-H01-E01"]}
        return QuestionTree.model_validate(
            {
                "theme_id": "PSY",
                "root_revisions": [
                    {
                        "revision": 1,
                        "question": "上司への働きかけを優先すべきか",
                        "aim": {
                            "kind": "business",
                            "decision_maker": "人事",
                            "decision": "優先するか",
                        },
                    }
                ],
                "nodes": [
                    {
                        "id": "PSY-Q01",
                        "question": "上司への働きかけを優先すべきか",
                        "answers": [answer(1, root_before), answer(2, root_now)],
                    },
                    {
                        "id": "PSY-Q02",
                        "question": "関連はあるか",
                        "parent_question_id": "PSY-Q01",
                        "contribution": "無ければ外す",
                        "answers": [answer(1, [said])],
                    },
                ],
            }
        )

    def test_an_event_cited_in_other_words_is_named(self) -> None:
        before = [{"kind": "claim", "text": "候補に残る", "cites": ["PSY-H01-E01"]}]
        now = [
            {"kind": "weakening", "text": "負荷で説明できる", "cites": ["PSY-H01-E01"]}
        ]

        assert _q6_of(self._tree(before, now)) == {("PSY-Q02", "PSY-H01-E01")}

    def test_an_event_the_answer_above_first_cites_in_the_last_round_is_not(
        self,
    ) -> None:
        before = [{"kind": "claim", "text": "別の結果", "cites": ["PSY-H02-E01"]}]
        now = [{"kind": "claim", "text": "候補に残る", "cites": ["PSY-H01-E01"]}]

        assert _q6_of(self._tree(before, now)) == set()

    def test_an_event_the_answer_above_stops_citing_is_not(self) -> None:
        before = [{"kind": "claim", "text": "候補に残る", "cites": ["PSY-H01-E01"]}]
        now = [{"kind": "claim", "text": "別の結果", "cites": ["PSY-H02-E01"]}]

        assert _q6_of(self._tree(before, now)) == set()


class TestTheScenarioHasBothForms:
    """US-4 AC 5: the tree shows an exploration, a confirmation and a verdict apart
    from the answer of its node."""

    @pytest.fixture
    def built(self, tmp_path: Path) -> Path:
        build(load_scenario("lib"), tmp_path)
        return tmp_path

    def _designs(self, built: Path) -> list[AnalysisDesign]:
        return [
            AnalysisDesign.model_validate(
                design_io.load_design(p.stem.split("_")[0], built)
            )
            for p in sorted((built / "designs").glob("*_hypothesis.yaml"))
        ]

    def test_the_scenario_holds_an_exploration_and_a_confirmation(
        self, built: Path
    ) -> None:
        forms = {d.form() for d in self._designs(built)}
        assert {DesignForm.exploration, DesignForm.confirmation} <= forms

    def test_a_node_has_a_verdict_that_differs_from_its_current_answer(
        self, built: Path
    ) -> None:
        tree = tree_io.load_tree_model("LIB", built)
        designs = {d.id: d for d in self._designs(built)}
        decided = {DesignStatus.supported, DesignStatus.rejected}
        differing = [
            n.id
            for n in tree.nodes
            if (a := n.current_answer()) is not None
            and any(s.kind is StatementKind.undetermined for s in a.statements)
            and any(
                designs[d].form() is DesignForm.confirmation
                and designs[d].status in decided
                for d in n.design_ids
            )
        ]
        assert len(differing) == 1

    def test_the_page_words_each_design_by_its_form(self, built: Path) -> None:
        html = (built / "themes" / "LIB_tree.html").read_text()

        assert "分析設計・探索" in html
        assert "探索済み（判定はしない）" in html
        assert "分析設計・検証" in html
        assert "検証仮説の判定: 支持" in html


class TestTheSecondScenario:
    """Epic 34 US-6 AC 1: psy holds an analysis that found no difference, and a
    node whose answer and numbers stay while the answer above cites them in
    other words."""

    @pytest.fixture
    def built(self, tmp_path: Path) -> Path:
        build(load_scenario("psy"), tmp_path)
        return tmp_path

    def _designs(self, built: Path) -> list[AnalysisDesign]:
        return [
            AnalysisDesign.model_validate(
                design_io.load_design(p.stem.split("_")[0], built)
            )
            for p in sorted((built / "designs").glob("*_hypothesis.yaml"))
        ]

    def test_it_has_a_rejected_confirmation_the_root_answer_never_cites(
        self, built: Path
    ) -> None:
        tree = tree_io.load_tree_model("PSY", built)
        rejected = {
            d.id
            for d in self._designs(built)
            if d.form() is DesignForm.confirmation and d.status is DesignStatus.rejected
        }
        root_cites = {
            tree_io.design_id_of(c)
            for a in tree.root().answers
            for s in a.statements
            for c in s.cites
        }
        assert len(rejected) == 1
        assert not rejected & root_cites

    def test_no_analysis_is_left_unfinished(self, built: Path) -> None:
        """ADR-0059: a stopped analysis is checked by the display tests, not here."""
        assert all(d.status in TERMINAL_STATUSES for d in self._designs(built))

    def test_q6_has_an_answer(self) -> None:
        q6 = load_key("psy").answers.q6
        assert q6.nodes
        assert q6.evidence

    def test_the_library_has_none(self) -> None:
        q6 = load_key("lib").answers.q6
        assert (q6.nodes, q6.evidence) == ([], [])

    def test_every_name_and_number_is_said_to_be_made_up(self) -> None:
        for file in ("stages.yaml", "key.yaml"):
            head = (handoff_trial.FIXTURES / "psy" / file).read_text().splitlines()[:6]
            assert any("made up" in line for line in head), file


class TestTheKey:
    def test_a_key_that_leaves_a_question_out_is_refused_when_read(
        self, key: handoff_trial.Key
    ) -> None:
        partial = key.model_dump(mode="json")
        del partial["answers"]["q6"]
        with pytest.raises(ValidationError, match="q6"):
            handoff_trial.Key.model_validate(partial)


class TestScore:
    """AC 2: scored by the judgment, never by the wording. A wrong answer names
    ids of the scenario it scores, so each scenario is really put to the test."""

    def test_the_key_itself_is_right_on_every_question(
        self, key: handoff_trial.Key
    ) -> None:
        assert score(key.answers, key) == dict.fromkeys(QUESTIONS, True)

    def test_one_wrong_judgment_marks_only_its_question(
        self, key: handoff_trial.Key, name: str
    ) -> None:
        wrong = _key_answers(key)
        wrong["q5"]["node_id"] = f"{name.upper()}-Q04"
        assert wrong["q5"]["node_id"] != key.answers.q5.node_id
        result = score(Answers.model_validate(wrong), key)
        assert result == dict.fromkeys(QUESTIONS, True) | {"q5": False}

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

    def test_a_reason_may_also_name_an_allowed_event(
        self, key: handoff_trial.Key
    ) -> None:
        more = _key_answers(key)
        more["q5"]["reason_events"] += key.answers.q5.also_allowed
        assert score(Answers.model_validate(more), key)["q5"] is True

    def test_a_reason_naming_only_an_allowed_event_is_wrong(
        self, key: handoff_trial.Key
    ) -> None:
        only = _key_answers(key)
        only["q5"]["reason_events"] = list(key.answers.q5.also_allowed)
        assert score(Answers.model_validate(only), key)["q5"] is False

    def test_naming_every_event_is_wrong(
        self, key: handoff_trial.Key, name: str
    ) -> None:
        hedged = _key_answers(key)
        others = [f"{name.upper()}-H01-E01", f"{name.upper()}-H02-E01"]
        assert not set(others) & set(key.answers.q5.reason_events)
        hedged["q5"]["reason_events"] += [*key.answers.q5.also_allowed, *others]
        assert score(Answers.model_validate(hedged), key)["q5"] is False

    def test_a_reason_without_the_key_events_is_wrong(
        self, key: handoff_trial.Key, name: str
    ) -> None:
        other = _key_answers(key)
        assert f"{name.upper()}-H01-E01" not in key.answers.q5.reason_events
        other["q5"]["reason_events"] = [f"{name.upper()}-H01-E01"]
        assert score(Answers.model_validate(other), key)["q5"] is False

    def test_a_node_too_many_is_wrong(self, key: handoff_trial.Key, name: str) -> None:
        extra = _key_answers(key)
        assert f"{name.upper()}-Q02" not in key.answers.q2.not_started
        extra["q2"]["not_started"].append(f"{name.upper()}-Q02")
        assert score(Answers.model_validate(extra), key)["q2"] is False


class TestParseAnswers:
    def test_a_fenced_json_reply_is_read(self, key: handoff_trial.Key) -> None:
        text = "```json\n" + json.dumps(_key_answers(key), ensure_ascii=False) + "\n```"
        assert parse_answers(text).model_dump(mode="json") == _key_answers(key)

    @pytest.mark.parametrize("fence", ["```", "```JSON", "```jsonc"])
    def test_any_fence_label_is_read(self, key: handoff_trial.Key, fence: str) -> None:
        text = fence + "\n" + json.dumps(_key_answers(key)) + "\n```"
        assert parse_answers(text).model_dump(mode="json") == _key_answers(key)

    def test_prose_around_the_fence_is_ignored(self, key: handoff_trial.Key) -> None:
        body = json.dumps(_key_answers(key))
        text = f"答えは次のとおり。\n```json\n{body}\n```\n以上。"
        assert parse_answers(text).model_dump(mode="json") == _key_answers(key)

    def test_a_reply_that_is_not_json_is_refused(self) -> None:
        with pytest.raises(ValueError):
            parse_answers("分かりません")


class TestPrompt:
    def test_the_prompt_asks_every_question_then_gives_only_the_html(self) -> None:
        html = "<!doctype html><p>tree</p>"
        prompt = prompt_for(html)
        assert prompt.endswith(html)
        head = prompt[: -len(html)]
        assert QUESTIONS == tuple(Answers.model_fields)
        for n in range(1, len(QUESTIONS) + 1):
            assert f"\n{n}. " in head
        for question, info in Answers.model_fields.items():
            assert f'"{question}"' in head
            reader_type = next(
                t for t in get_args(info.annotation) if t is not NoneType
            )
            for field in reader_type.model_fields:
                assert f'"{field}"' in head, f"{question}.{field}"
        for field in handoff_trial.EventRef.model_fields:
            assert f'"{field}"' in head

    def test_the_prompt_uses_the_words_the_analyst_sees(self) -> None:
        """Epic 34 US-5: the subject, and the kinds of statement q1 names."""
        head = prompt_for("")
        for word in (
            "主題",
            "これまでわかっていること（claim）",
            "まだ決められないこと（undetermined）",
        ):
            assert word in head
        assert not re.search("根(?!拠)", head)
        assert "未判別" not in head


class TestRecord:
    """AC 3: the record keeps the answers, right or wrong, and the time taken."""

    @pytest.fixture
    def key(self) -> handoff_trial.Key:
        return load_key(SCENARIO)

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

    @pytest.mark.parametrize(
        "kept",
        sorted((REPO_ROOT / "docs" / "handoff-trials").glob("*.yaml")),
        ids=lambda p: p.stem,
    )
    def test_a_kept_record_still_reads(self, kept: Path) -> None:
        """ADR-0035: a record is read as it was scored, from before q6 too."""
        record = Record.model_validate(yaml.safe_load(kept.read_text(encoding="utf-8")))
        assert set(record.score) <= set(QUESTIONS)


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
    @pytest.fixture
    def key(self) -> handoff_trial.Key:
        return load_key(SCENARIO)

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
        assert sum(record.score.values()) == len(QUESTIONS) - 1
        assert "q1" in done.stdout

    def test_record_refuses_a_reply_that_is_not_json(self, tmp_path: Path) -> None:
        reply = tmp_path / "reply.txt"
        reply.write_text("分かりません", encoding="utf-8")
        out = tmp_path / "record.yaml"
        done = _record_cli(reply, out)
        assert done.returncode == 1
        assert not out.exists()
