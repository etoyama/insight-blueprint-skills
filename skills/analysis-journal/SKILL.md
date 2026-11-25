---
name: analysis-journal
version: "1.2.0"
description: |
  Records reasoning steps during hypothesis-driven analysis as an Insight Journal.
  Supports observation logging, evidence tracking, method decisions, question management,
  and hypothesis branching. Journal data is stored as YAML alongside design files.
  Triggers: "journal", "記録して", "ジャーナル", "推論を残す", "分析ログ",
  "分析の経緯", "なぜこの結論に至ったか記録", "evidence log".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-journal — Insight Journal Manager

Records the reasoning process behind an analysis design as a structured
event journal. Each event captures a discrete reasoning step — observation,
hypothesis, evidence, question, decision, reflection, conclusion, or branch.

Based on Narrative Scaffolding (Huang+ IUI 2026) and Sensemaking Loop
(Pirolli & Card) frameworks.

## When to Use
- During active analysis: recording what you observed, decided, or discovered
- When choosing an analysis method or package (e.g., "CausalImpact を使う")
- When a new question arises during investigation
- When branching to an alternative hypothesis

## When NOT to Use
- Creating a new design from scratch (→ /analysis-design)
- Structured reflection and conclusion (→ /analysis-reflection)
- Registering data sources or knowledge (→ /catalog-register)

## Workflow

### Step 1: Identify Target Design

If `$ARGUMENTS` contains a design ID (e.g., "FP-H01"), use it directly.
Otherwise, run `design_io list --status analyzing`
and ask the user to select.

Validate with `design_io get --id {design_id}`
(empty `{}` output means not found).

### Step 2: Load or Initialize Journal

Read `.insight/designs/{design_id}_journal.yaml` using the Read tool.
- If exists: load and show summary (event count, last 3 events, open questions)
- If not exists: create with initial structure using the Write tool:

```yaml
metadata:
  design_id: "{design_id}"
  created_at: "{now in ISO 8601 JST}"
  updated_at: "{now in ISO 8601 JST}"
events: []
```

### Step 3: Record Events (Interactive Loop)

Listen to user input and classify into InsightType:

| User says... | InsightType | Example content |
|---|---|---|
| データを見たら〜 / 〜が見えた / 〜に気づいた | `observe` | "2026年1月以降、売上が前年比15%低下" |
| 〜だと思う / 仮説: / 〜が原因では | `hypothesize` | "価格改定（+8%）が売上低下の主因" |
| 〜で確認した / データが示す / 〜のエビデンス | `evidence` | "回帰分析でp<0.01の有意な負の相関" |
| 〜が気になる / 〜を調べたい / なぜ〜 | `question` | "季節要因を除外できているか？" |
| 〜さんに聞いたら / 担当者によると / ヒアリングで | `hearing` | "金曜に確保した本は月曜にまとめて通知している（予約担当）" |
| 〜を使う / 〜で分析する / 手法: | `decide` | "CausalImpact で因果効果を推定する" |
| 振り返ると / 見直すと / 反省点 | `reflect` | "初期の相関分析では交絡が未考慮だった" |
| 結論: / まとめると / 〜と言える | `conclude` | "価格改定は売上低下の主因と確認" |
| 別の仮説 / 分岐したい / fork | `branch` | → Step 4 (Branch Workflow) |

For each event, construct and append to the journal YAML:

```yaml
- id: "{design_id}-E{nn:02d}"   # Sequential within journal
  type: "{insight_type}"
  content: "{user's description}"
  evidence_refs: []               # Ask: "関連するデータソースID or ナレッジIDはある？"
  parent_event_id: null           # Ask: "どのイベントから派生した？" (show recent events)
  metadata: {}                    # Type-specific (see Metadata Convention below)
  created_at: "{now in ISO 8601 JST}"
```

Update `metadata.updated_at` in journal file header.

**Efficiency rule**: Don't ask for `evidence_refs` and `parent_event_id` on every event.
Ask only when the user's statement implies a connection. Default to empty/null.

