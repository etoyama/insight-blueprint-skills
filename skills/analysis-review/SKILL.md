---
name: analysis-review
version: "1.1.0"
description: |
  Produces a structured review of an analysis design and records it as a review batch.
  Claude critiques the design (question or hypothesis, methodology, metrics, confounders, charts)
  and, after the analysis, the result (notebook, verdict, figures),
  the user confirms the comments, and they are written via design_io review-batch with a
  post-review status — feeding /analysis-revision. The producer side of the review loop
  (there is no web UI).
  Triggers: "レビューして", "design をレビュー", "批評して", "review this design",
  "review design", "レビュー依頼".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-review — Analysis Design Review (producer)

Generates a peer-style review of an analysis **design** and records it as a review batch,
so `/analysis-revision` can work through the comments. This is the **producer** side of the
review loop; `/analysis-revision` is the **consumer**. With no web UI, reviews are created
here (via `design_io review-batch`) rather than submitted through a dashboard.

## When to Use

- A design is drafted and you want a critical review before investing in analysis
- After addressing revisions, to record a fresh review decision
- You (or a collaborator) want structured, section-targeted feedback captured in the design's history

## When NOT to Use

- Addressing / fixing existing review comments (-> /analysis-revision)
- Creating or editing the design itself (-> /analysis-design)
- Drawing your own conclusion from the evidence (-> /analysis-reflection). This skill records a
  *reviewer's* critique, not the analyst's self-reflection.

## Scope

Primarily a **design/plan review**: the outcome is `revision_requested` (needs work) or
`analyzing` (approved — go analyze). Terminal decisions (`explored` for an exploration,
`supported` / `rejected` / `inconclusive` for a confirmation) are possible through the same
mechanism, but concluding a design is the job of `/analysis-reflection`.

A review of the result after the analysis is optional and goes the same way: the `analyzing`
design moves back to `in_review` (Step 2), and approving it returns it to `analyzing`. The
analyst then concludes it with `/analysis-reflection`, not by analyzing again.

## Workflow

### Step 1: Load the design

1. Identify the design: use `$ARGUMENTS` if given, else
   `design_io list --status in_review` and let the user pick.
2. `design_io get --id {design_id}` — load content + status.

### Step 2: Ensure the design is reviewable

A review batch can only be recorded when the design is **reviewable** (`in_review` or
`revision_requested`).

- `in_review` / `revision_requested` → proceed.
- `analyzing` → ask "in_review に戻してレビューする？"; if yes,
  `design_io transition --id {design_id} --target in_review`.
- terminal (`explored` / `supported` / `rejected` / `inconclusive`) → cannot review; inform and exit.

### Step 3: Critique the design (Claude-native)

Review across dimensions and draft one comment per issue. Each comment targets a section
(`target_section`) drawn from the allowed set:

`exploration_question`, `exploration_background`, `hypothesis_statement`,
`hypothesis_background`, `metrics`, `explanatory`, `chart`, `next_action`,
`referenced_knowledge`, `methodology`, `analysis_intent`, `decision_context`,
`notebook`, `verdict`, `figures`. The last three are the result: use them only in a review
after the analysis (Step 3b).

When `.insight/notebooks/{design_id}_verdict.json` exists, the analysis has run: this is a
review of the result. Read the design with the lenses below, then go through Step 3b before
Step 4.

Suggested lenses:

Read `analysis_intent` first: the lenses differ by intent. An exploration (`exploratory` with
`exploration_question`) measures and answers and gives no verdict; a confirmation
(`confirmatory`) fixes a hypothesis and its criterion before the analysis. A legacy exploration
(`exploratory` with `hypothesis_statement`) is read with the confirmation lenses; when it is in
fact a confirmation, a comment on `analysis_intent` may suggest setting it to `confirmatory`.

- **exploration_question** (exploration) — is it narrower than the question node it answers,
  and does it say what is measured? Has a guess of the answer or a criterion slipped into the
  question, the background or a metric's `comparison`? An exploration carries neither.
- **hypothesis_statement** (confirmation) — is it falsifiable, specific, and non-circular? Is the
  criterion of the verdict written in the `comparison` of the `primary` metric, so the verdict is
  fixed before the result is seen?
- **decision_context** — both intents may have one. When the design has one, does it fit the
  question or the hypothesis? For an exploration: does the question measure what the `decision`
  needs? For a confirmation: would `supported` and `rejected` lead the `decision_maker` to
  different choices on the `decision`, and does `next_action` agree with it? The field is
  optional: a design without one is not an issue to raise.
- **methodology** — is the method appropriate; are assumptions stated?
- **explanatory** — are variable roles (treatment/confounder/covariate/…) correct; missing confounders?
- **metrics** — do they actually measure the question or the hypothesis; primary vs guardrail?
- **chart** — does the chart intent match the claim?
- **referenced_knowledge / analysis_intent / next_action** — grounded and coherent?

