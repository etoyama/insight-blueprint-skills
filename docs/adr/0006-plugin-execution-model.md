# ADR-0006: plugin execution model（bin ラッパー + env で自己完結）

## Status

Accepted

## Context

skills は分析データを `.insight/` に置き、`design_io`/`catalog_io`/`premortem.cli` を
`uv run python -m skills._shared.<mod> ... --base-dir .insight` の形で呼んでいた。これは
**この repo をカレントディレクトリにして動かす dev 前提**であり、Epic 09 の調査で
**別プロジェクトに install した plugin では core が動かない**ことが実機で判明した:

- Claude Code は skill のシェルコマンドを**利用者プロジェクトの cwd** で実行する。`skills._shared` は
  `${CLAUDE_PLUGIN_ROOT}/skills/` にしか無く、利用者 cwd からは import できない
  （`ModuleNotFoundError: No module named 'skills'` を再現）。
- `design_io`/`catalog_io` は `insight_blueprint`（PyPI `insight-blueprint-lineage`）を無条件 import するが、
  利用者 env に入っている保証がない。
- 検証 hook は `.claude/`（この repo の project 設定）にあり repo レイアウト前提で、plugin 同梱もされていない。

引き金: Epic 09 / #38。ユーザーは「別プロジェクトに install して実際に使えること」を要求。

## Decision

plugin を**自己完結**させ、パス/依存を実行時変数で解決する。

- **`bin/` ラッパー**（`bin/design_io` / `bin/catalog_io` / `bin/premortem`）を同梱する。plugin の `bin/` は
  有効時に Bash の PATH に載る。各ラッパーは:
  - `cd "${CLAUDE_PLUGIN_ROOT}"` して plugin 自身の **uv プロジェクト環境**で実行する
    （`insight_blueprint` と `skills._shared` を self-provide。利用者は core に何も install 不要）。
  - `INSIGHT_BASE_DIR="${CLAUDE_PROJECT_DIR}/.insight"` を渡し、**利用者プロジェクトの `.insight/`** に読み書きする。
  - `.insight/{designs,catalog/sources,catalog/knowledge}` を `mkdir -p` する（別 init 不要）。
  - `CLAUDE_PLUGIN_DATA` があれば `UV_PROJECT_ENVIRONMENT` をそこに向け、更新間で venv を維持する。
- **`design_io`/`catalog_io` の base-dir を env 化**: `DEFAULT_BASE_DIR = Path(os.environ.get("INSIGHT_BASE_DIR",
  ".insight"))`。`--base-dir` 引数は後方互換で維持（tests は従来どおり）。
- **SKILL のコマンドを wrapper 名**（`design_io …` / `catalog_io …` / `premortem`）に統一。素の
  `uv run python -m skills._shared…` は使わない。
- **notebook 実行**は利用者 cwd を保ったまま plugin 環境を借りる:
  `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook <marimo|python> …`（相対出力は利用者 `.insight/` に落ちる）。
- **検証 hook を plugin 同梱**: `hooks/hooks.json`（PreToolUse Write|Edit|MultiEdit）が
  `uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/hooks/validate-design.py"` を呼ぶ。
  スクリプトは `hooks/validate-design.py` に移設。この repo の `.claude/settings.json` は dev 用に同スクリプトを配線。

## Consequences

### Positive

- plugin が**別プロジェクトに install して動く**（core は利用者側 install 不要、`.insight/` へ正しく読み書き）。
- 検証 hook が利用者プロジェクトにも効く（従来は repo 内だけ）。
- SKILL のコマンドが短くなり、cwd/依存の前提が bin ラッパー1箇所に集約される。

### Negative

- 実行時に `${CLAUDE_PLUGIN_ROOT}` 等の Claude Code 変数へ依存する（`--plugin-dir`/marketplace install 前提）。
  素の `python -m skills._shared…` 直叩きは dev/test 用途に限られる。
- plugin 環境の初回 `uv run` で同期が走る（軽い初回コスト。`CLAUDE_PLUGIN_DATA` で更新間キャッシュ）。

## Alternatives considered

- **各 SKILL コマンドを inline で `cd … && uv run … --base-dir …`** — 約40箇所に冗長な定型が散る。bin ラッパーに集約する方が保守的。却下。
- **`insight-blueprint-lineage` を利用者に必須 install させる** — core すら外部 install 必須になりオンボーディングが重い。plugin 自己完結を優先。却下。
- **現状維持（dev-repo 前提と割り切る）** — 「install して使える plugin」という要求を満たさない。却下。

## Related

- Epic: #38 / `docs/design/epic-09-installable-plugin.md`
- Builds on: [ADR-0001](0001-drop-mcp-server-embed-validation.md)、Epic 07（notebook）、Epic 08 / [ADR-0005](0005-selective-autonomous-chaining.md)
- 影響: 公開済み v0.7.0 の install 経路修正 → 0.7.1 patch release
