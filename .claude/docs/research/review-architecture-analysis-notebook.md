# Architecture Review — /analysis-notebook (Epic 07)

Branch `epic/7-analysis-notebook` vs `main`. Scope: boundary/responsibility, chaining
graph consistency, project invariants, execution-model contract, doc↔skill consistency.

**Verdict: architecturally sound. Ship-able.** The skill stays in its lane, reuses the
existing lineage + design_io/catalog_io surfaces without touching the core, and the docs
are consistent with the implementation. Findings below are refinements, not blockers — no
High-severity issue. The strongest concern (Medium) is the tacit coupling between the skill
prose, the notebook-contract, and the lineage/IO public APIs, which nothing currently pins.

---

## 1. Boundary / Responsibility

**Assessment: clean.** The skill's stated job is generate + run + record, and every
delegation edge is correct and explicitly declared.

- **conclude → /analysis-reflection**: enforced in three places — "When NOT to Use",
  Step 6 ("**never emit `conclude`**"), and the contract's verdict→journal mapping
  ("never `conclude` — concluding is `/analysis-reflection`"). The journal only receives
  `observe`/`evidence`/`question`. This is the load-bearing boundary and it is airtight.
- **design edit → /analysis-design**: declared; the skill only `get`s + `transition`s the
  design, never writes `*_hypothesis.yaml`. Correct — and it keeps the pre-write hook out
  of the picture (it never emits a design write), so no validation coupling is introduced.
- **overlap with /data-lineage**: acceptable and intentional. `/analysis-notebook` *emits*
  lineage as a by-product of running the notebook (cell 7 calls `export_lineage_as_mermaid`);
  `/data-lineage` is the *setup/refactor/re-export* tool for pipelines. Step 7 correctly
  points re-export at `/data-lineage`. No responsibility is duplicated — one produces during
  a run, the other maintains/re-exports. See finding L1 for a wording nit.
- **overlap with /analysis-journal**: also clean. `/analysis-notebook` writes the
  *auto-derived* events from the verdict; `/analysis-journal` is for *manual* reasoning.
  The chaining edge notebook→journal is labelled exactly that ("Add manual reasoning beyond
  the auto-recorded events"). Good separation.

### Finding B1 — Medium — status precondition has a one-way trap, undocumented
`skills/analysis-notebook/SKILL.md` Step 1 / `src/insight_blueprint/validate.py`
`VALID_TRANSITIONS`.

The skill needs `analyzing` and will transition `in_review → analyzing`. But
`VALID_TRANSITIONS` only allows `analyzing → in_review` (no edge from terminal
supported/rejected/inconclusive back to `analyzing`). So a **re-run of a concluded
hypothesis is structurally impossible** — the skill will hit a hard `transition` failure
with no guidance. The skill says only "Terminal statuses can't be analyzed" as a parenthetical.

*Suggested improvement:* in Step 1, when the design is in a terminal status, tell the user
the concrete recovery path (branch a new hypothesis via `/analysis-reflection` →
`/analysis-design`) instead of leaving them at a raw `transition` error. This is a
usability/flow gap, not a model bug — the transition table is correctly conservative.

---

## 2. Chaining Graph Consistency

**Assessment: bidirectionally consistent, coherent placement.** I verified every new edge
against both endpoints.

| Edge | Declared at source | Declared at target | OK |
|---|---|---|---|
| design → notebook | analysis-design ✓ | analysis-notebook ✓ | ✓ |
| review → notebook | analysis-review ✓ | analysis-notebook ✓ | ✓ |
| notebook → journal | analysis-notebook ✓ | analysis-journal ✓ | ✓ |
| notebook → reflection | analysis-notebook ✓ | analysis-reflection ✓ | ✓ |

All four are present on *both* sides — the symmetry the Epic's AC5 promised holds. Placement
is right: notebook sits after design/review (needs `analyzing`) and before journal/reflection
(feeds evidence, defers conclusion). `analysis-notebook` is registered in
`ALL_SKILLS` (`tests/skills/test_skill_structure.py`), so the structure test covers it.

### Finding C1 — Low — inbound edges narrower than the real graph
The old flow allowed design → journal directly (that edge still exists). Now notebook is the
natural intermediary, but notebook has no inbound edge from `/analysis-journal` or
`/analysis-revision`. That's arguably correct (you don't loop back into notebook generation
from journaling), but a user who journals first and *then* wants to run the notebook has no
declared edge. Consider whether journal → notebook and revision → notebook (after
re-approval) are worth adding. Low because the design/review entry points cover the primary
path; this is only about secondary re-entry.

