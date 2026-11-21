# ADR-0028: 人に聞いた答えは、journal の出来事 `hearing` として残す

## Status

Accepted

## Context

論点ツリーの次の候補には、分析者が人に聞いてきた答えを残せる（[epic-18](../design/epic-18-question-tree.md) の Decision `inquiry-answer-copied-to-journal`）。
その論点に分析設計を起こすとき、答えを journal に写す。現時点の答えの根拠に使えるのは、journal の出来事だけだからである（[ADR-0025](0025-cited-answers-checked-after-writing.md)）。
どの種類の出来事として写すかは、epic-18 の未決事項として Story 18.5（[#126](https://github.com/etoyama/insight-blueprint-skills/issues/126)）に残っていた。

比較の前提にした事実と、確かめた方法は次のとおり。

- journal の出来事の種類は8つある（`observe`・`hypothesize`・`evidence`・`question`・`decide`・`reflect`・`conclude`・`branch`）。`observe` の定義は「データの観察」である（`skills/analysis-journal/SKILL.md` の InsightType Convention を読んだ）。
- `/analysis-report` は、journal の `observe` を Results の叙述として書き、`evidence` を向きで分けて書く（`skills/analysis-report/references/apa-template.md` を読んだ）。ほかの種類は Results に使わない。
- 出来事の種類を検証する Python のコードは無い（`src`・`skills`・`hooks` を grep した）。種類を列挙しているのは、journal の SKILL.md、用語表、[docs/ARCHITECTURE.md](../ARCHITECTURE.md) である。
- ツリーの検査は出来事の種類を見ない。論点ツリーの HTML は、引用した出来事の種類をそのまま出す（epic-18 の Decision `tree-check-reads-the-last-answer-and-compares-values`・`tree-html-is-static-and-marks-are-derived`）。

## Problem

- 課題1: 聞いてきた答えを現時点の答えの根拠に使うには、引用できる journal の出来事になっている必要がある。種類が決まっていない。
- 課題2: 人が言ったことと、データが示したことが同じ種類だと、答えを読む人とレポートを読む人が根拠の質を取り違える。人の答えは、分析で確かめた事実ではない。

扱わない範囲: ヒアリングそのもの（[docs/PRD.md](../PRD.md) のスコープ外）。レポートに人の答えを載せるかどうか。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 答えが引用できる出来事になる | Must | - | - | 課題1、ADR-0025 |
| W1 | 人の答えがデータの観察や証拠として読まれない | Want | 解決 | 高（Claude の推測、人間が推奨を採った） | 課題2 |
| W2 | 直す文書とテストの量 | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | 新しい種類 `hearing` | `observe` と `metadata.source` | `evidence` | 何もしない（写さない） |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たさない |

| Want | 新しい種類 `hearing` | `observe` と `metadata.source` | `evidence` |
|---|---|---|---|
| W1 | HTML に `type: hearing` と出る。レポートは `observe` と `evidence` しか読まないので、Results に混ざらない | HTML には `observe` と出る。レポートは Results に観察として書く | 証拠として数えられ、`direction` を付けることになる。分析の結果と区別がつかない |
| W2 | journal の SKILL.md、用語表、ARCHITECTURE を直す。種類が9つになる | journal の SKILL.md に metadata の行を1つ足すだけ | `observe` の案と同じくらい |

- 差がつく基準: W1 と W2。
- 感度: W1 を中に下げ、W2 を高にすると `observe` の案になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 新しい種類 `hearing` | 種類を数える既存の手順が `hearing` を知らない | 同じ Story で journal の SKILL.md の表と要約を直す |
| `observe` と `metadata.source` | 人の発言がレポートの Results に観察として載る | レポートの側で metadata を見る決まりを足すことになり、別 Epic の文書に手が入る |
| `evidence` | 人の発言が、支持する証拠として結論に効く | 抑えられない |

## Decision

journal の出来事の種類に `hearing` を足す（人間の判断、2026-11-21、Story 18.5 のセッション）。決め手は W1 で、`observe` にするとレポートの Results に混ざる経路が実際にある。

- `hearing` は、人に聞いて得た答えを残す出来事である。本文は答えで、`metadata` に誰に聞いたか（`answered_by`）と日付（`answered_at`）を持つ。次の候補から写したものは、聞いた問い（`ask`）と元の論点の id（`node_id`）も持つ。
- 次の候補の答えを journal に写すのは `tree_io copy-hearing` である。答えの文をコードが写し、モデルは打ち直さない。同じ答えを2度写さない。
- `/analysis-journal` で分析者が直接 `hearing` を残すこともできる。
- 名前に `inquiry` は使わない。journal の SKILL.md の「Inquiry Board」（未解決の `question` の一覧）と衝突する。

## Consequences

### Positive

- 現時点の答えが人の答えを引用すると、図に `type: hearing` と出る。読む人は、データで確かめた文と人から聞いた文を見分けられる。
- レポートの Results に人の発言が観察として混ざらない。

### Negative

- ツリーの検査は種類を見ないので、`hearing` の本文にある数は「記録にある数」として通る。人が口にした数が、検査を通って答えに入りうる。
- 答えを本当に人から聞いたかは、コードでは確かめない。モデルが `tree_io hear` で答えを書き、`tree_io copy-hearing` で写して引用すれば、その数は検査を通る。止めているのは、`/analysis-reflection` が KEEP ゲートで分析者に聞き、誰に聞いたかと日付を自分で埋めないという手順の文だけである。journal はもともと skill が書くファイルなので、これは journal に数を書き足せば検査を通せるという既にある穴と同じ種類である（push の自動セキュリティレビューの指摘、2026-11-21）。
- 見分ける手段は図である。引用した出来事がすべて `hearing` の文には、要約の行に「人に聞いた答えによる」と添える（人間の判断、2026-11-21、Story 18.5 のセッション）。データの出来事と一緒に引用した文には付かない。論点を開けば、出来事ごとに `type: hearing` が出る。`hearing` の数を検査で認めない案は採らなかった。人から正しく聞いた数まで答えに書けなくなるわりに、journal に直接書く道が残るためである。
- `/analysis-report` は `hearing` を読まない。人の答えが結論に効いた分析でも、レポートには載らない。載せるかどうかはこの ADR では決めない。
- journal から段階を推定する決まり（Phase Inference）に1行増える。

## Alternatives considered

- **論点ツリーに自分の出来事を持たせる** — 引用できる記録が journal と論点ツリーの2種類になり、ADR-0025 の検査の対象が増える。epic-18 の Decision `inquiry-answer-copied-to-journal` で落としてある。

## Related

- Epic: [#116](https://github.com/etoyama/insight-blueprint-skills/issues/116)、[epic-18](../design/epic-18-question-tree.md)
- Stories: [#126](https://github.com/etoyama/insight-blueprint-skills/issues/126)
- 関係する ADR: [ADR-0025](0025-cited-answers-checked-after-writing.md)
