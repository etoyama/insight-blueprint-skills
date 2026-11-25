---
name: analysis-design
version: "1.3.0"
description: |
  Guides Claude through creating analysis design documents for hypothesis-driven EDA:
  an exploration (a question to measure) or a confirmation (a hypothesis to judge).
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
- Starting a new analysis: a question to explore, or a hypothesis to confirm
- Deriving a design from a finished one (an explored question, or a judged hypothesis)
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
- If the user instead names an existing design to change (e.g. to declare its data sources),
  skip to Step 3b

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
| 利用可能データ | `source_ids`, `explanatory`, `metrics` | データソースの id を source_ids の候補にし、カラムから explanatory/metrics の候補を生成 |
| 既存分析 | `parent_id` | 関連デザイン ID を parent_id の候補として提示 |
| ギャップ | `exploration_background` / `hypothesis_background` | ギャップ情報を、選んだ意図の背景の下書きに活用 |
| 推奨方向.探索の問いの案 | `exploration_question` | 探索のときの下書き。Step 2 で意図を聞いてから確かめる |
| 推奨方向.検証仮説の案 | `hypothesis_statement` | 検証のときの下書き。Step 2 で意図を聞いてから確かめる |
| 推奨方向.theme_id | `theme_id` | デフォルト値として設定 |
| 推奨方向.node_id | （分析設計の項目ではない） | 作った分析設計を結ぶ論点。Step 3 の `tree_io link` に渡す |
| 推奨方向.論点 | `title`, `exploration_background` / `hypothesis_background` | この分析設計が答える問い。title 候補と背景の下書きに活用（探索の問いや検証仮説の文にそのまま写さない） |
| 推奨方向.parent_id | `parent_id` | デフォルト値として設定 |
| 推奨方向.analysis_intent | `analysis_intent` | 意図の下書き。Step 2 で必ず聞き直す |
| 推奨方向.推奨手法 | `methodology` | `{method: "推奨手法の値", reason: "Framing Brief の推奨"}` としてデフォルト設定 |

Present draft values to user: "Framing Brief の内容でよいか、修正したい点があるか"

Step 2 ではゼロからインタビューせず、draft 値を提示して確認しながら進める。

**If Framing Brief missing or incomplete:**
Framing Brief がない、または検出条件を満たさない場合は何もしない。Step 2 の通常インタビューフローに進む（後方互換）。不完全な場合はユーザーに通知: "Framing Brief が不完全なため通常フローで進めます"

### Step 2: Ask the Intent, Then Gather the Design Details

Ask the intent first, then interview the user for the fields of that form.

#### Intent (asked first)

Before any other field of the design, ask one question:
"この分析設計では、測って答えを探しますか（探索）、それとも先に仮の答えと判定の基準を決めて確かめますか（検証）？"

- 探索 is `exploratory`, 検証 is `confirmatory`. Never offer `mixed`: `design_io create` refuses it.
- A Framing Brief's `analysis_intent` and the default (`confirmatory`) are only drafts: show the
  draft as the suggestion and still ask. Never fill the intent without the analyst's answer.
- Help the analyst choose with this rule: 先に置ける仮の答えがあり、判定の基準を今固定できるなら検証。
  そうでなければ探索。Yes/No で答えられる論点でも、判定の基準を今固定できなければ探索になる。
- An exploration: confirm `exploration_question` and `exploration_background`. The question is
  narrower than the question node it answers and says what is measured. It carries no guess of
  the answer and no criterion; a guess the analyst wants to keep goes to the journal as a
  `hypothesize` event (`/analysis-journal`). Leave `hypothesis_statement`,
  `hypothesis_background` and `next_action` out of the payload: `design_io create` refuses them.
- A confirmation: confirm `hypothesis_statement` and `hypothesis_background`. Leave the two
  exploration fields out of the payload.
- The intent can be changed later only while the design is `in_review` or
  `revision_requested` (Step 3b).

