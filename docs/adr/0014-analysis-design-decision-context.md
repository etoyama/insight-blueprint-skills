# ADR-0014: 分析設計に、任意の決定の文脈を入れ子の型で持たせる

## Status

Accepted

## Context

[Epic 12](../design/epic-12-decision-ready-report.md) はレポートを「読者がそれだけで判断できる」ものにする。
Story [#64](https://github.com/etoyama/insight-blueprint-skills/issues/64)（US-2）は、
分析設計に「誰が何を決めるための分析か」（決定の文脈）を持たせる。
US-3 のレポートはこれと `next_action` から Recommendation を書く。

分析設計のスキーマは公開契約である。検証ライブラリと pre-write hook が形を確かめ、
`.insight/designs/` の YAML として利用者の手元に残る。全体図にもクラスが1つ増えるので、ADR に残す。

2026-11-15 に、Story #64 の中で人間が形を決めた（issue #64 のコメント）。比較の前提にした事実は次のとおり。

- `AnalysisDesign` は `extra="allow"` で、知らないキーをそのまま通す
  （`src/insight_blueprint/models/design.py` を読んだ）。スキーマを変えなくても、YAML に項目を書くことはできる。
- 入れ子の型の先例は `Methodology` である。任意（`Methodology | None`）で、あるときは `method` が空でないことを
  `Field(min_length=1)` で確かめる（同じファイル）。
- `design_io create` は受け取るキーを引数として列挙している。足した項目は引数にも足さないと、skill から書けない
  （`skills/_shared/design_io.py` の `create_design` を読んだ）。
- review コメントが指せる節は `ALLOWED_TARGET_SECTIONS` が決める。ここに無い節を指す review batch は記録できない
  （同じファイルの `append_review_batch` を読んだ）。
- US-2 の AC は、決定の文脈が任意であること（AC 2）と、持たない既存の分析設計が今のまま検証を通ること（AC 4）を求める。
  「誰が」と「何を」の両方がそろうことは、AC には書かれていない。

## Problem

- 課題1: レポートの読者が、推奨が誰のどの判断に答えるものかを読めない。分析設計に書く場所がなく、
  分析者の頭の中にしかない。放置すると、Recommendation は宛先のない一般論になる。
- 課題2: 「誰が」と「何を」の片方だけが書かれると、Recommendation が宛先か問いのどちらかを欠く。
  欠けた側をレポートが推測で補うか、半端な文を出すことになる。

扱わない範囲: `decision_maker` に役職・個人名・部署のどれを書くかを型で決めること。決定の期限や選択肢の列挙。
レポートへの載せ方（US-3）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 検証ライブラリが決定の文脈の形を確かめる | Must | - | - | US-2 AC 1 |
| M2 | 決定の文脈を持たない既存の分析設計が、今のまま検証を通る | Must | - | - | US-2 AC 4 |
| W1 | 片方だけ書かれた状態を作れない | Want | 解決 | 高（人間） | 課題2 |
| W2 | スキーマ・図・文書の変更の量 | Want | 費用 | 低（Claude の推測） | YAGNI |
| W3 | 既存のモデルの流儀にそろう | Want | 費用 | 低（Claude の推測） | `Methodology` の先例 |

案は次の4つ。

- A. 入れ子の型: `decision_context: DecisionContext | None`。`DecisionContext` は `decision_maker` と `decision` を持ち、どちらも空にできない。
- B. 平らな2項目: `decision_maker: str | None` と `decision: str | None` を `AnalysisDesign` に直接足す。
- C. 文字列1つ: `decision_context: str | None` に「誰が何を決めるか」を1文で書く。
- 何もしない: スキーマを変えず、`extra="allow"` が通すキーに任せる。

| Must | A. 入れ子の型 | B. 平らな2項目 | C. 文字列1つ | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす（文字列であることだけ） | 満たさない（検証が何も確かめない） |
| M2 | 満たす | 満たす | 満たす | 満たす |

| Want | A. 入れ子の型 | B. 平らな2項目 | C. 文字列1つ |
|---|---|---|---|
| W1 | 「無い」か「両方ある」の2通りだけになる。片方だけの分析設計は検証で落ちる | 片方だけ書ける。防ぐには、2項目をまたぐ validator を別に書くことになる | 1文の中で「誰が」が抜けても通る。機械では見分けられない |
| W2 | クラスが1つ増え、全体図・用語・skill の表に1行ずつ足す | クラスは増えないが、項目は2つ増える | 項目が1つ増えるだけで、最も少ない |
| W3 | `Methodology` と同じ形（任意の入れ子、必須の項目は `min_length=1`） | 平らな任意の項目は `parent_id` などにある | 同左 |

- 差がつく基準: W1 は A だけが満たす。W2 は C が勝つ。W3 はほぼ差がない。
- 感度: W2 の重みが高なら C に変わる。W1 が中以上なら A のまま。W1 の重みは人間が高と決めた。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 分析者が片方しか答えられず、検証で落ちて手が止まる | `/analysis-design` は片方だけなら1度聞き直し、それでも無ければ項目ごと省く |
| B | 「何を」だけの分析設計ができ、宛先のない Recommendation が出る | validator を足す。足すと A と同じ保証を、型でなくコードで持つことになる |
| C | 「誰が」の抜けた1文がそのまま Introduction と Recommendation に載る | review で人が見つけるしかない |
| 何もしない | キーの綴りを間違えても誰にも知らされず、レポートが決定の文脈を読めない | 抑えられない |

## Decision

A を採る。決め手は W1。

```python
class DecisionContext(BaseModel):
    decision_maker: str = Field(min_length=1)  # 誰が
    decision: str = Field(min_length=1)        # 何を決めるか

class AnalysisDesign(BaseModel):
    ...
    decision_context: DecisionContext | None = None
```

- 決定の文脈は任意である。持たない分析設計は今のまま検証を通る。
- あるときは、`decision_maker` と `decision` の両方が空でない。片方だけの分析設計は検証で落ち、書き込まれない。
- `DecisionContext` は、同じファイルのほかのモデルと同じく `extra="allow"` にする。
  手で足したキーを、読み書きのたびに黙って落とさないためである。
- `design_io create` は `decision_context` を受け取る。後から足すときは `design_io update` を使う。
- review コメントは `decision_context` を節として指せる（`ALLOWED_TARGET_SECTIONS` に足す）。
  `/analysis-review` が見つけた食い違いを、`/analysis-revision` が節ごとに追えるようにするためである。
- `/analysis-design` は、仮説と仮説の背景が決まった直後に1度だけ聞く。分析者は答えずに進められ、そのときは項目ごと省く。
  空文字や「未定」のような仮の値は書かない。
- `decision_maker` には、個人名ではなく役職かチームを書くよう `/analysis-design` が案内する。
  レポートは読者に渡るもので、役職は人が替わっても意味が残るからである。型では縛らない。
- guided autopilot は design のビート①（仮説）で決定の文脈も確認する。KEEP ゲートは増やさない。
- `/analysis-review` は、決定の文脈があるときだけ仮説と噛み合うかを見る。無いことは指摘しない。

## Consequences

### Positive

- レポート（US-3）は、決定の文脈があれば宛先と問いの両方を必ず読める。欠けた側を推測で補わずに済む。
- 既存の分析設計は何も変えずに通る。
- 形は検証ライブラリ1か所で確かめる。hook と `design_io` のどちらから書いても同じ結果になる。

### Negative

- AC にない保証（`min_length=1` と、両方がそろうこと）を1つ足している。今の AC は文字列1つ（案 C）でも満たせるので、
  YAGNI との緊張がある。課題2を型で防ぐことを優先した。
- `decision_maker` に役職・個人名・部署のどれが書かれるかは、型では決まらない。`/analysis-design` の聞き方に頼る。
- `min_length=1` は空白だけの文字列を通す。中身が意味を持つかどうかは、`/analysis-review` で人が見る。
- 片方しか答えられない分析者は、決定の文脈を書けない。「何を決めるか」だけを残す場所はない。
- 全体図にクラスが1つ増え、`design_io create` の引数と review コメントが指せる節も1つずつ増える。

## Alternatives considered

- **`next_action` の中に入れる** — `next_action` は検証の後の分岐（支持されたら・棄却されたら）で、
  型のない `dict` である。決定の文脈は検証の前から決まっているもので、意味が違う。形も確かめられない。
- **必須にする** — 決定の文脈を持たない既存の分析設計が検証で落ち、US-2 AC 4 を満たさない。
  探索的な分析では、決める人がまだいないこともある。

## Related

- Epic: [epic-12](../design/epic-12-decision-ready-report.md)（Story #64）
- 関連: [ADR-0013](0013-verdict-metric-optional-items.md)（同じ Epic で公開契約に任意の項目を足した前例）、
  [ADR-0011](0011-domain-model-overview-in-architecture.md)（モデルを変えた PR で全体図を更新する決まり）、
  [ADR-0007](0007-upstream-judgment-gates.md)（design のビート）
- Supersedes: なし
