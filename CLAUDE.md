# CLAUDE.md

Guidelines for AI coding assistants (Claude Code, etc.) and human contributors
working on this repository.

## 1. Project Overview

**insight-blueprint-skills** is a hypothesis-driven EDA platform delivered as a
Claude Code **skill plugin**. It is a lightweight fork of
[insight-blueprint](https://github.com/etoyama/insight-blueprint) that drops the
MCP server, WebUI, and SQLite in favor of **skills + YAML + an embedded validation
library**. See [ADR-0001](docs/adr/0001-drop-mcp-server-embed-validation.md) for the
rationale.

**Preserved core (non-negotiable):**

- marimo notebook templates & cell contract — data-processing transparency, lineage
- analysis design documents + the skills that generate them
- journal / reflection — interpreting results and drawing conclusions
- premortem — cost-incident prevention before expensive data access

**Migration status.** The MCP server / WebUI / SQLite have been removed (E1–E4 complete;
see ADR-0001 → Related). The architecture below is now the actual state, not just a target.
E5 completes the roadmap: premortem self-standing (E5a, done) / knowledge extraction
(E5b, done) / catalog flexibility (E5c, done — open-string taxonomy, see ADR-0004).

## 2. Architecture

Invariants: **No daemon. No MCP server. No SQLite.** Validation lives in a library
(`validate.py`), not a process — the same trade SQLite makes by embedding instead of
running a server. Components: skill layer (`skills/`), validation library
(`validate.py`), pre-write hook, skill-managed YAML (`.insight/`), marimo + lineage.

The full architecture (component map, current→target migration diagram, Epic mapping)
is canonical in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**; product requirements
live in **[docs/PRD.md](docs/PRD.md)**.

## 3. Tech Stack

uv (packaging) / ruff (lint+format) / ty (type check) / pytest (tests) / marimo
(notebooks). Details in [.claude/rules/dev-environment.md](.claude/rules/dev-environment.md).

## 4. Development Workflow

GitHub issue-driven, **two tiers**:

- **Epic** (`type:epic`): a coherent step toward the lightweight target; accompanied
  by `docs/design/epic-NN-<topic>.md` ([template](.claude/rules/design-doc-template.md)).
- **Story** (`type:story`): 0.5–3 day unit, ≤5 acceptance criteria.

Branching model is **trunk-based with stacked Epics** (`main` is the trunk; no `dev`
integration branch — see [ADR-0002](docs/adr/0002-trunk-based-epic-stacking.md)):

- Epic: `epic/<num>-<slug>` cut from `main`. Epic PRs target `main`.
- Story: by default, commit Stories directly onto the Epic branch. Only when a Story
  warrants independent review, cut `(feat|fix|chore|refactor)/<story-num>-<slug>` from
  the Epic branch and PR it into the Epic branch (a stacked PR).
- Releases are tag-driven (`publish.yml` on `v*`), so merging an Epic to `main` does
  not publish.

**AI assistants must not merge Epic PRs into `main`.** The user reviews and merges
manually.

## 5. Architecture Decision Records (ADR) — hard rule

Cross-epic design decisions, long-term constraints, and any change to the target
architecture above are recorded as ADRs under `docs/adr/NNNN-<slug>.md`
([template](.claude/rules/adr-template.md)). Epic-scoped decisions that will not be
cited later stay in the Epic's Design Doc `## Decisions` section.

When implementing a Story, if investigation surfaces a design choice the approved
plan did not anticipate, do **one** of the following before the PR can merge:

1. Create an ADR (default for non-trivial architectural / library / public-contract choices).
2. Add a `## Decision` block to the Epic's Design Doc (genuinely Epic-scoped only).
3. Flag in the PR description and ask the user (only when 1 and 2 are over-engineering).

## 6. Skills

| Skill | Purpose |
|-------|---------|
| `/rq-problematization` | Challenge prior-research assumptions, generate impactful RQs |
| `/analysis-framing` | Explore data & existing analyses to frame a direction |
| `/analysis-design` | Guided hypothesis design-document creation |
| `/analysis-review` | Produce a design review batch (producer side of the review loop) |
| `/analysis-notebook` | Generate + run a marimo notebook from the design's methodology; record results to journal |
| `/analysis-journal` | Record observations, evidence, decisions during analysis |
| `/analysis-reflection` | Structured reflection to conclude or branch a hypothesis |
| `/analysis-report` | Assemble a distributable APA-style Markdown report from a concluded analysis (read-only consumer) |
| `/analysis-revision` | Guided revision workflow for review comments (consumer side) |
| `/catalog-register` | Register a data source (flexibility extended in E5c) |
| `/knowledge-extract` | Claude-native extraction of source-scoped domain knowledge (since E5b) |
| `/data-lineage` | Track transformations, export lineage diagrams (Mermaid) |
| `/premortem` | Report-only pre-flight cost/risk evaluation (self-standing since E5a) |
| `/analysis-auto` | Guided autopilot: drives the pipeline, pausing at genuine gates (ADR-0005) |

`batch-analysis` was removed in E3.5 (superseded by Claude Code auto mode).
`premortem` is now report-only (token/run-history removed in E5a). `knowledge-extract`
is Claude-native (regex extraction not restored; findings stay in reflection — E5b).
Remaining E5 work: catalog flexibility (E5c). See ADR-0001.

## 7. Skill-Managed Data (`.insight/`)

Skills directly manage YAML outside any server's schema scope:

- `.insight/designs/*_hypothesis.yaml` — analysis design documents (validated via hook)
- `.insight/designs/*_journal.yaml` — Insight Journal
- `.insight/designs/*_revision.yaml` — revision tracking
- `.insight/catalog/` — data sources and extracted knowledge

## 8. Validation Guard

Design-document integrity is enforced by `hooks/validate-design.py`, which
calls `src/insight_blueprint/validate.py` on every write to a `*_hypothesis.yaml`:

- **Schema** — `AnalysisDesign` Pydantic model (notably `DesignStatus`, non-empty `Methodology.method`)
- **State transition** — `VALID_TRANSITIONS` guard (e.g. `in_review → supported`)

Violations block the write (`exit 2`). The hook **ships with the plugin** via
`hooks/hooks.json` (running through the plugin's own uv env), so it enforces integrity in a
user's installed project too — not just this repo. (This repo's `.claude/settings.json`
wires the same script for local development.) Skills that write via `design_io` also
self-validate on the Python path, so both the tool-write and helper-write paths are guarded.

## 9. Code Review

`orchestra:team-review` (5 reviewers: security / quality / test coverage /
requirements / …) runs after implementation. Use `--spec` only if a spec exists;
otherwise review against the Epic Design Doc and ACs.

## 10. Code Style & Testing

- ruff is the lint/format authority; CI rejects on violation.
- Public APIs carry type hints. Comments explain *why*, not *what*.
- pytest is the runner. TDD where reasonable (parsers, validation, pure functions).
- `validate.py` is pure-function and must stay unit-testable without I/O.

## 11. Rules and Templates

- [.claude/rules/adr-template.md](.claude/rules/adr-template.md)
- [.claude/rules/design-doc-template.md](.claude/rules/design-doc-template.md)
- [.claude/rules/dev-environment.md](.claude/rules/dev-environment.md)
- [.claude/rules/coding-principles.md](.claude/rules/coding-principles.md)
- [.claude/rules/testing.md](.claude/rules/testing.md)
- [.claude/rules/skill-format.md](.claude/rules/skill-format.md)

## 12. Language Rules

- Respond to users in **Japanese**.
- Code, YAML field names, and tool names stay in **English**.
- Documentation is **Japanese, single-language** (the bilingual ja/en policy from the
  upstream template is intentionally not adopted).
