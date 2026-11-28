---
name: analysis-reflection
version: "1.2.0"
description: |
  Guides structured reflection on an analysis design using its Insight Journal.
  Helps say what the results tell, check the open questions, and decide how the design ends:
  a verdict for a confirmation, `explored` for an exploration, or a derived design.
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
- Ready to end a design (an exploration to `explored`, a confirmation to supported/rejected/inconclusive)
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
  [Theme Reflection](references/theme-reflection.md).
- No argument: ask which design or theme to reflect on.

### Step 1: Load Design + Journal

1. `design_io get --id {design_id}` — load design (JSON)
2. Read `.insight/designs/{design_id}_journal.yaml` using Read tool — load journal
3. Read whether the analysis left a result. Never work it out from the status and the
   journal yourself:

```bash
design_io stage --id {design_id}
```

   - `stage` is `stopped`: the analysis was stopped, so there is no result to reflect on.
     Say so, and suggest deriving a new design with /analysis-design (`parent_id`) → exit
   - `stage` is `awaiting_confirmation`: the analysis waits for the analyst's answer to what
     `asks` holds. Say so → exit
   - `result_on_record` is false: the journal is missing, or holds only what was written
     before the analysis ran (the answer `/analysis-design` copied in as a `hearing`, say):
     "ジャーナルがない。まず /analysis-journal {id} で推論過程を記録してから振り返ろう" → exit

### Step 2: Present Analysis Summary

Show structured overview:

```
── Reflection: {design_id} ──
Title: {title}
Question: {exploration_question}       (an exploration)
Hypothesis: {hypothesis_statement}     (a confirmation or a legacy exploration)
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
Without a direction: {count} items
  - {content} ({created_at})

── Decisions Made ──
  - {method} ({package}) — {reason}

── Open Questions ──
  - {question_content} ({event_id})

── Branches ──
  - {child_design_id}: {child_title} ({child_status})

── 点検 ──
{check_line}

── 読むもの ──
開くファイル: {path}
分析ノート: {path}#{anchor}
論点: {node_ids}
気づいたことはこのチャットで返せば、journal に残す。
```

Open Questions lists the questions that are open as /analysis-journal defines it (Open
Questions): a confirmation the analyst already answered is not one of them.

An exploration's evidence carries no `direction` (ADR-0050): show it all under
`Without a direction` and leave out the other two lines. A legacy exploration may hold both:
evidence recorded before Epic 32 has a direction, and evidence from a notebook run since has
none. Show each group that is not empty.

To find branches, list designs and filter by parent_id:
```
designs = json(`design_io list`)
children = [d for d in designs if d["parent_id"] == design_id]
```

#### Before 読むもの: the check of the computation

The check of the computation tells whether the notebook computed what the design says
([ADR-0070](../../docs/adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md)).
It is done before the analyst reads, on every way into this step: called on its own, or
from the endings of `/analysis-auto`. It asks the analyst nothing. Before the render of
読むもの, read whether it is done:

```bash
design_io checked --id {design_id}
```

- `checked` is true: the check is done for the verdict and the design as they are now, so
  never run it again.
- `has_verdict` is true and `checked` is false: run the check now, before the block. Read
  [references/computation-check.md](references/computation-check.md) when this happens, and
  follow it: it says who reads, what the brief of a check agent holds and how the check is
  recorded. Then go on with what `design_io check` printed.
- `has_verdict` is false: no notebook left a verdict, so there is no computation to check.
  Leave the 点検 block out.
- A design that has ended is not checked. Show its 点検 line only when `checked` is true.
- If the check cannot be recorded, show the stderr and write 「点検できなかった」 with the
  reason as the 点検 line. Step 3 still goes on.

So the render comes after the check, and the design note shows the same result.

Fill `{check_line}` of the 点検 block from that JSON, in one line for each design:

- `differences` is empty: one line, 「分析設計と違う所は無い」.
- `differences` is not empty: 「分析設計と違う所が {n} つある。下の問いの前に並べる」. The
  differences themselves are shown in Step 3, and not here.
- Some `items` are `not_checkable`: add 「確かめられなかった: {labels}」 to the line, with
  the words of the table below.
- `checked_by` is `same_session`: say so in the line, 「読み比べたのはこのセッション自身」.
  For a check agent say nothing: the first sentence below names it.

