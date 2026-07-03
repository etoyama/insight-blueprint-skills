---
name: knowledge-extract
version: "1.0.0"
description: |
  Extracts reusable, source-scoped domain knowledge from a concluded analysis and
  persists it to the data catalog. Claude reads the design's journal / reflection /
  review comments, proposes DomainKnowledgeEntry candidates, and — after user
  confirmation — writes them via catalog_io add-knowledge.
  Triggers: "知見を抽出", "ナレッジ登録", "knowledge extract", "カタログに知見",
  "この分析の学びを残す", "extract domain knowledge".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /knowledge-extract — Domain Knowledge Extraction (Claude-native)

Turns the learnings of a concluded analysis into **reusable, source-scoped**
domain knowledge in the catalog. Claude is the extractor: it reads the design's
analysis artifacts and proposes structured entries; the library only validates and
persists. Replaces the old regex-based `extract_domain_knowledge` (removed with the
MCP server in E4).

## When to Use
- An analysis has concluded (or been reviewed) and produced reusable facts about a
  data source (a caution, a definition, a methodology note, contextual background)
- You want future analyses on the same source to inherit those facts

## When NOT to Use
- Recording an analytical **conclusion / finding** — that stays in the Insight
  Journal / reflection (→ /analysis-reflection). Catalog knowledge is source-scoped,
  not a conclusions log.
- Registering a new data source or its schema (→ /catalog-register)
- Still investigating (→ /analysis-journal)

## Core Principle

**Source-scoped, not design-scoped.** A knowledge entry answers "what should anyone
know about *this data source*?" — e.g. "population column is null before 2019". It
must attach to a registered source (`catalog_io add-knowledge` rejects unknown
sources). Analytical conclusions ("hypothesis X is supported") are NOT knowledge —
they live in reflection.

## Workflow

### Step 1: Load the Analysis Artifacts

1. `uv run python -m skills._shared.design_io get --id {design_id}` — load the design
2. Read `.insight/designs/{design_id}_journal.yaml` (Read tool) — evidence, decisions
3. `uv run python -m skills._shared.design_io list-reviews --id {design_id}` — review comments (if any)
4. If nothing to read: "抽出元がない。まず /analysis-journal / /analysis-reflection で記録してから" → exit

### Step 2: Identify the Target Source

Knowledge is source-scoped, so decide which registered source each learning attaches to.

1. Infer candidate sources from the design's data references / methodology.
2. Confirm with the user: "この知見はどのデータソースに紐づく？"
3. Verify it is registered: `uv run python -m skills._shared.catalog_io get --id {source_id}`
   (empty → not registered → suggest /catalog-register first, or pick another source).

### Step 3: Draft Knowledge Candidates (Claude-native)

Read the artifacts and synthesize candidate entries. For each, decide:

| Field | How to fill |
|-------|-------------|
| `key` | short stable slug, unique per source (e.g. `pop-null-pre-2019`) — re-running upserts by this key |
| `title` | one-line label |
| `content` | the reusable fact, stated so it helps a *future* analyst of this source |
| `category` | open string (E5c). Prefer a conventional value — `methodology` / `caution` / `definition` / `context` — or a domain-specific one (`data-quality`, `regulatory`, …). **Never `finding`** (findings stay in reflection) |
| `importance` | `high` / `medium` (default) / `low` |
| `affects_columns` | column names this touches (optional) |
| `source` | provenance — set to the originating `design_id` |

Only extract facts about the **data source**. Skip anything that is really a
conclusion about the hypothesis — that belongs in reflection.

### Step 4: Confirm with the User

Present the candidates as a table (key / category / importance / content) and let the
user drop, edit, or add. Do not persist unconfirmed entries.

### Step 5: Persist via catalog_io

Pipe the confirmed entries to `add-knowledge` (upsert by `key`):

```bash
echo '{
  "entries": [
    {
      "key": "pop-null-pre-2019",
      "title": "人口は2019年以前が欠損",
      "content": "population 列は2019年以前が欠損。時系列分析では起点を2019に。",
      "category": "caution",
      "importance": "high",
      "affects_columns": ["population"],
      "source": "{design_id}"
    }
  ]
}' | uv run python -m skills._shared.catalog_io add-knowledge --id {source_id}
```

Show the returned container and confirm. Verify with
`catalog_io get-knowledge --id {source_id}`.

## catalog_io Reference

`python -m skills._shared.catalog_io <command>` (from project root):

| Command | Purpose | Input |
|---------|---------|-------|
| `get --id ID` | Confirm the source is registered | — |
| `add-knowledge --id ID` | Append/upsert knowledge entries (validates, atomic write) | stdin: `{entries:[{key,title,content,category,importance?,affects_columns?,source?}]}` |
| `get-knowledge --id ID [--category C]` | Read back knowledge | — |

Validation runs inside `catalog_io` (DomainKnowledgeEntry model) before writing;
invalid input exits non-zero with nothing written. Unknown source → error.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-reflection | → /knowledge-extract | Conclusion produced reusable source knowledge |
| /catalog-register | → /knowledge-extract | Source registered; now capture what's known about it |
| /knowledge-extract | → /analysis-reflection | The learning is really a conclusion, not source knowledge |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Knowledge content follows the user's language (usually Japanese).
