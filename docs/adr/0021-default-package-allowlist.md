# ADR-0021: パッケージ許可リストが無いときは、plugin の既定の許可リストを使う

## Status

Accepted（ファイルがあるときに既定の許可リストを足さない、という決定は [ADR-0027](0027-default-allowlist-always-allowed.md) が改めた）

## Context

パッケージ許可リスト（`.insight/rules/package_allowlist.yaml`）は、notebook が import してよいパッケージの宣言である。
premortem の `allowlist_ok` の元になり、guided autopilot が notebook を自動で実行してよいかの境界にもなる（[ADR-0005](0005-selective-autonomous-chaining.md)）。
[docs/ARCHITECTURE.md](../ARCHITECTURE.md) はこのファイルを「任意」としている。それなのに、ファイルが無いときの扱いはどの文書にも書いていなかった。
v0.10.0 の手動確認（2026-11-20）では、`.insight/rules/` が空のプロジェクトで driver が `allowlist_ok: null` を入れ、premortem が `HIGH` を返して `/analysis-auto` が止まった（issue #101）。
2026-11-20 に人間が案 A を選び、ADR に残すと決めた（[epic-16](../design/epic-16-default-allowlist.md)）。

比較の前提にした事実は次のとおり。

- `allowlist_ok` は driver（LLM）が作る。`package_allowlist.yaml` を読むコードはリポジトリに無い（`grep -rn allowlist skills src` で確かめた）。
  `skills/premortem/cli.py` は渡された値を `SourceChecks` に入れるだけである。
- `skills/premortem/lib/risk_evaluator.py` は、`allowlist_ok` が `false` なら `HARD_BLOCK`、`null` なら `HIGH`（`allowlist check failed (read error)`）にする。
- 照らす対象は分析設計の `methodology.package` で、空でもよい自由な文字列である（`src/insight_blueprint/models/design.py` の `Methodology`）。
- plugin の env には `pyproject.toml` の `notebook` extra（marimo・pandas・matplotlib・numpy）と `insight_blueprint` が最初から入っている。
  notebook の契約は `marimo` と `LineageSession`（`insight_blueprint`）の import を求める（`skills/analysis-notebook/references/notebook-contract.md`）。
- `.insight/` を初期化する skill は無い。リポジトリの `.insight/rules/package_allowlist.yaml` は開発用の見本で、利用者のプロジェクトには配られない。
- driver が `null` を選んだのが、その回だけの解釈か、毎回そうなるのかは確かめていない。

## Problem

- 課題1: パッケージ許可リストが無い新しいプロジェクトでは、guided autopilot が premortem で `HIGH` になって止まる。費用の問題ではないのに、初めて使う分析者が最初に止まる。
- 課題2: ファイルが無いときに `allowlist_ok` をどう決めるかが書かれていない。driver によって `null`・`true`・`false` のどれにもなりうる。
- 課題3: パッケージ許可リストは notebook を自動で実行してよいかの境界でもある。ファイルが無いときに何でも許すと、この境界が消える。

扱わない範囲: `methodology.package` からパッケージを機械で取り出すこと。premortem のほかの確認（登録、location、行数）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | ファイルが無くても、基本のパッケージだけを使う分析は `HIGH` にならない | Must | - | - | 課題1 |
| M2 | ファイルが無いときの扱いが一つに決まり、SKILL.md に書かれる | Must | - | - | 課題2 |
| M3 | ファイルが無くても、基本のパッケージの外の import は止まる所として残る | Must | - | - | 課題3、ADR-0005 |
| W1 | 分析者のプロジェクトに、頼まれていないファイルを書かない | Want | 解決 | 中（Claude の推測。人間は案 A を選んで変えなかった） | ADR-0016 |
| W2 | 既定の許可リストと、plugin の env に実際に入るパッケージがずれない | Want | 費用 | 高（Claude の推測） | 保守 |
| W3 | 変更の量（payload の契約、コード、文書） | Want | 費用 | 中（Claude の推測） | coding-principles の YAGNI |

案は次の4つ。

- 案 A: ファイルが無いときは、plugin 側の既定の許可リスト（`notebook` extra と `insight_blueprint`）と照らして `allowlist_ok` を決める。
  正本は notebook の契約に置き、構造テストで `pyproject.toml` と一致させる。
- 案 B: ファイルが無いときは、何も照らさず `allowlist_ok: true` にする。
- 案 C: 既定の許可リストを雛形として、driver が初回に `.insight/rules/package_allowlist.yaml` に書き出す。
- 案 D: payload に `required_packages` を足し、`cli.py` がファイル（無ければ既定の許可リスト）と照らして `allowlist_ok` を計算する。

