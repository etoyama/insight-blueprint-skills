# Test Review — Epic 09 (installable plugin execution model)

- Branch: `epic/9-installable-plugin` vs `main`
- Test run: `uv run pytest -q` → **367 passed** (deterministic order; no pytest-randomly/xdist installed)
- Scope: `bin/` wrappers, `hooks/hooks.json` + moved `hooks/validate-design.py`, `INSIGHT_BASE_DIR` env routing in `design_io`/`catalog_io`.

## Verdict

The changed unit tests are sound and pass. The hook suite fully survives the move and still
covers schema + transition block/allow. The real weakness is **the "installed form" has zero
automated coverage** — the wrappers and the env-routing-through-a-wrapper path were only
manually simulated, yet the Design Doc Test Matrix implies coverage that does not exist.

---

## 1. `tests/test_design_io.py::TestBaseDirEnv` — reload approach

**Sound.** Verified empirically:

- `importlib.reload(design_io)` mutates the module object **in place** (`reload(mod) is mod` → True),
  so `DEFAULT_BASE_DIR` is re-read from `os.environ` and other tests keep the same module object.
- `test_env_overrides_default` restores in a `finally` (delenv + reload) → state restored to `.insight`.
- `test_default_is_dot_insight` deletes the env then reloads → also lands on `.insight`. No leak.
- **No pollution risk in practice** regardless: no other test reads `design_io.DEFAULT_BASE_DIR`
  (grep confirms only these two tests reference it), and every I/O helper is called with an
  explicit `base_dir=insight`. The reload restore is belt-and-suspenders, not load-bearing.

Minor nit (Low): `test_default_is_dot_insight` has no `finally` restore. Harmless here (it already
reloads to the default), but for symmetry with the sibling test it could reload in a `finally`.
Not worth changing on its own.

## 2. `tests/test_validate_hook.py` — HOOK_PATH move

**Passes and coverage is intact (20 tests).** The move was clean: old `.claude/hooks/` retains
only a stale `__pycache__`, no `.py`; dev `.claude/settings.json` points at `hooks/validate-design.py`;
tests target the new path via `HOOK_PATH = REPO_ROOT / "hooks" / "validate-design.py"` and invoke
it as a real subprocess.

Coverage confirmed:
- Schema violation → exit 2 (`test_schema_violation_blocks`)
- Valid transition (Write + body-only edit on terminal) → exit 0
- Invalid transition via Write and via in-place Edit → exit 2 + "transition" in stderr (the headline guard)
- Malformed YAML → exit 2
- Non-design file ignored → exit 0
- All three tools (Write/Edit/MultiEdit) parametrized

Note (Low): subprocess uses `sys.executable` directly, exercising the hook's `sys.path` src-fallback
import of `insight_blueprint`. It does **not** exercise the `hooks.json` `uv run --project "${CLAUDE_PLUGIN_ROOT}"`
form. Acceptable — the src-fallback is the more fragile branch, and `uv run --project` is Claude Code
plumbing, not our code.

---

## Coverage GAPS

### GAP 1 — No integration test for `bin/` wrappers (installed form). Priority: **High**

**Missing.** `bin/design_io`, `bin/catalog_io`, `bin/premortem` are the entire point of Epic 09
and have **no automated test** (`grep` for `CLAUDE_PLUGIN_ROOT|CLAUDE_PROJECT_DIR|bin/design_io`
in `tests/` → NONE). The exact bug this Epic fixes (`ModuleNotFoundError: No module named 'skills'`
when run from a foreign cwd) is precisely what a wrapper test would catch on regression. Everything
else was "simulated" manually per AC7 and the Story Timeline.

The env unit test (`TestBaseDirEnv`) proves the module *reads* `INSIGHT_BASE_DIR`, but nothing
proves the **wrapper sets it correctly and the module then writes to the user project** — the
seam where the real bug lived.

Suggested test (`tests/integration/test_bin_wrappers.py`):

