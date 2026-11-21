"""The handoff trial of a question tree (Epic 18, Story 18.8; docs/HANDOFF_TRIAL.md).

A reader with no other context gets the tree HTML of a synthetic scenario and
answers the five questions of the PRD success criteria. The answers name
judgments by id, so scoring compares judgments and never wording.

Usage:
    python scripts/handoff_trial.py build --scenario lib --out DIR [--through STAGE]
    python scripts/handoff_trial.py prompt --html PATH
    python scripts/handoff_trial.py record --scenario lib --answers PATH \\
        --reader-kind claude|human --reader-name NAME --date YYYY-MM-DD \\
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

REPO_ROOT = Path(__file__).resolve().parents[1]
# Run as a file, Python puts scripts/ on the path, not the root that holds skills/.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402
from pydantic import (  # noqa: E402
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from skills._shared import design_io, tree_io  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "handoff"
QUESTIONS = ("q1", "q2", "q3", "q4", "q5")

_Step = Callable[[str, Path, Any], object]


def _without(args: dict, name: str) -> dict:
    return {k: v for k, v in args.items() if k != name}


def _answer(theme: str, out: Path, answers: list[dict]) -> object:
    result = tree_io.answer(theme, answers=answers, base_dir=out)
    if result["violations"]:
        raise ValueError(f"the scenario's answers fail the tree check: {result}")
    return result


STEPS: dict[str, _Step] = {
    "create_tree": lambda t, out, a: tree_io.create_tree(theme_id=t, base_dir=out, **a),
    "add_node": lambda t, out, a: tree_io.add_node(t, base_dir=out, **a),
    "decide": lambda t, out, a: tree_io.decide(t, base_dir=out, **a),
    "create_design": lambda t, out, a: design_io.create_design(
        theme_id=t, base_dir=out, **a
    ),
    "link_design": lambda t, out, a: tree_io.link_design(
        t, a["node_id"], a["design_id"], base_dir=out
    ),
    "journal": lambda t, out, a: design_io.append_journal_event(
        a["design_id"], _without(a, "design_id"), out
    ),
    "transition_status": lambda t, out, a: design_io.transition_status(
        a["design_id"], a["target"], out
    ),
    "answer": _answer,
    "candidate": lambda t, out, a: tree_io.candidate(
        t, a["node_id"], base_dir=out, **_without(a, "node_id")
    ),
    "hear": lambda t, out, a: tree_io.hear(
        t, a["node_id"], base_dir=out, **_without(a, "node_id")
    ),
}


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    steps: list[dict[str, Any]]

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


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = ""


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


class Answers(BaseModel):
    """The reader's answers. A question left out is scored wrong, not refused."""

    model_config = ConfigDict(extra="forbid")

    q1: Q1 | None = None
    q2: Q2 | None = None
    q3: Q3 | None = None
    q4: Q4 | None = None
    q5: Q5 | None = None


