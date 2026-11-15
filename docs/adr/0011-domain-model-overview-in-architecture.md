# ADR-0011: Domain Model の全体図を ARCHITECTURE に置く

## Status

Accepted

## Context

repo-template の DesignDoc テンプレートは `## Domain Model` 節を初版で必須にしている
（[design-doc-template](../../.claude/rules/design-doc-template.md)）。
差分を描くには基準になる全体図が要るが、repo-template の ARCHITECTURE にも
[WORKFLOW](../WORKFLOW.md) §2 の正本の表にも、全体図の置き場所がない。

2026-11-15 に人間が D7 として決めた（準拠作業の論点番号）。
残っていた「Python のクラスを持たない YAML / JSON の契約を図に含めるか」も、同じ日に人間が決めた。
比較の前提にした事実は次のとおり。

- このリポジトリに mermaid の `classDiagram` と `stateDiagram` は1枚もなかった（判断時の調査による）。
- モデルのクラスは `src/insight_blueprint/models/` に18個、`skills/_shared/models.py` に4個ある
  （`grep -n '^class '` で確かめた）。状態遷移は `validate.py` の `VALID_TRANSITIONS` にある。
- 2026-07 以降に `models/` を変えたコミットは1件（E5c）だけである（判断時の調査による）。
- journal（`{id}_journal.yaml`）、revision、`verdict.json` の `figures[]`、`package_allowlist.yaml` は
  Python のクラスを持たず、形の正本は各 SKILL.md と `notebook-contract.md` にある（各ファイルを読んだ）。
- PR テンプレートには「Domain Model 図を変えた場合、その変更を本 PR に書いた」の項目がある
  （`.github/PULL_REQUEST_TEMPLATE.md` を読んだ）。

## Problem

- 課題1: 全体の Domain Model 図がなく、DesignDoc が差分を描く基準を示せない。
- 課題2: skill だけを変える Epic ではモデルが変わらない。毎回同じ図を描くと、レビューで読み比べることになる。
- 課題3: DesignDoc の節を省くと、「変更なし」と「書き忘れ」を区別できない。
- 課題4: クラスを持たないファイルの契約は、全体図から辿れない。フィールドまで図に描くと、
  `notebook-contract.md` などと正本が重複し、図とコードの照合もできなくなる。

扱わない範囲: `stateDiagram` の全体図（状態遷移の正本は `VALID_TRANSITIONS` のまま）。

## Decision Analysis

### 全体図の置き場所（D7）

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 「変更なし」と「書き忘れ」を区別できる | Must | - | - | 課題3、design-doc-template |
| W1 | 今の全体モデルが1か所で見える | Want | 解決 | 高（Claude の推測。人間が C を選んで追認） | 課題1 |
| W2 | モデルが変わらない Epic でレビューの量が増えない | Want | 解決 | 高（Claude の推測） | 課題2 |
| W3 | repo-template からの逸脱と、図の保守 | Want | 費用 | 中（Claude の推測） | ADR-0009 の D1 の決め手 |

| Must | 何もしない | A. 参照だけ | B. 毎回描く | C. ARCHITECTURE に全体図 | D. 準拠 Epic の DesignDoc に全体図 |
|---|---|---|---|---|---|
| M1 | 満たさない | 満たす | 満たす | 満たす | 満たす |

| Want | A. 参照だけ | B. 毎回描く | C. ARCHITECTURE に全体図 | D. 準拠 Epic の DesignDoc に全体図 |
|---|---|---|---|---|
| W1 | 全体図がなく、コードを読むしかない | 最新の DesignDoc を探せば見える | 正本の文書で1か所に見える | 閉じた Epic の文書にあり、更新すると凍結（ADR-0009）に反する |
| W2 | 増えない | 毎回増える | 増えない（「変更なし」とリンク） | 増えない |
| W3 | 逸脱なし | 逸脱なし。図の数が増える | WORKFLOW §2 の表にない節を ARCHITECTURE に足す | 逸脱なし |

