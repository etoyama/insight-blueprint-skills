# ADR-0046: plugin の env と既定の許可リストから marimo を外す

## Status

Accepted

## Context

[ADR-0045](0045-notebook-is-plain-python-with-percent-cells.md) で、notebook は `# %%` で cell を区切る素の Python になり、`import marimo` を書かなくなった。
marimo は今、plugin の env（`pyproject.toml` の `notebook` extra と、開発用の依存）と、既定の許可リストに入っている。
既定の許可リストは、契約の cell が import するパッケージであり、plugin の env に最初から入っているパッケージでもある（[ADR-0021](0021-default-package-allowlist.md)、[ADR-0027](0027-default-allowlist-always-allowed.md)）。
2026-11-23 に、[Epic 30](../design/epic-30-plain-python-notebook.md) の DesignDoc 初版のセッションで人間と決めた。

比較の前提にした事実と、確かめた方法は次のとおり。

- marimo 0.21.1 は site-packages で 114MB を占める。直下の依存は17個で、starlette・uvicorn・websockets を含む。pandas は 40MB である（`du` と `uv tree --package marimo`）。
- marimo の無い env で、旧形式の notebook を走らせると `ModuleNotFoundError` で止まり、終了コードは 1 だった。`--with marimo` を足すと走り、`verdict.json` と `lineage.mmd` が出た。
  同じ marimo の無い env で、新しい形の notebook は走った（どれも `uv run --isolated --no-project --with …` で実行した）。
- `/analysis-notebook` は Step 3 で notebook を毎回書き直す。既にある `.py` をそのまま走らせ直す手順は、どの skill にも無い（`skills/analysis-notebook/SKILL.md` を読んだ）。
  旧形式の notebook を走らせるのは、分析者が手でコマンドを打つときだけである。
- 構造テストは、既定の許可リストの pip 名と plugin の env、既定の許可リストの import 名と契約の cell の import を、それぞれ等号で照らす（`tests/skills/test_default_allowlist_structure.py`）。
- 既定の許可リストに無いパッケージは、`.insight/rules/package_allowlist.yaml` に書き、実行のときに `--with` で足せる（契約の「Supplying an allowlisted package to the run」）。
- premortem の `allowlist_ok` が照らすのは、分析設計の `methodology.package` である。notebook の import ではない（`skills/premortem/SKILL.md`）。
- 確かめていないこと。`methodology.package` に `marimo` と書いた分析設計が在るか。旧形式の notebook を手で走らせ直す場面が、どれだけ在るか。

## Problem

- 課題1: plugin の env がどの notebook も使わないパッケージを抱え続ける。
- 課題2: 既定の許可リストに marimo を残すと、「契約の cell が import するパッケージ」という定義と中身が食い違う。web サーバを連れてくるパッケージが、理由なく常に許される。
- 課題3: 外すと、既にある旧形式の notebook を今のコマンドで走らせ直せなくなる。動いていたものが止まる（[FLOW-0008](flow/0008-ask-before-narrowing-what-worked.md)）。

扱わない範囲: 旧形式の notebook のコードを分析ノートに出すか（ADR-0045）。lineage のライブラリ（marimo に依らない）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 既定の許可リスト、契約の import、plugin の env の3つが一致する | Must | - | - | ADR-0027、構造テスト |
| W1 | env と許可の境界に、使わないものが残らない | Want | 解決 | 高（Claude の推測。人間は結論に同意した） | 課題1、課題2 |
| W2 | 旧形式の notebook を、今のコマンドのまま走らせ直せる | Want | 解決 | 低（Claude の推測） | 課題3 |
| W3 | 変える量 | Want | 費用 | 低（Claude の推測） | YAGNI |

| Must | X: 依存と既定の許可リストの両方から外す | Y: 依存からだけ外す | Z: 両方に残し、定義を改める | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たさない（許されているのに env に無い） | 満たす（定義を改めれば） | 満たさない（契約が import しないものが残る） |

