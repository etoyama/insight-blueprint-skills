"""The handoff trial of a question tree (Epic 18, Story 18.8; docs/HANDOFF_TRIAL.md).

A reader with no other context gets the tree HTML of a synthetic scenario and
answers six questions: the five of the PRD success criteria and, since Epic 34
(ADR-0059), the evidence an answer above now cites in other words. The answers
name judgments by id, so scoring compares judgments and never wording.

Usage, from the repository root:
    python -m scripts.handoff_trial build --scenario lib|psy --out DIR [--through STAGE]
    python -m scripts.handoff_trial prompt --html PATH
    python -m scripts.handoff_trial record --scenario lib|psy --answers PATH \\
        --reader-kind claude|human --reader-name NAME [--reader-model ID] \\
        --date YYYY-MM-DD \\
        [--minutes-confirm N --minutes-reconstruct N] --out PATH
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from skills._shared import design_io, tree_io

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "handoff"
QUESTIONS = ("q1", "q2", "q3", "q4", "q5", "q6")
# Written into every directory build fills, so build never removes one it did not make.
BUILT_MARK = ".handoff-trial"


def _answer(*, theme_id: str, answers: list[dict], base_dir: Path) -> dict:
    result = tree_io.answer(theme_id, answers=answers, base_dir=base_dir)
    if result["violations"]:
        raise ValueError(f"the scenario's answers fail the tree check: {result}")
    return result


def _decide(*, theme_id: str, base_dir: Path, **decision: Any) -> dict:
    # decide writes nothing when its cites fail the check, and says so only in
    # what it returns: carrying on would build a tree without that decision.
    result = tree_io.decide(theme_id, **decision, base_dir=base_dir)
    if "violations" in result:
        raise ValueError(f"the scenario's decision fails the tree check: {result}")
    return result


# Step name -> (function, whether it takes the theme). The YAML names the function.
STEPS: dict[str, tuple[Callable[..., object], bool]] = {
    "create_tree": (tree_io.create_tree, True),
    "add_node": (tree_io.add_node, True),
    "decide": (_decide, True),
    "link_design": (tree_io.link_design, True),
    "answer": (_answer, True),
    "candidate": (tree_io.candidate, True),
    "hear": (tree_io.hear, True),
    "create_design": (design_io.create_design, True),
    "append_journal_event": (design_io.append_journal_event, False),
    "transition_status": (design_io.transition_status, False),
}


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    steps: list[dict[str, dict[str, Any]]]

    @field_validator("steps")
    @classmethod
    def _known_steps(cls, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for step in steps:
            if len(step) != 1 or next(iter(step)) not in STEPS:
                raise ValueError(f"a step is one of {sorted(STEPS)}, got {list(step)}")
        return steps


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_id: str
    stages: list[Stage] = Field(min_length=1)


def _same(a: object, b: object) -> bool:
    """Lists are compared as sets, so their order never counts."""
    if isinstance(a, list) and isinstance(b, list):
        return set(a) == set(b)
    return a == b


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = ""

    def accepts(self, answer: _Question) -> bool:
        """As the key: every field of *answer* but the note equals this one's."""
        return all(
            _same(getattr(answer, f), getattr(self, f))
            for f in type(answer).model_fields
            if f != "note"
        )


class Q1(_Question):
    verdict: Literal["claim", "undetermined"]


class Q2(_Question):
    not_started: list[str]
    analyzed_undetermined: list[str]


class EventRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    design_id: str


class Q3(_Question):
    supports: list[EventRef]
    weakens: list[EventRef]


class Q4(_Question):
    changed_nodes: list[str]
    evidence: list[str]


class Q5(_Question):
    node_id: str
    reason_events: list[str]


class KeyQ5(Q5):
    """The q5 key: the events the last decision cites (ADR-0058). A reader may
    rightly name an event next to them too, such as the node's origin."""

    also_allowed: list[str] = []

    def accepts(self, answer: _Question) -> bool:
        if not isinstance(answer, Q5):
            return False
        named = set(answer.reason_events)
        return (
            answer.node_id == self.node_id
            and set(self.reason_events) <= named
            and named <= set(self.reason_events) | set(self.also_allowed)
        )


class Q6(_Question):
    """Nodes whose answer and numbers stayed while an answer above them now cites
    their evidence in other words, and that evidence. Both empty when none."""

    nodes: list[str]
    evidence: list[str]


class Answers(BaseModel):
    """The reader's answers. A question left out is scored wrong, not refused."""

    model_config = ConfigDict(extra="forbid")

    q1: Q1 | None = None
    q2: Q2 | None = None
    q3: Q3 | None = None
    q4: Q4 | None = None
    q5: Q5 | None = None
    q6: Q6 | None = None


class KeyAnswers(Answers):
    """The key answers every question."""

    q1: Q1
    q2: Q2
    q3: Q3
    q4: Q4
    q5: KeyQ5
    q6: Q6


