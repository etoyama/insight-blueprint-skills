# ADR-0060: 試行の記録は、読み手が Claude ならモデルの ID を持つ

## Status

Accepted

## Context

Epic 34（[#249](https://github.com/etoyama/insight-blueprint-skills/issues/249)）は、論点ツリーの表示を変える前と後で引き継ぎの試行を取り、点を比べた。
[落ちた問いを直した後の記録](../handoff-trials/2026-11-26-after-the-gate-fixes.md)は、「前の記録はモデルのバージョンを残していないので、バージョンが同じかは確かめていない」と書いている。
Epic 34 の振り返り（#249 の最後のコメント、学びの 4）でこれを直すと決め、人間が反映する束 C に選んだ（2026-11-26）。

比較の前提にした事実と、確かめた方法は次のとおり。

- 保存済みの試行の記録は 54 件ある。`reader.name` は `sonnet (Claude Code 2.1.227)` か `sonnet (Claude Code 2.1.332)` の形で、haiku と opus も同じである（`grep -h "name:" docs/handoff-trials/*.yaml | sort | uniq -c` を実行した）。持っているのはモデルの呼び名と CLI のバージョンで、モデルの ID はどの記録にも無い。
- `sonnet` などの呼び名が指すモデルは、時期で変わる。2026-11-26 に `claude -p --model haiku --output-format json` を実行すると、応答の `modelUsage` のキーは `claude-haiku-5-5` だった。答えたモデルの ID はこの出力から読める。
- 試行の記録の型（`scripts/handoff_trial.py` の `Record` と `Reader`）は、知らないフィールドを拒む（`extra="forbid"`）。
- 過去の記録は書き換えない（[ADR-0035](0035-handoff-trial-records-keep-their-score.md)）。`tests/test_handoff_trial.py` の `test_a_kept_record_still_reads` は保存済みの記録をすべて今の型で読む。
- `Reader` に任意のフィールド `model` を足した型を仮に作り、54 件を読ませた。54 件とも読めた。
- 記録の型は Epic 18 の Decision `handoff-trial-scores-judgments-by-id` が定めた。Epic 18 は閉じている。

## Problem

- 課題1: 表示を変える前と後で、読み手のモデルが同じだったかを確かめられない。点が動いたとき、表示のせいかモデルのせいかを分けられない。
- 課題2: 記録の型を変えると、保存済みの記録が型に合わなくなりうる。書き換えれば、その時にどう記録したかを失う。

扱わない範囲: 保存済みの 54 件にモデルの ID を後から足すこと。人の読み手を記録で区別すること。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの記録を書き換えずに、今までどおり読める | Must | - | - | 課題2、ADR-0035 |
| W1 | モデルの ID の書き忘れを、道具が止める | Want | 解決 | 高（Claude の推測。人間が案A を選んだ） | 課題1 |
| W2 | 手続きと変更の量 | Want | 費用 | 中（Claude の推測） | YAGNI、[ADR-0012](0012-single-pr-scope.md) |

- 案A: `reader` に任意のフィールド `model` を足す。`record` に `--reader-model` を足し、読み手が Claude のときは渡さないと止まる。止めるのは `record` で、型は `model` の無い記録を通す。
- 案B: コードは変えない。手順の文書に、`--reader-name` にモデルの ID を書くと書く。
- 何もしない。

| Must | 案A | 案B | 何もしない |
|---|---|---|---|
| M1 | 満たす（54 件で試した） | 満たす | 満たす |

| Want | 案A | 案B |
|---|---|---|
| W1 | Claude の試行でモデルの ID を渡さないと、`record` が記録を書かずに止まる | 止めるものが無い。Epic 34 と同じ書き忘れが起きうる |
| W2 | 型に1行、`record` に引数1つと確かめ1つ、テスト、この ADR | 手順の文書の数行だけ |

- 差がつく基準: W1 と W2。
- 感度: W1 を低に置けば案B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | モデルの ID を持つ記録と持たない記録が混ざり、古い記録とは比べられないままになる | 手順の文書に、2026-11-26 までの記録は持たないと書く |
| 案A | `--reader-model` に、応答から読んだ ID ではなく、思い込みの ID を渡す | 手順の文書で、ID を応答の `modelUsage` から読ませる |
| 案B | 自由な文字列なので書き方が揃わず、後から並べて比べにくい | 書式の例を置くだけ |
| 何もしない | 次に表示を変えるときも、同じモデルで比べたかを確かめられない | 無い |

## Decision

案A を採る（人間の判断、2026-11-26）。決め手は W1 である。
Epic 18 の Decision `handoff-trial-scores-judgments-by-id` の記録の型を次のように改める。ここに書かない点はその Decision と ADR-0035 のままとする。

1. 試行の記録の `reader` は任意の `model` を持つ。値は答えたモデルの ID である（例: `claude-sonnet-5-5`）。
2. `record` は `--reader-model` を受け取る。読み手が Claude で `--reader-model` が無ければ、記録を書かずに止まる。
3. 型は `model` の無い記録を通す。2026-11-26 までの 54 件は書き換えない。
4. モデルの ID は `claude -p --output-format json` の応答の `modelUsage` から読む。手順は [docs/HANDOFF_TRIAL.md](../HANDOFF_TRIAL.md) の Step 2 と Step 5 に書く。

Epic 18 は閉じているので、DesignDoc には追記しない（[ADR-0009](0009-adopt-repo-template-flow.md)）。
plugin の振る舞いではなく開発用の道具を変えるので、Epic にせず単発の PR にする（ADR-0012。ADR-0035 と同じ扱い）。

## Consequences

### Positive

- 次に表示を変えるとき、前と後の読み手が同じモデルだったかを、記録だけで確かめられる。
- Claude の試行でモデルの ID を書き忘れると、`record` が止まる。

### Negative

- 2026-11-26 までの記録はモデルの ID を持たない。その記録と後の記録を比べるときは、今までどおり、同じモデルだったかを確かめられない。
- `record` は、渡された ID が実際に答えたモデルかを確かめない。応答から写すのは人か、試行を回すエージェントである。
- 型は、読み手が Claude で `model` の無い記録を拒まない。記録を手で書いて `model` を落としても、CI は気づかない（ADR-0035 の Negative と同じ穴）。
- 人の試行の記録にも `model: null` の行が出る。

## Alternatives considered

- **型の側で、読み手が Claude なら `model` を必須にする** — 保存済みの 54 件が型に合わなくなり、M1 を満たさない。
- **`reader.name` の文字列から、モデルの ID を読み取る決まりを足す** — 保存済みの記録の `name` は呼び名と CLI のバージョンしか持たず、読み取れる ID が無い。

## Related

- Epic: `docs/design/epic-18-question-tree.md`（Decision `handoff-trial-scores-judgments-by-id`）、`docs/design/epic-34-what-moved-the-answer.md`
- Issues: #249（振り返り、束 C）
- 関連: [ADR-0035](0035-handoff-trial-records-keep-their-score.md)、[ADR-0059](0059-the-handoff-trial-has-a-second-scenario-and-a-sixth-question.md)