### Finding C2 — Low — ASCII flow in README vs the richer edge set
`README.md` renders the flow as a single linear ASCII column with notebook replacing the old
"ad-hoc" line. Fine for a README, but it flattens the design/review→notebook fan-in and the
notebook→journal/reflection fan-out that the Chaining tables actually encode. Not worth a
Mermaid rewrite; noting only so the README isn't mistaken for the canonical graph (the
per-skill Chaining tables are canonical).

---

## 3. Project Invariants

**Assessment: fully respected.**

- **No daemon / MCP / SQLite**: the skill is prose + shell invocations of existing CLIs
  (`design_io`, `catalog_io`) + `marimo`/`python`. Nothing runs a server. ✓
- **validate.py single source**: the skill never writes `*_hypothesis.yaml`, so it never
  needs its own validation. Status changes go through `design_io transition`, which delegates
  to `validate_transition` in `validate.py` (verified: `design_io.py:233`). No parallel
  validation path introduced. ✓
- **skills manage YAML**: journal writes go straight to `.insight/designs/{id}_journal.yaml`,
  matching `/analysis-journal`. The skill correctly notes "there is no journal CLI subcommand"
  — consistent with `design_io` exposing `load_journal`/`write_journal` as functions but no
  `journal` argparse command (verified). ✓
- **core unchanged (AC3)**: diff touches no file under `src/insight_blueprint/`. The lineage
  package and design_io/catalog_io are consumed, not modified. ✓

### Finding I1 — Low — install-string / import-name correctness
Package `name = "insight-blueprint-lineage"` with a `notebook` extra, so
`uv add "insight-blueprint-lineage[notebook]"` (SKILL Prerequisites, README, AC4) is
correct, and the import name `insight_blueprint.lineage` is right. The one asymmetry:
`/data-lineage` still advises the *bare* `uv add insight-blueprint-lineage` (no extra),
while `/analysis-notebook` advises the `[notebook]` extra. Both work, but a user who set up
lineage via `/data-lineage` first will still be missing marimo/pandas when they reach
`/analysis-notebook`. The notebook skill's own prereq check catches this, so it's harmless —
just an inconsistency worth a one-line note.

---

## 4. Execution Model (export script → python; verdict.json side-effect)

**Assessment: sound and maintainable, with one real coupling risk.**

The `marimo export script` → `python flat.py` path is the right call: it sidesteps the
`nbformat` dependency that `export ipynb --include-outputs` would drag in, and it is
deterministic. The Epic's Decision block documents *why* `export session` was rejected
(doesn't exist in marimo 0.21) with E2E verification — this is exactly the kind of
version-pinned rationale that belongs in the Design Doc. Good.

The **verdict.json side-effect as the skill↔notebook data channel** is a pragmatic and
maintainable contract: the skill doesn't parse marimo output formats, it reads a plain JSON
file the notebook wrote. This decouples the skill from marimo's rendering entirely. Correct
instinct.

### Finding E1 — Medium — three-way coupling (skill ↔ contract ↔ lineage/IO API) is unpinned
The generated notebook is coupled to concrete public APIs that nothing in this Epic tests:

- `LineageSession(name=..., design_id=...)` and `export_lineage_as_mermaid(session,
  project_path=".")` — verified these signatures match `tracker.py`/`exporter.py` today.
- `tracked_pipe(fn, *, reason=, session=)` — matches.
- `design_io transition/get/list`, `catalog_io get-schema` — all verified present.

But the contract lives as *prose in markdown*, generated *per run by the model*. If the
lineage signature changes (e.g. `export_lineage_as_mermaid` renames `project_path`), the
contract silently drifts and the failure only surfaces at Step 5 (runtime traceback). The
Test Design Matrix claims an E2E cell (7.1) but there is **no committed test artifact** —
no fixture notebook, no golden verdict.json, no CI job exercising `export script`. The E2E
was run once by hand ("実機 E2E で検証済み") and the marimo/lineage deps aren't in CI (they're
an optional extra).

