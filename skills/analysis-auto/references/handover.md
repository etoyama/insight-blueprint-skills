# /analysis-auto — Hand several nodes over together

Step 3H of [the /analysis-auto SKILL.md](../SKILL.md), kept here because only a round of
several nodes needs all of it. A round of one node reads only *Stopping an analysis*.

### Step 3H: Hand several nodes over together

A round of several nodes runs this step in place of **framing brief** to **reflection** of
Step 3. Each design then runs in an execution agent of its own: a subagent you start in this
conversation and hand one design.

You are the dialogue agent. The dialogue agent alone writes the question tree, the designs
and the tree's HTML, one write after another. An execution agent writes only the notebook,
the verdict and the journal of its own design
([ADR-0062](../../../docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)).

Go through the items in order, on a first run and on a resumed one. Each names the designs
it acts on by their `stage` in `tree_io position`, and is skipped when there are none.

1. **briefs** (nodes of `undesigned_node_ids`): every node without a design needs one. Run
   `/analysis-framing {theme_id}` and hand it the output of `tree_io position`: its 4d takes
   those nodes as the answer and outputs a Framing Brief for each.
2. **designs** (the same nodes): for each Brief, in the order of `node_ids`, run
   `/analysis-design` through its Step 3: create the design, link it to its node, copy what
   the analyst heard. Draft every field from the Brief. The four beats are not asked: the
   analyst reads what they confirm at **check before handing over**
   ([ADR-0063](../../../docs/adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md)).
   Each design states its `data_scope` (population, grain, denominator). The design
   is saved `in_review`. No premortem and no data before the check: run no query, read no
   file of a source, profile nothing. Write the designs one after another, never in parallel.
3. **check before handing over** (`before_run`): a KEEP gate, asked once for all the designs.

```bash
tree_io render --theme LIB
tree_io handover --theme LIB
```

   - `handover` lists in `design_ids` the designs the analyst reads, and in `no_data_scope`
     those that state no `data_scope`. When `no_data_scope` is not empty, do not ask for
     the check yet: write the `data_scope` of each with `design_io update`, then run both
     commands again.
   - Show the `path` that `render` printed on a line of its own, right before the question,
     in a form the host opens: a code block `open {path}`, with the full path. A path inside
     a sentence is missed.
   - Ask one question and wait: hand the designs over as they are, comment on a design, or
     leave a design out. The question starts with
     「先にページの「分析を任せる前の確認」を開いて読んでから答える」.
     Write the summary of `differing` in the question itself, not only in the lines before
     it: for each row its `label`, and the `values` of each design (say `not_written` as
     the page does, 書かれていない). Never compare the values yourself: the page marks the
     same rows as 分析間の違い. When `differing` is empty, say that the page marks no
     difference. For comments, the analyst writes them on the page, presses
     コメントをまとめる and pastes the text it makes.
   - The pasted text has, under 分析を任せる前の確認へのコメント, one line `{design_id}: {comment}`
     for each design; a line without an id goes on with the comment above it. Record each
     comment on its design, in the analyst's words, change the design as the comment asks,
     and take it back to `in_review`:

```bash
echo '{"comments": [{"comment": "粒度を本1冊にそろえてほしい"}], "reviewer": "analyst"}' | design_io review-batch --id LIB-H03 --status revision_requested
echo '{"data_scope": {"population": "2025年度に取り置いた本", "grain": "本1冊", "denominator": "取り置いた本の全件"}}' | design_io update --id LIB-H03
design_io transition --id LIB-H03 --target in_review
```

     `/analysis-design` Step 3b says how a field is changed. When a comment does not say what
     to change, ask the analyst before you change anything. After the comments are recorded,
     run both commands of this item again and ask the check again, saying what changed. This
     repeats until the analyst hands the designs over.
   - A design the analyst leaves out is stopped, with the reason in the analyst's words, as
     *Stopping an analysis* below says.
   - When every design of the round is stopped, nothing is handed over: go to
     **theme reflection** of Step 3.
4. **premortem** (`before_run` after the check, and `running`): run `/premortem` for each of
   these designs, in the order of `design_ids`. On `HARD_BLOCK`/`HIGH`, stop and surface the
   risk as **premortem** of Step 3 says, and hand nothing over until the analyst has decided.
   A design `in_review` or `revision_requested` whose result is on record is
   `awaiting_reflection`, held by a review of its result: it is never moved into the analysis
   here, and its ending is asked at **endings**.
   Then move each `before_run` design into the analysis, one after another, and rebuild the
   page so that it shows them as 進行中:

```bash
design_io transition --id LIB-H04 --target analyzing
```

   If the transition exits non-zero, show stderr, leave that design where it is and take it
   back to **check before handing over** with what it lacks (a confirmation without the
   criterion of its verdict is refused); the others go on.
   A `running` design whose execution agent you did not start in this conversation has
   none: run its premortem here and hand it over again, and tell the analyst in the plan
   of Step 1 which analyses are handed over again, since the earlier run left no result on
   record. A design whose confirmation the analyst has just answered is `running` with no
   agent at work as well: its premortem runs here again, since the answer may have changed
   its extraction, and it is handed over again.
