# Quality Review — /analysis-notebook skill

Scope: `skills/analysis-notebook/SKILL.md` + `references/notebook-contract.md` on
`epic/7-analysis-notebook` vs `main`. Reviewed for clarity, correctness, and consistency
with sibling skills (`analysis-review`, `analysis-journal`, `catalog-register`) and against
the actual `design_io` / `catalog_io` CLIs and `tests/skills/test_skill_structure.py`.

Verdict: solid and largely consistent. Frontmatter, required sections, chaining wiring, and
CLI usage all check out. The one real defect is a cell-numbering mismatch between SKILL.md
and the contract (High). The rest are Medium/Low polish.

---

## Findings

### High

**H1 — Cell numbering in SKILL.md is off-by-one and drops the imports cell**
`SKILL.md` §Step 3 (lines 66–76) lists `cell 1 (meta)` … `cell 7 (lineage)` — seven cells
numbered 1–7. `references/notebook-contract.md` (lines 9–18) numbers the same notebook 0–7:
`cell 0 (imports)`, `cell 1 (meta)`, `cell 2 (data_load)`, … `cell 7 (lineage)`.

So SKILL.md's "cell 2 (data_load)" is the contract's cell 2 (coincidentally aligned there),
but SKILL.md's "cell 1 (meta)" vs contract "cell 1 (meta)" aligns while the imports cell
(contract cell 0) is entirely absent from the SKILL.md list. Net effect: SKILL.md claims a
"fixed 8-cell contract" (line 17) but enumerates only 7 cells and never mentions the imports
cell — a generator following SKILL.md alone would omit cell 0. The two documents must use
one numbering scheme.

- Fix: renumber SKILL.md Step 3 to match the contract (0=imports … 7=lineage) and add the
  missing `cell 0 (imports)` bullet, OR explicitly say "cells 1–7 below; cell 0 is imports
  per the contract." Prefer the former so the count reconciles with "8-cell."
- File refs: `SKILL.md:17`, `SKILL.md:66-76`; `references/notebook-contract.md:9-18`.

### Medium

**M1 — `results` required fields stated in two places; SKILL.md is the weaker copy**
`SKILL.md:73` says cell 4 must "build the `results` dict with the required direction fields"
without naming them. The contract (`notebook-contract.md:15`, 20–39) is authoritative:
`hypothesis_direction`, `observed_direction`, `confidence_level`, `decision_reason`. This is
fine (SKILL.md defers to the contract), but "the required direction fields" is vague enough
that a generator might guess. Consider naming the four fields inline, or say "the four
required fields listed in the contract's `results` shape."
- File ref: `SKILL.md:73`.

**M2 — Missing-schema behavior stated twice with slightly different instructions**
Prerequisites (`SKILL.md:48`) says an unregistered source → `/catalog-register`. Step 2
(`SKILL.md:62`) says "stop and suggest /catalog-register." Both point the same way, so no
contradiction, but Step 2's "stop" is the operative rule and the Prerequisites line reads as
softer. Minor; align the wording ("stop and hand off to /catalog-register").
- File refs: `SKILL.md:48`, `SKILL.md:62`.

**M3 — verdict→journal mapping: `inconclusive`/ambiguous path is split across two rules**
`notebook-contract.md:90-93`: for confirmatory `inconclusive` → "(question)", and separately
`confidence_level == "ambiguous"` → emit a `question`. These interact (an inconclusive result
is often also ambiguous) but the doc doesn't say which rule wins or whether both fire. Given
Step 6 forbids duplicate/`conclude` events, one line clarifying "ambiguous OR inconclusive →
a single `question` event, not an `evidence` event" would remove the ambiguity for the
generator.
- File ref: `references/notebook-contract.md:88-94`.

### Low

