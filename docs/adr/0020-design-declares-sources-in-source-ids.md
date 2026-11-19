# ADR-0020: 分析設計が使うデータソースは `source_ids` に宣言し、下流の skill はそこだけを読む

## Status

Accepted

## Context

分析設計には、データソースの id を置ける場所が2つある。`AnalysisDesign.source_ids` と、指標と説明変数の `data_source` である。
`source_ids` を書く skill は無い。`data_source` は型の無い値で、指標では辞書、説明変数では文字列であり、id でない文字列も入る。
`/analysis-report`・`/analysis-notebook`・`/premortem`・`/analysis-auto` の4つは分析設計が宣言したデータソースを前提にしているが、どの項目から読むかを書いた skill は無かった。
Epic 12 の Story #65 は `/analysis-report` に両方を読ませて回避した（[epic-12](../design/epic-12-decision-ready-report.md) の Decision `report-data-source-candidates`）。
issue #71 がこれを扱い、2026-11-20 に人間が Epic にすると決めた（判断13、[epic-15](../design/epic-15-declared-source-ids.md)）。

比較の前提にした事実は次のとおり。

- `source_ids` が出てくるのは `src/insight_blueprint/models/design.py`、`skills/_shared/design_io.py` の `create_design`、
  `/analysis-report` の SKILL.md とテンプレートだけだった（`git grep source_ids` で確かめた）。
- `/analysis-design` の Step 2.6 は、`data_source` が登録済みのデータソースを指すときにコードの型を作っていた。`data_source` を id として読む箇所はここにもあった。
- PyPI の wheel は `src/insight_blueprint` を含む（`pyproject.toml` の `packages`）。model の形を変えると、公開の契約が変わる。
  `skills/_shared/` の `catalog_io` と `design_io` は wheel に入らず、plugin の `bin/` から呼ぶ。
- `AnalysisDesign` は `extra="allow"` で、宣言に無いキーも検証を通る（同じファイル）。
- `catalog_io get` は、未登録の id で `{}` を返し、終了コードは 0 である（issue #71 のコメント、2026-11-20 に合成データで確かめた）。
  `/analysis-notebook` はこの返り方で未登録を見分けている（その SKILL.md の Step 2）。
- 利用者の手元に `source_ids` が空の分析設計がいくつあるかは確かめていない。v0.10.0 までの skill で作った分析設計は、すべて空のはずである（推測）。

## Problem

- 課題1: 分析設計が使うデータソースを宣言する場所が無い。下流の skill がそれぞれ別の回避を書き、同じデータソースを読む保証が無い。
- 課題2: `/analysis-report` が候補を集める手順は入力で出力が決まる処理なのに、LLM 向けの文で書いてあり、unit test が無い。
- 課題3: Method でのデータソースの書き方が決まっていない。指標の `data_source: {}` と説明変数の `data_source: ""` の扱いでモデルが迷った。

扱わない範囲: `catalog_io get` の `connection`（[ADR-0018](0018-catalog-io-omits-connection-by-default.md)）。`source_ids` と `data_source` の食い違いを機械で見つけること。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 既存の分析設計の YAML が、手直しせずに検証を通る | Must | - | - | 利用者の `.insight/`、ADR-0014 の M2 |
| W1 | 下流の4つの skill が読む場所が1つになる | Want | 解決 | 高（Claude の推測。人間が A を選んで追認） | 課題1、issue #71 |
| W2 | 集める手順をコマンドにして unit test で確かめられる | Want | 解決 | 中（Claude の推測） | 課題2 |
| W3 | Method のデータソースの書き方を決まりにできる | Want | 解決 | 中（Claude の推測） | 課題3 |
| W4 | 公開の契約（wheel の model）と既存データへの影響 | Want | 費用 | 高（Claude の推測。人間が A を選んで追認） | `pyproject.toml`、M1 |

案は次の3つ。

- A. `/analysis-design` が `source_ids` を書く。下流はすべて `source_ids` を読む。`data_source` はメモとして残し、id としては読まない。
- B. `source_ids` をやめ、`data_source` を source id を指す型のある項目にする。下流はその和集合を読む。
- C. 両方を読む今の決まりを文書で固定し、集める手順だけをコマンドに移す。

| Must | A | B | C | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（スキーマは変わらない） | 移行用の validator があれば満たす。ただし id でない文字列は id に直せず、落とすか退避するしかない | 満たす | 満たす |

| Want | A | B | C |
|---|---|---|---|
| W1 | 4つの skill が `source_ids` だけを読む。`source_ids` が空の既存の分析設計では、データソースの表が出なくなる | 和集合は導けるので1か所になり、指標と宣言の食い違いも起きない | 2か所のまま。notebook と premortem にも同じ回避を書き足す |
| W2 | 入力は `source_ids` だけで、コマンドは小さい | 型のある項目の和集合で、小さい | 自由な文字列の検査まで入って大きい |
| W3 | `### Data` の表は `source_ids` から作り、指標の表にはデータソースの列を置かない | 指標ごとの列にデータソースの名前を出せる | 今の形のまま、`{}` と `""` の扱いを文で足す |
| W4 | model は変わらない。skill の振る舞いだけが変わる | `Metric.data_source` の型が変わり、`source_ids` が消える。wheel の利用者には破壊的な変更 | 変わらない |