*Suggested improvement:* commit a minimal reference notebook that conforms to the 8-cell
contract and a smoke test (guarded by `pytest.importorskip("marimo")`) that runs
`export script` → `python` and asserts `verdict.json` + `.mmd` are produced. That converts
the contract from "prose the model must re-derive correctly every time" into an executable
pin that catches lineage/marimo API drift. This is the single highest-value follow-up.

### Finding E2 — Low — verdict.json path is hard-coded relative to CWD
Contract cell 6 writes `Path(".insight/notebooks/{id}_verdict.json")` and cell 7 uses
`project_path="."`. Both assume the flat script runs from the project root. Step 4 runs it
via `uv run python .insight/notebooks/{id}_flat.py` from repo root, so it works today, but
the contract doesn't state the CWD assumption. A one-line "run from project root" note in
the contract's Execution section would make the invariant explicit rather than incidental.

### Finding E3 — Low — no cleanup / gitignore guidance for generated artifacts
The run produces `{id}.py`, `{id}_flat.py`, `{id}_verdict.json`, optional `{id}.html`, and
`{id}.mmd`. The `_flat.py` and `_verdict.json` are intermediates the skill consumes; nothing
says whether they're committed or transient. Worth a line on which of `.insight/notebooks/*`
is durable vs scratch (and whether `_flat.py`/`_verdict.json` belong in `.gitignore`).

---

## 5. Doc ↔ Sequence ↔ Skill Consistency

**Assessment: consistent.** I cross-checked the Epic Design Doc sequence, the ARCHITECTURE
sequence, and the actual SKILL workflow — they tell the same story:

- ARCHITECTURE's "分析ワークフロー全体" sequence was updated from the old "ad-hoc, no skill"
  note to `/analysis-notebook` generating + running + appending journal events. The
  `CC->>IO: verdict を journal に追記` step matches SKILL Step 6.
- The Epic sequence (get → optional transition → get-schema → Write notebook → export script
  → verdict/mmd → journal append) is a 1:1 match with SKILL Steps 1–6.
- ARCHITECTURE's component prose now names `/analysis-notebook` and the `[notebook]` extra,
  matching pyproject.

### Finding D1 — Low — Data Model section undersells the verdict.json contract
The Epic's Data Model section lists generated files but calls verdict.json a mere artifact.
Given it is *the* skill↔notebook interface (Section 4), its shape
(`conclusion`/`evidence_summary`/`open_questions`) deserves to be pinned in the Design Doc's
Data Model table, not only in the reference markdown — it's a contract, not a scratch file.
Low because the contract md does define it; this is about putting it where a Design Doc
reader looks.

---

## Summary of Findings

| # | Severity | Area | One-liner |
|---|---|---|---|
| B1 | Medium | boundary | Terminal-status re-run is a one-way trap; give recovery guidance, not a raw transition error |
| E1 | Medium | execution/coupling | Contract↔lineage/IO API drift is unpinned; commit a `importorskip`-guarded E2E smoke test + reference notebook |
| C1 | Low | chaining | No journal/revision → notebook re-entry edge (may be intentional) |
| C2 | Low | chaining | README ASCII flow flattens the real fan-in/fan-out |
| I1 | Low | invariants | `/data-lineage` installs bare pkg, `/analysis-notebook` needs `[notebook]` extra — note the asymmetry |
| E2 | Low | execution | CWD=project-root assumption for verdict.json path is implicit |
| E3 | Low | execution | No durable-vs-scratch / gitignore guidance for generated artifacts |
| D1 | Low | docs | verdict.json shape belongs in the Design Doc Data Model, not only the reference |

No High-severity findings. The two Mediums are both "make the implicit explicit / pin the
contract" — the design itself is correct.
