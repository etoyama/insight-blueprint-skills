---
name: analysis-auto
version: "1.0.0"
description: |
  Guided autopilot and the analyst's single entry. Takes a theme, builds its question tree
  (or resumes at the node the latest tree decision names) and walks the tree one node per round:
  design → review → premortem → notebook → journal → reflection → report → upload →
  theme reflection → tree decision. Progresses automatically through low-friction steps and
  pauses only at genuine decision points (root question and aim, the node to investigate,
  hypothesis, source registration, cost/risk, code with external effects, conclusion, the tree
  decision, sending anything outside this machine).
  Triggers: "オートで進めて", "自動で分析を回して", "autopilot", "guided auto",
  "最後まで進めて", "analysis auto", "論点を順に調べて".
disable-model-invocation: true
argument-hint: "[theme_id | design_id]"
---

# /analysis-auto — Guided Autopilot (driver)

The one entry for the analyst. It takes a theme, keeps the theme's question tree, and
investigates the tree one node per round, so you type no `/command` between the steps. It
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
| framing ① root question and aim | **`theme_id`, the root question and the aim** (`/analysis-framing` 4a) | agentic exploration of `.insight/`; the Data Map; drafting the root question |
| framing ② first node | **the first-level nodes, the first node to investigate with the reason, and the node each existing design belongs to** (4b) | drafting the nodes; writing the tree, the Framing Brief and the HTML once the analyst has answered |
| framing ③ root revision | **whether a changed root question or aim raises the root revision, and the reason** (4c) | — |
| framing ④ next node | **the node to design next, when the position is `closed`** (4d) | when the position is `not_started`: the latest decision is the answer, so the Framing Brief of its node |
| design ① hypothesis | **confirm the hypothesis statement + background, and the decision context (who decides what; skippable)** | drafting them from the Framing Brief |
| design ② methodology | **confirm the method + metrics + explanatory roles (treatment/confounder/…) + intent** | auto-drafting these fields from the Framing Brief |
| design ③ data-extraction | **confirm the data-acquisition plan** — the actual query text (`methodology.steps`, with each table as `{source:ID}`) for SQL sources, or the data source id + columns + filter for CSV/others, plus expected grain & rough row scale | auto-drafting the query / column selection from the catalog schema |
| design ④ charts | **confirm the planned `chart[]` specs (intent / type / x / y)** | auto-drafting chart specs from the direction |
| review (optional) | **the verdict** (revision_requested vs approve) | running the critique itself |
| premortem | **result is `HARD_BLOCK`/`HIGH`** → stop, surface the risk | running premortem; `LOW`/`MEDIUM` |
| notebook | **non-allowlisted package / external comms beyond the declared source / other side-effects** | generate + run when premortem cleared AND it's declared-source read + allowlisted + local compute |
| journal | — | auto-record the notebook verdict (observe/evidence/question) |
| reflection | **the conclusion (conclude/refine/branch) + terminal transition** | presenting the evidence summary |
| report | — | writing the report with `/analysis-report` once the design is in a terminal status |
| upload | **the files to send to Claude Docs** — asked by `/report-upload` itself, at its approval gate; the driver adds no question of its own | starting `/report-upload` once the report is written |
| theme reflection | **the tree decision (deepen / return / close, the next node, the reason) and any answer the analyst heard** (`/analysis-reflection {theme_id}` T7) | writing the current answers, the tree check, the next candidates, the HTML |
| tree-upload | **the file to send as an Artifact** — asked by `/tree-upload` itself, at its approval gate; the driver adds no question of its own | starting `/tree-upload` when the analyst asks to hand the tree over |
| catalog-register | **registering a data source** (external-data side-effect); unregistered source → stop | — |

The four `design ①–④` beats are **ordered confirmation gates** run before `design_io create`
(and therefore before premortem): each is presented as its own AskUserQuestion so the user can
adjust it, rather than collapsing the whole design into a single "looks good?". Beat ③
(data-extraction) is where the *actual data pull* — the SQL query or the CSV file+columns+filter —
gets a seat, so premortem then estimates cost against the **confirmed** query.

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
- `design_io`, `catalog_io`, `tree_io`, `tree_check` and `report_check` are on PATH: call them
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

   It prints a `state`, and with a decision the `node_id` it names and the `design_ids` in
   play. Never work the position out yourself from the tree file, the dates or the journals.
   If it exits non-zero, show stderr and stop: a linked design is missing or unreadable, and
   the analyst has to fix it before the walk can go on.

