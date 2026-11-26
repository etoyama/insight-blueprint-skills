"""Structure tests for docs/HANDOFF_TRIAL.md (Epic 18, Story 18.8).

The document is the procedure of the handoff trial (US-7 AC 2 and AC 3). The
tests pin what a developer must not lose when it is rewritten: the reader gets
the HTML and nothing else, scoring is by judgment, and a trial leaves a record.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from scripts import handoff_trial
from tests.skills._markdown import section, unwrap

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = "docs/HANDOFF_TRIAL.md"
_SCRIPT_CALL = re.compile(r"-m scripts\.handoff_trial ([a-z]+)")


def _doc() -> str:
    return (REPO_ROOT / DOC).read_text(encoding="utf-8")


def _claude_command() -> list[str]:
    body = section(_doc(), "## Step 2").replace("\\\n", " ")
    line = next(line for line in body.splitlines() if "claude -p --" in line)
    return shlex.split(line[line.index("claude -p") :].split("<")[0])


class TestTheDocumentIsReachable:
    def test_claude_md_points_at_it(self) -> None:
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert f"]({DOC})" in section(claude_md, "## 2. Documents")

    def test_it_names_the_prd_success_criteria(self) -> None:
        assert "](PRD.md#成功基準)" in section(_doc(), "## Purpose")

    def test_it_lists_every_question_the_reader_answers(self) -> None:
        body = section(_doc(), "## Purpose")
        for n in range(1, len(handoff_trial.QUESTIONS) + 1):
            assert f"\n{n}. " in body
        assert f"\n{len(handoff_trial.QUESTIONS) + 1}. " not in body


class TestScenarios:
    """Epic 34 US-6: two synthetic scenarios share one sheet of questions."""

    def test_each_scenario_is_named_with_its_place(self) -> None:
        body = section(_doc(), "## Scenario")
        for path in sorted(handoff_trial.FIXTURES.iterdir()):
            if path.is_dir():
                assert f"`tests/fixtures/handoff/{path.name}/`" in body

    def test_it_uses_the_words_the_analyst_sees(self) -> None:
        """Epic 34 US-5: the subject, not the root."""
        assert not re.search("根(?!拠)", _doc())


class TestTheReaderGetsOnlyTheHtml:
    """AC 2: a Claude session with no context reads the HTML and nothing else."""

    def test_the_reader_has_no_tools(self) -> None:
        command = _claude_command()
        assert command[command.index("--tools") + 1] == ""

    def test_no_mcp_server_plugin_or_setting_is_loaded(self) -> None:
        command = _claude_command()
        assert "--strict-mcp-config" in command
        assert command[command.index("--setting-sources") + 1] == ""
        assert "--plugin-dir" not in command
        assert "--mcp-config" not in command

    def test_the_default_system_prompt_is_replaced(self) -> None:
        assert "--system-prompt" in _claude_command()

    def test_it_runs_from_an_empty_directory(self) -> None:
        assert "空のディレクトリ" in unwrap(section(_doc(), "## Step 2"))

    def test_nothing_but_the_model_api_receives_the_page(self) -> None:
        body = unwrap(section(_doc(), "## Step 2"))
        assert "モデルの API 以外には送らない" in body
        assert "Artifact" in body

    def test_what_the_flags_cannot_turn_off_is_said(self) -> None:
        assert "managed" in unwrap(section(_doc(), "## Step 2"))


class TestScoring:
    def test_scoring_is_by_judgment_not_by_wording(self) -> None:
        body = unwrap(section(_doc(), "## Step 4"))
        assert "文言" in body
        assert "`note`" in body

    def test_each_question_has_its_rule(self) -> None:
        body = section(_doc(), "## Step 4")
        for field in handoff_trial.Answers.model_fields:
            assert f"| {field} |" in body

    def test_q3_splits_the_events_by_the_kind_of_the_citing_statement(self) -> None:
        """US-4 AC 5 of Epic 32: an exploration's evidence carries no direction."""
        body = section(_doc(), "## Step 4")
        (row,) = [line for line in body.splitlines() if line.startswith("| q3 |")]
        assert "「これまでわかっていること」" in row
        assert "「注意すべきこと」" in row
        assert "引用した文の種類" in row


class TestRecord:
    """AC 3: a trial leaves the answers, right or wrong, and the time taken."""

    def test_a_human_records_both_times(self) -> None:
        body = unwrap(section(_doc(), "## Step 5"))
        assert "`minutes.confirm`" in body
        assert "`minutes.reconstruct`" in body

    def test_records_are_kept_under_docs(self) -> None:
        assert "docs/handoff-trials/" in section(_doc(), "## Step 5")

    def test_a_record_keeps_the_score_of_the_key_it_was_scored_with(self) -> None:
        body = unwrap(section(_doc(), "## Step 5"))
        assert "](adr/0035-" in body
        assert "採点し直さない" in body


class TestCommandsExist:
    def test_every_named_subcommand_exists(self) -> None:
        named = set(_SCRIPT_CALL.findall(_doc()))
        assert named >= {"build", "prompt", "record"}
        assert named <= set(handoff_trial.COMMANDS)
