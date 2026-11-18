# ADR-0018: `catalog_io` は、頼まれない限りデータソースの `connection` を返さない

## Status

Accepted

## Context

データソースは `connection` を持つ。中身はファイルのパス、クエリ、ホスト、project id で、認証情報が入ることもある。
`catalog_io get` と `catalog_io list` は保存した YAML をそのまま JSON にして出していた。
`create` と `update` も書いたデータソースを丸ごと返していた。

Epic 12 で `/analysis-report` が catalog を読むようになり、`/report-upload` でレポートを Claude Docs へ送れるようになった。
レポートに載ったものが外へ出る経路ができた。`connection` を載せない決まりは、
`skills/analysis-report/SKILL.md` と `references/apa-template.md` の文と、その文を見る構造テストだけが守っていた。
Epic 12 の Epic PR 前のレビュー（2026-11-17）がこれを指摘し、人間が issue #71 に回した。
#71 のコメントは「`get` が既定で除く変更は、データソース id の出典の決め方と関係が無いので先にやれる。
公開の CLI の振る舞いが変わるので ADR が要る」と書いている。

2026-11-19 に、人間がこの変更を Epic にせず単発の PR で入れると決めた（[ADR-0012](0012-single-pr-scope.md)）。
CLI の既定は変わるが、各 skill の定めた振る舞いは変わらないためである。
`/analysis-notebook` は今までどおり `connection` でデータを読み、`/analysis-report` は今までどおり `connection` を載せない。

比較の前提にした事実と、確かめた方法は次のとおり。

- `catalog_io get` を呼ぶ skill は4つある。`connection` を使うのは `/analysis-notebook` だけで、cell 2 の data load に使う。
  `/analysis-report` は名前・種類・説明だけを使い、`/knowledge-extract` は登録の有無だけを見て、
  `/catalog-register` は登録の確認に使う（`skills/` の SKILL.md と `references/` を `grep` した）。
- `catalog_io list` を呼ぶ skill は無い（同じ `grep`）。
- `get-schema` と `search` はもともと `connection` を返さない（`skills/_shared/catalog_io.py` を読んだ）。
- Python から `load_source` を呼ぶのは `catalog_io.py` の中の `update_source`・`get_schema`・`add_knowledge` だけである。
  `update_source` は読んだ辞書に変更を重ねて書き戻す（同じファイルを読んだ）。

確かめていないこと: plugin の外から `catalog_io get` を呼んで `connection` を読んでいる利用者がいるか。

## Problem

- 課題1: `/analysis-report` が `connection` を書き写すと、分析者のパスやクエリ、認証情報が、配るレポートと Claude Docs に出る。
  今は LLM が文を守ることだけに頼っている。
- 課題2: `/analysis-notebook` は `connection` が無いとデータを読めない。

扱わない範囲: レポートに載せるデータソース id を分析設計のどこから集めるか（#71 に残す）。
集める手順を `catalog_io` のコマンドに移すこと（出典が決まってから）。
skill が `.insight/catalog/sources/` の YAML を直接読む経路。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | `/analysis-notebook` が `connection` を得られる | Must | - | - | 課題2 |
| M2 | 保存したデータソースの `connection` が失われない | Must | - | - | 課題2 |
| W1 | `connection` が要らない呼び出し元の出力に、呼び出し元が何もしなくても `connection` が入らない | Want | 解決 | 高（人間。#71 のコメント） | 課題1 |
| W2 | 書き換える呼び出し元の数と、外の利用者が壊れる範囲 | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | A. データソースを返すコマンドが既定で除き、`--with-connection` で返す | B. `get` は今のまま、`connection` を除く別のコマンドを足す | C. `load_source` が `connection` を除く | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（返す手段が無くなる） | 満たす |
| M2 | 満たす（出力のときだけ除く） | 満たす | 満たさない（`update_source` が `connection` の無い辞書を書き戻す） | 満たす |

| Want | A | B |
|---|---|---|
| W1 | 入らない。オプションを書かない限り出ないので、新しい skill も既定で安全になる | 新しいコマンドを選んだ呼び出し元だけ入らない。`get` を書いた skill には今までどおり入る |
| W2 | `/analysis-notebook` の2行と `/catalog-register` の表の1行を書き換える。外から `get` で `connection` を読む利用者はオプションが要る | `/analysis-report`・`/knowledge-extract`・`/catalog-register` を書き換える。外の利用者は壊れない |

- 差がつく基準: W1 と W2。
- 感度: W2 の重みが高で、外の利用者を壊さないことを優先するなら B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 外から `catalog_io get` で `connection` を読んでいた利用者が、値を得られなくなる | CHANGELOG の Changed に書き、`--with-connection` を案内する |
| A | `--with-connection` を、要らない skill が書く | 構造テストが、`/analysis-notebook` 以外の skill がこのオプションで `get` を呼ばないことと、`/analysis-report` がオプションの名前を出さないことを見る |
| B | 後から足す skill が `get` を書き、`connection` がまた LLM の文脈に入る | なし |
| 何もしない | レポートに `connection` が載って外へ出る | 文と構造テストだけ |

## Decision

A を採る。決め手は W1。

- データソースを丸ごと返すコマンド（`get`・`list`・`create`・`update`）は `connection` を除いて返す。`--with-connection` を付けたときだけ返す。
- `update` を含める理由は、一部だけを変える呼び出しでも、保存してあった `connection` が返るためである。
  PR #83 のコミットへの自動のセキュリティレビュー（2026-11-19）が指摘した。`create` は同じ決まりにそろえた。
- 除くのは CLI が出力するときだけである。保存した YAML と `load_source`・`list_sources` は変えない。
- `--with-connection` を付けて `get` を呼ぶ skill は `/analysis-notebook` だけにする。
- `/analysis-report` の SKILL.md とテンプレートにある「`connection` を載せない」という文は残す。
  コードの守りは文を置き換えるものではなく、文が破られたときの備えである。

## Consequences

### Positive

- `/analysis-report` が読む `catalog_io get` の出力に `connection` が無い。LLM が文を読み飛ばしても、書き写す元が無い。
- 後から足す skill は何も書かなくても `connection` を受け取らない。

### Negative

- 公開の CLI の既定が変わる。外から `connection` を読んでいた呼び出しは `--with-connection` が要る。
- skill が `.insight/catalog/sources/{id}.yaml` を直接読むと、`connection` が見える。
  Epic 12 の実機確認では、`catalog_io` が動かないときに skill が YAML を読んで代えた例がある。この決定はその経路を塞がない。
- `/analysis-notebook` は `connection` を受け取り続ける。notebook に認証情報を書かない決まりは、今までどおり文で守る。

## Alternatives considered

なし。検討した案はすべて Decision Analysis の表に入れた。

## Related

- Issue: #71（データソース id の出典の話は、この issue に残る）
- Epic: [epic-12](../design/epic-12-decision-ready-report.md)（Decision `report-data-source-candidates`）
- 関連: [ADR-0012](0012-single-pr-scope.md)、[ADR-0016](0016-approval-before-external-send.md)
- Supersedes: なし
