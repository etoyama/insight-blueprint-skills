# ADR-0027: notebook の契約が求める import は、パッケージ許可リストにかかわらず許す

## Status

Accepted

## Context

notebook の契約（`skills/analysis-notebook/references/notebook-contract.md`）は、生成するすべての notebook に
`marimo`（cell 2 の `import marimo as mo`）と `insight_blueprint`（cell 0 の `LineageSession` など）の import を求める。
同じ契約は、notebook のトップレベルの `import X` について、`X` がパッケージ許可リストのキーにあることも求める。
[ADR-0021](0021-default-package-allowlist.md) は、`.insight/rules/package_allowlist.yaml` があるときはその中身だけを許可リストにし、既定の許可リストは足さないと決めた。
そのため、ファイルに `marimo` と `insight_blueprint` を書かないと、契約が求める import が許可リストの外になる。
ADR-0021 はこの食い違いを Negative に書いたが、塞がなかった（issue #108）。
2026-11-21 に人間が案 A を選び、新しい ADR を書いて単発の PR で出すと決めた。

比較の前提にした事実は次のとおり。

- パッケージ許可リストを読むコードはリポジトリに無い。照合は driver（LLM）が SKILL.md と契約の文に従って行う（ADR-0021。`grep -rln package_allowlist skills src` で確かめた）。
- `/analysis-auto` は、許可リストの外の import がある notebook を自動で実行せず、KEEP ゲートで止める（`skills/analysis-auto/SKILL.md` の notebook の項）。
- premortem の `allowlist_ok` が照らすのは `methodology.package` だけである。`marimo` は普通そこに書かれないので、止まるのは notebook の手前の KEEP ゲートのほうである。
- リポジトリの見本（`.insight/rules/package_allowlist.yaml`）にも `marimo` と `insight_blueprint` が無かった。見本を写したプロジェクトは毎回止まる。
- 実際に `/analysis-auto` を走らせて止まるかは確かめていない。上の文を読んで導いた。

## Problem

- 課題1: パッケージ許可リストのファイルを置いた分析者は、`marimo` と `insight_blueprint` を書き忘れると、notebook の手前の KEEP ゲートで毎回止まる。分析者が自分で選んだパッケージではないので、直し方も分かりにくい。
- 課題2: リポジトリの見本自体が契約を破っており、写した人は必ずこの穴に落ちる。

扱わない範囲: `pandas` など、契約が求めない既定の許可リストのパッケージの扱い。ファイルがあるときにこれらを足さないという ADR-0021 の決定は変えない。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 見本のファイルを写したプロジェクトが notebook の手前の KEEP ゲートで止まらない | Must | - | - | 課題2 |
| M2 | 契約の外のパッケージは、ファイルで許可を絞れる | Must | - | - | ADR-0021、ADR-0005 |
| W1 | 書き忘れたファイル（既にあるものも含む）でも止まらない | Want | 解決 | 高（Claude の推測。人間は案 A を選んで変えなかった） | 課題1 |
| W2 | 進め方の重さ（ADR-0012 の範囲に収まるか） | Want | 費用 | 中（Claude の推測） | [ADR-0012](0012-single-pr-scope.md) |

案は次の2つ。

- 案 A: 契約が求める import を、ファイルがあるかどうか、ファイルに何が書いてあるかにかかわらず許す。見本も直す。
- 案 B: 振る舞いは変えない。見本に2つを足し、ファイルには契約の import を必ず書くよう案内する。

| Must | 案 A | 案 B | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない |
| M2 | 満たす（契約の import を外しても守れるものが無いので、絞れる範囲は実質変わらない） | 満たす | 満たす |

| Want | 案 A | 案 B |
|---|---|---|
| W1 | 書き忘れても止まらない。穴を仕組みで塞ぐ。 | 案内を読んだ人だけが助かる。既にファイルを置いた人と、driver が案内を読み落としたときは止まる。 |
| W2 | ADR-0021 の決定を変えるので ADR-0012 を超え、新しい ADR が要る。変更は文書と構造テストだけで小さい。 | ADR-0012 に収まる。 |

- 差がつく基準: W1、W2。
- 感度: W2 を W1 より重く見るなら、案 B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案 A | 「ファイルだけ」の文に例外が入り、driver が読み違えうる。 | 例外の正本を契約の「Contract imports」節に置き、premortem と `/analysis-auto` も同じ文で書き、構造テストで縛る。 |
| 案 B | 案内で済ませるので、同じ穴が残る。 | 見本を直し、写す人だけは救う。 |
| 何もしない | 見本を写した人が全員止まる。 | 無い。 |

## Decision

案 A を採る。決め手は W1 である。契約が必ず書かせる import をパッケージ許可リストで拒めても、守れる境界は無く、分析者が落ちる穴だけが残る。

- 契約が求める import（`marimo`、`insight_blueprint`）は、パッケージ許可リストのファイルがあるかどうか、何が書いてあるかにかかわらず許す。
  正本は notebook の契約の「Contract imports」節に置く。
- パッケージ許可リストが決めるのは、それ以外の import である。ファイルがあるときにほかの既定の許可リストを足さないことは、ADR-0021 のまま変えない。
- premortem の `allowlist_ok` と `/analysis-auto` が notebook を自動で実行してよいかの判定は、同じ規則に従う。
- リポジトリの見本は、既定の許可リストから始めた形にする。
- 振る舞いを変えるが、変更は文書と構造テストだけで、効果は ADR-0021 の1つの決定に閉じる。ADR-0012 の例外として、Epic にせず単発の PR で出す（人間が決めた）。

## Consequences

### Positive

- ファイルを置いても、契約の import のせいで `/analysis-auto` が notebook の手前で止まることは無くなる。既にあるファイルも直さなくてよい。
- 構造テストが、契約の import が既定の許可リストに含まれることと、見本が既定の許可リストを含むことを確かめる。

### Negative

- 照合は今も driver の解釈で行う。SKILL.md の文が守られるかは、構造テストでは確かめられない。
- 契約が求める import を増やすときは、「Contract imports」節も直す必要がある。今はこれを縛るテストが無い（契約の cell の表から import を機械で取り出していない）。
- ADR-0012 の例外を1つ作った。

## Alternatives considered

- **ファイルがあるときも既定の許可リスト全体を足す案** — `pandas` などは契約が求めないので、分析者がファイルで許可を絞れなくなる。ADR-0021 が落とした案と同じなので、比較に入れなかった。

## Related

- Issue: #108
- 改める ADR: [ADR-0021](0021-default-package-allowlist.md)（「ファイルがあればファイルだけ」に、契約の import の例外を足す）
- [ADR-0005](0005-selective-autonomous-chaining.md)（パッケージ許可リストが自動実行の境界であること）
- [ADR-0012](0012-single-pr-scope.md)（単発の PR の範囲）