| Must | 案 A | 案 B | 案 C | 案 D | 何もしない |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす | 満たさない |
| M2 | 満たす | 満たす | 満たす | 満たす | 満たさない |
| M3 | 満たす | 満たさない（何でも通る） | 満たす | 満たす | — |

| Want | 案 A | 案 C | 案 D |
|---|---|---|---|
| W1 | 何も書かない。 | 初回に分析者のプロジェクトへファイルを書く。 | 何も書かない。 |
| W2 | 構造テストが `pyproject.toml` との一致を確かめる。 | 書き出したあとで plugin が基本のパッケージを増やしても、ファイルは古いまま残る。 | 案 A と同じく、コードの定数をテストで縛れる。 |
| W3 | 文書3つと構造テスト、`HARD_BLOCK` の理由の文。 | 案 A に加えて、書き出す手順と、既にあるかの判定が要る。 | payload の契約、`cli.py`、テスト、文書を変える。必要なパッケージを列挙するのは driver のまま。 |

- 差がつく基準: W1、W2、W3。
- 感度: 「`allowlist_ok` を決定的に計算したい」を高い重みの基準として足すなら、案 D に変わる。ただし必要なパッケージを列挙するのは driver のままなので、決定的になるのは照合の部分だけである。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案 A | `statsmodels` などを使う分析は、ファイルが無いと `false` になり `HARD_BLOCK` で止まる。ファイルを置いてそのパッケージを書かなかったときと同じ扱いである。 | `HARD_BLOCK` の理由に、`.insight/rules/package_allowlist.yaml` に宣言すれば許せることを書く。 |
| 案 B | notebook が任意のパッケージを import し、自動で実行される。ADR-0005 の境界が消える。 | 無い。 |
| 案 C | 古い雛形が残る。頼まれていないファイルが増える。 | 書く前に分析者に聞く（KEEP ゲートが増える）。 |
| 案 D | 契約が変わり、古い driver とずれる。PR が大きくなる。 | 新しいキーを任意にする。 |
| 何もしない | 新しいプロジェクトはすべて止まる。 | 無い。 |

## Decision

案 A を採る。決め手は W1 と W3 である。M1〜M3 を満たす案のうち、分析者のプロジェクトに何も書かず、payload の契約もコードの判定も変えないのは案 A だけである。W2 は構造テストで抑える。

- ファイルが無いときは、既定の許可リストを使う。既定の許可リストは `pyproject.toml` の `notebook` extra と `insight_blueprint` で、正本は `skills/analysis-notebook/references/notebook-contract.md` に置く。
- ファイルがあるときは、ファイルの内容だけを使う。既定の許可リストは足さない。
- `allowlist_ok` は、`methodology.package` に書かれた各パッケージを許可リストの import 名か pip 名と照らして決める。`methodology.package` が空なら `true` にする。
- `null` は、ファイルがあるのに読めないとき（YAML が壊れている、`allowed_packages` が無い）だけに使う。ファイルが無いことは `null` にしない。
- guided autopilot が notebook を自動で実行してよいかを決めるときも、同じ許可リストを使う。
- パッケージ許可リストの外のパッケージで `HARD_BLOCK` になったときの理由は、`.insight/rules/package_allowlist.yaml` に宣言すれば許せることを伝える。

## Consequences

### Positive

- 新しいプロジェクトでも、基本のパッケージだけを使う分析は premortem を通り、notebook まで進む。
- ファイルが無いときの扱いが一つに決まる。
- 既定の許可リストが plugin の env とずれると、構造テストが落ちる。

### Negative

- 新しいプロジェクトで `statsmodels` などを使う分析は、今は `HIGH` で止まるところが `HARD_BLOCK` で止まる。止まる理由は「読めない」から「許可リストの外」に変わり、直し方が分かるようになる。
- 照合は今も driver の解釈で行う。SKILL.md の文が守られるかは、構造テストでは確かめられない。
- ファイルを置いた分析者は、`marimo` と `insight_blueprint`（実際には既定の許可リストの5つすべて）も自分で書く必要がある。書かないと、notebook の契約が求める import が許可リストの外になる。この食い違いはこの ADR の前からあり、ここでは塞がない（issue #108）。[ADR-0027](0027-default-allowlist-always-allowed.md) が、既定の許可リストを常に許すことで塞いだ。

## Alternatives considered

- **ファイルがあるときも既定の許可リストを足し合わせる案** — 分析者がファイルで許可を絞れなくなる。人間に提示した案 A は「ファイルがあればファイルだけ」だったので、比較に入れなかった。

## Related

- Epic: #101、[docs/design/epic-16-default-allowlist.md](../design/epic-16-default-allowlist.md)
- [ADR-0005](0005-selective-autonomous-chaining.md)（パッケージ許可リストが自動実行の境界であること）
- issue #41（パッケージ許可リストの書式の文書）
