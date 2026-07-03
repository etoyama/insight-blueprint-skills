# ARCHITECTURE: insight-blueprint-skills

本書は軽量版（target state）アーキテクチャの**正本**。CLAUDE.md §2 は要約とポインタのみを置く。
プロダクト要件は [PRD.md](PRD.md)、個別決定は [docs/adr/](adr/) を参照。

**移行状況**: MCPサーバ / WebUI / SQLite は E1–E4 で除去済み
（[ADR-0001](adr/0001-drop-mcp-server-embed-validation.md)）。本書は現行アーキテクチャを表す。
E5 で解体計画は完結: premortem 自立化（E5a, report-only 化）/ knowledge 抽出強化（E5b,
Claude-native + source-scoped）/ catalog 柔軟化（E5c, open string taxonomy, [ADR-0004](adr/0004-open-string-catalog-taxonomy.md)）。

## 不変条件（invariants）

- **No daemon / No MCP server / No SQLite**。常駐プロセスを持たない。
- 検証はプロセスではなく**ライブラリ**として埋め込む（SQLite と同じ転換）。
- 設計書整合性の**正本は `validate.py` の1箇所**。hook と skill の双方が再利用する。
- リリースは **tag 駆動**（`publish.yml` は `v*` タグで発火）。main マージ＝publish ではない。

## 構成（E1–E4 完了後）

full（MCP server / WebUI / SQLite）は撤去済み。現行は軽量版のみ。

```mermaid
flowchart LR
    subgraph REMOVED["撤去済み（E1–E4）"]
        mcp["MCP server (FastMCP)"]
        web["WebUI / REST (FastAPI+React)"]
        sql["SQLite (FTS5)"]
    end
    subgraph LIGHT["現行: lightweight"]
        skills["Skill layer (skills/ + _shared/io)"]
        validate["Validation library (validate.py)"]
        hook["pre-write hook"]
        yaml["Skill-managed YAML (.insight/)"]
        marimo["marimo + lineage"]
    end
    REMOVED -.->|削除| LIGHT
```

## コンポーネントと責務

