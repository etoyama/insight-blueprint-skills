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
mechanism, but concluding a design is the job of `/analysis-reflection`. For a confirmation
whose analysis has not started, `supported` and `rejected` need the criterion written in the
design, as `analyzing` does; `inconclusive` does not (Step 5).

A review of the result after the analysis is optional and goes the same way: the `analyzing`
design moves back to `in_review` (Step 2), and approving it returns it to `analyzing`. The
analyst then concludes it with `/analysis-reflection`, not by analyzing again.

A review of the result reads what the check of the computation does not (ADR-0071): the
value against its judgment, the figures, the guardrails, and the interpretation with its
confounders (Step 3b). Whether the notebook computed what the design says is the check's to
read, and `/analysis-reflection` Step 2 runs it before the analyst reads.

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

- **The value and the judgment** — is there a value that contradicts the `judgment` it sits
  next to? A line keeps only its number and points the way the `comparison` says, so read
  the value against the lines that way: a value past the `support_line` with
  `judgment: rejected`, one past the `reject_line` with `judgment: supported`, an interval
  that crosses a line with a firm judgment. Point out the contradiction; never compute a new
  judgment.
- **The figures** — does each figure state what each axis shows and how to read it, and does it
  show what the verdict says?
- **The guardrails** — did each guardrail metric `pass` its `threshold`? A failed guardrail
  next to `supported` must be said.
- **The interpretation and its confounders** — is there another explanation of the result
  than the one the verdict gives (a confounder the design names or misses, a difference
  between the groups other than the one compared, a change in the period), and how far does
  the result reach (the population, the period, an association said as a cause)? Name the
  explanation or the limit; never test it with the data.

Whether the line a notebook copied matches the `comparison` and whether the order of its cells
is the 7-cell contract of `/analysis-notebook` are what the check of the computation reads,
before the analyst reads, in `/analysis-reflection` Step 2 (ADR-0071 6). Leave both to it: a
comment on them here would say again what the check says. Read
`design_io checked --id {design_id}` first: while it does not say `checked: true` (the check
has not run, or could not be recorded), read the line the notebook copied against the
`comparison` as well, and tell the analyst the check of the computation is not done, since
nothing else reads the line until it is.

An exploration has no criterion: it carries no line, no judgment, no threshold and no pass
(ADR-0050). Read its verdict with the figures and the interpretation lenses only.

A design with a verdict but no `analysis_started_at` was saved before the analysis mark
existed and reads as not started (ADR-0053). Tell the analyst so: the batch is recorded as
before the analysis, and the design does not keep its hypothesis, criterion or intent.

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

An approval that would let a confirmation, a legacy exploration or a `mixed` design into
`analyzing` without a `primary` metric whose `comparison` states the criterion is refused
(ADR-0053), and no batch is recorded. Tell the analyst the criterion is missing and send them
to `/analysis-design {design_id}` to write the `comparison`; then record the review again.

The same holds for a verdict of the hypothesis: `--status supported` or `--status rejected` on
such a design whose analysis has not started is refused, and no batch is recorded. A hypothesis
is not supported or rejected without a criterion on record. Offer the analyst the two ways
out: write the criterion with `/analysis-design {design_id}` and record the review again, or
close the design without a verdict of the hypothesis with `--status inconclusive`, which
needs no criterion.

### Step 6: Rebuild the design note

Run `tree_io render --design {design_id}` so that the design note shows the batch you
recorded, and tell the analyst where the note is: read the JSON it prints as the
`#### 読むもの` of /analysis-reflection says, and show its `分析ノート:` line. This step is
not a gate: ask nothing. If the render exits non-zero, show its stderr; the batch of Step 5
stays recorded.

### Step 7: Hand off

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
