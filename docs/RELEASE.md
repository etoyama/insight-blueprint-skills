# Release Procedure

This repository ships **one thing**: the Claude Code plugin (skills + hook + `.insight/`
conventions). It is distributed straight from this Git repository via the marketplace in
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json). There is no build or
upload step. The marketplace entry points at the release tag (`ref` in `marketplace.json`), so
an install gets the tagged commit and a merge to `main` reaches nobody until the next release
([ADR-0032](adr/0032-marketplace-serves-the-release-tag.md)).
Claude Code caches an installed plugin under its version, so **existing installs pick up new
content only when `version` in [`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json)
changes**.

The library under `src/insight_blueprint/` runs only inside the plugin env, which
`uv run --project "${CLAUDE_PLUGIN_ROOT}"` builds from the tagged source
([ADR-0047](adr/0047-stop-publishing-to-pypi.md)).

A release is **tag-driven**: pushing a `v*` tag makes the marketplace serve that commit, and
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) checks that the tag matches the
`pyproject.toml` version.

## Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**.
- Push access to `main` and permission to push tags.

## Step 1: Version bump

Update `version` in **both** `pyproject.toml` and `.claude-plugin/plugin.json`, following
[SemVer](https://semver.org/), and set the plugin's `ref` in `.claude-plugin/marketplace.json`
to the new tag (`vX.Y.Z`). `tests/test_plugin_structure.py` fails when the three differ:

- **Patch** (0.1.0 → 0.1.1): bug fixes, docs
- **Minor** (0.1.0 → 0.2.0): new features, backward-compatible
- **Major** (0.1.0 → 1.0.0): breaking changes

Move the `## [Unreleased]` notes in [CHANGELOG.md](../CHANGELOG.md) under the new version,
and update the comparison links at the bottom of the file.
Commit on a branch and merge to `main` before tagging (the tag must point at the commit
whose `pyproject.toml` version matches it).

## Step 2: Local pre-flight

Run the checks on the version-bump branch, before it is merged: once it is merged, plugin
installs fail until the tag is pushed (Step 3).

```bash
uv run poe all                                   # lint + typecheck + test
uv run poe check-tag-version --tag vX.Y.Z        # tag == pyproject version
```

Run the tag check before you push the tag. A pushed `v*` tag cannot be deleted or moved
(the `protect-release-tags` ruleset), so a wrong tag stays until the next version replaces it.

## Step 3: Tag and push

Tag the merged commit on `main`, not the version-bump branch: a pushed `v*` tag cannot be moved,
so a tag on any other commit stays wrong.

```bash
git switch main
git pull --ff-only origin main
git tag vX.Y.Z
uv run poe check-tag-version     # no --tag: checks the tag on HEAD, so a mistyped tag fails here
git push origin vX.Y.Z
```

If the check fails, delete the local tag (`git tag -d <tag>`) and tag again. It is not pushed
yet, so nothing has served it.

The push runs [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) on the tag. Its
`tag-version` job runs `scripts/check_tag_version.py` and fails if the tag differs from the
`pyproject.toml` version of the tagged commit.

Push the tag right after the version bump is merged. From the merge until the tag exists, the
marketplace on `main` points at a tag that is not there: a new install or an update fails with
`Remote branch vX.Y.Z not found`, and existing installs keep the version they have.

## Step 4: Verify the release

```bash
# The tag-version job passed on the tag push
gh run list --workflow ci.yml --branch vX.Y.Z

# The plugin the marketplace serves: expect "updated from … to X.Y.Z"
claude plugin marketplace update insight-blueprint-marketplace
claude plugin update insight-blueprint@insight-blueprint-marketplace
```

## Troubleshooting

### Tag/version mismatch

The `tag-version` job in `ci.yml` fails when the `v*` tag does not equal the `version` in
`pyproject.toml` of the tagged commit. Do not delete or move the tag: the
`protect-release-tags` ruleset forbids it, and installs may already have cached that version.
Instead, bump the patch version (Step 1) in `pyproject.toml` and `.claude-plugin/plugin.json`,
set `ref` in `.claude-plugin/marketplace.json` to the new tag, and tag the right commit with
the new `vX.Y.Z` (Steps 2 and 3). The wrong tag's version is replaced by the next update.

### Plugin install fails with "Remote branch vX.Y.Z not found"

The `ref` in `.claude-plugin/marketplace.json` names a tag that does not exist: the version bump
is merged but the tag is not pushed yet. Push the tag (Step 3). Do not move a pushed tag to a
commit with other plugin content: installs that already cached that version keep the old content.
