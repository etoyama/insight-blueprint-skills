# ADR-0002: `dev` を廃止しトランクベース（main）+ stacked Epic に移行する

## Status

Accepted

## Context

軽量版フォークは当初 Story→Epic→`dev`→`main` の GitFlow 風フローを CLAUDE.md §4 に
文書化していた。しかし運用開始直後の調査で、この `dev` 層が「形だけ GitFlow・実体が無い」
ことが判明した。

- **リリースは tag 駆動**。`.github/workflows/publish.yml` は `on: push: tags: ["v*"]` で
  発火する。`main` へのマージ自体は publish を起こさない。したがって `main` の手前に
  「リリース前 soak 用の統合ブランチ」を置く意味がない。
- **CI が `main` しかゲートしていない**。`.github/workflows/ci.yml` は
  `pull_request: branches: [main]` のみ。base=`dev` の Epic PR（実際に Epic 2 PR #13 で発生）
  には CI が一切走らなかった。ツールは既に main 中心フローを前提に組まれていた。
- **`dev` は `main` + 1 コミットに過ぎなかった**。`merge-base(main, dev) = main`、
  `main...dev = 0 1`。その 1 コミットは軽量版 init（ADR-0001 + CLAUDE.md + テンプレ）。
  `dev` は統合ブランチではなく「`main` 未マージの init を 1 個抱えただけのブランチ」だった。

`dev` は Epic ごとに「Epic→`dev`→`main`」の二重マージと、`dev`/`main` の恒常的な乖離を
強いるだけで、固有の成果物（デプロイ・soak 環境・リリースゲート）を一切持たなかった。

## Decision

`dev` ブランチを廃止し、**`main` をトランク**とするトランクベース開発に移行する。

- Epic ブランチ `epic/<num>-<slug>` は `main` から切り、Epic PR は `main` を base とする。
- Story は原則 Epic ブランチへ直コミットする。独立レビューが要る Story のみ、Epic から
  Story ブランチを切り Epic ブランチへ PR する（stacked PR）。
- リリースは従来どおり `v*` タグ駆動。Epic の `main` マージは publish を起こさない。
- AI は Epic PR を `main` にマージしない（人間が手動マージ）。

移行の一回限りの作業として、`dev` の init コミットを `main` に fast-forward 取り込みし、
open だった Epic PR の base を `main` に付け替え、`dev` ブランチを削除した。

## Consequences

### Positive

- Epic ごとの二重マージが消え、`dev`/`main` 乖離が無くなる。
- すべての PR が `main`（または Epic）を base とし、CI ゲート（`pull_request` 拡張後）と
  整合する。base=`dev` で CI 素通りという穴が塞がる。
- フローが GitHub Flow + stacked PR の定番形になり、説明・オンボーディングが容易。

### Negative

- `main` が Epic 単位の比較的大きなマージを受ける（ただし Epic は一貫した単位であり、
  Epic PR でレビューされる）。
- stacked PR は GitHub ネイティブ非対応のため、Story PR を使う場合は Story マージ後に
  後続 Story PR の rebase が要る。これを避けるため Story は原則直コミットとする。
- 旧フルアプリが `main` の tip に残るが、E1–E4 の Epic→`main` PR が段階的に除去する
  （init コミットはフルアプリを削除しないため、取り込み時点での機能損失は無い）。

## Alternatives considered

- **`dev` を統合ブランチとして維持** — soak/リリースゲートとしての実体が無く、CI も
  `dev` を見ていない以上、二重マージのコストに見合う便益が無いため却下。
- **別リポジトリで軽量版を再構築** — ADR-0001 案B として既に却下済み（履歴断絶コスト）。
  本 ADR の論点（trunk か dev か）とは別レイヤ。

## Related

- ADR: [ADR-0001](0001-drop-mcp-server-embed-validation.md) — MCPサーバ廃止・検証埋め込み化
  （その §Related の Epic ロードマップ E1–E5 は本トランクモデル上で進める）
- PRs: #13（Epic 2。base を `dev`→`main` に付け替え）
- Supersedes: CLAUDE.md §4 の旧ブランチ規則（Story→Epic→`dev`→`main`）
