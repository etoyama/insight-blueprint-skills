# Architecture Review — Epic 09 (installable plugin execution model)

Branch `epic/9-installable-plugin` vs `main`. Reviewed: `git diff main...HEAD`, ADR-0006,
`docs/design/epic-09-installable-plugin.md`, all changed files, plus ARCHITECTURE/CLAUDE/README.

## Verdict

The core design is **sound and correctly solves the "plugin doesn't run in an installed
project" problem** for the `design_io` / `catalog_io` / hook / notebook paths. bin wrappers
on PATH + `cd ${CLAUDE_PLUGIN_ROOT}` + plugin's own uv env (self-providing `insight_blueprint`
and `skills._shared`) + `INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight` is the right shape:
it decouples *code location* (plugin) from *data location* (user project) cleanly, and the
`.insight/*` mkdir removes the stale init step. 367 tests green. Docs (ADR/Epic/ARCHITECTURE/
CLAUDE/README) are consistent with each other and with the implementation.

But there is **one real correctness gap in the premortem path** and a couple of loose ends.

---

## Findings

### F1 — premortem ignores INSIGHT_BASE_DIR; user config silently dropped when installed  [HIGH]

- **Location**: `skills/premortem/cli.py:24-25,41-45,121`, `bin/premortem:9`,
  `skills/_shared/config_loader.py:25-26`
- **Concern**: `bin/premortem` `cd`s to `${CLAUDE_PLUGIN_ROOT}` and exports
  `INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight` — exactly like the other two wrappers.
  But `premortem/cli.py` never reads `INSIGHT_BASE_DIR`. Its `--config` defaults to a **relative**
  `Path(".insight/config.yaml")`, which after the `cd` resolves against the plugin root, not the
  user project. `load_premortem_config` treats a missing file as "use defaults" (config_loader.py:25),
  so it fails **silently**: the user's project-level premortem thresholds in
  `${CLAUDE_PROJECT_DIR}/.insight/config.yaml` are ignored, and premortem reports against built-in
  defaults. No crash, so it slips past the "simulate" test — this is exactly the class of bug the
  Epic set out to kill (data resolving to the wrong root), just in the one CLI the wrappers don't
  actually wire through.
- **Secondary**: `--base-dir` in premortem is fully dead — parsed at cli.py:41 but never referenced
  in `main`. `catalog_io`/`design_io` still honor `--base-dir` via `DEFAULT_BASE_DIR`; premortem does
  not, so the "`--base-dir` kept for back-compat" story (ADR §Decision) is **not uniformly true**.
- **Suggestion**: Make premortem read the env like the others. Cheapest coherent fix:
  ```python
  _DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))
  _CONFIG_PATH = _DEFAULT_BASE_DIR / "config.yaml"
  ```
  and either drop the dead `--base-dir` or actually derive `--config` from it. Add a unit test
  mirroring `TestBaseDirEnv` in `test_design_io.py` so premortem's env resolution is covered.

### F2 — `pyproject.toml` typecheck task still points at the emptied `.claude/hooks/`  [MEDIUM]

- **Location**: `pyproject.toml:102` (`cmd = "uv run ty check src/ .claude/hooks/ skills/"`),
  also the stale comment at `pyproject.toml:64-66`.
