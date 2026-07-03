# Quality Review — Epic 09 (installable plugin execution model)

Branch: `epic/9-installable-plugin` vs `main`. Reviewer scope: bin/ wrappers, `_shared` env
change, SKILL command rewrites, moved validation hook.

## Verdict

The execution-model change is well-designed and the mechanical parts are clean: wrappers are
POSIX-portable (pass `dash -n`), executable bits set, SKILL rewrites are complete and consistent,
and the hook move actually *fixes* the `src` path fallback. **One real correctness bug**: the
`premortem` wrapper's `INSIGHT_BASE_DIR`/`.insight` plumbing is dead — `cli.py` reads config from a
hardcoded relative path after the wrapper `cd`s into the plugin root, so it silently ignores the
user's project config.

---

## Findings

### High

**H1 — `bin/premortem` reads config from the plugin dir, not the user's project (silent wrong config)**
- File: `skills/premortem/cli.py:24-25`, `skills/premortem/cli.py:121`; wrapper `bin/premortem:9-12`.
- Current: `bin/premortem` does `cd "${CLAUDE_PLUGIN_ROOT}"` and exports
  `INSIGHT_BASE_DIR="$proj/.insight"`. But `cli.py` never reads `INSIGHT_BASE_DIR`; it uses
  `_CONFIG_PATH = Path(".insight/config.yaml")` (relative) and `_DEFAULT_BASE_DIR = Path(".insight")`.
  After the `cd`, `Path(".insight/config.yaml")` resolves to `<plugin_root>/.insight/config.yaml`,
  which does not exist, so `load_premortem_config` (config_loader.py:25-26) silently falls back to
  `PremortemConfig()` defaults. A user who tuned risk thresholds in their project
  `.insight/config.yaml` gets them ignored with no warning.
- Unlike `design_io`/`catalog_io` (which correctly consume `INSIGHT_BASE_DIR` via `DEFAULT_BASE_DIR`),
  premortem's env export is a no-op. The `bin/premortem` `INSIGHT_BASE_DIR` line and `mkdir` are also
  present but unused by cli.py.
- Suggestion: make `cli.py` honor the env, mirroring the `_shared` modules. E.g.
  `_DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))` and derive
  `_CONFIG_PATH = _DEFAULT_BASE_DIR / "config.yaml"` (or have `main` build the config path from
  `args.base_dir`). Add a unit test analogous to `TestBaseDirEnv` in test_design_io.py.

### Medium

**M2 — premortem `--base-dir` argument is dead code**
- File: `skills/premortem/cli.py:40-45`.
- Current: `--base-dir` is parsed (`args.base_dir`) but never referenced anywhere in `main`. It is
  `argparse.SUPPRESS`ed as a "testing override" yet overrides nothing. This is the flip side of H1:
  the arg that *should* have driven the config/base path is inert.
- Suggestion: wire `args.base_dir` into the config path (fixes H1 and gives the test hook a real
  effect), or delete the arg if truly unused. Do not leave a suppressed no-op.

### Low

**L3 — bin wrappers are near-identical; duplication is acceptable but the `mkdir` block could be shared**
- Files: `bin/design_io:14-23`, `bin/catalog_io:11-18`, `bin/premortem:5-14`.
- Current: `design_io` and `catalog_io` are byte-for-byte identical except the final `exec` module
  and the header comment; `premortem` is the same preamble minus the `mkdir` block. The shared
  preamble is ~8 lines (`set -e`, `proj=`, `cd CLAUDE_PLUGIN_ROOT`, `INSIGHT_BASE_DIR`,
  `UV_PROJECT_ENVIRONMENT`, `mkdir -p`).
- Assessment: for three ~15-line scripts, the duplication is **acceptable** — a shared helper
  (`. "$(dirname "$0")/_common.sh"`) adds a sourcing indirection and a fourth file for marginal
  savings, and the ADR explicitly chose "集約は bin ラッパー" over inlining. Not worth extracting now.
  Flagging only so it's a conscious call: if a 4th wrapper appears, extract then.
- Consistency nit: `bin/premortem` omits the `mkdir -p .insight/...` block that the other two have.
  premortem is report-only (writes nothing), so this is correct — but if a user runs `/premortem`
  as their very first action in a fresh project, `INSIGHT_BASE_DIR` points at a dir that may not
  exist. Harmless today (premortem doesn't read the tree, and once H1 is fixed it reads config
  which tolerates absence), so no change required.

