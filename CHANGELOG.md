# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[unreleased]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.4...v0.5.0
[0.4.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/etoyama/insight-blueprint-skills/releases/tag/v0.1.0
