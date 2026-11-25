# ADR-0053: 分析を始めた検証の分析設計は、検証仮説・判定の基準・意図を変えない

## Status

Accepted

## Context

Epic 33（[#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[DesignDoc](../design/epic-33-verdict-on-record.md)）の初版で決めた。
Epic 32 は「検証は基準を先に固定して判定する」と決め、意図を変えられる間を状態で区切った（[ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md) の5）。
Story 32.1 のレビューで、分析の後に検証仮説を書き換えられると分かり、人間は機械で止めるかを後で決めると言った（[#234](https://github.com/etoyama/insight-blueprint-skills/issues/234)）。
Epic 32 では手順だけを直し、検証仮説を直すときは派生を作ることにした（Epic 32 の Decision `a-changed-hypothesis-goes-into-a-derived-design`）。

比較の土台にした事実（main 09fc48a）。

- `analyzing` は review の承認で入る状態で、notebook を回す前に付く（`src/insight_blueprint/validate.py` の `VALID_TRANSITIONS` と `skills/analysis-review/SKILL.md` を読んだ）。
- 結果の review は `analyzing → in_review` に戻す（[ADR-0029](0029-analyzing-reaches-conclusion-directly.md)）。戻ると、状態だけでは分析の前と区別できない。意図も、検証仮説も、primary の指標の `comparison` も書き換えられる（`validate_update` を読んだ）。
- `validate.py` は I/O を持たない。hook（`hooks/validate-design.py`）は `design_io` と同じ `validate_update` を使い、守るのは `_hypothesis.yaml` と `_tree.yaml` だけである。verdict は守らない（コードを読んだ）。
- 分析は notebook を通さず、`/analysis-journal` だけでも進められる。そのとき verdict は無い（`skills/analysis-review/SKILL.md` の案内を読んだ）。
- 検証の分析設計は、primary の `comparison` に基準が無くても `analyzing` に進める。notebook は基準が無いと止まり、`/analysis-design` を勧める（[ADR-0050](0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md) の5、notebook の契約を読んだ）。
- ib-notebook の FRN の5本は、`analyzing` か terminal status である。H01〜H03 は1つのコミットで入っていて、分析の後に書き換えたかは git の履歴からは分からない（`git log --follow` を実行した。未確認のまま）。

## Problem

- 課題1: 結果を見た後で検証仮説や基準を書き換えても、記録に残らない。読み手は、基準が結果の前に置かれたと信じられない。
- 課題2: 状態だけでは、分析の前の `in_review` と、結果の review の `in_review` を区別できない。意図の固定（ADR-0048 の5）も、結果の review で外れる。
- 課題3: 区別に使う記録が hook の届かない所にあると、直書きで外せる。
- 課題4: 書き換えを拒むと、基準を書かずに `analyzing` へ進んだ検証が行き止まる。何も測っていないのに、派生を作るしかなくなる。

扱わない範囲: 探索の問いと背景の書き換え（探索は判定しない）。手法と、secondary・guardrail の指標の、後からの変更。`comparison` の文が基準として十分か（review の観点のまま）。

## Decision Analysis

決めることは3つある。分析を始めたことをどう知るか（D1）、何を固定するか（D2）、基準なしの検証をどう扱うか（D3）。
重みを「Claude の推測」としたものは、人間が案を選んだ時点で追認している。

### D1: 分析を始めたことを、記録がどう知るか

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 結果の review で `in_review` に戻っても、分析の後だと分かる | Must | - | - | 課題2 |
| M2 | 保存済みの YAML が、手を入れずに読める | Must | - | - | ADR-0047 |
| W1 | 直書きやファイルの削除で外れない | Want | 解決 | 高（Claude の推測） | 課題3 |
| W2 | notebook を通さない分析にも効く | Want | 解決 | 中（Claude の推測） | 課題2 |
| W3 | 結果を見る前に直すことを妨げない | Want | 費用 | 中（Claude の推測） | #234 |
| W4 | 検査が I/O を持たないままでいられる | Want | 費用 | 中（Claude の推測） | ADR-0001 |

| Must | A. 状態だけ（何もしない） | B. verdict の有無で導く | C. 遷移で分析設計に印を残す |
|---|---|---|---|
| M1 | 満たさない | 満たす | 満たす |
| M2 | 満たす | 満たす | 満たす（項目は任意） |

| Want | B. verdict の有無 | C. 印を残す |
|---|---|---|
| W1 | verdict を消せば外れる。hook は verdict を守らない | 印は hook が守るファイルの中にある。消す書き込みを検査が拒める |
| W2 | 効かない。journal だけの分析は verdict を作らない | 効く。回し方に依らない |
| W3 | 妨げない。回す前なら直せる | 承認から実行までの間に直すことも拒む。直すなら派生を作る |
| W4 | 呼び出し側（`design_io` と hook）がファイルを見て、真偽を渡す | 書き込む前と後の分析設計を比べるだけで済む |

- 差がつく基準: W1・W2・W4 は C、W3 は B が勝つ。
- 感度: W3 を高にすると B に寄る。ただし W2 の穴（journal だけの分析）は残る。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 課題1と課題2が残る | なし |
| B | verdict を消して書き換える。journal だけの分析が素通りする | verdict も hook で守る（守るファイルが増える） |
| C | 承認の後、回す前に誤りに気づいた分析設計も直せない | 派生で作り直す。拒む文で案内する |

### D2: 何を固定するか

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析を始めた後、判定を左右する項目が黙って変わらない | Must | - | - | 課題1 |
| W1 | 判定に効かない所（誤字、補足）を直せる | Want | 費用 | 中（Claude の推測） | #234 |
| W2 | 規則が1文で言える | Want | 費用 | 中（Claude の推測） | FLOW-0013 |
| W3 | 抜け道が残らない | Want | 解決 | 高（Claude の推測） | 課題1 |

| Must | A. 止めない（何もしない） | B. 検証仮説・primary の基準・意図を固定 | C. B に加えて背景も固定 | D. 通して、変更を記録に残す |
|---|---|---|---|---|
| M1 | 満たさない | 満たす | 満たす | 満たす（黙ってはいない） |

| Want | B | C | D |
|---|---|---|---|
| W1 | 背景の誤字と補足は直せる。検証仮説の誤字は直せない | どちらも直せない | 何でも直せる |
| W2 | 「分析を始めた検証は、検証仮説・primary の基準・意図が変わらない」 | 同じ形で言える | 「変えてよいが残る」。残す形（履歴の項目、表示）を新しく作る |
| W3 | 背景に後づけの理由を書ける。判定は動かない | 残らない | 基準そのものが後から動く。読み手が注記を読まなければ気づかない |

- 差がつく基準: W1 は D、B、C の順で、W3 は C、B、D の順である。
- 感度: W3 を最優先にすれば C に変わる。W1 を高にすれば D だが、Epic 32 が決めた「直すなら派生」と逆を向く。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | #234 のまま残る | なし |
| B | 検証仮説の誤字が直せず、派生が増える | 拒む文で派生を案内する |
| C | 背景の補足のためだけに派生を作る | なし |
| D | 履歴の仕組みが増え、基準は結局動く | 表示で目立たせる |

### D3: 基準を書かずに `analyzing` へ進む検証

全体の整合の段で分かった。D2 の B を採ると、課題4が起きる。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 結果を見た後に基準を書く道を開かない | Must | - | - | D2、課題1 |
| W1 | 書き忘れた分析者が、測る前に直せる | Want | 解決 | 高（Claude の推測） | 課題4 |
| W2 | 今まで通っていた操作を拒む範囲が小さい | Want | 費用 | 中（Claude の推測） | FLOW-0008、ADR-0050 の5 |

| Must | 何もしない（行き止まったら派生） | A. `analyzing` に入る書き込みで拒む | B. 空の基準を埋める書き込みは通す |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（journal だけの分析で、結果の後に基準を書ける） |

| Want | 何もしない | A |
|---|---|---|
| W1 | 直せない。notebook が止まった時点で派生を作り、元の分析設計は `analyzing` のまま残る | 承認の時点で拒まれるので、`in_review` のうちに直せる |
| W2 | 拒む操作は増えない | 基準なしの検証の承認を拒む |

- 差がつく基準: W1 は A、W2 は「何もしない」が勝つ。
- 感度: W2 を高にすれば「何もしない」に変わる。ADR-0050 の5の決め手は「拒む判断を実データの後に回せる」だった。D2 で書き忘れの費用が上がったので、前提が変わった。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 何もしない | 書き忘れのたびに、空の分析設計が `analyzing` で残る | notebook の止まる文で派生を案内する |
| A | 意味の無い文（「—」）で検査を通す | review の観点（基準が書かれているか）を残す |
| B | 後づけの基準が記録に入る | なし |

## Decision

人間が選んだ（2026-11-25、Epic 33 の DesignDoc 初版のセッションで直接）。D1 は C、D2 は B、D3 は A である。決め手は、D1 が W1 と W2、D2 が W3 と W1 の釣り合い、D3 が W1 である。
D2 と D3 は受け付けていた書き込みを拒むので、[FLOW-0008](flow/0008-ask-before-narrowing-what-worked.md) に従って人間に聞いた。

1. 分析設計が初めて `analyzing` か terminal status に入るとき、分析設計に分析の印（`analysis_started_at`。時刻）を残す。印は消えず、変わらない。状態が `in_review` や `revision_requested` に戻っても残る。
2. 分析の印を持たない保存済みの分析設計は読める。状態が `analyzing` か terminal status なら、分析を始めたものとして扱う。次に状態を変えるとき、`design_io` が印を付ける。
3. 分析を始めた検証・旧形式の探索・`mixed` の分析設計では、次を変える書き込みを拒む。検証仮説（`hypothesis_statement`）、primary の指標の組（`target` と `comparison`。足す・消す・`tier` を変えることを含む）、意図。拒む文は派生の分析設計を作るよう案内する。背景（`hypothesis_background`）と、ほかの項目は直せる。
4. 検証・旧形式の探索・`mixed` の分析設計が `analyzing` に入る書き込みは、primary の指標があり、その `comparison` が空でないときだけ通す。ADR-0050 の5（基準が書かれているかを機械では検査しない）を、この点だけ改める。見るのは空でないことだけで、基準の文になっているかは review が見る。
5. 意図と形を変えられるのは、分析の印が無い間だけにする。ADR-0048 の5の境目（状態が `in_review` か `revision_requested` の間）を、分析の印に改める。分析を始めた探索の分析設計も、意図と形は変わらない。
6. 旧形式の探索を `confirmatory` に直す例外（[ADR-0049](0049-legacy-exploration-stays-readable-and-is-marked.md) の6）は残す。検証仮説と状態が変わらず、意図だけが変わるからである。
7. 検査は `validate_update` に足す。`design_io` と hook の両方に、同じ検査と同じ文で効く。
8. 分析を始めていない検証・旧形式の探索・`mixed` の分析設計が、`supported` か `rejected` に入る書き込みも、4と同じ条件のときだけ通す。`inconclusive` に入る書き込みは、基準が無くても通す。人間が選んだ（2026-11-25、PM のセッションで直接。ボードの d9 の C）。
   - 経緯: Story 33.4 のレビューで、基準の無い検証が `in_review` や `revision_requested` から結論へ直接進めると分かった（[ADR-0029](0029-analyzing-reaches-conclusion-directly.md) の道）。4は `analyzing` に入る書き込みだけを決めていた。塞ぐと受け付けていた書き込みを拒むので、FLOW-0008 に従って人間に聞いた。
   - 比べた案: A は何もしない。B は結論の3つすべてで拒む。C は支持と棄却だけを拒む。
   - 決め手: 基準の無い支持と棄却を記録が許さないこと（A は満たさない）と、分析をせずに打ち切る道を残すこと（B は満たさない）。
   - `inconclusive` を例外にした理由: 検証仮説を支持も棄却もしないので、基準が要らない。分析を回さないと決めた分析設計を、基準を書かせずに閉じられる。
   - 確かめるのは、4と同じく、分析を始めていない分析設計だけである。保存済みの、基準を持たずに分析を始めた検証は、基準を書き足せない（3）。そこで拒むと `inconclusive` でしか閉じられなくなるので、今までどおり支持と棄却に進める。ただし、分析の印を持たないまま結果の review で `in_review` に戻っている保存済みの検証は、分析の前として読むので（Negative）、基準が無ければ拒む。`inconclusive` か派生で閉じる。

## Consequences

### Positive

- 読み手が、検証仮説と基準が分析を始める前のものだと、記録から信じられる。
- 結果の review で `in_review` に戻しても、意図の固定が外れない。
- 基準の書き忘れが測る前に分かる。
- 検査は I/O を持たないままで、hook の作りは変わらない。

### Negative

- 承認から notebook を回すまでの間に誤りに気づいても、検証仮説と基準は直せない。派生を作ることになり、元の分析設計は `analyzing` で残る。
- 検証仮説の誤字も直せない。
- 背景は直せるので、後づけの理由を書ける。判定は動かないが、読み手には区別がつかない。
- 手法と、secondary・guardrail の指標は、分析を始めた後も変えられる。分析のやり方を結果の後に変える道は残る。
- 保存済みの記録に後から付く分析の印は、付けた時刻で、分析を始めた時刻ではない。
- 分析の印を持たない保存済みの分析設計が、結果の review で `in_review` に戻ったままになっていると、分析の前として読む。ib-notebook の FRN には当たる記録が無い。
- 基準なしの検証の承認が失敗に変わる。空でない文なら何でも通る。
- 基準なしの検証を、分析を始めずに `supported` か `rejected` で閉じる書き込みも失敗に変わる（8）。保存済みの、基準を持たずに分析を始めた検証には効かないので、基準の無い支持と棄却は、その範囲では記録に残りうる。基準と `supported` を1回の書き込みで同時に書くことも通る。基準が結論より先に記録にあったかは確かめない。journal だけで分析を進めた `in_review` の検証を reflection が閉じるときは、結果が出た後なので、基準を書かずに `inconclusive` か派生を案内する（`/analysis-reflection` の Step 4）。
- 新しいファイルへの直書きは今までどおりスキーマだけを確かめる（ADR-0049 が認めた穴）。分析の印を付けずに `analyzing` の分析設計を手で作れる。そのときも、状態から分析を始めたものとして扱う。

## Alternatives considered

- **分析を始めたことを notebook の実行で印す（`/analysis-notebook` が印を書く）** — 印を書くのが skill の手順になり、飛ばせる。journal だけの分析にも効かない。
- **固定する項目でも、誤字を直す書き込みだけは通す** — 誤字かどうかを機械では見分けられない。

## Related

- Epic: [#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[docs/design/epic-33-verdict-on-record.md](../design/epic-33-verdict-on-record.md)
- Issues: [#234](https://github.com/etoyama/insight-blueprint-skills/issues/234)
- [ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md)（5の境目をこの ADR が改める）、[ADR-0050](0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)（5をこの ADR が改める）、[ADR-0049](0049-legacy-exploration-stays-readable-and-is-marked.md)、[ADR-0029](0029-analyzing-reaches-conclusion-directly.md)、[FLOW-0008](flow/0008-ask-before-narrowing-what-worked.md)
- Supersedes: なし
