# ADR-0013: verdict の指標に、任意の効果量・信頼区間・標本サイズを持たせる

## Status

Accepted

## Context

[Epic 12](../design/epic-12-decision-ready-report.md) は、レポートを「読者がそれだけで判断できる」ものにする。
Story [#63](https://github.com/etoyama/insight-blueprint-skills/issues/63)（US-1）はそのうち数値を扱う。
verdict の指標は値・閾値・p 値・合否だけを持ち、読者は「有意だが小さい効果」と「大きい効果」を区別できない。

指標の形は notebook の公開契約である。notebook が書き、`/analysis-report` が読む。
[ADR-0008](0008-notebook-figure-manifest.md)（figures manifest）と同じ種類の変更なので、ADR に残す。

2026-11-15 に、Story #63 の実装の中で人間が項目の形を決めた。比較の前提にした事実は次のとおり。

- 契約の変更前、指標の中のキーは `value`・`threshold`・`p_value`・`pass` の4つだった
  （`skills/analysis-notebook/references/notebook-contract.md` の `results` shape を読んだ）。
- 指標を書くのは notebook の cell 4 で、cell 6 が verdict に写す。読むのは `/analysis-report` の Results の数値表である
  （`skills/analysis-report/SKILL.md` と `references/apa-template.md` を読んだ）。
- `/analysis-report` は読み取り専用の消費者で、数値を自分で計算しない。足す項目はすべて任意にする
  （Epic 12 の Decision `lightweight-apa-plus-decision-context`）。
- verdict は notebook が書く JSON で、検証ライブラリ（`validate.py`）の対象ではない。形を機械で確かめる所は、
  契約テストの sample notebook だけである（`tests/integration/test_analysis_notebook_contract.py` を読んだ）。

## Problem

- 課題1: レポートの読者が、効果の大きさと確かさを読めない。放置すると、p 値と合否だけで判断することになる。
- 課題2: 効果量は種類（Cohen's d、相関係数、オッズ比など）が分からないと大小を読めない。
  信頼区間は水準（95% か 90% か）が分からないと幅を読めない。
  数値だけを載せると、レポートか読者が種類と水準を推測で補う。

扱わない範囲: 群ごとの標本サイズ、検定統計量と自由度、探索的な分析の `notable_patterns` への追加、
verdict の形を検証ライブラリで確かめること。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 3項目を持たない verdict が、今のまま通る | Must | - | - | US-1 AC 4 |
| M2 | レポートが計算も推測もせずに数値表を組める | Must | - | - | 課題2、Epic 12 の Decision |
| W1 | 読者が効果量の種類と信頼水準を取り違えない | Want | 解決 | 高（Claude の推測。人間が B を選んで追認） | 課題2 |
| W2 | 「どの指標にも値がない列は省く」の判定が単純である | Want | 解決 | 中（Claude の推測） | US-1 AC 3 |
| W3 | notebook を書く側の量と、間違えやすさ | Want | 費用 | 中（Claude の推測） | 課題1 |
| W4 | 既存の4つのキーと名前の流儀がそろう | Want | 費用 | 低（Claude の推測） | notebook-contract.md |

案は次の4つ。

- A. 素の値: `"effect_size": 0.42, "ci": [1200.3, 2153.5], "n": 1200`
- B. 自己記述の入れ子: `"effect_size": {"kind": "cohens_d", "value": 0.42}`、
  `"confidence_interval": {"level": 0.95, "lower": 1200.3, "upper": 2153.5}`、`"sample_size": 1200`
- C. 平たい接頭辞: `effect_size`・`effect_size_kind`・`ci_level`・`ci_lower`・`ci_upper`・`sample_size`
- 何もしない: 4つのキーのままにする。

| Must | A. 素の値 | B. 自己記述の入れ子 | C. 平たい接頭辞 | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |
| M2 | 満たさない（種類と水準が無く、レポートが「95%」を推測で書く） | 満たす | 満たす | 満たす（載せないので） |

「何もしない」は Must を通るが、課題1がそのまま残る。

| Want | B. 自己記述の入れ子 | C. 平たい接頭辞 |
|---|---|---|
| W1 | 種類と水準が値と同じ塊に入る。片方だけ書くことが起きにくい | `effect_size` だけを書いて `effect_size_kind` を落とせる。契約の文で縛るしかない |
| W2 | 1つの列が1つのキーに対応する。キーが無ければ列を省く | 信頼区間の列が3つのキーにまたがる。`ci_lower` だけがある状態を扱う決まりが要る |
| W3 | 入れ子の分だけ書く量が増える | 平たいので書きやすいが、キーが6つ並ぶ |
| W4 | 既存のキーは平たいスカラーなので、流儀から外れる | 平たいスカラーでそろう |

- 差がつく基準: W1 と W2 は B が勝ち、W4 は C が勝つ。W3 はほぼ差がない。
- 感度: W4 の重みが高なら C に変わる。W1 と W2 のどちらかが中以上なら B のまま。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 効果量 0.4 が d なのか r なのか分からないレポートが配られる | 抑えられない。後から種類を足すと、契約をもう1度変えることになる |
| B | notebook が `effect_size: 0.42` と素の値で書く | 契約に形を書き、sample notebook を手本にする。レポートは形のそろわない項目を「無い」として扱う |
| C | キーの組が半端になり、信頼区間の片側だけが載る | 契約に「3つそろわなければ省く」と書く |
| 何もしない | 読者が「有意だが小さい効果」を見分けられない | なし |

## Decision

B を採る。決め手は W1 と W2。

`verdict.metrics` の指標ごとに、次の3つの任意の項目を持たせる。形の正本は
[notebook-contract.md](../../skills/analysis-notebook/references/notebook-contract.md) の「Optional metric items」。

| キー | 形 | 意味 |
|---|---|---|
| `effect_size` | `{"kind": str, "value": float}` | 標準化した効果の大きさ。`kind` は種類の名前（`cohens_d`・`r`・`odds_ratio` など） |
| `confidence_interval` | `{"level": float, "lower": float, "upper": float}` | その指標の `value` の区間。`level` は割合（`0.95`） |
| `sample_size` | `int` | その指標の計算に使った観測の数 |

- 3つは互いに独立で、どれも任意である。手法が定義しない項目はキーごと省く。`null` や仮の値を書かない。
- 信頼区間は、効果量の区間ではなく、指標の `value` の区間とする。
- `kind` は open string にする。種類は手法ごとに増えるので、catalog の taxonomy
  （[ADR-0004](0004-open-string-catalog-taxonomy.md)）と同じ扱いにする。
- 項目は中身がそろって初めて有効とする。`kind` の無い `effect_size` と、`level` の無い `confidence_interval` は、
  消費者が「無い」として扱う。
- 計算するのは notebook（cell 4）である。`/analysis-report` は並べるだけで、欠けた項目を計算せず、種類も水準も仮定しない。
- レポートの数値表は、項目ごとに列を1つ持つ（Effect size・CI・N）。どの指標にも値がない列は省く。
  3項目を持たない verdict には、契約を広げる前と同じ表を出す。

## Consequences

### Positive

- 読者が、効果の大きさ・確かさ・件数を、種類と水準つきで読める。
- 効果量の種類と信頼水準が値から離れないので、契約の文に頼らなくても形が取り違えを防ぐ。
- 既存の verdict と、3項目を定義しない手法の verdict は、何も変えずに通る。

### Negative

- 指標の中に、平たいスカラーと入れ子が混ざる。
- verdict の形を機械で確かめる所は、契約テストの sample notebook だけである。
  実際の分析で notebook が形を外しても、レポートがその項目を省くだけで、誰にも知らせない。
- `kind` が open string なので、同じ効果量に別の名前（`cohens_d` と `d`）が付きうる。
- 標本サイズは整数1つで、群ごとの偏りは数値表から読めない。

## Alternatives considered

- **`effect_size` の中に効果量の信頼区間も持たせる** — 指標の `value` の区間と2つ並び、読者がどちらの区間かを取り違える。
  必要になる手法が出てから足す（YAGNI）。
- **`kind` を enum にする** — 手法ごとに種類が増え、そのたびに契約を変えることになる。

## Related

- Epic: [epic-12](../design/epic-12-decision-ready-report.md)（Story #63）
- 関連: [ADR-0008](0008-notebook-figure-manifest.md)（verdict を広げた前例）、
  [ADR-0004](0004-open-string-catalog-taxonomy.md)（open string の扱い）
- Supersedes: なし