| Want | X | Z |
|---|---|---|
| W1 | env から 114MB と、直下の依存17個が消える。常に許すのは insight_blueprint・pandas・matplotlib・numpy になる。 | 残る。既定の許可リストの定義に、使わない形式のための例外が入る。 |
| W2 | 今のコマンドでは `ModuleNotFoundError` になる。パッケージ許可リストに1行足し、`--with marimo` を付ければ走る。 | 今のまま走る。 |
| W3 | `pyproject.toml`、`uv.lock`、契約の Default allowlist、構造テスト、文書を直す。 | ADR-0027 の定義と構造テストを直す。 |

- 差がつく基準: W1 は X、W2 は Z が勝つ。
- 感度: 旧形式の notebook を手で走らせ直す場面が日常的にあるなら、Z になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| X | 更新した利用者が、旧形式の notebook を手で走らせて `ModuleNotFoundError` に当たる。`methodology.package` に `marimo` と書いた分析設計が、premortem で `HARD_BLOCK` になる | CHANGELOG に、起きることと直し方を書く。`HARD_BLOCK` の理由は、今もパッケージ許可リストへの足し方を伝える |
| Y | 許されているのに import できない状態が残る | 抑えられない |
| Z | 外すと決めた依存が残り、同じ議論をもう一度する | 消す時期を決める（守られる保証は無い） |
| 何もしない | 構造テストが落ち、契約を直す Story が進まない | なし |

## Decision

X を採る（人間の判断、2026-11-23）。決め手は W1 である。

- `pyproject.toml` の `notebook` extra と、開発用の依存から、marimo を外す。`uv.lock` も更新する。
- 既定の許可リストから marimo を外す。既定の許可リストは `insight_blueprint`・`pandas`・`matplotlib`・`numpy` になる。正本は今までどおり notebook の契約の「Default allowlist」の節に置く。
- 既定の許可リストの定義（契約の cell が import するパッケージで、plugin の env に最初から入っているもの）と、常に許すという扱いは変えない（ADR-0021、ADR-0027）。変わるのは中身だけである。
- 旧形式の notebook を走らせ直したい分析者は、`.insight/rules/package_allowlist.yaml` に `marimo: marimo` を書き、実行のコマンドに `--with marimo` を付ける。
- CHANGELOG に、更新した利用者に起きることと、この直し方を書く。

## Consequences

### Positive

- plugin の env が軽くなる。web サーバを含む依存が、env に入らなくなる。
- 常に許されるパッケージが、契約の cell が実際に import するものだけになる。
- 既定の許可リスト、契約の import、plugin の env が一致したまま保たれる。

### Negative

- 更新した後、旧形式の notebook を今のコマンドで走らせると `ModuleNotFoundError` で止まる。直し方は CHANGELOG にしか無い。エラーの文は直し方を伝えない。
- `methodology.package` に `marimo` と書いた分析設計は、パッケージ許可リストに足すまで premortem で `HARD_BLOCK` になる。
- ADR-0021 と ADR-0027 の本文は、既定の許可リストに marimo を挙げたままになる。索引の Status に、中身をこの ADR が改めたことを書く。

## Alternatives considered

- **marimo を、別の extra（例: `marimo`）として残す** — 使う skill が無い extra を持つことになる。要るときは `--with marimo` で足りる。

## Related

- Epic: [#176](https://github.com/etoyama/insight-blueprint-skills/issues/176)、[epic-30](../design/epic-30-plain-python-notebook.md)
- 関係する ADR: [ADR-0005](0005-selective-autonomous-chaining.md)、[ADR-0021](0021-default-package-allowlist.md)、[ADR-0027](0027-default-allowlist-always-allowed.md)、[ADR-0045](0045-notebook-is-plain-python-with-percent-cells.md)
- Supersedes: ADR-0021 と ADR-0027 の、既定の許可リストの中身（marimo を含むこと）
