# Release Procedure

This repository ships **two things**, released differently:

- **The Claude Code plugin** (skills + hook + `.insight/` conventions) is distributed
  straight from this Git repository via the marketplace in
  [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json). Merging to `main`
  makes the latest plugin available; there is no separate build/publish step for it.
- **The `insight-blueprint` Python package** (the lineage + validation library under
  `src/insight_blueprint/`, used optionally via `uv add insight-blueprint`) is published to
  **PyPI**, and that is what this document covers.

Publishing to PyPI is **tag-driven and automated**: pushing a `v*` tag runs
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml), which builds, verifies,
and uploads to PyPI via a trusted publisher (OIDC — no API token to manage).

## Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**.
- Push access to `main` and permission to push tags.
- PyPI credentials are **not** needed locally — publishing uses the repo's `pypi`
  environment (OIDC trusted publisher) inside CI.

## Step 1: Version bump

Update `version` in `pyproject.toml` following [SemVer](https://semver.org/):

- **Patch** (0.1.0 → 0.1.1): bug fixes, docs
- **Minor** (0.1.0 → 0.2.0): new features, backward-compatible
- **Major** (0.1.0 → 1.0.0): breaking changes

Move the `## [Unreleased]` notes in [CHANGELOG.md](../CHANGELOG.md) under the new version.
Commit on a branch and merge to `main` before tagging (the tag must point at the commit
whose `pyproject.toml` version matches it).

## Step 2: Local pre-flight

Run the same checks CI will run, so a bad tag never reaches PyPI:

```bash
uv run poe all                          # lint + typecheck + test
uv build                                # build sdist + wheel into dist/
uv run python scripts/verify_wheel.py   # assert insight_blueprint/py.typed is present (PEP 561)
uvx --from twine twine check dist/*     # validate package metadata
uv run python scripts/check_tag_version.py --tag vX.Y.Z   # tag == pyproject version
```

## Step 3: Tag and push

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

This triggers `publish.yml`, which re-runs `check_tag_version` → `uv build` →
`verify_wheel` → `twine check`, then publishes to PyPI from the `pypi` environment.

## Step 4: Verify the release

```bash
# PyPI page
open https://pypi.org/project/insight-blueprint/

# Fresh install of the library (there is no CLI; verify it imports)
uv run --with insight-blueprint --no-project python -c "import insight_blueprint; print(insight_blueprint.__name__)"
```

## Troubleshooting

### "File already exists" on publish

PyPI does not allow overwriting a version. Bump `version`, re-tag with the new `vX.Y.Z`,
and push again.

### Tag/version mismatch

`check_tag_version.py` fails the build if the `v*` tag does not equal `pyproject.toml`'s
`version`. Fix one so they match, delete the bad tag (`git tag -d` / `git push --delete`),
and re-tag.

### `verify_wheel` fails

The wheel must contain `insight_blueprint/py.typed`. Ensure `py.typed` exists under
`src/insight_blueprint/` and that `[tool.hatch.build.targets.wheel]` includes the package.
