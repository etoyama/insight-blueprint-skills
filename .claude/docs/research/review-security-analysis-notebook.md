# Security Review — /analysis-notebook skill (Epic 07)

Branch `epic/7-analysis-notebook` vs `main`. Reviewed 2026-07-03.

## Scope & nature

This is a **markdown SKILL** — instructions that tell Claude to *generate* a marimo
notebook (Python) from a design's `methodology` + a catalog data source, then *execute*
it headlessly (`marimo export script … && python …_flat.py`). No executable app code
ships in the diff except the `[notebook]` dependency extra in `pyproject.toml`.

Because the artifact is *instructions that lead to generated-and-executed code*, findings
are severity-scored as "advice that could lead to unsafe generated code / unsafe operator
behavior," not as live exploitable code. The dominant risk class here is
**code-generation-then-execution driven by design/source content that the skill treats as
trusted**.

Files reviewed:
- `skills/analysis-notebook/SKILL.md`
- `skills/analysis-notebook/references/notebook-contract.md`
- `pyproject.toml` (`[notebook]` extra), `uv.lock`
- Supporting: `skills/_shared/design_io.py`, `skills/_shared/catalog_io.py`

## Summary of findings

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 3 |

No Critical issues. The design is inherently a code-gen-and-run tool, so the residual
risk is real but bounded by the fact that the human operator drives it interactively and
reviews the generated notebook. The two High items are about the skill giving no guidance
that the inputs feeding generated code are untrusted, and about connection-secrets flowing
into a notebook the skill also renders/persists.

---

## High

### H1 — No trust boundary on design/source content feeding generated code (code-injection by content)
**Where:** `SKILL.md` Step 3 (cells 2/4) + `notebook-contract.md` cell 2 (data_load),
cell 4 (analysis "from `methodology.method` + `methodology.steps` (code patterns)").

**Description.** The skill instructs Claude to turn design fields into executable Python:
`methodology.steps` is explicitly described as "**code patterns**," and the source
`connection` (CSV path / SQL) is dropped into `pd.read_csv(...)` / SQL in cell 2. Neither
SKILL.md nor the contract states that these fields are **untrusted input** or that the
generated code must not blindly embed them. A design or catalog entry authored (or edited)
by someone other than the operator — or imported from an upstream `insight-blueprint`
project — can therefore steer arbitrary Python into a notebook that the skill then runs
headlessly (`python …_flat.py`). Concretely:
- A `connection.path` like `"; import os; os.system('…'); x='"` or an f-string-interpolated
  SQL string becomes live code if the generator string-concatenates it.
- `methodology.steps` framed as "code patterns" invites verbatim paste of attacker-controlled
  snippets into cell 4.

marimo runs the flat script as an ordinary Python process with the operator's full
privileges (filesystem, network, env, credentials). There is no sandbox in the design.

**Recommended fix.** Add an explicit "Untrusted input" note to SKILL.md Step 3 and to the
contract:
- Treat `methodology.steps`, `analysis_intent`, and `connection.*` as **data, not code**.
  Never string-interpolate them into executable statements. Bind data-source paths/SQL as
  literals/parameters (`pd.read_csv(path)` with `path` a Python string variable; for SQL,
  parameterized queries), and never `eval`/`exec`/`os.system`/`subprocess` on design content.
- "Code patterns" in `methodology.steps` must be reviewed by the operator before generation,
  not pasted verbatim. State that the operator confirms the generated cell 4 before Step 4 runs.
- Recommend running the notebook in a directory / with least privilege appropriate to the
  data source, and never against production credentials from an unreviewed design.

### H2 — Connection secrets can leak into the notebook, HTML export, verdict, and journal
**Where:** `SKILL.md` Step 2 ("the connection (CSV path / SQL)"), Step 3 cell 2, the
optional `marimo export html` in Step 4/contract, cell 1 (meta) `mo.md()` display.

**Description.** For SQL/DB sources the `connection` dict may hold credentials
(host, user, **password**, API keys, DSN with embedded secret). The skill tells Claude to
put the connection into cell 2 of a **persisted** `.insight/notebooks/{id}.py` file, and
optionally to render a human-viewable `{id}.html` export that captures cell source/output.
Secrets embedded in the notebook source therefore land in:
1. the committed-or-shared `.py` notebook,
2. the `_flat.py` script,
3. the optional `.html` report,
4. potentially the journal (Step 6 copies `evidence_summary` / observations — if a cell
   printed the connection or a query string, it can propagate).

Nothing in the skill warns against this or says to read secrets from env vars instead.

Note: `catalog_io.get_schema` (what Step 2 actually calls) returns only columns/PK/row
count — **not** the connection. So the SKILL's claim that `get-schema` yields "the
connection (CSV path / SQL)" is also factually wrong (see M3); the connection lives in the
full source YAML and would have to be read separately, which is exactly where the secret is.

**Recommended fix.**
- Instruct: never inline credentials into the generated notebook. Reference secrets via
  `os.environ[...]` / a `.env` loaded at runtime, and keep the catalog `connection` entry
  free of raw secrets (store a reference/DSN-without-password).
- Warn that `.insight/notebooks/*.py`, `*_flat.py`, and `*.html` may contain the data
  connection and must be `.gitignore`d if they can hold secrets; do not print connection
  objects or raw query strings into cells whose output feeds the journal.
- Add a "do not copy connection strings / query text into the journal" line to Step 6.

---

## Medium

### M1 — Path traversal via `design_id` into `.insight/notebooks|lineage` and verdict.json
**Where:** `SKILL.md` Step 3/4/6 (`.insight/notebooks/{design_id}.py`,
`{design_id}_verdict.json`, `.insight/lineage/{design_id}.mmd`), sourced from `$ARGUMENTS`.

