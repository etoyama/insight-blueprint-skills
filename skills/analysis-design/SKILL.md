---
name: analysis-design
version: "1.2.0"
description: |
  Guides Claude through creating analysis design documents for hypothesis-driven EDA.
  Use when the user wants to create, manage, or review analysis designs.
  Triggers: "create analysis design", "hypothesis document", "new hypothesis",
  "分析設計を作りたい", "仮説を立てたい", "新しい仮説", "仮説ドキュメント".
disable-model-invocation: true
argument-hint: "[theme_id]"
---

# /analysis-design — Analysis Design Builder

Guides Claude through creating a lightweight analysis design document by writing
`.insight/designs/*_hypothesis.yaml` directly via the `design_io` helper (no MCP
server). Follows the hypothesis-driven EDA workflow.

**design_io CLI** (provided on PATH by the plugin; reads JSON payloads on stdin,
prints JSON results; writes to your project's `.insight/`; validation runs before every write):

```bash
echo '<json>' | design_io create
echo '<changes-json>' | design_io update --id FP-H01
design_io transition --id FP-H01 --target analyzing
design_io get --id FP-H01
design_io list [--status in_review]
```

## When to Use
- Starting a new exploratory analysis (user wants to formalize a hypothesis)
- Deriving a sub-hypothesis after a parent hypothesis is rejected
- Reviewing or listing existing analysis designs

## When NOT to Use
- Browsing the data catalog (future: `/data-explorer` skill)
- General EDA discussion without intent to persist a design document

## Workflow

### Step 0: User Confirmation Gate

Before proceeding, confirm with the user:

- Ask: "分析設計を新規作成しますか？"
- If the user declines, exit gracefully with a brief message and do not proceed
- If the user confirms, continue to Step 1

### Step 1: Check Current State
Run `design_io list` to understand existing designs:
- Note existing theme IDs (e.g., "FP", "TX")
- Check if a `parent_id` should be referenced

### Step 1.5: Check for Framing Brief

Check the conversation context for a `## Framing Brief` from analysis-framing.

**Detection rules** (all must be satisfied):
1. `## Framing Brief` heading exists in conversation
2. `### テーマ` subsection exists under Framing Brief
3. `### 推奨方向` subsection exists under Framing Brief
4. `theme_id:` field exists within the 推奨方向 section
5. If multiple Framing Briefs exist, use the last (most recent) one

**If valid Framing Brief found:**

Map Brief sections to analysis-design fields as draft values:

| Framing Brief セクション | analysis-design フィールド | マッピング |
|---|---|---|
| テーマ | `title` | テーマの1行要約を title の候補として提示 |
| 利用可能データ | `explanatory`, `metrics` | データソース・カラムから explanatory/metrics の候補を生成 |
| 既存分析 | `parent_id` | 関連デザイン ID を parent_id の候補として提示 |
| ギャップ | `hypothesis_background` | ギャップ情報を仮説の背景・動機の下書きに活用 |
| 推奨方向.仮説の方向性 | `title`, `hypothesis_background` | 方向性から title 候補を生成し、背景の下書きに活用 |
| 推奨方向.theme_id | `theme_id` | デフォルト値として設定 |
| 推奨方向.parent_id | `parent_id` | デフォルト値として設定 |
| 推奨方向.analysis_intent | `analysis_intent` | デフォルト値として設定 |
| 推奨方向.推奨手法 | `methodology` | `{method: "推奨手法の値", reason: "Framing Brief の推奨"}` としてデフォルト設定 |

Present draft values to user: "Framing Brief の内容でよいか、修正したい点があるか"

Step 2 ではゼロからインタビューせず、draft 値を提示して確認しながら進める。

**If Framing Brief missing or incomplete:**
Framing Brief がない、または検出条件を満たさない場合は何もしない。Step 2 の通常インタビューフローに進む（後方互換）。不完全な場合はユーザーに通知: "Framing Brief が不完全なため通常フローで進めます"

### Step 2: Gather Hypothesis Details

Interview the user for required fields:

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `title` | Yes | Short descriptive title | "Foreign population vs crime rate" |
| `hypothesis_statement` | Yes | Testable statement | "No positive correlation exists between..." |
| `hypothesis_background` | Yes | Context and motivation (free-form, multi-line) | Background reasoning |
| `theme_id` | No | Uppercase identifier — defaults to "DEFAULT" | "FP", "TX", "ECON" |
| `parent_id` | No | Parent design ID if this is derived | "FP-H01" |
| `analysis_intent` | No | "exploratory", "confirmatory" (default), or "mixed" | "exploratory" |
| `metrics` | No | List of verification metric dicts (tier: "primary" / "secondary" / "guardrail") | `[{target: "crime_rate_per_100k", tier: "primary", data_source: {crime: "0000010111"}, grouping: [...], filter: "...", aggregation: "mean", comparison: "..."}]` |
| `explanatory` | No | List of explanatory variable dicts (role: "treatment" / "confounder" / "covariate" / "instrumental" / "mediator") | `[{name: "foreign_ratio", description: "外国人比率", role: "treatment", data_source: "0000010101", time_points: "2012-2022"}]` |
| `chart` | No | List of visualization definition dicts (intent: "distribution" / "correlation" / "trend" / "comparison") | `[{intent: "correlation", type: "scatter", description: "FP ratio vs crime rate", x: "foreign_ratio", y: "crime_rate"}]` |
| `methodology` | **Yes** | Analysis method and package (must include `method` key) | `{method: "OLS", package: "statsmodels", reason: "線形回帰で相関を検証"}` |
| `next_action` | No | Branch definition after hypothesis test | `{if_supported: "...", if_rejected: {reason: "...", pivot: "..."}}` |

If the user passed `$ARGUMENTS`, use it as `theme_id` (validate format first).

### Step 2.5: Pre-creation Check

Before creating the design, verify that `methodology` is NOT null.
If the interview did not cover methodology, ask now:
- "What analysis method will you use? (e.g., OLS, t-test, chi-square, DID)"
- Set `methodology = {method: "<answer>", reason: "<why this method>"}` at minimum.

### Step 2.6: Enrich Methodology with Code Patterns

Downstream notebook generation (Claude Code) works from methodology content. Concrete code patterns dramatically improve generation fidelity.

**When `data_source` references a registered catalog source**, auto-generate a code pattern from the catalog schema and include it in `methodology.steps`:

```python
methodology = {
    "method": "OLS",
    "package": "statsmodels",
    "reason": "線形回帰で相関を検証",
    "steps": [
        {
            "description": "from lib.accessor.bigquery import BigQueryAccessor\nacc = BigQueryAccessor(project_id='lmi-datau-prod')\nraw_df = acc.query_to_dataframe('''\n  SELECT col1, col2, ...\n  FROM `project.dataset.table`\n  WHERE ...\n''')"
        }
    ]
}
```

**Rules:**
- If `data_source` is a BQ table: generate `BigQueryAccessor` pattern with actual table name, key columns from schema, and filter conditions
- If methodology uses a specific library (e.g., lingam, shap, dowhy): include the exact API call with parameter names in a subsequent step
- If the user provides their own code pattern, use it as-is — do not overwrite

### Step 3: Create the Design

Build a JSON payload and pipe it to `design_io create`. `methodology` is REQUIRED.
The helper generates the `id` (`{theme_id}-H{nn}`), sets timestamps, validates the
schema, and writes `.insight/designs/{id}_hypothesis.yaml`.

```bash
echo '{
  "title": "<title>",
  "hypothesis_statement": "<statement>",
  "hypothesis_background": "<background>",
  "methodology": {"method": "OLS", "package": "statsmodels", "reason": "..."},
  "theme_id": "FP",
  "parent_id": null,
  "metrics": [],
  "explanatory": [],
  "chart": [],
  "next_action": null
}' | design_io create
```

Expected stdout (the written design as JSON):
```json
{"id": "FP-H01", "title": "...", "status": "in_review", ...}
```

If validation fails (e.g. empty `methodology.method`), the command exits non-zero
with the error on stderr and **nothing is written** — fix the payload and retry.

### Step 3b: Update an Existing Design (optional)

To add or modify fields, pipe a partial-changes JSON to `design_io update`. Only the
provided fields change; `updated_at` is refreshed and `referenced_knowledge` is merged.

```bash
echo '{"next_action": {"if_supported": "パネルFEへ進む", "if_rejected": {"reason": "相関なし", "pivot": "時系列分析"}}}' \
  | design_io update --id FP-H01
```

### Step 4: Confirm and Suggest Next Steps
- Show the returned `id` (e.g., "FP-H01") to the user
- Confirm the YAML file location: `.insight/designs/FP-H01_hypothesis.yaml`
- Suggest next steps:
  - Refine the hypothesis: add `chart` / `next_action` via `design_io update`
  - **Start recording reasoning: `/analysis-journal FP-H01`**
  - **Review and conclude: `/analysis-reflection FP-H01`**

## design_io Reference

`design_io <command>` (provided on PATH by the plugin; targets your project's
`.insight/`). Payloads are JSON on stdin; results are JSON on stdout.

| Command | Purpose | Input |
|---------|---------|-------|
| `list [--status S]` | List existing designs | — |
| `get --id ID` | Retrieve a design | — |
| `create` | Create new design (auto id, validated) | stdin: `{title, hypothesis_statement, hypothesis_background, methodology, theme_id?, parent_id?, metrics?, explanatory?, chart?, next_action?, analysis_intent?}` |
| `update --id ID` | Partial update (merge, refresh updated_at) | stdin: `{<fields to change>}` |
| `transition --id ID --target S` | Change status (validated) | — |

Validation (schema + state transition) runs inside `design_io` before writing — the
same `validate.py` the pre-write hook uses. Invalid writes raise and write nothing.

## Typed Field Values Reference

| Field | Type | Valid Values | Default |
|-------|------|-------------|---------|
| `explanatory[].role` | VariableRole | `"treatment"`, `"confounder"`, `"covariate"`, `"instrumental"`, `"mediator"` | `"covariate"` |
| `metrics[].tier` | MetricTier | `"primary"`, `"secondary"`, `"guardrail"` | `"primary"` |
| `chart[].intent` | ChartIntent | `"distribution"`, `"correlation"`, `"trend"`, `"comparison"` | inferred from `type` |
| `methodology.method` | str | free text (required, non-empty) | — |
| `methodology.package` | str | free text (optional) | `""` |
| `methodology.reason` | str | free text (optional) | `""` |
| `methodology.steps` | list[dict] | Each dict has `description` (str). Include concrete code patterns for notebook-generation fidelity. | `[]` |

**Backward compatibility**: `role`, `tier`, `intent` fields are optional in input. If omitted, defaults are applied automatically.

## theme_id Rules

- Must match `[A-Z][A-Z0-9]*` (uppercase letter first, then uppercase letters or digits)
- Valid: `"FP"`, `"TX"`, `"ECON"`, `"DEFAULT"`, `"FP2"`
- Invalid: `"fp"` (lowercase), `"FP/X"` (slash), `"1FP"` (starts with digit)
- On invalid input, `design_io` exits non-zero with the error on stderr — ask the user to correct it

## Error Handling

| Error (stderr) | Cause | Action |
|----------------|-------|--------|
| `Invalid theme_id 'fp': must match [A-Z][A-Z0-9]*` | Invalid theme_id format | Ask user for a valid uppercase theme_id |
| `Design 'FP-H99' not found` | Non-existent design_id | Confirm ID via `design_io list` |
| pydantic `ValidationError` (e.g. empty `methodology.method`) | Schema violation | Fix the payload; nothing was written |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-framing | → /analysis-design | Framing Brief 付きでフォワーディング |
| /analysis-auto | → /analysis-design | autopilot が仮説をまず用意する |
| /analysis-design | → /analysis-review | デザイン作成後にレビューを受ける: "作った design をレビューするなら /analysis-review {id}" |
| /analysis-design | → /analysis-notebook | デザイン確定後に分析実行: "分析を実行するなら /analysis-notebook {id}" |
| /analysis-design | → /analysis-journal | デザイン作成後: "推論過程を記録するなら /analysis-journal {id}" |
| /analysis-design | → /analysis-framing | データ不足で仮説の方向を再検討: "データを探し直すなら /analysis-framing" |
| /catalog-register | → /analysis-design | データ登録完了後にデザイン作成を続行 |
| /analysis-reflection | → /analysis-design | 派生仮説が明確な場合 |
| /analysis-revision | → /analysis-design | レビュー修正で大きな方針変更が必要な場合 |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Hypothesis text follows the user's language (usually Japanese)

## Workflow Rules

### Hypothesis Design Workflow

### Status Flow

Designs use the `DesignStatus` model. A new design starts `in_review`.

```
in_review ─┬→ revision_requested → (back to in_review / analyzing / terminal)
           ├→ analyzing → in_review
           └→ supported | rejected | inconclusive   (terminal — no exit)
```

- **in_review**: Created, under review.
- **revision_requested**: Review asked for changes.
- **analyzing**: Hypothesis is being tested.
- **supported / rejected / inconclusive**: Terminal disposition.

Status transitions MUST go through `design_io transition` (or `append_review_batch`),
which validates the move against `VALID_TRANSITIONS` in `validate.py`. Illegal moves
(e.g. `analyzing → supported`, or any exit from a terminal state) are rejected.

### Theme ID Rules

- Every design MUST have a `theme_id` linking it to a research theme.
- Theme IDs must match `[A-Z][A-Z0-9]*` (e.g., `CHURN`, `PRICING`).
- Use `/analysis-design` skill to create designs with proper theme association.

### Derived Hypotheses

- A design may reference `parent_id` to indicate it derives from another hypothesis.
- Parent must exist and be in `supported` or `active` status.
- This creates a hypothesis tree for tracking research lineage.

## YAML Format Reference

### .insight/ YAML File Operation Rules

#### Design documents go through `design_io`

`.insight/designs/*_hypothesis.yaml` and `*_reviews.yaml` MUST be created/updated via
the `design_io` helper, not hand-written. `design_io` owns id generation, timestamps,
`referenced_knowledge` merge, and validation (`validate.py`). A `*_hypothesis.yaml`
written via the Write/Edit tool is additionally guarded by the pre-write hook
(`hooks/validate-design.py`), which calls the same `validate.py` — so schema
and state-transition rules hold on either path.

**Direct read is always OK** — use Read tool / glob / cat freely for analysis.

#### Skill-managed directly (no design_io)

These contain skill- or user-managed data and are edited directly (Read/Write):

- `.insight/config.yaml` — project configuration
- `.insight/rules/*.yaml` — review / analysis rules, knowledge seed data
- `.insight/designs/*_journal.yaml` — Insight Journal (analysis-journal; `design_io` has
  `load_journal`/`write_journal` thin wrappers)
- `.insight/designs/*_revision.yaml` — Revision Tracking (analysis-revision)

> Catalog (`catalog/**`) is still MCP-backed until Epic 3.5.
