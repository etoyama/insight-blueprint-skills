---
name: rq-problematization
version: "1.0.0"
description: |
  Generates impactful research questions using Alvesson & Sandberg's (2011)
  problematization framework. Collects prior research, surfaces the assumptions a
  literature takes for granted across five types, and dialectically challenges them
  via a devil's-advocate subagent — moving beyond gap-spotting to assumption-challenging.
  Triggers: "リサーチクエスチョンを考えたい", "研究テーマから問いを立てたい",
  "問題化したい", "先行研究の前提を疑いたい", "インパクトのある研究の切り口がほしい",
  "research question を作りたい", "problematization".
disable-model-invocation: true
argument-hint: "[theme]"
---

# /rq-problematization — Research Question Problematization

Generates impactful (interesting and influential) research questions from a research
theme, grounded in Alvesson & Sandberg (2011) "Generating Research Questions Through
Problematization" (*Academy of Management Review*, 36(2), 247-271) and the sister paper
Sandberg & Alvesson (2011) "Ways of constructing research questions: gap-spotting or
problematization?" (*Organization*, 18(1), 23-44).

Read `references/alvesson-framework.md` first to load the exact definitions of the
framework before running the workflow.

## When to Use
- Have a research theme and want to generate impactful, novel research questions
- Want to question the taken-for-granted assumptions underlying prior research
- Need an angle that goes beyond incremental gap-filling

## When NOT to Use
- Want to explore available data and frame a verifiable direction → `/analysis-framing`
- Hypothesis is already clear and only needs structuring into a design → `/analysis-design`
- Recording reasoning during an ongoing analysis → `/analysis-journal`

## Core Principle: problematization, not gap-spotting

This is the heart of the skill and the easiest point to fail. Most RQ generation
collapses into **gap-spotting** — looking for "what is missing in the literature."
That is safe but bland and rarely produces influential theory. Alvesson argues that
theory becomes "interesting" only when we **identify the assumptions that existing
research takes for granted, then question and overturn them** (cf. Davis 1971,
"That's Interesting!").

Therefore, at every stage of the workflow, ask:
- "Is this merely pointing at an *under-researched area*?" (= gap-spotting)
- "Is this shaking an assumption the literature *takes for granted*?" (= problematization)
If it is not the latter, redo it.

## Workflow Overview

A flow mapped onto Alvesson's six-step logic. Copy the following checklist into your
response at the start and track progress (a pattern recommended for complex workflows):

```
Problematization progress:
- [ ] 1. Theme received
- [ ] 2. Literature domain identified & prior research collected (with verification status)
- [ ] 3. Existing theory summarized
- [ ] 4. Assumptions extracted (5 types)
- [ ] 5. Dialectical dialogue with critic (gap-rephrasings removed)
- [ ] 6. Assumptions evaluated (Davis typology + why now)
- [ ] 7. Alternative assumptions developed & RQs generated
- [ ] 8. Audience relationship considered
- [ ] 9. Markdown output produced
```

Run Steps 2–8 internally. Insert one optional human checkpoint at **Step 4 (extracted
assumptions)**. At the very start, ask once: "前提リストを一度確認しますか？それとも
最後まで自動で進めますか？"

---

## Step Details

### Step 1: Receive Theme

Accept the research theme from `$ARGUMENTS` or ask the user for one.
- If `$ARGUMENTS` is provided, use it as the theme.
- If the theme is too broad (e.g., "leadership"), confirm a single focus first.
- If forwarded from `/development-partner` or carrying an upstream context, build on it.

### Step 2: Identify Literature Domain & Collect Prior Research

**Citation accuracy is the top priority. Never invent papers or authors.** This is a
tool for researchers; fabricated citations are fatal.

- Use `WebSearch` to find major prior research, review articles, and key theorists.
  Prioritize Google Scholar / Semantic Scholar / journal pages.
- Adopt only citations whose author, year, title, venue, **volume, and page range** you
  could **verify through search**.
- If full text is paywalled, work from the abstract, reference lists, or secondary
  sources (and state that the full text was not read).
- In the output, tag every citation with a verification status:
  `[検索で確認済]` / `[要旨のみ確認]` / `[未確認・要検証]`.
  - `[検索で確認済]` means the author name(s), year, exact title, venue, and volume/pages
    were all confirmed via a search result pointing to the publisher's or an indexing
    service's page. **If the author names do not match the actual paper, it is NOT
    verified — do not apply this tag.**
- For any claim you cannot verify, attach `[未確認・要検証]` — never fill the gap with
  fabrication.

The goal is to grasp the **home position** (dominant view) and the **main schools** of
the domain.

### Step 3: Summarize Existing Theory

Concisely describe "what the existing theory looks like": the dominant theoretical
position, the main schools, and the shared view in the field.

### Step 4: Extract Assumptions (the heart of the skill)

For each of the five types, explicitly articulate what the existing literature
**takes for granted**. Use the definitions and prompting questions in
`references/alvesson-framework.md`.

| Type | What to question | Difficulty | Potential impact |
|------|------------------|------------|------------------|
| in-house | In-house assumptions of a specific school | Low | Low–Mid |
| root metaphor | The underlying metaphor/image of the field | Mid | Mid–High |
| paradigm | Ontological / epistemological / methodological assumptions | High | High |
| ideology | Political / moral / gender-related assumptions | High | High |
| field | Assumptions shared across competing schools | Highest | Highest |

