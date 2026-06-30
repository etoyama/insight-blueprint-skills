# ADR-0001: MCPサーバを廃止し、設計書検証を埋め込みライブラリ＋pre-write hook に移す

## Status

Accepted

## Context

insight-blueprint は hypothesis-driven EDA プラットフォームとして、
MCPサーバ（FastMCP）+ WebUI（FastAPI / React, 約232MB）+ SQLite(FTS5) + skill 群で
構成されてきた。

運用の実態として、分析設計は WebUI で確認するより Claude Code との対話で決めることが
主になり、WebUI のメンテナンス・オンボーディングコストが正味の負債になっていた。
軽量化にあたり、フォーク（insight-blueprint-skills）で結合度を調査し、以下を確定した。

- **WebUI**: レビュー承認を含む全操作に MCP tool 代替があり、機能ロスなく削除可能。
  WebUI 専用操作はゼロ。
- **設計書 CRUD**: `DesignService` は YAML 直接 I/O で動作し、SQLite を使っていない
  （`core/designs.py`, `storage/yaml_store.py`）。
- **FTS5 検索**: 設計書本体はインデックス対象外。検索対象は catalog / knowledge のみ
  （`storage/sqlite_store.py`）。
- **手放せない機能は2点のみ**:
  1. 状態遷移ガード（`core/reviews.py` の `VALID_TRANSITIONS` + `_validate_transition`）
  2. Pydantic スキーマ検証（`models/design.py` の `AnalysisDesign`、特に `DesignStatus`
     enum と `Methodology.method` 非空制約）

つまり MCPサーバという常駐プロセスの存在理由（REST API 供給・CRUD・検索）はほぼ消失し、
残る価値は「設計書 YAML の検証」だけだった。

## Decision

MCPサーバ（FastMCP / FastAPI / uvicorn / SQLite）と WebUI を廃止する。
設計書 CRUD は skill が YAML を直接読み書きする（journal / reflection と同じ作法に統一）。

検証ロジックだけを `src/insight_blueprint/validate.py` に純関数として残し、
`models/design.py` の Pydantic 検証と `core/reviews.py` の `VALID_TRANSITIONS` を
そこに集約する。

設計書 YAML（`.insight/designs/*_hypothesis.yaml`）への書き込みは pre-write hook
（`.claude/hooks/validate-design.py`）が `validate.py` を呼び、スキーマ検証＋状態遷移
検証を強制する。違反は `exit 2` で書き込みをブロックする。検証の正本は `validate.py`
の1箇所とする。

これは SQLite の設計思想（サーバを持たず、ライブラリとしてアプリに埋め込む）と同じ転換で
ある。常駐プロセスの起動・設定・運用コストを捨て、必要な保証（検証）だけをライブラリ関数
として持つ。

## Consequences

### Positive

- MCPサーバ・WebUI・SQLite・FastAPI / uvicorn 依存が消え、メンテ／オンボーディング
  コストが大幅に減る。
- 配布形態が「skill plugin + 軽量検証ライブラリ」になり、plugin として扱いやすい。
- 検証の正本が1ファイルに集約され、hook と skill の双方から再利用できる。
- marimo notebook 契約・リネージ・分析設計書・journal / reflection・premortem の
  コアは温存される。

### Negative

- 検証の強制力がサーバ側の堅牢さから hook 依存に移る。hook を迂回する経路
  （直接ファイル編集等）では保証が効かない。
- 設計書の全文検索を将来必要とする場合、FTS5 を別の形で再構築する必要がある
  （現状は設計書が非対象なので影響なし）。
- 移行は5 Epic に渡る段階的作業を要する（下記 Related 参照）。

## Alternatives considered

- **案A（MCPサーバ温存・WebUI のみ削除）** — 検証の堅牢性は最大だが、サーバ常駐の
  メンテ／オンボーディングコストが残り、軽量化の主目的を達成できない。
- **案B（新リポジトリにゼロから再構築）** — 案Cと出来上がりはほぼ同じだが、git 履歴の
  断絶・データ移植・CI 再構築という移行コストを追加で払う。コアが既存リポジトリから
  きれいに剥がせる以上その必然性がなく、フォーク（履歴連続）で同じ軽さを得る案Cを採った。

## Related

- Epic 計画:
  - E1: WebUI / REST 削除
  - E2: `validate.py` 抽出 + pre-write hook 新設
  - E3: skill を YAML 直接 I/O へ改修（設計書ライフサイクル: design/journal/reflection/revision）
  - E3.5: catalog / premortem / data-lineage の MCP→YAML I/O 変換（E4 の前提。[ADR-0003](0003-skill-yaml-io-via-design-io.md) で挿入）
  - E4: MCPサーバ層削除
  - E5: catalog 柔軟化 + premortem 自立化
- 派生リポジトリ: `etoyama/insight-blueprint-skills`（`etoyama/insight-blueprint` からのフォーク）
- Supersedes: なし
