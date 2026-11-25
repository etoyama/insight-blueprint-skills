# 開発フローの決定（repo-template のコピー）

このディレクトリには [etoyama/repo-template](https://github.com/etoyama/repo-template) の ADR の
コピーだけを置く。採用したコミットは `6ed7225a57aa74a02102bb5f9ac69d186a73f2b4`（FLOW-0011〜0013 を足した時点。FLOW-0001〜0010 の本文は変わっていない）。
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
| [0005](0005-designdoc-draft-checks-whole-and-mockup.md) | DesignDoc 初版では、全体の整合を確かめ、成果物の見本を見せてから承認を求める | Accepted |
| [0006](0006-pm-session-and-board.md) | Epic は PM セッションが段取りボードで統括し、作業は子セッションに渡す | Accepted |
| [0007](0007-story-done-includes-release-note-and-bug-review.md) | Story の完了の条件に、リリースノートの行と、バグ・セキュリティの観点のレビューを入れる | Accepted |
| [0008](0008-ask-before-narrowing-what-worked.md) | 今まで動いていたものを動かなくする判断は、Decisions に書くだけでなく人間に聞く | Accepted |
| [0009](0009-designdoc-decisions-scope-first.md) | DesignDoc 初版では、成果物の単位と範囲の判断を先に聞き、中身で迷ったら見本を見比べてから決める | Accepted |
| [0010](0010-retrospective-after-epic.md) | Epic のリリースの後に、軽量な定型の振り返りを回す | Accepted |
| [0011](0011-start-wave-one-before-designdoc-approval.md) | 波 1 の子は、DesignDoc 初版の子を立てるターンで、待機の指示で立てておく | Accepted |
| [0012](0012-shared-notes-in-app-folder-checked-by-path.md) | 共有ノートはアプリの置き場に置き、子が報告した絶対パスを PM が確かめてボードに残す | Accepted |
| [0013](0013-write-rules-reasons-and-helpers-into-designdoc-and-brief.md) | DesignDoc とブリーフには、守りたい規則、触らない理由、使う既存の道具を書く | Accepted |
| [0014](0014-start-all-waves-in-first-human-turn.md) | 後に続く波の子は、最初に子を立てる人間のターンで、全部待機の指示で立てておく | Accepted |
| [0015](0015-copy-pm-address-from-listagents.md) | ブリーフに書く PM の宛先は ListAgents から写し、PM のシステムプロンプトの宛先と置き場は写さない | Accepted |
| [0016](0016-try-with-real-data-before-epic-pr.md) | 利用者が触る Epic では、ゲートの後、Epic PR の前に、実データで使ってみる | Accepted |
