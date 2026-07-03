# insight-blueprint

[![PyPI](https://img.shields.io/pypi/v/insight-blueprint-lineage)](https://pypi.org/project/insight-blueprint-lineage/)
[![CI](https://github.com/etoyama/insight-blueprint-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/etoyama/insight-blueprint-skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/etoyama)

A **Claude Code skills plugin** for hypothesis-driven EDA. Analysis designs, journals,
reviews, and the data catalog live as YAML under `.insight/`; skills read and write them
directly. Integrity is enforced by an **embedded validation library** (`validate.py`) plus
a pre-write hook — **no server, no daemon, no SQLite**. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRD.md](docs/PRD.md).

## Quickstart

**Prerequisites:** [Claude Code](https://code.claude.com/docs), [uv](https://docs.astral.sh/uv/),
and Python 3.11+. The skills shell out to `uv run …`, which resolves the Python dependencies
automatically — there is nothing to `pip install`.

1. **Install the plugin.** In Claude Code, register this repo as a marketplace and install:
   ```
   /plugin marketplace add etoyama/insight-blueprint-skills
   /plugin install insight-blueprint@insight-blueprint-marketplace
   ```
2. **Open your analysis project** in Claude Code and take the first step:
   ```
   /analysis-framing        # explore your data & frame a direction
   /analysis-design         # turn it into a hypothesis design document
   /analysis-journal        # record reasoning as you investigate
   /analysis-reflection     # conclude (or branch) the hypothesis
   /knowledge-extract       # save reusable, source-scoped knowledge
   ```

There is nothing to launch — skills read and write YAML under `.insight/` in your project
(created on first use). Writes to design documents are validated automatically by a pre-write hook.

## Installation

### Claude Code plugin (recommended)

In Claude Code, add this repository as a plugin marketplace and install from it:

```
/plugin marketplace add etoyama/insight-blueprint-skills
/plugin install insight-blueprint@insight-blueprint-marketplace
```

Here `insight-blueprint` is the plugin name and `insight-blueprint-marketplace` is the
marketplace defined in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json).

### Local clone (for development)

```bash
git clone https://github.com/etoyama/insight-blueprint-skills.git
claude --plugin-dir ./insight-blueprint-skills
```

`--plugin-dir` loads the plugin for the current session only. Add a shell alias to make it stick:

```bash
alias claude-ib='claude --plugin-dir /path/to/insight-blueprint-skills'
```

### Optional: Python package (only for hand-written lineage)

**You do not need to install anything for the skills to work.** The plugin is
self-contained: its bundled uv environment provides `insight_blueprint` (models,
validation, lineage) and `/analysis-notebook` runs marimo/pandas through that same
environment (`--extra notebook`). See [ADR-0006](docs/adr/0006-plugin-execution-model.md).

Install the `insight-blueprint-lineage` package **only** if you want to import
`tracked_pipe` directly in your own notebooks/scripts (i.e. lineage tracking outside
`/analysis-notebook`). The import name stays `insight_blueprint`:

```bash
uv add insight-blueprint-lineage
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## How it works

- **Skills** (`skills/`) drive the workflow and read/write `.insight/` YAML via small
  server-free helpers (`skills/_shared/design_io.py`, `catalog_io.py`).
- **Validation** is centralized in `src/insight_blueprint/validate.py` (Pydantic schema +
  state-transition guard). A **pre-write hook** (`hooks/validate-design.py`, shipped with the
  plugin via `hooks/hooks.json`) calls
  the same library to block invalid writes to `*_hypothesis.yaml`.
- **Lineage** (`src/insight_blueprint/lineage/`) records DataFrame transformations and
  exports Mermaid diagrams.

## Skills

- `/rq-problematization` — Generate impactful research questions by problematizing prior-research assumptions (upstream of framing)
- `/analysis-framing` — Explore available data and existing analyses to frame a direction
- `/analysis-design` — Guided creation of hypothesis design documents
- `/analysis-review` — Produce a structured review of a design and record it as a review batch
- `/analysis-notebook` — Generate a marimo notebook from the design's methodology, run it, and record results to the journal
- `/analysis-journal` — Record reasoning steps during analysis (observations, evidence, decisions, questions)
- `/analysis-reflection` — Structured reflection to draw conclusions or branch hypotheses
- `/analysis-revision` — Guided revision workflow for addressing review comments
- `/catalog-register` — Step-by-step data source registration
- `/knowledge-extract` — Extract reusable, source-scoped domain knowledge from a concluded analysis
- `/data-lineage` — Track data transformations and export lineage diagrams (Mermaid)
- `/premortem` — Report-only pre-flight cost/risk evaluation of designs before expensive data access
- `/analysis-auto` — Guided autopilot: drives the pipeline, pausing only at genuine decisions

Skills support both English and Japanese trigger phrases.

## Analysis Workflow

```
/rq-problematization (problematize assumptions → research questions)  ← optional upstream
    ↓ (RQ Brief)
/analysis-framing (explore data, frame direction)
    ↓
/analysis-design (create hypothesis)
    ↓ ↘ /analysis-review (review the design) → /analysis-revision (address comments)
    ↓ ↘ /premortem (optional: cost/risk report before expensive data access)
/analysis-notebook (generate & run a marimo notebook from the methodology → record results)
    ↓ ↘ /data-lineage (optional: track transformations, export Mermaid)
/analysis-journal (record reasoning during analysis)
    ↓
/analysis-reflection (reflect → conclude or branch)
    ↓ ↗ back to /analysis-framing (new direction needed)
/knowledge-extract (save reusable, source-scoped knowledge)
```

Skills are **invoked explicitly** (`/command`) by default and the flow is **interactive**. The
actual analysis is run by `/analysis-notebook`, which generates a marimo notebook from the
design's `methodology`, executes it, and records the results to the journal
(`uv add "insight-blueprint-lineage[notebook]"` for the runtime deps).

**Guided autopilot.** `/analysis-auto` drives the whole pipeline for you — auto-advancing the
low-friction steps and **pausing only at genuine decisions**: confirming the hypothesis,
registering a data source, a `HARD_BLOCK`/`HIGH` premortem, a notebook that would need
out-of-allowlist packages or external communication beyond the declared source, and the
conclusion. It is opt-in and still interactive — not an unattended pipeline. The individual
skills stay explicit everywhere else. See
[ADR-0005](docs/adr/0005-selective-autonomous-chaining.md).

`/catalog-register` sits upstream (register a data source before you frame against it);
`/knowledge-extract` sits downstream (harvest what a concluded analysis taught you about that source).

Each design has an `analysis_intent` field (`exploratory`, `confirmatory`, or `mixed`).
The Insight Journal (`.insight/designs/{id}_journal.yaml`) tracks your reasoning with event
types mapped to the Narrative Scaffolding framework (Huang+ IUI 2026).

## Designs, status & review

There is no web UI — everything is skill-driven over `.insight/` YAML:

- **Status transitions** are performed by the skills, not by hand. `/analysis-reflection`
  proposes the terminal transition (e.g. `analyzing → supported`) and runs it via
  `design_io transition`; the pre-write hook enforces the allowed transitions.
- **Review** is a producer/consumer pair (no dashboard): `/analysis-review` critiques a
  design and records a review batch under `.insight/designs/{id}_reviews.yaml` (via
  `design_io review-batch`), setting the design to `revision_requested` or `analyzing`.
  `/analysis-revision` then consumes a `revision_requested` batch, walking you through each
  comment — tracking per-comment progress in `.insight/designs/{id}_revision.yaml` — and
  re-submitting for review.

## Capturing knowledge (`/knowledge-extract`)

When an analysis concludes, `/knowledge-extract` reads its journal/reflection/review and
proposes **source-scoped** knowledge entries (a caution, a definition, a methodology note),
which — after you confirm — are persisted to the catalog:

```bash
echo '{"entries": [
  {"key": "pop-null-pre-2019", "title": "population null before 2019",
   "content": "population is null before 2019; start time series at 2019.",
   "category": "caution", "importance": "high", "affects_columns": ["population"]}
]}' | catalog_io add-knowledge --id <source_id>
```

`category` is an open string (conventional values: `methodology` / `caution` / `definition` /
`context`). Analytical conclusions stay in the reflection, not the catalog.

## Pre-flight Risk Evaluation (`/premortem`)

`/premortem` evaluates designs for cost/risk before expensive data access and prints a risk
report (`HARD_BLOCK` / `HIGH` / `MEDIUM` / `LOW` / `SKIP`). It is **report-only** — it issues
no tokens and writes nothing; it advises. It exits non-zero when any design is
`HARD_BLOCK`/`HIGH`, so you can gate a script on it if you want.

## Development

Requires **Python 3.11+** and **uv**.

```bash
git clone https://github.com/etoyama/insight-blueprint-skills.git
cd insight-blueprint-skills
uv sync --all-extras

# Run lint + typecheck + test
uv run poe all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, code style, and PRs.
Contributor/architecture docs: [CLAUDE.md](CLAUDE.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/PRD.md](docs/PRD.md).

### Tech Stack

| Tool | Purpose |
|------|---------|
| **uv** | Package management |
| **ruff** | Linting and formatting |
| **ty** | Type checking |
| **pytest** | Testing |
| **marimo** | Notebooks & lineage |

## Support

If you find this project useful, consider buying me a coffee.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/etoyama)

## License

MIT