### Step 4: Branch Workflow

When user wants to branch to an alternative hypothesis:

1. Ask for: new `title`, new `hypothesis_statement`, optional `hypothesis_background`
2. Create the child design via design_io (inherits parent's `theme_id`; `methodology`
   is required — carry over the source's or ask the user):
   ```bash
   echo '{
     "title": "<new_title>",
     "hypothesis_statement": "<new_hypothesis>",
     "hypothesis_background": "<source.hypothesis_background if not provided>",
     "parent_id": "<source_design_id>",
     "theme_id": "<source.theme_id>",
     "methodology": {"method": "<carry over or ask>"}
   }' | design_io create
   ```
3. Link the derived design to the question tree, with the `id` that `design_io create`
   returned:
   ```bash
   tree_io link-derived --theme LIB --design LIB-H02
   ```
   - `--theme` is the source's `theme_id`.
   - It links the design to every node its source is linked to: a derived design is another
     hypothesis for the same question. `node_ids` in the output are those nodes. Tell the
     analyst which nodes the design now sits on. Do not ask which node to link.
   - An empty `node_ids` means the source is on no node, or the theme has no tree. Nothing
     was linked; go on. Say that the design is on no node of a question tree and that
     `/analysis-framing {theme_id}` can place it.
   - If it exits non-zero, show the error. The design stays as written; do not create it
     again, and go on with step 4.
   - Never run `tree_io link` or `tree_io add-node` here, and never write the tree file. A
     derived design that answers another question is placed by `/analysis-framing`.
4. Record `branch` event in source journal:
   ```yaml
   - id: "{source_id}-E{nn}"
     type: branch
     content: "分岐: {new_design_id} — {new_title}"
     metadata:
       new_design_id: "{new_design_id}"
       reason: "{why branching}"
   ```
5. Initialize new journal with `hypothesize` event:
   ```yaml
   metadata:
     design_id: "{new_design_id}"
     created_at: "{now}"
     updated_at: "{now}"
   events:
     - id: "{new_id}-E01"
       type: hypothesize
       content: "{new_hypothesis_statement}"
       metadata:
         forked_from: "{source_design_id}"
       created_at: "{now}"
   ```
6. Show: "分岐完了。{new_design_id} のジャーナルを開始した。/analysis-journal {new_design_id} で続けられる"

### Step 5: Show Summary on Exit

When user is done recording, show:

```
── Journal Summary: {design_id} ──
Phase: {inferred_phase}
Events: {total} ({observe}obs / {hypothesize}hyp / {evidence}evi / {hearing}hear / {question}q / {decide}dec / {reflect}ref / {conclude}con)
Open questions: {count}
  - {question_content} ({event_id})
Branches: {list of child design IDs}
Latest decision: {method} ({package})

Next: /analysis-reflection {design_id} で振り返りと結論導出
```

## InsightType Convention

| type | When to use | metadata fields |
|------|-------------|-----------------|
| `observe` | Raw data observation, pattern noticed | — |
| `hypothesize` | Hypothesis formed or refined | `{forked_from?: design_id}` |
| `evidence` | Evidence found from data analysis | `{direction?: "supports" \| "contradicts"}` — the lean against `hypothesis_statement`; an exploration's evidence has no `direction` |
| `hearing` | What a person answered when asked | `{answered_by: str, answered_at: "YYYY-MM-DD", ask?: str, node_id?: str}` |
| `question` | New question or uncertainty raised | `{priority?: "high" \| "medium" \| "low"}` |
| `decide` | Method, tool, or approach chosen | `{method: str, package?: str, reason?: str}` |

> **methodology への昇格**: decide イベントで記録した method/package は、analysis-design の methodology フィールドに昇格できる。`design_io update --id {design_id}` に `{"methodology": {method, package, reason}}` を渡す。

| `reflect` | Meta-level thinking about the analysis | — |
| `conclude` | Conclusion drawn from evidence | `{resolves?: event_id \| [event_id]}` |
| `branch` | Fork to alternative hypothesis | `{new_design_id: str, reason?: str}` |

> **direction**: `direction` says whether the evidence supports or contradicts the design's hypothesis (`hypothesis_statement`), so it exists only for a design that holds one. An exploration answers its question without an expectation, so leave `direction` out of its evidence ([ADR-0050](../../docs/adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)). A guess formed during an exploration is a `hypothesize` event, not a `direction`: record the guess in its own words, and test it with a confirmation later.

> **hearing**: a `hearing` event is what a person said, not an `observe` of the data and not `evidence` from an analysis. Ask who answered and when, and keep the answer in their words. `tree_io copy-hearing` writes one when a design is made on a question node whose next candidate holds a heard answer; it adds `ask` and `node_id` ([ADR-0028](../../docs/adr/0028-hearing-is-its-own-journal-event.md)).

## Phase Inference (Derived, Not Stored)

The current phase is inferred from the latest event type:

| Latest event type | Inferred phase |
|---|---|
| `observe`, `hypothesize` | Narrative Development |
| `evidence`, `hearing`, `question`, `decide` | Investigation |
| `reflect` | Reflection |
| `conclude`, `branch` | Integration |

## Journal File Location

`.insight/designs/{design_id}_journal.yaml`

This file is skill-managed data (see the YAML Format Reference in analysis-design
SKILL.md). `design_io` exposes `load_journal` / `write_journal` thin wrappers, but
direct Read/Write of this file is also fine.

## Sibling/Tree Queries

List designs via `design_io list` (JSON), then filter by `parent_id` / `theme_id`:
```
designs = json(`design_io list`)          # list[dict]
siblings = [d for d in designs if d["parent_id"] == target["parent_id"] and d["id"] != target["id"]]
roots = [d for d in designs if d["parent_id"] is None]
# Recursively build children from parent_id references
```

## Open Questions (Inquiry Board)

A `question` event is considered **open** if no `conclude` event references it via
`metadata.resolves`. `metadata.resolves` holds one event id or a list of event ids
(/analysis-reflection writes a list). To list open questions:

```
questions = [e for e in events if e.type == "question"]
resolved_ids = set()
for e in events:
    if e.type == "conclude" and e.metadata.get("resolves"):
        r = e.metadata["resolves"]
        resolved_ids |= set(r) if isinstance(r, list) else {r}
open_questions = [q for q in questions if q.id not in resolved_ids]
```

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load target design |
| `list [--status S]` | Find designs for tree/sibling queries (filter by parent_id/theme_id in the JSON) |
| `create` (stdin JSON) | Branch workflow (create child design) |

## tree_io Reference

`tree_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `tree_io link-derived --theme T --design ID` | Branch workflow (link the child design to the nodes of its source) |

## Error Handling

| Situation | Action |
|---|---|
| Design not found | Show error, suggest `design_io list` |
| Journal file corrupted | Backup corrupt file, reinitialize |
| Event ID conflict | Re-scan existing IDs and use max+1 |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-design | → /analysis-journal | After design creation: "推論過程を記録するなら /analysis-journal {id}" |
| /analysis-review | → /analysis-journal | Design approved (analyzing): "分析を始めるなら /analysis-journal {id}" |
| /analysis-notebook | → /analysis-journal | Notebook を実行後に手動の推論を追記 |
| /analysis-journal | → /analysis-reflection | Evidence gathered: "振り返りと結論は /analysis-reflection {id}" |
| /analysis-journal | → /analysis-journal | After branch: "分岐先のジャーナル: /analysis-journal {new_id}" |
| /analysis-reflection | → /analysis-journal | Need more evidence: "追加調査は /analysis-journal {id}" |
| /data-lineage | → /analysis-journal | Lineage diagram generated: "リネージ結果を証拠として記録するなら /analysis-journal {id}" |
| /analysis-revision | → /analysis-journal | Need to investigate before fixing: "調査してから修正するなら /analysis-journal {id}" |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Journal content follows the user's language (usually Japanese).