- **Concern**: The hook moved to `hooks/validate-design.py`, but the ty task and the ruff comment
  still reference `.claude/hooks/`, which now holds only `__pycache__`. `ty` tolerates the empty
  dir today (it didn't error), so CI stays green *by luck* — but the sole design-validation
  enforcement point (`hooks/validate-design.py`) is **no longer under the type-check authority**
  that CLAUDE.md §10 explicitly requires for it. A future type regression in the hook would ship
  unnoticed.
- **Suggestion**: Change to `uv run ty check src/ hooks/ skills/` and update the comment block at
  lines 64-66 to say `hooks/`. Delete the empty `.claude/hooks/` dir.

### F3 — Double-hook when developing in-repo (redundant, not harmful)  [LOW]

- **Location**: `.claude/settings.json:9` (`uv run python hooks/validate-design.py`) +
  `hooks/hooks.json:9` (plugin, `uv run --project ${CLAUDE_PLUGIN_ROOT} ...`).
- **Concern**: If a contributor has the plugin enabled while working in this repo, both hooks fire
  on the same `Write|Edit|MultiEdit`. Validation is a pure, idempotent, read-only check, so the
  worst case is running it twice (slightly slower, possibly a duplicated block message). Not a
  correctness bug. Worth a one-line note so nobody "fixes" it by deleting the dev wiring (which
  would break in-repo dev when the plugin isn't enabled). ADR-0006 §Decision already anticipates
  the dual wiring; CLAUDE.md §8 now documents it. Acceptable as-is.
- **Suggestion**: None required. Optionally add a comment in `.claude/settings.json` (or a line in
  the Epic doc's Decisions) noting the intentional overlap.

### F4 — notebook relative-path side-effects vs INSIGHT_BASE_DIR: two resolution models  [LOW]

- **Location**: `skills/analysis-notebook/references/notebook-contract.md:49,90-106`,
  `skills/analysis-notebook/SKILL.md:41-46`.
- **Concern**: notebook execution keeps **cwd = user project** and uses `--project
  ${CLAUDE_PLUGIN_ROOT} --extra notebook`, so the notebook's hardcoded relative writes
  (`.insight/notebooks/{id}_verdict.json`, `.insight/lineage/{id}.mmd`) land in the user project.
  This is coherent *for the documented flow* (commands run from project root). But it is a
  **different resolution model** from `design_io`/`catalog_io`, which resolve via the absolute
  `INSIGHT_BASE_DIR`. If a user ever runs a notebook command from a subdirectory, verdict/lineage
  land in `<subdir>/.insight` while `design_io` writes to `<project>/.insight` — a split-brain. The
  contract does say "run from your project directory," so this is a documented constraint, not a
  bug. Flagging the latent divergence, not asking for a rewrite.
- **Suggestion**: Leave as-is for this Epic. If it ever bites, have the notebook cells resolve
  output under `os.environ.get("INSIGHT_BASE_DIR", ".insight")` to unify on one model.

### F5 — Version story: pyproject/plugin.json still 0.7.0  [LOW / informational]

- **Location**: `pyproject.toml:3` (`version = "0.7.0"`), `.claude-plugin/plugin.json:3`
  (`"version": "0.7.0"`).
- **Concern**: ADR-0006 and the Epic doc both say "merge後 0.7.1 patch release." Versions are
  still 0.7.0 on the branch. This is consistent with a tag-driven release (`publish.yml` on `v*`),
  where the bump happens at release time, so it's likely intentional — just confirm the 0.7.1 bump
  isn't expected to be in this PR.
- **Suggestion**: Confirm whether the version bump belongs in the Epic PR or the release step. No
  change if the release workflow owns it.

---

## Invariants check (all respected)

- **No daemon / no MCP server / no SQLite**: wrappers and hook are one-shot `uv run` invocations;
  nothing long-lived is introduced. `.mcp.json` only carries the unrelated dev-time `spec-workflow`
  server. PASS.
- **validate.py single source**: hook (`hooks/validate-design.py:123`) and `design_io` both delegate
  to `insight_blueprint.validate`; no second validation path introduced. The new CLAUDE.md §8 line
  ("both the tool-write and helper-write paths are guarded") is accurate — both funnel to the same
  library. PASS.
- **`.insight/` skill-managed layout**: wrappers create exactly `designs / catalog/sources /
  catalog/knowledge`, matching §7. PASS.

## Coupling assessment

wrappers → modules → plugin env is a clean one-directional chain: the wrapper owns cwd/env/dirs,
the module owns logic (Module Responsibilities table holds). The `--base-dir` (back-compat) vs
`INSIGHT_BASE_DIR` (new) duality is **only mildly confusing and only because premortem breaks it**
(F1): for design_io/catalog_io the env sets the default and `--base-dir` overrides it — a normal
env-default/flag-override pattern, fine. Fixing F1 makes the dual mechanism uniform and the
confusion goes away.

## Bottom line

Architecturally the fix is correct and well-documented. **F1 (premortem) is a genuine
install-time correctness gap and should be fixed before the 0.7.1 release** — it's the same
wrong-root failure mode the Epic exists to eliminate, hiding behind a silent config fallback.
F2 should be fixed to keep the hook under the type-check authority CLAUDE.md mandates. F3–F5 are
low/informational.
