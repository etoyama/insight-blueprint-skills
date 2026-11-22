# ADR-0035: 引き継ぎの試行の記録は、その時点の鍵での採点として残し、CI で採点し直さない

## Status

Accepted

## Context

Epic 18 の Decision `handoff-trial-scores-judgments-by-id`（[docs/design/epic-18-question-tree.md](../design/epic-18-question-tree.md)）は、引き継ぎの試行の道具と記録の形を決めた。
試行の記録は1回1ファイルで `docs/handoff-trials/` にコミットする。
決めたのはそこまでで、コミットした記録を CI で採点し直すことは決めていない。
ただ Story 18.8 の実装は `scripts/handoff_trial.py` に `rescore` を置き、`tests/test_handoff_trial.py` で記録をすべて今の鍵で採点し直していた。
Epic 18 のゲートの thermos（PR #128 のコメント、F9）がこの経路を挙げ、残すかどうかを人が決めることになった（#144）。

比較の前提にした事実と、確かめた方法は次のとおり。

- `rescore` を呼ぶのはテスト3本だけである（`grep -rn rescore` を実行した）。
  記録をすべて採点し直すテスト（`test_every_kept_record_has_the_score_its_answers_get`）、記録が1件以上あることを確かめるテスト（`test_at_least_one_record_is_kept`）、記録と鍵の段階が食い違えば `rescore` が止まることを確かめるテスト（`test_a_record_for_another_stage_than_the_key_is_refused`）である。
- `record` は記録の段階に鍵の段階を書く（`scripts/handoff_trial.py` の `_record` を読んだ）。段階の食い違いは古い記録を今の鍵で採点し直すときにしか起きない。
- 記録は3件あり、どれも 2026-11-21 の Claude の試行である（`docs/handoff-trials/` を見た）。
- #137 で q5 の鍵が変わると、3件の採点し直しがそろって落ちる（#144 の人間のコメント）。
- `prompt` サブコマンドの中身は問いの文と HTML をつなぐだけだが、手順の文書（[docs/HANDOFF_TRIAL.md](../HANDOFF_TRIAL.md)）の Step 2 がこれを使っている（文書を読んだ）。
- 人の時間を記録する経路（`Minutes`）は、人の記録がまだ無いので使われていない。Decision は人の試行で時間を必須にしている。

## Problem

- 課題1: 鍵を直すたびに、過去の記録が CI を落とす。直すには、過去の記録の正誤を書き換えるか、記録を消すしかない。どちらも、その時に読み手がどう答えどう採点されたかを失う。
- 課題2: 記録は試行を繰り返して読み手の答えを後から並べて比べるために残している（Decision の基準 C）。比べる場所を失ってはいけない。

扱わない範囲: q5 の鍵の中身（#137）。`build`・`score`・fixture・手順の形。人の試行をいつ回すか。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | US-7 の AC 3（記録の型、人の時間）を満たし続ける | Must | - | - | Epic 18 の US-7 |
| W1 | 使っていない経路を減らす | Want | 費用 | 低（人間） | #144 |
| W2 | 鍵を直しても過去の記録が CI を落とさない | Want | 解決 | 高（人間） | 課題1 |
| W3 | 記録を後から並べて比べられる | Want | 解決 | 高（人間、Decision の基準 C） | 課題2 |

- A: `rescore` と、コミットした記録を採点し直すテストを消す。記録は `docs/handoff-trials/` にコミットし続け、各記録はその時点の鍵での採点として残す。`prompt` と `Minutes` は残す。
- B: A に加えて `prompt` を消す。
- C: 記録もコミットしない。結果は DesignDoc の Story Timeline に要約で残す。
- 何もしない: `rescore` とテストを残す。

| Must | A | B | C | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす（型は残る） | 満たす |

| Want | A | B | C | 何もしない |
|---|---|---|---|---|
| W1 | `rescore` とテスト3本が消える。数十行 | A より `prompt` の2行が多く消えるが、手順の文書の Step 2 を書き換えることになる | 記録とテストが消え、最も減る | 減らない |
| W2 | 落ちない | 落ちない | 落ちない（記録が無い） | #137 で3件がそろって落ちる |
| W3 | 残る | 残る | 失う。閉じた Epic の DesignDoc には追記しないので、Epic 18 の後の記録を置く場所が無い | 残るが、鍵を直すたびに過去の正誤を書き換えることになる |

- 差がつく基準: W2 と W3。W1 の差は数十行から百数十行で、重みは低い。
- 感度: W3 を低に置けば C に変わる。W1 を高に置けば B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 鍵が変わると、古い記録と新しい記録の採点の基準がずれる | 記録はその時点の鍵での採点だと手順の文書に書く。鍵の変更は git の履歴で追える |
| B | A と同じ。加えて、手順の文書が `cat` の並びを持つことになる | A と同じ |
| C | 試行の答えと `note` が残らず、読み手がどこで迷ったかを後から読めない | Story Timeline の要約だけ |
| 何もしない | 鍵を直す PR が、過去の記録の正誤を書き換える | なし |

## Decision

A を採る（人間の判断、2026-11-22。記録は #144 のコメント）。決め手は W2 で、W3 も残る。
Epic 18 の Decision `handoff-trial-scores-judgments-by-id` を次のように改める。ここに書かない点はその Decision のままとする。

- 試行の記録は、`record` が記録を書いた時点の鍵での採点として残す。CI は記録の正誤を今の鍵で採点し直さない。
- `scripts/handoff_trial.py` の `rescore` を消す。あわせて、`rescore` だけを確かめていたテスト3本を消す（`test_every_kept_record_has_the_score_its_answers_get`、`test_at_least_one_record_is_kept`、`test_a_record_for_another_stage_than_the_key_is_refused`）。
- 記録は1回1ファイルで `docs/handoff-trials/` にコミットし続ける。`prompt` サブコマンドと `Minutes` は残す。
- 手順の文書（[docs/HANDOFF_TRIAL.md](../HANDOFF_TRIAL.md)）の Step 5 に、記録はその時点の鍵での採点だと書く。

Epic 18 は閉じているので、DesignDoc には追記しない（[ADR-0009](0009-adopt-repo-template-flow.md)）。
DesignDoc の Test Design Matrix の Story 18.8 にある「`TestRecord` は `docs/handoff-trials/` の記録を採点し直す」は、この ADR で改めたものとして読む。
plugin の振る舞いではなく開発用の道具を変えるので、Epic にせず単発の PR にする（[ADR-0012](0012-single-pr-scope.md)）。

## Consequences

### Positive

- 鍵を直す PR が過去の記録に触れずに済む。#137 で q5 の鍵を変えても CI は落ちない。
- 記録の答えと `note` は残り、試行を後から並べて比べられる。

### Negative

- 鍵が変わると、古い記録と新しい記録の採点の基準がずれる。記録を並べて比べるとき、正誤をそのまま比べられるとは限らない。どの鍵で採点したかは、記録の日付と git の履歴から読む。
- コミットした記録が型に合うことも CI で確かめなくなる。記録は `record` が型を通して書くので、手で書き換えない限り型は崩れない。

## Alternatives considered

- **`prompt` を消し、`Minutes` も消す** — `Minutes` は US-7 の AC 3 が求める人の時間を記録する経路で、M1 を満たさない。比較の前に落とした。

## Related

- Epic: `docs/design/epic-18-question-tree.md`（Decision `handoff-trial-scores-judgments-by-id`）
- Issues: #144、#137
- PRs: #128（Epic 18 のゲートの thermos、F9）
