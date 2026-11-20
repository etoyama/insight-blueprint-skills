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
  - Present 2-3 candidate directions based on the data sources `catalog_io list` returns
  - Ask the user to select or refine a direction before proceeding
  - Do NOT depend on development-partner for theme narrowing --- handle it independently
- If forwarded from development-partner: accept the framing context from the conversation and build upon it
- If an **RQ Brief** is present in the conversation (forwarded from `/rq-problematization`):
  use its `テーマ` as the theme and its `検証の方向性` as the seed direction. The research
  questions are theory-driven and not yet grounded — your job is to ground them in
  available data. Carry the central assumption forward into the Direction Dialogue (Step 4).
- If `.insight/` does not exist yet, that's fine — it holds nothing to explore, so tell the user
  it's empty and proceed to frame from the conversation/theme. The `.insight/` directory tree is
  created automatically the first time a skill writes to it (via the `design_io`/`catalog_io`
  wrappers); there is no separate init step.

### Step 2: Domain Exploration (Agentic Search)

Explore `.insight/` to gather theme-relevant information.
Do NOT use MCP tools. Use only Glob, Read, and Grep via Agent tool, plus `catalog_io list`
for the data sources (2b).

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

1. Run `catalog_io list` to get every registered data source. It prints each source
   without its `connection` (ADR-0018); the paths, hosts and project ids in `connection`
   are for `/analysis-notebook` alone, so never open the source YAML files instead
   ([ADR-0022](../../docs/adr/0022-connection-reaches-only-the-notebook.md)).
2. Identify the data sources usable for the theme:
   - Check source name, column definitions (`schema_info`), period, granularity
   - Also check the tags field

#### 2c: Knowledge Exploration

1. Glob `.insight/rules/*.yaml` to list domain knowledge entries
2. Read each entry and identify findings/cautions relevant to the theme:
   - Check category (caution / finding / context)
   - Cautions are especially important (data constraints, pitfalls)

#### 2d: Cross-search

Run Grep across `.insight/designs/`, `.insight/catalog/knowledge/` and `.insight/rules/`
with keywords derived from the theme (synonyms, broader terms, narrower terms) to catch
files missed in 2a-2c. Data sources come from 2b only: a Grep over the source YAML prints
`connection` lines.

#### Scope Control Guidelines

- **Glob first, Read selectively**: List files with Glob first, then filter by filename/path relevance before Read. Do NOT Read all files unconditionally.
- **Per-directory Read cap**: Read at most 20 files per directory (designs/, catalog/knowledge/, rules/). If more exist, prioritize by filename relevance and timestamp (newer first).
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

If `catalog_io list` returns no sources or no relevant data:
- Clearly report that no data sources were found
- Suggest `/catalog-register` to register new data sources

### Step 4: Direction Dialogue

Discuss with the user to narrow the hypothesis direction:
- New angles building on conclusions of existing analyses
- Hypothesis directions verifiable with available data
- How to fill missing data (guide toward `/catalog-register`)

The agreed direction is kept as the theme's **question tree**
(`.insight/themes/{theme_id}_tree.yaml`): the root question, its aim, and the first-level
nodes under it. The analyst settles them at two KEEP gates (4a, 4b). You draft, the analyst decides.

Do NOT create a hypothesis statement (`hypothesis_statement`).
The framing skill's responsibility ends at "proceed to analysis-design on this node."

#### 4a: Root question and aim (KEEP gate)

This is a KEEP gate. Settle three things with the analyst and wait for their answer:

1. **`theme_id`** — it names the tree file and prefixes every design id, so it must match
   `[A-Z][A-Z0-9]*`. Propose the theme of the related designs in the Data Map, or a new one.
   Then run `tree_io get --theme {theme_id}`. If it prints a tree, go to 4c instead of 4b.
2. **Root question** — the one question the whole theme answers, as a single sentence.
3. **Aim** — what the root question is for. It has one of two kinds:

| `kind` | Fields (both required) | Meaning |
|---|---|---|
| `business` | `decision_maker`, `decision` | Who decides what on the strength of the answer. Write a role or a team, not a personal name |
| `research` | `audience`, `claim_scope` | Who reads the claim, and how far it reaches (population, period, conditions) |

Take the kind from the conversation and confirm it. A theme that came from
`/rq-problematization` is `research`, and its root question is the research question the
analyst chooses to test.
If the RQ Brief does not state the audience, ask the analyst who the audience is before you go on.
Take `claim_scope` from the analyst as well; propose a draft from the research questions if that helps.

