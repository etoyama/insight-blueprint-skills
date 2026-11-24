# ADR-0050: 探索は予想を持たずに測った値を残し、検証は基準を分析設計に書く

## Status

Accepted

## Context

Epic 32（[#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)、[DesignDoc](../design/epic-32-exploration-and-confirmation.md)）の初版で決めた。
人間は、探索は測って答え、判定しないこと、検証は基準を先に固定して判定すること、探索には見込みも置かないことを決めた。
[ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md) は、探索の分析設計が検証仮説を持たないと決めた。

比較の土台にした事実（main aec5a4c。`skills/analysis-notebook/references/notebook-contract.md` の全文と、関係するコードを読んだ）。

- 契約の探索の `results` は、`hypothesis_direction` に「予想した方向」を書く。journal へ写すときは、予想に合えば `supports`、反すれば `contradicts` を付ける。
- `hypothesis_direction` は notebook の中の `results` の項目で、保存される verdict JSON には入らない。verdict の形は `conclusion`・`evidence_summary`・`open_questions`・`metrics`・`figures` である。Python で読む箇所も無い。
- 契約は verdict の `metrics` を「confirmatory: persist」としか書いていない。探索で測った値を残す決まりは無い。
- 分析ノートは、`direction` の無い evidence を「向きの無い証拠」の群に入れる道を持つ（`skills/_shared/design_note.py`）。指標の表は `threshold`・`p`・`pass` が無くても描ける。
- 分析設計の `Metric` で基準に使えるのは、自由記述の `comparison` だけである。`skills/analysis-design/SKILL.md` に、閾値を書く場所の記述は無い。`metrics` は任意である。
- design ② の対話は今も閾値を分析者に確かめている（[#210](https://github.com/etoyama/insight-blueprint-skills/issues/210) の記述）。確かめた結果を記録のどこに書くかが決まっていない。
- FRN-H01 の「振れ幅 1.5」という閾値は、分析設計の記録に置き場が無いまま判定に使われた（issue の記載）。

## Problem

- 課題1: 探索の契約が予想を書かせ、予想に合うかで証拠に向きを付ける。探索に見込みを置かないという決定に反する。
- 課題2: 探索は測って答えるのに、測った値を verdict に残す決まりが無い。分析ノートとレポートの指標の表が、探索では空になる。
- 課題3: 検証は基準を先に固定して判定するのに、分析設計に基準を書く場所が決まっていない。閾値は notebook の中で初めて数字になり、notebook を書く AI が決めることがある。

扱わない範囲: 検証の `results` と、検証の evidence の向き。表示の言葉（[ADR-0051](0051-designs-nest-under-their-question-and-state-is-worded-by-role.md)）。

## Decision Analysis

形式は `decision-analysis` スキルに従う（[FLOW-0004](flow/0004-decision-analysis-plugin.md)）。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 探索の契約と journal に、見込み・予想の項目が無い | Must | - | - | 人間の決定（探索に見込みを置かない）、課題1 |
| M2 | 保存済みの verdict JSON と journal が読める | Must | - | - | [ADR-0047](0047-stop-publishing-to-pypi.md) |
| W1 | 探索で測った値が、分析ノートとレポートに表で出る | Want | 解決 | 高（Claude の推測） | 課題2 |
| W2 | 検証の基準が、結果を見る前の記録から読める | Want | 解決 | 中（Claude の推測） | 課題3 |
| W3 | 契約と入口に足す決まりの量 | Want | 費用 | 中（Claude の推測） | 課題1〜3 |

### 探索の evidence の向き

| Must | a. `direction` を書かない | b. 探索の問いに対する別の向きを作る | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（予想が残る） |
| M2 | 満たす | 満たす | 満たす |

| Want | a | b |
|---|---|---|
| W3 | 既にある「向きの無い証拠」の道に乗る。足すコードが無い | 新しい2値と、その判断を notebook の後に毎回させる決まりが要る。判定に近い |

### 探索の `results` と verdict

| Must | a. 予想の項目を消し、`metrics` に値を持たせる | b. 予想の項目だけ消し、`metrics` は持たせない | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない |
| M2 | 満たす | 満たす | 満たす |

| Want | a | b |
|---|---|---|
| W1 | 表に値が出る。閾値と合否の列は出ないか「—」になる | 値は `evidence_summary` の文の中だけで、表は空 |

### 検証の基準の置き場

| Must | a. 文で決める | b. 作成時に機械で検査する | 何もしない |
|---|---|---|---|
| M1 | — | — | — |
| M2 | 満たす | 満たす（読むときは検査しない） | 満たす |

| Want | a | b | 何もしない |
|---|---|---|---|
| W2 | 記録から読める。書き忘れは review で拾う | 必ず読める | 読める保証が無い |
| W3 | SKILL.md 3つと契約の文 | a に加えて、作るときだけの検査。`metrics` が任意という今の決まりを検証で変える | 無し |

- 差がつく基準: 向きは W3、値は W1、基準の置き場は W2 と W3。
- 感度: W2 を高にするなら、基準の置き場は b に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 向きを書かない | 探索の証拠がすべて1群に並び、答えを強める材料と弱める材料が分かれない | 分かれ目は論点の現時点の答え（言えること、弱める証拠と留保）が持つ。引用つきで既に分かれる |
| 別の向きを作る | 向きの判断が、判定の代わりに使われる | なし |
| 値を持たせる | 探索で p 値を書き、閾値なしの「有意」が判定の代わりに使われる | 契約に、p 値は書いてよいが合否は書かないと書く |
| 値を持たせない | 探索の結果が文の中にしか残らない | なし |
| 基準を文で決める | 基準を書かないまま走る検証が出る | review の観点と design ② の確認 |
| 基準を機械で検査する | 指標なしで作れていた検証が作れなくなる。検査が作るときと読むときで2通りになる | 検査を `validate.py` の別の関数に置く |
| 何もしない | 閾値が notebook で初めて現れ続ける | なし |

## Decision

人間が選んだ（2026-11-25、Epic 32 の DesignDoc 初版のセッションで直接）。探索の evidence の向きは、人間が「どちらでもよい」と答えたので、推奨の a を採った。

1. journal の `evidence` の `direction` は検証仮説に対する向きである。探索の verdict から作る evidence は `direction` を持たない。探索の途中の見込みは、journal の `hypothesize` に残す。
2. 契約の探索の `results` から、`hypothesis_direction`（予想した方向）と `decision_reason` を消す。予想に合うかで向きを付ける規則も消す。
3. 探索の `results` と verdict の `metrics` は測った値を持つ。任意で効果量・信頼区間・標本サイズを持つ（[ADR-0013](0013-verdict-metric-optional-items.md)）。`threshold` と `pass` は置かない。p 値は書いてよいが、合否は書かない。
4. 検証の判定の基準は分析設計の primary の指標の `comparison` に文で書く（例:「分館と本館の差が 2.0 日以上なら支持。1.0 日未満なら棄却。その間は結論しない」）。`/analysis-design` の design ② が確かめ、`/analysis-review` の観点に入れる。notebook の `threshold` は `comparison` から写し、notebook が作らない。
5. 基準が書かれているかを、機械では検査しない。書き忘れが実際に起きてから足す。決め手は、足した検査を後から緩めるより、後から足すほうが、作れていたものを拒む判断を実データの後に回せること。
6. 引き継ぎの試行の q3 の正解の鍵は、根の現時点の答えが引用する出来事を、journal の `direction` ではなく、引用した文の種類で分ける。「言えること」が引用する出来事が支える証拠、「弱める証拠と留保」が引用する出来事が弱める証拠である。全体の整合で、1 の決まりと今の鍵（`direction` で分ける）がぶつかると分かり、人間が決めた。過去の試行の記録はその時点の鍵での採点として残す（[ADR-0035](0035-handoff-trial-records-keep-their-score.md)）。

## Consequences

### Positive

- 探索の notebook が予想を書かなくなる。
- 探索で測った値が分析ノートとレポートの表に出る。
- 検証の基準が結果を見る前の分析設計から読める。

### Negative

- 基準を書かないまま検証を作れる。止めるのは design ② の確認と review である。
- `comparison` は自由記述で、notebook がそこから `threshold` を写すのは AI の読みによる。写しまちがいを機械では確かめない。
- 探索の証拠は1群になる。答えを強める材料と弱める材料は、論点の現時点の答えを読まないと分かれない。論点ツリーの無いテーマでは分かれない。
- 契約の探索の例と `tests/integration/fixtures/sample_notebook.py` を直す。古い契約で作った探索の notebook は、走らせ直さないかぎり、verdict に `metrics` を持たない。分析ノートは今までどおり表を出さない。

## Alternatives considered

- **`Metric` に閾値の項目（数値）を足す** — 基準は「2.0 日以上なら支持、1.0 日未満なら棄却、その間は結論しない」のように、数1つで書けないことがある。今ある `comparison` に文で書けば足りる。数値の項目は、機械の検査が要ると分かってから考える。

## Related

- Epic: [#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)、[docs/design/epic-32-exploration-and-confirmation.md](../design/epic-32-exploration-and-confirmation.md)
- Stories: 32.3（入口）、32.4（notebook と journal）
- ADR: [ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md)、[ADR-0013](0013-verdict-metric-optional-items.md)、[ADR-0045](0045-notebook-is-plain-python-with-percent-cells.md)（契約の形は変えない。変えるのは `analysis` cell の `results` の中身と、verdict から journal への写し方）
