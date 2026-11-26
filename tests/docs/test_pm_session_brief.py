"""Structure tests for the brief of the pm-session skill (retrospective of Epic 34).

Two rules were added after Epic 34: a value shown in several places was changed in
one of them only, and a Story went on with eleven unplanned decisions after it had
told the PM. Both rules live in this repository only, not in the upstream template.
"""

from __future__ import annotations

from pathlib import Path

from tests.skills._markdown import section, unwrap

REPO_ROOT = Path(__file__).resolve().parents[2]


def _skill() -> str:
    path = REPO_ROOT / ".claude/skills/pm-session/SKILL.md"
    return path.read_text(encoding="utf-8")


def _brief() -> str:
    return unwrap(section(section(_skill(), "## 4."), "### ブリーフの型"))


class TestTheBrief:
    def test_it_lists_every_place_that_shows_the_same_value(self) -> None:
        body = _brief()
        assert "同じ値を出す所を全部挙げる" in body
        for place in ("画面", "コマンドの出力", "レポート"):
            assert place in body

    def test_a_story_stops_and_asks_past_two_unplanned_decisions(self) -> None:
        assert "計画外の判断が2件を超えたら、進めずに止まって PM に聞くこと" in _brief()

    def test_every_rule_on_unplanned_decisions_stops_the_story(self) -> None:
        """The model section and the brief must not say two different things."""
        rules = [
            line
            for line in _skill().splitlines()
            if "計画外の判断が2件を超えたら" in line
        ]
        assert len(rules) >= 2
        assert all("止まって" in line for line in rules)