Never fill a field of the aim with a guess, an empty string, or a placeholder such as "未定":
`tree_io` rejects a half-filled aim, and a placeholder would later read as a real decision.
If the analyst cannot name the aim yet, stop here and say that the tree needs it.

#### 4b: First-level nodes and the first node to investigate (KEEP gate)

Draft the first-level nodes: the questions that sit directly under the root question.
Each node has two parts:

- `question` — what to find out, as a question. Not a hypothesis and not a method.
- `contribution` — how answering it moves the judgment on the root question.
  A node whose contribution you cannot state does not belong under this root.

Ground the draft in the Data Map: say for each node which sources could answer it, and name
the gaps. Present the nodes with a recommended order and the reason for it. This is a KEEP
gate, so ask the analyst two things and wait: whether the nodes are right (add, drop, reword), and which node
to investigate first, with their reason. Keep the reason in the analyst's words.

The second level may stay empty. Deeper nodes are added when the analysis raises them.

#### 4c: When the theme already has a tree

One theme has one tree. When `tree_io get` printed a tree in 4a, the theme already has one, so
show it (root question, aim, nodes, decisions) and ask what this run changes.

- **New nodes** — draft and confirm them as in 4b, then add them with `tree_io add-node` (5a).
- **The node to design next** — the analyst picks it; it goes into the Framing Brief (5b).
  Record a `start` decision only if the tree has no decision yet (an earlier run stopped
  halfway). `start` is the first choice, so a tree never gets a second one.
- **The root question or the aim** — this skill is the only place they change, and it is a
  KEEP gate. Show the old and the new root question and aim side by side, and ask whether
  the root revision goes up. Send the analyst's answer as `bump`:

```bash
echo '{"question": "取り置き期限を延ばす試行を、分館も含めて始めるか", "bump": true, "reason": "分館も対象に入り、決める範囲が変わった"}' | tree_io revise-root --theme LIB
```

`"bump": true` appends a root revision and needs the analyst's `reason`. From then on the
earlier answers are shown as answers to the previous root.
`"bump": false` rewrites the current revision in place, so it is only for a rewording that keeps the meaning.
Send `aim` in the same payload when the aim changes.

Never choose `bump` yourself and never default it. A change of meaning always raises the
revision: the question asks something else, another role decides, the decision differs, or
the audience or the claim scope moves. If the analyst answers "no bump" to a change you read
as one of these, tell them which part changed and that earlier answers would silently read
as answers to the new root, then ask once more. Their second answer stands.

### Step 5: Output Framing Brief

#### 5a: Write the question tree

Write the tree with `tree_io` (on PATH; JSON on stdin, JSON on stdout; it validates before
every write). Never create or change `.insight/themes/*_tree.yaml` with the Write or Edit tool.
Run the commands in this order, one `add-node` per first-level node:

```bash
echo '{"theme_id": "LIB",
  "question": "取り置き期限を延ばす試行をするか",
  "aim": {"kind": "business", "decision_maker": "図書館員", "decision": "取り置き期限を延ばす試行を始めるか"}}' | tree_io create

echo '{"question": "期限切れを一貫して数えられるか",
  "parent_question_id": "LIB-Q01",
  "contribution": "予約取消が混ざると、延長で改善しうる件数が変わる"}' | tree_io add-node --theme LIB

echo '{"kind": "start", "node_id": "LIB-Q02",
  "reason": "取消が混ざると延長で改善しうる件数が変わるため"}' | tree_io decide --theme LIB
```

- `create` writes the root question as `{theme_id}-Q01` with the first root revision.
  A research aim is `{"kind": "research", "audience": "...", "claim_scope": "..."}`.
- `add-node` prints the node it wrote. Its `id` (`{theme_id}-Q{nn}`) is the id to use from here on.
- `decide` records the first node to investigate and the analyst's reason (4b).

A command that exits non-zero wrote nothing: read stderr, fix the payload and run that
command again. Do not output the Framing Brief until `decide` has succeeded. If the run
stops between commands, the next run finds the tree in 4a and continues from 4c.

#### 5b: Framing Brief

Output the following structured text **verbatim**
(copy the heading hierarchy exactly). analysis-design will detect this format
from the conversation context and pre-populate draft values.
`theme_id` is the theme of the tree, and `node_id` is the `{theme_id}-Q{nn}` id that
`tree_io` printed in 5a for the node to design next. `/analysis-design` links the design it
creates to that node.

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
- theme_id: {theme_id}
- node_id: {node_id}
- 論点: {node_question}
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
