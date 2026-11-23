# ADR-0045: notebook は `# %%` で cell を区切る素の Python にし、marimo の書式をやめる

## Status

Accepted

## Context

[Epic 30](../design/epic-30-plain-python-notebook.md)（[#176](https://github.com/etoyama/insight-blueprint-skills/issues/176)）は、notebook を marimo で書くことをやめるかを決める。
`/analysis-notebook` は Epic 07 から、8つの cell を持つ marimo notebook を生成してきた（`skills/analysis-notebook/references/notebook-contract.md`）。
分析者が読む面は、Epic 28 で分析ノートになった（[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)）。分析ノートは notebook の `.py` を cell ごとに切り出して出す。
2026-11-23 に、DesignDoc 初版のセッションで人間と決めた。

比較の前提にした事実と、確かめた方法は次のとおり。

- 分析者は `marimo edit` も、`marimo export html` の HTML も使っていない（人間、2026-11-23）。
- 見本の notebook（`tests/integration/fixtures/sample_notebook.py`）を、`# %%` 区切りの形と、cell を関数にした形に書き直して走らせた。
  marimo の2段の実行、marimo の `.py` の直の実行、`# %%` 区切り、関数の形の4通りで、`verdict.json` と `lineage.mmd` はバイト単位で同じだった（scratchpad で `cmp`）。
- marimo の書式のままでも、`python {id}.py` を直に走らせると同じ出力が出る（実行した）。
- 同じ変数を2つの cell で代入した marimo notebook は、`MultipleDefinitionError` で止まる。終了コードは `marimo export script` でも直の実行でも 1 だった（実行した）。
  契約はこれを notebook が動かない原因の筆頭と書いている（marimo rules の 8）。回数を数えた記録は無い。
- `marimo export script` が出す flat script も `import marimo as mo` し、`mo.md` と `mo.mermaid` を呼ぶ。その表示はどこにも出ない（flat script を読んだ）。
- `# %%` 区切りの `.py` は標準ライブラリの `tokenize` と `ast` で cell に切り出せた。約40行の試作に、契約どおりの形と崩れた形の10通りを渡し、期待どおりに分かれた（scratchpad で実行した）。
  marimo の書式の `.py` を渡すと、切り出しは何も返さなかった。
- `# %%` 区切りの notebook から、plotly の `write_html` で HTML の図を保存できた（`uv run --with plotly` で実行した）。
- 分析ノートは、cell を切り出せないとき「notebook が契約の形でなく、データ取得の cell を特定できないので、コードを1つも載せない」と出す（`skills/_shared/design_note.py` の `_code`）。
  結果・図・経過・結論の節は `.py` の形に依らずに出る（`skills/_shared/design_note_read.py` の `load_design_note` を読んだ）。
- 分析ノートの「分析コード」の節は v0.15.0（2026-11-23）で入った（`CHANGELOG.md`）。
- 結論の出た分析設計は `/analysis-notebook` で走らせ直せない（`skills/analysis-notebook/SKILL.md` の Step 1）。
- 確かめていないこと。エディタが `# %%` を実行できる cell として扱うこと。旧形式の notebook が利用者のプロジェクトに何本あるか。

## Problem

- 課題1: 生成した notebook が分析の中身と関係のない marimo の決まり（marimo rules の 1〜9）で止まる。直すのは AI と分析者で、分析の手戻りになる。
- 課題2: 実行が2段（`marimo export script` の後に `python {id}_flat.py`）で、誰も読まない `{id}_flat.py` が `.insight/notebooks/` に残る。
- 課題3: 分析者はいざというときに、手元の `.py` を開いて分析コードを確かめる（ADR-0036 の課題4）。その `.py` はデコレータと、引数と戻り値の tuple と、`_` で始まる変数名に包まれている。
- 課題4: 切り出しを新しい形に替えると、既にある marimo の書式の `.py` は、分析ノートにコードが出なくなる。動いていた表示が消える（[FLOW-0008](flow/0008-ask-before-narrowing-what-worked.md)）。
- 課題5: 切り出しは接続情報を分析ノートに載せないための実装である（[ADR-0022](0022-connection-reaches-only-the-notebook.md)）。2通り持つと、守る面が2つになる。

扱わない範囲: plugin の env と既定の許可リストから marimo を外すこと（[ADR-0046](0046-marimo-leaves-the-plugin-env-and-the-default-allowlist.md)）。図を動かして確かめられる形で出すこと（[#175](https://github.com/etoyama/insight-blueprint-skills/issues/175)）。
verdict・figures manifest・lineage の形（変えない）。

## Decision Analysis

notebook の形式をどれにするか。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | verdict・figures manifest・lineage の形と置き場が変わらない | Must | - | - | 分析ノートとテーマの最終報告（`tree_io render`・`tree_io report`）が読む（[ADR-0008](0008-notebook-figure-manifest.md)、[ADR-0013](0013-verdict-metric-optional-items.md)） |
| M2 | 分析ノートが cell ごとにコードを出し、データ取得の cell を特定できなければ1つも出さない | Must | - | - | ADR-0022、ADR-0036 |
| M3 | notebook が HTML の図を保存することを妨げない | Must | - | - | #175、#176 のコメント |
| W1 | 形式の決まりで notebook が止まりにくい | Want | 解決 | 高（Claude の推測。人間は結論に同意した） | 課題1 |
| W2 | 手元の `.py` が分析のコードとして読みやすい | Want | 解決 | 中（Claude の推測） | 課題3 |
| W3 | 実行の経路が短く、依存が軽い | Want | 解決 | 中（Claude の推測） | 課題2 |
| W4 | 変える量（契約、切り出し、テスト、文書、既にある notebook） | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | A': marimo の書式を残し、実行を1段にする | B: `# %% <名前>` で区切る素の Python | C: cell を関数にした素の Python | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（実行した） | 満たす（実行した） | 満たす（実行した） | 満たす |
| M2 | 満たす（今の実装） | 満たす（試作した） | 満たす（推定。今の `ast` の切り出しに近い） | 満たす |
| M3 | 満たす（推定） | 満たす（実行した） | 満たす（推定） | 満たす（推定） |

| Want | A' | B | C | 何もしない |
|---|---|---|---|---|
| W1 | marimo rules の 1〜9 が残る。多重の定義で止まる。 | 形式の決まりは区切りの行だけになる。多重の代入でも走る。 | 関数の引数と `main()` のつなぎが食い違うと止まる。決まりは marimo より少ない。 | A' と同じ。 |
| W2 | 見本は161行。デコレータと引数と戻り値が分析のコードを包む。 | 見本は101行。上から下へ読めるスクリプトになる。 | 見本は121行。処理の順は `main()` を見ないと分からない。 | A' と同じ。 |
| W3 | 1段になり、`_flat.py` が消える。実行に marimo が要る。 | 1段になり、`_flat.py` が消える。実行に marimo が要らない。 | B と同じ。 | 2段のままで、`_flat.py` が残る。 |
| W4 | 契約と SKILL.md の実行のコマンドと、結合テストだけを変える。 | 契約を書き直し、切り出しを替え、見本・結合テスト・文書を直す。既にある notebook の扱いを決める必要がある。 | B と同じ。関数の外に書かれたコードの扱いを新しく決める必要がある。 | 何も変えない。 |

- 差がつく基準: W1 と W2 は B が最も良く、C、A' の順になる。W3 は B と C が並ぶ。W4 は A' が最も軽い。
- 感度: cell の間の依存が書式の上で明示されることを W1 より重く見るなら C になる。変える量を最も重く見て、止まることを許せるなら A' になる。

既にある marimo の書式の notebook を、分析ノートでどう扱うか。B を採ったうえで比べた。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M4 | どの形式でも、データ取得の cell を特定できなければコードを載せない | Must | - | - | ADR-0022、ADR-0036 |
| W5 | 既にある分析の分析コードが、分析ノートで読める | Want | 解決 | 低（Claude の推測。人間は結論に同意した） | 課題4 |
| W6 | 守る切り出しが1つで、契約の形が1つである | Want | 解決 | 高（Claude の推測） | 課題5 |
| W7 | 足すコード・テスト・文書の量 | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | Q: 新しい形だけを読む | P: 両方を読む | R: Q に、書き換えの手順を足す | 何もしない（扱いを決めない） |
|---|---|---|---|---|
| M4 | 満たす | 満たす（2通りのそれぞれで守る） | 満たす | 満たさない（実装が決めることになる） |

| Want | Q | P | R |
|---|---|---|---|
| W5 | 旧形式はコードが出ない。手元の `.py` では読める。結論の出た分析は、出ないまま残る。 | 旧形式も今までどおり出る。 | 書き換えた分は出る。書き換えは分析者が頼む。 |
| W6 | 切り出しも契約も1つになる。 | 切り出しが2つになる。旧形式には名前との一致の検査を足せないので、下に書く穴が旧形式にだけ残る。 | 切り出しは1つになる。書き換えが cell を取り違えないことを、別に守る必要がある。 |
| W7 | 案内の文1つとテストを足す。 | 今のコードとテストを残し、形式を見分ける分岐を足す。消す時期を別に決める。 | 書き換えの手順かコマンドと、そのテストを足す。 |

- 差がつく基準: W5 は P、W6 と W7 は Q が勝つ。
- 感度: 結論の出た旧形式の分析を、コードごと Artifact で人に渡す予定が既にあるなら、P か R になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A' | 使っていない道具の決まりで止まり続ける。#175 の後に外すと、契約を二度書き直す | 抑えにくい |
| B | 下の cell が上の cell の変数を上書きしても走る。cell の順を入れ替えて壊れても、走らせるまで分からない | 契約に「契約の変数は、その cell だけで代入する」と書く。`raw_df` の多重の代入は、切り出しが拾ってコードを載せない |
| B、C | 後で `marimo edit` を使いたくなっても、そのままでは開けない | 抑えない。使っていないので受け入れる |
| C | 生成のたびに `main()` のつなぎを書き、食い違いで止まる。関数の外の定数に接続情報が書かれうる | 関数の外は import だけ、という決まりと検査が要る |
| Q | 更新した利用者の分析ノートから、出ていたコードが消える。理由が分からないと不具合に見える | 案内の文に、理由と直し方を書く。CHANGELOG に書く |
| P | 旧形式の切り出しがいつまでも残り、穴の残る経路を持ち続ける | 消す時期を決める（守られる保証は無い） |
| R | 書き換えが接続情報の入った行を別の cell に置き、分析ノートに載る | 書き換えた後も、新しい切り出しを通す |
| 何もしない | 課題1〜3 が残る | なし |

## Decision

B と Q を採る（人間の判断、2026-11-23）。決め手は形式では W1 と W2、既にある notebook の扱いでは W6 である。

- notebook は上から下へ走る素の Python のスクリプトにする。`import marimo` を書かず、`marimo.App` と `@app.cell` を使わない。
- cell は行頭に書いた `# %% <名前>` のコメントで区切る。区切りの行から、次の区切りの行の前までが1つの cell である。
- 契約の cell は7つで、この順に並べる。`imports`、`data_load`、`data_prep`、`analysis`、`viz`、`verdict`、`lineage`。
  今の meta の cell は無くす。分析設計の id・題・仮説・intent は、ファイルの冒頭の docstring に書く。最初の区切りより前に書けるのは、この docstring だけである。
- 契約の変数（`raw_df`、`session`、`df_clean`、`results`、`figure_manifest`、`verdict`）は、それを作る cell だけで代入する。
- marimo rules の節は無くす。cell の中だけで使う変数に `_` を付ける決まり、引数で依存を表す決まり、戻り値を tuple にする決まり、viz の最後の式を `plt.gcf()` にする決まり、`mo.md` と `mo.mermaid` による表示は、どれも要らなくなる。
- verdict・figures manifest・lineage の形と置き場、`LineageSession` と `tracked_pipe` の呼び方、`results` の形は変えない。
- 実行は1段にする。`uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook python .insight/notebooks/{id}.py`。
  `{id}_flat.py` と `{id}.html` は作らない。[ADR-0006](0006-plugin-execution-model.md) の notebook の実行の行（`<marimo|python>`）は、この形に置き換える。
- 分析ノートは、次のすべてを満たす `.py` からだけ、cell を切り出す。1つでも欠けたら、コードを1つも載せない。
  - Python として読める。
  - 区切りの行が1つ以上ある。区切りは列0から始まるコメントのうち `# %%` で始まるものである。文字列の中の `# %%` は区切りにしない。
  - 最初の区切りより前に、docstring のほかの文が無い。
  - どの区切りも文の途中に無い。
  - `data_load` という名前の cell がちょうど1つ在る。
  - `raw_df` を代入する cell がその `data_load` の cell だけである。
- データ取得の cell は `data_load` という名前の cell である。分析ノートには載せない。ほかの cell は名前を添えて順に載せる。切り出しはほかの cell の名前と数を確かめない。
- 分析ノートは marimo の書式の `.py` を読まない。`@app.cell` の切り出しは消す。旧形式の notebook は契約の形でないものとして扱い、コードを載せない。
  案内の文に、`/analysis-notebook` で作り直すと載ることを足す。
- 用語表の「notebook」と「データ取得の cell」の定義を改め、「cell」を足す。直すのは文書の Story である。

## Consequences

### Positive

- notebook は、形式の決まりでは止まらなくなる。止まるのは Python の誤りだけになる。
- 手元の `.py` が、上から下へ読める分析のスクリプトになる。
- 実行が1段になり、`_flat.py` が残らない。実行に marimo が要らない。
- データ取得の cell の見分け方が厳しくなる。今の決まり（`raw_df` を代入する cell が1つ）では、接続情報を別の cell で変数に入れてから `raw_df` を作る notebook で、その cell が分析ノートに載る。
  名前との一致を足すと、この notebook からはコードを載せなくなる。
- 分析ノートは cell を名前で示せる。
- #175 の動く図は、この契約の上に足せる。cell の書式は、図の保存のしかたを縛らない。

### Negative

- 多重の代入と cell の順の誤りを、書式が止めなくなる。marimo が持っていた検査を手放す。`raw_df` のほかの契約の変数は、文の決まりだけで守る。
- 既にある marimo の書式の notebook は、分析ノートにコードが出なくなる。結論の出た分析設計は走らせ直せないので、出ないまま残る。分析者は手元の `.py` で読む。
- `raw_df` の代入として数えるのは、名前への代入だけである。`import … as raw_df`、`def raw_df`、`globals()` を通した代入は数えない。今の切り出しと同じ穴で、ここでは塞がない。
- 分析コードの cell に、接続情報のほかの秘密や個人情報が書かれていても、検査しない（ADR-0036 と同じ）。
- 冒頭の docstring には、分析設計の題と仮説の文が入る。文の中の `"""` や `\` で docstring が壊れないように、文字列として正しく書く必要がある。今の meta の cell の `mo.md("…")` と同じ注意である。
- cell の間の依存は、変数の名前でしか分からない。
- `marimo edit` で notebook を開く道は無くなる。使いたくなったら、決め直す。
- エディタが `# %%` を cell として扱うかは、確かめていない。
- [Epic 07](../design/epic-07-analysis-notebook.md) の DesignDoc と ADR-0006 の記述のうち、8つの cell、marimo rules、2段の実行は、この ADR で古くなる。どちらも凍結しているので直さない（[ADR-0009](0009-adopt-repo-template-flow.md)）。
- ADR-0036 の「notebook の HTML の書き出しは、任意のままにする」と、cell の形を `@app.cell` とした記述は、この ADR で古くなる。
  [Epic 28](../design/epic-28-tree-entry-point.md) の Decision `the-data-load-cell-is-the-one-that-binds-raw-df` も古くなる。Epic 28 は閉じているので直さない。

## Alternatives considered

- **`{id}_flat.py` を分析ノートが読む** — `marimo export script` が出す flat script は、名前の無い `# %%` で区切られている（flat script を読んだ）。
  旧形式のコードを出す手になるが、cell に名前が無いので、名前との一致で見分けられない。`{id}_flat.py` が無い notebook もある。
- **cell を別々のファイルにする** — 実行の順と変数の受け渡しを、新しく決める必要がある。分析者が開くファイルも増える。
- **Jupyter の `.ipynb` にする** — JSON なので、手元で読みにくく、差分も読みにくい。実行に `nbformat` などの依存が要る。

## Related

- Epic: [#176](https://github.com/etoyama/insight-blueprint-skills/issues/176)、[epic-30](../design/epic-30-plain-python-notebook.md)
- 関係する ADR: [ADR-0006](0006-plugin-execution-model.md)、[ADR-0008](0008-notebook-figure-manifest.md)、[ADR-0013](0013-verdict-metric-optional-items.md)、[ADR-0022](0022-connection-reaches-only-the-notebook.md)、
  [ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0046](0046-marimo-leaves-the-plugin-env-and-the-default-allowlist.md)
- 関係する issue: [#175](https://github.com/etoyama/insight-blueprint-skills/issues/175)
- Supersedes: ADR-0006 の notebook の実行の行。ADR-0036 の、cell の形と notebook の HTML の書き出しについての記述。