#### Fields of the design

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `title` | Yes | Short descriptive title | "Foreign population vs crime rate" |
| `analysis_intent` | Yes (asked first) | `"exploratory"` or `"confirmatory"` — see "Intent" above | "exploratory" |
| `exploration_question` | Yes for an exploration | The question this design measures to answer. No guess of the answer, no criterion | "分館と本館で、貸出の返却日数はどれだけ違うか" |
| `exploration_background` | Yes for an exploration | Why this question, and what is known so far (free-form, multi-line) | Background reasoning |
| `hypothesis_statement` | Yes for a confirmation | Tentative answer to confirm, stated so it can be refuted | "No positive correlation exists between..." |
| `hypothesis_background` | Yes for a confirmation | Context and motivation (free-form, multi-line) | Background reasoning |
| `decision_context` | No | Who decides what on the strength of this analysis: `decision_maker` + `decision`, both or neither | `{decision_maker: "マーケティング部長", decision: "来期もクーポン施策を続けるか"}` |
| `theme_id` | No | Uppercase identifier — defaults to "DEFAULT" | "FP", "TX", "ECON" |
| `parent_id` | No | Parent design ID if this is derived | "FP-H01" |
| `source_ids` | No (always asked) | Ids of the registered catalog data sources the analysis uses — see "Data sources" below | `["crime_stats", "population"]` |
| `metrics` | No | List of verification metric dicts (tier: "primary" / "secondary" / "guardrail") | `[{target: "crime_rate_per_100k", tier: "primary", data_source: {column: "crime_count"}, grouping: [...], filter: "...", aggregation: "mean", comparison: "..."}]` |
| `explanatory` | No | List of explanatory variable dicts (role: "treatment" / "confounder" / "covariate" / "instrumental" / "mediator") | `[{name: "foreign_ratio", description: "外国人比率", role: "treatment", data_source: "population の foreign_count 列", time_points: "2012-2022"}]` |
| `chart` | No | List of visualization definition dicts (intent: "distribution" / "correlation" / "trend" / "comparison") | `[{intent: "correlation", type: "scatter", description: "FP ratio vs crime rate", x: "foreign_ratio", y: "crime_rate"}]` |
| `methodology` | **Yes** | Analysis method and package (must include `method` key) | `{method: "OLS", package: "statsmodels", reason: "線形回帰で相関を検証"}` |
| `next_action` | No, and a confirmation only | Branch definition after the verdict. An exploration has none | `{if_supported: "...", if_rejected: {reason: "...", pivot: "..."}}` |

If the user passed `$ARGUMENTS`, use it as `theme_id` (validate format first).

#### Decision context (asked with the question or the hypothesis)

Right after the question or the hypothesis is settled (`exploration_question` and
`exploration_background`, or `hypothesis_statement` and `hypothesis_background`), ask one question:
"この分析は、誰が何を決めるためのものですか？（無ければスキップできます）"

- `decision_maker` — who decides. Write a role or a team ("マーケティング部長", "プロダクトチーム"),
  not a personal name: the report is handed to readers, and a role stays true after people move.
- `decision` — what they decide, phrased as the choice the result feeds
  ("来期もクーポン施策を続けるか").

The two come as a pair. The analyst may skip the question; then omit `decision_context` from the
payload. Never write only one side, an empty string, or a placeholder such as "未定": validation
rejects a half-filled context, and a placeholder would later read as a real decision in the report.
If the answer covers only one side, ask once for the other; if it still is not given, omit the field.
It can be added later with `design_io update` (Step 3b).

#### Data sources (asked before the metrics)

Before the metrics and the explanatory variables, ask: "この分析で使うデータソースは？"
`source_ids` is the only place a design declares its data sources; every other skill reads them
from there ([ADR-0020](../../docs/adr/0020-design-declares-sources-in-source-ids.md)).

- If the analyst gives a name rather than an id, find the id with
  `catalog_io search --query {name}` and confirm it with them.
- Check the ids in one call: `catalog_io describe --ids={id},{id}`. Put on the command line
  only ids that fully match `^[a-zA-Z0-9_-]+$`; any other value is not an id, so ask again.
- Write the ids of `sources`, in that order, to `source_ids`. For each id in `missing`, suggest
  /catalog-register and leave it out. **Never write an unregistered id**: downstream skills look
  each id up in the catalog and would find nothing.
- The analyst may not know the sources yet; then write `source_ids: []` and declare them later
  (Step 3b).

`data_source` on a metric or an explanatory variable is a free-form note on where in the declared
sources the value comes from (a column, a table, a filter). It is not read as a source id by any
skill. Put the ids in `source_ids`, not in `data_source`. If a value comes from a source the
analyst could not declare (unregistered), say so in the note and tell the analyst.

#### Metrics explained before they are asked

