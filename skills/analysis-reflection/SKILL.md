---
name: analysis-reflection
version: "1.1.0"
description: |
  Guides structured reflection on an analysis design using its Insight Journal.
  Helps draw conclusions, identify gaps, and decide whether to conclude, refine, or branch.
  Triggers: "振り返り", "reflection", "まとめ", "結論を出す", "分析を振り返る",
  "この仮説どうなった", "wrap up analysis".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-reflection — Structured Analysis Reflection

Guides the user through a structured reflection on their analysis,
using the Insight Journal as source material. Helps reach a conclusion,
identify remaining gaps, or decide to branch.

## When to Use
- Enough evidence has been gathered and it's time to reflect
- Want to assess open questions and decide next steps
- Ready to conclude (transition to supported/rejected/inconclusive)

## When NOT to Use
- Still actively investigating (→ /analysis-journal)
- Creating a new design (→ /analysis-design)
- Registering data sources or knowledge (→ /catalog-register)

## Workflow

### Step 1: Load Design + Journal

1. `uv run python -m skills._shared.design_io get --id {design_id}` — load design (JSON)
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
   - supported: `uv run python -m skills._shared.design_io transition --id {design_id} --target supported`
   - rejected: `... --target rejected`
   - inconclusive: `... --target inconclusive`

   Note: Current status must be "analyzing" for terminal transition (design_io
   validates this via VALID_TRANSITIONS). If status is "in_review", go through the
   review process first.

3. Show final summary and suggest:
   - "レビューコメントを付けるなら /analysis-review（記録後 /analysis-revision で対応）"
   - "この分析で分かったソースの再利用知識を残すなら /knowledge-extract"
   - "新しいデータソース自体を登録するなら /catalog-register"
   - "派生仮説を立てるなら /analysis-design"

   Note: 結論そのもの（finding）はここ（journal/reflection）に残す。/knowledge-extract は
   データソースに紐づく再利用可能な知見だけを抽出する。

### Step 5: Record Refinement (if not concluding)

If user chooses to refine:

1. Record `hypothesize` event with the refined hypothesis in journal
2. Optionally refine the design: `echo '{"hypothesis_statement": "<refined>"}' | uv run python -m skills._shared.design_io update --id {design_id}`
3. Suggest: "/analysis-journal {id} で追加調査を続けよう"

## design_io Reference

`python -m skills._shared.design_io <command>` (from project root):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details |
| `transition --id ID --target S` | Terminal status transition (validated) |
| `update --id ID` (stdin JSON) | Hypothesis refinement |
| `list` | Find child/sibling designs (filter the JSON by parent_id/theme_id) |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-journal | → /analysis-reflection | Evidence gathered |
| /analysis-notebook | → /analysis-reflection | Notebook 実行の結果が揃った: 結論づけへ |
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
