# ADR-0005: selective autonomous chaining（`/analysis-auto` driver）

## Status

Accepted

## Context

軽量版の skill 群は意図的に **`disable-model-invocation: true`（明示 `/command`・human-in-the-loop）** で
設計されており、これは全体フロー点検（Epic の #31）で `docs/ARCHITECTURE.md` の «Skill invocation model»
節にも明文化された（「auto mode ≠ 無人自動連鎖」）。一方でユーザーは「分析設計が固まった後、本当に
ユーザー判断が要る所まで手動 `/command` 無しで進めたい」という要求を持つ（Epic 08 = b）。

素朴に各 skill の `disable-model-invocation` を `false` に倒すと、Claude が文脈で skill を自動起動できる
反面、**`/analysis-notebook` が生成した Python を無レビューで実行**しかねない（Epic 07 の security 緩和は
「自動起動しない + human-in-the-loop」に依存していた）。catalog へのソース登録（外部データの副作用）や
仮説の結論づけも本来ユーザー判断であり、大域的な invocation 解放はこれらの安全境界を崩す。

引き金: Epic 08 / AskUserQuestion（実現手段 = driver スキル、notebook 実行 = premortem 事前ゲート +
source/allowlist 限定なら auto、宣言 source 以外の外部通信は判断ゲート）。

## Decision

自律チェーンを **driver スキル `/analysis-auto` による guided autopilot** として実装する。

- **既定は変えない**: 個々の skill は `disable-model-invocation: true`（明示・対話型）のまま。invocation
  フラグを大域変更しない。自律性は `/analysis-auto` を起動したセッションに限定（selective autonomy）。
- **driver が pipeline を駆動**し、**KEEP ゲートでのみ停止**、AUTO（摩擦）は自動進行する:
  - **KEEP（停止）**: 仮説の確定（`/analysis-design`）、データソース登録（`/catalog-register`）、
    premortem が `HARD_BLOCK`/`HIGH`、notebook が非 allowlist パッケージ・宣言 source 以外の外部通信・
    その他副作用を要する場合、review の可否判定、reflection の結論（Q3）+ terminal 遷移。
  - **AUTO（進行）**: Step0 の続行確認、design のフィールド逐次インタビュー（framing brief から自動ドラフト）、
    premortem の実行、`in_review→analyzing` 等の遷移、notebook verdict の journal 記録。
- **notebook 実行ポリシー**: `/premortem`（source_registered / location_ok / **allowlist_ok** /
  estimated_rows）が事前レビューとして通過し、かつ notebook が **宣言済み source の読取 + allowlist 内
  パッケージ + ローカル計算**に収まるなら driver は auto 実行してよい。**宣言 source 以外の外部通信・
  非 allowlist 依存・その他副作用**を検知したら停止する。`.insight/rules/package_allowlist.yaml` が
  その依存・外部通信の境界を成す。

これにより #31 の «Skill invocation model» を「明示が既定、`/analysis-auto` 起動時のみ selective autonomy」に
精緻化する。

## Consequences

### Positive

- Epic 07 の code-exec 安全（無レビュー実行の防止）を維持したまま摩擦を減らせる。安全境界が driver に集約され contained。
- 個々の skill の挙動・テストが不変（大域的リグレッションが無い）。自律性は明示的にオプトイン。
- 孤立していた `/premortem` が driver の pre-flight ゲートとして機能上の役割を得る。

### Negative

- driver は prose オーケストレーションであり、ゲート遵守は Claude の SKILL 追従に依存（機械的強制ではない）。
- 「摩擦」と「本物の判断」の線引きはヒューリスティックで、境界事例は driver 側の判断に委ねられる。

## Alternatives considered

- **各 skill の `disable-model-invocation` を false に大域変更** — Claude が通常会話で自動連鎖できる反面、
  notebook の無レビュー実行・副作用の暴発リスクがあり Epic 07 の緩和を退行させる。境界も緩い。却下。
- **設計ドキュメントのみ（実装しない）** — 要求（手動 command 削減）を満たさない。却下。

## Related

- Epic: #34 / `docs/design/epic-08-analysis-auto.md`
- Builds on: [ADR-0001](0001-drop-mcp-server-embed-validation.md)（skills + YAML の軽量アーキテクチャ）、
  Epic 07（`/analysis-notebook` と security 緩和）、#31（«Skill invocation model» の明文化）
- Skills: `/analysis-auto`（新）が `/analysis-framing`・`/analysis-design`・`/analysis-review`・`/premortem`・
  `/analysis-notebook`・`/analysis-journal`・`/analysis-reflection` を駆動