Once in a conversation, before the first 点検 line, say what the check is and what it does
not tell, in these words:
「点検（分析設計どおりに計算したかの点検）とは、分析設計に書いたことと、分析コードがしている計算が同じかを、エージェントが読み比べること。
数が正しいか、分析設計が妥当か、結果の解釈が妥当かは確かめていない。」

The words the analyst reads for a subject and for a result. Never show the names of the
JSON:

| In the JSON | Shown to the analyst |
|---|---|
| `population` | 対象 |
| `grain` | 粒度 |
| `denominator` | 分母 |
| `extraction` | 抽出 |
| `metrics` | 指標 |
| `compared_against` | 比べ先 |
| `figures` | 図 |
| `criterion` | 判定の基準 |
| `cells` | 分析コードの区切り |
| `agrees` | 分析設計どおり |
| `differs` | 分析設計と違う |
| `not_checkable` | 確かめられなかった |

#### 読むもの

The 読むもの block tells the analyst where to read the evidence before Step 3 asks for a
conclusion: the design note, which holds the method, the metrics, the results, the
figures, the code and the progress of the analysis (ADR-0036).

- Right before you show the block, run `tree_io render --design {design_id}`, whether or
  not the theme has a question tree. It rewrites the page that holds the design note and
  prints JSON: `path` always, and `anchor` and `node_ids` when the note is in the tree page.
- Fill the block from that JSON. `論点:` lists the `node_ids` in their order.
- When `anchor` is not there, the file is the note itself (the theme has no tree). When
  `node_ids` is empty, no question links the design. In either case show only the
  `分析ノート:` line, and leave out `#{anchor}` when there is no `anchor`.
- If the render exits non-zero, show its stderr, say that the design note could not be
  rebuilt, and show no path: the page may be out of date. Step 3 still goes on.
- Do not list the figures, the verdict, the notebook or the metrics in the chat; the
  design note holds them. Do not copy the values of the verdict either, and embed no
  figure in the chat.
- Build the rest of Step 2 from the design, the journal and the verdict, and never read
  the design note: it is made from them for the analyst.
- A reply to Step 3 is recorded as `reflect` and `conclude` events (Steps 3 and 4). Any
  other remark the analyst sends goes in as an event of the types `/analysis-journal`
  records. Add no new type of event.

### Step 3: Guided Reflection (3 Questions)

Read the form of the design first, from `design_io get`:

| Form | How it reads |
|---|---|
| Exploration | `analysis_intent: exploratory` with `exploration_question`. It measures and answers; it never gets a verdict |
| Confirmation | any other intent (`confirmatory`, a saved `mixed`, none). It ends on a verdict against the criterion fixed before the analysis |
| Legacy exploration | `exploratory` with only `hypothesis_statement`, saved before Epic 32. It ends on a verdict like a confirmation (ADR-0049) |

Ask the three questions in order, one at a time, under the headings below: each heading is
the question itself. Show the heading to the analyst as written for the form of the design;
never call the questions by a letter and a number, which reads like the id of a node. Record each answer as a `reflect`
event in the journal. Say what you ask in plain words, with no metaphor: write "答えが出ると
判定が変わる", not a figure of speech for it.

#### Before the questions: what differs from the design

Only when `differences` of Step 2 is not empty. Show the differences at the head of the
first question, above its heading, so that the analyst knows them before answering
([ADR-0071](../../docs/adr/0071-a-difference-is-shown-before-reading-and-the-review-of-a-result-is-narrowed.md)):

```
── 分析設計と違う所 ──
- {label}: {note}
このまま読むか、分析設計どおりに計算し直させるか。
```

- One line for each item of `differences`: `label` is the word of the table of Step 2 for
  its `subject`, and the `note` as written. Never reword a `note`, and leave its `cell`
  out: the design note shows it.
- The choice is 「このまま読む」 or 「分析設計どおりに計算し直させる」. It is asked in the same
  question as 結果から何が言えるか, and adds no question of its own: an answer to the first
  question takes 「このまま読む」.
- 「このまま読む」 → go on with the three questions; the record of the check stays, and the
  design note goes on showing the differences.
- 「分析設計どおりに計算し直させる」 → run `/analysis-notebook {design_id}` in this session, with
  the differences as what to put right: the notebook is changed to compute as the design
  says, run, and its verdict recorded again, and no premortem runs again, since the
  extraction does not change. Then come back to Step 2 of this skill, which checks the new verdict before
  it shows 読むもの again, and ask the three questions after that. Differences that remain
  are shown and asked about in the same way.
