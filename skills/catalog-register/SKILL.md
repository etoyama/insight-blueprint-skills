---
name: catalog-register
version: "1.2.0"
description: |
  Guides Claude through discovering data source schemas and registering them
  in the insight-blueprint data catalog. Supports CSV, API, and SQL sources.
  Triggers: "register data source", "add to catalog", "catalog register",
  "データカタログ登録", "ソース登録", "カタログにデータを追加".
disable-model-invocation: true
argument-hint: "[source_type: csv|api|sql]"
---

# /catalog-register — Data Source Registration

Guides Claude through exploring a data source's structure and registering it
in the insight-blueprint catalog by writing `.insight/catalog/` YAML directly via
the `catalog_io` helper (no MCP server).

**catalog_io CLI** (run from project root; JSON payload on stdin, JSON on stdout;
`--base-dir` defaults to `.insight`):

```bash
echo '<source-json>' | uv run python -m skills._shared.catalog_io create
echo '<changes-json>' | uv run python -m skills._shared.catalog_io update --id <source_id>
uv run python -m skills._shared.catalog_io get --id <source_id>
uv run python -m skills._shared.catalog_io get-schema --id <source_id>
uv run python -m skills._shared.catalog_io search --query "<q>" [--type csv] [--tags a,b]
```

> Note: the create payload uses `id` (not `source_id`) for the source identifier.

## When to Use
- User wants to register a new data source (CSV file, API endpoint, SQL table)
- User wants to catalog an existing dataset with schema information
- User mentions "データカタログ", "ソース登録", or "register"

## When NOT to Use
- Updating an existing source (use `catalog_io update` directly)
- Searching the catalog (use `catalog_io search` directly)
- Authoring domain knowledge for a source (→ /knowledge-extract)

## Workflow

### Step 0: User Confirmation Gate

Before proceeding, confirm with the user:

- Ask: "このソースをカタログに登録しますか？"
- If the user declines, exit gracefully with a brief message and do not proceed
- If the user confirms, continue to Step 1

### Step 1: Determine Source Type

`type` is an **open string** (E5c / ADR-0004): any non-empty value is valid. Suggest
the conventional values but accept whatever fits the source:
- **csv** — Local file with headers
- **api** — REST API endpoint (e.g., e-Stat, custom API)
- **sql** — Database table (e.g., BigQuery, PostgreSQL)
- …or another kind: `parquet`, `gsheet`, `bigquery`, `graphql`, `excel`, etc.

If `$ARGUMENTS` is provided, use it as the source type. The workflows below cover the
three most common cases; for other types, reuse the closest one and adjust `connection`.

### Step 2: Explore Data Structure

Follow the appropriate exploration workflow below.

### Step 3: Build Registration

Construct the `catalog_io create` JSON payload with the discovered schema.

### Step 4: Register and Confirm

Pipe the payload to `catalog_io create` and show the returned JSON to the user.
Optionally verify with `catalog_io get-schema --id <id>` and `catalog_io search`.

---

## CSV Source Workflow

### Step 2a: Read File Headers

1. Ask the user for the CSV file path
2. Read the first 5 rows to discover columns:
   ```
   Read the file with limit=5 to see headers and sample data
   ```
3. For each column, infer:
   - **name**: Header name
   - **type**: Infer from sample values (string, integer, float, date, boolean)
   - **description**: Ask user or infer from column name
   - **nullable**: Check if any sample values are empty
   - **examples**: First 2-3 non-empty values

### Step 2b: Gather Metadata

Ask the user for:
- **source_id**: A short slug (e.g., `local-survey-2024`)
- **name**: Human-readable name
- **description**: What this dataset contains

### Step 3a: Build Call

```bash
echo '{
  "id": "local-survey-2024",
  "name": "Local Survey 2024",
  "type": "csv",
  "description": "Annual community survey results",
  "connection": {"file_path": "data/survey_2024.csv", "encoding": "utf-8", "delimiter": ","},
  "columns": [
    {"name": "respondent_id", "type": "integer", "description": "Unique respondent ID"},
    {"name": "age", "type": "integer", "description": "Respondent age", "range": {"min": 18, "max": 99}}
  ],
  "tags": ["survey", "local"]
}' | uv run python -m skills._shared.catalog_io create
```

---

## API Source Workflow

### Step 2a: Identify API Structure

1. Ask the user for the API base URL and provider
2. For **e-Stat** APIs:
   - Use `getMetaInfo` endpoint to discover table structure:
     ```
     GET {base_url}/app/json/getMetaInfo?appId=$API_KEY&statsDataId={table_id}
     ```
   - **Security**: API keys must come from environment variables. Never hardcode keys in YAML or catalog entries.
   - Parse CLASS_INF to extract column definitions
3. For **custom APIs**:
   - Ask the user for a sample endpoint
   - Fetch the response (or ask user to paste a sample)
   - Analyze JSON structure to extract field names and types

### Step 2b: Gather Metadata

Ask the user for:
- **source_id**: A short slug (e.g., `estat-population`)
- **name**: Human-readable name
- **description**: What this data provides
- **auth**: Authentication method (`none`, `api_key`, `oauth`)

### Step 3a: Build Call

