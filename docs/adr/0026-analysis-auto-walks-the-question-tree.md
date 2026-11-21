# ADR-0026: 分析者の入口を `/analysis-auto` ひとつにし、論点ごとに巡回させる

## Status

Accepted

## Context

Epic 18 はテーマごとの論点ツリーを足す（[epic-18](../design/epic-18-question-tree.md)）。
DesignDoc の初版は着手を `/analysis-framing`、横断の振り返りを `/analysis-reflection` に置き、分析者がそれぞれを起動する形にしていた。
`/analysis-auto` からの論点ツリーの操作は範囲外で、guided autopilot は分析設計1つを単位に動かしたままだった。

人間は初版のシーケンス図を見て、次の3つを求めた（2026-11-20）。

- 分析者からの入口は `/analysis-auto` ひとつにする。そこから framing をして、必要なときだけ分析者に確認し、reflection を経て次の論点を決める。これを繰り返して探索を進める。
- 研究では上流にラピッドレビュー、問題化、RQ の設定を入れる。
- 深める・親に戻る・区切るを決める前に、そこまでの分析の結果をレポートで見たい。ツリーだけでは決められない。

比較の前提にした事実は次のとおり。

- `/analysis-auto` は今、分析設計1つを framing から upload まで一直線に流して終わる（`skills/analysis-auto/SKILL.md` の Step 2 を読んで確かめた）。
- レポートを書く前の確認は KEEP ゲートである（同じファイルの Gate policy の表、report の行）。
- `/analysis-report` は、分析設計が terminal status でないとレポートを書かない（`skills/analysis-report/SKILL.md:48`）。
- `/rq-problematization` は RQ Brief を出して `/analysis-framing` へつなぐ。分析者に聞くのは、前提の一覧を途中で確認するかどうかと、確認を選んだときの前提の選び直しだけである（`skills/rq-problematization/SKILL.md` の Workflow Overview と Chaining）。
- 個々の skill は `disable-model-invocation: true` のままで、自律は `/analysis-auto` を起動した実行に限る（[ADR-0005](0005-selective-autonomous-chaining.md)）。
- `.insight/` の中身を外へ送る前は、KEEP ゲートで承認を待つ（[ADR-0016](0016-approval-before-external-send.md)）。

## Problem

- 課題1: 入口が skill ごとに分かれていると、論点を順に調べていく流れが分析者の頭の中にしか残らない。経験の浅い分析者は次にどの skill を呼ぶかで止まる。
- 課題2: ツリーの決定に要る材料が、決めるときに揃っていない。レポートは今、結論の後に作るかを聞かれてから書く。
- 課題3: 研究では、問いを立てるまでの工程（先行研究の収集、前提の問い直し、RQ の設定）が auto の外にある。

扱わない範囲: `/rq-problematization` の先行研究の集め方を、検索の記録や採否の基準を残すラピッドレビューに強めること。結果を別のソースや別の条件で確かめる skill。どちらも epic-18 の未決事項に置く。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 個々の skill は単独で起動でき、`disable-model-invocation` を変えない | Must | - | - | ADR-0005 |
| M2 | 外へ送る前の承認は残る | Must | - | - | ADR-0016 |
| W1 | 分析者が覚える入口が少ない | Want | 解決 | 高（人間） | 課題1 |
| W2 | ツリーの決定の前に、レポートと論点ツリーが揃う | Want | 解決 | 高（人間） | 課題2 |
| W3 | 今の auto の使い方（分析設計1つを流す）を変えない | Want | 費用 | 中（Claude の推測） | Epic 08 の利用者 |
| W4 | 作る・保守する部品が少ない | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | auto を巡回に広げる | 巡回用の driver を別に作る | 何もしない（入口を分けたまま） |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たす |
| M2 | 満たす | 満たす | 満たす |

| Want | auto を巡回に広げる | 巡回用の driver を別に作る |
|---|---|---|
| W1 | 入口は1つ。 | 入口が2つになり、どちらを使うかを分析者が選ぶ。 |
| W2 | 巡回の中でレポートを書いてから決定を聞ける。 | 同じ。 |
| W3 | 変わる。分析設計1つで終わらず、ツリーの決定まで進む。 | 変わらない。 |
| W4 | SKILL.md は1つのまま。ゲートの表が長くなる。 | driver が2つになり、ゲートの決まりを2か所で保つ。 |

