# ADR-0066: 分析設計は、対象・粒度・分母を持てる

## Status

Accepted

## Context

Epic 35（[#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[DesignDoc](../design/epic-35-hand-over-questions.md)）の初版で、ほかの決定を組み合わせる途中で見つけた。
[ADR-0063](0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md) は、任せる分析設計を横に並べ、分析設計の間で違う行にコードが印を付けると決めた。
[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) は、任せる前に読んだ内容を変えないと進めないなら聞くと決めた。
どちらも、対象（誰を、何を数えるか）・粒度（1行が何か）・分母（割合の下に置く数）が記録にあることを前提にしている。

比較の土台にした事実。

- `AnalysisDesign` が持つのは、問いか検証仮説、手法、指標、説明変数、図、データソースである。`Methodology` は手法名・パッケージ・理由と、自由な項目（抽出の手順など）を持つ（`src/insight_blueprint/models/design.py` を読んだ）。対象・粒度・分母の項目は無い。
- 今の確認（design ③）は、想定の粒度とおおよその行数を、対話エージェントがチャットで言う（`skills/analysis-auto/SKILL.md`）。記録には残らない。
- 見本の画面1 は、粒度と分母の行に「A と違う」の印を付けている。
- `AnalysisDesign` は既定値つきの項目を足せる。決定の文脈（`DecisionContext`）は、任意で、あるときは両方が空でない組として足された（[ADR-0014](0014-analysis-design-decision-context.md)）。

## Problem

- 課題1: 対象・粒度・分母が記録に無いと、横に並べたときの印をコードで付けられない。対話エージェントの文に頼る。
- 課題2: 任せた後に「読んだ内容を変えたか」を照らす相手が無い。実行エージェントが自分で気づくのに頼る。
- 課題3: 戻った後に、どの粒度と分母で走ったのかを、分析ノートから読めない。

扱わない範囲: 対象・粒度・分母を、notebook の出力と機械で照らすこと。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの分析設計がそのまま読める | Must | - | - | 不変条件（正本は YAML） |
| W1 | 印と、読んだ内容の照らし合わせが、記録に対して効く | Want | 解決 | 高（人間が足すと決めた） | 課題1、課題2 |
| W2 | 単独で分析設計を作る流れの手間が増えない | Want | 費用 | 中（Claude の推測） | [ADR-0005](0005-selective-autonomous-chaining.md) |

- 案A: 分析設計に、対象・粒度・分母の組を任意の項目として足す。まとめて任せる分析設計では必須にする。
- 案B: 足さない。粒度と分母の違いは、対話エージェントがチャットの要約で言う。
- 何もしない（案B と同じ）。

| | 案A | 案B |
|---|---|---|
| M1 | 満たす | 満たす |
| W1 | 効く。印はコードが付け、確認の原則は項目と照らせる | 効かない。印も、変えたかの判断も、文に頼る |
| W2 | 単独の流れでは任意のままで、増えない | 増えない |

- 差がつく基準: W1 だけである。
- 感度: どの重みを動かしても変わらない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | 文で書くので、同じ意味を違う言葉で書いた分析設計にも「違う」の印が付く | 印は読む所を示すだけで、判断は分析者がする |
| 案A | 項目に書いた粒度と、実際の抽出の粒度がずれる | 任せる前の確認で、抽出と並べて読む。機械では照らさない |
| 案B | 粒度の違いに気づかずに任せる | 抑えにくい |

## Decision

案A を採る（人間の判断、2026-11-27）。

1. 分析設計は、データの範囲（`data_scope`）を任意で持てる。データの範囲は、対象（`population`）・粒度（`grain`）・分母（`denominator`）の組で、どれも文で書く。
2. データの範囲を持つときは、3つとも空でない。持たない保存済みの分析設計は、そのまま読める。
3. まとめて任せる分析設計は、データの範囲を持つ。持たない分析設計は、任せる前の確認に進めない。
4. 単独で起動した `/analysis-design` と、論点を1つだけ調べる巡回では、任意のままにする。
5. 分析ノートは、データの範囲を手法の近くに出す。任せる前に読む節は、3つをそれぞれの行に出す。
6. 割合を測らない分析の分母は、分母が無いことを文で書く。

## Consequences

### Positive

- 任せる前に読んだ対象・粒度・分母が、記録に残る。分析ノートで後から読める。
- 違う行の印と、任せた後の確認の原則が、記録に対して効く。

### Negative

- 文で書く項目なので、機械で確かめられるのは「あるか」「同じ文字か」だけである。
- 項目と実際の抽出のずれは、分析者が読んで見つける。
- 単独の流れで作った分析設計は、データの範囲を持たないことがある。それをまとめて任せるには、先に書き足す。

## Alternatives considered

- **`methodology` の自由な項目として書く** — `Methodology` は知らない項目を通すので、形を確かめられない。書き忘れと、名前の揺れを拒めない。

## Related

- Epic: [#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[docs/design/epic-35-hand-over-questions.md](../design/epic-35-hand-over-questions.md)（US-7）
- [ADR-0007](0007-upstream-judgment-gates.md)、[ADR-0014](0014-analysis-design-decision-context.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0063](0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md)、[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md)
