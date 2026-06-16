---
name: analysis-framing
version: "1.0.0"
description: |
  Explores existing data and analyses to help frame a hypothesis.
  Triggers: "framing", "何を分析する", "分析テーマ", "仮説を考えたい",
  "データを探して", "既存分析を確認", "analysis framing".
disable-model-invocation: true
argument-hint: "[theme]"
---

# /analysis-framing --- Analysis Framing Explorer

Explores the `.insight/` directory to discover available data, existing analyses,
and domain knowledge, helping the user frame a well-grounded hypothesis direction.
Does NOT create hypotheses --- that is `/analysis-design`'s responsibility.

## When to Use
- Vague analysis theme, need to explore available data
- Want to discover what data and existing analyses are available
- Starting a new analysis direction, need grounding in existing context

## When NOT to Use
- Hypothesis is already clear --- use `/analysis-design`
- Recording reasoning during analysis --- use `/analysis-journal`
- Structured reflection on completed analysis --- use `/analysis-reflection`

## Workflow

### Step 1: Receive Theme

Accept the analysis theme from `$ARGUMENTS` or ask the user for one.

- If `$ARGUMENTS` is provided, use it as the theme
- If the theme is vague or overly broad (e.g., "データ分析", "社会問題"):
  - Present 2-3 candidate directions based on available data in `.insight/catalog/`
  - Ask the user to select or refine a direction before proceeding
  - Do NOT depend on development-partner for theme narrowing --- handle it independently
- If forwarded from development-partner: accept the framing context from the conversation and build upon it
- If an **RQ Brief** is present in the conversation (forwarded from `/rq-problematization`):
  use its `テーマ` as the theme and its `検証の方向性` as the seed direction. The research
  questions are theory-driven and not yet grounded — your job is to ground them in
  available data. Carry the central assumption forward into the Direction Dialogue (Step 4).
- If `.insight/` directory does not exist: inform the user that the project is not initialized and guide them to run `insight-blueprint init`. Stop the workflow here.

### Step 2: Domain Exploration (Agentic Search)

Explore `.insight/` directories to gather theme-relevant information.
Do NOT use MCP tools. Use only Glob, Read, and Grep via Agent tool.

**Execution method**: Delegate exploration to an Agent tool (subagent_type: "Explore").
Loading all `.insight/` YAML files into the main context would cause token
consumption to spike and degrade the quality of the subsequent dialogue (Steps 3-5).
Pass the theme and the exploration instructions below to the subagent, and have it
return a structured summary in the Data Map format (Step 3) to the main context.

#### 2a: Design Exploration

1. Glob `.insight/designs/*_hypothesis.yaml` to list all design files
2. Read each file and judge relevance to the theme:
   - If relevant: record title, hypothesis_statement, status, methodology, conclusion
   - If a journal exists (`*_journal.yaml`), check key findings
3. Capture parent/child relationships among related designs

#### 2b: Catalog Exploration

1. Glob `.insight/catalog/*.yaml` to list all catalog entries
2. Read each entry and identify data sources usable for the theme:
   - Check source name, column definitions, period, granularity
   - Also check the tags field

#### 2c: Knowledge Exploration

1. Glob `.insight/rules/*.yaml` to list domain knowledge entries
2. Read each entry and identify findings/cautions relevant to the theme:
   - Check category (caution / finding / context)
   - Cautions are especially important (data constraints, pitfalls)

#### 2d: Cross-search

Run Grep across all of `.insight/` with keywords derived from the theme
(synonyms, broader terms, narrower terms) to catch files missed in 2a-2c.

#### Scope Control Guidelines

- **Glob first, Read selectively**: List files with Glob first, then filter by filename/path relevance before Read. Do NOT Read all files unconditionally.
- **Per-directory Read cap**: Read at most 20 files per directory (designs/, catalog/, rules/). If more exist, prioritize by filename relevance and timestamp (newer first).
- **Staged reading**: On first pass, Read only the header fields (title, hypothesis_statement, source_id, name, etc.). Read full content only for files judged to be relevant.
- **If too many relevant files found**: When more than 20 relevant files are identified, ask the user to narrow the theme before continuing.

#### Subagent Return

Return exploration results as a structured summary in the Data Map format (Step 3).
Do NOT return raw file contents. Return a semantically grouped summary with
relevance judgments applied.

### Step 3: Present Data Map

Present the exploration results in the following structured format:

```
-- Data Map: {theme} --

利用可能データ:
  - {source_name} ({source_id})
    カラム: {key_columns}  期間: {period}  粒度: {granularity}
  - ...

既存分析:
  - {design_id}: {title} [{status}]
    手法: {methodology}  結論: {conclusion_summary}
  - ...

関連知識:
  - [{category}] {content_summary}
    出典: {source_design_id or manual}
  - ...

ギャップ:
  - {gap_description}
  - ...
```

If `.insight/catalog/` is empty or has no relevant data:
- Clearly report that no data sources were found
- Suggest `/catalog-register` to register new data sources

### Step 4: Direction Dialogue

Discuss with the user to narrow the hypothesis direction:
- New angles building on conclusions of existing analyses
- Hypothesis directions verifiable with available data
- How to fill missing data (guide toward `/catalog-register`)

Do NOT create a hypothesis statement (`hypothesis_statement`).
The framing skill's responsibility ends at "proceed to analysis-design in this direction."

### Step 5: Output Framing Brief

When a direction is agreed upon, output the following structured text **verbatim**
(copy the heading hierarchy exactly). analysis-design will detect this format
from the conversation context and pre-populate draft values.

````markdown
## Framing Brief

### テーマ
{theme_one_liner}

### 利用可能データ
- {source_name} ({source_id}): {key_columns}, {period}, {granularity}

### 既存分析
- {design_id}: {title} [{status}] --- {conclusion_summary}

### ギャップ
- {gap_description}

### 推奨方向
- 仮説の方向性: {direction_description}
- theme_id: {suggested_theme_id}
- parent_id: {suggested_parent_id or "なし"}
- analysis_intent: {exploratory | confirmatory | mixed}
- 推奨手法: {methodology_suggestion}
````

After outputting the Framing Brief, suggest:
"仮説を設計するなら `/analysis-design`"

## Chaining

| From | To | When |
|------|-----|------|
| /development-partner* | → /analysis-framing | 分析テーマが出て、ドメイン接地が必要: "データと既存分析を探索するなら /analysis-framing" |
| /rq-problematization | → /analysis-framing | RQ が出てデータ接地が必要（RQ Brief 付き）: "RQ をデータに接地して検証枠組みにするなら /analysis-framing" |
| /analysis-design | → /analysis-framing | データ不足で仮説の方向を再検討: "データを探し直すなら /analysis-framing" |
| /analysis-reflection | → /analysis-framing | 新仮説が必要だがデータ・方向の探索が先: "新しい角度を探すなら /analysis-framing" |
| /catalog-register | → /analysis-framing | データ登録完了、フレーミングに戻る: "フレーミングに戻るなら /analysis-framing" |
| /analysis-framing | → /analysis-design | 仮説の方向性が定まった（Framing Brief 付き）: "仮説を設計するなら /analysis-design" |
| /analysis-framing | → /catalog-register | 必要なデータが未登録: "データを登録するなら /catalog-register" |
| /analysis-framing | → /development-partner* | テーマが分析ドメインを超えて漠然: "問題を整理するなら /development-partner" |

\* = 外部スキル（development-deck）。存在時のみ表示する。存在しない場合この行は Chaining セクションに含めない。

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Theme and analysis content follows the user's language (usually Japanese).
