# ADR-0023: catalog は認証情報を持たない

## Status

Accepted

## Context

データソースの `connection` は自由な dict で、パス・ホスト・project id・クエリを持つ。
[ADR-0018](0018-catalog-io-omits-connection-by-default.md) は「認証情報が入ることもある」と書き、`connection` を出す先を絞った。
認証情報を入れること自体は止めていない。

#102 の検討で、人間が方針を示した（2026-11-20）。「認証情報などなぜ必要になるの？そんなもの取り扱いたくない。」
このプラグインは認証情報を扱わない、という方針として受け取った。
方針をどこまで構造で守るかを Decision Analysis で示し、人間が選んだ（[epic-17](../design/epic-17-connection-boundary.md)）。

比較の前提にした事実と、確かめた方法は次のとおり。

- 認証情報の決まりは `/catalog-register` の「API keys must come from environment variables. Never hardcode keys in YAML or catalog entries.」という1文だけだった（`skills/` を grep した）。
- `DataSource.connection` は `dict` で、キーを縛らない（`src/insight_blueprint/models/catalog.py` を読んだ）。model は PyPI の wheel に入るので、変えると公開の契約が変わる。
- `create_source` と `update_source` は `catalog_io` の中にあり、どちらも書く前に `DataSource` で検証する。`update_source` は保存済みの値に変更を浅く重ねる（`skills/_shared/catalog_io.py` を読んだ）。
- `/catalog-register` の API の見本は `"auth": "api_key"` を持つ。これは方式の名前で、値ではない（同じ SKILL.md）。
- `/analysis-notebook` は今も「認証情報は環境変数に置き、notebook に書かない」と書いている（その SKILL.md と notebook の契約）。
- 利用者の catalog に認証情報のキーがすでにあるかは確かめていない。

## Problem

- 課題1: 分析者が `connection` に認証情報を書くと、YAML に平文で残り、`get --with-connection` で notebook の文脈に入る。人間はこのプラグインで認証情報を扱いたくない。
- 課題2: 守っているのが文1つで、`catalog_io` は `password` を書いても通す。

扱わない範囲: notebook のセルに認証情報を書かない決まり（文で守る）。`connection` の値をどの skill が読むか（[ADR-0022](0022-connection-reaches-only-the-notebook.md)）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの YAML が読めなくならない | Must | - | - | ADR-0018 の M2 |
| M2 | 環境変数の名前を書く道が残る（`/analysis-notebook` が認証の要るデータソースを読める） | Must | - | - | 課題1 |
| W1 | 認証情報を catalog に入れられないことを、文ではなくコードで守れる | Want | 解決 | 高（人間の発言） | 課題1・2 |
| W2 | 正当な値の誤検知と、利用者が直す手間 | Want | 費用 | 中（Claude の推測。人間が 3B を選んで追認） | 課題1 |

| Must | 3A. 文だけ（`*_env` に環境変数の名前を書く） | 3B. 3A に加え、`create`・`update` がキー名で拒む | 3C. 3B に加え、値の形でも拒む | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす（読み込みは変えない） | 満たす | 満たす |
| M2 | 満たす | 満たす（`*_env` は通す） | 満たす | 満たす |

| Want | 3A | 3B | 3C |
|---|---|---|---|
| W1 | 文だけ。誰かが `password` を書けば notebook まで流れる | 名前の付いた認証情報は書き込み時に止まる。キー名を変えるとすり抜ける | 名前を偽った値も一部止まる |
| W2 | 誤検知は無い | `token_count` のような正当なキーも止まる。`"auth": "api_key"` は値なので通る | table id やハッシュ風の id を誤検知しやすい |

- 差がつく基準: W1 と W2。
- 感度: W2 を低く置けば 3C、W1 を中に下げれば 3A に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 3A | 認証情報が YAML に平文で残り、notebook の文脈に入る | 文だけ |
| 3B | キー名を変えてすり抜ける。正当なキーを誤検知する | `/catalog-register` の文と見本で `*_env` を示す。誤検知はエラーで知らせ、キー名を変えてもらう |
| 3C | 誤検知で登録が止まり、利用者が回避の書き方を覚える | なし |
| 何もしない | 3A と同じ | なし |