An analyst shown metrics they have never seen cannot judge them, and approves a method they do
not understand (#210). Explain the metrics before asking about them. First tell the analyst, in
one line: "どの指標にも、詳しい解説を求められます。"

- Every metric gets one sentence of what number it is (何を表す数か), next to its `target`.
- A metric built from two or more quantities (標準化, 期待値との差, 比の比, モデルの係数,
  合成した指数) that no design of the theme has yet gets the five parts below. To tell, run
  `design_io list` and read the `metrics[].target` of the designs with the same `theme_id`.
  A design under `DEFAULT` treats every such metric as new: unrelated designs gather there.
  A metric of one quantity (a mean, a share, a quantile) gets the sentence only, unless the
  analyst asks for more.
- The five parts, in this order:
  1. **何を表す数か** — the one sentence above.
  2. **作り方** — the computation in words, step by step, from the columns of the declared sources.
  3. **実データの例** — two or three rows of a table worked through 作り方.
  4. **迷いやすい点** — a choice in the computation that is easy to get wrong (a negative value,
     a zero denominator, a small group), and what changes if it is handled the other way.
  5. **言えないこと** — what the number does not show, though its name seems to say it.
- The numbers of the example come from the journal of the theme (a value already recorded) or from
  another group computed the same way (another year, another category). Never use the result this
  design will judge: seen before the criterion is fixed, it lets the result pick the criterion.
  Write 概算 on an approximation, and say where the numbers come from.
- Then confirm the metrics with the analyst. The analyst may ask for the five parts on any metric.
- A metric added or replaced later with `design_io update` (Step 3b) is explained the same way.

Sample, for a metric new to a theme on reserved library books:

```text
どの指標にも、詳しい解説を求められます。

wait_excess_days（予約の待ち超過日数）
- 何を表す数か: 予約した本が届くまでに、所蔵冊数と貸出期間から見込める日数より何日多く待ったか。
- 作り方: 予約ごとに、見込みの日数を「予約したときの順位 ÷ 所蔵冊数 × 貸出期間 14 日」で出す。
  実際に待った日数から見込みの日数を引き、館ごとに平均する。
- 実データの例（概算。LIB-H01 の journal にある児童書の順位・所蔵冊数・待った日数から、作り方どおりに計算した。
  これから比べる一般書ではない）:
  | 予約 | 順位 | 所蔵冊数 | 見込み | 実際 | 超過 |
  | A | 6 | 2 | 42 日 | 50 日 | +8 日 |
  | B | 3 | 3 | 14 日 | 9 日 | −5 日 |
- 迷いやすい点: 見込みより早く届いた予約は、超過が負になる。負のまま平均すると、早い予約が遅い予約を
  打ち消す。負を 0 に切ると平均は大きくなり、館の差も変わる。
- 言えないこと: 超過は「館の対応が遅れた日数」ではない。前の人の返却の遅れや、取り置きを受け取りに
  来なかった日数も入る。
```

#### Criterion (a confirmation fixes it now)

A confirmation fixes its criterion before the analysis. Write the criterion of the verdict, as a
sentence, in the `comparison` of the `primary` metric, and confirm it with the analyst together
with the metrics. Example: "分館と本館の差が 2.0 日以上なら支持。1.0 日未満なら棄却。その間は結論しない".
The notebook copies its threshold from this sentence and never makes one up
([ADR-0050](../../docs/adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)).

With the criterion, tell the analyst what the criterion means in the words of the metric, and how
the verdict changes if a handling of 迷いやすい点 changes (扱いを変えると判定がどう変わるか).
A metric of one quantity has no 迷いやすい点: name the handling that moves its verdict most instead
(which rows are left out, how a value on the threshold is read).
Example: "2.0 日以上とは、分館の予約が本館より平均で2日以上、見込みより多く待つこと。負の超過を 0 に
切ると両館の平均が上がり、差が縮めば支持から結論しないに変わりうる". The analyst then fixes the handling
together with the criterion.

An exploration's `comparison` says what is compared and how, with no threshold and no rule for
passing: an exploration measures and answers, and gives no verdict.

### Step 2.5: Pre-creation Check

Before creating the design, verify that `methodology` is NOT null.
If the interview did not cover methodology, ask now:
- "What analysis method will you use? (e.g., OLS, t-test, chi-square, DID)"
- Set `methodology = {method: "<answer>", reason: "<why this method>"}` at minimum.

### Step 2.6: Enrich Methodology with Code Patterns

Downstream notebook generation (Claude Code) works from methodology content. Concrete code patterns dramatically improve generation fidelity.

**For each id in `source_ids`**, auto-generate a code pattern from the catalog schema (`catalog_io get-schema --id {source_id}`) and include it in `methodology.steps`:

```python
methodology = {
    "method": "OLS",
    "package": "statsmodels",
    "reason": "線形回帰で相関を検証",
    "steps": [
        {
            "description": "SELECT store_id, month, sales\nFROM {source:sales_monthly}\nWHERE month >= '2024-01'"
        },
        {
            "description": "raw_df = pd.read_csv({source:stores}, usecols=['store_id', 'region'])"
        }
    ]
}
```

**Rules:**
- Name each data source as `{source:ID}`, where `ID` is an id in `source_ids`. `/analysis-notebook`
  replaces it with the location in the source's `connection`. Never write a path, host, project id or
  table name: the design is read by every later skill and by the report, and `connection`
  reaches only the notebook ([ADR-0022](../../docs/adr/0022-connection-reaches-only-the-notebook.md)).
- If the source is a SQL table: write the query with key columns from the schema and the filter
  conditions, and `FROM {source:ID}` for the table
- If methodology uses a specific library (e.g., lingam, shap, dowhy): include the exact API call with parameter names in a subsequent step
- If the user provides their own code pattern, use it as-is — do not overwrite — but replace any
  path, host, project id or table name in it with `{source:ID}`

> **Under `/analysis-auto`**: this auto-generated query is not committed silently. The driver surfaces it
> as the *data-extraction* confirmation beat (`/analysis-auto` gate policy, design beat ③) — the actual
> query text (or, for a non-SQL source, the data source id + columns/filter) is presented to the user **before**
> `design_io create` and before premortem. Standalone `/analysis-design` invocation is unchanged.

### Step 3: Create the Design

Build a JSON payload for the intent the analyst chose and pipe it to `design_io create`.
`methodology` is REQUIRED. The helper generates the `id` (`{theme_id}-H{nn}`), sets
timestamps, validates the schema and the form of the intent, and writes
`.insight/designs/{id}_hypothesis.yaml`.

An exploration carries the question and its background, and no hypothesis or `next_action`:

```bash
echo '{
  "title": "<title>",
  "analysis_intent": "exploratory",
  "exploration_question": "<question>",
  "exploration_background": "<background>",
  "methodology": {"method": "group comparison", "package": "pandas", "reason": "..."},
  "decision_context": {"decision_maker": "<who decides>", "decision": "<what they decide>"},
  "theme_id": "FP",
  "parent_id": null,
  "source_ids": ["<source_id>"],
  "metrics": [],
  "explanatory": [],
  "chart": []
}' | design_io create
```

A confirmation carries the hypothesis and its background, and the criterion in the `comparison`
of its `primary` metric:

```bash
echo '{
  "title": "<title>",
  "analysis_intent": "confirmatory",
  "hypothesis_statement": "<statement>",
  "hypothesis_background": "<background>",
  "methodology": {"method": "OLS", "package": "statsmodels", "reason": "..."},
  "decision_context": {"decision_maker": "<who decides>", "decision": "<what they decide>"},
  "theme_id": "FP",
  "parent_id": null,
  "source_ids": ["<source_id>"],
  "metrics": [{"target": "<metric>", "tier": "primary", "comparison": "<criterion of the verdict>"}],
  "explanatory": [],
  "chart": [],
  "next_action": null
}' | design_io create
```

Expected stdout (the written design as JSON):
```json
{"id": "FP-H01", "title": "...", "status": "in_review", ...}
```

Leave `decision_context` out of the payload when the analyst skipped it (Step 2).

If validation fails (e.g. empty `methodology.method`, a hypothesis in an exploration, or
`mixed`), the command exits non-zero with the error on stderr and **nothing is written** — fix
the payload and retry.

#### Link the design to its question node

When the Framing Brief carries a `node_id`, link the design you just created to that node of
the theme's question tree, with the `id` that `design_io create` returned:

```bash
tree_io link --theme FP --node FP-Q02 --design FP-H01
```

- `--theme` and `--node` come from the Brief's `theme_id` and `node_id`. The node belongs to
  that theme, so a design the analyst moved to another theme is not linked: say so, and that
  `/analysis-framing` can place it in the other theme's tree.
- When no `node_id` came in (no Framing Brief, or a Brief without one), run
  `tree_io get --theme {theme_id}`. When it prints a tree, show its questions with their ids
  and ask which question this design answers, or none. Link the design to the one the analyst
  picks with the same `tree_io link` command, that question's id as `--node`.
- With no `node_id` and no question tree (`tree_io get` prints `{}`), or when the analyst picks
  none, skip this step. The design is created unlinked, as before.
- If `tree_io link` exits non-zero, show the error. The design stays as written; do not
  create it again.
- Never run `tree_io add-node` or write the tree file here. Nodes are made by `/analysis-framing`.

#### Copy what the analyst heard

The node may carry an answer the analyst heard from a person (`/analysis-reflection` keeps
it on the node). Run this every time `tree_io link` succeeded, with the same three ids:

```bash
tree_io copy-hearing --theme FP --node FP-Q02 --design FP-H01
```

- It copies the answer into the design's journal as one `hearing` event, with who answered
  and when, so that a later answer can cite it. `"copied": true` comes with the event:
  tell the analyst its id.
- `"copied": false` means the node has no answer, or the same answer is already in the
  journal. Both are fine; go on.
- Never retype the answer into the journal yourself, and never write a `hearing` event for
  it by hand: `tree_io` copies the text as the analyst gave it.
- A finished design (`explored`, `supported`, `rejected`, `inconclusive`) is refused: its journal is
  the record it was concluded on. The answer stays on the node, and the next design linked
  there gets it from its own `copy-hearing`. Never reopen the design or write the event
  yourself to get around it.
- If it exits non-zero, show the error. The design and its link stay as written.

### Step 3b: Update an Existing Design (optional)

To add or modify fields, pipe a partial-changes JSON to `design_io update`. Only the
provided fields change; `updated_at` is refreshed and `referenced_knowledge` is merged.

```bash
echo '{"next_action": {"if_supported": "パネルFEへ進む", "if_rejected": {"reason": "相関なし", "pivot": "時系列分析"}}}' \
  | design_io update --id FP-H01
echo '{"source_ids": ["sales_monthly", "stores"]}' | design_io update --id FP-H01
```

To change the intent, the design must be `in_review` or `revision_requested`, and the change
sends the fields of the other form as `null` so they are dropped:

```bash
echo '{"analysis_intent": "exploratory", "exploration_question": "<question>", "exploration_background": "<background>", "hypothesis_statement": null, "hypothesis_background": null, "next_action": null, "metrics": [{"target": "<metric>", "tier": "primary", "comparison": "<what is compared, no threshold>"}]}' \
  | design_io update --id FP-H01
```

`design_io` does not read the `comparison` of the metrics, so send `metrics` with it when the
intent changes: a new confirmation needs the criterion of its verdict in the `primary` metric's
`comparison`, and a new exploration drops it (Step 2 "Criterion"). Confirm the rewritten
`comparison` with the analyst. `metrics` is replaced as a whole.

A legacy exploration (`exploratory` with a `hypothesis_statement`) that is in fact a confirmation
can be set to `confirmatory` in any status:
`echo '{"analysis_intent": "confirmatory"}' | design_io update --id FP-H01`
([ADR-0049](../../docs/adr/0049-legacy-exploration-stays-readable-and-is-marked.md)).
If it is refused because `hypothesis_background` is blank, a confirmation needs it written: ask
the analyst for it and send it in the same update. That works only while the design is
`in_review` or `revision_requested`; in any other status the hypothesis and its background must
stay as they are.

To change `source_ids`, ask and check the ids as "Data sources" (Step 2) says first. `source_ids`
is replaced as a whole, so send every id the design uses, not only the new ones.

### Step 4: Confirm and Suggest Next Steps
- Show the returned `id` (e.g., "FP-H01") to the user
- Confirm the YAML file location: `.insight/designs/FP-H01_hypothesis.yaml`
- If the design was linked, show the question node it answers (e.g., "FP-Q02")
- Suggest next steps:
  - Refine the design: add `chart` / `decision_context` (and `next_action` for a confirmation) via `design_io update`
  - **Start recording reasoning: `/analysis-journal FP-H01`**
  - **Review and conclude: `/analysis-reflection FP-H01`**

## design_io Reference

`design_io <command>` (provided on PATH by the plugin; targets your project's
`.insight/`). Payloads are JSON on stdin; results are JSON on stdout.

| Command | Purpose | Input |
|---------|---------|-------|
| `list [--status S]` | List existing designs | — |
| `get --id ID` | Retrieve a design | — |
| `create` | Create new design (auto id, validated) | stdin: `{title, analysis_intent, methodology, exploration_question + exploration_background (exploration) or hypothesis_statement + hypothesis_background (confirmation), theme_id?, parent_id?, source_ids?, metrics?, explanatory?, chart?, next_action? (confirmation), decision_context?}` |
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
| `analysis_intent` | AnalysisIntent | `"exploratory"`, `"confirmatory"` for a new design. A saved `"mixed"` is read as a confirmation; a new one is refused | `"confirmatory"` (a draft only: Step 2 asks) |
| `methodology.method` | str | free text (required, non-empty) | — |
| `methodology.package` | str | free text (optional) | `""` |
| `methodology.reason` | str | free text (optional) | `""` |
| `decision_context.decision_maker` | str | free text (required and non-empty when `decision_context` is present) | — |
| `decision_context.decision` | str | free text (required and non-empty when `decision_context` is present) | — |
| `source_ids` | list[str] | ids of catalog sources. Not checked by `design_io`: "Data sources" (Step 2) writes only ids `catalog_io describe` returns in `sources` | `[]` |
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
| pydantic `ValidationError` on `decision_context.decision_maker` / `decision_context.decision` | Only one side of the decision context was given | Ask for the missing side, or drop `decision_context`; nothing was written |
| pydantic `ValidationError` naming `exploration_question`, `exploration_background`, `hypothesis_statement`, `hypothesis_background` or `next_action` | The payload does not match its intent: an exploration with a hypothesis or `next_action`, a confirmation without its hypothesis, or neither | Send only the fields of the chosen intent; nothing was written |
| `ValueError` naming `mixed` or a legacy exploration | A new design chose `mixed`, or an exploration with a hypothesis | Ask the intent again (探索 or 検証); nothing was written |

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
| /analysis-reflection | → /analysis-design | 派生の分析設計を作る場合（直した検証仮説、探索の後に確かめる検証仮説、次の探索の問い） |
| /analysis-revision | → /analysis-design | レビュー修正で大きな方針変更が必要な場合 |
| /analysis-journal | → /analysis-design | 分岐で派生の分析設計を作る場合（`parent_id` に分岐元） |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Hypothesis text follows the user's language (usually Japanese)

## Workflow Rules

### Hypothesis Design Workflow

### Status Flow

Designs use the `DesignStatus` model. A new design starts `in_review`. The form of the
design decides how it ends: an exploration ends `explored`, and a confirmation ends on a verdict.

**Confirmation** (`confirmatory`; also a saved `mixed` and a legacy exploration):

```
in_review ─┬→ revision_requested → (back to in_review / analyzing / a verdict)
           ├→ analyzing → in_review | supported | rejected | inconclusive
           └→ supported | rejected | inconclusive   (terminal — no exit)
```

**Exploration** (`exploratory` with `exploration_question`):

```
in_review ─┬→ revision_requested → (back to in_review / analyzing / explored)
           ├→ analyzing → in_review | explored
           └→ explored   (terminal — no exit)
```

- **in_review**: Created, under review.
- **revision_requested**: Review asked for changes.
- **analyzing**: The analysis is running. `/analysis-reflection` concludes it directly;
  going back to `in_review` is an optional review of the result.
- **supported / rejected / inconclusive**: The verdict on a confirmation's hypothesis. Terminal.
- **explored**: An exploration is finished. It gives no verdict. Terminal.

Status transitions MUST go through `design_io transition` (or `append_review_batch`),
which validates the move against `VALID_TRANSITIONS` in `validate.py` and the form of the
design. Illegal moves (e.g. `analyzing → revision_requested`, a verdict on an exploration,
`explored` for a confirmation, or any exit from a terminal state) are rejected.

### Theme ID Rules

- Every design MUST have a `theme_id` linking it to a research theme.
- Theme IDs must match `[A-Z][A-Z0-9]*` (e.g., `CHURN`, `PRICING`).
- Use `/analysis-design` skill to create designs with proper theme association.

### Derived Hypotheses

- A design may reference `parent_id` to indicate it derives from another design.
- Write the id of a design that exists. `design_io` does not check the parent: it does not look up
  whether the id exists or what status it is in.
- This creates a tree of derived designs for tracking research lineage.

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
