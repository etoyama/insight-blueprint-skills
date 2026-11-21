# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Upgrade note

- A project's `.insight/rules/package_allowlist.yaml` can no longer forbid pandas, matplotlib,
  numpy, marimo or insight_blueprint: the default allowlist is always allowed. The packages the
  file already lists stay allowed, so nothing that ran before stops.

### Added

- `/analysis-reflection {theme_id}` now goes on after the current answers: it lists the next
  candidates (the nodes of the question tree with no design on them or below them), can attach a
  question to ask a person, keeps the answer you bring back with who answered and when, and asks
  whether you deepen the same node, return to its parent, or close. Your choice and its reason are
  kept in the tree as a decision.
- A new journal event type, `hearing`, holds what a person answered. `/analysis-design` copies an
  answer kept on a question node into the journal of the design it links to that node, so a later
  answer can cite it. `/analysis-journal` records one too.
- The HTML view of the question tree lists the next candidates, shows the round each decision was
  taken at, and marks an answer that no longer matches the record instead of showing it as the
  current answer.
- `/analysis-framing` makes the HTML view of the question tree with `tree_io render` after it
  writes the tree, and tells you its path.
- `/tree-upload` uploads the HTML view of a theme's question tree to the host's Artifact as a new
  page that only you can see. It lists the file and waits for your approval; without the host's
  Artifact feature nothing is sent and the HTML stays on your machine.

### Changed

- A rerun of `/analysis-framing` on a theme that has a question tree now always asks which node to
  design next. When you pick a node other than the one the latest decision names, it asks for your
  reason and keeps the change as a decision.
