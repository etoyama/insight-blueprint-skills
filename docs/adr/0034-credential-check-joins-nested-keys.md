# ADR-0034: 認証情報の判定は、入れ子のキーを親とつないで見て、`authorization` と `sas` を名前全体で拒む

## Status

Accepted

## Context

[ADR-0023](0023-catalog-holds-no-credentials.md) は、`catalog_io` の `create` と `update` が、`connection` のキー名で認証情報を拒むと決めた。
キー名は小文字にして英数字以外を除き、拒む語（`_CREDENTIAL_KEY_PARTS`）を含むかで見る。
#135 を直した PR #150 の `pstack:thermos` レビューで、この判定に穴が3つ残っていると分かった（#149）。

比較の前提にした事実と、確かめた方法は次のとおり。

- `authorization`・`headers.Authorization`・`db_pass`・`consumer_key`・`sas` と、入れ子の `{"api": {"key": …}}`・`{"app": {"id": …}}`・`{"private": {"key": …}}` は、どれも通った（`_credential_keys` に渡して実行した）。
- 入れ子のキーを親のキーとつないで判定する試作では、上の入れ子の3つを拒み、`{"api": {"key_env": "ESTAT_API_KEY"}}` は通った。
  誤検知は `api.keyword`・`map.pid`・`access.key_column` で出た。この3つは、平らな `api_keyword`・`map_pid`・`access_key_column` でも ADR-0023 の判定がすでに拒む。
  `{"s3": {"key": "data/x.csv"}}` は通った（同じ試作を実行した）。
- `authorization` を拒む語に足すと、`authorization_url` や `authorization_endpoint` も拒む。名前全体が一致するときだけ拒めば、この2つは通る。
- `/catalog-register` の SQL の手順は「Ask the user to run the query and paste results, or run it if credentials are available」と書いていた（その SKILL.md を読んだ）。
  API の手順は PR #150 で「Claude は API を呼ばない」に直してある。
- リポジトリの見本の `connection` は3つとも平らである（`skills/` を grep した）。利用者の catalog に入れ子の `connection` があるかは確かめていない。
- 人間の方針（2026-11-21）: データの取得は plugin の範囲外で、分析を行う project の取得スクリプトが担う。plugin は認証情報の値を扱わない。人間はリポジトリをシンプルに保ちたい。

## Problem

- 課題1: `connection` に `authorization: "Bearer …"`・`db_pass`・`consumer_key`・`sas` を書いても通る。値が YAML に平文で残り、`get --with-connection` で notebook の文脈に入る。
- 課題2: 入れ子に分けた `{"api": {"key": …}}` は通り、平らな `api_key` は拒まれる。同じ認証情報が書き方しだいで通る。
- 課題3: SQL の手順が Claude に手元の認証で問い合わせを走らせる道を残している。データの取得を plugin の外に置く方針と食い違う。

扱わない範囲: 値の形の検査（ADR-0023 が 3C として退けた）。URL や DSN に埋めたパスワード。保存済みの YAML の書き換え。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの YAML が読めなくならない | Must | - | - | ADR-0023 の M1 |
| M2 | `*_env` に環境変数の名前を書く道が残る | Must | - | - | ADR-0023 の M2 |
| W1 | 認証情報を catalog に入れられないことを、コードで守れる | Want | 解決 | 高（人間、ADR-0023） | 課題1・2 |
| W2 | データの取得を plugin の外に置く方針と、skill の文が揃う | Want | 解決 | 高（人間の発言、2026-11-21） | 課題3 |
| W3 | 正当なキーの誤検知と、利用者が直す手間 | Want | 費用 | 中（Claude の推測。人間が A を選んで追認） | ADR-0023 の W2 |
| W4 | 判定の仕組みの複雑さ | Want | 費用 | 中（Claude の推測。人間が A を選んで追認） | 人間の発言（シンプルに保ちたい） |

- A: 3つとも直す。拒む語に `consumerkey`・`dbpass` を足し、`authorization`・`sas` は名前全体が一致するときに拒む。入れ子のキーは親とつないで判定する。SQL の手順は分析者に問い合わせを走らせてもらう形だけにする。
- B: 名前と SQL の手順だけを直す。入れ子は ADR-0023 が認めた穴として残す。
- C: SQL の手順だけを直す。拒む語は足さない。
- 何もしない: #149 を閉じる。

| Must | A | B | C | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（読み込みは変えない） | 満たす | 満たす | 満たす |
| M2 | 満たす（入れ子の `*_env` も通す） | 満たす | 満たす | 満たす |

| Want | A | B | C |
|---|---|---|---|
| W1 | `headers.Authorization` と、入れ子に分けたキーが止まる。キー名を変えればすり抜ける | `Authorization` は止まる。`{"api": {"key": …}}` は通る | 今のまま |
| W2 | 揃う | 揃う | 揃う |
| W3 | `api.keyword` のような入れ子の正当なキーが新しく止まる。どれも平らな形ならすでに止まる名前である | 新しく止まるのは `authorization` と `sas` という名前そのものだけ | 無い |
| W4 | 名前全体で比べる集合と、親のキーを持ち回す引数が増える | 名前全体で比べる集合だけが増える | 変わらない |