| `state` | What it means | Enter at |
|---|---|---|
| `no_tree` | The theme has no question tree. stderr names the file it looked for: check that it is under this project's `.insight` | Step 2 |
| `no_decision` | A tree without a first node to investigate: an earlier framing stopped halfway | Step 2, item 3 (`/analysis-framing` finishes it: 4c, "An unfinished tree") |
| `not_started` | The latest decision names `node_id`, and no design was made on it since | Step 3, item 1 |
| `in_progress` | `design_ids` are the unfinished designs on `node_id` | Step 3, at the item the first of them calls for |
| `concluded` | `design_ids` were made after the decision and are all finished; the round lacks its theme reflection | Step 3, item 8 |
| `closed` | The analyst closed the walk at `node_id`, and no design was made on it since | Step 3, item 1 (`/analysis-framing` asks which node to resume, 4d) |

   For `in_progress`, read the design with `design_io get --id {design_id}`:
   `in_review` / `revision_requested` → item 3 or 4. For `analyzing`, read the journal: no event
   other than `hearing` → item 4; any other event → item 7. A `hearing` event is the answer
   `/analysis-design` copied in before premortem, so it does not mean the analysis ran.
   With more than one unfinished design, carry the first
   and tell the analyst which ones wait.
3. A `design_id` of a theme that has a tree is never asked about: carry that design, entering
   Step 3 at the item its status calls for. If no node of the tree holds it, say so and run
   `/analysis-framing {theme_id}` first, which asks where it belongs (4c, "Designs no node holds").