**Description.** `design_id` comes from user `$ARGUMENTS` and is interpolated directly into
several write paths, including a path **written from inside the generated notebook**
(`Path(".insight/notebooks/{id}_verdict.json").write_text(...)`, contract cell 6). Unlike
`catalog_io._validate_id` (`SAFE_ID_PATTERN.fullmatch`), `design_io.load_design` /
`transition_status` do **not** validate the id before building paths, so a value like
`../../foo` or an absolute path would resolve outside `.insight/`. The generated notebook
bakes `{id}` into a literal path string, so a crafted id can direct a write anywhere the
process can write. This is partly a pre-existing core property (Epic scope excludes changing
`design_io`), but the new skill *extends* the blast radius (three new id-derived paths, one
of them written by generated code).

**Recommended fix.** Have SKILL.md Step 1 validate `design_id` against `^[A-Za-z0-9_-]+$`
(reject `/`, `.`, `..`, absolute paths) before using it in any path, and state that all
generated `{id}`-derived paths must be relative to `.insight/`. Ideally also add
`_validate_id` to `design_io` (flag as a cross-cutting follow-up even if out of Epic scope).

### M2 — Fix-and-rerun loop can execute partially-attacker-influenced code repeatedly
**Where:** `SKILL.md` Step 5 ("read the traceback, fix the offending cell … re-run").

**Description.** The loop re-executes the notebook after edits. If H1 is unaddressed, each
rerun re-runs whatever code was generated from design content. The guidance says "keep it
interactive — resolve with the user rather than looping blindly," which is good, but there
is no explicit gate that the operator reviews the *generated code* (not just the traceback)
before the first run and before each rerun.

**Recommended fix.** State that before the first `python …_flat.py` in Step 4, the operator
must review the generated notebook (especially cells 2 and 4) for anything beyond pandas/
numpy analysis — no shell-outs, no network beyond the declared source, no writes outside
`.insight/`. Make that review an explicit precondition of Step 4.

### M3 — Inaccurate instruction: `get-schema` does not return the connection
**Where:** `SKILL.md` Step 2 — "`catalog_io get-schema` … and the connection (CSV path / SQL)."

**Description.** `catalog_io.get_schema()` returns only `source_id`, `columns`,
`primary_key`, `row_count_estimate` — not `connection`. Following the instruction literally,
Claude will not obtain the connection from `get-schema` and may improvise (read the raw
source YAML, or invent a path), which is both a correctness bug and a security-relevant one:
improvised paths defeat any catalog-level control over what data is read. Security-adjacent
because "where does the data actually come from" becomes ambiguous.

**Recommended fix.** Correct Step 2 to say `get-schema` yields columns only, and specify the
sanctioned way to obtain the connection (e.g. a dedicated read that deliberately excludes
secrets, per H2). Do not let Claude free-form a data path.

---

## Low

### L1 — `python …_flat.py` executes with no resource / network bounds
**Where:** `SKILL.md` Step 4, `notebook-contract.md` Execution.

The generated script runs unbounded (CPU/memory/time/network). A large or hostile source,
or a `read_csv` of a remote URL, runs to completion with no timeout. Low because it is a
local dev tool. Suggest: recommend running against a bounded sample first, and note that
`pd.read_csv` accepts URLs (an SSRF-ish vector if a path/URL comes from an untrusted source).

### L2 — Optional `.html` export broadens the artifact footprint
**Where:** Step 4 optional export / contract Execution.

`marimo export html` bundles cell source + outputs into a shareable file. Combined with H2,
this is the most likely secret-exfiltration surface (an HTML someone forwards). Low on its
own; call out that HTML exports may embed the connection and analysis data and should be
handled/gitignored accordingly.

### L3 — Dependency extra pulls a large surface (`marimo`) with a floor-only pin
**Where:** `pyproject.toml` `[project.optional-dependencies] notebook`, `uv.lock`.

`marimo>=0.21.1`, `pandas>=3.0.1`, `matplotlib`, `numpy` are floor pins (`>=`). marimo is a
sizeable dependency (bundles a web server/UI). Supply-chain-wise the floor pins let an
unbounded future major in; `uv.lock` pins for reproducibility, which mitigates. Low.
Suggest: it is an opt-in extra (good — not forced on all installs); consider an upper bound
on `marimo` given the skill relies on 0.21-specific `export script` behavior (the contract
itself notes `export session` was removed), so a major bump could silently break the
documented execution path.

---

## Positives (design choices that reduce risk)

- `disable-model-invocation: true` — the skill only runs on explicit `/analysis-notebook`,
  not auto-triggered. Good: no unattended code-gen-and-run.
- Interactive, human-in-the-loop framing throughout; explicitly *not* the removed unattended
  headless/queue mechanism (Epic Decisions).
- Runtime deps are an **opt-in extra**, not core dependencies.
- Writes are confined to `.insight/` by convention (modulo M1's id-validation gap).
- The skill records only observe/evidence/question and never `conclude` — narrow write scope
  into the journal.

## Top recommendations (priority order)

1. **H1 / M2** — Add an explicit "untrusted input, data-not-code" boundary: never interpolate
   `methodology.steps` / `connection` into executable statements; operator reviews generated
   cells 2 & 4 before running. This is the core risk of the whole design.
2. **H2 / L2** — Keep credentials out of the notebook/flat/HTML/journal; read secrets from
   env, gitignore the artifacts.
3. **M1** — Validate `design_id` (`^[A-Za-z0-9_-]+$`) before any path use; propose adding
   `_validate_id` to `design_io` as a follow-up.
4. **M3** — Fix the `get-schema`-returns-connection inaccuracy and pin down the sanctioned
   data-source read path.
