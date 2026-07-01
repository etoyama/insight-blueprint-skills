# ARCHITECTURE: insight-blueprint-skills

本書は軽量版（target state）アーキテクチャの**正本**。CLAUDE.md §2 は要約とポインタのみを置く。
プロダクト要件は [PRD.md](PRD.md)、個別決定は [docs/adr/](adr/) を参照。

**移行中**: MCPサーバ / WebUI / SQLite はまだツリーに残り、Epic E1–E4 で段階的に除去される
（[ADR-0001](adr/0001-drop-mcp-server-embed-validation.md)）。本書は移行の到達点を示す。

## 不変条件（invariants）

- **No daemon / No MCP server / No SQLite**。常駐プロセスを持たない。
- 検証はプロセスではなく**ライブラリ**として埋め込む（SQLite と同じ転換）。
- 設計書整合性の**正本は `validate.py` の1箇所**。hook と skill の双方が再利用する。
- リリースは **tag 駆動**（`publish.yml` は `v*` タグで発火）。main マージ＝publish ではない。

## 現状 → 目標

```mermaid
flowchart LR
    subgraph FULL["現状: full（移行で除去）"]
        mcp["MCP server (FastMCP)"]
        web["WebUI / REST (FastAPI+React)"]
        sql["SQLite (FTS5)"]
    end
    subgraph LIGHT["目標: lightweight"]
        skills["Skill layer (skills/)"]
        validate["Validation library (validate.py)"]
        hook["pre-write hook"]
        yaml["Skill-managed YAML (.insight/)"]
        marimo["marimo + lineage"]
    end
    FULL -->|"E1–E4 で撤去"| LIGHT
```

## コンポーネントと責務

```mermaid
flowchart TD
    user["分析者"]
    cc["Claude Code"]
    subgraph plugin["insight-blueprint-skills（plugin）"]
        skills["Skill layer（skills/）<br/>分析能力・拡張点"]
        validate["validate.py<br/>純関数検証（単一正本）"]
        hook["pre-write hook<br/>.claude/hooks/validate-design.py"]
        marimo["marimo + lineage<br/>notebook 契約・加工透明性"]
    end
    yaml["(.insight/) designs / journals / catalog / knowledge — YAML"]

    user --> cc --> skills
    skills -->|read/write| yaml
    cc -->|Write/Edit/MultiEdit| hook
    hook -->|検証| validate
    hook -->|"対象: *_hypothesis.yaml"| yaml
    skills --> marimo
```

- **Skill layer（`skills/`）** — すべての分析能力。拡張点。設計書・journal・catalog 等の YAML を直接 read/write する。
- **Validation library（`src/insight_blueprint/validate.py`）** — I/O を持たない純関数。
  Pydantic スキーマ検証（`AnalysisDesign`）+ 状態遷移ガード（`VALID_TRANSITIONS`）。設計書整合性の単一正本。
- **pre-write hook（`.claude/hooks/validate-design.py`）** — `.insight/designs/*_hypothesis.yaml` への
  Write/Edit/MultiEdit を `validate.py` で検証し、違反を `exit 2` でブロックする I/O 殻。
- **Skill-managed YAML（`.insight/`）** — designs / journals / catalog / knowledge。skill が直接管理する。
- **marimo + lineage（`src/insight_blueprint/lineage/`, `_templates/`）** — notebook 契約と加工の透明性・追跡。

## 代表シーケンス（分析ワークフロー）

分析者とモジュールの時系列インタラクション。仮説設計 → 検証ガード → 分析 → 記録の代表フローを示す
（個別 Epic の詳細シーケンスは各 Epic Design Doc 側）。

```mermaid
sequenceDiagram
    actor U as 分析者
    participant CC as Claude Code
    participant SK as Skill layer
    participant H as pre-write hook
    participant V as validate.py
    participant FS as .insight/（YAML）
    participant MO as marimo + lineage

    U->>CC: 「仮説を設計したい」等の依頼
    CC->>SK: skill 起動（例: /analysis-design）
    SK->>CC: hypothesis.yaml を Write/Edit
    Note over CC,H: *_hypothesis.yaml への書込は PreToolUse で捕捉
    CC->>H: PreToolUse(tool_input)
    H->>FS: read_yaml(現ファイル)
    FS-->>H: current_data | None
    H->>V: validate_design_change(new_data, current_data)
    V-->>H: list[str]（空=合格）
    alt 違反
        H-->>CC: exit 2（書込ブロック）
        CC-->>U: 検証エラーを提示
    else 合格
        H-->>FS: 書込実行（exit 0）
        SK->>MO: 分析 notebook 実行・lineage 記録
        SK->>FS: journal / reflection を更新
        SK-->>U: 結果・次アクションを提示
    end
```

## Epic マッピング

| Epic | 主に触るコンポーネント |
|---|---|
| E1 | WebUI/REST（撤去）— full の縮小 |
| E2 | Validation library + pre-write hook（新設） |
| E3 | Skill layer ↔ Skill-managed YAML（設計書ライフサイクルの直接 I/O 化、design_io） |
| E3.5 | catalog / premortem / lineage の MCP→YAML 変換 + batch-analysis 撤去（E4 前提） |
| E4 | MCP server（撤去） |
| E5 | catalog（柔軟化）/ premortem（自立化） |

## 参照

- [ADR-0001](adr/0001-drop-mcp-server-embed-validation.md) — MCPサーバ廃止・検証の埋め込み化
- [ADR-0002](adr/0002-trunk-based-epic-stacking.md) — トランクベース + stacked Epic
