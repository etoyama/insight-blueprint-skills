# ADR-0022: `connection` の値をモデルの文脈に入れるのは `/analysis-notebook` だけにする

## Status

Accepted

## Context

[ADR-0018](0018-catalog-io-omits-connection-by-default.md) は、`catalog_io` のデータソースを返すコマンドが `--with-connection` なしでは `connection` を出さないと決めた。
`--with-connection` を付けて呼ぶ skill は `/analysis-notebook` だけである。
ADR-0018 は、skill がデータソースの YAML を直接読む経路を Negative に挙げ、塞がなかった。

v0.10.0 の実機確認（2026-11-20）で、この経路から `connection` がモデルの文脈に入り、分析設計に書き写された（issue #102、[epic-17](../design/epic-17-connection-boundary.md)）。
`/analysis-framing` が YAML を読み、そのあと `/analysis-design` の Step 2.6 が CSV の絶対パスを `methodology.steps` のコードに書いた。
`/analysis-report` は `design_io get` でそのコードを読むので、パスがレポートの材料に入った。

比較の前提にした事実と、確かめた方法は次のとおり。

- `/analysis-framing` の Step 2b は `.insight/catalog/*.yaml` を Glob して Read するよう書いていた。データソースは `.insight/catalog/sources/` にあるので、この glob は何も拾わない。
  Step 2d は `.insight/` 全体を Grep するよう書いていた（`skills/analysis-framing/SKILL.md` を読んだ）。
- `catalog_io list` は `connection` を除いたデータソースを全部返す。framing が見る名前・`schema_info`・`tags` はすべて入る（`skills/_shared/catalog_io.py` を読んだ）。
- `/catalog-register` を除くと、`catalog/sources` という語を書いた skill の文書は無い（`skills/` を grep した）。
- `/analysis-design` の Step 2.6 の見本は、利用者の環境の project id とライブラリを含む BigQuery のコードだった。
  `get-schema` は `connection` を返さないので、テーブル名やパスは会話の文脈から取っていたことになる（推測）。
- `/analysis-notebook` の cell 2 は、`methodology.steps` に確かめ済みのクエリがあればそのまま使う決まりである（その SKILL.md の Step 3）。
- plugin の hook は Write/Edit に対する `hooks/validate-design.py` の1本だけである（`hooks/hooks.json` を読んだ）。

## Problem

- 課題1: framing が YAML を直接読むと、`connection`（パス・ホスト・project id、認証情報のこともある）がモデルの文脈に入る。
  ADR-0018 のコードの守りを、skill の文が迂回させている。
- 課題2: 分析設計の `methodology.steps` に `connection` の値が入ると、分析設計を読むすべての skill に値が渡る。レポートに載るかどうかは、Method の叙述の書き方しだいになる。

扱わない範囲: notebook のセルに認証情報を書かない決まり（今までどおり文で守る）。catalog に認証情報を入れないこと（[ADR-0023](0023-catalog-holds-no-credentials.md)）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | `/analysis-notebook` がデータを読める | Must | - | - | ADR-0018 の M1 |
| M2 | 保存済みの YAML が読めなくならない | Must | - | - | ADR-0018 の M2 |
| W1 | `connection` が framing・design・report の文脈に入らないことを、文ではなくコードと構造テストで守れる | Want | 解決 | 高（人間。ADR-0018 の W1） | 課題1・2 |
| W2 | 利用者や `/catalog-register` の正当な作業を止めない | Want | 費用 | 中（Claude の推測） | 課題1 |
| W3 | 変える範囲 | Want | 費用 | 低（Claude の推測） | YAGNI |

framing の読み方（課題1）:

| Must | 1A. Step 2b を `catalog_io list` に替え、2d の Grep から `catalog/sources/` を外す。構造テストで見る | 1B. 1A に加えて PreToolUse hook で `catalog/sources/` の読み取りを拒む | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす（`catalog_io` は hook を通らない） | 満たす |
| M2 | 満たす | 満たす | 満たす |

| Want | 1A | 1B |
|---|---|---|
| W1 | skill の文書が YAML を読ませないことは構造テストで見る。モデルが文を読み飛ばして `cat` すると止められない | Read と Grep は止まる。Bash のコマンドからは対象を確実に見分けられず（`cat`・`sed`・`python -c`）、穴が残る |
| W2 | 止めない | 利用者が自分で YAML を開くことと、`/catalog-register` が手で直すことも止まる。plugin の hook は入れた全プロジェクトで動く |
| W3 | framing の SKILL.md と構造テスト | 1A に加えて hook とその判定 |

分析設計の `methodology.steps`（課題2）:

| Must | 2A. データソースを `{source:ID}` で指し、notebook が `get --with-connection` で置き換える | 2B. 今のまま、パスを書いてよい | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たす |
| M2 | 満たす（既存の分析設計は読める。パスを書いたコードもそのまま動く） | 満たす | 満たす |

| Want | 2A | 2B |
|---|---|---|
| W1 | `design_io get` の出力に `connection` の値がもともと無い。構造テストで Step 2.6 と notebook の契約を見る | レポートの SKILL.md とテンプレートの文だけに頼る |
| W2 | `/analysis-auto` の design ③ のビートで、分析者はパスの代わりにデータソースの id を見る | 止めない |
| W3 | design・notebook・auto の SKILL.md と notebook の契約 | なし |

- 差がつく基準: framing では W1 と W2、`methodology.steps` では W1。
- 感度: framing で W1 を W2 より重く置くなら 1B になる。ただ、Bash の穴で 1B も W1 を満たしきれない。`methodology.steps` は、どの重みを動かしても 2A が変わらない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 1A | モデルが文を無視してデータソースの YAML を読む | `list` で framing に要るものが全部手に入るので、直接読む理由が無い。文に理由（`connection` は notebook だけのもの）を書く |
| 1B | hook の誤検知で正当な作業が止まる。Bash で迂回される | なし |
| 2A | notebook が `{source:ID}` を置き換え損ねる。`source_ids` に無い id を書く | 契約に置き換え方を書き、構造テストで見る。`{source:ID}` の id は `source_ids` にあるものに限る |
| 2B | 今回と同じく、パスが分析設計とレポートの材料に入る | 文と構造テストだけ |
| 何もしない | 1B・2B と同じ | なし |

## Decision

1A と 2A を採る（人間の判断、2026-11-20）。決め手は、framing では W2 と 1B に残る Bash の穴、`methodology.steps` では W1。

- `connection` の値がモデルの文脈に入るのは、`/analysis-notebook` が `catalog_io get --with-connection` を呼んだときだけにする。
- `/analysis-framing` はデータソースを `catalog_io list` で読む。Step 2d の Grep は `.insight/designs/`・`.insight/catalog/knowledge/`・`.insight/rules/` に限る。
- `/catalog-register` を除く skill の文書は、`catalog/sources` を書かない。構造テストが見る。
- `/analysis-design` は `methodology.steps` でデータソースを `{source:ID}` と書く（データソースの参照）。パス・ホスト・project id・テーブル名を書かない。`ID` は `source_ids` にある id に限る。
- `/analysis-notebook` の cell 2 は、`{source:ID}` を `get --id ID --with-connection` の `connection` の値で置き換える。
  Python のコード（ファイルのパス、URL）には文字列のリテラルとして入れる。SQL のクエリには、`connection` から組み立てたテーブル名を、その方言の引用符で囲んだ識別子として入れる。
  文字列の値として入れるとクエリが壊れる（`pstack:thermos` のレビュー、2026-11-20）。テーブル名はパラメータにできないので、値は `catalog_io get` からだけ取り、`methodology.steps` からは取らない。

## Consequences

### Positive

- `design_io get` の出力に `connection` の値が無い。`/analysis-report` は書き写す元を持たない。
- 分析設計は、データソースの置き場所が変わっても書き直さずに済む。notebook を作るたびに catalog から引く。

### Negative

- モデルが文を無視してデータソースの YAML を `cat` すると、今までどおり `connection` が見える。この決定は塞がない（1B を採らなかった）。
- v0.11.0 までに作った分析設計の `methodology.steps` にあるパスは残る。分析者が `/analysis-design` で直す。移行はしない。
- notebook の `.py` には `connection` の値がリテラルで入る。notebook を読む `/data-lineage` と、notebook のあとに同じ会話でレポートまで進む `/analysis-auto` では、
  `connection` の値がすでに文脈にある。「`/analysis-report` は書き写す元を持たない」は、レポートを単独で呼んだときにだけ成り立つ。そこではレポートのテンプレートの文が守る。
- `/analysis-auto` の design ③ で、分析者は読み込み先のパスを見なくなる。どのファイルやテーブルかは、データソースの id から `/catalog-register` の登録で分かる。

## Alternatives considered

なし。検討した案はすべて Decision Analysis の表に入れた。

## Related

- Epic: #102、[epic-17](../design/epic-17-connection-boundary.md)
- Stories: #110、#111
- 関連: [ADR-0018](0018-catalog-io-omits-connection-by-default.md)、[ADR-0020](0020-design-declares-sources-in-source-ids.md)、[ADR-0023](0023-catalog-holds-no-credentials.md)
- Supersedes: なし