**L4 — `set -e` correctness: fine, but no `set -u` despite relying on defaulted vars**
- Files: all three wrappers, line 4 (`set -e`).
- Current: `set -e` is correct here — the only commands that can fail (`cd`, `mkdir`, `exec uv`)
  should abort, and the `:?` expansion on `CLAUDE_PLUGIN_ROOT` gives a clear message + non-zero exit
  when unset (verified: this is the intended guard and it works under `sh`/`dash`). The `${VAR:-…}`
  and `${VAR:?…}` forms are POSIX; no bashisms. Good.
- Note: `set -u` is *not* set, which is the right call — the scripts intentionally read possibly-unset
  vars (`CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_DATA`) with `:-` defaults, and `CLAUDE_PLUGIN_ROOT` is
  guarded explicitly with `:?`. Adding `set -u` would be redundant/risky. No change; documenting that
  the omission is deliberate and correct.

**L5 — `_shared` module docstrings still show the old invocation form**
- Files: `skills/_shared/design_io.py:11`, `skills/_shared/catalog_io.py:12-13`.
- Current: module docstrings still say
  `echo '<json>' | python -m skills._shared.design_io create --base-dir .insight`. These are
  dev/maintainer-facing (module header), and `--base-dir` remains supported for back-compat, so they
  are not *wrong*. But they no longer match the SKILL-facing `design_io …` wrapper form.
- Suggestion (optional): add a one-line note that installed usage goes through the `bin/` wrapper /
  `INSIGHT_BASE_DIR`, so a maintainer reading the module doesn't think `--base-dir` is the canonical
  path. Low priority.

---

## Confirmed correct (no action)

- **SKILL command rewrites — complete and consistent.** No leftover
  `uv run python -m skills._shared` in any `skills/**/*.md`; no leftover `skills.premortem.cli`;
  no stray `--base-dir` or "project root" phrasing in SKILL docs. All ~11 files use the bare
  `design_io` / `catalog_io` / `premortem` wrapper names. The "available on PATH via the plugin"
  reference-line phrasing is uniform across analysis-design/journal/reflection/review/revision and
  catalog-register/knowledge-extract. Notebook commands consistently use
  `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook` in both SKILL.md and
  references/notebook-contract.md. The framing SKILL's stale `insight-blueprint init` guidance was
  correctly removed and replaced with "created automatically by the wrappers".
- **`DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))`** in design_io.py:37 /
  catalog_io.py:37 — clean. Module-import-time env read is fine *because* the `bin/` wrapper exports
  `INSIGHT_BASE_DIR` before `uv run python -m …` starts the process, so the value is always present at
  import. `--base-dir default=str(DEFAULT_BASE_DIR)` correctly threads the env value into the arg
  default. Covered by new `TestBaseDirEnv` (uses `importlib.reload` to re-trigger the import-time
  read — the right way to test this). Both tests pass.
- **hook move — `parents[1]` fallback is correct.** Script moved from `.claude/hooks/` to `hooks/`.
  `_REPO_ROOT = Path(__file__).resolve().parents[1]` now = repo root, so `<root>/src` resolves
  correctly. This is actually a *fix*: at the old `.claude/hooks/` location `parents[1]` would have
  been `.claude/`, making the `src` fallback wrong. `test_validate_hook.py` HOOK_PATH updated to the
  new location; 20 hook tests pass. Old `.claude/hooks/` is untracked (only a stale local
  `__pycache__`), so the git move is clean.
- **Dual hook registration is intentional, not a double-run.** `.claude/settings.json`
  (`uv run python hooks/validate-design.py`) is dev-only project config; `hooks/hooks.json`
  (`uv run --project "${CLAUDE_PLUGIN_ROOT}" …`) is the shipped plugin hook. An installed user gets
  only the plugin one; a dev working in this repo gets only settings.json. No overlap.
- **Portability.** All three wrappers pass `sh -n` and `dash -n`; `#!/usr/bin/env sh`; only POSIX
  parameter expansions. Executable bits set (`-rwxr-xr-x`).

## Test status
`pytest tests/test_design_io.py::TestBaseDirEnv tests/test_validate_hook.py` → 22 passed.