- A design that a review of its result holds (`in_review` or `revision_requested`) takes
  no new result, so it cannot be computed again until the review returns it to
  `analyzing`: say so, and offer 「このまま読む」 alone.
- Never fix a difference on your own, and never choose for the analyst (ADR-0071). When
  the notebook cannot compute as the design says without changing something the design
  writes, say what and ask the analyst before any data is touched.

#### 結果から何が言えるか

- **Confirmation** — first show the criterion fixed before the analysis: the `comparison`
  of the primary metric (`tier: primary`), as the design writes it. With more than one
  primary metric, show the `comparison` of each. A confirmation saved before Epic 32 may
  have no primary metric or an empty `comparison`: then say
  「分析の前に固定した基準は無い。判定は、結果を検証仮説に照らした読みで決まる」 and ask with
  the hypothesis alone. Never write a criterion yourself after the result is known. Then ask:
  「分析の前に固定した基準「{criterion}」に照らすと、検証仮説「{hypothesis_statement}」について、結果から何が言えるか」
  - The results meet the criterion → toward `supported`
  - The results go against it → toward `rejected`
  - The results cannot tell → toward `inconclusive`, or more investigation
- **Legacy exploration** — its hypothesis was written without a criterion fixed before the
  analysis. When the `comparison` of its primary metric writes none, say
  「分析の前に固定した基準は無い。判定は、結果を検証仮説に照らした読みで決まる」 and ask as
  for a confirmation with the hypothesis alone. Evidence without a `direction` is a measured
  value, not a reading: show each item and ask whether it speaks for the hypothesis, against it,
  or neither. Never give it a direction yourself, and never count the items to choose the verdict.
- **Exploration** — ask: 「探索の問い「{exploration_question}」に、結果から何が言えるか」.
  The answer is what was measured and what it shows, in the analyst's words. When the answer
  states no measured value (「特になし」, say), show the measured values of the journal's
  `evidence` events and ask once more: 「測った値はこのとおり。この値から、探索の問いにどう答えるか」.
  Keep the analyst's words as the answer, and do not write one for them. Offer no verdict
  and no direction toward one: an exploration has no verdict.

#### まだ答えの出ていない問いで、判定は変わるか

An exploration reads this heading as 「まだ答えの出ていない問いで、答えは変わるか」.

Before you ask, say what the question covers and what it asks about:

- The questions are the `question` events of this design's journal that no `conclude`
  event lists in `resolves`: not the questions of the theme or of the root question.
- 判定 is this design's verdict: `supported`, `rejected` or `inconclusive` against the
  criterion of the first question. For an exploration, 答え is the answer to the first
  question.

For each open question, show the question and what its answer would change, then ask:

```
── まだ答えの出ていない問い ──
- {question_content} ({event_id})
  答えが {A} なら判定は {X} に変わる。{B} なら変わらない。
- {question_content} ({event_id})
  どう答えても判定は変わらない。
```

For an exploration, write 答え for 判定 in every line, and {X} is how the answer to the
first question would read: never `supported`, `rejected` or `inconclusive`.

Then ask: 「この中に、答えが出ると判定（探索では答え）が変わる問いはあるか」.

- When there is no open question, say so and go to the next question.
- ある → recommend more investigation (→ /analysis-journal) before the design ends.
- ない → go on to the next question.
- A question whose answer changes no verdict is not dropped. Say that it is kept, and that the
  theme reflection (`/analysis-reflection {theme_id}`) writes it into the answers as
  まだ決められないこと or 注意すべきこと, for example:
  「この問いは捨てない。テーマの振り返りで、主題への答えに、まだ決められないこと か 注意すべきこと として書く。」

#### この分析設計をどう終えるか

Before the choices, say: 「ふつうは1つ目の答えのとおりに終える。変わるのは、2つ目で『ある』と答えたときだけ」.

- **Confirmation** (and a legacy exploration) — the choices:
  - 「判定を出して終える」 (`supported` / `rejected` / `inconclusive`) → Step 4
  - 「調べ足す」 → /analysis-journal
  - 「検証仮説を直すか別の仮説を立てて、派生の分析設計で調べ直す」 → Step 5
