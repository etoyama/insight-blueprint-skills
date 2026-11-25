# ADR-0052: verdict の指標は、支持の線と棄却の線、指標の判定、値の区間の種類、群の行を持つ

## Status

Accepted

## Context

Epic 33（[#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[DesignDoc](../design/epic-33-verdict-on-record.md)）の初版で決めた。
Epic 32 の Epic PR の前に、人間が ib-notebook の実データ（テーマ FRN）で使用感を確かめた（2026-11-25）。
そこで、verdict の指標の形に収まらないものが3つ見つかった（[#235](https://github.com/etoyama/insight-blueprint-skills/issues/235)、[#237](https://github.com/etoyama/insight-blueprint-skills/issues/237) の F17 と F09）。
人間は3つを1本の ADR にまとめると決めた（2026-11-25）。

比較の土台にした事実（main 09fc48a）。

- verdict を書くのは notebook だけで、契約（`skills/analysis-notebook/references/notebook-contract.md`）の文に従って AI が生成する。verdict を検査するのは、fixture の契約テストだけである（契約と `tests/integration/` を読んだ）。
- verdict を読むのは `skills/_shared/design_note_read.py` の `_metric` だけである。`threshold` は任意の JSON を文字にして出す。`pass` は真偽でなければ無いものとして読む。`effect_size` と `confidence_interval` は、項目がそろわなければ無いものとして読む（コードを読んだ）。
- 読み手は並べるだけで、計算しない（[ADR-0013](0013-verdict-metric-optional-items.md)）。
- 保存済みの verdict には7つの形がある（DesignDoc の「前提にした事実」）。ib-notebook の FRN の5本は、`value`・`threshold`（数）・`pass`・`confidence_interval`・`sample_size` だけを持つ（実物を読んだ）。
- FRN-H05 の guardrail の指標は `pass: true` だけを持つ。`pass` は、検査に通ったかどうかとして使われている（実物を読んだ）。
- FRN-H05 の基準は「ρ の 95% HDI の上端が 0.70 未満なら支持。HDI の下端が 0.90 を超えるなら棄却。それ以外は結論できず」である。線に当てるのは区間の端である（分析設計の YAML を読んだ）。
- FRN-H04 の verdict は国籍と区分の組ごとの値を `名前[群|群]` の形で101個持つ（実物を読んだ）。
- 検証の判定の基準は分析設計の primary の指標の `comparison` に文で書く。notebook はそこから `threshold` を写す（[ADR-0050](0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md) の4）。

## Problem

- 課題1: 基準が2本の線を持つとき、`threshold`（数1つ）と `pass`（真偽）に収まらない。読み手は棄却の線を表から読めず、`pass: false` が棄却なのか、結論しないなのかも分からない。
- 課題2: 区間の種類を書く場所が無い。HDI を `confidence_interval` に入れると、分析ノートは「信頼区間」と出し、読み手はベイズの区間を頻度論の区間と読む。
- 課題3: 群ごとに値を持つ指標は群を名前に入れて平たく並べるしかない。分析ノートの表が101行になり、どの群の値かは名前の文字からしか分からない。
- 課題4: notebook が基準を `comparison` の文から写すのは AI の読みで、写しまちがいを誰も確かめない（ADR-0050 の Negative）。

扱わない範囲: verdict 全体の判定（`results` の `hypothesis_direction`）を verdict に持たせること。基準が書かれているかの検査（[ADR-0053](0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)）。

## Decision Analysis

### 判定の線の形

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの verdict の7つの形が、今と同じ表で出る | Must | - | - | ADR-0047 |
| M2 | 支持・棄却・結論しないの3つを、指標ごとに表から読める | Must | - | - | 課題1 |
| W1 | 線に何をどう当てたかを、表だけで読める | Want | 解決 | 中（Claude の推測） | 課題1、FRN-H05 |
| W2 | notebook（AI）が書きまちがえにくい | Want | 費用 | 高（Claude の推測） | 課題4 |
| W3 | 基準の写しを、後から確かめられる | Want | 解決 | 中（Claude の推測） | 課題4、#237 の F19 |
| W4 | 分析設計の側を変えない | Want | 費用 | 中（Claude の推測） | ADR-0050 の5 |

重みを「Claude の推測」としたものは、人間が案を選んだ時点で追認している。

- A. primary の指標に `support_line`・`reject_line`（数）と `judgment`（3つの値）を足す。`threshold` と `pass` はsecondary と guardrail の合否として残す。
- B. A の線を、数と当て方の文の組（`{"at": 数, "rule": 文}`）にする。
- C. A に加えて、分析設計の `Metric` にも `support_line`・`reject_line` を持たせ、notebook は数をそこから写す。

| Must | 何もしない | A | B | C |
|---|---|---|---|---|
| M1 | 満たす | 満たす（項目を足すだけで、古い項目の読み方は変えない） | 満たす | 満たす（`Metric` の新しい項目は任意） |
| M2 | 満たさない | 満たす | 満たす | 満たす |

| Want | A | B | C |
|---|---|---|---|
| W1 | 読めない。向きと当て方は、同じ分析ノートの「指標の定義」に出る `comparison` で読む | 読める。「0.70（HDI の上端が 0.70 未満）」と出る | A と同じ |
| W2 | 数を2つと語を1つ書く | 文を2つ足す。`comparison` の言い換えになり、食い違いうる | 数は分析設計から写すので、文を読まなくてよい |
| W3 | review が `comparison` の文と数を目で比べる | 同じ。比べる文が増える | 分析設計の数と verdict の数を機械で比べられる |
| W4 | 変えない | 変えない | `Metric` に2項目を足す。`/analysis-design` の手順と、分析を始めた後に固定する範囲も変わる |

- 差がつく基準: W1 は B、W2 と W3 は C、W4 は A と B が勝つ。
- 感度: W3 を高にすれば C、W1 を高にすれば B に変わる。どちらも中なら、変える所がいちばん小さい A になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 何もしない | 棄却と結論しないを取り違える | なし |
| A | 表だけ見た人が、線の向きを取り違える | 分析ノートは同じページに `comparison` を出している。結果の review の観点に、線と判定が `comparison` と合うかを入れる（[ADR-0054](0054-review-covers-the-result-and-its-comments-reach-the-reader.md)） |
| B | `rule` の文が `comparison` と食い違う | review で拾う |
| C | 区間の端に当てる基準は数2つでは書ききれず、結局 `comparison` の文も要る | 文と数の両方を持つ |

### 値の区間と群の行

どちらも、評価の前に形がほぼ決まった。落とした案は Alternatives considered に書く。

## Decision

人間が選んだ（2026-11-25、Epic 33 の DesignDoc 初版のセッションで直接）。見本（Artifact。コミットしていない）で案 A と案 B の表を見比べた。線の形は A で、決め手は W2 と W4 である。

1. 検証の notebook は判定の基準を持つ primary の指標に、支持の線（`support_line`）と棄却の線（`reject_line`）を数で書く。数は `comparison` から写し、notebook が作らない。線は少なくとも一方を書く。基準が1本の線なら `support_line` だけを書く。
2. 同じ指標に、指標の判定（`judgment`）を書く。値は `supported`・`rejected`・`inconclusive` のどれかである。2本の線の間は結論しない範囲で、判定は `inconclusive` になる。3つの判定を `pass` で表さない。`results` の `hypothesis_direction` はprimary の指標の判定と食い違わない。
3. `threshold` と `pass` はsecondary と guardrail の指標の合否として残す。1本の線と、通ったかどうかである。primary の指標には新しく書かない。
4. 探索の指標は線も、指標の判定も、合否も持たない（ADR-0050 の3のまま）。
5. 指標の値の区間は `interval` に書く。形は `{"kind": str, "level": float, "lower": float, "upper": float}` である。`kind` は区間の種類の名前で、open string にする（`confidence`・`hdi`・`eti` など）。項目は4つがそろって初めて有効である。notebook は `confidence_interval` を新しく書かない。
6. 群ごとに値を持つ指標は軸の名前の並び（`by`）と群の行の並び（`groups`）を持つ。群の行は、軸と同じ数の群の名前（`group`）と、`value` と、任意の項目（効果量・値の区間・標本サイズ・p 値）を持つ。群の行は、指標の判定と合否を持たない。指標は、値を1つ持つか、群の行を持つかのどちらかである。群を指標の名前に埋めない。
7. 読み手は保存済みの verdict を今までどおりに読む。`confidence_interval` は、種類が信頼区間の値の区間として読む。`interval` と両方があれば `interval` を読む。`judgment` が3つの値のどれでもなければ、無いものとして読む。
8. 分析ノートとレポートの表は、支持の線・棄却の線・判定の列を持ち、判定を「支持」「棄却」「結論しない」と出す。区間の列の見出しは「区間」で、種類と水準を添える。表示の言葉を持つ種類は `confidence`（信頼区間）・`hdi`（HDI）・`eti`（等裾信用区間）で、ほかは書かれたとおりに出す。どの指標も値を持たない列は出さない。
9. 群を持つ指標は指標ごとの表に出す。軸が2つで、群の行が値だけを持つときは、軸を縦と横に置く。それ以外は群の列を持つ縦の表にする。
10. 用語を次のとおりにする。支持の線、棄却の線、結論しない範囲、指標の判定、値の区間、群の行。「信頼区間」は値の区間の種類の1つの名前にする。「しきい値」と「合否」は、secondary と guardrail の指標の語として残す。
11. 分析設計の `comparison` は構造化しない。写しを機械で照らす検査は、写しまちがいが実際に起きてから足す。

## Consequences

### Positive

- 読み手が棄却の線と、結論しないという判定を、表から読める。
- HDI が信頼区間と出なくなる。
- 群ごとの値が軸を持つ表で読める。
- 保存済みの verdict は手を入れずに今と同じ表で出る。

### Negative

- 線の向き（以上か未満か）と、線に何を当てるか（値か区間の端か）は、verdict に残らない。`comparison` の文を読まないと分からない。
- notebook が線を写しまちがえても、機械は気づかない。拾うのは結果の review である。
- 指標の中に、2組の語が並ぶ。primary の線と判定、secondary と guardrail のしきい値と合否である。notebook が取り違えると、primary に `pass` を書く。読み手は書かれたとおりに出す。
- `kind` が open string なので、同じ種類に別の名前（`hdi` と `credible`）が付きうる。
- ADR-0013 の `confidence_interval` は、新しい verdict では使わなくなる。読む道は消す時期を決めていない。
- 群の軸が3つ以上のときは、縦の表になり、行数は減らない。
- 契約の例と `tests/integration/fixtures/sample_notebook.py` を直す。古い契約で作った notebook は、走らせ直さないかぎり、新しい項目を持たない。

## Alternatives considered

- **`confidence_interval` に `kind` を足す** — 項目は増えないが、名前が HDI に対して嘘になる。
- **群ごとの値を、verdict の top-level の別の表に置く** — 指標の名前と値が離れ、読み手が2か所を結ぶことになる。
- **線を演算子つきで構造化する（`{"of": "interval_upper", "op": "<", "value": 0.70}`）** — 読み手が判定を計算し直せるが、読み手は計算しない（ADR-0013）。当てる量の種類も手法ごとに増える。

## Related

- Epic: [#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[docs/design/epic-33-verdict-on-record.md](../design/epic-33-verdict-on-record.md)
- Issues: [#235](https://github.com/etoyama/insight-blueprint-skills/issues/235)、[#237](https://github.com/etoyama/insight-blueprint-skills/issues/237)（F17、F09）
- [ADR-0013](0013-verdict-metric-optional-items.md)（区間の項目をこの ADR が改める）、[ADR-0050](0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)（4の「`threshold` を写す」を、primary では線を写すと改める）、[ADR-0047](0047-stop-publishing-to-pypi.md)
- Supersedes: なし
