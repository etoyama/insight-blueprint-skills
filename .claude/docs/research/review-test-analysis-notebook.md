# Test Review: analysis-notebook (Epic 7)

Branch `epic/7-analysis-notebook` vs `main`. Reviewed `git diff main...HEAD`,
`tests/skills/test_skill_structure.py`, `skills/analysis-notebook/SKILL.md`,
`skills/analysis-notebook/references/notebook-contract.md`, `pyproject.toml`.

## Verdict

The change is a markdown skill + wiring + docs with **no new `src/` Python**. Execution
is marimo/python at runtime, so classic code-coverage is largely N/A. The structural
tests do cover the new skill, but there are two real gaps: an **untested execution path**
(design doc claims E2E coverage that does not exist) and a **pre-existing skill-list drift**
in `test_plugin_structure.py` that `analysis-notebook` silently inherits.

## Suite status

`uv run pytest -q` → **338 passed in ~7.6s**. Suite is green. Skipped `--cov=src` per
instructions (no `src/` change; coverage of `src/` is unaffected by this diff).

## What IS covered

`analysis-notebook` was added to `ALL_SKILLS` in `tests/skills/test_skill_structure.py`,
so it is now exercised by that module's parametrized/looping tests:

- `TestSkillStructure.test_all_skills_have_required_sections` — frontmatter present +
  all 5 required sections (When to Use / When NOT to Use / Workflow / Chaining / Language Rules). Confirmed present in the SKILL.md.
- `test_chaining_table_format` — `| From | To | When |` header present. Confirmed.
- `TestForwardingGraph.test_bidirectional_consistency` — the four Chaining edges
  (analysis-design→, analysis-review→, →analysis-journal, →analysis-reflection) are
  checked for bidirectional consistency against the counterpart skills.
- `TestSkillDeployment.test_all_skills_have_skill_md` — SKILL.md exists.

Non-markdown wiring checks that pass out-of-band:
- CLI subcommands the skill invokes all exist: `design_io {list,get,transition}`,
  `catalog_io get-schema`. `skills/_shared/` is unmodified by this diff.
- Lineage API the contract references exists: `LineageSession`, `tracked_pipe`,
  `export_lineage_as_mermaid` (`insight_blueprint.lineage`).
- `notebook` optional-extra resolves in `uv.lock` (`provides-extras = ["dev", "notebook"]`).

## Gaps

### Gap 1 — Execution path (8-cell → export script → run → verdict.json / lineage.mmd) is untested. Priority: Medium

The design doc `docs/design/epic-07-analysis-notebook.md` Test Design Matrix marks Story 7.1
as **✓ E2E** with the note "8-cell → export script → 実行 → verdict.json / lineage.mmd".
**No such test exists.** `grep` for marimo/verdict/notebook in `tests/` returns only
`test_skill_structure.py` plus false positives (the word "notebook" inside unrelated
premortem manifest fixtures under `tests/e2e/fixtures/`). So the matrix's E2E ✓ is
aspirational, not real — a documentation/traceability defect in the PR.

Why Medium and not High: the moving parts the skill *orchestrates* (lineage API, design/catalog
CLIs, marimo export) are individually real and the lineage side is already unit-tested
(`tests/lineage/`). The untested seam is specifically the **contract the skill instructs
Claude to generate**: the fixed 8-cell shape, the `results`/`verdict` dict keys, the
verdict.json side-effect, and the verdict→journal mapping. A regression here (e.g. marimo
0.22 changing `export script`, or a cell-signature drift) would not be caught by any test.
It is a skill (instructions), so runtime correctness ultimately depends on Claude following
the contract — that argues against gold-plating with heavy E2E, but a lightweight guard is cheap.

Suggested test (lightweight integration, gated on the `notebook` extra):

- Add `tests/integration/test_notebook_contract.py` with a **committed fixture notebook**
  `tests/fixtures/notebooks/sample_8cell.py` that follows the 8-cell contract against a
  tiny in-repo CSV (no external source).
