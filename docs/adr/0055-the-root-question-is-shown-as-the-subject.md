# ADR-0055: 分析者に見せる言葉を内側の用語と分け、「根の問い」を「主題」と呼ぶ

## Status

Accepted

## Context

Epic 34（[#249](https://github.com/etoyama/insight-blueprint-skills/issues/249)、[DesignDoc](../design/epic-34-what-moved-the-answer.md)）の初版で決めた。
利用者は、#249〜#251 の見本を読んで「根の問い」が伝わらないと言い、「主題」への言い換えを求めた（[#262](https://github.com/etoyama/insight-blueprint-skills/issues/262)、2026-11-26）。
Epic 34 は主題のカードとページの冒頭に、新しい見出しと文を足す。言い換えの時期を先に決める必要があった。

比較の土台にした事実（epic ブランチ dc785c4、`grep` で確かめた）。

- 「根の」が出るのは次の所である。`skills/_shared/tree_render.py`、`skills/_shared/theme_report.py`（読み手向けの言い換えの表）、skill 4本（`analysis-framing`・`analysis-reflection`・`report-export`・`tree-upload`）、`tests/fixtures/handoff/prompt.md`、テスト 8 ファイル、`docs/UBIQUITOUS_LANGUAGE.md`、PRD、ARCHITECTURE、HANDOFF_TRIAL。
- レポートは読み手向けにすでに「根の問い」を「主題」と出している（`theme_report.py`）。
- 閉じた Epic の DesignDoc と ADR にも「根の問い」がある。閉じた Epic の DesignDoc には追記しない（[ADR-0009](0009-adopt-repo-template-flow.md)）。
- 用語の改名は ADR を伴う（[docs/WORKFLOW.md](../WORKFLOW.md) §7）。Epic 以外の単発の PR は定めた振る舞いを変えない変更だけである（[ADR-0012](0012-single-pr-scope.md)）。表示の言葉を変えるのは振る舞いの変更に当たる。
- コード上の名前（`RootRevision`、`root_revisions`、`tree_io revise-root`）と YAML の項目名を変えると、保存済みの論点ツリーの移行が要る。
- 初版の見本を人間が読んでコメントを付けた（2026-11-26）。「言えること」は主題を支持する結果と読まれた。「引用する」「出来事」「下の論点」は意味が取れなかった。7件のコメントのうち6件が言葉でつまずいた所だった。
- 答えの文の種類の言葉（言えること、弱める証拠と留保、未判別）は、論点ツリーの HTML、`/analysis-reflection`、レポート（`theme_report.py`）、問いの紙、図書館の鍵に出る（`grep` で確かめた）。

## Problem

- 課題1: 分析者に見せる「根の問い」「根の版」「根の変更前の答え」が伝わらない。分析者は、論点ツリーのいちばん上で読む手が止まる。
- 課題2: Epic 34 が足す見出しと文を「根」のまま書くと、後で全部書き直す。引き継ぎの試行の読み手にも「根」の言葉で読ませることになり、表示の効果と言葉のつまずきが混ざる。
- 課題3: 表示が記録の作りの言葉（引用する、出来事、下の論点）と、向きを感じさせる言葉（言えること）で書かれている。分析者は分析結果を答えの中でどう位置づけたかを読み取れない。

扱わない範囲: コード上の名前と YAML の項目名と値。Decision の表に無い言葉（検証中、寄与、発見元、`type`、`direction`）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの論点ツリーの YAML がそのまま読める | Must | - | - | 不変条件（正本は YAML） |
| W1 | Epic 34 の新しい表示が、最初から伝わる言葉で出る | Want | 解決 | 高（人間） | 課題1、課題2 |
| W2 | 同じ文言を2度書き直さない | Want | 費用 | 中（Claude の推測） | 課題2 |
| W3 | Epic 34 の範囲が膨らまない | Want | 費用 | 中（Claude の推測） | #262 の「#249 とは分ける」 |

- 案A: Epic 34 の最初の Story で、表示の言葉と用語集だけを言い換える。
- 案B: #262 を独立の Epic にして、終わってから Epic 34 を始める。
- 案C: Epic 34 の後に言い換える。
- 何もしない。

| Must | 案A | 案B | 案C | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |

| Want | 案A | 案B | 案C |
|---|---|---|---|
| W1 | 出る | 出る | 出ない。新しい見出しも試行も「根」で出る |
| W2 | 1度で済む | 1度で済む | 2度書く |
| W3 | Story が1つ増える。レポートは済んでいるので小さい | 膨らまないが、Epic の段取りがもう1周要る | 膨らまない |

- 差がつく基準: W1（案C が落ちる）と W3（案A と案B の差）。
- 感度: W3 の重みを高にすると案B になる。言い換えそのものは小さく、Epic 1周の段取りのほうが重い。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | ほかの伝わらない言葉まで直し始めて膨らむ | AC を「根」の付く3語に限る。ほかは issue に書く |
| 案A | 問いの紙の言葉が変わり、過去の試行の記録と条件がずれる | 言い換えの後に基準を取り直す。過去の記録は書き換えない（[ADR-0035](0035-handoff-trial-records-keep-their-score.md)） |
| 案B | Epic 34 の着手が遅れる | 無い |
| 案C | 試行の読み手が「根」でつまずき、表示の効果と混ざる | 無い |
| 何もしない | 課題1 が残る | 無い |

## Decision

案A を採る（人間の判断、2026-11-26）。決め手は W1 と W2 である。

1. 分析者に見せる言葉を次のように変える。3語とも人間が承認した。

   | 今 | これから |
   |---|---|
   | 根の問い | 主題 |
   | 根の版 | 主題の版 |
   | 根の変更前の答え | 見直す前の主題への答え |

2. 変えるのは、論点ツリーの HTML、skill が分析者に出す文、問いの紙、生きている文書（用語集、PRD、ARCHITECTURE、HANDOFF_TRIAL）である。
3. 用語集は「主題」「主題の版」を用語にし、「根の問い」「根の版」を使わない言い換えに置く。
4. コード上の名前（`RootRevision`、`root_revisions`、`tree_io revise-root`、`root_revision`）と YAML の項目名は変えない。
5. 閉じた Epic の DesignDoc と、この ADR より前の ADR の本文は変えない。旧い語は用語集の「使わない言い換え」で読み替える。
6. 引き継ぎの試行の基準は言い換えの後に取る。
7. 答えの文の種類は次の言葉で分析者に見せる（人間が選んだ、2026-11-26）。YAML の値（`claim`・`weakening`・`undetermined`）は変えない。レポートも同じ言葉で出す。

   | 今 | これから |
   |---|---|
   | 言えること | これまでわかっていること |
   | 弱める証拠と留保 | 注意すべきこと |
   | 未判別 | まだ決められないこと |

8. 分析者に見せる文では「引用する」を「根拠にする」、答えが引用した journal の出来事を「分析結果」と呼ぶ。人に聞いた答え（`hearing`）は「分析結果」と呼ばず、「人に聞いた答え」と出す。「下の論点」は使わず、分析結果を主語にして言う。
9. 文書・コード・テストは今までどおり内側の用語（引用、journal の出来事）を使う。対応は Epic 34 の DesignDoc の US-5 の表に置き、用語集に写す。

## Consequences

### Positive

- 論点ツリーとレポートが、同じものを同じ言葉で呼ぶ。
- Epic 34 が足す見出しを、1度で書ける。

### Negative

- コードと YAML には `root` が残る。開発者は表示の「主題」とコードの `root` の対応を用語集で読む。
- 過去の ADR と DesignDoc には「根の問い」が残る。
- 過去の試行の記録は「根の問い」の問いの紙で取ったもので、これからの記録と条件が1語ぶんずれる。
- 「検証中」（探索の分析でも出る）、「寄与」、「発見元」が伝わるかは確かめていない。この決定では直さない。Epic 34 が触らない欄には、内側の言葉が残る。
- 内側の用語と分析者に見せる言葉が2組になる。開発者は対応の表を引く。
- 「注意すべきこと」は何に注意するのかを言葉だけでは言わない。直前の「これまでわかっていること」への注意だと読めるのは、並び順による。
- 言葉は初版の見本を読んだ1人の指摘で選んだ。ほかの読み手で通じるかは確かめていない。

## Alternatives considered

- **コード上の名前と YAML の項目名も変える** — 保存済みの論点ツリーの移行が要り、M1 を満たさない。

## Related

- Epic: [#249](https://github.com/etoyama/insight-blueprint-skills/issues/249)、[docs/design/epic-34-what-moved-the-answer.md](../design/epic-34-what-moved-the-answer.md)
- Issues: [#262](https://github.com/etoyama/insight-blueprint-skills/issues/262)
- [ADR-0009](0009-adopt-repo-template-flow.md)、[ADR-0012](0012-single-pr-scope.md)、[ADR-0024](0024-question-tree-yaml-and-generated-html.md)、[ADR-0035](0035-handoff-trial-records-keep-their-score.md)
- Supersedes: なし