## Decision

3B を採る（人間の判断、2026-11-20）。決め手は W1 と W2 の釣り合い。

- `catalog_io` の `create_source` と `update_source` は、`connection` のキー名が認証情報を表すときに `ValueError` を出し、何も書かない。CLI は非ゼロで終わる。
  入れ子の dict と、リストの中の dict も見る。
- キー名は小文字にし、英数字以外を除いてから、`password`・`passwd`・`passphrase`・`secret`・`token`・`bearer`・`apikey`・`credential`・`privatekey`・`accesskey` を含むかで見る（`_CREDENTIAL_KEY_PARTS`）。
- `_env` で終わり、`_env` を除いた部分が認証情報の語を含むキー（`password_env` など）は通す。ただし値は環境変数の名前の形（`^[A-Z_][A-Z0-9_]*$`）に限る。形が合わなければ拒む。
  認証情報と関係の無い `_env` のキー（`conda_env` など）は、ほかのキーと同じに扱い、値を問わない。
  名前の形だけを見ないと、`password_env: "hunter2"` のように秘密そのものが除外をすり抜ける（自動のセキュリティレビュー、2026-11-20）。
  ほかのキーの値は見ない。
- エラーは拒んだキーの場所（`connection.auth.client_secret` など）を挙げ、値を出さない。環境変数の名前を `*_env` に書くよう案内する。
- `update_source` は、変更を重ねたあとの `connection` を見る。保存済みのデータソースに認証情報のキーがあると、`connection` を丸ごと差し替えるまで `update` できない。
- `connection` が dict でなければ、値を出さずに拒む。そのまま `DataSource` の検証に渡すと、pydantic のエラーが値を出す。
- 保存済みのデータソースに認証情報のキーがあると、エラーは「分析者が YAML を手で直す。`--with-connection` で読まず、ファイルも開かない」と案内する。
  `connection` を組み直すために、モデルが秘密ごと読みに行くのを防ぐ（`pstack:thermos` のレビュー、2026-11-20）。
- 読み込み（`load_source`・`list_sources`・`catalog_io get`・`list`）は変えない。model（`DataSource`）も変えない。

## Consequences

### Positive

- `password` や `api_key` を書いたデータソースは登録できない。認証情報は環境変数に置き、catalog には名前だけが残る。
- エラーが値を出さないので、拒んだときに認証情報がモデルの文脈に入らない。

### Negative

- キー名を変えた認証情報（`pw`、`key` など）は通る。値の形は見ない（`*_env` を除く）。
  `auth`・`key`・`pass` は、`"auth": "api_key"` や `passage` のような正当なキーまで拒むので、拒む語に入れていない。
- 大文字・数字・`_` だけでできた秘密は、`*_env` の値として通る。小文字の環境変数の名前は拒む。
- URL や DSN に埋めたパスワード（`postgresql://user:password@host/db`）は通る。値の形を見ないため。判断3で 3C を採らなかった結果で、`/catalog-register` の文で書かないよう頼む。
- 秘密でない正当なキーも拒む。`credentials_path`（鍵ファイルのパス）、`secret_name`（秘密の保管先の参照名）、`token_uri`、`max_tokens` など。
- `token_count` のような正当なキーも拒む。利用者はキー名を変える必要がある。
- 保存済みのデータソースに認証情報のキーがあれば、今までどおり読め、`get --with-connection` で notebook に渡る。この決定は既存の YAML を書き換えない。
- `catalog_io` を通さずに YAML を手で書けば、この検査は効かない。

## Alternatives considered

- **`DataSource` model の検証に入れる** — 読み込みでも検証が走り、保存済みの YAML が読めなくなる（M1）。wheel の公開の契約も変わる。

## Related

- Epic: #102、[epic-17](../design/epic-17-connection-boundary.md)
- Stories: #112
- 関連: [ADR-0018](0018-catalog-io-omits-connection-by-default.md)、[ADR-0022](0022-connection-reaches-only-the-notebook.md)
- Supersedes: なし
