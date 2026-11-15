# PRD: insight-blueprint-skills

仮説駆動 EDA プラットフォームを **Claude Code skill plugin** として提供するプロダクトの
要件定義。詳細なアーキテクチャは [ARCHITECTURE.md](ARCHITECTURE.md)、個別の設計判断は
[docs/adr/](adr/) を正とする。本書は「なぜ・何を」を簡潔に示す上位ドキュメント。

## ビジョン / 解く課題

分析者が「仮説 → 設計 → 検証 → 結論」のサイクルを、加工の透明性とリネージを保ったまま
回せるようにする。本家 insight-blueprint は MCP 常駐サーバ + WebUI + SQLite で同じ価値を
提供してきたが、運用の実態は Claude Code との対話に寄り、サーバ/WebUI のメンテ・オンボーディング
コストが正味の負債になっていた（[ADR-0001](adr/0001-drop-mcp-server-embed-validation.md)）。

本プロダクトはその核を **skills + YAML + 埋め込み検証ライブラリ**で再構成し、常駐プロセスを
持たない軽量な plugin として同じ価値を届ける。

## コアバリュー（温存すべき核）

- marimo notebook 契約 & lineage — データ加工の透明性・追跡可能性
- 分析設計（`*_hypothesis.yaml`）と、それを生成する skills
- journal / reflection — 結果の解釈と結論づけ
- premortem — 高コストなデータアクセス前の費用・リスク評価

## 主要要件

### 機能要件

- 分析設計の整合性を**サーバを常駐させずに**強制する（スキーマ + 状態遷移）
- 分析設計・journal・reflection・revision を skill 経由の対話で作成・更新できる
- データ加工をリネージとして記録し Mermaid 図で出力できる
- データソースを catalog として登録・検索できる

### 非機能要件

- 常駐プロセスを持たない（No daemon / No MCP server / No SQLite）
- 検証ロジックは I/O を持たない純関数ライブラリに集約し、単一正本とする
- Claude Code plugin として配布・利用できる
- リリースは tag 駆動（`v*`）。トランク（main）へのマージは publish を起こさない

## スコープ外

- 分析設計の全文検索（旧 FTS5 機能の再構築。現状コアは非対象）
- WebUI / REST API
- MCP 常駐サーバ

## ロードマップ

E1〜E5 は [ADR-0001 §Related](adr/0001-drop-mcp-server-embed-validation.md) の解体計画に対応する。
Epic 06 からは軽量版の上に分析の能力を足していく。

| Epic | DesignDoc | 内容 | 状態 |
|---|---|---|---|
| E1 | [epic-01](design/epic-01-remove-webui.md) | WebUI / REST 削除 | 完了 |
| E2 | [epic-02](design/epic-02-validate-lib.md) | `validate.py` 抽出 + pre-write hook 新設 | 完了 |
| E3 | [epic-03](design/epic-03-skills-yaml-io.md) | skill を YAML 直接 I/O（分析設計のライフサイクル） | 完了 |
| E3.5 | [epic-3.5](design/epic-3.5-remaining-yaml-io.md) | catalog / premortem / lineage の MCP→YAML 変換 + batch-analysis 撤去 | 完了 |
| E4 | [epic-04](design/epic-04-remove-mcp-server.md) | MCPサーバ層削除 | 完了 |
| E5a | [epic-05a](design/epic-05a-premortem-standalone.md) | premortem 自立化（report-only 化） | 完了 |
| E5b | [epic-05b](design/epic-05b-knowledge-extraction.md) | knowledge 抽出強化（Claude-native + source-scoped） | 完了 |
| E5c | [epic-05c](design/epic-05c-catalog-flexibility.md) | catalog 柔軟化（open string taxonomy） | 完了 |
| Epic 06 | [epic-06](design/epic-06-analysis-review.md) | `/analysis-review`（レビューの生産者） | 完了 |
| Epic 07 | [epic-07](design/epic-07-analysis-notebook.md) | `/analysis-notebook`（methodology から marimo notebook を生成・実行） | 完了 |
| Epic 08 | [epic-08](design/epic-08-analysis-auto.md) | `/analysis-auto`（guided autopilot） | 完了 |
| Epic 09 | [epic-09](design/epic-09-installable-plugin.md) | plugin をインストール先で動かす（execution model） | 完了 |
| Epic 10 | [epic-10](design/epic-10-analysis-report.md) | `/analysis-report`（APA 風レポート） | 完了 |
| Epic 11 | [epic-11](design/epic-11-repo-template-compliance.md) | repo-template の開発フローへの準拠 | 進行中 |

各 Epic の DesignDoc は `## Scope` 節で、本書のどの要件と
ARCHITECTURE のどのコンポーネントを前進させるかを示す。

## 成功基準

- 検証の正本が `validate.py` 1 箇所に集約され、hook と skill の双方から再利用される
- 移行の各段階で `pytest` が全緑を保つ（挙動の非回帰）
- 常駐プロセス・WebUI・SQLite 依存が消え、plugin として動作する
- コアバリュー（marimo 契約 / 分析設計 / journal・reflection / premortem）が維持される
