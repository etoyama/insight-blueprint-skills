---
name: analysis-revision
version: "1.0.0"
description: |
  Guides structured revision of an analysis design based on review comments.
  Reads review feedback via design_io, tracks progress per comment, and helps fix each issue.
  Triggers: "レビューを直して", "指摘を反映して", "revision対応して", "fix review",
  "address comments", "レビュー修正".
disable-model-invocation: true
argument-hint: "[design_id]"
---

# /analysis-revision — Structured Review Revision

Guides the user through a structured revision workflow for an analysis design
that has received review comments. Reads review feedback via design_io
(`list-reviews`), creates a persistent tracking file for per-comment progress,
and helps address each comment through interactive dialogue.

## When to Use
- Design status is `revision_requested` and review comments need to be addressed
- Resuming a previously interrupted revision session
- Systematically working through all reviewer feedback before re-submitting

## When NOT to Use
- Creating a new design from scratch (-> /analysis-design)
- Recording reasoning during active analysis (-> /analysis-journal)
- Structured reflection and conclusion (-> /analysis-reflection)
- Design is not in `revision_requested` status

## Workflow

### Phase 1: Situation Assessment

1. If `$ARGUMENTS` contains a design ID (e.g., "FP-H01"), use it directly.
   Otherwise, run `uv run python -m skills._shared.design_io list --status revision_requested`
   and ask the user to select.

2. `uv run python -m skills._shared.design_io get --id {design_id}` -- load the design (JSON).

3. **Status check**: If `status != "revision_requested"`, display an error and exit:
   ```
   このデザイン ({design_id}) は revision_requested 状態ではない (現在: {status})。
   レビューで修正依頼が出た後にこのスキルを使おう。
   ```

4. `uv run python -m skills._shared.design_io list-reviews --id {design_id}` -- get all review batches (JSON, newest first).

5. **Batch selection** (important -- do NOT just pick the newest batch overall):
   - Filter the returned batches to only those where `status_after == "revision_requested"`
   - From the filtered set, pick the one with the newest `created_at`
   - This is the **target batch** for this revision session

6. If no qualifying batch found (all batches have `status_after != "revision_requested"`):
   ```
   revision_requested に対応するレビューバッチが見つからない。
   レビューが WebUI 経由で提出されているか確認しよう。
   ```
   Exit.

7. Display situation summary:
   ```
   -- Revision: {design_id} --
   Title: {title}
   Status: {status}
   Target batch: {batch.id} ({batch.created_at})
   Reviewer: {batch.reviewer}
   Comments: {len(batch.comments)} items
   ```

### Phase 2: Tracking Initialization

1. Read `.insight/designs/{design_id}_revision.yaml` using the Read tool.

2. **If file exists AND `batch_id` matches the target batch** -> reuse existing tracking (session resume).
   Show: "前回のセッションから再開する。未対応のコメントから進めよう。"

3. **If file does not exist OR `batch_id` does not match the target batch** -> create new tracking file.

4. **If file exists but is corrupted (parse error)** -> treat as non-existent and create new tracking file.
   Show: "tracking file が破損していたため、新しいバッチから再作成する。"

New tracking file schema:

```yaml
batch_id: "{target_batch.id}"
created_at: "{now_jst in ISO 8601 format}"
items:
  - index: 0
    fingerprint: "{fingerprint}"
    comment_summary: "{first 50 chars of comment}"
    target_section: "{target_section or null}"
    status: "open"
    addressed_at: null
  - index: 1
    fingerprint: "{fingerprint}"
    comment_summary: "{first 50 chars of comment}"
    target_section: "{target_section or null}"
    status: "open"
    addressed_at: null
  # ... one item per comment in the batch
```

**Fingerprint generation formula** (stable identity key for cross-session matching):

```python
import hashlib
fingerprint = hashlib.sha256(f"{comment}|{target_section or ''}".encode()).hexdigest()[:8]
```

The fingerprint is based on comment content rather than index position, so it remains
stable even if comments are reordered. It is used for reconciliation when resuming a session.

Write the tracking file using the Write tool. Write the full YAML content to
`.insight/designs/{design_id}_revision.yaml`.