class Key(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    answers: KeyAnswers


class Reader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["human", "claude"]
    name: str
    # The alias in `name` (`sonnet`) moves to a new version without a trace, so two
    # trials can only be compared when the id is kept. Optional because the records
    # kept before ADR-0060 have none and are not rewritten (ADR-0035).
    model: str | None = None


class Minutes(BaseModel):
    """Minutes spent confirming the current state and reconstructing the next step."""

    model_config = ConfigDict(extra="forbid")

    confirm: float | None
    reconstruct: float | None


class Record(BaseModel):
    """One trial: who read which stage, the answers, the score and the time taken.

    A record kept before q6 existed has no q6; it is read as it was scored (ADR-0035)."""

    model_config = ConfigDict(extra="forbid")

    date: date
    scenario: str
    stage: str
    reader: Reader
    minutes: Minutes
    answers: Answers
    score: dict[str, bool]

    @model_validator(mode="after")
    def _only_a_human_is_timed(self) -> Self:
        times = (self.minutes.confirm, self.minutes.reconstruct)
        if self.reader.kind == "human" and None in times:
            raise ValueError("minutes: a human trial records confirm and reconstruct")
        if self.reader.kind == "claude" and times != (None, None):
            raise ValueError("minutes: a Claude trial is not timed; leave both empty")
        return self


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_scenario(name: str) -> Scenario:
    return Scenario.model_validate(_read_yaml(FIXTURES / name / "stages.yaml"))


def load_key(name: str) -> Key:
    return Key.model_validate(_read_yaml(FIXTURES / name / "key.yaml"))


def _start_over(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        if not (out / BUILT_MARK).exists():
            raise ValueError(f"{out} is not empty and was not built by handoff_trial")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / BUILT_MARK).touch()


def build(scenario: Scenario, out: Path, through: str | None = None) -> Path:
    """Write the scenario's ``.insight/`` into *out* up to stage *through*; return the HTML."""
    stages = scenario.stages
    if through is not None:
        ids = [s.id for s in stages]
        if through not in ids:
            raise ValueError(f"no stage '{through}' in the scenario; stages are {ids}")
        stages = stages[: ids.index(through) + 1]
    _start_over(out)
    for stage in stages:
        for step in stage.steps:
            ((name, args),) = step.items()
            function, themed = STEPS[name]
            theme = {"theme_id": scenario.theme_id} if themed else {}
            try:
                function(**theme, **args, base_dir=out)
            except TypeError as e:
                raise ValueError(f"stage '{stage.id}', step '{name}': {e}") from e
    return Path(tree_io.render(scenario.theme_id, base_dir=out)["path"])


def prompt_for(html: str) -> str:
    return (FIXTURES / "prompt.md").read_text(encoding="utf-8") + html


_FENCED = re.compile(r"```[A-Za-z]*[ \t]*\n(\{.*?\})\s*```", re.S)


def parse_answers(text: str) -> Answers:
    """Read the reader's reply, with or without a fenced code block around the JSON."""
    found = _FENCED.search(text)
    body = found.group(1) if found else text.strip()
    try:
        return Answers.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"the reply is not the answer JSON: {e}") from e


def score(answers: Answers, key: Key) -> dict[str, bool]:
    """Right or wrong per question, by the ids the answers name."""
    result = {}
    for q in QUESTIONS:
        given = getattr(answers, q)
        result[q] = given is not None and getattr(key.answers, q).accepts(given)
    return result


def _build(args: argparse.Namespace) -> int:
    print(build(load_scenario(args.scenario), Path(args.out), args.through))
    return 0


def _prompt(args: argparse.Namespace) -> int:
    sys.stdout.write(prompt_for(Path(args.html).read_text(encoding="utf-8")))
    return 0


def _record(args: argparse.Namespace) -> int:
    if args.reader_kind == "claude" and not args.reader_model:
        raise ValueError(
            "--reader-model: a Claude trial records the model id that answered"
        )
    key = load_key(args.scenario)
    answers = parse_answers(Path(args.answers).read_text(encoding="utf-8"))
    record = Record(
        date=date.fromisoformat(args.date),
        scenario=args.scenario,
        stage=key.stage,
        reader=Reader(
            kind=args.reader_kind, name=args.reader_name, model=args.reader_model
        ),
        minutes=Minutes(
            confirm=args.minutes_confirm, reconstruct=args.minutes_reconstruct
        ),
        answers=answers,
        score=score(answers, key),
    )
    Path(args.out).write_text(
        yaml.safe_dump(
            record.model_dump(mode="json"), allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    for question, right in record.score.items():
        print(f"{question}: {'right' if right else 'wrong'}")
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "build": _build,
    "prompt": _prompt,
    "record": _record,
}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handoff_trial")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="write the scenario and its tree HTML")
    b.add_argument("--scenario", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--through", help="the last stage to apply (default: all)")
    p = sub.add_parser("prompt", help="print the reader prompt with the HTML")
    p.add_argument("--html", required=True)
    r = sub.add_parser("record", help="score a reply and write the trial record")
    r.add_argument("--scenario", required=True)
    r.add_argument("--answers", required=True)
    r.add_argument("--reader-kind", required=True, choices=["human", "claude"])
    r.add_argument("--reader-name", required=True)
    r.add_argument("--reader-model", help="the model id that answered (Claude)")
    r.add_argument("--date", required=True)
    r.add_argument("--minutes-confirm", type=float)
    r.add_argument("--minutes-reconstruct", type=float)
    r.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
