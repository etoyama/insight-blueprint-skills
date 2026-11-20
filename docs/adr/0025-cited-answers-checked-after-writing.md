# ADR-0025: モデルが書く答えは記録を引用させ、書いた後に検査する

## Status

Accepted

## Context

論点ツリーの振り返りでは、`/analysis-reflection` が複数の分析設計の journal を読み、論点ごとに現時点の答えを書く（[epic-18](../design/epic-18-question-tree.md)）。
これは、モデルに統合の文を書かせることにあたる。

同じ型の失敗が既に起きている。`/analysis-report` は SKILL.md とテンプレートで計算を禁じているのに、Implications に入力に無い比（約1.9倍）を書いた（[#105](https://github.com/etoyama/insight-blueprint-skills/issues/105)、v0.10.0 の実機確認、2026-11-20）。
決まりを文で書くだけでは止まらないことが分かった。

比較の前提にした事実は次のとおり。

- 計算の禁止は `skills/analysis-report/SKILL.md:82` にある（#105 の本文と、ファイルを読んで確かめた）。
- 書いた後の検査には前例がある。`report_check`（`skills/_shared/report_check.py`、[ADR-0019](0019-report-source-text-escaped-and-checked.md)）は、できたレポートを読むだけで書き換えず、違反があれば終了コード 1 を返す。
- journal の出来事は `{design_id}-E{nn}` の id と本文を持つ。`evidence` は `metadata.direction` を持つ（`skills/analysis-journal/SKILL.md`）。

## Problem

- 課題1: 現時点の答えに記録に無い数や結論が混ざると、分析者はそれを根拠に次の判断をする。新人の分析者ほど見抜けない。
- 課題2: 決まりを文で書いても守られないことが #105 で分かっている。効いたかを確かめる手段が要る。
- 課題3: 現時点の答えは文章として読めなければならない。読めないと、引き継いだ人が使えない。

扱わない範囲: `/analysis-report` の Implications の修正（#105 そのもの）。数を含まない言い過ぎを機械で止めること。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 効いたかをテストで確かめられる | Must | - | - | 課題2、[ADR-0010](0010-skill-tdd-structure-tests.md) |
| W1 | 記録に無い数と参照が、分析者に届く前に止まる | Want | 解決 | 高（Claude の推測、人間が推奨を採った） | 課題1 |
| W2 | 答えが文章として読める | Want | 解決 | 中（Claude の推測） | 課題3 |

| Must | 引用と検査器 | 禁止を書くだけ | 答えは人が書く | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（検査器の unit test と、合成シナリオでの再現） | 満たさない（#105 で効かないと分かった） | 満たす | 満たさない |

| Want | 引用と検査器 | 答えは人が書く |
|---|---|---|
| W1 | 数と参照は機械で止まる。数を含まない言い過ぎは止まらない。 | AI が答えを書かないので生じない。 |
| W2 | 読める。 | 新人の分析者に統合を任せることになり、「委ねる」価値が落ちる。 |

- 差がつく基準: W1 と W2。
- 感度: W2 を低く見るなら「答えは人が書く」が最も安全。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 引用と検査器 | 数を含まない言い過ぎは通る。数の表記の揺れ（全角、桁区切り、%）で誤検知する | 文に種類（言えること・未判別・弱める証拠と留保）を宣言させる。引き継ぎの試行で人が読む。表記は検査器で正規化し、unit test で固める |
| 答えは人が書く | 利用価値が落ちる | （課題3 と衝突する） |

## Decision

引用と検査器を採る（人間の判断3、2026-11-20）。決め手は W1 と W2 の両立。

- 現時点の答えは文の並びで書く。文はそれぞれ、種類（`claim`・`undetermined`・`weakening`）と、引用する journal の出来事の id を1つ以上持つ。
- 親の論点の答えは子の進捗の数から推定せず、子孫の論点にひもづく分析設計の出来事を引用して書く。
- ツリーの検査（`tree_check`）は、書いた後に次を違反として挙げる。引用先の出来事が無い。引用先の分析設計がその論点か子孫の論点にひもづいていない。文に出てくる数が引用した出来事の本文に無い。検査は読むだけで、ツリーを書き換えない。
- skill は、違反が0件になるまで分析者に答えを届けない。直せない文は除き、除いたことを分析者に伝える。
- 用語「違反」は、レポートの検査とツリーの検査の両方が挙げるものを指すように広げる（[docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md)）。

## Consequences

### Positive

- #105 と同じ型の捏造を、モデルや決まりの文に頼らず止められる。
- 答えの各文から証拠へ戻れるので、引き継いだ人が根拠を確かめられる。

### Negative

- 数を含まない言い過ぎは通る。この ADR では塞がない（epic-18 の未決事項）。
- 引用先の本文に数が無い答え（たとえば、2つの数を比べた「多い」「少ない」）は書けても、比や差の値は書けない。値が要るなら、notebook で計算して journal に残してから引用する。

## Alternatives considered

- **答えを検査の前に構造テストで縛る** — 構造テストは SKILL.md の文を確かめるだけで、モデルが書いた答えは確かめられないので落とした。

## Related

- Epic: [#116](https://github.com/etoyama/insight-blueprint-skills/issues/116)、[epic-18](../design/epic-18-question-tree.md)
- Issue: [#105](https://github.com/etoyama/insight-blueprint-skills/issues/105)
- 関係する ADR: [ADR-0019](0019-report-source-text-escaped-and-checked.md)、[ADR-0024](0024-question-tree-yaml-and-generated-html.md)