```bash
echo '{
  "id": "estat-population",
  "name": "e-Stat Population Census",
  "type": "api",
  "description": "Japanese population statistics from e-Stat",
  "connection": {"base_url": "https://api.e-stat.go.jp/rest/3.0", "provider": "e-stat", "table_id": "0003348423", "auth": "api_key"},
  "columns": [
    {"name": "prefecture_code", "type": "string", "description": "JIS X 0401 code (01-47)", "nullable": false, "examples": ["01", "13", "47"]},
    {"name": "year", "type": "integer", "description": "Census year", "range": {"min": 2000, "max": 2024}},
    {"name": "population", "type": "integer", "description": "Total population", "unit": "people"}
  ],
  "tags": ["government", "population", "demographics"],
  "primary_key": ["prefecture_code", "year"],
  "row_count_estimate": 2350
}' | uv run python -m skills._shared.catalog_io create
```

---

## SQL Source Workflow

### Step 2a: Query Schema Metadata

1. Ask the user for connection details (provider, project/database, table)
2. For **BigQuery**:
   ```sql
   SELECT column_name, data_type, is_nullable, description
   FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
   WHERE table_name = '{table}'
   ORDER BY ordinal_position
   ```
3. For **PostgreSQL/MySQL**:
   ```sql
   SELECT column_name, data_type, is_nullable,
          col_description(c.oid, a.attnum) as description
   FROM information_schema.columns
   WHERE table_name = '{table}'
   ORDER BY ordinal_position
   ```
4. Ask the user to run the query and paste results, or run it if credentials are available

### Step 2b: Gather Metadata

Ask the user for:
- **source_id**: A short slug (e.g., `bq-sales-data`)
- **name**: Human-readable name
- **description**: What this table contains

### Step 3a: Build Call

```bash
echo '{
  "id": "bq-sales-data",
  "name": "BigQuery Sales Data",
  "type": "sql",
  "description": "Daily sales transaction data from BigQuery",
  "connection": {"provider": "bigquery", "project_id": "my-gcp-project", "dataset": "analytics", "table": "daily_sales"},
  "columns": [
    {"name": "sale_date", "type": "date", "description": "Transaction date"},
    {"name": "product_id", "type": "string", "description": "Product identifier"},
    {"name": "amount", "type": "float", "description": "Sale amount", "unit": "JPY"},
    {"name": "quantity", "type": "integer", "description": "Units sold"}
  ],
  "tags": ["sales", "bigquery"],
  "primary_key": ["sale_date", "product_id"],
  "row_count_estimate": 500000
}' | uv run python -m skills._shared.catalog_io create
```

---

## catalog_io Reference

`python -m skills._shared.catalog_io <command>` (from project root):

| Command | Purpose | Input |
|---------|---------|-------|
| `create` | Register a new source (writes sources/ + empty knowledge/) | stdin: `{id, name, type, description, connection, columns?, tags?, primary_key?, row_count_estimate?}` |
| `update --id ID` | Partial update | stdin: `{<fields>}` |
| `get --id ID` | Full source YAML | — |
| `get-schema --id ID` | Column schema | — |
| `search --query Q [--type T] [--tags a,b]` | Compact hits across sources + knowledge | — |
| `get-knowledge --id ID [--category C]` | Knowledge entries for a source | — |
| `add-knowledge --id ID` | Append/upsert knowledge (authoring: → /knowledge-extract) | stdin: `{entries:[...]}` |

Validation runs inside `catalog_io` (DataSource model) before writing; invalid input
exits non-zero with nothing written.

## Error Handling

| Error (stderr) | Cause | Action |
|-------|-------|--------|
| `Source 'X' already exists` | Duplicate id | Use `catalog_io update` or choose a different ID |
| `Invalid source_id '...'` | id not `[a-zA-Z0-9_-]+` | Use a slug id |
| pydantic `ValidationError` | Missing required field, or empty `type` | `type` may be any non-empty string; fix the payload |

## Chaining

| From | To | When |
|------|-----|------|
| /analysis-framing | → /catalog-register | Data missing: "必要なデータを登録するなら /catalog-register" |
| /analysis-reflection | → /catalog-register | A new data source needs registering |
| /catalog-register | → /knowledge-extract | Source registered; capture what's known about it |
| /catalog-register | → /analysis-framing | Registration complete, return to framing: "フレーミングに戻るなら /analysis-framing" |
| /catalog-register | → /analysis-design | Registration complete, continue design: "デザイン作成を続けるなら /analysis-design" |

## Language Rules
- Follow project CLAUDE.md language settings. Default to Japanese if no setting.
- Code, IDs, tool names, and YAML fields always stay in English.
- Descriptions can be in the user's preferred language

## Workflow Rules

# Data Catalog Operation Rules

### Source Registration

- Use `/catalog-register` skill to register new data sources interactively.
- Each source gets a unique `source_id` and is stored as `.insight/catalog/sources/<source_id>.yaml`.
- Source metadata includes: name, type (csv/api/sql), description, connection info, tags.

### Schema Management

- Schemas are stored within each source YAML under `schema_info.columns`.
- Schema changes go through `catalog_io update` (pass a new `columns` list).
- Breaking schema changes should be noted in the source description.

### Domain Knowledge

- Knowledge is stored in `.insight/catalog/knowledge/{source_id}.yaml` (created empty on register).
- Knowledge entries link back to their source via `source_id`.
- Reads: `catalog_io get-knowledge --id <source_id>`; search spans knowledge too.
- Writes: `catalog_io add-knowledge --id <source_id>` (validates + upserts by `key`).
- **Authoring/extraction** is Claude-native via `/knowledge-extract` (reads a
  concluded analysis and proposes source-scoped entries). Findings/conclusions stay
  in reflection, not the catalog.
