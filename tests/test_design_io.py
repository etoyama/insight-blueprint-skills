"""Unit tests for skills/_shared/design_io.py (Epic 3, Story 3.1).

design_io is the server-free YAML I/O helper that skills call instead of MCP
tools. It must replicate DesignService/ReviewService behaviour (id generation,
timestamps, merge, transition, reviews batches) and route all validation through
insight_blueprint.validate (the single source of truth).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from skills._shared import design_io
from skills._shared._atomic import atomic_write_yaml


@pytest.fixture
def insight(tmp_path: Path) -> Path:
    """Return a temp .insight base dir."""
    base = tmp_path / ".insight"
    (base / "designs").mkdir(parents=True)
    return base


def _create(insight: Path, **over: object) -> dict:
    kwargs: dict = {
        "theme_id": "FP",
        "title": "Test",
        "hypothesis_statement": "X improves Y",
        "hypothesis_background": "because Z",
        "methodology": {"method": "OLS"},
        "metrics": [_PRIMARY],
        "base_dir": insight,
    }
    kwargs.update(over)
    return design_io.create_design(**kwargs)


_PRIMARY = {
    "target": "lead time",
    "tier": "primary",
    "comparison": "supported at 2.0 days or more, rejected under 1.0 day",
}


def _explore(insight: Path, **over: object) -> dict:
    """An exploratory design: a question and its background, no hypothesis."""
    kwargs: dict = {
        "theme_id": "FP",
        "title": "Test",
        "analysis_intent": "exploratory",
        "exploration_question": "How far apart are the regions?",
        "exploration_background": "Nobody has measured the spread",
        "methodology": {"method": "describe"},
        "base_dir": insight,
    }
    kwargs.update(over)
    return design_io.create_design(**kwargs)


def _saved(insight: Path, design_id: str, **fields: object) -> None:
    """Write a design as an older plugin left it, without going through create."""
    body: dict = {
        "id": design_id,
        "theme_id": "FP",
        "title": "Saved",
        "hypothesis_statement": "X improves Y",
        "hypothesis_background": "because Z",
        "status": "analyzing",
        "next_action": None,
        "created_at": "2026-10-01T10:00:00+09:00",
        "updated_at": "2026-10-01T10:00:00+09:00",
    }
    body.update(fields)
    atomic_write_yaml(insight / "designs" / f"{design_id}_hypothesis.yaml", body)


_BAD_IDS = ["../evil", "a/b", "..", "x/../y", "", "with space"]


class TestBaseDirEnv:
    """DEFAULT_BASE_DIR honors INSIGHT_BASE_DIR (set by the bin/ wrappers, Epic 09)."""

    def test_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        monkeypatch.setenv("INSIGHT_BASE_DIR", "/tmp/ib-env/.insight")
        mod = importlib.reload(design_io)
        try:
            assert str(mod.DEFAULT_BASE_DIR) == "/tmp/ib-env/.insight"
        finally:
            monkeypatch.delenv("INSIGHT_BASE_DIR", raising=False)
            importlib.reload(mod)

    def test_default_is_dot_insight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        monkeypatch.delenv("INSIGHT_BASE_DIR", raising=False)
        mod = importlib.reload(design_io)
        assert str(mod.DEFAULT_BASE_DIR) == ".insight"


class TestResolveBaseDir:
    """resolve_base_dir rejects an absurd anchor (defense in depth for M1, ADR-0006)."""

    def test_tmp_base_passes(self, tmp_path: Path) -> None:
        base = tmp_path / ".insight"
        assert design_io.resolve_base_dir(base) == base.resolve()

    def test_non_insight_leaf_passes(self, tmp_path: Path) -> None:
        # The .insight suffix is enforced by the wrapper, not here (back-compat / tests).
        base = tmp_path / "workdir"
        assert design_io.resolve_base_dir(base) == base.resolve()

    def test_filesystem_root_rejected(self) -> None:
        with pytest.raises(ValueError, match="filesystem root"):
            design_io.resolve_base_dir(Path("/"))

    def test_home_dir_rejected(self) -> None:
        with pytest.raises(ValueError, match="home directory"):
            design_io.resolve_base_dir(Path.home())


class TestIdValidation:
    """design_id is interpolated into paths — reject anything that could escape."""

    @pytest.mark.parametrize("bad", _BAD_IDS)
    def test_readers_and_writers_reject_bad_id(self, insight: Path, bad: str) -> None:
        with pytest.raises(ValueError):
            design_io.load_design(bad, base_dir=insight)
        with pytest.raises(ValueError):
            design_io.load_journal(bad, base_dir=insight)
        with pytest.raises(ValueError):
            design_io.write_journal(bad, {"events": []}, base_dir=insight)
        with pytest.raises(ValueError):
            design_io.list_review_batches(bad, base_dir=insight)
        with pytest.raises(ValueError):
            design_io.update_design(bad, {}, base_dir=insight)
        with pytest.raises(ValueError):
            design_io.transition_status(bad, "analyzing", base_dir=insight)

    def test_traversal_does_not_escape_insight(self, insight: Path) -> None:
        target = insight.parent / "designs" / "pwned_journal.yaml"
        with pytest.raises(ValueError):
            design_io.write_journal("../../designs/pwned", {"x": 1}, base_dir=insight)
        assert not target.exists()

    def test_valid_id_passes(self, insight: Path) -> None:
        d = _create(insight)  # FP-H01
        assert design_io.load_design(d["id"], base_dir=insight)["id"] == d["id"]


class TestDesignIdGrammar:
    @pytest.mark.parametrize(
        ("design_id", "theme", "number"),
        [("LIB-H01", "LIB", 1), ("FP2-H10", "FP2", 10), ("LIB-H123", "LIB", 123)],
    )
    def test_a_design_id_names_its_theme_and_number(
        self, design_id: str, theme: str, number: int
    ) -> None:
        assert design_io.theme_of(design_id) == theme
        assert design_io.design_number(design_id) == number

    @pytest.mark.parametrize(
        "design_id", ["LIB-H", "LIB-01", "lib-H01", "LIB-H01x", "-H01", "LIB-H01-H02"]
    )
    def test_an_id_outside_the_grammar_has_neither(self, design_id: str) -> None:
        assert design_io.theme_of(design_id) is None
        assert design_io.design_number(design_id) is None


# ---------------------------------------------------------------------------
# create / id generation
# ---------------------------------------------------------------------------


class TestCreateDesign:
    def test_creates_file_with_generated_id(self, insight: Path) -> None:
        d = _create(insight)
        assert d["id"] == "FP-H01"
        assert (insight / "designs" / "FP-H01_hypothesis.yaml").exists()
        assert d["status"] == "in_review"
        assert d["created_at"] and d["updated_at"]

    def test_id_increments_max_n_plus_1(self, insight: Path) -> None:
        _create(insight)
        _create(insight)
        d3 = _create(insight)
        assert d3["id"] == "FP-H03"

    def test_id_per_theme(self, insight: Path) -> None:
        _create(insight, theme_id="FP")
        d = _create(insight, theme_id="TX")
        assert d["id"] == "TX-H01"

    def test_invalid_theme_id_rejected(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="theme_id"):
            _create(insight, theme_id="bad-theme")

    def test_empty_methodology_method_rejected(self, insight: Path) -> None:
        with pytest.raises(ValidationError):
            _create(insight, methodology={"method": ""})

    def test_not_written_when_invalid(self, insight: Path) -> None:
        with pytest.raises(ValidationError):
            _create(insight, methodology={"method": ""})
        # id was FP-H01 but write must not have happened
        assert not (insight / "designs" / "FP-H01_hypothesis.yaml").exists()

    def test_decision_context_is_written(self, insight: Path) -> None:
        """Epic 12 US-2 AC 1: the decision context reaches the YAML file."""
        context = {"decision_maker": "事業責任者", "decision": "値上げを実施するか"}
        d = _create(insight, decision_context=context)
        assert d["decision_context"] == context
        loaded = design_io.load_design(d["id"], base_dir=insight)
        assert loaded["decision_context"] == context

    def test_decision_context_is_optional(self, insight: Path) -> None:
        """Epic 12 US-2 AC 2: the analyst may go on without writing one."""
        assert _create(insight)["decision_context"] is None

    def test_half_filled_decision_context_writes_nothing(self, insight: Path) -> None:
        with pytest.raises(ValidationError):
            _create(insight, decision_context={"decision_maker": "事業責任者"})
        assert not (insight / "designs" / "FP-H01_hypothesis.yaml").exists()


# ---------------------------------------------------------------------------
# load / list
# ---------------------------------------------------------------------------


class TestLoadList:
    def test_load_missing_returns_empty(self, insight: Path) -> None:
        assert design_io.load_design("NOPE-H01", base_dir=insight) == {}

    def test_load_roundtrip(self, insight: Path) -> None:
        d = _create(insight)
        loaded = design_io.load_design(d["id"], base_dir=insight)
        assert loaded["id"] == d["id"]
        assert loaded["hypothesis_statement"] == "X improves Y"

    def test_list_sorted_and_filtered(self, insight: Path) -> None:
        _create(insight)  # FP-H01 in_review
        d2 = _create(insight)  # FP-H02 in_review
        design_io.transition_status(d2["id"], "analyzing", base_dir=insight)
        all_ids = [d["id"] for d in design_io.list_designs(base_dir=insight)]
        assert all_ids == ["FP-H01", "FP-H02"]
        analyzing = design_io.list_designs(base_dir=insight, status="analyzing")
        assert [d["id"] for d in analyzing] == ["FP-H02"]


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdateDesign:
    def test_partial_update_refreshes_updated_at(self, insight: Path) -> None:
        d = _create(insight)
        updated = design_io.update_design(
            d["id"], {"title": "New title"}, base_dir=insight
        )
        assert updated["title"] == "New title"
        assert updated["created_at"] == d["created_at"]
        assert updated["updated_at"] >= d["updated_at"]

    def test_referenced_knowledge_union_dedup(self, insight: Path) -> None:
        d = _create(insight, referenced_knowledge={"metrics": ["k1"]})
        updated = design_io.update_design(
            d["id"],
            {"referenced_knowledge": {"metrics": ["k1", "k2"]}},
            base_dir=insight,
        )
        assert updated["referenced_knowledge"]["metrics"] == ["k1", "k2"]

    def test_missing_design_raises(self, insight: Path) -> None:
        with pytest.raises(ValueError):
            design_io.update_design("FP-H99", {"title": "x"}, base_dir=insight)

    def test_invalid_update_not_persisted(self, insight: Path) -> None:
        d = _create(insight)
        with pytest.raises(ValidationError):
            design_io.update_design(
                d["id"], {"methodology": {"method": ""}}, base_dir=insight
            )
        reloaded = design_io.load_design(d["id"], base_dir=insight)
        assert reloaded["methodology"]["method"] == "OLS"

    def test_design_written_before_decision_context_still_updates(
        self, insight: Path
    ) -> None:
        """Epic 12 US-2 AC 4: a file that lacks the key passes validation as is."""
        d = _create(insight)
        path = insight / "designs" / f"{d['id']}_hypothesis.yaml"
        legacy = design_io.read_yaml(path)
        del legacy["decision_context"]
        design_io.atomic_write_yaml(path, legacy)

        updated = design_io.update_design(d["id"], {"title": "New"}, base_dir=insight)
        assert updated["title"] == "New"
        assert updated["decision_context"] is None

    def test_decision_context_can_be_added_later(self, insight: Path) -> None:
        d = _create(insight)
        context = {"decision_maker": "事業責任者", "decision": "値上げを実施するか"}
        updated = design_io.update_design(
            d["id"], {"decision_context": context}, base_dir=insight
        )
        assert updated["decision_context"] == context


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


class TestTransition:
    def test_valid_transition(self, insight: Path) -> None:
        d = _create(insight)
        out = design_io.transition_status(d["id"], "analyzing", base_dir=insight)
        assert out["status"] == "analyzing"

    def test_analyzed_design_concludes_without_a_review(self, insight: Path) -> None:
        d = _create(insight)
        design_io.transition_status(d["id"], "analyzing", base_dir=insight)
        out = design_io.transition_status(d["id"], "supported", base_dir=insight)
        assert out["status"] == "supported"
        assert design_io.load_design(d["id"], base_dir=insight)["status"] == "supported"

    def test_invalid_transition_raises_and_not_persisted(self, insight: Path) -> None:
        d = _create(insight)
        design_io.transition_status(d["id"], "analyzing", base_dir=insight)
        with pytest.raises(ValueError, match="transition"):
            design_io.transition_status(d["id"], "revision_requested", base_dir=insight)
        assert design_io.load_design(d["id"], base_dir=insight)["status"] == "analyzing"


# ---------------------------------------------------------------------------
# reviews
# ---------------------------------------------------------------------------


class TestReviewBatch:
    def test_append_batch_and_transition(self, insight: Path) -> None:
        d = _create(insight)
        batch = design_io.append_review_batch(
            d["id"],
            status_after="analyzing",
            comments=[
                {
                    "comment": "vague",
                    "target_section": "hypothesis_statement",
                    "target_content": "X improves Y",
                }
            ],
            base_dir=insight,
        )
        assert batch["id"].startswith("RB-")
        # design transitioned
        assert design_io.load_design(d["id"], base_dir=insight)["status"] == "analyzing"
        # reviews.yaml persisted
        batches = design_io.list_review_batches(d["id"], base_dir=insight)
        assert len(batches) == 1
        assert batches[0]["status_after"] == "analyzing"

    def test_invalid_target_section_rejected(self, insight: Path) -> None:
        d = _create(insight)
        with pytest.raises(ValueError, match="target_section"):
            design_io.append_review_batch(
                d["id"],
                status_after="analyzing",
                comments=[
                    {
                        "comment": "x",
                        "target_section": "not_a_section",
                        "target_content": "y",
                    }
                ],
                base_dir=insight,
            )

    def test_comment_may_target_the_decision_context(self, insight: Path) -> None:
        """Epic 12 US-2 AC 3: a review can point at the decision context."""
        d = _create(
            insight,
            decision_context={
                "decision_maker": "事業責任者",
                "decision": "値上げを実施するか",
            },
        )
        batch = design_io.append_review_batch(
            d["id"],
            status_after="revision_requested",
            comments=[
                {
                    "comment": "仮説が支持されても、この決定は変わらない",
                    "target_section": "decision_context",
                    "target_content": "値上げを実施するか",
                }
            ],
            base_dir=insight,
        )
        assert batch["comments"][0]["target_section"] == "decision_context"

    def test_empty_comments_rejected(self, insight: Path) -> None:
        d = _create(insight)
        with pytest.raises(ValueError):
            design_io.append_review_batch(
                d["id"], status_after="analyzing", comments=[], base_dir=insight
            )


# ---------------------------------------------------------------------------
# journal
# ---------------------------------------------------------------------------


class TestJournal:
    def test_journal_roundtrip(self, insight: Path) -> None:
        d = _create(insight)
        design_io.write_journal(
            d["id"],
            {"metadata": {"design_id": d["id"]}, "events": []},
            base_dir=insight,
        )
        loaded = design_io.load_journal(d["id"], base_dir=insight)
        assert loaded["metadata"]["design_id"] == d["id"]
        assert loaded["events"] == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_create_and_list(self, insight: Path, tmp_path: Path) -> None:
        payload = {
            "theme_id": "FP",
            "title": "CLI test",
            "hypothesis_statement": "a",
            "hypothesis_background": "b",
            "methodology": {"method": "OLS"},
        }
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "skills._shared.design_io",
                "create",
                "--base-dir",
                str(insight),
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        assert res.returncode == 0, res.stderr
        out = json.loads(res.stdout)
        assert out["id"] == "FP-H01"
        assert (insight / "designs" / "FP-H01_hypothesis.yaml").exists()


# ---------------------------------------------------------------------------
# Epic 32, Story 32.1: the intent decides the form and the end (ADR-0048, ADR-0049)
# ---------------------------------------------------------------------------


def _on_disk(insight: Path, design_id: str) -> dict:
    return design_io.read_yaml(insight / "designs" / f"{design_id}_hypothesis.yaml")


class TestCreateByIntent:
    """US-2 AC 1: create writes an exploration or a confirmation, and nothing else."""

    def test_an_exploration_is_written_without_a_hypothesis(
        self, insight: Path
    ) -> None:
        design = _explore(insight)
        written = _on_disk(insight, design["id"])
        assert written["exploration_question"] == "How far apart are the regions?"
        assert written["exploration_background"] == "Nobody has measured the spread"
        for absent in ("hypothesis_statement", "hypothesis_background"):
            assert absent not in written

    def test_a_confirmation_is_written_without_a_question(self, insight: Path) -> None:
        written = _on_disk(insight, _create(insight)["id"])
        assert written["analysis_intent"] == "confirmatory"
        assert "exploration_question" not in written

    @pytest.mark.parametrize(
        "over",
        [
            {"exploration_question": None},
            {"exploration_background": None},
            {"hypothesis_statement": "X", "hypothesis_background": "Y"},
            {"hypothesis_background": "Y"},
            {"next_action": {"if_supported": "go", "if_rejected": "stop"}},
        ],
        ids=[
            "no-question",
            "no-background",
            "hypothesis",
            "hypothesis-background",
            "next-action",
        ],
    )
    def test_an_exploration_out_of_its_form_writes_nothing(
        self, insight: Path, over: dict
    ) -> None:
        with pytest.raises((ValidationError, ValueError)):
            _explore(insight, **over)
        assert not list((insight / "designs").iterdir())

    @pytest.mark.parametrize(
        "over",
        [
            {"exploration_question": "Q?"},
            {"exploration_background": "B"},
            {"hypothesis_statement": None},
            {"hypothesis_background": ""},
        ],
        ids=["question", "background", "no-hypothesis", "blank-background"],
    )
    def test_a_confirmation_out_of_its_form_writes_nothing(
        self, insight: Path, over: dict
    ) -> None:
        with pytest.raises((ValidationError, ValueError)):
            _create(insight, **over)
        assert not list((insight / "designs").iterdir())

    def test_a_mixed_design_is_not_created(self, insight: Path) -> None:
        with pytest.raises(ValueError, match="mixed"):
            _create(insight, analysis_intent="mixed")
        assert not list((insight / "designs").iterdir())

    def test_an_exploration_with_a_hypothesis_is_not_created(
        self, insight: Path
    ) -> None:
        with pytest.raises(ValueError, match="exploration_question"):
            _create(insight, analysis_intent="exploratory")
        assert not list((insight / "designs").iterdir())

    def test_the_cli_creates_an_exploration(self, insight: Path) -> None:
        payload = {
            "theme_id": "FP",
            "title": "CLI exploration",
            "analysis_intent": "exploratory",
            "exploration_question": "How far apart?",
            "exploration_background": "Not measured",
        }
        res = subprocess.run(
            [sys.executable, "-m", "skills._shared.design_io", "create"]
            + ["--base-dir", str(insight)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        assert res.returncode == 0, res.stderr
        assert "hypothesis_statement" not in json.loads(res.stdout)


class TestConclusionByForm:
    """US-2 AC 2: an exploration ends as explored, the others on a verdict."""

    def test_an_exploration_ends_as_explored(self, insight: Path) -> None:
        design_id = _explore(insight)["id"]
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        design_io.transition_status(design_id, "explored", base_dir=insight)
        assert _on_disk(insight, design_id)["status"] == "explored"

    @pytest.mark.parametrize("verdict", ["supported", "rejected", "inconclusive"])
    def test_an_exploration_takes_no_verdict(self, insight: Path, verdict: str) -> None:
        design_id = _explore(insight)["id"]
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        with pytest.raises(ValueError, match="Cannot transition"):
            design_io.transition_status(design_id, verdict, base_dir=insight)
        assert _on_disk(insight, design_id)["status"] == "analyzing"

    def test_a_confirmation_does_not_end_as_explored(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        with pytest.raises(ValueError, match="Cannot transition"):
            design_io.transition_status(design_id, "explored", base_dir=insight)

    def test_an_update_does_not_give_an_exploration_a_verdict(
        self, insight: Path
    ) -> None:
        design_id = _explore(insight)["id"]
        with pytest.raises(ValueError, match="ends as explored"):
            design_io.update_design(design_id, {"status": "supported"}, insight)
        assert _on_disk(insight, design_id)["status"] == "in_review"

    def test_a_review_ends_an_exploration_as_explored(self, insight: Path) -> None:
        design_id = _explore(insight)["id"]
        design_io.append_review_batch(
            design_id, "explored", [{"comment": "measured"}], base_dir=insight
        )
        assert _on_disk(insight, design_id)["status"] == "explored"


class TestIntentChange:
    """US-2 AC 3: the intent changes only before the analysis, or to fix a legacy one."""

    _TO_EXPLORATION = {
        "analysis_intent": "exploratory",
        "exploration_question": "How far apart?",
        "exploration_background": "Not measured",
        "hypothesis_statement": None,
        "hypothesis_background": None,
    }

    @pytest.mark.parametrize("status", ["in_review", "revision_requested"])
    def test_the_intent_changes_before_the_analysis(
        self, insight: Path, status: str
    ) -> None:
        design_id = _create(insight)["id"]
        if status != "in_review":
            design_io.transition_status(design_id, status, base_dir=insight)
        design_io.update_design(design_id, self._TO_EXPLORATION, insight)
        written = _on_disk(insight, design_id)
        assert written["analysis_intent"] == "exploratory"
        assert "hypothesis_statement" not in written

    def test_the_changed_design_must_take_the_new_form(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        with pytest.raises(ValueError, match="exploration_question"):
            design_io.update_design(
                design_id, {"analysis_intent": "exploratory"}, insight
            )
        assert _on_disk(insight, design_id)["analysis_intent"] == "confirmatory"

    def test_the_intent_does_not_change_once_analyzing(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        with pytest.raises(ValueError, match="analysis_intent"):
            design_io.update_design(design_id, self._TO_EXPLORATION, insight)
        assert _on_disk(insight, design_id)["analysis_intent"] == "confirmatory"

    @pytest.mark.parametrize("status", ["analyzing", "supported", "rejected"])
    def test_a_legacy_exploration_is_fixed_to_confirmatory_in_any_status(
        self, insight: Path, status: str
    ) -> None:
        _saved(insight, "FP-H01", analysis_intent="exploratory", status=status)
        design_io.update_design("FP-H01", {"analysis_intent": "confirmatory"}, insight)
        written = _on_disk(insight, "FP-H01")
        assert written["analysis_intent"] == "confirmatory"
        assert written["status"] == status
        assert written["hypothesis_statement"] == "X improves Y"

    def test_the_fix_does_not_rewrite_the_hypothesis(self, insight: Path) -> None:
        _saved(insight, "FP-H01", analysis_intent="exploratory", status="supported")
        with pytest.raises(ValueError, match="analysis_intent"):
            design_io.update_design(
                "FP-H01",
                {"analysis_intent": "confirmatory", "hypothesis_statement": "Later"},
                insight,
            )


class TestSavedDesigns:
    """US-2 AC 4: designs an older plugin wrote are read and moved as before."""

    @pytest.fixture(
        params=[{"analysis_intent": "exploratory"}, {"analysis_intent": "mixed"}, {}],
        ids=["legacy-exploration", "mixed", "no-intent"],
    )
    def saved(self, insight: Path, request: pytest.FixtureRequest) -> str:
        _saved(insight, "FP-H01", **request.param)
        return "FP-H01"

    def test_it_is_listed(self, insight: Path, saved: str) -> None:
        assert [d["id"] for d in design_io.list_designs(insight)] == [saved]

    @pytest.mark.parametrize("verdict", ["supported", "rejected", "inconclusive"])
    def test_it_concludes_on_a_verdict(
        self, insight: Path, saved: str, verdict: str
    ) -> None:
        design_io.transition_status(saved, verdict, base_dir=insight)
        assert _on_disk(insight, saved)["status"] == verdict

    def test_it_does_not_end_as_explored(self, insight: Path, saved: str) -> None:
        with pytest.raises(ValueError, match="Cannot transition"):
            design_io.transition_status(saved, "explored", base_dir=insight)

    def test_it_is_updated_in_its_own_form(self, insight: Path, saved: str) -> None:
        before = _on_disk(insight, saved)
        design_io.update_design(saved, {"title": "Edited"}, insight)
        after = _on_disk(insight, saved)
        assert after["title"] == "Edited"
        assert after.get("analysis_intent", "confirmatory") == before.get(
            "analysis_intent", "confirmatory"
        )
        assert after["hypothesis_statement"] == before["hypothesis_statement"]


class TestReviewBatchByForm:
    """A review that ends a design out of its form leaves no batch behind."""

    def test_a_verdict_on_an_exploration_writes_no_batch(self, insight: Path) -> None:
        design_id = _explore(insight)["id"]
        with pytest.raises(ValueError, match="Cannot transition"):
            design_io.append_review_batch(
                design_id, "supported", [{"comment": "ok"}], base_dir=insight
            )
        assert design_io.list_review_batches(design_id, insight) == []
        assert _on_disk(insight, design_id)["status"] == "in_review"


class TestRepairingABrokenDesign:
    """A design that no longer parses is repaired in place, without moving it."""

    def test_a_repair_keeps_the_status(self, insight: Path) -> None:
        _saved(insight, "FP-H01", status="analyzing", methodology={"method": ""})
        design_io.update_design("FP-H01", {"methodology": {"method": "OLS"}}, insight)
        assert _on_disk(insight, "FP-H01")["methodology"]["method"] == "OLS"

    def test_a_repair_does_not_move_the_design(self, insight: Path) -> None:
        _saved(insight, "FP-H01", status="supported", methodology={"method": ""})
        with pytest.raises(ValueError, match="repair"):
            design_io.update_design(
                "FP-H01",
                {"methodology": {"method": "OLS"}, "status": "in_review"},
                insight,
            )
        assert _on_disk(insight, "FP-H01")["status"] == "supported"


class TestAnalysisMark:
    """Epic 33 US-3 AC 1, AC 5: the mark is written once and stays."""

    @pytest.mark.parametrize("target", ["analyzing", "supported"])
    def test_the_first_move_into_the_analysis_writes_the_mark(
        self, insight: Path, target: str
    ) -> None:
        design_id = _create(insight)["id"]
        out = design_io.transition_status(design_id, target, base_dir=insight)
        assert out["analysis_started_at"] == out["updated_at"]
        assert _on_disk(insight, design_id)["analysis_started_at"]

    def test_an_update_that_moves_the_status_writes_the_mark(
        self, insight: Path
    ) -> None:
        design_id = _create(insight)["id"]
        design_io.update_design(design_id, {"status": "analyzing"}, insight)
        assert _on_disk(insight, design_id)["analysis_started_at"]

    def test_a_review_that_approves_writes_the_mark(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        design_io.append_review_batch(
            design_id, "analyzing", [{"comment": "ok"}], base_dir=insight
        )
        assert _on_disk(insight, design_id)["analysis_started_at"]

    def test_a_design_before_its_analysis_has_no_mark(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        design_io.transition_status(design_id, "revision_requested", base_dir=insight)
        design_io.update_design(design_id, {"title": "Edited"}, insight)
        assert "analysis_started_at" not in _on_disk(insight, design_id)

    def test_the_mark_stays_through_a_review_of_the_result(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        first = design_io.transition_status(design_id, "analyzing", base_dir=insight)
        for target in ("in_review", "revision_requested", "in_review", "analyzing"):
            design_io.transition_status(design_id, target, base_dir=insight)
        design_io.update_design(design_id, {"title": "Edited"}, insight)
        last = design_io.transition_status(design_id, "supported", base_dir=insight)
        assert last["analysis_started_at"] == first["analysis_started_at"]

    def test_an_update_does_not_take_the_mark_away(self, insight: Path) -> None:
        design_id = _create(insight)["id"]
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        with pytest.raises(ValueError, match="analysis_started_at"):
            design_io.update_design(design_id, {"analysis_started_at": None}, insight)
        assert _on_disk(insight, design_id)["analysis_started_at"]

    def test_a_saved_design_gets_the_mark_on_its_next_move(self, insight: Path) -> None:
        _saved(insight, "FP-H01", status="analyzing")
        design_io.update_design("FP-H01", {"title": "Edited"}, insight)
        assert "analysis_started_at" not in _on_disk(insight, "FP-H01")
        design_io.transition_status("FP-H01", "in_review", base_dir=insight)
        assert _on_disk(insight, "FP-H01")["analysis_started_at"]


class TestStartedConfirmation:
    """Epic 33 US-3 AC 2, AC 3: design_io refuses what validate_update refuses."""

    @pytest.fixture(params=["analyzing", "in_review", "revision_requested"])
    def started(self, insight: Path, request: pytest.FixtureRequest) -> str:
        design_id = _create(insight)["id"]
        path = {
            "analyzing": ["analyzing"],
            "in_review": ["analyzing", "in_review"],
            "revision_requested": ["analyzing", "in_review", "revision_requested"],
        }[request.param]
        for target in path:
            design_io.transition_status(design_id, target, base_dir=insight)
        return design_id

    def test_the_hypothesis_is_not_rewritten(self, insight: Path, started: str) -> None:
        with pytest.raises(ValueError, match="hypothesis_statement.*derive"):
            design_io.update_design(
                started, {"hypothesis_statement": "X improves Y a little"}, insight
            )
        assert _on_disk(insight, started)["hypothesis_statement"] == "X improves Y"

    def test_the_criterion_is_not_rewritten(self, insight: Path, started: str) -> None:
        looser = [{**_PRIMARY, "comparison": "supported at 0.5 days or more"}]
        with pytest.raises(ValueError, match="metrics.*derive"):
            design_io.update_design(started, {"metrics": looser}, insight)
        assert (
            _on_disk(insight, started)["metrics"][0]["comparison"]
            == (_PRIMARY["comparison"])
        )

    def test_the_background_is_still_edited(self, insight: Path, started: str) -> None:
        design_io.update_design(
            started, {"hypothesis_background": "because Z, as surveyed"}, insight
        )
        assert _on_disk(insight, started)["hypothesis_background"].endswith("surveyed")

    def test_a_saved_design_sent_back_keeps_its_hypothesis(self, insight: Path) -> None:
        _saved(insight, "FP-H01", status="analyzing")
        design_io.transition_status("FP-H01", "in_review", base_dir=insight)
        with pytest.raises(ValueError, match="hypothesis_statement"):
            design_io.update_design(
                "FP-H01", {"hypothesis_statement": "Written after the result"}, insight
            )


class TestCriterionBeforeTheAnalysis:
    """Epic 33 US-3 AC 4: a judging design is analyzed only with its criterion."""

    def test_a_transition_without_a_criterion_is_refused(self, insight: Path) -> None:
        design_id = _create(insight, metrics=[])["id"]
        with pytest.raises(ValueError, match="comparison"):
            design_io.transition_status(design_id, "analyzing", base_dir=insight)
        written = _on_disk(insight, design_id)
        assert written["status"] == "in_review"
        assert "analysis_started_at" not in written

    def test_an_update_without_a_criterion_is_refused(self, insight: Path) -> None:
        design_id = _create(insight, metrics=[])["id"]
        with pytest.raises(ValueError, match="comparison"):
            design_io.update_design(design_id, {"status": "analyzing"}, insight)
        assert _on_disk(insight, design_id)["status"] == "in_review"

    def test_an_approval_without_a_criterion_writes_no_batch(
        self, insight: Path
    ) -> None:
        design_id = _create(insight, metrics=[])["id"]
        with pytest.raises(ValueError, match="comparison"):
            design_io.append_review_batch(
                design_id, "analyzing", [{"comment": "ok"}], base_dir=insight
            )
        assert design_io.list_review_batches(design_id, insight) == []
        assert _on_disk(insight, design_id)["status"] == "in_review"

    def test_the_criterion_written_in_review_opens_the_analysis(
        self, insight: Path
    ) -> None:
        design_id = _create(insight, metrics=[])["id"]
        design_io.update_design(design_id, {"metrics": [_PRIMARY]}, insight)
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        assert _on_disk(insight, design_id)["status"] == "analyzing"

    def test_an_exploration_is_analyzed_without_a_criterion(
        self, insight: Path
    ) -> None:
        design_id = _explore(insight)["id"]
        design_io.transition_status(design_id, "analyzing", base_dir=insight)
        assert _on_disk(insight, design_id)["analysis_started_at"]

    def test_a_saved_design_without_a_criterion_returns_to_the_analysis(
        self, insight: Path
    ) -> None:
        _saved(insight, "FP-H01", status="analyzing")
        design_io.transition_status("FP-H01", "in_review", base_dir=insight)
        design_io.transition_status("FP-H01", "analyzing", base_dir=insight)
        assert _on_disk(insight, "FP-H01")["status"] == "analyzing"
