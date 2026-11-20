---
name: analysis-reflection
version: "1.1.0"
description: |
  Guides structured reflection on an analysis design using its Insight Journal.
  Helps draw conclusions, identify gaps, and decide whether to conclude, refine, or branch.
  Given a theme, writes the current answer of each node of its question tree across the
  designs of the theme, citing journal events, and checks it before the analyst sees it.
  Triggers: "振り返り", "reflection", "まとめ", "結論を出す", "分析を振り返る",
  "この仮説どうなった", "wrap up analysis", "テーマの振り返り", "現時点の答え".
disable-model-invocation: true
argument-hint: "[design_id | theme_id]"
---

# /analysis-reflection — Structured Analysis Reflection

Guides the user through a structured reflection on their analysis,
using the Insight Journal as source material. Helps reach a conclusion,
identify remaining gaps, or decide to branch.

## When to Use
- Enough evidence has been gathered and it's time to reflect
- Want to assess open questions and decide next steps
- Ready to conclude (transition to supported/rejected/inconclusive)
- Want the current answer of each node of a theme's question tree, across its designs

## When NOT to Use
- Still actively investigating (→ /analysis-journal)
- Creating a new design (→ /analysis-design)
- Registering data sources or knowledge (→ /catalog-register)

## Workflow

### Step 0: Pick the reflection

- The argument is a design id (`{theme_id}-H{nn}`, e.g. `LIB-H01`): reflect on that one
  design. Go to Step 1.