**L1 — "fixed 8-cell" vs the table's 0–7 range reads as 8 cells only if you count cell 0**
The contract table is correct (0–7 = 8 cells), but a reader skimming "cell 7" as the last row
may momentarily read it as 7. Not an error; a one-word note "(cells 0–7 = 8 cells)" at the
top of the Cells table would preempt the confusion. Ties into H1.
- File ref: `references/notebook-contract.md:7-8`.

**L2 — HTML export described as "runs the notebook too" — verify it is not a second run**
`SKILL.md:86` and `notebook-contract.md:78-82` both offer `marimo export html` as an optional
viewable artifact and note it executes the notebook. If a user runs Step 4 (flat script) and
then the HTML export, the analysis runs twice and re-writes `{id}_verdict.json`. Harmless if
deterministic, but worth a half-sentence: "optional; re-executes, so run after journaling or
expect verdict.json to be rewritten identically."
- File refs: `SKILL.md:86`, `references/notebook-contract.md:78-82`.

**L3 — Journal-CLI absence is stated clearly and correctly (no fix; confirmation)**
`SKILL.md:113-114` says the journal is written by editing `{id}_journal.yaml` directly because
"there is no journal CLI subcommand." Verified against `design_io._main` choices
(`create/update/transition/get/list/review-batch/list-reviews`) — journal is indeed only
exposed as `load_journal`/`write_journal` functions, not CLI commands. Correct and matches
`analysis-journal/SKILL.md:176-182`. No change needed.

**L4 — Step 3 bullet list ends at cell 7 but references "8-cell" earlier; cell 0 imports
never appears in the SKILL body at all** (same root as H1; noting for the fix that the
Prerequisites import line at `SKILL.md:43` is the closest the body comes to describing cell 0,
but it is a preflight check, not a generation instruction).

---

## Confirmed correct (no action)

- **Frontmatter**: `name`, `version: "1.0.0"`, block `description` with `Triggers:`,
  `disable-model-invocation: true`, `argument-hint: "[design_id]"` — all present and match the
  sibling convention (`analysis-review`, `analysis-journal`, `catalog-register`). `1.0.0` is
  correct for a new skill; it is not in `test_existing_skills_version_bump`'s expected-version
  map, so no test constrains it.
- **Required sections**: When to Use / When NOT to Use / Workflow / Chaining / Language Rules
  all present as `##` headings → passes `test_all_skills_have_required_sections`.
- **`ALL_SKILLS` registration**: `analysis-notebook` added at `test_skill_structure.py:38`.
- **Chaining bidirectional consistency**: notebook's four edges are mirrored —
  `analysis-design → analysis-notebook` (present in analysis-design per AC5),
  `analysis-review → analysis-notebook` (`analysis-review/SKILL.md:144`),
  `analysis-notebook → analysis-journal` (`analysis-journal/SKILL.md:229`),
  `analysis-notebook → analysis-reflection`. Chaining header format `| From | To | When |`
  matches `test_chaining_table_format`.
- **design_io CLI**: `list --status analyzing`, `get --id`, `transition --id --target` all
  exist and use the correct flags (`design_io.py:334-348`). Flag names verified against argparse.
- **catalog_io CLI**: `get-schema --id` exists (`catalog_io.py:339,366`). Correct.
- **Status-transition claims**: `in_review → analyzing` is valid; terminal statuses
  (`supported`/`rejected`/`inconclusive`) have empty transition sets, so "Terminal statuses
  can't be analyzed" is accurate (`validate.py:22-41`).
- **Package/extra name**: project name is `insight-blueprint-lineage` and pyproject adds
  `[project.optional-dependencies] notebook`, so `uv add "insight-blueprint-lineage[notebook]"`
  (`SKILL.md:44`, `notebook-contract` execution) is correct.
- **Verdict side-effect contract**: SKILL Step 4/6 and contract agree — flat-script run writes
  `{id}_verdict.json`, skill reads it back; matches the Epic Decision
  `execution-via-export-script-and-verdict-sideeffect`.