- 差がつく基準: W1・W3・W4。
- 感度: W3 を高にすると「巡回用の driver を別に作る」に変わる。W1 は人間が高と決めたので、今の重みでは変わらない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| auto を巡回に広げる | 1回の実行が長くなり、途中で文脈が尽きる。ゲートが増えて、聞かれる回数が増える | 状態は論点ツリーが持つ。auto は最新のツリーの決定から再開できる。足すゲートは4つに限る |
| auto を巡回に広げる（レポートを AUTO で書く） | 分析者が頼んでいないレポートが手元に増える | 書くのは手元のファイルだけ。Claude Docs へ送る前の承認は残す |
| 巡回用の driver を別に作る | 2つの driver のゲートの決まりがずれる | （抑えにくい） |
| 何もしない | 課題1〜3 が残る | （抑えられない） |

## Decision

`/analysis-auto` を巡回に広げる（人間の判断、2026-11-20）。決め手は W1。

- 分析者の入口は `/analysis-auto` ひとつとする。auto はテーマを受け、論点ツリーが無ければ `/analysis-framing` で作り、あれば最新のツリーの決定が指す論点から再開する。
- 1回の巡回は論点に分析設計を起こし、premortem、notebook、journal、分析設計の振り返り、レポート、テーマを横断した振り返りを経て、ツリーの決定を残すまでとする。分析者が区切るを選ぶか、止めると言うまで巡回を続ける。
- KEEP ゲートを4つ足す。根の問いと到達点、最初に調べる論点、ツリーの決定、根の版を上げるかどうか。
- 分析設計の結論が出たら（terminal status）、auto は聞かずに `/analysis-report` でレポートを書き、続けて `/report-upload` を始める。レポートを書く前の確認は KEEP から AUTO に移す。Claude Docs へ送る前の承認は `/report-upload` の KEEP ゲートのまま残す。
- 結論が出ていない回（refine・branch）はレポートを書かない。そのときのツリーの決定は論点ツリーと journal を見てする（人間の判断、2026-11-20）。
- 研究で RQ がまだ無いときは、auto が framing の前に `/rq-problematization` を呼び、RQ Brief を framing に渡す。
- 個々の skill は今までどおり単独で起動できる。ADR-0005 の「自律は `/analysis-auto` を起動した実行に限る」は変えない。
- `skills/analysis-auto/SKILL.md` と [docs/ARCHITECTURE.md](../ARCHITECTURE.md) は、Epic 18 の Story で実装と同じ PR で直す。

## Consequences

### Positive

- 分析者は skill の名前と順番を覚えずに、問いを委ねて次の論点を選ぶところまで進められる。
- ツリーの決定のときに、レポートと論点ツリーの両方が手元にある。
- 業務と研究が同じ入口と同じ巡回を使う。違うのは上流だけになる。

### Negative

- 今の auto の使い方が変わる。分析設計1つを流して終えたい分析者は、ツリーの決定で区切るを選ぶ。
- 論点ツリーが無いテーマの、既にある分析設計を `design_id` で渡されたときは、ツリーを作るかどうかを聞く（epic-18 の Decision: ask-once-for-treeless-design）。
- レポートを手で直す前に `/report-upload` が始まる。直してから送りたい分析者は、承認のゲートで送らずに止める。
- ゲートを守るかどうかは今までと同じく SKILL.md に従う Claude に頼る（ADR-0005 の Negative のまま）。
- `/rq-problematization` の先行研究の収集は検索の記録、採否の基準、文献ごとの質の評価を残さない。ラピッドレビューと呼べる所までは届かない。

## Alternatives considered

- **framing と reflection を入口のままにし、案内の文だけを足す** — 「次は `/analysis-design`」と案内しても、呼ぶのは分析者のままで、課題1 が残るので落とした。
- **結論が出ていない回にも途中経過のレポートを書く** — `/analysis-report` の terminal status の条件を緩めることになる。人間が要らないと判断したので落とした。

## Related

- Epic: [#116](https://github.com/etoyama/insight-blueprint-skills/issues/116)、[epic-18](../design/epic-18-question-tree.md)（US-8、Sequence Diagram）
- 関係する ADR: [ADR-0005](0005-selective-autonomous-chaining.md)、[ADR-0016](0016-approval-before-external-send.md)、[ADR-0024](0024-question-tree-yaml-and-generated-html.md)、[ADR-0025](0025-cited-answers-checked-after-writing.md)