Difficulty and potential impact trade off. Where possible, draw assumptions from
multiple types so the later evaluation can choose an ambition level.

**Critical:** what you surface here is not "what the literature does not say" but
"what the literature assumes without saying." The former is a gap; the latter is an
assumption. If you conflate them, re-extract.

### Step 5: Dialectical Dialogue with a Critic Agent

Problematization is a dialectical process. Test the quality of the extracted
assumptions by **spawning a separate critic (devil's advocate) agent**. Launch it with
the `Agent` tool (subagent_type: `general-purpose`) and ask it to:

> You are a critical reviewer. Scrutinize the following list of "extracted assumptions"
> and evaluate each item strictly:
> 1. Is this genuinely an assumption the existing research *takes for granted*, or is it
>    merely a rephrasing of an under-researched area (a gap)?
> 2. Do the major researchers/schools really believe this assumption? Are there
>    counter-examples (research that already questions it)?
> 3. If overturned, what would change theoretically? Is the impact real or trivial?
> 4. Is there a deeper/more fundamental assumption hidden behind it?
> Classify each assumption as "true assumption / gap-rephrasing / already challenged"
> and return improvement suggestions.

Use the critic's feedback to remove gap-rephrasings and refine the assumptions. One or
two rounds if needed. This realizes dialectical depth without human intervention.

**If subagents are unavailable:** when the `Agent` tool cannot be used, switch roles
explicitly and become the "critic" yourself, refuting each extracted assumption once
using the critique points above (making the role switch explicit improves quality). If
even that is impractical, present the pre-refinement assumption list to the human and
ask them to select/reject.

(In human-checkpoint mode, present the refined assumption list here and ask the user to
select/modify.)

### Step 6: Evaluate Assumptions

Evaluate "is it worth challenging?" on two axes:

**(a) Impact if overturned** — label with the Davis (1971) interestingness typology
(see `references/davis-interestingness.md`). E.g., "what seems single is actually
plural," "what seems independent is actually interdependent," "what is deemed good is
actually bad." Naming the type clarifies the *kind* of impact.

**(b) Feasibility of overturning** — the reason this assumption *can be challenged now*:
new empirical evidence/data, technological innovation, social/institutional change, or
new theory from an adjacent field. The more concretely you can state "why now," the
stronger and more timely the RQ.

Drop assumptions weak on both axes; keep the strong ones.

### Step 7: Develop Alternative Assumptions & Generate RQs

For each chosen assumption, construct an **alternative assumption ground** and write the
RQ it generates.
- The RQ must directly reflect the assumption shift (not a gap-filling question).
- Attach a **verification plan** to each RQ: research design, data, method, and
  falsifiable hypotheses.

### Step 8: Consider the Audience

Alvesson's step 5. Skipping it yields "interesting but nobody cares" problematization.
- Which audience (school/community) holds this assumption?
- What message would persuade them and make it "interesting"?
- What pushback is expected, and how to mitigate it.

### Step 9: Produce Output

Generate a Japanese markdown file following the structure in
`references/output-template.md`. **Save the file to the working directory and present
its path to the user** (do not rely on any external presentation mechanism).

Then output a concise **RQ Brief** in the conversation so the next skill
(`/analysis-framing`) can pick it up and ground it in data:

````markdown
## RQ Brief

### テーマ
{theme_one_liner}

### 疑う中心的前提（類型）
{central assumption being challenged} ({type})

### リサーチクエスチョン
- {RQ 1}
- {RQ 2}

### 検証の方向性（要データ接地）
- {what data / method could test these — to be grounded by analysis-framing}
````

After the RQ Brief, suggest:
"データに接地して検証可能な枠組みにするなら `/analysis-framing`"

---

## Notes Throughout

- **Self-check for gap-spotting regression** at every step. This is the biggest quality
  factor.
- **Cite only what you verified.** Always show the verification status. Fabrication is
  forbidden.
- The generated document is in **Japanese**; key concepts may carry the English
  original in parentheses (useful when writing the paper).
- In assumption extraction, prefer drawing candidates across **multiple types** to
  preserve a choice of ambition level.
- **Do not skip the critic agent.** Dialectical verification is what underpins quality.

## Chaining

| From | To | When |
|------|-----|------|
| /development-partner* | → /rq-problematization | 研究テーマがあり先行研究の前提を問い直したい: "前提を疑うなら /rq-problematization" |
| /analysis-reflection | → /rq-problematization | 仮説が棄却/不確定で前提から問い直したい: "前提から問い直すなら /rq-problematization" |
| /rq-problematization | → /analysis-framing | RQ が出てデータ接地が必要: "データに接地して検証枠組みにするなら /analysis-framing" |

\* = 外部スキル（development-deck）。存在時のみ表示する。存在しない場合この行は Chaining セクションに含めない。

Note: `/rq-problematization` does not chain directly to `/analysis-design`. The RQ must
first be grounded in available data by `/analysis-framing`, which is the data-grounding
gate before a hypothesis is structured.

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- The generated research-question document is written in Japanese (key concepts may
  include the English original in parentheses).