```mermaid
flowchart TD
    user["分析者"]
    cc["Claude Code"]
    subgraph plugin["insight-blueprint-skills（plugin）"]
        skills["Skill layer（skills/）<br/>分析能力・拡張点"]
        validate["validate.py<br/>純関数検証（単一正本）"]
        hook["pre-write hook<br/>hooks/validate-design.py（plugin 同梱）"]
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
- **pre-write hook（`hooks/validate-design.py`, plugin 同梱 `hooks/hooks.json`）** —
  `.insight/designs/*_hypothesis.yaml` への Write/Edit/MultiEdit を plugin の uv 環境で `validate.py`
  にかけ、違反を `exit 2` でブロックする I/O 殻。利用者の install 先プロジェクトでも効く
  （この repo の `.claude/settings.json` は dev 用に同スクリプトを配線）。
- **Skill-managed YAML（`.insight/`）** — designs / journals / catalog / knowledge。skill が直接管理する。
- **marimo + lineage（`src/insight_blueprint/lineage/`）** — 分析 notebook は同梱テンプレートでなく、
  **`/analysis-notebook` skill が設計書の `methodology` から 8-cell 契約に沿って生成・実行**する
  （`skills/analysis-notebook/references/notebook-contract.md`）。`lineage`（`tracked_pipe` / Mermaid export）は
  optional な `insight-blueprint-lineage[notebook]` パッケージで、notebook 内の加工を追跡・可視化する。

### Skill invocation model

**既定は明示・対話型**: 全 skill は frontmatter で `disable-model-invocation: true`（明示 `/command` 起動）
であり、各ステップはユーザーが明示的に起動する。無人バッチ実行は batch-analysis の役割で E3.5 で意図的に撤去された。

**selective autonomy（`/analysis-auto`）**: driver スキル `/analysis-auto` を起動したときに限り、Claude が
既存 skill を順に駆動し、**本物の判断（KEEP ゲート）でだけ停止**する guided autopilot になる。invocation フラグは
大域変更しない（自律性はこの run に限定）。KEEP ゲート = 仮説確定 / データソース登録 / premortem `HARD_BLOCK`・`HIGH` /
notebook の非 allowlist・宣言 source 以外の外部通信 / 結論。notebook の auto 実行は premortem 通過 + allowlist +
宣言 source 限定のときのみ。詳細は [ADR-0005](adr/0005-selective-autonomous-chaining.md)。**「auto mode」は無人ではなく
guided autopilot**（対話型・オプトイン）である。

## ディレクトリ構成（開発時 vs plugin 利用時）

この plugin は **コードの在処**（plugin 本体）と **データの在処**（利用者の分析成果物 `.insight/`）を
分離する。開発リポジトリでは両者が**同一ツリーに同居**するため混同しやすい。実際、install 先で
動かない不具合（Epic 09）はこの2役割の混同が根本原因だった（cwd 前提・repo レイアウト前提のコマンドが
「コード置き場＝データ置き場」を暗黙に仮定していた）。以下で2つの視点を明確に分ける。
実行時のパス解決の詳細は [ADR-0006](adr/0006-plugin-execution-model.md)。

### 1. 開発リポジトリ上の構成（このリポジトリ）

開発時は **cwd = リポジトリルート** で、plugin コードと自分の分析データ（`.insight/`）が
**同じツリーに同居**する。これが「開発では動くのに install 先で動かない」錯覚を生む。

```
insight-blueprint-skills/          ← リポジトリルート（＝ plugin 配布物の中身）
├── .claude-plugin/                # plugin マニフェスト（plugin.json / marketplace.json）
├── bin/                           # plugin 有効時に PATH に載る: design_io / catalog_io / premortem ラッパー
├── hooks/                         # plugin 同梱 hook: hooks.json + validate-design.py
├── skills/                        # 全 skill + _shared/（design_io.py / catalog_io.py / config_loader.py / models.py）+ premortem/
├── src/insight_blueprint/         # PyPI パッケージ insight-blueprint-lineage: models/ · validate.py · lineage/
├── tests/  docs/  scripts/
├── pyproject.toml · uv.lock       # ← この uv プロジェクトが「plugin の実行環境」を供給する
├── .claude/                       # dev 専用: settings.json が hook をローカル配線（配布されない）
└── .insight/                      # dev 専用のサンプル作業データ（config.yaml + rules/。このリポジトリ自身の分析ワークスペース）
```

- **配布物** = リポジトリツリーそのもの。install 時これが `${CLAUDE_PLUGIN_ROOT}` に展開される。
- **dev 専用**（配布物ではない）: `.claude/`（ローカル hook 配線）と リポジトリ直下の `.insight/`。
  後者はこのリポジトリを「1人の利用者プロジェクト」として使うときの作業データで、利用者の `.insight/` とは無関係。
- したがって dev では `${CLAUDE_PLUGIN_ROOT}`（コード）と `${CLAUDE_PROJECT_DIR}`（データ）が
  **たまたま同じ**（どちらもリポジトリルート）。install 先ではこれが分離する（下記）。

### 2. plugin 利用者視点の構成

`/plugin marketplace add … && /plugin install …` で導入すると、2つのルートが**物理的に分離**する。

| ルート | 変数 | 実体 | 誰が触る |
|---|---|---|---|
| plugin コード | `${CLAUDE_PLUGIN_ROOT}` | Claude Code の plugin キャッシュ（例 `~/.claude/plugins/cache/…/insight-blueprint-skills/`） | 触らない（読み取り専用の配布物） |
| 利用者データ | `${CLAUDE_PROJECT_DIR}/.insight/` | **自分のプロジェクト直下** | 分析成果物すべてがここに出る |

利用者の分析成果物は**すべて自分のプロジェクトの `.insight/`** に出力される（plugin 側には一切書かない）:

```
<あなたのプロジェクト>/.insight/          ← ${CLAUDE_PROJECT_DIR}/.insight
├── config.yaml                     # 任意: premortem 閾値など（無ければ既定値）
├── rules/
│   └── package_allowlist.yaml      # 任意: notebook が使ってよいパッケージ許可リスト
├── designs/
│   ├── {id}_hypothesis.yaml        # design_io create/update（pre-write hook が検証）
│   ├── {id}_journal.yaml           # journal イベント
│   └── {id}_reviews.yaml           # review バッチ
├── catalog/
│   ├── sources/{id}.yaml           # /catalog-register
│   └── knowledge/{id}.yaml         # /knowledge-extract
├── notebooks/
│   ├── {id}.py                     # /analysis-notebook が生成する 8-cell marimo notebook
│   ├── {id}_flat.py                # marimo export script（実行可能なフラット版）
│   ├── {id}_verdict.json           # verdict 副作用（skill が読み戻して journal に反映）
│   └── {id}.html                   # 任意: 閲覧用レポート
└── lineage/
    └── {id}.mmd                    # lineage の Mermaid 図
```

**marimo notebook はどこに出るか（混乱ポイントの明示回答）**: 利用者プロジェクトの
`${CLAUDE_PROJECT_DIR}/.insight/notebooks/`（および `lineage/`）に出る。**plugin ディレクトリではない**。
理由は下のパス解決機構にある。

### パス解決機構（なぜ同じ `.insight/` に着地するのか）

コードは `${CLAUDE_PLUGIN_ROOT}` にあるのに、出力は `${CLAUDE_PROJECT_DIR}/.insight/` に落ちる。
これを実現する経路は**2種類**あり、着地先は同じでも仕組みが違う。

| 経路 | cwd | パス解決 | 出力先 |
|---|---|---|---|
| `design_io` / `catalog_io` / `premortem`（bin ラッパー） | `cd ${CLAUDE_PLUGIN_ROOT}` に**移動する** | 絶対パス env `INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight` で解決 | 利用者 `.insight/` |
| `/analysis-notebook`（marimo 実行） | **利用者プロジェクトのまま**（移動しない） | 相対パス `.insight/notebooks/…`（cwd 基準） | 利用者 `.insight/` |

ポイントは notebook 経路の `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook …`:
`--project` は **実行環境（marimo/pandas/insight_blueprint を供給する uv 環境）だけを plugin から借りる**
指定で、**cwd は移動しない**。だから notebook 内の相対 `.insight/…` は利用者プロジェクトに解決される。
一方 bin ラッパーは `cd` で plugin へ移動する代わりに、絶対 `INSIGHT_BASE_DIR` でデータ先を指す。
どちらも「コードは plugin・データは利用者プロジェクト」を別の手段で満たしている。

## 代表シーケンス

### 設計書の書込と検証ガード

`*_hypothesis.yaml` を書くときの検証フロー。skill は `/command` で明示起動され、書込は
pre-write hook が捕捉して検証する。

```mermaid
sequenceDiagram
    actor U as 分析者
    participant CC as Claude Code
    participant SK as Skill (/analysis-design)
    participant H as pre-write hook
    participant V as validate.py
    participant FS as .insight/（YAML）

    U->>CC: /analysis-design（明示起動）
    CC->>SK: skill 実行
    SK->>U: 確認ゲート + 必須項目インタビュー
    U-->>SK: 回答
    SK->>CC: hypothesis.yaml を Write/Edit
    Note over CC,H: *_hypothesis.yaml への書込は PreToolUse で捕捉
    CC->>H: PreToolUse(tool_input)
    H->>V: validate_design_change(new, current)
    alt 違反
        H-->>CC: exit 2（書込ブロック）
        CC-->>U: 検証エラーを提示
    else 合格
        H-->>FS: 書込実行（exit 0, status=in_review）
        SK-->>U: 次アクションを提示
    end
```

### 分析ワークフロー全体（対話型・明示起動）

end-to-end の代表フロー。既定では**各 `/skill` はユーザーが明示的に起動する**が、`/analysis-auto`
（guided autopilot）を使うと driver がこの同じ経路を駆動し KEEP ゲートでだけ停止する（上記 «Skill invocation model» /
[ADR-0005](adr/0005-selective-autonomous-chaining.md)）。**notebook の生成・実行は `/analysis-notebook` が design の
`methodology` から 8-cell 契約に沿って行う**（`skills/analysis-notebook/references/notebook-contract.md`）。
`/analysis-review`・`/premortem`・`/data-lineage` は任意ステップ。

```mermaid
sequenceDiagram
    actor U as 分析者
    participant CC as Claude Code
    participant IO as design_io / catalog_io
    participant MO as marimo + lineage
    participant FS as .insight/（YAML）

    Note over U,FS: 各ステップは /command で明示起動（対話型・human-in-the-loop）
    U->>CC: /analysis-framing → /analysis-design
    CC->>IO: create（hypothesis.yaml, status=in_review）
    IO->>FS: atomic write

    opt 任意: レビュー / 事前リスク評価
        U->>CC: /analysis-review
        CC->>IO: review-batch（コメント記録 + status 遷移）
        U->>CC: /analysis-revision（revision_requested を消化）
        U->>CC: /premortem（高コストアクセス前の risk report, report-only）
    end

    Note over U,MO: 分析実行: /analysis-notebook が methodology から<br/>8-cell marimo notebook を生成・実行（tracked_pipe で lineage 追跡）
    U->>CC: /analysis-notebook
    CC->>MO: notebook 生成 → marimo export script → 実行 → verdict.json / lineage.mmd
    MO-->>CC: 結果・図表
    CC->>IO: verdict を journal に追記（observe/evidence/question）

    U->>CC: /analysis-journal（観察・証拠・決定を記録）
    CC->>IO: journal 追記
    opt 任意: lineage 図出力
        U->>CC: /data-lineage（Mermaid export）
    end
    U->>CC: /analysis-reflection（結論 → status 遷移）
    CC->>IO: transition（supported / rejected / inconclusive）
    opt 任意: 知見の永続化
        U->>CC: /knowledge-extract（source-scoped 知見を catalog へ）
    end
```

### guided autopilot（`/analysis-auto`）の詳細シーケンス

初学者が最初に使う想定の入口。driver `/analysis-auto` が各 skill を駆動し、**KEEP ゲート**（太字の
`U に確認`）でだけ停止する。個々の skill・CLI・premortem・notebook 実行との詳細インタラクションを示す
（[ADR-0005](adr/0005-selective-autonomous-chaining.md)）。

```mermaid
sequenceDiagram
    actor U as 分析者
    participant D as /analysis-auto (driver)
    participant IO as design_io / catalog_io
    participant H as pre-write hook + validate.py
    participant PM as /premortem
    participant NB as /analysis-notebook + marimo
    participant FS as .insight/

    U->>D: /analysis-auto {theme|design id}
    D->>IO: get / list（現在地を判定）
    IO-->>D: design（無 / in_review / analyzing / results）

    Note over D,FS: framing（仮説が無ければ）
    D->>IO: .insight/ 探索（catalog / 既存 design / 知識）
    D->>U: 【KEEP】Data Map 提示 + Direction Dialogue（方向を一緒に決める）
    U-->>D: 方向を合意 → Framing Brief
    Note over D,FS: design（AUTO: Framing Brief から各フィールドを自動ドラフト）
    D->>U: 【KEEP】設計全体を確認（仮説 + 手法 + metrics + explanatory の因果役割 + intent）
    U-->>D: 確定（or 修正）
    D->>IO: design_io create（*_hypothesis.yaml, status=in_review）
    IO->>H: PreToolUse 検証
    H-->>FS: 合格→書込（exit 0）

    opt 任意: レビュー
        D->>IO: design_io review-batch
        D->>U: 【KEEP】可否（revision_requested なら /analysis-revision へ）
    end

    Note over D,PM: pre-flight ゲート（高コストデータアクセス前）
    D->>IO: design_io get + catalog_io get-schema + package_allowlist.yaml
    D->>PM: source_checks_map を渡して premortem 実行
    alt HARD_BLOCK / HIGH（未登録/allowlist違反/location/高コスト）
        PM-->>D: risk
        D->>U: 【KEEP】停止しリスク提示（/catalog-register or コスト判断）
    else LOW / MEDIUM
        D->>IO: design_io transition（in_review→analyzing, AUTO）
        D->>NB: 8-cell notebook 生成（.insight/notebooks/{id}.py）
        alt 宣言 source + allowlist + ローカル計算
            D->>NB: marimo export script → python（AUTO 実行）
            NB->>FS: verdict.json / lineage/{id}.mmd
            D->>FS: verdict→journal（observe/evidence/question, AUTO 記録）
        else 非allowlist / 宣言 source 以外の外部通信 / 副作用
            D->>U: 【KEEP】実行前に承認要求
        end
        D->>U: 【KEEP】/analysis-reflection で結論（conclude/refine/branch）+ terminal 遷移
    end
    D-->>U: 実行サマリ（自動進行した所 / 停止した所 / 最終状態）
```

## Epic マッピング

| Epic | 主に触るコンポーネント |
|---|---|
| E1 | WebUI/REST（撤去）— full の縮小 |
| E2 | Validation library + pre-write hook（新設） |
| E3 | Skill layer ↔ Skill-managed YAML（設計書ライフサイクルの直接 I/O 化、design_io） |
| E3.5 | catalog / premortem / lineage の MCP→YAML 変換 + batch-analysis 撤去（E4 前提） |
| E4 | MCP server（撤去） |
| E5a | premortem（report-only 自立化） |
| E5b | catalog_io（knowledge write/upsert）+ /knowledge-extract（Claude-native 抽出） |
| E5c | models.catalog（open string taxonomy + extra=allow）+ 2 skill 汎用化 |

## 参照

- [ADR-0001](adr/0001-drop-mcp-server-embed-validation.md) — MCPサーバ廃止・検証の埋め込み化
- [ADR-0002](adr/0002-trunk-based-epic-stacking.md) — トランクベース + stacked Epic
- [ADR-0003](adr/0003-skill-yaml-io-via-design-io.md) — skill の設計書 I/O を design_io に集約
- [ADR-0004](adr/0004-open-string-catalog-taxonomy.md) — catalog の taxonomy を open string に
