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

### Optional: Python package (for lineage)

For data-lineage tracking with `tracked_pipe` in your notebooks/scripts, install the
`insight-blueprint-lineage` package (the import name stays `insight_blueprint`):

```bash
uv add insight-blueprint-lineage
```

This is optional but recommended for analysis-pipeline transparency. The skills themselves
work without it.

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## How it works

- **Skills** (`skills/`) drive the workflow and read/write `.insight/` YAML via small
  server-free helpers (`skills/_shared/design_io.py`, `catalog_io.py`).
- **Validation** is centralized in `src/insight_blueprint/validate.py` (Pydantic schema +
  state-transition guard). A **pre-write hook** (`.claude/hooks/validate-design.py`) calls
  the same library to block invalid writes to `*_hypothesis.yaml`.
- **Lineage** (`src/insight_blueprint/lineage/`) records DataFrame transformations and
  exports Mermaid diagrams.

## Skills

- `/rq-problematization` — Generate impactful research questions by problematizing prior-research assumptions (upstream of framing)
- `/analysis-framing` — Explore available data and existing analyses to frame a direction
- `/analysis-design` — Guided creation of hypothesis design documents
- `/analysis-journal` — Record reasoning steps during analysis (observations, evidence, decisions, questions)
- `/analysis-reflection` — Structured reflection to draw conclusions or branch hypotheses
- `/analysis-revision` — Guided revision workflow for addressing review comments
- `/catalog-register` — Step-by-step data source registration
- `/knowledge-extract` — Extract reusable, source-scoped domain knowledge from a concluded analysis
- `/data-lineage` — Track data transformations and export lineage diagrams (Mermaid)
- `/premortem` — Report-only pre-flight cost/risk evaluation of designs before expensive data access

Skills support both English and Japanese trigger phrases.

## Analysis Workflow

```
/rq-problematization (problematize assumptions → research questions)  ← optional upstream
    ↓ (RQ Brief)
/analysis-framing (explore data, frame direction)
    ↓
/analysis-design (create hypothesis)
    ↓
/analysis-journal (record reasoning during analysis)
    ↓
/analysis-reflection (reflect → conclude or branch)
    ↓ ↗ back to /analysis-framing (new direction needed)
    ↕ review → /analysis-revision (address review comments)
/knowledge-extract (save reusable, source-scoped knowledge)
```

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
- **Review** is recorded as review batches under `.insight/designs/{id}_reviews.yaml`
  (written by `design_io append_review_batch`, read by `list-reviews`). `/analysis-revision`
  then walks you through addressing each comment — tracking per-comment progress in
  `.insight/designs/{id}_revision.yaml` — and re-submitting for review.

## Capturing knowledge (`/knowledge-extract`)

When an analysis concludes, `/knowledge-extract` reads its journal/reflection/review and
proposes **source-scoped** knowledge entries (a caution, a definition, a methodology note),
which — after you confirm — are persisted to the catalog:

```bash
echo '{"entries": [
  {"key": "pop-null-pre-2019", "title": "population null before 2019",
   "content": "population is null before 2019; start time series at 2019.",
   "category": "caution", "importance": "high", "affects_columns": ["population"]}
]}' | uv run python -m skills._shared.catalog_io add-knowledge --id <source_id>
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
