# insight-blueprint

[![PyPI](https://img.shields.io/pypi/v/insight-blueprint)](https://pypi.org/project/insight-blueprint/)
[![CI](https://github.com/etoyama/insight-blueprint/actions/workflows/ci.yml/badge.svg)](https://github.com/etoyama/insight-blueprint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/etoyama)

A **Claude Code skills plugin** for hypothesis-driven EDA. Analysis designs, journals,
reviews, and the data catalog live as YAML under `.insight/`; skills read and write them
directly. Integrity is enforced by an **embedded validation library** (`validate.py`) plus
a pre-write hook — **no server, no daemon, no SQLite**. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRD.md](docs/PRD.md).

## Installation

### Claude Code Plugin (recommended)

```bash
# Option 1: From the official marketplace
claude plugin install etoyama/insight-blueprint

# Option 2: Via custom marketplace (permanent install)
/plugin marketplace add etoyama/insight-blueprint
/plugin install insight-blueprint@insight-blueprint-marketplace

# Option 3: From a local clone (session only)
git clone https://github.com/etoyama/insight-blueprint.git
claude --plugin-dir ./insight-blueprint
```

All options install the analysis skills. There is nothing to launch — skills operate on
`.insight/` YAML directly.

> **Tip:** Option 3 loads the plugin for the current session only. Add a shell alias:
> ```bash
> alias claude-ib='claude --plugin-dir /path/to/insight-blueprint'
> ```

### Optional: Python package (for lineage)

For data-lineage tracking with `tracked_pipe` in your notebooks/scripts:

```bash
uv add insight-blueprint
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
- `/data-lineage` — Track data transformations and export lineage diagrams (Mermaid)
- `/premortem` — Pre-flight cost/risk evaluation of queued designs with approval-token issuance

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
/catalog-register (register findings as domain knowledge)
```

Each design has an `analysis_intent` field (`exploratory`, `confirmatory`, or `mixed`).
The Insight Journal (`.insight/designs/{id}_journal.yaml`) tracks your reasoning with event
types mapped to the Narrative Scaffolding framework (Huang+ IUI 2026).

## Pre-flight Risk Evaluation (`/premortem`)

`/premortem` evaluates queued designs for cost/risk before expensive data access and issues
an approval token. It runs in `manual` / `review` / `auto` modes (risk-gating strength).

## Development

Requires **Python 3.11+** and **uv**.

```bash
git clone https://github.com/etoyama/insight-blueprint.git
cd insight-blueprint
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