- 差がつく基準: W1（C > D > A・B）と W3（A・D > C）。決め手は W1。
- 感度: 逸脱をゼロにしたいなら D に変わる。

### クラスを持たない契約の扱い（D7 の残り）

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 図のクラスがコードと自動で照合できる | Must | - | - | [ADR-0010](0010-skill-tdd-structure-tests.md)（✓ は自動テストだけ） |
| W1 | 契約の所在が全体図の節から辿れる | Want | 解決 | 高（Claude の推測。人間が A を選んで追認） | 課題4 |
| W2 | 契約の正本が重複しない | Want | 解決 | 中（Claude の推測） | WORKFLOW §2 |

| Must | 何もしない | A. 図はクラスだけ、表でリンク | B. 契約もフィールドつきで描く | C. 名前だけのノードで描く |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（コードに照合先がない） | 満たす（照合テストに例外の一覧が要る） |

| Want | 何もしない | A. 表でリンク | C. 名前だけのノード |
|---|---|---|---|
| W1 | 辿れない | 図のすぐ下の表から辿れる | 図の中から辿れる |
| W2 | 重複しない | 重複しない | 重複しない |

- 差がつく基準: W1（何もしないは辿れない）と、照合テストの単純さ（A は例外の一覧が要らない）。
- 感度: 図の中で関係まで見せたいなら C に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 全体図 C | モデルを変えた PR が全体図の更新を忘れる | 図とコードのクラスの一致を `tests/docs/` で検査する。PR テンプレートの Domain Model の項目を、全体図の更新も含むと読む |
| 全体図 D | 準拠 Epic が閉じたあと、全体図を更新できない | なし |
| 契約 A | 表のリンク先の契約が変わっても、表が古くなる | リンク切れを `tests/docs/` で検査する |
| 契約 C | 例外の一覧と図がずれる | なし |

## Decision

全体図は C、契約は A を採る。決め手はどちらも W1。

- `docs/ARCHITECTURE.md` に `## Domain Model` 節を置き、`src/insight_blueprint/models/` と
  `skills/_shared/models.py` のすべてのクラスを mermaid の `classDiagram` で描く。
- Python のクラスを持たないファイルの契約は図に描かず、図の下の表に、ファイルと形の正本へのリンクを置く。
- Epic の DesignDoc の `## Domain Model` 節は差分だけを描く。変更がなければ「変更なし」と書き、全体図へリンクする。
- モデルを変えた PR では、同じ PR で全体図も更新する。PR テンプレートの「Domain Model 図を変えた場合」の項目は、
  全体図の更新も含むと読む。テンプレートは repo-template のコピーなので書き換えない。
- 図とコードのクラスが一致することは `tests/docs/test_canonical_docs.py` が確かめる。

## Consequences

### Positive

- 今のモデルを ARCHITECTURE の1枚で見られ、DesignDoc は差分だけを描けばよい。
- クラスを足したり消したりして全体図を直し忘れると、テストが落ちる。

### Negative

- WORKFLOW §2 の正本の表にない節を ARCHITECTURE に足す。repo-template に返すまで、ここだけの形になる。
- テストが照合するのはクラス名だけで、フィールドと関係のずれは捕まえない。
- PR テンプレートの項目の読み方はテンプレートの文面には書かれていない。

## Alternatives considered

なし。検討した案はすべて Decision Analysis の表に入れた。

## Related

- Epic: [epic-11](../design/epic-11-repo-template-compliance.md)（Story #58 で全体図を描き、#59 でこの ADR を書いた）
- 関連: [ADR-0009](0009-adopt-repo-template-flow.md)、[ADR-0010](0010-skill-tdd-structure-tests.md)、[ARCHITECTURE の Domain Model](../ARCHITECTURE.md#domain-model)
- Supersedes: なし
