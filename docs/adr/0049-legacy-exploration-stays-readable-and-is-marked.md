# ADR-0049: 旧形式の探索は読めるままにし、印を付ける

## Status

Accepted

## Context

Epic 32（[#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)、[DesignDoc](../design/epic-32-exploration-and-confirmation.md)）の初版で決めた。
[ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md) は、探索の分析設計が探索の問いを持ち、検証仮説を持てず、`explored` で終わると決めた。

比較の土台にした事実（main aec5a4c。ファイルを読んで確かめた）。

- これまで `hypothesis_statement` は必須だった。今ある探索の分析設計は、FRN の3件に限らず、すべて仮説を持つ。終わったものは `supported` / `rejected` / `inconclusive` を持つ。
- 分析設計を読む道はどれも model の検査を通る（`skills/_shared/design_io.py`、`skills/_shared/design_note_read.py`）。hook も書き込みのたびに同じ検査をする。「読むときは緩く」の道は無い。
- 分析設計が1つでも読めないと、そのテーマの論点ツリーのページ全体がエラーになる（Epic 28 の決定）。
- terminal status からは遷移できない。終わった記録の状態は `design_io` では変えられない。
- 分析ノートは記録を書かれたとおりに並べ、解釈の文を生成しない（[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)）。
- FRN の3件の中身は issue の記載による。FRN-H01 は開いた問いに作り物の閾値を付けた。FRN-H02 は FRN-H01 から生まれた仮説の検証で、形は合っている。

## Problem

- 課題1: 新しい形で検査すると、今ある探索の記録がすべて落ちる。plugin を上げた利用者のテーマが、表示もレポートも止まる。
- 課題2: 古い記録を新しい言葉で言い換えて出すと、記録に無いことを表示が言う。探索の問いは書かれていない。判定は実際に付いている。
- 課題3: 古い形を読めるようにすると、新しく作る記録にも古い形が混ざりうる。

扱わない範囲: 既存の記録を書き換える道具（Epic 32 の範囲外）。

## Decision Analysis

形式は `decision-analysis` スキルに従う（[FLOW-0004](flow/0004-decision-analysis-plugin.md)）。受け付けていた入力を拒む案を含むので、[FLOW-0008](flow/0008-ask-before-narrowing-what-worked.md) のとおり人間に聞いた。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの YAML が、手を入れずに読める | Must | - | - | [ADR-0047](0047-stop-publishing-to-pypi.md)、課題1 |
| M2 | 表示が、記録に書かれていないことを言わない | Must | - | - | PRD の非機能要件（届く数と結論は記録にあるものに限る）、課題2 |
| W1 | 読み手が、古い形の探索を新しい形の探索と取り違えない | Want | 解決 | 高（Claude の推測） | 課題1 |
| W2 | 新しく作る記録に古い形が混ざらない | Want | 解決 | 高（人間。探索に仮説を置かない） | 課題3 |
| W3 | 検査と表示に足す道の数 | Want | 費用 | 中（Claude の推測） | Context（検査は1通り） |

| Must | A. 形で読み、印を付ける | B. 形で読み、印を付けない | C. 拒む | D. 新しい探索の言葉に読み替えて出す |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（今ある探索の記録がすべて落ち、テーマごと止まる） | 満たす |
| M2 | 満たす | 満たす | 満たす | 満たさない（仮説の文を問いとして出し、付いている判定を隠す） |

「何もしない」は B と同じである。

| Want | A | B |
|---|---|---|
| W1 | 「探索（旧形式）」が付くので、仮説と判定が出ていても、新しい探索と違うと分かる | 同じ「探索」の表示で、仮説のあるものと無いものが並ぶ |
| W2 | 作る道は新しい形だけを書く。古い形は読めるだけ | 同じ |
| W3 | model の検査に「探索は2つの形のどちらか」の1条。表示は旧形式を検証の道に流し、印を1つ足す | 印が無い分だけ少ない |

- 差がつく基準: W1 だけ。
- 感度: C を選べるのは M1 を外すとき、つまり古い探索は読めなくてよいと決めるときである。そのときは ADR-0047 の「保存済みの YAML が読める」に例外を作る。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 旧形式がいつまでも残り、2つの形を読む道を持ち続ける | 直し方を CHANGELOG の Upgrade note に書く。印が直すきっかけになる |
| B | 探索なのに作り物の判定を持つ記録が、新しい形と見分けなしに残る | なし |
| C | plugin を上げた利用者のテーマが、突然出なくなる | Upgrade note。それでも直すまで止まる |
| D | 表示と記録が食い違い、記録にあることだけを出すという前提が崩れる | なし |

## Decision

A を採る。人間が選んだ（2026-11-25、Epic 32 の DesignDoc 初版のセッションで直接）。決め手は W1。

1. `exploratory` で検証仮説を持つ分析設計を「旧形式の探索」と呼ぶ。model は探索に2つの形を認める。探索の問いを持つ形と、検証仮説を持つ形である。両方を持つ記録と、どちらも持たない記録は不正である。
2. 旧形式の探索の検査と遷移は、検証と同じにする。結論の状態は `supported`・`rejected`・`inconclusive` で、`explored` へは進めない。
3. 表示は旧形式の探索の仮説と判定を、書かれたとおりに出す。意図は「探索（旧形式）」と出し、「旧形式の探索: 探索の分析設計に、仮説と判定が書かれている。」の注記を添える。
4. 保存済みの `mixed` は検証として扱い、意図を「探索と検証（旧形式）」と出す。
5. 新しく作る道（`design_io create` と、`design_io update` による意図の変更）は、新しい形だけを書く。旧形式の探索と `mixed` を作れない。この検査は `validate.py` に、読むときの検査とは別の関数として置く。
6. 旧形式の探索を `confirmatory` に直すことは、どの状態でも `design_io update` でできる。検証仮説と状態は変わらず、意図だけが変わるので、結果を見てから検証仮説を置く道にはならない。全体の整合で、意図は分析の前だけ変えられるという決まり（ADR-0048）とぶつかると分かり、人間が例外として決めた。
7. 直し方を CHANGELOG の Upgrade note に書く。実質が検証の記録（FRN-H02 の型）は、6 の道で検証に直す。開いた問いに判定を付けて終えた記録（FRN-H01 の型）は、印を付けたまま残す。

## Consequences

### Positive

- plugin を上げても、今あるテーマの表示とレポートは止まらない。
- 表示は記録に書いてあることだけを言い続ける。
- 旧形式の印が読み手に「この探索は判定を持つ古い形だ」と伝える。

### Negative

- 検査が2段になる。読むときの検査（旧形式を通す）と、作るときの検査（旧形式を拒む）である。hook は書き込みを読むときの検査で確かめるので、YAML を手で書けば旧形式の探索を作れる。作る道は `design_io create` だと SKILL.md に書いて補う。
- 旧形式の探索を既に持つ分析設計を `design_io update` で直すと（図の仕様を足すなど）、旧形式のまま残る。
- 旧形式を読む道は消す時期を決めていない。

## Alternatives considered

- **既存の記録を新しい形へ書き換える道具を作る** — Epic 32 の範囲を決めたときに、対象が少ないうちは作らないと人間が決めた（DesignDoc の Decision `all-thirteen-surfaces-and-no-migration-tool`）。

## Related

- Epic: [#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)、[docs/design/epic-32-exploration-and-confirmation.md](../design/epic-32-exploration-and-confirmation.md)
- Stories: 32.1（土台）、32.2（用語と文書）、32.5（分析ノートとレポート）、32.6（論点ツリー）
- ADR: [ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0047](0047-stop-publishing-to-pypi.md)
