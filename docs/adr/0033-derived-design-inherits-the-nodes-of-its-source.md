# ADR-0033: 派生の分析設計は、派生元が結ばれている論点に聞かずに結ぶ

## Status

Accepted

## Context

`/analysis-reflection` の分析設計の振り返りで branch を選ぶと、`/analysis-journal` の Branch Workflow が派生の分析設計を作る。
この分析設計は論点ツリーのどの論点にも結ばれなかった（[#134](https://github.com/etoyama/insight-blueprint-skills/issues/134)）。
Epic 18 の Story 18.9 のレビューで見つかり、DesignDoc の Decision `position-is-derived-by-tree-io` に「残した穴」として書いてあった。
Epic 18 は閉じているので、DesignDoc には追記せず、この ADR に決定を残す（[ADR-0009](0009-adopt-repo-template-flow.md)）。

比較の前提にした事実と、確かめた方法は次のとおり。

- 派生の分析設計を作るのは `/analysis-journal` の Branch Workflow だけである。`design_io create` に `parent_id` を付けて呼び、`tree_io link` は呼ばない（`skills/analysis-journal/SKILL.md` を読んだ）。
- `/analysis-design` が分析設計を論点に結ぶのは、Framing Brief に `node_id` があるときだけである（`skills/analysis-design/SKILL.md` を読んだ）。
- 合成のプロジェクトで再現した。論点 LIB-Q02 に LIB-H01 を結んで `rejected` にし、`parent_id: LIB-H01` の LIB-H02 を作った。LIB-H02 は終わっていないのに、`tree_io progress` は LIB-Q02 を `analyzed` と返し、論点の `design_ids` は LIB-H01 だけだった（`bin/tree_io` を実行した）。
- 1つの分析設計は複数の論点に結べる（[Epic 18 の DesignDoc](../design/epic-18-question-tree.md) の US-2 AC 3）。
- `/analysis-auto` が分析者に聞くのは、列挙した KEEP ゲートだけである（同 US-8 AC 3）。
- `tree_io` に、結んだ分析設計を論点から外すコマンドは無い（`skills/_shared/tree_io.py` のコマンドの一覧を読んだ）。
- 複数の論点に結んだ分析設計が実際にどれだけあるかは未確認である。

## Problem

- 課題1: 分析者は派生の分析設計を論点ツリーの上で追えない。進捗は終わっていない分析設計を数えず、巡回の現在地は派生を進める対象に出さない。テーマを横断した振り返りは、派生の journal の出来事を引用できない（ツリーの検査が `unlinked-design` の違反にする）。
- 課題2: 派生の分析設計を結ぶ先の決め方が定まっていない。派生元が複数の論点に結ばれているときと、どこにも結ばれていないときがある。

扱わない範囲: Framing Brief を持たずに `/analysis-design` を単独で起動して作った分析設計。「結ばずに作る」と定めてあり、変えない。結んだ分析設計を論点から外す手段。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析者が選んでいない論点を、聞かずに出さない | Must | - | - | 人間の判断（[#126](https://github.com/etoyama/insight-blueprint-skills/issues/126)） |
| W1 | 派生の分析設計が、現在地・進捗・横断の振り返りの引用に現れる | Want | 解決 | 高（Claude の推測） | 課題1 |
| W2 | 派生が答えない論点に結ばない | Want | 解決 | 中（Claude の推測） | 課題2 |
| W3 | 足す手続きとコードの量 | Want | 費用 | 高（人間） | 人間の発言（リポジトリをシンプルに保ちたい） |

| Must | A: 派生元が結ばれている論点すべてに、聞かずに結ぶ | B: 結ぶ先を分析者に毎回聞く | C: 派生元の論点が1つなら聞かずに結び、複数なら聞く | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（派生元の論点は、分析者が framing で選んだものである） | 満たす | 満たす | 満たす |

| Want | A | B | C |
|---|---|---|---|
| W1 | 派生元が論点に結ばれていれば、必ず現れる | 現れる | 現れる |
| W2 | 派生元が複数の論点に結ばれていて、派生がその一部にしか答えないとき、余分に結ぶ | 余分には結ばない | 余分には結ばない |
| W3 | `tree_io` にコマンドを1つ足し、Branch Workflow に手順を1つ足す。KEEP ゲートは増えない | KEEP ゲートが1つ増える。US-8 AC 3 を変えるので、新しい Epic と DesignDoc が要る | B と同じく Epic が要り、手順の分岐も増える |

- 差がつく基準: W2 と W3。W1 は「何もしない」以外のすべての案が満たす。
- 感度: W2 の重みを高にするなら C になる。W3 を中に下げても、W2 が中のままなら A が残る。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 派生が答えない論点の進捗が「検証中」に見える | 結んだ論点を分析者に示す。派生の分析設計が終われば、進捗は元に戻る |
| B | 巡回のたびに質問が増え、分析者が読まずに答える | 抑えられない |
| C | 手順の分岐をモデルが取り違える（Epic 18 の Story 18.2 と 18.5 の手動確認で前例がある） | 分岐を `tree_io` の側に寄せる |
| 何もしない | 課題1 が残る | なし |

## Decision

A を採る。決め手は W3（人間の判断、2026-11-22）。

- 派生の分析設計は、派生元が結ばれている論点すべてに結ぶ。派生は同じ問いへの別の仮説なので、派生元と同じ論点に答えるものとして扱う。分析者には聞かず、結んだ論点を伝える。
- 結ぶのは `tree_io link-derived --theme T --design ID` である。派生元は分析設計の `parent_id` から読むので、呼ぶ側は渡さない。何度呼んでも結果は同じになる。
- 派生元がどの論点にも結ばれていないときと、テーマに論点ツリーが無いときは、何も結ばず、何も書かない。ツリーがあるテーマでは、`/analysis-framing` で論点に置けることを分析者に伝える。
- 呼ぶのは `/analysis-journal` の Branch Workflow で、分析設計を作った直後である。
- 単発の PR で入れる（[ADR-0012](0012-single-pr-scope.md)）。巡回は論点に起こした分析設計を進め（US-8 AC 2）、横断の振り返りは論点に結んだ分析設計を読む（US-3 AC 1）。派生がそこから外れていたので、定めた振る舞いに戻す fix である。

## Consequences

### Positive

- 派生の分析設計が進捗・現在地・横断の振り返りの引用に現れる。
- KEEP ゲートは増えず、`/analysis-auto` の手順は変わらない。派生を結んだ後の現在地は `in_progress` になり、終わっていない分析設計として `design_ids` に並ぶ。

### Negative

- 派生元が複数の論点に結ばれていると、派生が答えない論点にも結ぶ。外すコマンドは無いので、分析者は正本を手で直すことになる。
- 派生元と違う問いに答える派生は、誤った論点に結ばれる。journal の `question` を論点に昇格し、`/analysis-framing` で置くのが本来の道である。
- Epic 18 の DesignDoc の Decision `position-is-derived-by-tree-io` にある「どの skill も論点に結ばない」という記述は、この ADR で古くなる。DesignDoc は凍結しているので直さない。
- `tree_io` のコマンドが1つ増える。

## Alternatives considered

- **`design_io create` が `parent_id` を見て結ぶ** — `tree_io` は `design_io` を読む側にあり、逆向きの依存ができる。論点ツリーを書くのは `tree_io` だけ、という決まりも崩れる。
- **SKILL.md の文だけで、モデルに `tree_io get` から論点を探させて `tree_io link` を呼ばせる** — 文だけの手順はモデルが取り違えた前例があり、テストで確かめられない。

## Related

- Issue: [#134](https://github.com/etoyama/insight-blueprint-skills/issues/134)
- Epic: [epic-18](../design/epic-18-question-tree.md)（Decision `position-is-derived-by-tree-io`）
- 関連: [ADR-0012](0012-single-pr-scope.md)、[ADR-0026](0026-analysis-auto-walks-the-question-tree.md)
- Supersedes: なし