- 差がつく基準: W1 と W4。W2 と W3 は C だけが劣り、A と B の差は小さい。
- 感度: W4 の重みが低なら（wheel を直接使う人がいない、既存の分析設計を捨ててよい）、B が A を上回る。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | `source_ids` と `data_source` が食い違う（指標が宣言に無いデータソースのメモを持つ） | `/analysis-design` が先にデータソースを聞き、`data_source` はその中のどこかを書くメモだと説明する |
| B | 利用者の自由な文字列が移行で消えるか、検証で落ちる。wheel の利用者のコードが動かなくなる | 移行用の validator と退避用の項目を置き、破壊的な変更として CHANGELOG に書く |
| C | 次に足す skill も両方を読む回避を書く | 抑えられない |
| 何もしない | 課題1〜3がすべて残る | なし |

`source_ids` が空の既存の分析設計の扱いは、次の2つを比べた。

- A1. 読まない。データソースの表は省き、`design_io update` で足せることを分析者に伝える。
- A2. `source_ids` が空のときだけ、コマンドが旧形式として `data_source` の値も候補に入れる。読む場所は2つ残る。

A2 は W1 を自分で崩す。A1 は既存の分析設計のレポートから表が消えるが、分析者に知らせ、1回の `design_io update` で戻せる。

## Decision

A を採り、既存の分析設計は A1 で扱う。決め手は W1 と W4。2026-11-20 に人間が選んだ。

- 分析設計が使うデータソースは `source_ids` に宣言する。宣言する場所はここだけである。
  `/analysis-design` は指標と説明変数より先に使うデータソースを聞き、`catalog_io get --id` で登録を確かめた id だけを書く。
- 指標と説明変数の `data_source` は、宣言したデータソースのどこから値を取るかを書くメモである。どの skill も id として読まない。
- `/analysis-report`・`/analysis-notebook`・`/premortem`・`/analysis-auto` は、データソースを `source_ids` からだけ読む。
- レポートに載せるデータソースは `catalog_io describe --ids a,b` が返す。登録済みのデータソースの `id`・`name`・`type`・`description` を、
  渡した順に重複なく `sources` に入れる。未登録の id と id の形でない値は `missing` に入れる。`connection` は返さない。
  `catalog_io` は分析設計を読まない。`source_ids` を渡すのは呼ぶ skill の役目である。
- `catalog_io get` は変えない。未登録の id には `{}` を返し、終了コードは 0 のままである。
- model は変えない。`source_ids` は `list[str]` のまま、`data_source` は今の型のままである。
- `source_ids` が空の分析設計からは、どの skill もデータソースを拾わない。

## Consequences

### Positive

- 下流の skill は同じデータソースを読む。新しい skill も `source_ids` を読めばよい。
- レポートのデータソースの集め方はコードになり、unit test で確かめられる。
- wheel の契約と既存の YAML の形は変わらない。

### Negative

- v0.10.0 までに作った分析設計は `source_ids` が空で、レポートからデータソースの表が消え、premortem は `HARD_BLOCK` を返し、notebook は止まる。分析者が `/analysis-design`（`design_io update`）で足す。
- `source_ids` と `data_source` の食い違いは型で防げず、`/analysis-design` の聞き方に頼る。
- `source_ids` の各要素が id の形かどうかは model が確かめない。`/analysis-design` は確かめた id だけを書くが、手で書いた値は `catalog_io describe` が `missing` として返すまで分からない。

## Alternatives considered

- **`design_io` にデータソースを集めるコマンドを置く** — `design_io` が catalog を読むことになり、分析設計と catalog の境界が崩れる。
  `catalog_io` に id を渡す形なら、`/premortem` など分析設計を持たない呼び手も使える。
- **未登録の id で `catalog_io get` を失敗させる** — `/analysis-notebook` が `{}` で未登録を見分けているので、公開の CLI の振る舞いが変わる。`describe` の `missing` で足りる。

## Related

- Epic: [epic-15](../design/epic-15-declared-source-ids.md)（#71。Story #97・#98・#99）
- 関連: [ADR-0018](0018-catalog-io-omits-connection-by-default.md)（`connection` を返さない）、
  [ADR-0014](0014-analysis-design-decision-context.md)（既存の分析設計が検証を通ることを Must にした先例）、
  [epic-12](../design/epic-12-decision-ready-report.md) の Decision `report-data-source-candidates`（この ADR が置き換える回避）
- Supersedes: なし