- **A project's `.insight/rules/package_allowlist.yaml` now adds packages to the default
  allowlist instead of replacing it.** The default allowlist (pandas, matplotlib, numpy, marimo,
  insight_blueprint) is what every contract notebook imports, so it is always allowed and
  `/analysis-auto` no longer pauses on those imports at the notebook gate. To allow one more
  package, list only that package in the file. Only `json` and `pathlib`, the standard-library modules
  the contract itself imports, need no entry ([ADR-0027](docs/adr/0027-default-allowlist-always-allowed.md), #108).

### Fixed

- **`premortem` showed `unknown` in the INTENT column for every design** (#109). It read an
  `intent` key, but `design_io get` returns the field as `analysis_intent`. The risk level was
  not affected; only the table display was wrong.

## [0.12.0] - 2026-11-20

### Upgrade note

- `catalog_io create` and `update` now refuse a `connection` key that names a credential. A source
  stored earlier with such a key is still read, but `update` refuses it. Edit its YAML by hand: keep
  the secret in an environment variable and name it in a `*_env` key (e.g.
  `"password_env": "PG_PASSWORD"`). Do not ask the model to read the source with `--with-connection`.
- Designs created earlier may carry a file path or table name in `methodology.steps`. They still
  work. To keep the path out of the design and the report, rewrite the step with `{source:ID}`
  through `/analysis-design`.

Epic 17 (#102): a data source's `connection` reaches the model only in `/analysis-notebook`, and the
catalog holds no credentials. Design: `docs/design/epic-17-connection-boundary.md`.

Epic 16 (#101): a project without `.insight/rules/package_allowlist.yaml` uses the default
allowlist instead of stopping at premortem. Design: `docs/design/epic-16-default-allowlist.md`.

### Changed

- **`/analysis-framing` reads the data sources with `catalog_io list`**, which leaves `connection`
  out, instead of opening the catalog YAML. Its cross-search no longer greps the source files
  ([ADR-0022](docs/adr/0022-connection-reaches-only-the-notebook.md)).
- **`/analysis-design` names a data source as `{source:ID}` in `methodology.steps`** and never writes
  a path, host, project id or table name. `/analysis-notebook` replaces each `{source:ID}` with the
  location in that source's `connection` in cell 2. `/analysis-auto`'s data-extraction beat shows
  the data source id instead of the file ([ADR-0022](docs/adr/0022-connection-reaches-only-the-notebook.md)).
- **`catalog_io create` and `update` refuse credential keys in `connection`** (`password`, `token`,
  `api_key`, `secret`, `credential`, `private_key`, `access_key`, nested too) and exit non-zero,
  naming the key but not its value. A `*_env` key such as `password_env` passes when its value is an
  environment variable name (`^[A-Z_][A-Z0-9_]*$`). Reading is unchanged
  ([ADR-0023](docs/adr/0023-catalog-holds-no-credentials.md)).
- **`/premortem` and `/analysis-auto` no longer stop a project that has no
  `.insight/rules/package_allowlist.yaml`.** They use the default allowlist (the packages the plugin
  env ships, listed in the notebook contract). A methodology that needs another package now stops at
  `HARD_BLOCK` instead of `HIGH` (ADR-0021).
- The `HARD_BLOCK` reason for a package outside the allowlist is now
  `package outside allowlist (declare it in .insight/rules/package_allowlist.yaml)`. A script that
  matches the old reason exactly must match its prefix instead.

## [0.11.0] - 2026-11-20

### Upgrade note

- Designs created before this release have an empty `source_ids`. Their report leaves out the data
  source table and says how to add them, `/premortem` returns `HARD_BLOCK`, and `/analysis-notebook`
  stops and points to `/analysis-design`. Add the ids once with `/analysis-design`: open the existing
  design and declare its sources (Step 0 → Step 3b).

Epic 15 (#71): a design declares the data sources it uses in `source_ids`, and every skill reads
them from there. Design: `docs/design/epic-15-declared-source-ids.md`.

Epic 14 (#76): a report written from the same analysis has the same shape whichever model writes
it. The parts of the `/analysis-report` template that were left to the model are now rules.
Design: `docs/design/epic-14-report-template-gaps.md`.

### Added

- **`catalog_io describe --ids a,b`** returns `{"sources": [...], "missing": [...]}`: the registered
  sources in the order given, once each, with only `id`, `name`, `type`, and `description` (never
  `connection`), and every other id under `missing`
  ([ADR-0020](docs/adr/0020-design-declares-sources-in-source-ids.md)).

### Changed

- **`/analysis-design` asks for the data sources and writes them to `source_ids`**, after checking
  the ids with `catalog_io describe`. It never writes an unregistered id. It can also open an
  existing design to declare its sources (Step 0 → Step 3b). `data_source` on a metric or an
  explanatory variable is now a free-form note that no skill reads as an id.
- **`/analysis-report`, `/analysis-notebook`, `/premortem`, and `/analysis-auto` read the data sources
  from `source_ids` only.** The report passes them to `catalog_io describe` and no longer collects
  candidates from `data_source`. `/premortem` returns `HARD_BLOCK` with the reason
  `no data source declared` for a design whose `source_ids` is empty. The model is unchanged.
- **`/analysis-report` names the source of every section.** Open questions follow the journal's
  definition, and the title comes from the design's `title`. The report no longer reads the
  verdict's `evidence_summary` or `open_questions`, which reach it through the journal. Future
  Directions is written from the open questions only. The line written when there is no figure
  depends on why there is none.
- **Fixed formats for tables and numbers.** Method has a table of metrics and one of explanatory
  variables, and a column with no value in any row is left out. `Pass` is written as `✓`, `✗`, or
  `—`. Results splits the evidence into what supports the hypothesis and what contradicts it.
- **Fixed lead sentences.** The Abstract opens with one sentence per terminal status, and
  Recommendation opens with one sentence per row of its table.
- **Discussion.** Limitations is one paragraph built from the limits, the assumptions, and the
  evidence against the conclusion. An empty Limitations or Future Directions is left out, with no
  note in its place.
- **`/analysis-journal`** accepts one id or a list of ids in `metadata.resolves`.

## [0.10.0] - 2026-11-20

Epic 13 (#75): text that came from the analysis inputs is written into the report as characters,
never as markup. Design: `docs/design/epic-13-report-source-text.md`.

### Added

- **`report_check --id {design_id}`** checks a written report for markup that is still active: an
  image that is not a figure, any tag start (`<` followed by a letter, `/`, `!`, or `?`), and, in a
  Mermaid block, a tag other than `<br/>` or a line the lineage export never writes. It fails
  closed: code spans and fences other than Mermaid are checked like any text. It exits 1
  and prints the violations as JSON. `/analysis-report` runs it right after writing the report
  ([ADR-0019](docs/adr/0019-report-source-text-escaped-and-checked.md)).

### Changed

- **`/analysis-report` escapes source text instead of leaving the choice to the model
  ([ADR-0019](docs/adr/0019-report-source-text-escaped-and-checked.md)).** Figure captions,
  data-source fields, lineage reasons, metric names, the decision context, and the title keep
  every word, become one line, and get a backslash before `\` `` ` `` `*` `_` `[` `]` `<` `|`.
  A sentence in them that reads as an instruction stays as text, and the skill tells the analyst
  where it is. A lineage diagram is left out of the Appendix when a label carries a tag other than
  `<br/>` or a line is not one the lineage export writes.

- **`catalog_io` no longer prints a source's `connection` (`get`, `list`, `create`, `update`)
  ([ADR-0018](docs/adr/0018-catalog-io-omits-connection-by-default.md)).** A connection holds file
  paths, queries, hosts, and sometimes credentials, and `/analysis-report` reads `catalog_io get`
  to build a report that can leave the machine. Pass `--with-connection` to get it back;
  `/analysis-notebook` does, because it loads the data. The stored YAML is unchanged.

## [0.9.0] - 2026-11-19

Epic 12 (#62): `/analysis-report` now writes a report a reader can **decide from**, and a new
`/report-upload` skill copies it to Claude Docs. Design: `docs/design/epic-12-decision-ready-report.md`.
Unlike Epic 10 and 11, this touches the PyPI wheel: `insight_blueprint.models.design` gains
`DecisionContext`. Every addition is optional, so existing designs, notebooks, and verdicts keep working.

Epic 11 (#56): the development docs follow the repo-template flow (ADR-0009). Design:
`docs/design/epic-11-repo-template-compliance.md`. The PyPI wheel's runtime (`src/insight_blueprint`)
and the skills are untouched.

### Added

- **`/report-upload` — upload a report to Claude Docs.** Reads `.insight/reports/{id}.md` and its
  figures and creates a **new** Doc, visible only to you until you share it. It never updates,
  overwrites, or shares a Doc. It uses the host's Claude Docs connector; the plugin still ships no
  MCP server ([ADR-0015](docs/adr/0015-host-connectors-for-optional-features.md)). Without the
  connector nothing is sent and the Markdown report stays as it is. A figure that cannot be
  uploaded is left out with a one-line note.
- **Approval before anything leaves the machine ([ADR-0016](docs/adr/0016-approval-before-external-send.md)).**
  `/report-upload` lists the files it would send and waits for your answer. Nothing is created or
  sent before a clear yes. The approval covers that one run and is never remembered, also inside
  `/analysis-auto`.
- **`decision_context` in the design document ([ADR-0014](docs/adr/0014-analysis-design-decision-context.md)).**
  An optional `{decision_maker, decision}` pair: who decides what from this analysis. When present,
  both fields must be non-empty. `/analysis-design` asks for it once after the hypothesis (you can
  skip it), `design_io create` / `update` accept it, and `/analysis-review` checks that it fits the
  hypothesis. Designs without it validate as before.
- **Optional metric items in the notebook contract ([ADR-0013](docs/adr/0013-verdict-metric-optional-items.md)).**
  Each entry of `verdict.metrics` may carry `effect_size` (`{kind, value}`), `confidence_interval`
  (`{level, lower, upper}`), and `sample_size`. The notebook computes them; a method that does not
  define one omits the key. A verdict without them is read as before.

### Changed

- **`/analysis-report` carries what a decision needs.** Introduction shows the decision context.
  Method describes the data sources (name, type, and description from the catalog; never the
  `connection` values) and the row counts through the pipeline (from the lineage diagram). The
  Results table gains Effect size / CI / N columns, each shown only when some metric has a value.
  Discussion gains Implications and Recommendation, and a new Appendix holds the lineage diagram
  and the notebook path. The skill stays read-only and computes no numbers; sections whose inputs
  are missing are omitted, so a report from an older analysis looks as it did.
- **`/analysis-auto` starts `/report-upload` after it builds a report.** The driver does not ask
  whether to upload; the approval of `/report-upload` is the only question.
- Development docs (Epic 11): `CLAUDE.md` holds only a summary and pointers; `CONTRIBUTING.md` keeps Setup / Common Commands /
  Testing / Security Checklist. `docs/UBIQUITOUS_LANGUAGE.md` gets its first edition, and
  `docs/ARCHITECTURE.md` gets a context map and a Domain Model class diagram.
- New development ADRs (Epic 11): [ADR-0010](docs/adr/0010-skill-tdd-structure-tests.md) (skill TDD reading),
  [ADR-0011](docs/adr/0011-domain-model-overview-in-architecture.md) (Domain Model overview),
  [ADR-0012](docs/adr/0012-single-pr-scope.md) (scope of non-Epic PRs).

### Removed

- **`.mcp.json` (user-facing).** The plugin payload is the repository root, so installed plugins
  (up to 0.8.0) carried a `.mcp.json` that registered the dev-only `spec-workflow` MCP server
  (`npx -y @pimzino/spec-workflow-mcp@latest`). The file is gone; the plugin now ships no MCP
  server configuration, matching the "No MCP server" invariant. If you added `spec-workflow` to
  your own setup on purpose, configure it in your project instead.
- `.spec-workflow/` (pre-fork steering docs and templates, superseded by `docs/design/` + `docs/adr/`).

### Fixed

- **`design_io`, `catalog_io`, and `premortem` failed in an installed plugin (since 0.7.1).**
  Claude Code puts the plugin's `bin/` on the Bash tool's PATH but does not export
  `CLAUDE_PLUGIN_ROOT` there, so the wrappers stopped with `CLAUDE_PLUGIN_ROOT is not set`.
  They now fall back to their own location to find the plugin root
  ([ADR-0017](docs/adr/0017-plugin-variables-not-in-bash-env.md)).

## [0.8.0] - 2026-07-08

Epic 10 (#47): a new `/analysis-report` skill that assembles a **distributable APA-style
Markdown report** from a concluded analysis, so results can be explained to others — not just
read in the notebook. Design: `docs/design/epic-10-analysis-report.md`; contract change:
[ADR-0008](docs/adr/0008-notebook-figure-manifest.md). The PyPI wheel's runtime
(`src/insight_blueprint`) is untouched — the surface is skills, the notebook contract, and docs.

### Added

- **`/analysis-report` — APA-style report assembly.** A read-only consumer that reads the design
  (`design_io get`), Insight Journal, notebook verdict, and figure manifest, and writes
  `.insight/reports/{id}.md` with English APA headings (Abstract / Introduction / Method /
  Results / Discussion→Limitations/Future Directions / References); narrative stays in the user's
  language. Requires a terminal status (`supported`/`rejected`/`inconclusive`). Each figure carries
  mandatory **Axes（軸の説明）** and **How to read（図の読み方）** captions. Template:
  `skills/analysis-report/references/apa-template.md`.

### Changed

- **notebook 8-cell contract extended for figures ([ADR-0008](docs/adr/0008-notebook-figure-manifest.md)).**
  The viz cell now saves each figure to `.insight/notebooks/{id}_fig{NN:02d}.png`, and the verdict
  cell records a `figures[]` manifest (`file`/`title`/`axes`/`how_to_read`) plus `metrics` in
  `{id}_verdict.json` — so `/analysis-report` embeds figures with axis + how-to-read captions
  without re-rendering, and the figure's truth lives with the producer. **Backward compatible**:
  a verdict lacking `figures` is treated as `[]` (graceful degrade — the report omits figures and
  notes it). `figures[].file` is constrained to a bare basename (no path traversal into a
  distributable artifact).
- **Pipeline wiring.** `/analysis-reflection` and `/analysis-auto` chain to `/analysis-report`;
  `/analysis-auto` offers report generation as a KEEP gate after a terminal conclusion. README,
  `CLAUDE.md`, and `docs/ARCHITECTURE.md` updated.

## [0.7.3] - 2026-07-06

Patch release closing the two open Epic 09 follow-ups (#40 / #41). Both are hardening /
documentation of the plugin **execution model** shipped in 0.7.1 — no change to the PyPI
wheel's runtime (`src/insight_blueprint` is untouched); the surface is the `bin/` wrappers,
`skills/_shared`, and docs. Source review: `.claude/docs/research/review-security-epic09.md`
(M1/M3/L3) and `review-docs-epic09.md` (F5).

### Security

- **`INSIGHT_BASE_DIR` / `--base-dir` is now a validated trust boundary (M1, #40).** The base
  flows into every read/write path, so it is no longer trusted verbatim. Two layers: the
  `bin/` wrappers (`design_io` / `catalog_io` / `premortem`) assert `${CLAUDE_PROJECT_DIR}`
  exists and that the base ends in `/.insight` **before** `mkdir` (folding in the L1 finding),
  and `design_io` / `catalog_io` gain `_resolve_base_dir()` which rejects an absurd anchor
  (filesystem root, the bare `$HOME`) after `Path.resolve()`. The `.insight` suffix is enforced
  only in the wrapper, so `--base-dir` back-compat and tmp-dir tests are unaffected.
- **Host-variable trust boundaries documented in [ADR-0006](docs/adr/0006-plugin-execution-model.md)
  (M3 / L3, #40).** Claude Code hooks take a single command string (no `argv` form), so
  `CLAUDE_PLUGIN_ROOT` is assumed a Claude-Code-controlled path free of shell metacharacters;
  `UV_PROJECT_ENVIRONMENT` ← `CLAUDE_PLUGIN_DATA` is recorded as the same class of host-var trust.

### Documentation

- **`package_allowlist.yaml` format & package-supply procedure (F5, #41).** New "Package
  allowlist — format & supplying packages" section in
  `skills/analysis-notebook/references/notebook-contract.md`: the file is an `import-name →
  pip-name` map (a boundary declaration, not an installer), and an allowlisted package outside
  the `notebook` extra is supplied to a run ephemerally with `--with <pip-name>` (no mutation of
  the read-only plugin env). `analysis-notebook/SKILL.md` and `docs/ARCHITECTURE.md` now link it.

## [0.7.2] - 2026-07-06

Patch release enriching the **upstream dialogue** of `/analysis-auto`. The autopilot's
single design gate collapsed at runtime into one direction pick, so methodology, figures,
and — most importantly — the actual data pull (SQL) never got a confirmation seat. This
release re-weights the gates toward the epistemic decision points
([ADR-0007](docs/adr/0007-upstream-judgment-gates.md), amending
[ADR-0005](docs/adr/0005-selective-autonomous-chaining.md)).

### Added

- **`data-extraction` gate** (design beat ③, before premortem) — `/analysis-auto` now
  surfaces the actual data-acquisition plan for confirmation before `design_io create`: the
  SQL query text drafted into `methodology.steps` for SQL sources, or the file + columns +
  filter for CSV/others, plus expected grain and a rough row/scan estimate. premortem then
  estimates cost against the **confirmed** query. A source with no SQL still gets this beat.

### Changed

- **`/analysis-auto` design confirmation is now four ordered beats** — hypothesis → methodology
  (+ metrics + explanatory roles + intent) → data-extraction → charts — each presented as its
  own AskUserQuestion so the user can adjust it, instead of a single "confirm the whole design".
  Downstream steps (premortem / notebook / journal) stay AUTO; friction is added only upstream.
- `/analysis-design` Step 2.6 and `/analysis-notebook` cell 2 note that, under the driver, the
  auto-drafted extraction query is user-confirmed and must not silently diverge at execution.

## [0.7.1] - 2026-07-04

Patch release fixing the **installed-plugin execution model** (Epic 09). v0.7.0's skill
commands assumed the dev-repo layout, so the published plugin did not actually run when
installed into a separate project. This release makes the plugin self-contained.

### Fixed

- **The plugin now runs when installed into a user's own project** (Epic 09). Previously
  skill commands assumed the repo cwd and an externally-installed `insight_blueprint`, so an
  installed plugin failed with `ModuleNotFoundError: No module named 'skills'`. Commands now
  go through `bin/` wrappers that execute in the plugin's own uv environment and target the
  user project's `.insight/` via `INSIGHT_BASE_DIR`; the validation hook ships with the plugin
  (`hooks/validate-design.py` + `hooks/hooks.json`) and enforces integrity in the user's
  project too ([ADR-0006](docs/adr/0006-plugin-execution-model.md))
- `/premortem` now reads `.insight/config.yaml` from the user's project (honors
  `INSIGHT_BASE_DIR` / `--base-dir`) instead of silently falling back to default risk
  thresholds
- Pre-write hook now fails **closed** for design documents on an internal error (was
  fail-open), so an unvalidated `*_hypothesis.yaml` write cannot slip through
- Fixed a mermaid parse error in the Epic 09 design doc sequence diagram

### Changed

- Notebook execution borrows the plugin's uv environment
  (`uv run --project ${CLAUDE_PLUGIN_ROOT} --extra notebook`) while keeping the user's cwd, so
  generated artifacts land in the user project's `.insight/notebooks/` and `.insight/lineage/`
- Docs: ARCHITECTURE gains a dev-vs-installed directory-layout section (path-resolution
  mechanisms); README dependency story clarified (the plugin is self-contained;
  `insight-blueprint-lineage` is needed only for hand-written `tracked_pipe` lineage);
  `analysis-design` hook path and README knowledge example corrected

## [0.7.0] - 2026-07-03

Lightweight migration (Epics E1–E8): the platform is now a Claude Code skills plugin —
skills + YAML + an embedded validation library, with no server, daemon, or SQLite.
First release under the PyPI name **`insight-blueprint-lineage`** (import name stays
`insight_blueprint`).

### Added

- New skill `/knowledge-extract` — Claude-native extraction of source-scoped domain knowledge from a concluded analysis, persisted via `catalog_io add-knowledge` (E5b)
- New skill `/analysis-review` — produce a design review batch (producer side of the review loop) via `design_io review-batch` (Epic 06)
- New skill `/analysis-notebook` — generate a marimo notebook from the design's methodology (8-cell contract), run it, and record results to the journal; optional `insight-blueprint-lineage[notebook]` extra (Epic 07)
- New skill `/analysis-auto` — guided autopilot that drives the pipeline and pauses only at genuine decision gates ([ADR-0005](docs/adr/0005-selective-autonomous-chaining.md), Epic 08)
- `catalog_io` / `design_io` server-free YAML helpers backing the skills; `catalog_io add-knowledge` write path (validate + upsert-by-key + atomic write) (E3, E3.5, E5b)
- Pre-write hook (`.claude/hooks/validate-design.py`) enforcing design-document schema + state transitions via `src/insight_blueprint/validate.py` (E2)

### Changed

- `/premortem` is now **report-only** — no approval tokens, no run history, no `.insight/premortem/` writes; it prints a static risk report and exits non-zero on HARD_BLOCK/HIGH (E5a)
- Catalog taxonomy is now **open strings**: source `type` and knowledge `category` accept any non-empty value (conventional values kept as `KNOWN_*` constants); `ColumnSchema`/`DataSource` allow extra fields (ADR-0004, E5c)
- Docs overhauled for public plugin release: corrected install commands and repo naming (`insight-blueprint-skills`), added Quickstart and status/review guidance
- PyPI distribution renamed to **`insight-blueprint-lineage`** to avoid colliding with the upstream `insight-blueprint` (MCP) package; the import name stays `insight_blueprint`. Install the optional lineage library with `uv add insight-blueprint-lineage`

### Fixed

- Path-traversal hardening in `design_io` / `catalog_io`: `design_id` / `source_id` are validated (`[a-zA-Z0-9_-]+`) before being interpolated into `.insight/` paths, closing an escape via `../`

### Removed

- MCP server, REST API, WebUI, and SQLite (E1–E4) — replaced by skills + YAML + `validate.py`
- `batch-analysis` skill and its harness (token / run-history / manifest / crash-recovery), superseded by Claude Code auto mode (E3.5, E5a)
- Pre-fork `.spec-workflow/specs/` design documents and the orphaned `_templates/` package (superseded by `docs/design/` + `docs/adr/`)

## [0.6.0] - 2026-06-16

### Added

- New skill `/rq-problematization` — generate impactful research questions via the Alvesson & Sandberg (2011) problematization framework: surface taken-for-granted assumptions across five types and challenge them with a devil's-advocate critic subagent (assumption-challenging over gap-spotting)
  - Positioned upstream of `/analysis-framing`: rq-problematization (theory-driven RQ) → analysis-framing (data grounding) → analysis-design. Does not chain directly to analysis-design — framing is the data-grounding gate
  - Re-generation path from `/analysis-reflection`: when a hypothesis is rejected/inconclusive, question the underlying assumption instead of only seeking a new angle
  - Bundled `evals/evals.json` — the repository's first eval suite, focused on gap-spotting regression and citation-fabrication checks

## [0.5.1] - 2026-04-21

### Fixed

- Remove `$schema` field from `.claude-plugin/marketplace.json` to restore plugin skill loading (#123)
  - Claude Code's marketplace validator rejected `$schema` as an Unrecognized key,
    causing the runtime to treat the plugin as disabled even when enabled in settings
  - This blocked all insight-blueprint skills (`analysis-design`, `analysis-framing`,
    `catalog-register`, `premortem`, etc.) from loading into the available skills list

## [0.5.0] - 2026-04-21

### Added

- New skill `/premortem` — pre-flight risk evaluation with approval token issuance (#117) — _the approval token was removed in E5a; `/premortem` is now report-only (see [Unreleased])_
- `spec-workflow` MCP server registered in `.mcp.json` (#118)

### Changed

- Batch analysis harness hardened for overnight stability (#117)
  - Flat manifest status contract with `completed` state (was nested `execution.status`)
  - 2-stage design hash verification for safe resume after crash
  - Launcher-owned `finalize_run` for consistent lifecycle termination
  - Hash mismatch detection in claude step + stub env toggles
  - User-facing documentation for risk levels, `.insight/config.example.yaml`, crash recovery

### Fixed

- `uv.lock` self-reference version out of sync with `pyproject.toml` (#119)

### Chore

- Ignore per-clone runtime stubs under `.insight/` (#120)

## [0.4.2] - [0.4.4]

Version bumps and maintenance releases. See git history for details:
`git log v0.4.1..v0.4.4 --oneline`.

## [0.4.1] - 2026-04-06

### Added

- `/batch-analysis` skill for overnight batch execution of queued analysis designs
- `batch-prompt.md` headless orchestration prompt with 8-cell notebook contract
- `next_action` field convention for queue management (`batch_execute` type)
- Claude Code Plugin distribution format (`.claude-plugin/plugin.json`, `.mcp.json`)
- Plugin validation CI job (`plugin-validate`)
- data-lineage Python package prerequisites check
- Migration guide in README
- Custom marketplace for plugin distribution

### Changed

- Skills moved from `src/insight_blueprint/_skills/` to `skills/` (repository root) for Plugin auto-discovery
- Rules (`_rules/`) integrated into SKILL.md definitions
- Extension policy and optional package note added to CLAUDE.md managed section

### Removed

- `upgrade-templates` CLI subcommand
- Skill/rule copy logic from `storage/project.py` (~400 lines)

## [0.4.0] - 2026-03-20

### Added

- `--mode server` for team deployment: serves WebUI + MCP SSE on the same HTTP port
- `--mode headless` for lightweight deployment: MCP SSE only (no WebUI)
- `--host` and `--port` options for server/headless mode (default: 0.0.0.0:4000)
- `--no-browser` flag to suppress browser auto-open in full mode
- Concurrent write safety with `threading.Lock` on `write_yaml`

### Deprecated

- `--headless` flag: use `--no-browser` instead (flag still works with deprecation warning)

## [0.3.0] - 2026-03-17

### Added

- `get_review_comments` MCP tool for reading review batches (closes read/write asymmetry in review workflow)
- `/analysis-revision` skill for structured revision of review comments with per-comment tracking

### Changed

- Added methodology and analysis_intent as reviewable sections in WebUI inline comments

## [0.2.0] - 2026-03-11

### Added

- Analysis Framing skill for structuring analysis scope and approach
- Unified 6-skill chaining: analysis-design → analysis-framing → analysis-journal → analysis-reflection → catalog-register → data-lineage
- `--version` flag for CLI version display

### Changed

- Upgraded shadcn from 4.0.0 to 4.0.2
- Restructured README to prioritize user experience

### CI

- Added Dependabot auto-merge for patch updates

## [0.1.0] - 2026-03-10

### Added

- Analysis Design management with hypothesis-driven workflow
- Data Catalog for domain knowledge and caution registration
- Review workflow with status transitions (draft → reviewing → approved/revised)
- Domain Knowledge suggestion for analysis designs (4 matching strategies)
- Data Lineage tracking for data transformations
- WebUI Dashboard with 2-tab navigation (Designs / Catalog)
- Bundled Skills: analysis-design, analysis-journal, analysis-reflection, catalog-register, data-lineage
- Typed verification models: ExplanatoryVariable, Metric, ChartSpec, Methodology
- YAML direct edit resilience (extra field preservation + corrupt file isolation)
- SQLite FTS5 full-text search index

[unreleased]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.12.0...HEAD
[0.12.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.3...v0.8.0
[0.7.3]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.4...v0.5.0
[0.4.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/etoyama/insight-blueprint-skills/releases/tag/v0.1.0
