# ADR-0029: analyzing から結論の status へ直接遷移できるようにする

## Status

Accepted

## Context

guided autopilot（`/analysis-auto`）の既定の巡回が、分析を終えた後の reflection で毎回止まる（[#138](https://github.com/etoyama/insight-blueprint-skills/issues/138)）。
2026-11-21 に ib-notebook でオープンデータの分析を試したとき、1巡目の `/analysis-reflection` が `design_io transition --target supported` を呼び、拒まれた。
分析者は `/analysis-review` を走らせて `in_review` を経てから閉じたので、結果を見る必要の無いレビューが1回挟まった。

比較の前提にした事実と、確かめた方法は次のとおり。

- `VALID_TRANSITIONS`（`src/insight_blueprint/validate.py`）では、`analyzing` から行けるのは `in_review` だけである。結論の status（`supported` / `rejected` / `inconclusive`）へは `in_review` か `revision_requested` からしか行けない。
  この表は Epic 2（`232f81b`）で `validate.py` に移したときからこの形で、元は upstream の #26 である（ファイルと `git show 232f81b` を読んだ）。
- `/analysis-design` の Status Flow の図（`analyzing → in_review`）と [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の状態遷移ガードの記述（「`analyzing → supported` は拒む」）は、表と同じことを定めている（ファイルを読んだ）。
- `/analysis-reflection` の結論の手順の注記は「結論へ遷移するには `analyzing` が必要」と書き、表と逆を言う（`skills/analysis-reflection/SKILL.md` を読んだ）。
- `/analysis-auto` の Step 3 の review は分析の前に行う設計レビューで、通れば `analyzing` になる。分析の後に `in_review` へ戻す手順は無い（`skills/analysis-auto/SKILL.md` を読んだ）。#138 の本文は原因を「review が任意だから」と書いていたが、誤りだったので訂正した。
- [docs/PRD.md](../PRD.md) は review を守る核に入れていない。review をしたかどうかは `{id}_reviews.yaml` に残り、status には残らない（PRD と `design_io review-batch` を読んだ）。
- `review-batch` が受け付ける遷移先は `VALID_TRANSITIONS[in_review]` で決まる（`skills/_shared/design_io.py` を読んだ）。`analyzing` の行を変えても影響しない。

## Problem

- 課題1: 分析者が既定の巡回で分析を終えても、reflection で結論の status に閉じられない。巡回が毎回同じ所で止まる。
- 課題2: 閉じるために、結果を見る必要の無いレビューを挟むことになる。status と `{id}_reviews.yaml` が実際に起きていないレビューを表す。
- 課題3: 遷移表と skill の文書が食い違っていて、どちらを正とすればよいか読む人に分からない。

扱わない範囲: レビューを分析の後に必ず行う運用にするかどうか（PRD の守る核の変更になる）。`analyzing → revision_requested` の辺。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析の前にだけ review を行う巡回で、reflection から結論の status に閉じられる | Must | - | - | 課題1 |
| M2 | 遷移表と skill の文書が同じことを言う | Must | - | - | 課題3 |
| W1 | status が実際に起きたことを表す | Want | 解決 | 高（人間） | 課題2 |
| W2 | 変える所と巡回の手順が少なく、シンプルである | Want | 費用 | 高（人間） | 人間の発言（シンプルさを重視する）、YAGNI |

| Must | A: 結果を見た後のレビューを必須にする | B: analyzing から結論の status への辺を足す | C: 表は変えず、analyzing → in_review → 結論と2回遷移させる | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（巡回に review を足す） | 満たす | 満たす | 満たさない |
| M2 | 満たす（reflection の注記を直す） | 満たす（図と注記を直す） | 満たす（reflection の注記を直す） | 満たさない |

| Want | A | B | C |
|---|---|---|---|
| W1 | レビューが毎回本当に行われるので、status は起きたことを表す | 結果を見た後のレビューをしたときだけ `in_review` を経る。status は起きたことを表す | 誰もレビューしていないのに `in_review` を経る。見せかけの状態を作る儀式になる |
| W2 | 表は変えないが、巡回が毎回 review を1回挟み、分析者が判断で止まる回が増える | 表に辺を3本足し、図と注記を直す。巡回の手順は増えない | 表は変えないが、reflection に遷移を2回呼ぶ手順を足す |

- 差がつく基準: W1 と W2。M1 と M2 は「何もしない」以外のすべての案が満たす。
- 感度: W2 を低にし、結果を見た後のレビューを守る核に入れるなら A になる。W1 を低にしても、W2 で B が残る。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 巡回が重くなり、分析者がレビューを形だけで通す | 抑えられない |
| B | 結果を誰にも見せずに結論が閉じる。レビューをしたかどうかは status から読めない | `{id}_reviews.yaml` に残る。reflection は、結果を見てもらいたいときの `/analysis-review` を任意として案内する |
| C | 1回目の遷移の後に止まると、誰もレビューしていない `in_review` の分析設計が残る | 手順の文だけ |

## Decision

`VALID_TRANSITIONS` の `analyzing` の行に `supported`・`rejected`・`inconclusive` を足す（人間の判断、2026-11-22）。`analyzing → in_review`（結果を見た後のレビュー）は任意として残す。決め手は W1 で、W2 でも B が最も小さい。

- `/analysis-reflection` は `analyzing` から結論の status へ直接遷移させる。結果を見た後の `/analysis-review` は任意で、使ったときは `in_review` を経る。
- `/analysis-design` の Status Flow と [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の状態遷移ガードの記述を、表に合わせて直す。
- `review-batch` が受け付ける遷移先は変えない。

## Consequences

### Positive

- 既定の巡回が reflection で止まらずに結論の status へ閉じる。
- 遷移表、`/analysis-design`、`/analysis-reflection`、ARCHITECTURE が同じことを言う。
- pre-write hook も同じ表を使うので、直接の書き込みにも同じ規則が働く。

### Negative

- 結果を誰にも見せずに結論を出せる。結果を見た後のレビューは分析者の判断に任せる。status だけを見て、レビューを経たかどうかは分からない。
- `analyzing` から行ける status が増えるので、モデルが分析を終えていない分析設計を結論へ遷移させても表は拒まない。止めているのは、`/analysis-reflection` が結論と遷移を分析者に聞く手順だけである。

## Alternatives considered

評価の前に落とした案は無い。

## Related

- Epic: [#146](https://github.com/etoyama/insight-blueprint-skills/issues/146)、[epic-19](../design/epic-19-direct-conclusion.md)
- Stories: [#147](https://github.com/etoyama/insight-blueprint-skills/issues/147)
- 不具合: [#138](https://github.com/etoyama/insight-blueprint-skills/issues/138)