- Test body: run `marimo export script` on the fixture, then execute the flat script in a
  `tmp_path` cwd; assert `{id}_verdict.json` exists and parses to a dict with keys
  `conclusion`, `evidence_summary`, `open_questions`; assert `.insight/lineage/{id}.mmd`
  exists and is non-empty Mermaid.
- Guard with `pytest.importorskip("marimo")` so the default (no-notebook-extra) suite and
  CI stay green without the extra installed.
- This pins the execution recipe (`export script` still exists, flat-script run produces
  both side-effects) and the verdict.json schema the skill reads back — the highest-value
  seam — without trying to test Claude's generation step.

Minimum acceptable alternative (if the above is deemed over-engineering for a skill):
fix the design doc matrix to **not** claim E2E ✓, downgrading it to "manual / not automated",
so traceability is honest. Do at least this.

### Gap 2 — `test_plugin_structure.py::ALL_SKILLS` omits analysis-notebook. Priority: Medium

`tests/test_plugin_structure.py` has its own `ALL_SKILLS` list (7 entries) that was **not**
updated and is already stale on `main` (also missing `analysis-review`, `knowledge-extract`).
Consequently the plugin-structure parametrized checks — `test_all_skills_exist`,
`test_skill_md_has_frontmatter` (name + description), `test_skill_md_has_version` — do **not**
run against `analysis-notebook`. The frontmatter/version guarantees for the new skill come
only from `test_skill_structure.py`, not the plugin-structure module.

The drift predates this branch, but this Epic is the right moment to close it since it adds a
skill. Suggested fix: add `analysis-notebook` (and, to stop the recurring drift, `analysis-review`
and `knowledge-extract`) to `tests/test_plugin_structure.py::ALL_SKILLS`. Better still, have
both modules derive the list from `skills/*/SKILL.md` on disk (single source of truth) so a
new skill can never be added without being tested.

Suggested test: parametrize over discovered `skills/*/` dirs, e.g.
`[p.name for p in (REPO_ROOT/"skills").iterdir() if (p/"SKILL.md").is_file()]`, and drop the
hand-maintained lists in both `test_plugin_structure.py` and `test_skill_structure.py`.

### Gap 3 — No assertion that referenced CLI subcommands / lineage symbols exist. Priority: Low

The skill hard-codes `design_io transition`, `catalog_io get-schema`,
`export_lineage_as_mermaid`, etc. Today these are verified only manually (they do all exist).
A cheap guard would catch a future rename that silently breaks the skill's instructions.

Suggested test (Low): a doc-lint test that greps `analysis-notebook/SKILL.md` +
`notebook-contract.md` for `design_io <sub>` / `catalog_io <sub>` tokens and asserts each
subcommand appears in the respective argparse `choices`, and that `insight_blueprint.lineage`
exposes each referenced symbol. Optional; the fixture test in Gap 1 partially covers the
lineage symbols already.

## No new source logic lacking tests

Confirmed: the diff touches only markdown (SKILL.md, references, docs, CLAUDE.md, README,
ARCHITECTURE), `pyproject.toml`/`uv.lock` (the `notebook` extra — declarative, no logic),
and the one-line test edit. No helper Python was introduced, so there is no untested
imperative code beyond the runtime-generated notebook discussed in Gap 1.

## Recommendation summary

| Gap | Priority | Action |
|---|---|---|
| Execution path untested; design matrix falsely claims E2E ✓ | Medium | Add gated fixture-notebook integration test (export→run→assert verdict.json + lineage.mmd). At minimum, correct the matrix. |
| `test_plugin_structure.py::ALL_SKILLS` omits the new skill | Medium | Add analysis-notebook (+ review, knowledge-extract); ideally discover skills from disk in both test modules. |
| Referenced CLI/lineage symbols not asserted | Low | Optional doc-lint test tying SKILL.md tokens to argparse choices / lineage exports. |

For a skill (instructions, not source), Gap 1's minimum bar (honest matrix) is a merge
blocker on traceability grounds; the fixture test is the recommended, still-lightweight fix.
Gap 2 is a genuine test-coverage hole worth closing in this Epic. Gap 3 is nice-to-have.
