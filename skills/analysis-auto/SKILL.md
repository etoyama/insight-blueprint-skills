---
name: analysis-auto
version: "1.0.0"
description: |
  Guided autopilot for the hypothesis→analysis pipeline. Drives the existing skills
  (framing → design → review → premortem → notebook → journal → reflection) in sequence,
  progressing automatically through low-friction steps and pausing only at genuine decision
  points (hypothesis, source registration, cost/risk, code with external effects, conclusion).
  Triggers: "オートで進めて", "自動で分析を回して", "autopilot", "guided auto",
  "最後まで進めて", "analysis auto".
disable-model-invocation: true
argument-hint: "[theme_id | design_id]"
---

# /analysis-auto — Guided Autopilot (driver)

Drives the analysis pipeline so you don't type a `/command` at every step. It **orchestrates
the existing skills** (it does not reimplement them) and **stops only at genuine decisions**.
Autonomy is scoped to this run — the individual skills stay explicit/interactive everywhere else.
See [ADR-0005](../../docs/adr/0005-selective-autonomous-chaining.md).

## When to Use

- You have (or are about to frame) a hypothesis and want Claude to carry it through to results
  with minimal manual dispatch, pausing for your judgment where it matters.

## When NOT to Use

- You want to run a single step (use that step's `/command` directly).
- Unattended / headless batch execution — this is **not** that. It is interactive; it stops at
  the gates below and waits for you.

## Gate policy

The whole point is *reduce friction, keep judgment*. The driver enforces:

| Step | KEEP — pause for the user | AUTO — proceed without asking |
|------|---------------------------|-------------------------------|
| framing | **present the Data Map + candidate directions and settle the direction with the user** (Direction Dialogue) | agentic exploration of `.insight/`; Framing Brief construction once the direction is agreed |
| design | **confirm the drafted hypothesis once** | auto-draft fields from the Framing Brief; Step-0 "proceed?" |
| review (optional) | **the verdict** (revision_requested vs approve) | running the critique itself |
| premortem | **result is `HARD_BLOCK`/`HIGH`** → stop, surface the risk | running premortem; `LOW`/`MEDIUM` |
| notebook | **non-allowlisted package / external comms beyond the declared source / other side-effects** | generate + run when premortem cleared AND it's declared-source read + allowlisted + local compute |
| journal | — | auto-record the notebook verdict (observe/evidence/question) |
| reflection | **the conclusion (conclude/refine/branch) + terminal transition** | presenting the evidence summary |
| catalog-register | **registering a data source** (external-data side-effect); unregistered source → stop | — |

If in doubt whether something is a genuine decision, **stop and ask** — bias toward the KEEP column.

## Workflow

### Step 1: Locate the current position

- `uv run python -m skills._shared.design_io get --id {id}` (if an id was given) or
  `design_io list` to see existing designs. Decide the entry point:
  - no hypothesis yet → start at framing/design;
  - design exists in `in_review`/`analyzing` → continue from review/premortem/notebook;
  - design has journal/results → continue from reflection.
- Tell the user the plan ("これから design→premortem→notebook→journal→reflection を自動で進める。
  仮説確定・コスト判定・結論では止まる").

### Step 2: Drive each step (delegate to the skill, apply the gate policy)

For each step, **follow that skill's SKILL.md** (do not duplicate its logic here) and apply the
gate policy above:

1. **framing** (if no hypothesis yet): run `/analysis-framing` in full — explore `.insight/`, present the
   **Data Map**, and **hold the Direction Dialogue with the user** (candidate directions, gaps, missing
   data). Do not silently auto-pick the direction — this is where a beginner's intent gets elicited.
   Settle the direction with the user, then produce the Framing Brief.
2. **design**: run `/analysis-design`, auto-drafting fields from the agreed Framing Brief; **pause once**
   for the user to confirm the hypothesis before `design_io create`.
3. **review** (optional): if the user wants a review pass, run `/analysis-review`; **pause on the verdict**.
4. **premortem**: always run `/premortem` before touching data. If `HARD_BLOCK`/`HIGH`, **stop** and
   surface the risk (unregistered source → offer /catalog-register; cost/allowlist/location → let the
   user decide). If `LOW`/`MEDIUM`, continue.
5. **notebook**: run `/analysis-notebook`. Auto-run only when premortem cleared **and** the analysis is
   confined to the declared source(s) + allowlisted packages (`.insight/rules/package_allowlist.yaml`) +
   local computation. If the methodology needs a non-allowlisted package, network egress beyond the
   declared source, or another side-effect, **stop** and get the user's go-ahead first.
6. **journal**: the notebook step already records observe/evidence/question — no pause.
7. **reflection**: run `/analysis-reflection`; **pause at the conclusion** (conclude/refine/branch) and
   the terminal transition. This is where the run ends.

### Step 3: Summarize

Report what ran automatically, where it paused and why, and the final state (status, journal, lineage).

## Delegated skills

`/analysis-framing`, `/analysis-design`, `/analysis-review`, `/premortem`, `/analysis-notebook`,
`/analysis-journal`, `/analysis-reflection`, `/catalog-register` — each remains explicit-invocable on
its own; `/analysis-auto` only sequences them and enforces the gate policy.

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-auto | → /analysis-design | Autopilot needs a hypothesis first |
| /analysis-auto | → /analysis-reflection | Autopilot reaches results; conclusion is the user's call |

## Language Rules

- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
