"""Structure tests for the release docs (Epic 31, ADR-0047).

A release is a tag: docs/RELEASE.md tells to tag the merged `main` and check the tag
before it is pushed, and no living document offers a package published to PyPI.
"""

from __future__ import annotations

import re

import pytest

from tests.docs._changelog import changelog_entry
from tests.docs.test_canonical_docs import _read, _without_link_targets
from tests.skills._markdown import section, unwrap


class TestReleaseProcedure:
    """Existing plugin installs update only when plugin.json's version changes."""

    def test_intro_ties_plugin_updates_to_the_manifest_version(self) -> None:
        intro = _read("docs/RELEASE.md").split("\n## ", 1)[0]
        assert ".claude-plugin/plugin.json" in intro

    def test_version_bump_names_both_files(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 1")
        assert "pyproject.toml" in step
        assert ".claude-plugin/plugin.json" in step

    def test_intro_says_the_marketplace_serves_the_release_tag(self) -> None:
        intro = _read("docs/RELEASE.md").split("\n## ", 1)[0]
        assert "adr/0032-" in intro

    def test_version_bump_names_the_marketplace_ref(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 1")
        assert ".claude-plugin/marketplace.json" in step

    def test_missing_tag_error_is_named_where_it_can_happen(self) -> None:
        """Between the merge and the tag, the marketplace points at a tag that does not exist."""
        release = _read("docs/RELEASE.md")
        error = "Remote branch vX.Y.Z not found"
        assert error in section(release, "## Step 3")
        assert error in section(release, "## Troubleshooting")

    def test_a_failed_tag_check_bumps_the_patch_instead_of_moving_the_tag(self) -> None:
        """ADR-0047: protect-release-tags forbids moving a v* tag, so the fix is a new version."""
        trouble = unwrap(section(_read("docs/RELEASE.md"), "### Tag/version mismatch"))
        assert "Do not delete or move the tag" in trouble
        assert "patch" in trouble
        assert ".claude-plugin/marketplace.json" in trouble
        assert "git push --delete" not in trouble

    def test_verification_covers_the_plugin_the_marketplace_serves(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 4")
        assert (
            "claude plugin update insight-blueprint@insight-blueprint-marketplace"
            in step
        )

    def test_preflight_checks_the_tag_before_it_is_pushed(self) -> None:
        """A pushed v* tag cannot be moved, so the check runs locally first (ADR-0047)."""
        step = section(_read("docs/RELEASE.md"), "## Step 2")
        assert "uv run poe check-tag-version --tag vX.Y.Z" in step

    def test_the_tag_itself_is_checked_before_it_is_pushed(self) -> None:
        """Without --tag the script checks the tag on HEAD, so a mistyped tag fails here."""
        step = section(_read("docs/RELEASE.md"), "## Step 3")
        tag = step.index("git tag vX.Y.Z")
        check = re.search(
            r"^uv run poe check-tag-version(?!\s+--tag)", step, re.MULTILINE
        )
        assert check
        push = step.index("git push origin vX.Y.Z")
        assert tag < check.start() < push

    def test_the_tag_is_made_on_the_pulled_main(self) -> None:
        """A pushed v* tag cannot be moved, so it must land on the merged commit."""
        step = section(_read("docs/RELEASE.md"), "## Step 3")
        switch = step.index("git switch main")
        pull = step.index("git pull")
        tag = step.index("git tag vX.Y.Z")
        assert switch < pull < tag

    def test_tag_push_names_the_ci_check(self) -> None:
        step = section(_read("docs/RELEASE.md"), "## Step 3")
        assert ".github/workflows/ci.yml" in step
        assert "check_tag_version" in step

    def test_release_never_deletes_or_moves_a_pushed_tag(self) -> None:
        """protect-release-tags forbids it, and installs may have cached that version."""
        release = _read("docs/RELEASE.md")
        assert not re.search(
            r"git push\b[^\n]*(--delete|\s-d\b|\s:|--force|\s-f\b)"
            r"|git tag\b[^\n]*(--force|\s-f\b)",
            release,
        )

    @pytest.mark.parametrize("word", ["pypi", "twine", "publish.yml", "verify_wheel"])
    def test_release_ships_only_the_plugin(self, word: str) -> None:
        """Epic 31 US-2 AC 3: nothing is published to PyPI any more."""
        assert word not in _without_link_targets(_read("docs/RELEASE.md")).lower()


class TestPypiPublishingStopped:
    """Epic 31 US-3: the docs no longer present a package published to PyPI."""

    def test_architecture_outside_the_epic_mapping_has_no_pypi(self) -> None:
        text = _read("docs/ARCHITECTURE.md")
        body = text.replace(section(text, "## Epic マッピング"), "")
        assert "pypi" not in _without_link_targets(body).lower()
        assert "publish.yml" not in body

    def test_architecture_release_invariant_names_the_ci_check(self) -> None:
        invariants = section(_read("docs/ARCHITECTURE.md"), "## 不変条件（invariants）")
        release = next(line for line in invariants.splitlines() if "tag 駆動" in line)
        assert "check_tag_version" in release

    def test_changelog_upgrade_note_tells_what_stopping_the_upload_means(self) -> None:
        note = unwrap(
            section(
                changelog_entry(
                    _read("CHANGELOG.md"), "is no longer published to PyPI"
                ),
                "### Upgrade note",
            )
        )
        assert "0.17.0" in note
        assert "archive" in note
        assert "git+https://github.com/etoyama/insight-blueprint-skills@" in note
        assert "`src/insight_blueprint/models/`" in note
