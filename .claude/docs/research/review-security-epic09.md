# Security Review — Epic 09 (installable plugin execution model)

Branch `epic/9-installable-plugin` vs `main`. Scope: `bin/*` sh wrappers,
`hooks/hooks.json`, `hooks/validate-design.py` (moved), `skills/_shared/{design_io,catalog_io}.py`
(`INSIGHT_BASE_DIR` env). Reviewed against `git diff main...HEAD`.

## Summary

Overall the change is defensively written: every shell expansion in the wrappers is
double-quoted, `"$@"` passthrough is correct, there is no `eval`/backtick/word-split
risk, `set -e` is set, and `CLAUDE_PLUGIN_ROOT` is `:?`-guarded. The pre-existing
`design_id` path-traversal guard (`SAFE_ID_PATTERN.fullmatch`) still holds.

No **Critical** findings. The material issues are (a) `INSIGHT_BASE_DIR` /
`--base-dir` is trusted verbatim and never validated, so path containment depends
entirely on the caller, and (b) the validation hook is a silent fail-open guard whose
new `uv run --project` invocation adds more ways to fail open. Both are Medium.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 4 |

---

## Findings

### M1 (Medium) — `INSIGHT_BASE_DIR` / `--base-dir` is unvalidated; containment is caller-trust only
`skills/_shared/design_io.py:37`, `skills/_shared/catalog_io.py:37`, and the
`--base-dir` CLI arg (`design_io.py:360`, `catalog_io.py:344`).

```python
DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR", ".insight"))
```

The base dir flows straight into every read/write path (`_designs_dir`, `_sources_dir`,
`atomic_write_yaml`) with no check. The `design_id` guard (`SAFE_ID_PATTERN`) only
protects the *leaf* segment — it does nothing for the base. So whoever controls
`INSIGHT_BASE_DIR` (or passes `--base-dir`) chooses where the tool reads and writes YAML,
including absolute paths and `..`.

In the intended flow this is fine: the wrapper sets
`INSIGHT_BASE_DIR="$proj/.insight"` and `proj` falls back to `$PWD`, so it can never
be empty and never yields `/.insight`. The risk is that the module treats an
attacker-influenceable env var / arg as fully trusted, so any *future* caller that sets
it from less-trusted input (or a wrapper regression) becomes an arbitrary-path
write primitive with no defense in depth.

**Recommended fix**: resolve and assert containment where it matters. The wrappers
already know the intended root; validate there (e.g. `case "$INSIGHT_BASE_DIR" in
*/.insight) ;; *) exit 1;; esac`) and/or have `design_io`/`catalog_io` reject a
`base_dir` that, after `Path(...).resolve()`, is `/`, `$HOME`, or otherwise absurd.
At minimum document that `INSIGHT_BASE_DIR` is a trust boundary.

### M2 (Medium) — validation hook fails open silently; `uv run --project` widens the fail-open surface
`hooks/validate-design.py:150-164`, `hooks/hooks.json:9`.

The hook is, per CLAUDE.md §8 and ADR-0001, the **only** enforcement point for design
integrity now that the MCP server is gone. Yet `main()` deliberately returns
`EXIT_ALLOW` (0) on a malformed payload and on any internal exception:

```python
except Exception as exc:  # a hook bug must not brick every design write
    print(f"validate-design hook: internal error, allowing ({exc})", file=sys.stderr)
    return EXIT_ALLOW
```

Fail-open is a reasonable availability trade for a *bug*, but it means the guard is
bypassable by anything that makes it throw or mis-parse — e.g. feeding a payload shape
it doesn't expect, or making the import of `insight_blueprint.validate` fail. Epic 09
compounds this: the hook now runs via
`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/hooks/validate-design.py"`.
If `uv` is missing, the plugin env fails to sync, or `CLAUDE_PLUGIN_ROOT` is unset,
the hook process never runs (or errors before reading stdin) and the write proceeds
unvalidated. The security-relevant guarantee ("invalid design writes are blocked")
therefore rests on a toolchain that is assumed present but not asserted.

**Recommended fix**: distinguish *guard-inoperable* from *input-valid*. On a genuinely
malformed payload where a `file_path` is nonetheless extractable and matches
`*_hypothesis.yaml`, prefer `EXIT_BLOCK` over allow. Consider a health assertion (import
`insight_blueprint.validate` at top; if it fails on a design-file write, block rather
than allow). Keep fail-open only for non-design writes.

### M3 (Medium) — `hooks.json` command relies on Claude Code to quote `${CLAUDE_PLUGIN_ROOT}`
`hooks/hooks.json:9`.

```json
"command": "uv run --project \"${CLAUDE_PLUGIN_ROOT}\" python \"${CLAUDE_PLUGIN_ROOT}/hooks/validate-design.py\""
```