Comment shape (for the payload in Step 5). Two valid forms:

```json
// section-targeted: target_section AND target_content are BOTH required
{"target_section": "methodology", "target_content": "OLS", "comment": "OLS assumes homoscedasticity; residuals look funnel-shaped — consider robust SE."}

// general comment: omit target_section (and target_content)
{"comment": "The overall framing mixes exploratory and confirmatory goals."}
```

Contract (`BatchComment`, enforced by `design_io`): `comment` is required and non-empty;
if you set `target_section` you MUST also set `target_content` (a snippet of what the
comment refers to); for a comment not tied to a section, omit `target_section` entirely.

### Step 3b: Critique the result (when a verdict exists)

Before the critique, tell the analyst what you read, in one short list:

- the notebook `.insight/notebooks/{design_id}.py`
- the verdict `.insight/notebooks/{design_id}_verdict.json`
- the figures `.insight/notebooks/{design_id}_fig*.png` (the ones the verdict's `figures` lists)
- the `comparison` of each metric in the design

Then read the result with these lenses, one comment per issue:

- **The criterion** — do the `support_line` and the `reject_line` of each `primary` metric
  carry the numbers its `comparison` states, and does the `judgment` follow from them? A
  notebook that copied a line wrong still runs, so this is where it is caught.
- **The value and the judgment** — is there a value that contradicts the judgment it sits next to
  (a value above the support line with `judgment: reject`, an interval that crosses a line
  with a firm judgment)? Point out the contradiction; never compute a new judgment.
- **The figures** — does each figure state what each axis shows and how to read it, and does it
  show what the verdict says?
- **The guardrails** — did each guardrail metric `pass` its `threshold`? A failed guardrail
  next to `supported` must be said.
- **The cells** — does each cell keep one job per cell (the 7-cell contract of
  `/analysis-notebook`), so the criterion, the computation and the verdict can be read apart?

An exploration has no criterion: it carries no line, no judgment and no pass (ADR-0050).
Read its verdict with the last three lenses only.

A comment on the result targets `notebook` (a cell), `verdict` (a metric of the verdict) or
`figures` (a figure), with the snippet it points at as `target_content`. A comment on the
hypothesis, the criterion or the intent of a started confirmation is still recorded, but the
design keeps them (ADR-0053): `/analysis-revision` answers it without changing them.

### Step 4: Confirm with the user

Present the draft comments as a table (section / comment) and let the user drop, edit, or add.
Do not record unconfirmed comments. Then agree on the decision:

- **revision_requested** — issues must be addressed before analyzing.
- **analyzing** — approved; proceed to analysis.

### Step 5: Record the review batch

Pipe the confirmed comments and record the decision. This writes the batch to
`{design_id}_reviews.yaml` and transitions the design in one step:

```bash
echo '{
  "comments": [
    {"target_section": "hypothesis_statement", "target_content": "A improves B", "comment": "..."},
    {"target_section": "methodology", "target_content": "OLS", "comment": "..."},
    {"comment": "General note not tied to a section."}
  ],
  "reviewer": "analyst"
}' | design_io review-batch --id {design_id} --status revision_requested
```

Use `--status analyzing` to approve instead. Show the returned batch to the user.

An approval that would let a confirmation into `analyzing` without a `primary` metric whose
`comparison` states the criterion is refused (ADR-0053), and no batch is recorded. Tell the
analyst the criterion is missing and send them to `/analysis-design {design_id}` to write the
`comparison`; then record the review again.

### Step 6: Hand off

- `revision_requested` → "指摘に対応するなら /analysis-revision {design_id}"
- `analyzing` → "分析を始めるなら /analysis-journal {design_id}"（結果のレビューなら "結論を出すなら /analysis-reflection {design_id}"）

## design_io Reference

`design_io <command>` (available on PATH via the plugin):

| Command | Used for |
|---------|----------|
| `list --status in_review` | Find designs awaiting review |
| `get --id ID` | Load design content + status |
| `transition --id ID --target in_review` | Make an `analyzing` design reviewable |
| `review-batch --id ID --status S` (stdin JSON) | Record comments + transition to `S` |
| `list-reviews --id ID` | Inspect existing review batches |

Validation (reviewable status, allowed `target_section`, non-empty comments, valid
`status_after`) runs inside `design_io` before writing; invalid input exits non-zero.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-design | -> /analysis-review | Design drafted: "作った design をレビューするなら /analysis-review {id}" |
| /analysis-review | -> /analysis-revision | revision_requested: "指摘に対応するなら /analysis-revision {id}" |
| /analysis-review | -> /analysis-notebook | analyzing (approved): "分析を実行するなら /analysis-notebook {id}" |
| /analysis-review | -> /analysis-journal | analyzing (approved): "分析を始めるなら /analysis-journal {id}" |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Review comments follow the user's language (usually Japanese).
