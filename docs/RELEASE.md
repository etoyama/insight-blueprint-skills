# Release Procedure

This repository ships **two things**, released differently:

- **The Claude Code plugin** (skills + hook + `.insight/` conventions) is distributed
  straight from this Git repository via the marketplace in
  [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json). There is no
  separate build/publish step for it. The marketplace entry points at the release tag
  (`ref` in `marketplace.json`), so an install gets the tagged commit and a merge to `main`
  reaches nobody until the next release ([ADR-0032](adr/0032-marketplace-serves-the-release-tag.md)).
  Claude Code caches an installed plugin under its version, so **existing installs pick up new
  content only when `version` in [`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json)
  changes**.
- **The `insight-blueprint-lineage` Python package** (the lineage + validation library under
  `src/insight_blueprint/` — the import name stays `insight_blueprint`, used optionally via
  `uv add insight-blueprint-lineage`) is published to **PyPI**, and that is what this document covers.

Publishing to PyPI is **tag-driven and automated**: pushing a `v*` tag runs
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml), which builds, verifies,
and uploads to PyPI via a trusted publisher (OIDC — no API token to manage).

## Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**.
- Push access to `main` and permission to push tags.
- PyPI credentials are **not** needed locally — publishing uses the repo's `pypi`
  environment (OIDC trusted publisher) inside CI.

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

Run the same checks CI will run, so a bad tag never reaches PyPI. Run them on the version-bump
branch, before it is merged: once it is merged, plugin installs fail until the tag is pushed
(Step 3).

```bash
uv run poe all                          # lint + typecheck + test
uv build                                # build sdist + wheel into dist/
uv run python scripts/verify_wheel.py   # assert insight_blueprint/py.typed is present (PEP 561)
uvx --from twine twine check dist/*     # validate package metadata
uv run python scripts/check_tag_version.py --tag vX.Y.Z   # tag == pyproject version
```

These checks do not cover the upload itself. `pypa/gh-action-pypi-publish` validates the
files with the twine **bundled in the action**, which can be older than the twine `uvx` runs
here, so a local `twine check` can pass while the publish job rejects the same wheel
(this happened with v0.9.0). Before tagging:

```bash
gh pr list --author app/dependabot --search "gh-action-pypi-publish in:title"   # open updates of the publish action
```

Merge any open Dependabot update of `gh-action-pypi-publish` first. The workflow runs from
the tagged commit, so an update merged after the tag does not apply to it.

## Step 3: Tag and push

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

This triggers `publish.yml`, which re-runs `check_tag_version` → `uv build` →
`verify_wheel` → `twine check`, then publishes to PyPI from the `pypi` environment.

Push the tag right after the version bump is merged. From the merge until the tag exists, the
marketplace on `main` points at a tag that is not there: a new install or an update fails with
`Remote branch vX.Y.Z not found`, and existing installs keep the version they have.

## Step 4: Verify the release

```bash
# PyPI page
open https://pypi.org/project/insight-blueprint-lineage/

# Fresh install of the library (there is no CLI; verify it imports)
uv run --with insight-blueprint-lineage --no-project python -c "import insight_blueprint; print(insight_blueprint.__version__)"

# The plugin the marketplace serves: expect "updated from … to X.Y.Z"
claude plugin marketplace update insight-blueprint-marketplace
claude plugin update insight-blueprint@insight-blueprint-marketplace
```

## Troubleshooting

### "File already exists" on publish

PyPI does not allow overwriting a version. Bump `version`, re-tag with the new `vX.Y.Z`,
and push again.

### Tag/version mismatch

`check_tag_version.py` fails the build if the `v*` tag does not equal `pyproject.toml`'s
`version`. Fix one so they match, delete the bad tag (`git tag -d` / `git push --delete`),
and re-tag.

### "not a valid metadata version" on publish

The build backend wrote a newer core metadata version than the twine bundled in
`gh-action-pypi-publish` accepts. Nothing was uploaded, so the version can be reused:
merge the update of the action into `main`, delete the tag (`git tag -d vX.Y.Z` /
`git push --delete origin vX.Y.Z`), then tag the new `main` commit and push again.

The marketplace already served the first tag, so this re-tag moves a tag that plugin installs
may have cached. Merge nothing else in between: then the two commits differ only in the
workflow file, and the plugin content under that version stays one.

### Plugin install fails with "Remote branch vX.Y.Z not found"

The `ref` in `.claude-plugin/marketplace.json` names a tag that does not exist: the version bump
is merged but the tag is not pushed yet, or the tag was deleted for a re-tag. Push the tag
(Step 3). Do not move a pushed tag to a commit with other plugin content: installs that already
cached that version keep the old content.

### `verify_wheel` fails

The wheel must contain `insight_blueprint/py.typed`. Ensure `py.typed` exists under
`src/insight_blueprint/` and that `[tool.hatch.build.targets.wheel]` includes the package.
