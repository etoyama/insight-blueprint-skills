---
name: analysis-auto
version: "1.1.0"
description: |
  Guided autopilot and the analyst's single entry. Takes a theme, builds its question tree
  (or resumes at the node the latest tree decision names) and walks the tree one decision per round:
  design → review → premortem → notebook → journal → reflection → theme reflection →
  tree decision. A decision that names several nodes hands their designs over together, after
  one check of all of them. Progresses automatically through low-friction steps and
  pauses only at genuine decision points (root question and aim, the node to investigate,
  intent and the question to explore or the hypothesis, the designs to hand over together,
  what a handed-over analysis cannot go on without changing, source registration, cost/risk, code with external effects, conclusion, the results
  the theme's answers rest on, the tree decision, sending anything outside this machine).
  Triggers: "オートで進めて", "自動で分析を回して", "autopilot", "guided auto",
  "最後まで進めて", "analysis auto", "論点を順に調べて".
disable-model-invocation: true
argument-hint: "[theme_id | design_id]"
---

# /analysis-auto — Guided Autopilot (driver)

The one entry for the analyst. It takes a theme, keeps the theme's question tree, and
investigates the tree one decision per round, so you type no `/command` between the steps. It
**orchestrates the existing skills** (it does not reimplement them) and **stops only at
genuine decisions**. Autonomy is scoped to this run — the individual skills stay
explicit/interactive everywhere else.
See [ADR-0005](../../docs/adr/0005-selective-autonomous-chaining.md) and
[ADR-0026](../../docs/adr/0026-analysis-auto-walks-the-question-tree.md).

## When to Use

- You have something to decide, or a research theme, and want Claude to frame it as a question
  tree and carry each node through to results, pausing for your judgment where it matters.
- A theme already has a question tree and you want to go on from where it stands.

## When NOT to Use

- You want to run a single step (use that step's `/command` directly).
- Unattended / headless batch execution — this is **not** that. It is interactive; it stops at
  the gates below and waits for you.

## Gate policy

The whole point is *reduce friction, keep judgment*. The driver enforces:

| Step | KEEP — pause for the user | AUTO — proceed without asking |
|------|---------------------------|-------------------------------|
| entry: a design without a tree | **whether to build a tree for the theme and walk it, or to carry only this design** — asked once, and only for a `design_id` whose theme has no tree | reading the position (`tree_io position`) |
| rq-problematization | **whether to review the list of assumptions, and the review when chosen** — asked by `/rq-problematization` itself | collecting prior research, extracting and testing assumptions, the RQ Brief |
| framing ① root question and aim | **`/analysis-framing` 4a** | — |
| framing ② first node | **`/analysis-framing` 4b** | — |
| framing ③ root revision | **`/analysis-framing` 4c** | — |
| framing ④ next node | **`/analysis-framing` 4d** | — |
| design ① intent | **ask the intent first (exploration or confirmation, never `mixed`), then confirm the question to explore + its background, or the hypothesis + its background, and the decision context (who decides what; skippable)** | drafting them from the Framing Brief |
| design ② methodology | **confirm the method + metrics + explanatory roles (treatment/confounder/…), and for a confirmation the criterion of the verdict in the primary metric's `comparison`**, after explaining the metrics as `/analysis-design` Step 2 "Metrics explained" does: one sentence for each metric, and the five parts for a metric built from two or more quantities that is new to the theme | auto-drafting these fields from the Framing Brief |
| design ③ data-extraction | **confirm the data-acquisition plan** — the actual query text (`methodology.steps`, with each table as `{source:ID}`) for SQL sources, or the data source id + columns + filter for CSV/others, plus expected grain & rough row scale | auto-drafting the query / column selection from the catalog schema |
| design ④ charts | **confirm the planned `chart[]` specs (intent / type / x / y)** | auto-drafting chart specs from the direction |
| check before handing over | **the designs of a round of several nodes, read side by side on the page: hand them over as they are, comment on a design, or leave a design out** — asked once for all of them (Step 3H) | drafting the designs, saving them `in_review`, linking them, rebuilding the page |
| confirmation after handing over | **what a handed-over analysis cannot go on without changing: answer it, or stop that analysis** — asked for one analysis at a time, while the others go on (Step 3H) | rebuilding the page on every return, recording the answer, running premortem again |
| endings | **how the analyses that came back end: the three questions of `/analysis-reflection` Step 3 for each design** — asked once for all of them (Step 3H) | the summary and 読むもの of each design, and after the reply the conclusions and the terminal transitions |
| review (optional) | **the verdict** (revision_requested vs approve) | running the critique itself |
| premortem | **result is `HARD_BLOCK`/`HIGH`** → stop, surface the risk | running premortem; `LOW`/`MEDIUM` |
| notebook | **non-allowlisted package / external comms beyond the declared source / other side-effects** | generate + run when premortem cleared AND it's declared-source read + allowlisted + local compute |
| journal | — | auto-record the notebook verdict (observe/evidence/question) |
| reflection | **この分析設計をどう終えるか (`/analysis-reflection` Step 3) + the terminal transition** — for a confirmation a verdict, more investigation or a derived design; for an exploration `explored` or more investigation, never a verdict | presenting the evidence summary and the place of the design note (`/analysis-reflection` Step 2) |
| theme reflection | **`/analysis-reflection {theme_id}` T3 + T7** | — |
| tree-upload | **the file to send as an Artifact** — asked by `/tree-upload` itself, at its approval gate; the driver adds no question of its own | starting `/tree-upload` when the analyst asks to hand the tree over |
| catalog-register | **registering a data source** (external-data side-effect); unregistered source → stop | — |

A KEEP cell that names a step of a delegated skill is that skill's own gate. That skill says what
the step asks, and also when it does not ask (4d, for a `not_started` position). The rest of that
skill follows it as written.

The four `design ①–④` beats are **ordered confirmation gates** run before `design_io create`
(and therefore before premortem): each is presented as its own AskUserQuestion so the user can
adjust it, rather than collapsing the whole design into a single "looks good?". Beat ③
(data-extraction) is where the *actual data pull* — the SQL query or the CSV file+columns+filter —
gets a seat, so premortem then estimates cost against the **confirmed** query.
The four beats belong to a round of one node; a round of several nodes has the check before
handing over in their place (Step 3H). The **reflection** row is that of a round of one node
as well: a round of several nodes asks the **endings** in its place.

Ask the analyst nothing outside the KEEP column. If in doubt whether something is a genuine
decision, **stop and ask** — bias toward the KEEP column.

## How the driver runs a skill

Every delegated skill is `disable-model-invocation: true`, so the Skill tool refuses it. That
is intended: outside this run the skills stay explicit. Inside this run, the analyst's
`/analysis-auto` is the explicit invocation that covers them
([ADR-0005](../../docs/adr/0005-selective-autonomous-chaining.md)).

- To run a skill, Read its file — `${CLAUDE_PLUGIN_ROOT}/skills/{skill-name}/SKILL.md`, the
  sibling of this skill's own directory — and follow it as written, under the gate policy
  above. Never search the disk for it.
- A file you Read is not loaded as a skill, so the host fills in neither of its two variables.
  Read the variable `CLAUDE_PLUGIN_ROOT` (written with `${` and `}` around it) as the plugin
  root, which is the part before `/skills/` in the path above. Read the variable `ARGUMENTS`
  (written with a `$` in front) as the value you hand that skill: the `design_id`, the
  `theme_id`, or nothing. In a shell command, write the path itself in its place: the shell
  does not have the variable.
- Never call the Skill tool for a delegated skill, and never ask the analyst to type its
  `/command`: carrying the steps is what this run is for.
- `design_io`, `catalog_io`, `tree_io` and `tree_check` are on PATH: call them
  by name, from the project directory.

## Workflow

### Step 1: Locate the position

Never `cd` anywhere before a `*_io` command: each one reads the `.insight` of the directory it
is run from.

1. Find the theme. A `theme_id` (`[A-Z][A-Z0-9]*`) is the theme. A `design_id`
   (`{theme_id}-H{nn}`) names its theme by its prefix; load it with
   `design_io get --id {design_id}`. With no argument, ask what the analyst wants decided, or
   what they want to research: there is no theme yet, so go to Step 2.
2. Read where the theme stands:

```bash
tree_io position --theme LIB
```

   It prints a `state`, and with a decision the `node_id` it names, every node it names
   (`node_ids`), the `design_ids` in play, and in `nodes` each design on those nodes with its
   analysis `stage`. Never work the position out yourself from the tree file, the dates or the journals.
   If it exits non-zero, show stderr and stop: a linked design is missing or unreadable, and
   the analyst has to fix it before the walk can go on.

| `state` | What it means | Enter at |
|---|---|---|
| `no_tree` | The theme has no question tree. stderr names the file it looked for: check that it is under this project's `.insight` | Step 2 |
| `no_decision` | A tree without a first node to investigate: an earlier framing stopped halfway | Step 2, item 3 (`/analysis-framing` finishes it: 4c, "An unfinished tree") |
| `not_started` | No design is unfinished, and `undesigned_node_ids` names the nodes of the latest decision with no design made on them since | Step 3, item 1 |
| `in_progress` | `design_ids` are the unfinished designs on the nodes the decision names (`node_ids`); a stopped one is not unfinished | Step 3, by the `stage` of each of them (below) |
| `concluded` | `design_ids` were made after the decision on its `node_ids`, and each is finished or stopped; the round lacks its theme reflection | Step 3, item 8 |
| `closed` | The analyst closed the walk at `node_id`, and no design was made on it since | Step 3, item 1 |

   A decision that names more than one node (`node_ids`) makes the round one of several nodes:
   whatever the `state`, short of `concluded`, it runs Step 3H from its first item, and each
   item there skips what no design calls for. A decision that names one node runs Step 3.

   For `in_progress` in a round of one node, read the `stage` of each design of `design_ids`
   in `nodes`. Never work the stage out yourself from the status of the design and its
   journal.

| `stage` | What it means | Enter Step 3 at |
|---|---|---|
| `before_run` | Saved, and not run yet | **review** or **premortem** |
| `running` | Moved into the analysis, with no result on record | **premortem** |
| `awaiting_confirmation` | It asked the analyst something and waits for the answer | **confirmation** of Step 3H, then **premortem** |
| `awaiting_reflection` | Its result is on record | **reflection** |

   With more than one unfinished design, carry the first and tell the analyst which ones wait.
3. A `design_id` of a theme that has a tree is never asked about: carry that design, entering
   the round at the item its stage calls for. If no node of the tree holds it, say so and run
   `/analysis-framing {theme_id}` first (4c, "Designs no node holds").
4. Tell the analyst the plan, naming every node of `node_ids` ("論点ツリーの {node_id} から、design→premortem→notebook→journal→
   reflection→テーマを横断した振り返り の順に進める。意図と探索の問いか検証仮説の確定・コスト判定・
   結論・論点ツリーの決定では止まる").

### Step 2: Build the tree (the theme has none)

1. **entry gate** (only when a `design_id` was given): this is a KEEP gate. Ask
   "このテーマには論点ツリーがない。ツリーを作って巡回に入るか、この分析設計だけを流すか" and wait.
   A design of a theme that has a tree is never asked this. The answer is not stored: whether
   the tree exists is the record.
   - Build the tree → go on to item 2.
   - Carry only this design → run Step 3 items 2–7 for it once, with no tree step (no
     item 1, 8 or 9), then go to Step 4.
2. **rq-problematization**: when the analyst brings a research theme and has no research
   question yet (they state none, and no RQ Brief is in the conversation), run
   `/rq-problematization` before framing. Its questions are its own gates. It ends with an RQ
   Brief, which `/analysis-framing` picks up. Skip this item for a business theme and for a
   theme that already has its research question. When it is unclear whether the theme is
   research, do not ask: go to framing, whose 4a gate settles the kind of the aim.
3. **framing**: run `/analysis-framing` in full. Its KEEP gates are 4a and 4b. The skill writes
   the tree, records the first node as the `start` decision, outputs the Framing Brief and
   renders the HTML.
4. Then read `tree_io position` again and enter Step 3 by its `state`, as in Step 1: an
   unfinished design that 4b placed on the first node makes it `in_progress`, and that design is
   carried instead of a new one. When the run started from a `design_id`, the round carries
   that design: enter the round at the item its stage calls for.

### Step 3: Walk the tree, one decision per round

A round takes the node of one decision from its design to the tree decision. For each item, **follow that
skill's SKILL.md** (do not duplicate its logic here) and apply the gate policy above. Repeat
the round until the analyst closes the walk or says stop.

1. **framing brief**: a design is made from the Framing Brief of its node. When the position
   is `not_started` or `closed` and that Brief is not in the conversation yet, run
   `/analysis-framing {theme_id}` and hand it the output of `tree_io position`, which its 4d
   reads. Skip this item when Step 2 has just output the Brief of that node.
2. **design**: run `/analysis-design`, auto-drafting fields from the agreed Framing Brief. Then **walk
   the four ordered confirmation beats — one AskUserQuestion each — before `design_io create`**, letting
   the user adjust at every beat. Do not collapse them into a single "looks good?"; don't silently commit
   auto-picked methodology / roles / query.
   1. **intent** — ask `analysis_intent` first, as `/analysis-design` Step 2 "Intent" does: exploration
      (`exploratory`) or confirmation (`confirmatory`), never `mixed`. The Brief's intent is only the
      suggestion. Then present the drafts of that form: `exploration_question` + `exploration_background`
      for an exploration, or `hypothesis_statement` + `hypothesis_background` for a confirmation. Ask for
      `decision_context` (who decides what — `/analysis-design` Step 2; the user may skip it); confirm.
   2. **methodology** — present `methodology` (method + code patterns), `metrics`, and especially the
      explanatory variables' causal roles (`treatment` / `confounder` / `covariate` / …); confirm. These
      shape the analysis and are genuine choices. For a confirmation, present the criterion of the
      verdict written in the `comparison` of the `primary` metric (`/analysis-design` Step 2 "Criterion")
      and confirm it here, before the data is touched. Explain the metrics before asking, as
      `/analysis-design` Step 2 "Metrics explained" does: say "どの指標にも、詳しい解説を求められます。",
      give every metric its one sentence, and give the five parts to a metric built from two or more
      quantities that is new to the theme, with example numbers that are not the result to be judged.
   3. **data-extraction** — present the design's `source_ids` (each checked as `/analysis-design`
      "Data sources" says) and the actual **data-acquisition plan**: for a SQL source, the query text
      drafted into `methodology.steps` (see `/analysis-design` Step 2.6); for a CSV/other source, the data source id
      + the columns/filter that will be read — plus the expected grain and a rough row-count. Confirm the
      pull *before* it is committed to the design, so premortem (item 4) estimates cost against the
      confirmed query. A source with no SQL still gets this beat as a data-acquisition plan.
   4. **charts** — present the planned `chart[]` specs (intent / type / x / y); confirm.

   After all four beats are confirmed, `design_io create` the design.

   `/analysis-design` then links the design to the Brief's `node_id` and copies an answer the
   analyst heard into its journal. A design left unlinked never shows in the tree: if the link
   fails, stop and show the error.
3. **review** (optional): if the user wants a review pass, run `/analysis-review`; **pause on the verdict**.
4. **premortem**: always run `/premortem` before touching data. If `HARD_BLOCK`/`HIGH`, **stop** and
   surface the risk (`source not registered` → offer /catalog-register; `no data source declared` →
   offer /analysis-design to fill `source_ids`; `package outside allowlist` → offer to declare the
   package in `.insight/rules/package_allowlist.yaml` (list only that package); cost/location → let
   the user decide).
   If `LOW`/`MEDIUM`, continue.
5. **notebook**: run `/analysis-notebook`. The declared source(s) are the ids in the design's
   `source_ids`. Auto-run only when premortem cleared **and** the analysis is
   confined to the declared source(s) + allowlisted packages + local computation. The allowlist is
   the default allowlist in the notebook contract plus `.insight/rules/package_allowlist.yaml`
   (ADR-0027). If the methodology needs a non-allowlisted package, network egress beyond the
   declared source, or another side-effect, **stop** and get the user's go-ahead first.
6. **journal**: the notebook step already records observe/evidence/question — no pause.
7. **reflection**: run `/analysis-reflection {design_id}`; **pause at its third question,
   この分析設計をどう終えるか**, and at the terminal transition. An exploration ends as
   `explored` and is never asked for a verdict. Its Step 2 読むもの says what
   the analyst reads; the driver adds no list of files of its own.
8. **theme reflection**: run `/analysis-reflection {theme_id}`. Its Steps T3 and T7 are the
   KEEP gates of the round. Before that gate, show the path of the tree's HTML, so the analyst decides
   with the tree in view. When the analyst chooses 主題そのものを見直す at that gate, the
   reflection runs only 4c of `/analysis-framing {theme_id}`, a KEEP gate of its own. The
   round is not over then: after the revision the reflection asks the decision again at
   Step T7, and the walk goes on from that decision.
9. **next round**: after a `deepen` or a `return` the walk goes on: read `tree_io position`
   again and start the next round at item 1, in the same turn, or at Step 3H when the
   decision names several nodes (Step 1). Do not summarize in between, and
   never tell the analyst to run `/analysis-auto` again to continue: a decision that names the
   next node is the go-ahead for it. After a `close`, go to Step 4. When the analyst leaves the
   decision open or says stop, go to Step 4 as well: the tree keeps its last decision, and the
   next run resumes from it.

Three things happen only when the analyst asks for them, at any point of the walk, in Step 3H
as well:

- **The root question or the aim changes** → run `/analysis-framing {theme_id}`, whose KEEP
  gate is 4c, "The root question or the aim". Then read `tree_io position` again. Inside a
  round the analyst reaches the same gate from Step T7 (item 8); never offer it yourself
  anywhere else.
- **The analyst asks to hand the tree over by URL** → run `/tree-upload {theme_id}`. Do not
  ask whether to send: the skill lists the file and waits at its own KEEP gate, the only
  question about it. Never answer it for them
  ([ADR-0016](../../docs/adr/0016-approval-before-external-send.md)). Never start it unasked.
- **The analyst asks to stop an analysis** → do what *Stopping an analysis* of Step 3H says,
  in a round of one node as well. Never stop an analysis unasked.

### Step 3H: Hand several nodes over together

A round of several nodes runs this step in place of **framing brief** to **reflection** of
Step 3. Each design then runs in an execution agent of its own: a subagent you start in this
conversation and hand one design.

You are the dialogue agent. The dialogue agent alone writes the question tree, the designs
and the tree's HTML, one write after another. An execution agent writes only the notebook,
the verdict and the journal of its own design
([ADR-0062](../../docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)).

Go through the items in order, on a first run and on a resumed one. Each names the designs
it acts on by their `stage` in `tree_io position`, and is skipped when there are none.

1. **briefs** (nodes of `undesigned_node_ids`): every node without a design needs one. Run
   `/analysis-framing {theme_id}` and hand it the output of `tree_io position`: its 4d takes
   those nodes as the answer and outputs a Framing Brief for each.
2. **designs** (the same nodes): for each Brief, in the order of `node_ids`, run
   `/analysis-design` through its Step 3: create the design, link it to its node, copy what
   the analyst heard. Draft every field from the Brief. The four beats are not asked: the
   analyst reads what they confirm at **check before handing over**
   ([ADR-0063](../../docs/adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md)).
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
   - Show the `path` that `render` printed and say that its section 「分析を任せる前の確認」
     lays the designs side by side. Then sum up `differing`: for each row its `label`, and
     the `values` of each design (say `not_written` as the page does, 書かれていない). Never
     compare the values yourself: the page marks the same rows as 分析間の違い. When
     `differing` is empty, say that the page marks no difference.
   - Ask one question and wait: hand the designs over as they are, comment on a design, or
     leave a design out. For comments, the analyst writes them on the page, presses
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
   same message so that they run side by side. Give each the brief below. Start them in the
   background when the host lets you, so that each return reaches you on its own.
6. **return** (a design whose execution agent came back): each time one or more agents
   have returned, without waiting for the others, rebuild the page and read where the round
   stands:

```bash
tree_io render --theme LIB
tree_io position --theme LIB
```

   The dialogue agent alone rebuilds the page; an execution agent never does
   ([ADR-0062](../../docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)).
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
     after. A design that began its analysis keeps its hypothesis and the criterion of its
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
   - Then ask one question for all of them and wait. Under a heading for each design, with
     its id and title, put the three questions of `/analysis-reflection` Step 3 as that step
     words them for the form of the design; the third is この分析設計をどう終えるか, with
     its choices. Add no question of your own, and leave none out. Say in the same question
     what Step 4 would ask of a design that ends (a review of its result first, the
     tentative answer of an exploration, the change of its status), so that Step 4 asks
     nothing again. The analyst answers for all the designs in one reply.
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

#### The brief of an execution agent

An execution agent knows nothing of this conversation. Write its brief from these lines:

- The `design_id`, and the project directory: it runs every command from there and never
  `cd`s before a `*_io` command.
- What to do: Read `{plugin root}/skills/analysis-notebook/SKILL.md`, with the plugin root
  written out as its path, and follow it for this design: build the notebook, run it, and
  record its verdict in the journal. The design is already `analyzing` and its premortem
  has cleared.
- What it writes: only the notebook, the verdict and the journal of this design. The
  journal goes in through `design_io journal-append` and `design_io ask-analyst`, never by
  writing the file.
- What it never runs: any `design_io` command that writes a design (`create`, `update`,
  `transition`, `review-batch`, `stop`), `design_io answer-analyst`, and any `tree_io`
  command that writes. Never `tree_io render` either: the dialogue agent rebuilds the page.
- Where it stops: the analyst read this design before it was handed over. When the
  analysis cannot go on without changing something they read (its population, grain or
  denominator, its extraction, a source, its primary metric, the criterion of its
  verdict), it stops before it touches the data, records what it would have to change
  with `design_io ask-analyst`, and returns. It never asks the analyst anything itself:

```bash
echo '{"content": "予約の記録が2025年10月より前に無い。対象を2025年10月以降の予約に変えてよいか"}' | design_io ask-analyst --id LIB-H05
```

  After the confirmation it records nothing more: `design_io journal-append` refuses an
  analysis that waits for the analyst. Before a package outside the allowlist or any other
  side effect, it does not do that thing either: it returns and says what it needs, with no
  confirmation in the journal.
- What it returns: the `design_id`, and one of three: that the verdict is in the journal,
  the `id` of the confirmation it recorded, or why it stopped.

### Step 4: Summarize

Report what ran automatically, where it paused and why, and the final state (status, journal, lineage).
For the walk, add the nodes it went through, the tree decisions the analyst took, the path of
the tree's HTML, and the node the next `/analysis-auto {theme_id}` resumes from.
When the theme has a question tree, name `/report-export {theme_id}` as the skill to use next
once the analyst judges the theme ready to report: it writes the theme's report and exports it
to Claude Docs. Never start it, and do not ask whether to export
([ADR-0040](../../docs/adr/0040-report-export-sends-the-report-to-claude-docs.md)).

## Delegated skills

`/rq-problematization`, `/analysis-framing`, `/analysis-design`, `/analysis-review`, `/premortem`,
`/analysis-notebook`, `/analysis-journal`, `/analysis-reflection`, `/tree-upload`, `/catalog-register` — each remains explicit-invocable on its own; `/analysis-auto` only
sequences them and enforces the gate policy. It never writes the question tree itself: the skills do,
through `tree_io`. In Step 3H it writes the designs' review comments, their changes, their
stops and the analyst's answers through `design_io`, and rebuilds the page.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-auto | → /rq-problematization | A research theme has no research question yet |
| /analysis-auto | → /analysis-framing | The theme has no tree, the round needs the Framing Brief of its node, or the root changes |
| /analysis-auto | → /analysis-design | The node of the round needs its design |
| /analysis-auto | → /analysis-reflection | Autopilot reaches results; the conclusion and the tree decision are the user's call |
| /analysis-auto | → /tree-upload | The analyst asks to hand the tree over; its own approval gate is the only question |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