- 差がつく基準: W1・W3・W4。W2 は3案とも同じ。
- 感度: W4 を高に置けば B に、拒む語を足すこと自体を見合わないと見れば C に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 入れ子の正当なキーが登録で止まる | エラーがキーの場所を挙げる。利用者はキー名を変えるか、`*_env` に環境変数の名前を書く。CHANGELOG に書く |
| B | モデルが `{"api": {"key": …}}` と書くと、認証情報が平文で残る | `/catalog-register` の文だけ |
| C | `Authorization: Bearer …` が平文で残る。API のデータソースで書かれやすい形である | `/catalog-register` の文だけ |
| 何もしない | C と同じ。SQL の手順も方針と食い違ったまま残る | なし |

## Decision

A を採る（人間の判断、2026-11-22）。決め手は W1。ADR-0023 の判定を次のように改める。ここに書かない点は ADR-0023 のままとする。

- 入れ子のキーは親のキーとつないだ名前で判定する。`connection` の直下から順に、小文字にして英数字以外を除いたキー名をつなぐ。
  `{"api": {"key": …}}` は `apikey` として、`{"app": {"id": …}}` は `appid` として拒む。リストの添字はつながない。
  拒む語（`_CREDENTIAL_KEY_PARTS`）については、入れ子にしても平らに書いても判定の結果は同じになる。
- `*_env` の例外もつないだ名前で判定する。`{"api": {"key_env": "ESTAT_API_KEY"}}` は通り、値が環境変数の名前の形でなければ拒む。
- 拒む語に `consumerkey` と `dbpass` を足す。
- `authorization` と `sas` は、キー名そのもの（小文字にして英数字以外を除いたもの）が一致するときに拒む（`_CREDENTIAL_KEY_NAMES`）。
  親のキーとはつながず、含むかどうかでも見ない。`headers.Authorization` は拒み、`authorization_url` と `sas_region` は通す。
- `/catalog-register` の SQL の手順から「or run it if credentials are available」を外す。問い合わせは分析者が走らせ、結果を貼る。Claude は走らせない。
- 単発の PR で直す（[ADR-0012](0012-single-pr-scope.md)）。ADR-0023 の「認証情報を名指すキーを拒む」という決まりに戻す fix と読んだ。
  ADR-0023 が「通る」と書いた `key` の一部を拒むようになるので、判定の変更はこの ADR に残す。

## Consequences

### Positive

- `headers: {Authorization: "Bearer …"}` を書いたデータソースは登録できない。
- 拒む語を含む名前は、入れ子に分けても平らに書いたときと同じ判定になる。`api_key` を `{"api": {"key": …}}` と分けても通らない。
- `/catalog-register` は、API でも SQL でも、Claude にデータソースへ問い合わせさせない。

### Negative

- 入れ子の正当なキーが新しく拒まれる。`api.keyword`、`map.pid`、`access.key_column`、秘密でない `app.id` など。利用者はキー名を変えるか、`*_env` を使う。
- 足した拒む語は、平らなキーにも新しい誤検知を生む。`db_passthrough` や `consumer_keyword` は拒まれる。
- 保存済みのデータソースがこれらのキーを持つと、YAML を手で直すまで `update` できない（ADR-0023 と同じ扱い）。
- 親との間に別のキーが挟まる形（`{"api": {"v2": {"key": …}}}`）は通る。平らな `api_v2_key` が通るのと同じである。
- `proxy_authorization` や `headers_authorization` は通る。`authorization` と `sas` は名前全体でしか比べないので、入れ子の `headers.Authorization` は拒み、平らな `headers_authorization` は通す。この2語では、入れ子と平らで結果が分かれる。
- `authorization` という名前のキーは、値が dict でも丸ごと拒む（`{"authorization": {"url": …}}`）。
- キー名を変えた認証情報（`pw`、`pass`、`account_key` など）、URL や DSN に埋めたパスワード、値の形は、ADR-0023 と同じく見ない。
- SQL のデータソースを登録するとき、分析者が自分で問い合わせを走らせて結果を貼る手間が要る。

## Alternatives considered

- **`authorization` を拒む語に足し、`_url`・`_endpoint` で終わるキーを例外にする** — 例外の一覧が増え続ける。名前全体で比べるほうが規則が1つで済む。
- **キー名を単語に分け、単語の並びで比べる** — `map.pid` のような誤検知は減るが、ADR-0023 の「含むかで見る」判定を全部作り直すことになる。

## Related

- Issue: #149
- PRs: #150（#135・#136 を直した PR。その `pstack:thermos` のレビューが穴を見つけた）
- 関連: [ADR-0023](0023-catalog-holds-no-credentials.md)（判定の一部をこの ADR が改める）、[ADR-0012](0012-single-pr-scope.md)
- Supersedes: なし（ADR-0023 の Decision のうち、入れ子のキーと拒む語の一覧だけを改める）
