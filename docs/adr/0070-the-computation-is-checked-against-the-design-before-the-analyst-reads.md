# ADR-0070: 計算の点検を、分析者が読む前に済ませる

## Status

Proposed

## Context

Epic 36（[#302](https://github.com/etoyama/insight-blueprint-skills/issues/302)、[DesignDoc](../design/epic-36-before-the-analyst-answers.md)）の初版で決めた。
Epic 35 の実データで使う段で、分析者は「notebook が設計どおりに計算したかは、分析ノートを読み始める前に終わっていてほしい」と言った
（[#297](https://github.com/etoyama/insight-blueprint-skills/issues/297)）。
[ADR-0066](0066-a-design-may-state-its-population-grain-and-denominator.md) は、分析設計が対象・粒度・分母を持てると決め、
notebook の出力と照らすことは扱わない範囲に置いた。この ADR がそこを決める。

比較の土台にした事実（v0.22.0 を読み、実データのテーマの記録を読むだけにして試した。値は書かない）。

- 結果のレビュー（`skills/analysis-review/SKILL.md` の Step 3b）の観点は、判定の線、値と判定、図、guardrail、cell の5つである。
  対象・粒度・分母・抽出が計算と合うかは、どの skill も見ていない。#297 の本文は「レビューの観点の1つ」と書いているが、違う。
- 実行エージェントの数の照合は、データの中で足し合わせて合うかを見るだけで、分析設計と合うかは見ない。
- 分析設計の指標（`Metric`）は id も名前も持たない。verdict の `metrics` は、notebook が付けた名前の dict である。
  それでも、3つの分析設計の指標11本のうち10本は、verdict に `target` と同じ名前で入っていた。契約には無い。
- 名前を照らすだけで、設計に無い verdict の指標が、1つの分析設計で4本、別の1つで1本見つかった。後者は図が2枚で、分析設計の図の仕様は1枚だった。
- `data_scope`（対象・粒度・分母）は自由な文である。コードでは notebook と照らせない。
- 1つの分析設計と notebook（210 行）を読むと、約3分で、対象・粒度・分母が計算と合うことと、設計に無い比べ先の行が1つあることが分かった。
- 単独の経路も、まとめて任せる流れの終え方の問いも、`/analysis-reflection` の Step 2 を通る。
- 論点ツリーと分析設計を書くのは対話エージェントだけである（[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)）。
- 確かめていないこと: 点検エージェントがどのくらい見落とすか。

## Problem

- 課題1: notebook が分析設計どおりに計算したかを、誰も確かめていない。分析者が読んで答えた後に、計算の誤りが見つかりうる。
- 課題2: 実行エージェントが分析設計に無い指標や比べ先を足しても、分析者は読むまで気づけない。
- 課題3: 単独の経路（`/analysis-notebook` → `/analysis-reflection`）でも、同じことが起きる。

扱わない範囲: 食い違いが出たときに分析者に何を聞くか（[ADR-0071](0071-a-difference-is-shown-before-reading-and-the-review-of-a-result-is-narrowed.md)）。
点検エージェントが数を計算し直すこと。

## Decision Analysis

決めることは3つある。誰が何と照らすか（判断1）、結果をどこに置くか（判断2）、どこで済ませたと保証するか（判断3）である。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析者に聞かずに終わる | Must | - | - | #297、原則（AUTO は KEEP ゲートより前） |
| M2 | 対象・粒度・分母・抽出が計算と合うかを見られる | Must | - | - | 課題1 |
| M3 | 終え方を聞く前に、いまの verdict への点検が済んでいる | Must | - | - | 課題1、課題3 |
| W1 | 見落としにくい | Want | 解決 | 高（Claude の推測、人間が推奨を採った） | 課題1、課題2 |
| W2 | 対話エージェントの文脈と、待ち時間 | Want | 費用 | 中（Claude の推測） | Epic 35 |
| W3 | 契約と型を変える広さ | Want | 費用 | 中（Claude の推測） | YAGNI |

判断1 の案。

- 案1A: コードだけ。指標と図の対応を照らす。
- 案1B: 点検エージェント。分析設計ごとに1つ立て、分析設計・notebook・verdict を読ませる。
- 案1C: 対話エージェントが自分で読む。
- 案1D: コードと点検エージェント。コードが形（指標・図・cell の並び）を見て、点検エージェントが意味（対象・粒度・分母・抽出・比べ先・判定の基準）を読む。
- 何もしない。

判断2 の案。

- 案2A: 分析設計ごとの新しい記録（`{design_id}_check.yaml`）。`design_io` の命令だけが書く。
- 案2B: review batch として書く。
- 案2C: journal の出来事として書く。

判断3 の案。

- 案3A: `/analysis-reflection` の Step 2。読むものを出す前に、いまの verdict への点検が無ければ走らせる。
  まとめて任せる流れと `/analysis-notebook` は、先に走らせて待ちを減らす。
- 案3B: `/analysis-auto` のまとめて任せる流れだけ。
- 案3C: `/analysis-notebook` が verdict を記録した後だけ。

| Must | 案1A | 案1B | 案1C | 案1D |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |
| M2 | 満たさない（`data_scope` は自由な文） | 満たす | 満たす | 満たす |

| Must | 案3A | 案3B | 案3C |
|---|---|---|---|
| M3 | 満たす | 満たさない（単独の経路を通らない） | 満たさない（手で走らせ直した notebook を取りこぼす） |

| Want | 案1B | 案1C | 案1D |
|---|---|---|---|
| W1 | notebook を書いていない目が読む。数の数え落としはありうる | 何本も読むと見落としやすい | 形はコードが必ず拾い、意味は別の目が読む |
| W2 | 対話エージェントの文脈に入るのは結果だけ。並行で走る | notebook 200 行 × 本数が文脈に入る | 案1B と同じ |
| W3 | 契約は変えない | 変えない | notebook の契約に1行足す。保存済みの verdict は壊れない |

| Want | 案2A | 案2B | 案2C |
|---|---|---|---|
| W3 | 型と命令と hook の守りを1つずつ足す | 型は足さない。review batch は状態の遷移を1回起こす契約で、点検は状態を変えたくない | 型は足さない。journal は答えが引用する記録で、分析の結果でないものが混ざる。分析の段階の規則も、結果と点検を見分ける必要が出る |

- 差がつく基準: 判断1 は W1 と W2。判断2 は W3 の中身（何とぶつかるか）。判断3 は M3 で決まる。
- 感度: W3 を高く見るなら、判断1 は案1B になる。形の食い違いを数え落とす危険を受け入れることになる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案1B | 設計に無い指標を数え落とす | 無い |
| 案1C | 対話エージェントの文脈が埋まり、後の問いの質が落ちる | 無い |
| 案1D | 名前を変えただけの指標が、食い違いと出る | 契約に「設計の指標は `target` の名前で書く」と足す。古い verdict では、点検エージェントが中身を読んで注を書く |
| 案1D | 点検エージェントが食い違いを見落とす、または無い食い違いを挙げる | 食い違いには根拠の cell を持たせ、分析者が分析ノートでそこを開ける。見落としは実データで使う段で数える |
| 案2A | 記録が1種類増える | 読むのは分析ノートと skill の2か所に限る |
| 案3A | 単独の経路で、点検エージェントを立てられないホストがある | 同じセッションが読み、誰が点検したかを記録に残す |
| 何もしない | 読んで答えた後に、計算の誤りが見つかる | 無い |

## Decision

案1D・案2A・案3A を採る（人間の判断、2026-11-28）。決め手は、判断1 が W1 と W2、判断2 が既存の契約とぶつからないこと、判断3 が M3 である。

1. **計算の点検**を足す。分析設計ごとに、notebook が分析設計どおりに計算したかを確かめ、項目ごとに、
   合っている・食い違う・確かめられないのどれかを記録する。分析者には何も聞かない（AUTO）。データには触らない。
2. 項目は、対象・粒度・分母・抽出・指標・比べ先・図・判定の基準・cell の並びである。判定の基準は、検証の分析設計だけが持つ。
3. 指標・図・cell の並びは、コードが見る。次を食い違いに挙げる。
   - 設計の指標が verdict に同じ名前で無い。
   - verdict の指標が設計に無い。
   - verdict の図の数が、分析設計の図の仕様の数と違う。
   - notebook の cell が、契約の7つの並びと違う。
4. notebook の契約に足す: 分析設計の指標は、その `target` を名前にして verdict の `metrics` に書く。設計に無い指標を足すことは、
   比べ先を足すことと同じく、データに触る前に分析者への確認を書いて戻る条件に当たる（[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md)）。
5. 対象・粒度・分母・抽出・比べ先・判定の基準は、**点検エージェント**が読む。点検エージェントは、その notebook を書いていない、
   同じセッションの中の Claude で、分析設計・notebook・verdict を読み比べ、項目ごとの結果を返す。何も書かない。
   食い違いには、何が違うかの文と、根拠にした cell を添える。
6. 点検の記録は分析設計ごとに1つ持つ（`.insight/designs/{design_id}_check.yaml`）。`design_io check` だけが書く。
   手で書くことは検証 hook が止める。まとめて任せた実行では、対話エージェントだけがこの命令を呼ぶ。
   コードが見る項目は、命令がその場で照らして書く。点検エージェントの返事では上書きできない。
7. 点検の記録は点検した verdict を覚える。いまの verdict と違えば、点検は済んでいないと読む。点検し直すと、前の点検を置き換える。
8. `/analysis-reflection` は、読むものを出す前に、いまの verdict への点検が済んでいることを確かめ、無ければ走らせる。
   まとめて任せる流れは、実行エージェントが戻るたびに、その分析の点検を始める。`/analysis-notebook` は、verdict を journal に記録した後に走らせる。
9. 点検エージェントを立てられないホストでは、同じセッションが読む。誰が点検したか（点検エージェントか、同じセッションか）を記録に持つ。
10. 分析の状態も、分析の段階も変えない。点検が済んだかは、点検の記録と verdict から導く。

## Consequences

### Positive

- 分析者が分析ノートを読む時点で、計算が分析設計どおりかの点検が済んでいる。食い違いは根拠の cell と一緒に読める。
- 設計に無い指標と図は、モデルの注意に頼らず、コードが拾う。
- 守る所が `/analysis-reflection` の Step 2 の1か所で、単独の経路とまとめて任せる流れの両方に効く。

### Negative

- 意味の点検はモデルの読みで、見落としと誤りがありうる。塞がない。根拠の cell を見せて、分析者が確かめられるようにするだけである。
- 単独の経路（`/analysis-notebook`）に、分析者に聞かない段が1つ増える。Epic 35 は単独の流れを触らない所に置いたが、
  点検は別の skill へ進む自律ではなく、同じ skill の中の確認なので、[ADR-0005](0005-selective-autonomous-chaining.md) には反しない。
- 同じセッションが点検した結果は、書いた本人の読みである。記録にそう残るが、独立した目ではない。
- この ADR より前に書かれた verdict は、指標の名前が `target` と違うことがある。その分析設計では、指標の項目が食い違いと出る。
  終えた分析設計は点検しないので、効くのは、終える前の分析設計だけである。
- 点検の記録を読む所（分析ノート、skill）が増える。

## Alternatives considered

- **分析設計の指標に id を足し、verdict に写させる** — `target` の名前で結べると分かった。項目を足すと、保存済みの分析設計との読み分けが要る。
- **実行エージェントに、自分で点検させる** — 書いた本人の読みで、分析設計に無いものを足した本人でもある。課題2 を解かない。
- **点検エージェントに、点検の記録を書かせる** — 共有の記録を書くのは対話エージェントだけ、という ADR-0062 の分担を崩す。

## Related

- Epic: [#302](https://github.com/etoyama/insight-blueprint-skills/issues/302)、[docs/design/epic-36-before-the-analyst-answers.md](../design/epic-36-before-the-analyst-answers.md)
- Issue: [#297](https://github.com/etoyama/insight-blueprint-skills/issues/297)
- 関係する ADR: [ADR-0005](0005-selective-autonomous-chaining.md)、[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)、[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md)、[ADR-0066](0066-a-design-may-state-its-population-grain-and-denominator.md)、[ADR-0071](0071-a-difference-is-shown-before-reading-and-the-review-of-a-result-is-narrowed.md)