Note: In production code, atomic writes should use the `tempfile + os.replace()` pattern.
Since the skill operates through Claude's Write tool, the tool handles file writing directly.

### Phase 3: Comment Addressing Loop

For each item in the tracking file where `status == "open"`:

1. **Display the comment with context**:
   ```
   -- Comment {index+1}/{total} --
   Section: {target_section or "general"}
   Comment: {full comment text from the batch}
   Target content: {target_content from the batch, if present}
   Current value: {current value of that section from design_io get, if target_section is set}
   Status: {status}
   ```

   To get the current value, run `design_io get --id {design_id}` and extract
   the field matching `target_section` (e.g., if `target_section == "hypothesis_statement"`,
   show `design["hypothesis_statement"]`).

2. **Ask user for direction**:
   ```
   どう対応する？
   1. fix -- 修正する (修正内容を一緒に考える)
   2. skip -- 対応しない (wontfix としてマーク)
   3. discuss -- 方針を相談したい
   ```

3. **If fix**:
   - Discuss the fix with the user
   - Apply the change: `echo '{<changed fields>}' | uv run python -m skills._shared.design_io update --id {design_id}`
   - Update tracking item: `status: "addressed"`, `addressed_at: "{now_jst}"`

4. **If skip (wontfix)**:
   - Confirm with user: "このコメントを wontfix にする。理由を一言で?"
   - Update tracking item: `status: "wontfix"`, `addressed_at: "{now_jst}"`

5. **If discuss**:
   - Engage in discussion about the comment
   - After discussion, return to the direction choice (fix / skip)

6. **Write updated tracking file** after each comment is resolved.
   Write the full YAML content to `.insight/designs/{design_id}_revision.yaml`
   using the Write tool.

### Phase 4: Completion Check

1. After all items have been processed, verify: every item has `status` of either
   `"addressed"` or `"wontfix"`.

2. **Show summary**:
   ```
   -- Revision Summary --
   Total: {total} comments
   Addressed: {addressed_count}
   Won't fix: {wontfix_count}
   ```

3. **Propose re-submission**:
   ```
   全コメントへの対応が完了した。in_review に戻してレビュアーに再確認を依頼する？
   ```
   If yes: `uv run python -m skills._shared.design_io transition --id {design_id} --target in_review`

4. **Suggest next steps**:
   - "大きな方針変更が必要なら /analysis-design {design_id} で再設計"
   - "調査してから修正したい場合は /analysis-journal {design_id} で記録しながら進めよう"
   - "in_review に戻した後、レビュアーは WebUI で再レビューできる"

## design_io Reference

`python -m skills._shared.design_io <command>` (from project root):

| Command | Used for |
|---------|----------|
| `get --id ID` | Load design details and check status |
| `list --status revision_requested` | Find designs awaiting revision |
| `list-reviews --id ID` | Get review batches with comments (newest first) |
| `update --id ID` (stdin JSON) | Apply fixes to design fields |
| `transition --id ID --target in_review` | Re-submit for review |

## Tracking File Location

`.insight/designs/{design_id}_revision.yaml`

This file is skill-managed data, edited directly (see YAML Format Reference
in analysis-design SKILL.md).

## Error Handling

| Situation | Action |
|---|---|
| Design not found | Show error, suggest `design_io list` |
| Design not in revision_requested status | Show current status, exit with guidance |
| No revision_requested batch found | Show message, suggest reviewing first |
| Tracking file corrupted | Re-create from target batch, warn user |
| `design_io update` fails | Show error, ask user to retry or adjust |
| Session interrupted mid-loop | On next run, resume from tracking file (open items) |

## Chaining

| From | To | When |
|------|-----|------|
| WebUI review (revision_requested) | -> /analysis-revision | Review submitted with revision_requested status |
| /analysis-revision | -> /analysis-design | Major redesign needed: "大きな方針変更が必要なら /analysis-design {id}" |
| /analysis-revision | -> /analysis-journal | Need to investigate before fixing: "調査してから修正するなら /analysis-journal {id}" |
| /analysis-revision | -> (WebUI review) | After transition to in_review, reviewer re-reviews in WebUI |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Revision workflow guidance follows the user's language (usually Japanese).
