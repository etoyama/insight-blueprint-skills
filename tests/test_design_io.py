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
        "base_dir": insight,
    }
    kwargs.update(over)
    return design_io.create_design(**kwargs)


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


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


class TestTransition:
    def test_valid_transition(self, insight: Path) -> None:
        d = _create(insight)
        out = design_io.transition_status(d["id"], "analyzing", base_dir=insight)
        assert out["status"] == "analyzing"

    def test_invalid_transition_raises_and_not_persisted(self, insight: Path) -> None:
        d = _create(insight)
        design_io.transition_status(d["id"], "analyzing", base_dir=insight)
        with pytest.raises(ValueError, match="transition"):
            design_io.transition_status(d["id"], "supported", base_dir=insight)
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
