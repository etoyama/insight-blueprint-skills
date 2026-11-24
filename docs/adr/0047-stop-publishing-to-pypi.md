# ADR-0047: `insight-blueprint-lineage` を PyPI に公開するのをやめ、`/data-lineage` を plugin の env で走らせる

## Status

Accepted

## Context

plugin は `uv run --project "${CLAUDE_PLUGIN_ROOT}"` で、手元のソースから env を作る。core の skill は PyPI を使わない（[ADR-0006](0006-plugin-execution-model.md)）。
それとは別に、同じソースを `insight-blueprint-lineage` という名前で PyPI に出してきた。
タグの push で `.github/workflows/publish.yml` が wheel を組み、trusted publisher で上げる（[docs/RELEASE.md](../RELEASE.md)）。

人間は 2026-11-23 に、PyPI の公開がまだ要るかを Decision Analysis で比べた。そして「plugin の外で `insight-blueprint-lineage` を `uv add` して使う分析者はいない」と答え、公開をやめると決めた（Epic 30 の PM セッションで直接。[#207](https://github.com/etoyama/insight-blueprint-skills/issues/207)）。
この ADR はやめ方と、やめた後に何が契約でなくなるかを決める。

比較の前提にした事実と、確かめた方法は次のとおり（`main` の 7cdf83a、2026-11-25）。

- PyPI を使う道は2つだけである。
  - `skills/data-lineage/SKILL.md` の Step 0。利用者のプロジェクトの Python で `insight_blueprint.lineage` の import を試し、無ければ `uv add insight-blueprint-lineage` を勧める。
  - README の「Optional: Python package」の節と、Analysis Workflow の `uv add "insight-blueprint-lineage[notebook]"`。
  - `grep` で repo 全体を探して確かめた。凍結した DesignDoc と ADR、`.claude/docs/research/` は数えていない。
- 利用者のプロジェクトの env と plugin の env では、互いのパッケージが見えない。scratchpad で `uv init` し、`uv add tabulate` したプロジェクトで試した。
  - そのプロジェクトの env では `import insight_blueprint` が `ModuleNotFoundError` になる。
  - 同じ cwd から `uv run --project <plugin> --extra notebook` で走らせると、`insight_blueprint.lineage` は import できる。`tabulate` は import できない。`--with tabulate` を付けると import できる。
- `/analysis-notebook` が作る notebook（以下、契約の notebook）は必ず `tracked_pipe` を使う。`lineage` の cell が `.insight/lineage/{id}.mmd` を書く（`skills/analysis-notebook/references/notebook-contract.md`）。
- `.mmd` には各 step の行数と増減が載る（`src/insight_blueprint/lineage/exporter.py`）。step の記録はファイルに残らない。
- PyPI に wheel を出しているので、model の形が公開の契約として扱われてきた。[ADR-0020](0020-design-declares-sources-in-source-ids.md) の Context は「model の形を変えると、公開の契約が変わる」と書き、W4 の重みを「高」にした。[ADR-0023](0023-catalog-holds-no-credentials.md) も同じ理由で model の検証を避けた。
- PyPI に出すためだけの道具がある。`publish.yml`、`ci.yml` の `build-check` job（`uv build`、`scripts/verify_wheel.py`、`twine check`）、poe の `verify-wheel` と `release-dry-run`、`tests/test_packaging.py`、`tests/test_verify_wheel.py`。
- タグの名前と、タグの commit の `pyproject.toml` の版を照らしているのは、`publish.yml` の最初の step（`scripts/check_tag_version.py`）だけである。`tests/test_plugin_structure.py` は3つの版の一致（`pyproject.toml`・`plugin.json`・`marketplace.json` の `ref`）を見るが、タグは見ない。
- GitHub の ruleset は2つある（`gh api repos/etoyama/insight-blueprint-skills/rulesets/<id>` で読んだ）。
  - `protect-main` は `python`・`plugin-validate`・`build-check` の3つを、`main` に入れる PR の必須のチェックにしている。
  - `protect-release-tags` は `v*` のタグを消すことと動かすことを止めている。
- PyPI の archive は project を消さず、install も止めない。止まるのは新しい upload で、project のページに通知が出る。owner は戻せる。PyPI は archive の前に、説明を書き直した最後の版を出すよう勧めている（PyPI の公式ブログ、2025-01-30。docs.pypi.org の該当ページは 404 だった）。
- pypistats では、mirror を除く過去180日のダウンロードが1,529件あった。bot との区別はついていない（#207）。

## Problem

- 課題1: `/data-lineage` の Step 0 が plugin の外へ `insight_blueprint` を入れる入口になっている。公開をやめた後は、古い 0.17.0 を入れ続ける入口になる。
- 課題2: `/data-lineage` の Mode B と Mode C の「notebook を走らせる」は、どの env で走らせるかを書いていない。契約の notebook は `insight_blueprint` を import するので、利用者の env では走らない。
- 課題3: wheel を外に出しているかぎり、model の形が公開の契約になる。次の Epic（[#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)）が `src/insight_blueprint/models/design.py` を変えられない。
- 課題4: PyPI に出すためだけの検査が CI とリリースの手順の手間になり、失敗の元にもなる。v0.9.0 では、publish の action が同梱する twine の版の違いで publish が落ちた（RELEASE.md の Step 2）。
- 課題5: タグを打つのは人間で、版と違う commit にタグを打つと、marketplace がその中身を配る（[ADR-0032](0032-marketplace-serves-the-release-tag.md)）。publish を消すと、それを機械で見る所が無くなる。
- 課題6: PyPI の project のページは、公開をやめた後も 0.17.0 の README を出し続ける。そこには `uv add insight-blueprint-lineage` と書いてある。

扱わない範囲: lineage の API と `.mmd` の形。notebook の契約。配布名 `insight-blueprint-lineage`（既定の許可リストと `src/insight_blueprint/__init__.py` が参照する）。
公開済みの版の yank。

## Decision Analysis

判断は3つある。どれも人間が 2026-11-25 に、この Epic の DesignDoc のセッションで直接選んだ。

### d1: `/data-lineage` の対象と、走らせる env

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | skill が plugin の外へ `insight_blueprint` を入れることを勧めない | Must | - | - | 課題1、課題3、人間の決定（2026-11-23） |
| M2 | skill に書いた「走らせる」が、書いたコマンドのまま走る env を名指ししている | Must | - | - | 課題2 |
| W1 | 分析者が lineage でできること（図の出し直し、加工の見直し）が減らない | Want | 解決 | 中（Claude の推測。人間が A を選んで追認） | 課題2、PRD のコアバリュー「notebook 契約 & lineage」 |
| W2 | 走らせる手順が notebook の中身に依らず通る | Want | 解決 | 高（Claude の推測。人間が A を選んで追認） | 課題2 |
| W3 | 変える量と、後で守るもの | Want | 費用 | 中（Claude の推測） | coding-principles の YAGNI |

案は次の4つ。

- A. 対象を契約の notebook（`.insight/notebooks/{id}.py`）に絞り、`/analysis-notebook` と同じコマンドで plugin の env で走らせる。Step 0 と Mode A（setup）を消し、Mode B（図の出し直し）と Mode C（refactor）を残す。
- B. 自分で書いた notebook も対象に残し、それも plugin の env で走らせる。Mode A〜C を全部残す。
- C. 自分で書いた notebook は利用者の env で走らせ、PyPI の代わりに git のタグからの install を勧める。
- D. `/data-lineage` の skill ごと消す。図は `/analysis-notebook` を走らせ直して出す。

| Must | A | B | C | D | 何もしない |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（git から外へ入れる。model の形は契約のまま） | 満たす | 満たさない |
| M2 | 満たす | 満たす | 満たす | 満たす（走らせる文が無くなる） | 満たさない |

| Want | A | B | D |
|---|---|---|---|
| W1 | 図の出し直しと refactor は残る。自分で書いた notebook に `tracked_pipe` を足す手伝いが無くなる。人間の答えでは、その使い手はいない | 何も減らない | refactor の表（5つの型）が無くなる。図の出し直しは `/analysis-notebook` の走らせ直しに寄る |
| W2 | 契約の notebook は既定の許可リストとパッケージ許可リストの中だけを import するので、`/analysis-notebook` と同じコマンドで通る | 自分で書いた notebook は何でも import する。許可リストに無いパッケージや、利用者のプロジェクトの中の module で止まる。`insight_blueprint` を import した notebook は、利用者自身の env とエディタでは走らなくなる | 走らせる手順が無い |
| W3 | SKILL.md 1つと構造テスト2つ。Mode が1つ減る | Step 0 と走らせる文を直し、自分で書いた notebook の止まり方を書き足す | SKILL.md を消し、README・ARCHITECTURE・`analysis-journal`・`analysis-notebook`・plugin の構造テストを直す |

- 差がつく基準: W2 と W1。W2 で B が落ち、W1 で D が A に負ける。
- 感度: W1 を「高」にして、自分で書いた notebook の手伝いを残すなら B に変わる。W3 を最も重くしても A のまま。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 自分で書いた notebook に `/data-lineage setup` を使っていた人が、更新の後に手伝いを失う | CHANGELOG の Upgrade note に書く。契約の notebook でないものを渡されたら、skill は対象を告げて止まる |
| B | plugin の env でしか走らない notebook が、利用者のプロジェクトに増える | 抑えにくい |
| C | 0.17.0 より後の model が外に入り、model の形が契約のまま残る | なし |
| D | refactor の型が失われ、要ると分かったら skill を作り直す | 表を `/analysis-notebook` の文書へ移す |
| 何もしない | 0.17.0 の model が外に入り続け、plugin と食い違う | なし |

### d2: ビルドの道具をどこまで消すか

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | PyPI に上げるファイルだけを守る検査が、CI とリリースの手順に残らない | Must | - | - | 課題4 |
| M2 | plugin の env を作れることを、CI が確かめ続ける | Must | - | - | ADR-0006 |
| W1 | タグの打ち間違いに、人が見なくても気づける | Want | 解決 | 中（Claude の推測。人間が B を選んで追認） | 課題5、ADR-0032 |
| W2 | 残るコードとテストの量 | Want | 費用 | 中（Claude の推測） | YAGNI |

案は次の2つ。

- A. 全部消す。`check_tag_version` も消す。
- B. wheel の検査は全部消し、タグと版の照合（`scripts/check_tag_version.py`）だけを残す。`ci.yml` で、`v*` のタグの push のときに回す。

| Must | A | B | 何もしない（`publish.yml` だけ消す） |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（`build-check` と `twine check` が残る） |
| M2 | 満たす（`python` job の `uv sync --all-extras`） | 満たす | 満たす |

| Want | A | B |
|---|---|---|
| W1 | 機械の検査が無くなる。気づくのは RELEASE.md の Step 4 を人が回したとき | タグの push で CI が落ちる。push した後に気づく形だが、人の手順に頼らない |
| W2 | スクリプト2つとテスト3つが消える | 約90行のスクリプト1つとテスト1つ、CI の step が1つ残る |

- 差がつく基準: W1 と W2。向きが逆で、重みが同じなら W1 を取る。間違ったタグは、marketplace がそのまま配るからである。
- 感度: W2 を「高」にするなら A に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 版と違うタグを打っても何も落ちず、Step 4 を飛ばすと気づかない | Step 4 を必須と書く（人の手順に頼る） |
| B | CI が落ちるのはタグを push した後で、タグは動かせないので、次の版を出すまで間違った中身が配られる | RELEASE.md の Step 2 で、push の前に手元で `check_tag_version` を回す |
| 何もしない | 使わない wheel の検査で CI が落ち、直す手間が出る | なし |

### d3: PyPI の側の後始末

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 公開済みの版を消さない。yank もしない | Must | - | - | 人間の決定（#207） |
| W1 | PyPI に来た人が、公開をやめたことと次に使う道を知れる | Want | 解決 | 中（Claude の推測。人間が A を選んで追認） | 課題6 |
| W2 | 後始末のために、消した publish の道具をもう一度走らせる手間 | Want | 費用 | 高（Claude の推測） | d2、課題4 |

案は次の2つ。

- A. archive だけを行う。最後の版は出さない。
- B. 説明だけを書き直した最後の版を PyPI に出してから archive する。

| Must | A | B | 何もしない（archive もしない） |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たす |

| Want | A | B | 何もしない |
|---|---|---|---|
| W1 | archive の通知で、もう版が出ないことは伝わる。やめた理由と次の道は伝わらない。下の README の `uv add` は残る | 説明の先頭で、やめた理由と plugin の入れ方を伝えられる | 何も伝わらない |
| W2 | 手間は無い。人間が設定の画面で1回押す | 版を1つ上げてタグを打つ。そのタグは marketplace にも届く。publish の道具は2回目の PR で消すことになる | 手間は無い |

- 差がつく基準: W1 と W2。B で得られるのは README の数行で、そのためにリリースの手順を1回まるごと回すことになる。
- 感度: W1 を「高」にするなら B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | PyPI の README に従って 0.17.0 を入れる人が出る | archive の通知で、もう更新されないことは伝わる。GitHub の README と CHANGELOG に直し方を書く |
| B | 説明のためだけに plugin の版も上がり、中身の変わらない update が marketplace の利用者に届く | 版を上げる PR を README の差分だけにする |
| 何もしない | `publish.yml` を戻せば、古いタグからでも upload できる。ページはいつまでも現役に見える | なし |

## Decision

d1 は A、d2 は B、d3 は A を採る。決め手は d1 が W2、d2 が W1、d3 が W2 である。

- `insight-blueprint-lineage` を PyPI に公開しない。`src/insight_blueprint/` は plugin の env の中でだけ使う。
- **model の形（`src/insight_blueprint/models/`）は公開の契約ではなくなる。** 変えるときに守るのは、`.insight/` に保存済みの YAML が読めることと、plugin の中の呼び出し側だけである。
  ADR-0020 の Context の「model の形を変えると、公開の契約が変わる」と、ADR-0023 の同じ理由は、この ADR の後は効かない。両 ADR の決定そのものは変えない。
- `/data-lineage` の対象は、`/analysis-notebook` が作った契約の notebook（`.insight/notebooks/{id}.py`）だけにする。
  - 走らせるときは、`/analysis-notebook` と同じコマンド（`uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook python .insight/notebooks/{id}.py`）を使う。パッケージ許可リストにあって `notebook` extra に無いパッケージは、同じく `--with` で足す。
  - Step 0（import を試して `uv add` を勧める）と Mode A（setup）を消す。Mode B（図の出し直し）と Mode C（refactor）を残す。
  - 契約の notebook でないもの（`.insight/notebooks/{id}.py` が無い、または `tracked_pipe` を使っていない）を渡されたら、skill は対象を告げ、`/analysis-notebook` を案内して止まる。
- PyPI に出すための道具を消す。`.github/workflows/publish.yml`、`ci.yml` の `build-check` job、poe の `verify-wheel` と `release-dry-run`、`scripts/verify_wheel.py`、`tests/test_verify_wheel.py`、`tests/test_packaging.py`。
- タグと版の照合は残す。`scripts/check_tag_version.py`、`tests/test_check_tag_version.py`、poe の `check-tag-version` はそのままにし、`ci.yml` で `v*` のタグの push のときに回す。
  RELEASE.md の Step 2 では、タグの push の前に手元でも回す。
- ADR-0032 の Decision の4つ目（PyPI への publish が失敗してタグを打ち直すとき）は、publish が無くなるので効かない。
  `check_tag_version` が落ちても、タグは消さず、動かさない（ruleset の `protect-release-tags` が止めている）。
  patch の版を1つ上げ、`marketplace.json` の `ref` もそろえて、正しい commit に新しいタグを打つ。間違ったタグの版は、次の版で入れ替わる。
- `pyproject.toml` と build-system、`notebook` extra、配布名は残す。`uv run --project` が手元のソースから env を作るのに要るからである。`pyproject.toml` の `version` も、plugin の版と照らす場所として残す。
- PyPI の公開済みの版は残し、yank しない。最後の版は出さない。
- 人間が次の4つを行う。1つ目は Epic PR のマージの前で、残りはマージの後である。
  1. ruleset の `protect-main` の必須のチェックから `build-check` を外す。外さないと、`build-check` の結果が来ない Epic PR はマージできない。
  2. GitHub の `pypi` の environment を消す。
  3. PyPI の trusted publisher の設定を消す。
  4. PyPI の project を archive する。
- 案内は GitHub の README と CHANGELOG に置く。ADR-0006 は凍結のまま変えない。ADR の索引で、ADR-0006・0020・0023・0032 の Status に、この ADR が改めた所を書く。

## Consequences

### Positive

- 次の Epic（#217）が公開の契約を気にせずに model を変えられる。
- `/data-lineage` の走らせ方が `/analysis-notebook` と同じ1つのコマンドになり、notebook の中身に依らず通る。
- リリースはタグを打つだけになる。publish の action と twine の版のずれで、リリースが止まらない。
- タグの打ち間違いは、今と同じく CI が落とす。

### Negative

- 自分で書いた notebook に `tracked_pipe` を足す手伝いが無くなる。`/data-lineage setup` は使えなくなる。CHANGELOG の Upgrade note に書く。
- PyPI のページには、0.17.0 の README（`uv add insight-blueprint-lineage`）が archive の通知と並んで残る。そこから 0.17.0 を入れた人には、plugin と違う古い model が入る。
- plugin の外で `insight_blueprint` を使い続けたい人は、git のタグから入れることになる。その model の形は版をまたいで変わりうる。
- `check_tag_version` が落ちるのは、タグを push した後である。タグは動かせないので、間違ったタグの版は、次の版を出すまで marketplace から配られる。その版を入れた cache は、次の版への update で入れ替わる。
- `.mmd` からは step の記録を読み戻せないので、Mode C は notebook を走らせ直す。データの取得をもう一度行う。

## Alternatives considered

- **配布名を変え、PyPI の名前を手放す** — 既定の許可リスト（notebook の契約）と `src/insight_blueprint/__init__.py` の `version()` が配布名を参照する。名前を変える利点が無い。
- **`pyproject.toml` の `[project]` から classifier と URL を消す** — 公開しなくても害が無く、消すと差分が増えるだけである。

## Related

- Epic: [#207](https://github.com/etoyama/insight-blueprint-skills/issues/207) / [epic-31](../design/epic-31-drop-pypi-publish.md)
- 改める: [ADR-0006](0006-plugin-execution-model.md)（Context の PyPI の記述。本文は凍結）、[ADR-0020](0020-design-declares-sources-in-source-ids.md)（Context の公開の契約）、[ADR-0023](0023-catalog-holds-no-credentials.md)（Context の公開の契約）、[ADR-0032](0032-marketplace-serves-the-release-tag.md)（Decision の4つ目）
- 関連: [ADR-0012](0012-single-pr-scope.md)（振る舞いを変えるので Epic にする）、[ADR-0021](0021-default-package-allowlist.md)（既定の許可リストが配布名を使う）
- Supersedes: なし
