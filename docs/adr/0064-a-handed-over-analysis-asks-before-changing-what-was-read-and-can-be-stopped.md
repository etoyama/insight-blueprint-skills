# ADR-0064: 任せた分析は、読んだ内容を変える前に聞き、1つずつ止められる

## Status

Accepted（[ADR-0005](0005-selective-autonomous-chaining.md) のゲートに、任せた後の確認を足す）

## Context

Epic 35（[#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[DesignDoc](../design/epic-35-hand-over-questions.md)）の初版で決めた。
分析者は任せる前に1回、分析設計を並べて読む（[ADR-0063](0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md)）。
その後は実行エージェントが走り、分析者は席を外す。[#250](https://github.com/etoyama/insight-blueprint-skills/issues/250) は任せた後に確認する条件を4つ挙げた
（分母か粒度を変えないと進めない、新しいデータソースが要る、費用が上限を超える、データや結果を外へ送る）。

比較の土台にした事実。

- premortem は抽出の行数を見積もり、`.insight/config.yaml` の `premortem.static_rows_high`（既定 1,000 万行）を超えると `HIGH` で止まる（`skills/premortem/lib/risk_evaluator.py`、`.insight/config.example.yaml`）。金額や時間の上限は無い。
- まとめて任せる流れでは、premortem は任せる前に回る（手で通したとき、3つぶんを1回で回せた）。任せた後に費用が変わるのは、抽出を変えたときである。
- 許可リストに無いパッケージ、宣言していないデータソース、外へ送ることは、今も KEEP ゲートで止まる（ADR-0005、[ADR-0016](0016-approval-before-external-send.md)）。
- journal の出来事は種類ごとに自由な項目（metadata）を持てる。未解決の問いは、`conclude` の `metadata.resolves` に挙がっていない `question` である（`skills/_shared/design_note_read.py`）。
- journal の出来事の種類を足すと、種類の一覧を持つ所の全部に波及する（`hearing` を足した [ADR-0028](0028-hearing-is-its-own-journal-event.md)）。
- 実行エージェントは自分の journal だけを書く（[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)）。
- 図書館の合成シナリオで、journal に仮の印を置き、確認待ちと止めたを導けた（1回）。
- 確かめていないこと: 確認待ちが実際にどのくらい出るか（手で通した2回では0回）。

## Problem

- 課題1: 任せた後に、実行エージェントが分析者の読んでいない内容で走ると、実行の前に読んで直せるという約束（[ADR-0007](0007-upstream-judgment-gates.md)）が守られなくなる。何でも聞くと、止まる回数が戻る。
- 課題2: 確認を待つ分析と、分析者が止めた分析を書く所が無い。止めた分析は進行中のまま残り、理由は誰にも読めない。
- 課題3: 「費用が上限を超える」の上限が、何の値かが決まっていない。

扱わない範囲: 前の分析の記録にある注意が、次の分析の抽出に当たったときの確認（次の Epic）。止めた分析を、同じ分析設計のまま再開すること。

## Decision Analysis

確認に出す条件。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析者が読んでいない抽出・分母・粒度で、データに触らない | Must | - | - | ADR-0007 |
| W1 | 条件を、実行エージェントが迷わず当てはめられる | Want | 解決 | 高（Claude の推測） | 課題1、ADR-0005 の Negative |
| W2 | 新しく置く設定が少ない | Want | 費用 | 中（Claude の推測） | 課題3、YAGNI |

- 案A: 条件を1つの原則にする。任せる前に読んだ内容を変えないと進めないなら、止まって聞く。費用は新しい値を置かず、今ある行数の線を使う。
- 案B: #250 の4条件を並べ、費用の上限を新しい設定として置く。
- 何もしない（任せた後は聞かない）。

| | 案A | 案B | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない |
| W1 | 「読んだ内容を変えるか」の1問で、分析設計の項目と照らせる | 4条件を個別に当てる。費用は実行エージェントが見積もる | - |
| W2 | 置かない | 1つ置く。データソースの種類ごとに測り方が違う | - |

- 差がつく基準: W1 と W2 の両方で案A である。
- 感度: 金額の上限が要る利用があれば、案B になる。

記録の置き場。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M2 | 止めた理由と、何を確認待ちかが、記録から読める | Must | - | - | 課題2 |
| M3 | 実行エージェントが、自分の持ち場の外を書かない | Must | - | - | ADR-0062 |
| W3 | 書き方が1つに決まり、分析の段階を導く規則が壊れにくい | Want | 解決 | 高（Claude の推測） | [ADR-0061](0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| W4 | 変える所が少ない | Want | 費用 | 中（Claude の推測） | YAGNI |

- 案C: その分析設計の journal に、今ある種類の出来事（`question`、`decide`）で書く。印は metadata に置き、`design_io` の専用の命令だけが書く。
- 案D: 論点ツリーの YAML に書く。
- 案E: journal に新しい種類の出来事を足す。
- 何もしない。

| | 案C | 案D | 案E | 何もしない |
|---|---|---|---|---|
| M2 | 満たす | 満たす | 満たす | 満たさない |
| M3 | 満たす | 満たさない。実行エージェントが論点ツリーを書くことになる | 満たす | - |
| W3 | 専用の命令が形を決める。印は metadata の決まりで、種類を見ても分からない | - | 種類を見れば分かる | - |
| W4 | 命令3つと、導く規則 | - | 種類の一覧を持つ分析ノート・レポート・journal の skill・用語集に波及する | - |

- 差がつく基準: W4 である。
- 感度: W3 を最優先にすると案E になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | 行数は少ないが高い抽出を止められない | 単独の実行と同じ穴で、この決定では塞がない |
| 案B | 見積もりが外れて、上限の意味が無くなる | 抑えにくい |
| 案C | 確認の `question` が、未解決の問いに混ざる | 答えの付いた確認は、未解決の問いに数えない |
| 案C | 止めた分析設計の状態は `analyzing` のまま残る | 進捗と現在地は分析の段階を読むので、止めたと出る |
| 案E | 種類の一覧の直し漏れ | 抑えにくい |
| 何もしない | 課題1〜3 が残る | 無い |

## Decision

条件は案A、記録の置き場は案C を採る（人間の判断、2026-11-27）。決め手は、条件が W1 と W2、置き場が W4 である。

1. 実行エージェントは、任せる前に分析者が読んだ内容を変えないと進めないとき、データに触る前に止まり、分析者への確認を自分の journal に書いて、対話エージェントに戻る。読んだ内容とは、分析設計の対象・粒度・分母・抽出・データソース・主指標・判定の基準である。
2. 確認を待つ間、止まるのはその分析だけである。対話エージェントはほかの実行エージェントを止めずに、分析者に確認を聞く。
3. 分析者の答えは、対話エージェントがその分析設計の journal に書く。答えは、どの確認への答えかを持つ。答えで分析設計が変わるときは、対話エージェントが分析設計を直す。抽出を変えたら、実行の前に premortem をやり直し、`HIGH` 以上なら今のゲートで止まる。
4. 費用の上限は新しく置かない。任せる前と、抽出を変えた後の premortem が、今ある行数の線で見る。
5. 許可リストに無いパッケージ、宣言していないデータソース、外へ送ることは、今の KEEP ゲートのまま止まる。
6. 分析者は進行中の分析を1つだけ止められる。任せる前の確認で、任せないと決めた分析設計も同じように止める。対話エージェントが、止めた理由をその分析設計の journal に書く。
7. 止めた分析は再開しない。やり直すときは、派生で別の分析設計を作る。止めた分析設計の状態は変えない。
8. 記録の形は次のとおり。印は `design_io` の専用の命令だけが書き、skill は metadata を手で書かない。
   - 分析者への確認: `question` の出来事。本文は何を変えないと進めないか。印は `metadata.asks_analyst`。
   - 分析者の答え: `decide` の出来事。本文は答え。`metadata.answers` に、確認の出来事の id を持つ。
   - 止めた理由: `decide` の出来事。本文は理由。印は `metadata.stopped`。
9. 答えの付いた分析者への確認は、未解決の問いに数えない。

## Consequences

### Positive

- 実行エージェントが当てる条件は1つで、分析設計の項目と照らせる。
- 止めた理由と、確認とその答えが、その分析の journal に残り、分析ノートで読める。
- journal の出来事の種類は増えない。

### Negative

- 条件を守るかは、実行エージェントが skill に従うことに頼る（ADR-0005 の Negative のまま）。照らす相手（対象・粒度・分母）が記録にあるので、守りやすくなる（[ADR-0066](0066-a-design-may-state-its-population-grain-and-denominator.md)）。
- 行数は少ないが高い抽出は、止まらない。
- 止めた分析設計は `analyzing` か `in_review` のまま残る。状態だけを読む所（分析設計の一覧など）は、止めたと分からない。
- 印は metadata の決まりである。専用の命令を通さずに journal を手で書くと、分析の段階を正しく導けなくなる。
- 止めた分析は再開できない。同じ問いをやり直すと、分析設計が1つ増える。

## Alternatives considered

- **止めた分析設計を terminal status にする** — 探索は `explored`、検証は判定の3つでだけ終わる（[ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md)）。結果の無い分析を、そのどれかにはできない。状態の値を足す案は ADR-0061 で落とした。

## Related

- Epic: [#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[docs/design/epic-35-hand-over-questions.md](../design/epic-35-hand-over-questions.md)（US-4）
- Issues: [#250](https://github.com/etoyama/insight-blueprint-skills/issues/250)
- [ADR-0005](0005-selective-autonomous-chaining.md)、[ADR-0007](0007-upstream-judgment-gates.md)、[ADR-0016](0016-approval-before-external-send.md)、[ADR-0028](0028-hearing-is-its-own-journal-event.md)、[ADR-0061](0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md)、[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)
