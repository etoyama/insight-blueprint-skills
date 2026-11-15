# 開発フローの決定（repo-template のコピー）

このディレクトリには [etoyama/repo-template](https://github.com/etoyama/repo-template) の ADR の
コピーだけを置く。採用したコミットは `921b1bcdac979bd285e539a9578025a5c1a39bc0`。
[docs/WORKFLOW.md](../../WORKFLOW.md) と `.claude/rules/` のテンプレートは、ここの文書を決定の出典として参照する。

- 番号は repo-template のものを保つ。表記は `FLOW-000N` とし、`ADR-000N` とは書かない。
  `ADR-000N` は、このリポジトリの [docs/adr/](../README.md) にある決定を指す。
- このリポジトリで行った決定は、フローに関するものも含めて `docs/adr/` に置く。ここには足さない。
- 本文は repo-template のままで、変えたのは表記（`ADR-000N` → `FLOW-000N`）だけ。
  そのため、本文中の「CLAUDE.md の `## 8. Language`」のような記述は repo-template の構成を指す。
- 置き方を決めた経緯は [ADR-0009](../0009-adopt-repo-template-flow.md) にある。

| FLOW | Title | Status |
|---|---|---|
| [0001](0001-designdoc-owns-requirements.md) | 要求と背景の正本を DesignDoc に置く | Accepted |
| [0002](0002-ubiquitous-language.md) | ユビキタス言語の正本を置き、コード・テスト・図をその語で書く | Accepted |
| [0003](0003-yomiyasu-for-japanese-docs.md) | 日本語の文書を yomiyasu で推敲する | Accepted |
| [0004](0004-decision-analysis-plugin.md) | 判断の提示と ADR を Decision Analysis の形式にそろえる | Accepted |