4. Tell the analyst the plan ("論点ツリーの {node_id} から、design→premortem→notebook→journal→
   reflection→レポート→テーマを横断した振り返り の順に進める。仮説の確定・コスト判定・結論・ツリーの決定では
   止まる。結論が出たらレポートは聞かずに書く。外へ送る前には、送るファイルを見せて承認を待つ").

### Step 2: Build the tree (the theme has none)

1. **entry gate** (only when a `design_id` was given): this is a KEEP gate. Ask
   "このテーマには論点ツリーがない。ツリーを作って巡回に入るか、この分析設計だけを流すか" and wait.
   A design of a theme that has a tree is never asked this. The answer is not stored: whether
   the tree exists is the record.
   - Build the tree → go on to item 2.
   - Carry only this design → run Step 3 items 2–9 for it once, with no tree step (no
     item 1, 10 or 11), then go to Step 4.
2. **rq-problematization**: when the analyst brings a research theme and has no research
   question yet (they state none, and no RQ Brief is in the conversation), run
   `/rq-problematization` before framing. Its questions are its own gates. It ends with an RQ
   Brief, which `/analysis-framing` picks up. Skip this item for a business theme and for a
   theme that already has its research question. When it is unclear whether the theme is
   research, do not ask: go to framing, whose 4a gate settles the kind of the aim.
3. **framing**: run `/analysis-framing` in full — explore `.insight/`, present the **Data Map**,
   and hold its two KEEP gates: the `theme_id`, the root question and the aim (4a), then the
   first-level nodes and the first node to investigate (4b). When the theme has existing designs,
   4b also asks which node each of them belongs to. Do not silently pick any of these — this
   is where the analyst's intent gets elicited. The skill writes the tree, records the first node
   as the `start` decision, outputs the Framing Brief and renders the HTML.
4. Then read `tree_io position` again and enter Step 3 by its `state`, as in Step 1: an
   unfinished design that 4b placed on the first node makes it `in_progress`, and that design is
   carried instead of a new one. When the run started from a `design_id`, the round carries
   that design: enter Step 3 at the item its status calls for.

### Step 3: Walk the tree, one node per round

A round takes one node from its design to the tree decision. For each item, **follow that
skill's SKILL.md** (do not duplicate its logic here) and apply the gate policy above. Repeat
the round until the analyst closes the walk or says stop.

1. **framing brief**: a design is made from the Framing Brief of its node. When the position
   is `not_started` or `closed` and that Brief is not in the conversation yet, run
   `/analysis-framing {theme_id}` and hand it the output of `tree_io position`. For
   `not_started` the skill takes the node of the latest decision without asking again; for
   `closed` it asks which node to resume (4d). Skip this item when Step 2 has just output the
   Brief of that node.
2. **design**: run `/analysis-design`, auto-drafting fields from the agreed Framing Brief. Then **walk
   the four ordered confirmation beats — one AskUserQuestion each — before `design_io create`**, letting
   the user adjust at every beat. Do not collapse them into a single "looks good?"; don't silently commit
   auto-picked methodology / roles / query.
   1. **hypothesis** — present the drafted `hypothesis_statement` + `hypothesis_background`, and ask for
      `decision_context` (who decides what — `/analysis-design` Step 2; the user may skip it); confirm.
   2. **methodology** — present `methodology` (method + code patterns), `metrics`, and especially the
      explanatory variables' causal roles (`treatment` / `confounder` / `covariate` / …) + `analysis_intent`;
      confirm. These shape the analysis and are genuine choices.
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
7. **reflection**: run `/analysis-reflection {design_id}`; **pause at the conclusion**
   (conclude/refine/branch) and the terminal transition.
8. **report**: when the design is in a terminal status (`supported` / `rejected` /
   `inconclusive`), run `/analysis-report {design_id}` without asking; the report is a file on
   this machine. A report that is already there (`.insight/reports/{design_id}.md`) is not
   written again: say so, and that `/report-upload {design_id}` is theirs to run if it was
   never sent. When the design is not in a terminal status (refine or branch), write no report
   and go to item 10.
9. **upload**: when item 8 wrote the report, run `/report-upload {design_id}` right after it.
   **Do not ask whether to upload**, before or after starting the skill. The skill lists the files it
   would send and waits at its own KEEP gate; that is the only question the analyst gets about the
   upload. Never answer it for them, and never treat an earlier "yes" as a "yes" to the upload
   ([ADR-0016](../../docs/adr/0016-approval-before-external-send.md)). Without the Claude Docs
   connector the skill sends nothing and asks nothing; go on to the theme reflection. Skip this item
   when no report was written. Keep the skill's one-line outcome for item 10 and the summary.
10. **theme reflection**: run `/analysis-reflection {theme_id}`. It writes the current answer
    of each node, checks them, shows the next candidates and renders the HTML without asking. Its
    Step T7 is the KEEP gate of the round. Before that gate, show the report's path next to the
    path of the tree's HTML, so the analyst decides with both in view. The report is the one of
    this round's design, also when an earlier run wrote it; add the upload outcome when this run
    has one. A round without a conclusion has no report: say so. Never choose the kind, the node or the reason for them, and never
    fill in an answer they heard.
11. **next round**: after a `deepen` or a `return` the walk goes on: read `tree_io position`
    again and start the next round at item 1, in the same turn. Do not summarize in between, and
    never tell the analyst to run `/analysis-auto` again to continue: a decision that names the
    next node is the go-ahead for it. After a `close`, go to Step 4. When the analyst leaves the
    decision open or says stop, go to Step 4 as well: the tree keeps its last decision, and the
    next run resumes from it.

Two things happen only when the analyst asks for them, at any point of the walk:

- **The root question or the aim changes** → run `/analysis-framing {theme_id}`. Whether the
  root revision goes up is its KEEP gate (4c, "The root question or the aim"). Then read
  `tree_io position` again.
- **The analyst asks to hand the tree over by URL** → run `/tree-upload {theme_id}`. Do not
  ask whether to send: the skill lists the file and waits at its own KEEP gate, the only
  question about it. Never answer it for them
  ([ADR-0016](../../docs/adr/0016-approval-before-external-send.md)). Never start it unasked.

### Step 4: Summarize

Report what ran automatically, where it paused and why, and the final state (status, journal, lineage).
For the walk, add the nodes it went through, the tree decisions the analyst took, the path of
the tree's HTML, and the node the next `/analysis-auto {theme_id}` resumes from.
When a report was written, add the report's path and the upload outcome: the Doc URL, "承認されなかった",
"コネクタが無い", or "アップロードに失敗した" with the reason.

## Delegated skills

`/rq-problematization`, `/analysis-framing`, `/analysis-design`, `/analysis-review`, `/premortem`,
`/analysis-notebook`, `/analysis-journal`, `/analysis-reflection`, `/analysis-report`, `/report-upload`,
`/tree-upload`, `/catalog-register` — each remains explicit-invocable on its own; `/analysis-auto` only
sequences them and enforces the gate policy. It never writes the question tree itself: the skills do,
through `tree_io`.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-auto | → /rq-problematization | A research theme has no research question yet |
| /analysis-auto | → /analysis-framing | The theme has no tree, the round needs the Framing Brief of its node, or the root changes |
| /analysis-auto | → /analysis-design | The node of the round needs its design |
| /analysis-auto | → /analysis-reflection | Autopilot reaches results; the conclusion and the tree decision are the user's call |
| /analysis-auto | → /analysis-report | The design reached a terminal status; the report is written without asking (AUTO) |
| /analysis-auto | → /report-upload | The report is written; start the upload, whose own approval gate is the only question |
| /analysis-auto | → /tree-upload | The analyst asks to hand the tree over; its own approval gate is the only question |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
