"""Tests for the helper that finds a CHANGELOG entry wherever a release moved it.

A release moves the notes from `## [Unreleased]` to `## [X.Y.Z] - date`. A structure
test that names either heading breaks at a release or at the next Epic's first note,
so it finds the notes by a phrase in them instead.
"""

from __future__ import annotations

import pytest

from tests.docs._changelog import changelog_entry

HEAD = "# Changelog\n\nPreamble that mentions nothing.\n\n"


def test_an_unreleased_note_is_found_in_unreleased() -> None:
    changelog = (
        HEAD
        + "## [Unreleased]\n\n- Stopped the upload.\n\n## [0.1.0] - 2026-01-01\n\n- Old.\n"
    )
    assert (
        changelog_entry(changelog, "Stopped the upload")
        == "\n- Stopped the upload.\n\n"
    )


def test_a_released_note_is_found_in_its_version_when_unreleased_is_empty() -> None:
    changelog = (
        HEAD + "## [Unreleased]\n\n## [9.9.9] - 2099-01-01\n\n- Stopped the upload.\n"
    )
    assert (
        changelog_entry(changelog, "Stopped the upload") == "\n- Stopped the upload.\n"
    )


def test_a_released_note_is_still_found_after_the_next_epic_adds_a_note() -> None:
    changelog = (
        HEAD
        + "## [Unreleased]\n\n- Something new.\n\n"
        + "## [9.9.9] - 2099-01-01\n\n- Stopped the upload.\n"
    )
    assert (
        changelog_entry(changelog, "Stopped the upload") == "\n- Stopped the upload.\n"
    )


def test_the_phrase_may_span_a_line_break() -> None:
    changelog = HEAD + "## [Unreleased]\n\n- Stopped the\n  upload.\n"
    assert "Stopped the" in changelog_entry(changelog, "Stopped the upload")


def test_the_entry_keeps_its_subsections() -> None:
    changelog = (
        HEAD
        + "## [Unreleased]\n\n### Upgrade note\n\n- Stopped the upload.\n\n### Changed\n\n- X.\n"
    )
    assert "### Changed" in changelog_entry(changelog, "Stopped the upload")


def test_a_phrase_in_no_entry_fails() -> None:
    changelog = HEAD + "## [Unreleased]\n\n- Something else.\n"
    with pytest.raises(AssertionError, match="no CHANGELOG entry"):
        changelog_entry(changelog, "Stopped the upload")


def test_a_phrase_outside_the_entries_is_not_an_entry() -> None:
    changelog = HEAD.replace("nothing", "Stopped the upload") + "## [Unreleased]\n"
    with pytest.raises(AssertionError, match="no CHANGELOG entry"):
        changelog_entry(changelog, "Stopped the upload")


def test_a_phrase_in_two_entries_fails_and_names_both() -> None:
    changelog = (
        HEAD
        + "## [Unreleased]\n\n- Stopped the upload again.\n\n"
        + "## [9.9.9] - 2099-01-01\n\n- Stopped the upload.\n"
    )
    with pytest.raises(AssertionError, match=r"\[Unreleased\].*\[9\.9\.9\]"):
        changelog_entry(changelog, "Stopped the upload")
