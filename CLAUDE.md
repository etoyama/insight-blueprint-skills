# CLAUDE.md

AI コーディングアシスタント（Claude Code 等）と人間のコントリビュータ向けガイドライン。
本ファイルは**要約とポインタのみ**を置く。実体は §2 の各正本にある。

## 1. Project Overview

**insight-blueprint-skills** は、仮説駆動 EDA を Claude Code の skill plugin として届ける。
[insight-blueprint](https://github.com/etoyama/insight-blueprint) から MCP サーバ・WebUI・SQLite を外し、
skills と YAML と埋め込みの検証ライブラリで組み直した軽量版である
（[ADR-0001](docs/adr/0001-drop-mcp-server-embed-validation.md)）。

- 守る核（marimo notebook 契約、分析設計、journal / reflection、premortem）: [docs/PRD.md](docs/PRD.md)
- 不変条件（No daemon / No MCP server / No SQLite）と、検証 hook・`.insight/` の構成:
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- skill の一覧: [README.md の Skills](README.md#skills)

## 2. Documents（正本の所在）

| 知りたいこと | 正本 |
|---|---|
| なぜ・何を（要件、ロードマップ） | [docs/PRD.md](docs/PRD.md) |
| 全体構成・不変条件・Domain Model の全体図 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 用語（ユビキタス言語） | [docs/UBIQUITOUS_LANGUAGE.md](docs/UBIQUITOUS_LANGUAGE.md) |
| 開発フローの定義 | [docs/WORKFLOW.md](docs/WORKFLOW.md) |
| Epic ごとの詳細設計 | `docs/design/epic-NN-*.md` |
| 個別の設計判断 | [docs/adr/](docs/adr/README.md) |
| skill の一覧と使い方 | [README.md](README.md) |
| 環境構築・コマンド・テスト | [CONTRIBUTING.md](CONTRIBUTING.md) |
| リリース手順 | [docs/RELEASE.md](docs/RELEASE.md) |

## 3. Tech Stack

uv（パッケージ管理）/ ruff（lint と format）/ ty（型検査）/ pytest（テスト）/ marimo（notebook）。
新しい worktree では先に `uv sync --all-extras`、確認は `uv run poe all`（lint + typecheck + test）。
詳細は [CONTRIBUTING.md](CONTRIBUTING.md)。

## 4. Development Workflow

GitHub issue 駆動の2階層。定義の正本は [docs/WORKFLOW.md](docs/WORKFLOW.md)。本書と食い違う場合は WORKFLOW を正とする。

- **Epic**（`type:epic`）: DesignDoc（`docs/design/epic-NN-<topic>.md`）を必ず伴う開発単位。
  背景・ユーザーストーリー・AC の正本は DesignDoc。issue には要約とリンクだけを書く。
- **Story**（`type:story`）: 動作確認可能な最小単位。0.5–3日、扱う Acceptance Criteria は5個以下。
- 流れ: Epic 起票 → DesignDoc 初版（Background・User Stories・構成図・**ドメインモデル図**・
  **シーケンス図**）→ Story 分割 → 実装のたびに DesignDoc を詳細化（Decisions / Story Timeline / Test Design Matrix）。
- ブランチはトランクベース + Epic stacking（[ADR-0002](docs/adr/0002-trunk-based-epic-stacking.md)）。
  Epic は `epic/<issue番号>-<slug>`、Story は既定で Epic ブランチに直接コミット。
  リリースはタグ駆動（`v*`）で、`main` へのマージはリリースではない。
- Test Design Matrix 全✓ が Epic PR のレビューゲート。✓ と「—（理由）」の読み方は [ADR-0010](docs/adr/0010-skill-tdd-structure-tests.md)。
- Epic 以外の単発の PR は、定めた振る舞いを変えない変更だけ（[ADR-0012](docs/adr/0012-single-pr-scope.md)）。
- Epic 10 までの DesignDoc と ADR-0001〜0008 は旧形式のまま凍結する
  （[ADR-0009](docs/adr/0009-adopt-repo-template-flow.md)）。閉じた Epic の DesignDoc には追記しない。
- **AI アシスタントは Epic PR を `main` にマージしない**。人間がレビューしてマージする。

## 5. ADR ハードルール

実装中に計画外の設計判断が出たら、PR マージ前に必ず次のいずれかを行う
（詳細: [docs/WORKFLOW.md §6](docs/WORKFLOW.md)）。

1. ADR を作る（既定。`docs/adr/NNNN-<slug>.md`）。
2. Epic の DesignDoc `## Decisions` に書く（効果がその Epic を超えない場合のみ）。
3. PR 説明に明記して人間に確認する（1 も 2 も過剰な小さい判断のみ）。

黙って判断して先へ進むことを禁止する。

人間に判断を仰ぐときと ADR を書くときは、`decision-analysis` スキルの形式で提示する
（[FLOW-0004](docs/adr/flow/0004-decision-analysis-plugin.md)。プラグインは `.claude/settings.json` で宣言し、
clone ごとに `scripts/install-plugins.sh` で入れる）。

## 6. Coding Principles（ハードルール）

正本: [.claude/rules/coding-principles.md](.claude/rules/coding-principles.md)

- YAGNI: 今必要でない機能・抽象を先回りで作らない。共通化は Rule of Three。
- TDD（t-wada 流）: Red → Green → Refactor を小さく回す。テストリストを作り、
  仮実装 → 三角測量 → 明白な実装の順で一般化する。テストコードが正（仕様）。
  SKILL.md と文書は構造テストを先に書いて Red にしてから本文を書く（[ADR-0010](docs/adr/0010-skill-tdd-structure-tests.md)）。
- ruff が lint と format の基準で、CI は違反を拒む。公開 API には型ヒントを付ける。
  コメントには「何を」ではなく「なぜ」を書く。

## 7. Rules and Templates

- [.claude/rules/coding-principles.md](.claude/rules/coding-principles.md)
- [.claude/rules/adr-template.md](.claude/rules/adr-template.md)
- [.claude/rules/design-doc-template.md](.claude/rules/design-doc-template.md)

## 8. Language

- ユーザーへの応答は日本語。コード（コメントと docstring を含む）・YAML のフィールド名・ツール名は英語のまま。
- 文書は日本語の単一言語で書く（上流テンプレートの日英併記は採らない）。
- 文書・コード・テスト・図は [docs/UBIQUITOUS_LANGUAGE.md](docs/UBIQUITOUS_LANGUAGE.md)
  の語だけを使う。書く前に読み、表にない概念は同じ PR で足す（[docs/WORKFLOW.md §7](docs/WORKFLOW.md)）。
- 日本語の文書は `yomiyasu:yomiyasu` スキルで推敲する。対象・タイミング・文書の種類は
  [docs/WORKFLOW.md §8](docs/WORKFLOW.md) に従う。
- 節名は英語のまま。日常的に使われる語や専門用語も英語でよく、推敲でも訳さない。

## 9. Code Review

Epic PR を開く前に、次の手順でレビューする。

1. `pstack:thermos` を回す（バグ・セキュリティとコード品質の2観点）。
   pstack が入っていない環境では、代わりに Claude Code 同梱の `/code-review` を回す。
2. テストカバレッジと AC は、Epic PR の作者が DesignDoc の User Stories と Test Design Matrix に照らして確かめ、
   結果を PR 説明に書く。
3. レビューの出力は PR のコメントに残し、ファイルとしてコミットしない。直す指摘は Story のコミットで直し、
   残す判断は ADR・DesignDoc の Decisions・issue のどれかに移す。

`.claude/docs/research/` は Epic 09 までのレビュー出力で、凍結している（追記しない）。