- The argument is a theme id (e.g. `LIB`): reflect across the designs of the theme. Go to
  [Theme Reflection](#theme-reflection).
- No argument: ask which design or theme to reflect on.

### Step 1: Load Design + Journal

1. `design_io get --id {design_id}` — load design (JSON)
2. Read `.insight/designs/{design_id}_journal.yaml` using Read tool — load journal
3. If no journal exists: "ジャーナルがない。まず /analysis-journal {id} で推論過程を記録してから振り返ろう" → exit

### Step 2: Present Analysis Summary

Show structured overview:

```
── Reflection: {design_id} ──
Title: {title}
Hypothesis: {hypothesis_statement}
Intent: {analysis_intent}
Status: {status}

── Journal Overview ──
Total events: {count}
Phase: {inferred_phase}  (see /analysis-journal Phase Inference rules)
Timeline: {first_event.created_at} → {last_event.created_at}

── Evidence ──
Supporting: {count} items
  - {content} ({created_at})
Contradicting: {count} items
  - {content} ({created_at})

── Decisions Made ──
  - {method} ({package}) — {reason}

── Open Questions ──
  - {question_content} ({event_id})

── Branches ──
  - {child_design_id}: {child_title} ({child_status})
```

To find branches, list designs and filter by parent_id:
```
designs = json(`design_io list`)
children = [d for d in designs if d["parent_id"] == design_id]
```

### Step 3: Guided Reflection (3 Questions)

Ask in sequence. Record each answer as a `reflect` event in the journal.

**Q1: Evidence Assessment**
"証拠を総合すると、仮説「{hypothesis_statement}」についてどう言える？"
- Supporting evidence dominant → supported direction
- Contradicting evidence dominant → rejected direction
- Inconclusive → inconclusive direction or more investigation

**Q2: Open Questions Check**
If open questions exist:
"未解決の問い ({count}件) がある。これらは結論に影響する？"
- Affects conclusion → recommend more investigation (→ /analysis-journal)
- Does not affect → proceed to conclusion

**Q3: Conclusion or Next Step**
"どう進める？"
- Draw conclusion (supported / rejected / inconclusive)
- Refine hypothesis and re-investigate (→ hypothesize event + /analysis-journal)
- Branch to new hypothesis (→ /analysis-journal branch workflow)

### Step 4: Record Conclusion

If user chooses to conclude:

1. Record `conclude` event in journal:
   ```yaml
   - id: "{design_id}-E{nn}"
     type: conclude
     content: "{user's conclusion statement}"
     metadata:
       resolves: ["{question_event_ids that are now resolved}"]
     created_at: "{now}"
   ```

2. Suggest status transition (via design_io transition):
   "結論が出た。ステータスを変更する？"
   - supported: `design_io transition --id {design_id} --target supported`
   - rejected: `... --target rejected`
   - inconclusive: `... --target inconclusive`

   Note: Current status must be "analyzing" for terminal transition (design_io
   validates this via VALID_TRANSITIONS). If status is "in_review", go through the
   review process first.

3. Show final summary and suggest:
   - "周囲に説明・配布できる形にするなら /analysis-report（APAレポート化）"
   - "レビューコメントを付けるなら /analysis-review（記録後 /analysis-revision で対応）"
   - "この分析で分かったソースの再利用知識を残すなら /knowledge-extract"
   - "新しいデータソース自体を登録するなら /catalog-register"
   - "派生仮説を立てるなら /analysis-design"

   Note: 結論そのもの（finding）はここ（journal/reflection）に残す。/knowledge-extract は
   データソースに紐づく再利用可能な知見だけを抽出する。

### Step 5: Record Refinement (if not concluding)

If user chooses to refine:

1. Record `hypothesize` event with the refined hypothesis in journal
2. Optionally refine the design: `echo '{"hypothesis_statement": "<refined>"}' | design_io update --id {design_id}`
3. Suggest: "/analysis-journal {id} で追加調査を続けよう"

## Theme Reflection

Writes the current answer of each node of the theme's question tree. An answer is a list
of statements, and each statement cites the journal events it rests on. The analyst sees
an answer only after the tree check has passed (ADR-0025).

### Step T1: Load the tree, its designs and their journals

1. `tree_io get --theme {theme_id}` — load the question tree (JSON). If it prints `{}`,
   the theme has no tree: "このテーマには論点ツリーがない。/analysis-framing {theme_id} で
   根の問いと論点を決めよう" → exit.
2. `tree_io progress --theme {theme_id}` — the progress of each node, derived from its
   linked designs.
3. For every design id in the `design_ids` of any node, read
   `.insight/designs/{design_id}_journal.yaml` with the Read tool. A design without a
   journal has no events to cite.

### Step T2: Write the statements of each node

Work from the leaves up to the root question. For each node, the source is the journal
events of the designs linked to the node and to the nodes below it. A node whose branch
holds no journal event gets no answer in this round: say so in Step T5 instead.

Each statement has a `kind`, a `text` and `cites`:

| `kind` | What the statement does |
|---|---|
| `claim` | 言えること — what the cited events let you say about the node's question |
| `undetermined` | 未判別 — what the cited events leave open, even though the analysis ran |
| `weakening` | 弱める証拠と留保 — a cited event that speaks against a claim, or a limit on how far it reaches |

Rules for every statement:

- Every statement cites one or more journal events (`{design_id}-E{nn}`) in `cites`.
  A sentence you cannot cite is not written.
- The answer of a parent node rests on the events of the designs linked to the nodes
  below it, read again for the parent's question: the source is the journal event, not
  the answer of a child. Never answer a parent from the progress of its children or from
  a count of them ("3つのうち2つが分析済み" is not an answer).
- A number appears only the way a cited event wrote it, sign included. Never compute a
  number: no ratio, difference, sum, average, rounding or unit conversion of recorded
  numbers. When the answer needs such a value, say that it is not recorded; the notebook
  computes it and the journal records it before an answer may state it.
- No id and no date in `text`. The digits of `LIB-H01-E02` or `11月21日` are read as
  numbers and reported as violations. Event ids go in `cites`; nothing else needs them.
- An event of kind `evidence` with `direction: contradicts` that bears on the node is
  cited in a `weakening` statement, not left out.

### Step T3: Write the answers through tree_io

Send the answers of every node of this reflection in one call. One call is one reflection
round: `tree_io` sets `round` and `root_revision` itself, appends the answers, and leaves
earlier rounds as they are.

```bash
echo '{"answers": [
  {"node_id": "LIB-Q02", "statements": [
    {"kind": "claim", "text": "状態の履歴から取消を除き、期限を迎えた予約同士を比べられた", "cites": ["LIB-H01-E01"]}
  ]}
]}' | tree_io answer --theme LIB
```

Never write `.insight/themes/{theme_id}_tree.yaml` with the Write or Edit tool: the hook
rejects a rewritten answer, and only `tree_io answer` checks the answer before it lands.

`tree_io answer` checks the answers first and reports on stdout:

- Exit code 0: the answers are written. `written` lists the nodes that got an answer in
  this round, each with `previous_round` (`null` for a first answer) and `restated`
  (`true` when the statements are the same as before and only the root revision is newer).
  `unchanged` lists the nodes whose statements equal their current answer under the
  current root revision; nothing is written for them. `round` is the last round the tree
  now holds.
- Exit code 3: `violations` is not empty and `tree_io` wrote nothing, for any node. Fix
  each violation in your draft and send the whole call again.
- Exit code 1: nothing was written, and the reason is on stderr. When it names the
  payload (unknown node, a missing field, JSON that does not parse), fix the payload and
  send it again. When a tree, design or journal file cannot be read or holds the same
  event id twice, rewriting the answer cannot help: report the message to the analyst and stop.

| Violation `kind` | How to fix it |
|---|---|
| `number-not-cited` | The number in `text` is in none of the cited events. Rewrite it the way the record wrote it: the same digits and the same sign. When the record states the direction in words ("3.2ポイント減った"), use those words instead of a sign ("−3.2"). If another event of the branch records the number, cite it. If no event records it, the number was computed or remembered: take it out |
| `missing-event` | The cited id is not in the journal of its design. Cite the event you actually read, or take the cite out |
| `unlinked-design` | The cited event belongs to a design that is linked neither to the node nor to a node below it. Cite an event from the node's own branch, or take the cite out |

Never edit a journal to make an answer pass, and never add a number to a journal that the
analysis did not produce. When a statement still violates after one rewrite, remove the
statement from the draft and keep a note of its text and the violation for Step T5. When
every statement of a node is removed, send no answer for that node in this round.

### Step T4: Check the tree after writing

Run `tree_check --theme {theme_id}`. It reads the tree and the journals and writes nothing.

- Exit code 0: no violation. Go to Step T5.
- Exit code 1: the current answer of some node violates. `tree_io answer` already stopped
  the answers of this round, so this is an answer from an earlier round whose journal has
  changed since. Write a new answer for that node (Steps T2 and T3) and check again, once.
  When the node has no event left to cite, or the check still reports it, leave the node:
  an answer cannot be withdrawn. List it under "Stale answers" in Step T5 with its
  violations, show its answer nowhere, and go on with the other nodes.
- Exit code 2: the check could not run (the message is on stderr). Do not rewrite any
  answer: nothing is known to be wrong with them. Report the message to the analyst and stop.

Before Step T5, run `tree_io render --theme {theme_id}` so that the HTML of the tree shows
the new answers. With a stale answer left, tell the analyst that the HTML still shows it.

Show no answer to the analyst before `tree_check` has run, and never show an answer that
`tree_check` reports.

### Step T5: Present the current answers

```
── Theme Reflection: {theme_id} (round {round}, root revision {root_revision}) ──
Root question: {root question}

{node_id}  {question}
  Progress: {未着手 | 検証中 | 分析済み}
  Answer (round {round}{, 根の変更前の答え}):
    [言えること] {text}  ← {cites}
    [未判別] {text}  ← {cites}
    [弱める証拠と留保] {text}  ← {cites}

── Changed in this round ──
  - {node_id}: 初めての答え | 回 {previous_round} から変わった | 根の版が上がり、同じ文で書き直した

── Unchanged ──
  - {node_id}

── Not answered ──
  - {node_id}: {引用できる出来事がまだ無い | すべての文を除いた}

── Removed statements ──
  - {node_id}: 「{text}」 — {violation kind}: {violation text}

── Stale answers ──
  - {node_id}: 回 {round} の答えは記録と合わなくなった — {violation kind}: {violation text}
```

- Changed and unchanged nodes come from `written`, `previous_round`, `restated` and
  `unchanged` in the output of `tree_io answer`. For a changed node, show the previous
  answer next to the new one. A `restated` answer says the same as before: say so
  instead of calling it changed.
- A node under "Stale answers" shows its question and progress, not its answer.
- An answer whose `root_revision` is lower than the current root revision answers an
  earlier root question: mark it "根の変更前の答え".
- List every removed statement with its violation. Never drop one silently: the analyst
  must know what the answer does not say.
- Suggest what to do next:
  - "未着手の論点に分析設計を起こすなら /analysis-design"
  - "根の問いか到達点を変えるなら /analysis-framing {theme_id}"
  - "分析設計の結論を出すなら /analysis-reflection {design_id}"

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details |
| `transition --id ID --target S` | Terminal status transition (validated) |
| `update --id ID` (stdin JSON) | Hypothesis refinement |
| `list` | Find child/sibling designs (filter the JSON by parent_id/theme_id) |

## tree_io / tree_check Reference

Both are on PATH via the plugin. JSON on stdout.

| Command | Used for |
|---------|----------|
| `tree_io get --theme T` | Load the question tree |
| `tree_io progress --theme T` | Progress of each node, derived from its designs |
| `tree_io answer --theme T` (stdin JSON) | Check and append the answers of one reflection round |
| `tree_check --theme T` | Check the current answers after writing (read-only) |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-journal | → /analysis-reflection | Evidence gathered |
| /analysis-notebook | → /analysis-reflection | Notebook 実行の結果が揃った: 結論づけへ |
| /analysis-auto | → /analysis-reflection | autopilot が結果到達; 結論はユーザー判断 |
| /analysis-reflection | → /analysis-report | Conclusion reached (terminal status): 配布用 APA レポートに畳む |
| /analysis-reflection | → /analysis-journal | Need more evidence or branching |
| /analysis-reflection | → /knowledge-extract | Conclusion produced reusable source knowledge |
| /knowledge-extract | → /analysis-reflection | The learning is really a conclusion, not source knowledge |
| /analysis-reflection | → /catalog-register | A new data source needs registering |
| /analysis-reflection | → /analysis-framing | New hypothesis needed, explore data/direction first: "新しい角度を探すなら /analysis-framing" |
| /analysis-reflection | → /rq-problematization | 仮説が棄却/不確定で、別角度でなく前提自体を問い直したい: "前提から問い直すなら /rq-problematization" |
| /analysis-reflection | → /analysis-design | Derived hypothesis already clear: "派生仮説を作るなら /analysis-design" |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Reflection content follows the user's language (usually Japanese).
