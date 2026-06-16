# insight-blueprint

[![PyPI](https://img.shields.io/pypi/v/insight-blueprint)](https://pypi.org/project/insight-blueprint/)
[![CI](https://github.com/etoyama/insight-blueprint/actions/workflows/ci.yml/badge.svg)](https://github.com/etoyama/insight-blueprint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/etoyama)

A Python MCP server for hypothesis-driven data analysis. Manage analysis designs, data catalogs, and review workflows through Claude Code or any MCP-compatible client.

## Installation

### Recommended: Claude Code Plugin

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

All options provide 8 analysis skills and auto-configure the MCP server. A WebUI dashboard opens automatically at http://127.0.0.1:3000.

> **Tip:** Option 3 loads the plugin for the current session only. Add a shell alias for convenience:
> ```bash
> alias claude-ib='claude --plugin-dir /path/to/insight-blueprint'
> ```

### Alternative: Direct Execution

```bash
# Start the server without plugin (zero-install)
uvx insight-blueprint --project /path/to/my-analysis

# Or install permanently
uv tool install insight-blueprint
insight-blueprint --project /path/to/my-analysis
```

### Updating

When a new version is published, run the following from within Claude Code to pull the latest plugin (auto-update is off by default for third-party marketplaces):

```bash
/plugin marketplace update insight-blueprint-marketplace
/plugin update insight-blueprint@insight-blueprint-marketplace
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.

### Optional: Python Package

For data-lineage tracking with `tracked_pipe` in your notebooks/scripts:

```bash
uv add insight-blueprint
```

This is optional but recommended for analysis pipeline transparency. MCP tools work without it.

## Features

### MCP Tools

insight-blueprint exposes 18 tools via the [Model Context Protocol](https://modelcontextprotocol.io/), allowing AI assistants to manage your analysis workflow:

| Category | Tools |
|----------|-------|
| **Analysis Design** | `create_analysis_design`, `update_analysis_design`, `get_analysis_design`, `list_analysis_designs` |
| **Data Catalog** | `add_catalog_entry`, `update_catalog_entry`, `get_table_schema`, `search_catalog` |
| **Domain Knowledge** | `get_domain_knowledge`, `extract_domain_knowledge`, `save_extracted_knowledge`, `suggest_knowledge_for_design`, `suggest_cautions` |
| **Review Workflow** | `transition_design_status`, `save_review_comment`, `save_review_batch`, `get_review_comments` |
| **Project** | `get_project_context` |

### WebUI Dashboard

A browser-based dashboard (http://127.0.0.1:3000) with two tabs:

- **Designs** -- Browse analysis designs, view details (overview + history), and track status transitions
- **Catalog** -- Search domain knowledge, browse data sources, and check cautions

### Bundled Skills

The plugin provides 10 analysis skills that are automatically available after installation:

- `/rq-problematization` -- Generate impactful research questions by problematizing the assumptions in prior research (upstream of framing)
- `/analysis-framing` -- Explore available data and existing analyses to frame a hypothesis direction
- `/analysis-design` -- Guided workflow for creating hypothesis documents
- `/analysis-journal` -- Record reasoning steps during analysis (observations, evidence, decisions, questions)
- `/analysis-reflection` -- Structured reflection to draw conclusions or branch hypotheses
- `/analysis-revision` -- Guided revision workflow for addressing review comments
- `/catalog-register` -- Step-by-step data source registration
- `/data-lineage` -- Track data transformations and export lineage diagrams (Mermaid)
- `/batch-analysis` -- Overnight batch execution of queued designs (headless notebooks, self-review, journal recording)
- `/premortem` -- Pre-flight risk evaluation of queued designs with approval token issuance (gates `/batch-analysis`)

Skills support both English and Japanese trigger phrases.

### Analysis Workflow

Skills chain together to support the full hypothesis-driven analysis lifecycle:

```
/rq-problematization (problematize assumptions → research questions)  ← optional upstream
    ↓ (RQ Brief)
/analysis-framing (explore data, frame direction)
    ↓
/analysis-design (create hypothesis)
    ↓ (interactive)          ↓ (batch)
/analysis-journal        /batch-analysis (overnight headless)
    ↓                        ↓
    ↓
/analysis-reflection (reflect → conclude or branch)      ← morning review
    ↓ ↗ back to /analysis-framing (new direction needed)
    ↕ WebUI review → /analysis-revision (address review comments)
/catalog-register (register findings as domain knowledge)
```

Each design has an `analysis_intent` field (`exploratory`, `confirmatory`, or `mixed`) to distinguish whether you're testing a specific hypothesis or exploring data for patterns. The Insight Journal (`.insight/designs/{id}_journal.yaml`) tracks your reasoning process with 8 event types mapped to the Narrative Scaffolding framework (Huang+ IUI 2026).

## Overnight Operation

Batch analysis runs overnight via a two-step workflow: risk evaluation
followed by headless execution.

### Workflow

```
/premortem --queued --yes --mode review
    ↓ (exit 0: token issued)
    ↓ (exit 2: HIGH detected, human triage needed)
/batch-analysis --approved-by TOKEN
    ↓
Morning review: summary.md + /analysis-reflection per design
```

### Automation Modes

| Mode | HIGH Risk Handling | Human Interaction |
|------|-------------------|-------------------|
| `manual` | Interactive prompt for every design | Required |
| `review` | Blocks on HIGH (exit 2), auto-approves LOW/MEDIUM | Only when HIGH detected |
| `auto` | Includes HIGH in approved set with warning | None |

Set the mode in `.insight/config.yaml` under `batch.automation` (default: `review`).

### Phased Rollout of `--approved-by`

The `--approved-by TOKEN` argument is introduced in two phases:

- **Phase A** (`batch.approved_by_required: false`): Omitting the flag prints a
  warning and runs in legacy mode. Existing workflows are not broken.
- **Phase B** (`batch.approved_by_required: true`): Omitting the flag causes
  exit 1. All batch runs must go through `/premortem` first.

Transition from Phase A to Phase B by setting `approved_by_required: true` in
`.insight/config.yaml` when your team is ready.

## CLI Options

```bash
insight-blueprint --project /path/to/project   # Specify project directory
insight-blueprint --no-browser                  # Suppress browser auto-open
insight-blueprint --version                     # Show version
insight-blueprint                               # Use current directory
```

## Team Server Mode

Multiple Claude Code instances can share a single insight-blueprint server via MCP SSE (Server-Sent Events).

### Server mode (WebUI + MCP SSE)

```bash
insight-blueprint --project /path/to/project --mode server --port 4000
```

Each Claude Code instance connects by adding to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "insight-blueprint": {
      "type": "sse",
      "url": "http://<host>:4000/mcp/sse"
    }
  }
}
```

### Headless mode (MCP SSE only, no WebUI)

```bash
insight-blueprint --project /path/to/project --mode headless --port 4000
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode full` | (default) | stdio MCP + WebUI on localhost:3000. Standard single-user mode |
| `--mode server` | - | HTTP MCP SSE + WebUI on the same port. For team/multi-client use |
| `--mode headless` | - | HTTP MCP SSE only (no WebUI). Lightweight deployment |
| `--host` | `0.0.0.0` | Bind address (server/headless mode only) |
| `--port` | `4000` | Listen port (server/headless mode only) |
| `--no-browser` | `false` | Suppress browser auto-open in full mode |

> **WARNING: No authentication.** Phase 1 does not include authentication.
> Run the server on a trusted network only, or bind to localhost with `--host 127.0.0.1`.

## Migration Guide (from v0.3.x)

If you previously used insight-blueprint without the plugin system, clean up the old skill copies:

```bash
# Remove old skill copies (now provided by the plugin)
rm -rf .claude/skills/analysis-design .claude/skills/analysis-framing \
       .claude/skills/analysis-journal .claude/skills/analysis-reflection \
       .claude/skills/analysis-revision .claude/skills/catalog-register \
       .claude/skills/data-lineage

# Remove old rule copies (now integrated into skill definitions)
rm -rf .claude/rules/analysis-workflow.md .claude/rules/catalog-workflow.md \
       .claude/rules/insight-yaml.md .claude/rules/extension-policy.md
```

The plugin's skills take precedence, so old copies won't cause errors but should be removed to avoid confusion.

## Development

Requires **Python 3.11+**, **uv**, and **Node.js** (for frontend build).

```bash
git clone https://github.com/etoyama/insight-blueprint.git
cd insight-blueprint
uv sync --all-extras

# Build frontend assets (required for WebUI)
poe build-frontend

# Run lint + typecheck + test
poe all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code style, and how to submit pull requests.

### Tech Stack

| Tool | Purpose |
|------|---------|
| **uv** | Package management |
| **ruff** | Linting and formatting |
| **ty** | Type checking |
| **pytest** | Testing |
| **FastMCP** | MCP server framework |
| **FastAPI** | WebUI backend |

## Support

If you find this project useful, consider buying me a coffee.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/etoyama)

## License

MIT