The `${CLAUDE_PLUGIN_ROOT}` tokens are inside double quotes, which is correct *if* Claude
Code expands them by handing the string to a shell (spaces in the plugin path then stay
one argument). But this is a single command string, not an `argv` array: the safety of a
plugin root containing spaces, `$(...)`, or `;` depends entirely on how the host expands
and executes it. A path like `/Users/a b/$(touch pwned)/...` would be a problem only if
the host does a second, unquoted expansion pass — not expected, but unverified here and
outside this repo's control.

**Recommended fix**: prefer an `argv`-array hook form if the Claude Code hook schema
supports it (no shell parsing of the interpolated path). Otherwise, document the
assumption that `CLAUDE_PLUGIN_ROOT` is a Claude-Code-controlled, non-hostile path and
that plugin install paths must not contain shell metacharacters.

### L1 (Low) — `mkdir -p` on an attacker-influenced base creates directories anywhere
`bin/design_io:19-21`, `bin/catalog_io:14-16`.

The wrappers `mkdir -p "$INSIGHT_BASE_DIR/designs" ...`. Since `INSIGHT_BASE_DIR` is
derived from `CLAUDE_PROJECT_DIR` (M1), a hostile/mis-set `CLAUDE_PROJECT_DIR` turns this
into "create these three dirs under an arbitrary path". It only creates directories (no
file content, no traversal beyond what the caller already dictates), so impact is low, but
it happens *before* any validation and as a side effect of merely invoking the wrapper.
Fix folds into M1 (validate the base first).

### L2 (Low) — `premortem` wrapper omits the `mkdir -p` the other two perform
`bin/premortem:1-14` vs `bin/design_io:19`.

`bin/premortem` sets `INSIGHT_BASE_DIR` but does not create the `.insight` subdirs, unlike
`design_io`/`catalog_io`. Not a vulnerability, but an inconsistency: if `premortem` ever
writes under `INSIGHT_BASE_DIR` it assumes the dirs exist. Confirm premortem is truly
report-only (it is, per CLAUDE.md §6) or add the same `mkdir -p`.

### L3 (Low) — `UV_PROJECT_ENVIRONMENT` points at `CLAUDE_PLUGIN_DATA` without validation
`bin/design_io:15-17`, `bin/catalog_io:10-12`, `bin/premortem:10-12`.

`export UV_PROJECT_ENVIRONMENT="$CLAUDE_PLUGIN_DATA/uv-venv"` trusts `CLAUDE_PLUGIN_DATA`
to designate where a Python venv (executable code) is materialized and later run. If that
var were attacker-controlled it would redirect which interpreter/packages execute. It is a
Claude-Code-provided var, so this is low, but it is another host-var trust point worth
noting alongside M1/M3. It is correctly quoted and guarded by `-n`, so no shell issue.

### L4 (Low) — `uv run --extra notebook` executes marimo-generated notebooks in the plugin env
`skills/analysis-notebook/SKILL.md:46,103-110`, `pyproject.toml:44` (`marimo>=0.21.1`).

The notebook flow runs `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook
<marimo|python> ...`, i.e. it executes generated Python (marimo cells) with the plugin's
full dependency set against the user's data. This is inherent to the feature and gated by
`/premortem`, but note the dependency-supply-chain surface: `marimo` and its transitive
deps run with the user's file access. `uv.lock` is committed (pinned), which mitigates
drift. Keep the lock authoritative and review `marimo` bumps.

---

## Positives (verified, not findings)

- All wrapper expansions are double-quoted; paths with spaces are safe. `"$@"` passthrough
  is correct (no word-splitting of skill arguments). No `eval`, backticks, or unquoted
  command substitution anywhere in `bin/*`.
- `cd "${CLAUDE_PLUGIN_ROOT:?...}"` hard-fails with a clear message if the var is unset,
  rather than silently `cd`-ing to `$HOME`.
- `proj="${CLAUDE_PROJECT_DIR:-$PWD}"` cannot be empty, so `INSIGHT_BASE_DIR` never
  degrades to `/.insight`. `proj` is captured before the `cd`, so `$PWD` is the real cwd.
- `set -e` is present in all three wrappers, so `mkdir -p` / `cd` failures abort before
  `exec`.
- `design_id` / `source_id` path-traversal guard is intact and uses `re.fullmatch` (anchored),
  correctly rejecting `../evil`, `a/b`, `..`, `x/../y`, `""`, `with space` (see
  `tests/test_design_io.py` `_BAD_IDS`). Env change does not weaken it.
- Writes go through `atomic_write_yaml` (tempfile in same dir + `os.replace` + `filelock`),
  so no TOCTOU/partial-write window introduced by this change.
- No secrets are read, logged, or embedded by the diff. Hook stderr messages print
  exception text only (paths/parse errors), not credentials.

## Top priority

1. **M1** — validate/anchor `INSIGHT_BASE_DIR` (adds defense in depth to the whole I/O path).
2. **M2** — make the sole validation hook fail *closed* for design-file writes when the
   guard itself can't run.
3. **M3** — pin down the `hooks.json` quoting assumption (argv form or documented constraint).