```python
import json, os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

def test_design_io_wrapper_writes_to_project_dir(tmp_path):
    proj = tmp_path / "userproj"
    proj.mkdir()
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(REPO),   # plugin = this repo
        "CLAUDE_PROJECT_DIR": str(proj),   # user project elsewhere
    }
    payload = json.dumps({
        "theme_id": "FP", "title": "t",
        "hypothesis_statement": "x improves y",
        "hypothesis_background": "z", "methodology": {"method": "OLS"},
    })
    # run from a cwd that is neither plugin nor project → the original failure mode
    r = subprocess.run(
        [str(REPO / "bin" / "design_io"), "create"],
        input=payload, env=env, cwd=tmp_path,
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    # AC2: .insight auto-created under CLAUDE_PROJECT_DIR, not cwd, not plugin
    assert (proj / ".insight" / "designs").is_dir()
    assert list((proj / ".insight" / "designs").glob("*_hypothesis.yaml"))
    assert not (tmp_path / ".insight").exists()

def test_wrapper_fails_loud_without_plugin_root(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    r = subprocess.run([str(REPO / "bin" / "design_io"), "create"],
                       input="{}", env=env, cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "CLAUDE_PLUGIN_ROOT" in r.stderr  # the `:?` guard fired
```

Caveats to document if adopting: (a) the wrappers `exec uv run`, so the test needs `uv` on PATH
(CI has it); (b) run only `design_io` + `catalog_io` (both hit `.insight` auto-create + env routing);
`premortem` is a thinner variant. This single file closes the highest-value gap.

### GAP 2 — `catalog_io` has NO `INSIGHT_BASE_DIR` unit test (asymmetry). Priority: **Medium**

`skills/_shared/catalog_io.py` got the identical `DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))`
change, but `tests/test_catalog_io.py` has **no `TestBaseDirEnv` equivalent** (its "reloaded"
references are unrelated — they re-read YAML, not the module). Only `design_io`'s env behavior is
locked down. A future edit to catalog's default would go uncaught.

Suggested: copy `TestBaseDirEnv` into `test_catalog_io.py` against `catalog_io` (2 tests, mechanical).
Note: if GAP 1's wrapper test also runs `bin/catalog_io`, that partially covers the same behavior
end-to-end; the unit test is still cheap insurance and keeps the two modules symmetric.

### GAP 3 — `hooks/hooks.json` is untested config. Priority: **Low**

`hooks.json` is JSON config Claude Code consumes; the hook *script* is well tested but the
`hooks.json` matcher/command string is not (e.g. a typo in `"${CLAUDE_PLUGIN_ROOT}"` or the
`Write|Edit|MultiEdit` matcher). A tiny schema/JSON-validity + field-shape test is possible but
low value — this is framework plumbing, and `test_plugin_structure.py` may already assert file
presence. Optional.

---

## False / overstated claims in the Design Doc Test Matrix

`docs/design/epic-09-installable-plugin.md` Story 9.1 row overstates coverage:

1. **`test_skill_structure` listed under Unit for AC3.** False. `test_skill_structure.py` checks
   frontmatter, required sections, chaining tables, versions, and framing-brief structure. It does
   **not** assert skill commands use the wrapper names (`design_io`/`catalog_io`/`premortem`) nor
   forbid raw `python -m skills._shared`. It was not modified in this Epic. AC3's "全 SKILL のコマンド
   統一" therefore has **no automated guard** — a skill silently reverting to `python -m ...` passes CI.
   (Low-priority follow-up: add a test asserting no SKILL.md contains `python -m skills._shared` and
   that command lines use wrapper names.)

2. **"✓ (notebook contract test)" under Integration for AC4.** Overstated. `tests/integration/
   test_analysis_notebook_contract.py` was **not changed** in this Epic and contains no reference to
   `uv run --project`, `--extra notebook`, or `CLAUDE_PLUGIN_ROOT`. It validates the notebook cell
   *contract*, not the Epic-09 *execution form*. So AC4 (notebook run form) has no automated coverage.

3. **"✓ E2E (simulate ...)" — the simulate was manual, not committed.** The matrix marks E2E ✓, but
   there is no committed simulate test (see GAP 1). The ✓ reflects a one-off manual run, not a
   regression guard. GAP 1's test is exactly what would make this ✓ truthful.

Recommend: either land GAP 1 (+ optionally the AC3 command-lint test) so the ✓ marks are backed by
committed tests, or downgrade the overstated cells to note "manual / not automated".

---

## Priority summary

| # | Gap | Priority |
|---|---|---|
| 1 | No committed integration test for `bin/` wrappers (installed form / env routing / `.insight` auto-create) | **High** |
| 2 | `catalog_io` lacks `INSIGHT_BASE_DIR` unit test (asymmetric vs `design_io`) | **Medium** |
| — | AC3 skill-command form has no lint/guard test | Medium (follow-up) |
| 3 | `hooks.json` config untested | Low |
| — | `test_default_is_dot_insight` missing `finally` restore | Low |