- **Exploration** — the choices are 「探索を終える」 (→ Step 4) and 「調べ足す」
  (→ /analysis-journal). Offer no verdict.

### Step 4: Record Conclusion

When the analyst ends the design:

1. Ask whether to have the result reviewed first. A review of the result with /analysis-review
   is optional, and the analyst decides whether to ask for one. It comes before the conclusion
   is recorded: it moves the design back to `in_review`, and approving it returns the design to
   `analyzing`. Once the design has ended it can no longer be reviewed.
   Before you ask, say what the review does, in these words:
   「結果のレビューでは、Claude が notebook・verdict・図・分析設計を批評し、コメントを残す。
   受けると、結論の記録はレビューの後になる。受けないと、この場で結論を記録し、以後はレビューできない」.
   Then give one line of suggestion for this design, by the guide below.

   **The guide to a review of the result.** For a confirmation, which ends on a verdict,
   suggest taking the review. For an exploration, say it usually does not need one. Still
   offer it as a choice worth taking when the analysis added something the design does not
   have (a comparison, say), or when the only check of the numbers adds up figures within
   the data, against no total from outside it. The analyst decides: the line is a
   suggestion, and either answer goes on.

   - The analyst takes the review → record no `conclude` yet, and send them to
     `/analysis-review {design_id}`. After the review, `/analysis-reflection {design_id}` comes
     back to this step and records one `conclude` for the design. Do not ask about a review
     again then.
   - The analyst declines → go on.

2. Record `conclude` event in journal:
   ```yaml
   - id: "{design_id}-E{nn}"
     type: conclude
     content: "{user's conclusion statement}"
     metadata:
       resolves: ["{question_event_ids that are now resolved}"]
     created_at: "{now}"
   ```

3. Suggest the status transition (via design_io transition). Without a review the design ends
   right after its analysis, as each form below shows (validated by VALID_TRANSITIONS).

   - **Confirmation** (and a legacy exploration) — 「判定が出た。ステータスを変更する？」
     - supported: `design_io transition --id {design_id} --target supported`
     - rejected: `design_io transition --id {design_id} --target rejected`
     - inconclusive: `design_io transition --id {design_id} --target inconclusive`
     - Without a review it closes straight from its analysis (`analyzing → supported`).
     - A design whose analysis never started (still `in_review` or `revision_requested`, no
       `analysis_started_at`) and that has no criterion (no `primary` metric, or an empty
       `comparison`) is refused `supported` and `rejected`
       ([ADR-0053](../../docs/adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)).
       Check for this before recording `conclude` in item 2. The refusal names
       `/analysis-design`, but the result is known here, so do not write a criterion now.
       Tell the analyst the hypothesis has no criterion fixed before the result, and offer
       the two ways on: close the design as `inconclusive`, or derive a design that fixes its
       criterion first (Step 5).
   - **Exploration** — before the transition, ask 「次に確かめたい仮の答えはあるか（飛ばしてよい）」.
     When the analyst gives one, record it as a `hypothesize` event in this journal, in the
     analyst's words: the journal is the record the design ends on. The analyst may skip the
     question: then record nothing. Then 「探索を終える。ステータスを変更する？」
     `design_io transition --id {design_id} --target explored`. It refuses the three verdicts.
     Without a review it closes straight from its analysis (`analyzing → explored`).
     With a tentative answer, say 「検証の分析設計を派生で起こすなら /analysis-design（`parent_id` に {design_id}）」.
     When the analyst does, link it and record it as Step 5 items 3 and 4 do; the journal
     gets the `branch` event as the link to the new design.

4. Show final summary and suggest:
   - "この分析で分かったソースの再利用知識を残すなら /knowledge-extract"
   - "新しいデータソース自体を登録するなら /catalog-register"
   - "派生の分析設計を立てるなら /analysis-design"

   Note: 結論そのもの（finding）はここ（journal/reflection）に残す。/knowledge-extract は
   データソースに紐づく再利用可能な知見だけを抽出する。

### Step 5: Derive a Design (when the hypothesis changes)

When the analyst corrects the hypothesis or sets another one, the change goes into a new
design derived from this one. The hypothesis of this design was fixed before its analysis
ran (ADR-0048).

1. Record a `hypothesize` event in this journal: the corrected or new hypothesis and what
   in the results led to it.
