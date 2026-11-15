# ADR-0012: Epic 以外の PR は、定めた振る舞いを変えない変更に限る

## Status

Accepted

## Context

[WORKFLOW](../WORKFLOW.md) は開発の単位を Epic と Story の2階層で定める。
Epic を伴わない PR（リリース、依存の更新、単発の fix や chore）をいつ認めるかは書いていない。
このリポジトリでは単発の PR が多く、[ADR-0009](0009-adopt-repo-template-flow.md) の chore PR（#55）もその1本だった。

2026-11-15 に人間が D11 として決めた（準拠作業の論点番号）。
比較の前提にした事実は次のとおり。

- #55 より前に merged になった PR は、Dependabot を除いて27本ある。Epic が13本、単発が14本で、
  単発の内訳はリリース5本、chore と docs が6本、fix 2本、feat 1本（#43）だった
  （`gh pr list --state merged` を head ブランチの接頭辞で分けて数えた。判断時の調査は「25本中13本」で、数え方の範囲が少し違う）。
- #43（`feat/analysis-auto-upstream-gates`）は単発の PR で、[ADR-0007](0007-upstream-judgment-gates.md) を含み、
  `/analysis-auto` の振る舞いを変えた（PR の題と ADR-0007 を読んだ）。
- ADR-0009 は「閉じた Epic の DesignDoc には追記しない。機能を直すときは、新しい Epic を新形式で切る」と決めている。
- PR テンプレートは repo-template のコピーである（`.github/PULL_REQUEST_TEMPLATE.md`）。

## Problem

- 課題1: 振る舞いを変える変更が単発の PR で入ると、要求と背景の正本（DesignDoc、[FLOW-0001](flow/0001-designdoc-owns-requirements.md)）がないまま `main` に入る。
- 課題2: リリースや依存の更新まで Epic にすると、DesignDoc と Story の手続きが中身に見合わない。
- 課題3: 単発か Epic かの線が引かれていないと、PR ごとに判断が揺れる。

扱わない範囲: PR テンプレートの変更、Dependabot の PR の扱い（今のまま単発）。

## Decision Analysis

選択肢は人間との判断（D11）で比べた内容を、この ADR を書くときに表へまとめ直したものである。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 振る舞いを足す・変える変更は、DesignDoc を伴って `main` に入る | Must | - | - | 課題1、ADR-0009 |
| W1 | 単発か Epic かを、PR を出す前に迷わず決められる | Want | 解決 | 中（Claude の推測） | 課題3 |
| W2 | 手続きの数 | Want | 費用 | 高（Claude の推測。人間が A を選んで追認） | 課題2、YAGNI |

| Must | 何もしない | A. 定めた振る舞いを変えない変更だけ単発 | B. すべて Epic | C. 種類（リリース・依存・文書・fix）を列挙して単発 |
|---|---|---|---|---|
| M1 | 満たさない（#43 のような feat が単発で入る） | 満たす | 満たす | 満たさない（fix の名で振る舞いを変えられる） |

| Want | A. 定めた振る舞いを変えない変更だけ単発 | B. すべて Epic |
|---|---|---|
| W1 | 「既存の DesignDoc・ADR が定めた振る舞いを変えるか」の1問で決まる。境目の fix は迷いうる | 迷わない |
| W2 | 27本中14本は単発のまま。単発だった feat の #43 だけが Epic 側に移る | 27本すべてが Epic になり、リリースにも DesignDoc が要る |

- 差がつく基準: W2。W1 は B が勝つが、A の迷いは「迷ったら Epic にするか人間に聞く」で抑えられる。
- 感度: 単発の PR がほとんど出ないなら B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 振る舞いを変える変更が「fix」として単発で入る | 判定の問いを「定めた振る舞いに戻すか、変えるか」にする。迷ったら Epic にするか人間に聞く |
| B | リリースの PR にも DesignDoc を書くことになり、手続きが形だけになる | なし |

## Decision

A を採る。決め手は W2。

- Epic を伴わない単発の PR は、既存の DesignDoc・ADR が定めた振る舞いを変えない変更だけに認める。
  リリース、依存の更新、文書の修正、定めた振る舞いに戻す fix、道具の移植（#55 など）がこれに当たる。
- 振る舞いを足す・変える変更は Epic にする。閉じた Epic の機能を直すときも新しい Epic を切る（ADR-0009 と同じ）。
- 単発の PR で設計判断が出たら、ADR を書くか（CLAUDE.md §5 の選択肢1）、PR 説明に書いて人間に確かめる（選択肢3）。
- 単発か Epic か迷ったら、Epic にするか人間に聞く。
- CLAUDE.md §4 から、この ADR へポインタを1行張る。PR テンプレートは変えない。

## Consequences

### Positive

- 振る舞いの変更には、必ず要求と背景の正本（DesignDoc）が付く。
- 単発の PR の大半（リリース・依存・文書・fix）は、今の手続きのまま出せる。

### Negative

- 「定めた振る舞いに戻す fix」と「振る舞いを変える fix」の境目は、判断が要る。
- 小さな feat でも Epic と DesignDoc が要り、#43 のような変更の手続きが増える。
- この規則は repo-template にない。repo-template に返すまで、ここだけの規則になる。

## Alternatives considered

なし。検討した案はすべて Decision Analysis の表に入れた。

## Related

- Epic: [epic-11](../design/epic-11-repo-template-compliance.md)（Story #59）
- 関連: [ADR-0009](0009-adopt-repo-template-flow.md)、[ADR-0007](0007-upstream-judgment-gates.md)（単発の PR で入った ADR の例）
- Supersedes: なし
