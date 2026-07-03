# Doc Review: /analysis-notebook (Epic 07)

Branch `epic/7-analysis-notebook` vs `main`. Reviewed: README.md, docs/ARCHITECTURE.md,
CLAUDE.md, docs/design/epic-07-analysis-notebook.md, skills/analysis-notebook/SKILL.md,
skills/analysis-notebook/references/notebook-contract.md, pyproject.toml, tests.

Verdict: docs are largely consistent and complete. One High-severity stale contradiction
in ARCHITECTURE.md, plus a few Low items. Package name / deps extra / execution mechanism
all check out.

---

## High

### H1 — ARCHITECTURE.md:115 — stale "ad-hoc, not a skill" prose contradicts its own diagram

File/section: `docs/ARCHITECTURE.md`, "分析ワークフロー全体" intro paragraph (line 115).

Current text:
> **notebook の生成・実行は skill ではなく Claude Code が methodology から ad-hoc に行う**ステップである
> （図中の破線 Note）。

This is the pre-#31 wording and directly contradicts:
- the same file's component note (line 68), now correctly `/analysis-notebook` skill,
- the sequence diagram 8 lines below (line 138–140), which correctly shows
  `/analysis-notebook` generating/running the notebook,
- SKILL.md, README, CLAUDE, and the Epic Design Doc.

It also references "図中の破線 Note" — but the diagram's Note was rewritten (line 138) to
name `/analysis-notebook`, so the cross-reference is dangling too.

Suggested update (replace line 115):
> **notebook の生成・実行は `/analysis-notebook` skill が担う**（設計書の `methodology` から
> 8-cell marimo notebook を生成・実行し、verdict を journal に記録する）。
> `/analysis-review`・`/premortem`・`/data-lineage` は任意ステップ。

This is the only remaining "ad-hoc / no skill" leftover from PR #31 anywhere in the tree
(grep confirms: `README`, `CLAUDE`, `SKILL` are all clean; only this line survives).

---

## Low

### L1 — SKILL.md:66–76 — Step 3 lists "cell 1–7", silently omits cell 0 (imports)

File/section: `skills/analysis-notebook/SKILL.md`, Step 3 "Generate the notebook".

The contract (notebook-contract.md) defines cells **0–7** (8 cells: imports=0 … lineage=7).
SKILL.md Step 3's bullet list starts at "cell 1 (meta)" and ends "cell 7 (lineage)",
skipping cell 0 (imports) and thus enumerating only 7 of the 8. Not wrong per se (it says
"see references" and imports is boilerplate), but a reader counting bullets against the
"8-cell" label sees a mismatch.

Suggested update: add a leading bullet `- cell 0 (imports): pandas/matplotlib/numpy +
lineage helpers` or note "cell 0 is fixed boilerplate — see references". Cheap consistency win.

### L2 — notebook-contract.md:13,17 — verdict/data_load cell param lists vs signatures

File/section: `references/notebook-contract.md`, Cells table.

Minor: cell 6 (verdict) signature is `def _(results, json, Path, mo):` and cell 2 declares
it "**Only this cell** does `import marimo as mo`" yet several later cells (3,4,6,7) receive
`mo` as a parameter. That is exactly correct for marimo (import once, pass by DAG), and rule
#5 states it — but a contributor unfamiliar with marimo may read "only this cell does
import mo" as conflicting with "cell 6 takes mo". Consider a half-sentence: "other cells
receive `mo` as a parameter (see rule 5)". Purely a clarity nit; not blocking.

### L3 — SKILL.md frontmatter says "runs it headlessly" while docs stress interactive

File/section: `skills/analysis-notebook/SKILL.md` description + heading.

The description says "runs it headlessly" and Step 4 is titled "Run it headlessly", while
the Epic scope explicitly excludes "無人 headless 実行". The word is used here in the narrow
sense of "no GUI / flat-script execution", not "unattended pipeline" — and Step 5 keeps it
interactive. No factual error, but "headless" collides with the Epic's own vocabulary where
"headless" = the rejected unattended mode. Consider "runs it non-interactively via a flat
script" to avoid overloading the term. Optional.

---

## Verified consistent (no action)

- **README Skills list**: `/analysis-notebook` added in correct workflow position
  (after `/analysis-review`, before `/analysis-journal`). Accurate one-liner.
- **README Analysis Workflow diagram**: the old
  `[ Claude Code generates & runs a marimo notebook … ] ← ad-hoc, no skill` line is fully
  replaced by `/analysis-notebook (generate & run … → record results)`. The follow-up prose
  paragraph is rewritten and no longer says "ad-hoc step, not a dedicated skill".
- **README deps guidance**: `uv add "insight-blueprint-lineage[notebook]"` — correct. The
  package name in pyproject is `insight-blueprint-lineage` and `[notebook]` is a real
  optional-dependencies extra (marimo/pandas/matplotlib/numpy). Matches SKILL.md
  Prerequisites and ARCHITECTURE line 70.
- **ARCHITECTURE component note (line 68) + sequence diagram (line 138–142)**: both name
  `/analysis-notebook`, cite `references/notebook-contract.md`, show the correct chain
  (generate → marimo export script → run → verdict.json / lineage.mmd → journal append).
- **CLAUDE §6 skill table**: row added for `/analysis-notebook` with accurate purpose
  ("Generate + run a marimo notebook from the design's methodology; record results to
  journal"). Table position between review and journal is sensible.
- **Execution mechanism cross-consistency**: README, ARCHITECTURE, SKILL.md (Step 4),
  notebook-contract.md (Execution section), and Design Doc (AC2, Decision
  execution-via-export-script-and-verdict-sideeffect) all agree on
  `marimo export script → python flat.py`. The nonexistent `export session` appears only
  once — in notebook-contract.md:66 as an explicit "marimo 0.21 has **no** export session"
  warning. No doc prescribes it. Correct.
- **Epic Design Doc completeness**: all template sections present — Acceptance Criteria
  (7, all checked), Glossary, Scope (in/out), Architecture (mermaid flowchart), Module
  Responsibilities (table with responsibility + boundary columns), Sequence Diagram
  (mermaid), Data Model, Decisions (2 Epic-scoped), Test Design Matrix (Story 7.1/7.2),
  Story Timeline. **ADR-not-needed justification is present and correct** ("### ADR は不要"
  section, cites CLAUDE §5: Epic-internal, no invariant/architecture change). Design Doc
  correctly notes the `export session` → `export script` correction as an implementation
  finding.
- **Chaining / ALL_SKILLS**: SKILL.md Chaining table wires design/review → notebook →
  journal/reflection symmetrically; `analysis-notebook` added to `ALL_SKILLS` in the test.

---

## New-user readability

A new contributor can run an analysis from the docs alone: README workflow shows where the
skill sits, SKILL.md gives step-by-step (load design → schema → generate 8-cell → export
script + run → fix-and-rerun → journal → handoff), and notebook-contract.md is the precise
cell contract + execution commands + verdict→journal mapping. The one thing that would
mislead a reader is **H1** — a reader landing on ARCHITECTURE.md line 115 first is told the
notebook step is "not a skill, done ad-hoc", which is now false. Fix H1 and the docs are
coherent end-to-end.