2. Run /analysis-design with `parent_id` set to {design_id}, the same `theme_id`, and the
   hypothesis of step 1 as the draft. It asks the intent first and fixes the criterion of a
   confirmation before the new analysis.
3. With the id it returns, link the new design to the nodes of this one with
   `tree_io link-derived --theme {theme_id} --design {new_design_id}`, record a `branch` event
   in this journal, and start the new design's journal with a `hypothesize` event that has
   `forked_from: {design_id}`, as /analysis-journal Step 4 does (items 3, 4 and 5).
4. This design stays as it is, at `analyzing`. It may end later in its own reflection.

Never rewrite the hypothesis of this design to refine it. Once the analysis has started,
`design_io` refuses a change of the hypothesis, of the criterion (the `primary` metrics) and
of the intent, also after a review of the result has sent the design back to `in_review`
([ADR-0053](../../docs/adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)).
The background and the other fields can still be edited.

## Theme Reflection

Read [references/theme-reflection.md](references/theme-reflection.md) when the argument is a
theme id (Step 0), and follow its Steps T1 to T7 there. The `design_io` and `tree_io`
references below hold for it as well.

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details |
| `checked --id ID` | Whether the check of the computation is done for the verdict as it is now, and what differs (read-only) |
| `check --id ID` (stdin JSON) | Record the check of the computation: the reader's items, and the subjects the code decides |
| `transition --id ID --target S` | Terminal status transition (validated against the form) |
| `list` | Find child/sibling designs (filter the JSON by parent_id/theme_id) |

## tree_io / tree_check Reference

Both are on PATH via the plugin. JSON on stdout.

| Command | Used for |
|---------|----------|
| `tree_io get --theme T` | Load the question tree |
| `tree_io progress --theme T` | Progress of each node (its word or `null`) and the counts below it, derived from its designs |
| `tree_io position --theme T` | Where the walk stands: the nodes the last decision names, their designs and the stage of each analysis |
| `tree_io answer --theme T` (stdin JSON) | Check and append the answers of one reflection round |
| `tree_check --theme T` | Check the current answers after writing (read-only) |
| `tree_io changes --theme T` | What each answer changed, and the results the answers above leave out (read-only) |
| `tree_io changes --theme T --with-answers` (stdin JSON) | The same for the answers about to be written, with whether each left-out result was shown before (read-only, Step T3) |
| `tree_io candidates --theme T` | The next candidates: nodes with no design on them or below them |
| `tree_io candidate --theme T --node N` (stdin JSON) | Write the notes of a candidate (`ask`, `changes_if`, `known`) |
| `tree_io hear --theme T --node N` (stdin JSON) | Keep the answer a person gave, with who and when |
| `tree_io decide --theme T` (stdin JSON) | Append the analyst's decision (`deepen`, `return`, `close`), after checking its `cites` |
| `tree_io render --theme T` | Rebuild the HTML of the tree from the canonical file |
| `tree_io render --design D` | Rebuild the page that holds the design note of D, and say where the note is |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-journal | → /analysis-reflection | Evidence gathered |
| /analysis-notebook | → /analysis-reflection | Notebook 実行の結果が揃った: 結論づけへ |
| /analysis-auto | → /analysis-reflection | autopilot が結果到達; 結論はユーザー判断 |
| /analysis-reflection | → /tree-upload | 現時点の答えを書き、図（HTML）を作り直した: "論点ツリーの図を URL で渡すなら /tree-upload" |
| /analysis-reflection | → /analysis-journal | Need more evidence (調べ足す) |
| /analysis-reflection | → /knowledge-extract | Conclusion produced reusable source knowledge |
| /knowledge-extract | → /analysis-reflection | The learning is really a conclusion, not source knowledge |
| /analysis-reflection | → /catalog-register | A new data source needs registering |
| /analysis-reflection | → /analysis-framing | A new question to explore or a new hypothesis to confirm is needed, and the data or the direction comes first: "新しい角度を探すなら /analysis-framing" |
| /analysis-reflection | → /rq-problematization | 検証仮説が棄却されたか結論できなかった、または探索の答えが前提と合わず、前提から問い直したい: "前提から問い直すなら /rq-problematization" |
| /analysis-reflection | → /analysis-design | A derived design is clear (a corrected hypothesis, Step 5, or a tentative answer after an exploration, Step 4): "派生の分析設計を作るなら /analysis-design" |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Reflection content follows the user's language (usually Japanese).