5. **hand over** (`running`): start one execution agent for each design, all of them in the
   same message so that they run side by side. Give each the brief of
   [execution-brief.md](execution-brief.md). Start them in the
   background when the host lets you, so that each return reaches you on its own.
6. **return** (a design whose execution agent came back): each time one or more agents
   have returned, without waiting for the others, rebuild the page and read where the round
   stands:

```bash
tree_io render --theme LIB
tree_io position --theme LIB
```

   The dialogue agent alone rebuilds the page; an execution agent never does
   ([ADR-0062](../../../docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)).
   Then go by the `stage` of each design that came back:
   - `awaiting_confirmation` → **confirmation**, right away.
   - `awaiting_reflection` → it waits for **endings**. Ask nothing about it yet.
   - `running` → it came back without a result. Tell the analyst what its agent reported,
     and hand it over again only if they ask. Say as well that the round stays open until
     this analysis is handed over again or stopped (*Stopping an analysis*).

   This item and **confirmation** repeat until no execution agent is at work.
7. **confirmation** (`awaiting_confirmation`): a KEEP gate, asked as soon as an analysis
   waits, for one analysis at a time. Only that analysis waits: never stop or hold back
   another execution agent for it.

```bash
design_io stage --id LIB-H04
```

   - `asks` holds what the analysis asks, each with the `id` an answer names. Never read
     the confirmation out of the journal yourself. Show the analyst the design it belongs
     to and each `content` as written, then ask one question and wait: answer it, or stop
     this analysis. Never answer for them.
   - The analyst answers → record the answer in the analyst's words:

```bash
echo '{"answers": "LIB-H04-E01", "content": "2025年10月以降の予約に絞ってよい"}' | design_io answer-analyst --id LIB-H04
```

   - When the answer changes the design, write the change with `design_io update` before
     anything runs, and tell the analyst each field you changed, with its value before and
     after. List every field the answer touches and change each of them: not only the
     extraction in `methodology.steps`, but every field that writes the same definition,
     such as the `description` of an `explanatory` variable, `data_scope` and `metrics`.
     Check that every field is changed before you take the analysis back to
     **premortem**. A design that began its analysis keeps its hypothesis and the criterion of its
     verdict: when `update` refuses the change, show stderr and offer to stop this analysis
     and derive a design from it (*Stopping an analysis*).
   - The answered analysis is `running` again, with no agent at work. Take it back to
     **premortem**, which runs again before any data is touched, and then to **hand over**:
     add what it asked and the analyst's answer to the brief of its new agent.
   - The analyst stops it → *Stopping an analysis*.
8. **endings** (`awaiting_reflection`): a KEEP gate, asked once for all of these designs,
   when no execution agent is at work and no analysis waits for a confirmation.
   - For each design, in the order of `design_ids`, run `/analysis-reflection {design_id}`
     through its Step 2: the summary and 読むもの. Ask nothing yet.
   - Show the path of the page on a line of its own, as **check before handing over** does,
     and say which analysis notes to read there: those the page marks
     「計算が終わり、振り返りを待っている」. The page lists finished designs with them.
   - Then ask one question for all of them and wait. Under a heading for each design, with
     its id and title, put the three questions of `/analysis-reflection` Step 3 as that step
     words them for the form of the design; the third is この分析設計をどう終えるか, with
     its choices. Add no question of your own, and leave none out. Say in the same question
     what Step 4 would ask of a design that ends (a review of its result first, the
     tentative answer of an exploration, the change of its status), so that Step 4 asks
     nothing again. For the review, say what it does and give the suggestion for each
     design, as the guide to a review of the result in `/analysis-reflection` Step 4 says;
     never write the guide here. The analyst answers for all the designs in one reply.
   - Never end a design on an answer the analyst did not give: ask again about each design
     the reply does not cover.
   - Then do what each answer chose, as `/analysis-reflection` says. A design that ends goes
     through its Step 4, one design after another, never in parallel: the `conclude` event,
     then the terminal transition. A design the analyst wants to look into further, or to
     derive from, keeps the round open: carry on with it as its answer says and come back
     to this item. A derived design is a new design on its node, and goes through
     **check before handing over**.
   - When every design of the round has ended or is stopped, run `tree_io render --theme`
     once more and go on to **theme reflection** of Step 3.

#### Stopping an analysis

The analyst may stop one analysis at any point: at the check before handing over, while it
runs, or while it waits for their answer. Stop only the one they name: the others go on.

```bash
echo '{"content": "先に予約の数え方を確かめたいので、今回は任せない"}' | design_io stop --id LIB-H05
```

- The reason is in the analyst's words. Ask for it when they gave none.
- When its execution agent is still at work, stop that agent as well if the host lets you.
  The stop holds either way: `design_io journal-append` refuses a stopped analysis, so its
  agent records nothing more and returns.
- `stop` refuses an analysis whose result is on record (`awaiting_reflection`): say so, and
  that its ending is asked at **endings**.
- Never delete the design or unlink it from its node, and never move it: the page shows it
  as 止めた, with the reason, and `design_io transition` refuses a stopped design.
- A stopped analysis is not resumed. To try again, derive a design from it with
  `/analysis-design` (`parent_id`): a new design on the same node, which goes through
  **check before handing over** before it runs.
- Rebuild the page after a stop (`tree_io render --theme`).