class Key(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    answers: Answers


class Reader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["human", "claude"]
    name: str


class Minutes(BaseModel):
    """Minutes spent confirming the current state and reconstructing the next step."""

    model_config = ConfigDict(extra="forbid")

    confirm: float | None
    reconstruct: float | None


class Record(BaseModel):
    """One trial: who read which stage, the answers, the score and the time taken."""

    model_config = ConfigDict(extra="forbid")

    date: date
    scenario: str
    stage: str
    reader: Reader
    minutes: Minutes
    answers: Answers
    score: dict[str, bool]

    @model_validator(mode="after")
    def _a_human_is_timed(self) -> Self:
        timed = (
            self.minutes.confirm is not None and self.minutes.reconstruct is not None
        )
        if self.reader.kind == "human" and not timed:
            raise ValueError(
                "minutes: a human trial records both confirm and reconstruct"
            )
        return self


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_scenario(name: str) -> Scenario:
    return Scenario.model_validate(_read_yaml(FIXTURES / name / "stages.yaml"))


def load_key(name: str) -> Key:
    return Key.model_validate(_read_yaml(FIXTURES / name / "key.yaml"))


def build(scenario: Scenario, out: Path, through: str | None = None) -> Path:
    """Write the scenario's ``.insight/`` into *out* up to stage *through*; return the HTML."""
    stages = scenario.stages
    if through is not None:
        ids = [s.id for s in stages]
        if through not in ids:
            raise ValueError(f"no stage '{through}' in the scenario; stages are {ids}")
        stages = stages[: ids.index(through) + 1]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for stage in stages:
        for step in stage.steps:
            ((name, args),) = step.items()
            STEPS[name](scenario.theme_id, out, args)
    return Path(tree_io.render(scenario.theme_id, base_dir=out)["path"])


def prompt_for(html: str) -> str:
    return (FIXTURES / "prompt.md").read_text(encoding="utf-8") + html


_FENCED = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


def parse_answers(text: str) -> Answers:
    """Read the reader's reply, with or without a fenced code block around the JSON."""
    found = _FENCED.search(text)
    body = found.group(1) if found else text.strip()
    try:
        return Answers.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"the reply is not the answer JSON: {e}") from e


def _same(a: list[Any], b: list[Any]) -> bool:
    return set(a) == set(b)


def score(answers: Answers, key: Key) -> dict[str, bool]:
    """Right or wrong per question, by the ids the answers name."""
    k = key.answers
    assert k.q1 and k.q2 and k.q3 and k.q4 and k.q5, "the key answers every question"
    a = answers
    return {
        "q1": a.q1 is not None and a.q1.verdict == k.q1.verdict,
        "q2": a.q2 is not None
        and _same(a.q2.not_started, k.q2.not_started)
        and _same(a.q2.analyzed_undetermined, k.q2.analyzed_undetermined),
        "q3": a.q3 is not None
        and _same(a.q3.supports, k.q3.supports)
        and _same(a.q3.weakens, k.q3.weakens),
        "q4": a.q4 is not None
        and _same(a.q4.changed_nodes, k.q4.changed_nodes)
        and _same(a.q4.evidence, k.q4.evidence),
        # The reason is free text on the page and cites nothing, so a reader may
        # rightly name more of the events behind it; the key's must all be there.
        "q5": a.q5 is not None
        and a.q5.node_id == k.q5.node_id
        and set(k.q5.reason_events) <= set(a.q5.reason_events),
    }


def rescore(record: Record) -> dict[str, bool]:
    key = load_key(record.scenario)
    if record.stage != key.stage:
        raise ValueError(
            f"the key is for stage '{key.stage}', the record for '{record.stage}'"
        )
    return score(record.answers, key)


def _build(args: argparse.Namespace) -> int:
    print(build(load_scenario(args.scenario), Path(args.out), args.through))
    return 0


def _prompt(args: argparse.Namespace) -> int:
    sys.stdout.write(prompt_for(Path(args.html).read_text(encoding="utf-8")))
    return 0


def _record(args: argparse.Namespace) -> int:
    key = load_key(args.scenario)
    answers = parse_answers(Path(args.answers).read_text(encoding="utf-8"))
    record = Record(
        date=date.fromisoformat(args.date),
        scenario=args.scenario,
        stage=key.stage,
        reader=Reader(kind=args.reader_kind, name=args.reader_name),
        minutes=Minutes(
            confirm=args.minutes_confirm, reconstruct=args.minutes_reconstruct
        ),
        answers=answers,
        score=score(answers, key),
    )
    Path(args.out).write_text(
        yaml.safe_dump(
            record.model_dump(mode="json", exclude_none=False),
            allow_unicode=True,
            sort_keys=False,
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
    r.add_argument("--date", required=True)
    r.add_argument("--minutes-confirm", type=float)
    r.add_argument("--minutes-reconstruct", type=float)
    r.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
