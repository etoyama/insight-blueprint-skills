# ADR-0067: 検証 hook は、journal の印を design_io が書いたとおりに保つ

## Status

Accepted

## Context

Epic 35（[#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[DesignDoc](../design/epic-35-hand-over-questions.md)）の Story 35.2（[#286](https://github.com/etoyama/insight-blueprint-skills/issues/286)）のレビューで見つけた。
[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) の 8 は、分析者への確認・分析者の答え・止めた理由の印（`metadata.asks_analyst`・`answers`・`stopped`）を、`design_io` の専用の命令だけが書くと決めた（US-4 AC 5）。
分析の段階は、この印から導く（[ADR-0061](0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) の 6）。

比較の土台にした事実。

- `design_io.append_journal_event` は3つの印を拒む。命令（`ask-analyst`・`answer-analyst`・`stop`）は、段階を確かめてから印を書く（テストで確かめた）。
- 実行エージェントは、journal を Write ツールで直接書く（`skills/analysis-notebook/SKILL.md` の Step 6 と design_io Reference の注）。`/analysis-journal` も同じ。
- 検証 hook（`hooks/validate-design.py`）が見るのは、分析設計と論点ツリーだけで、journal は見なかった（読んだ）。
- hook は Write・Edit・MultiEdit のツールの書き込みでだけ動く。`design_io` の Python からの書き込みでは動かない。
- hook の写しに journal の検査を足して試した（scratchpad、2026-11-27）。印の無い出来事を Write や Edit で足すのは通った。新しい journal の Write、命令が印を書いた後の追記も通った。印を手で足す Write、止めた出来事を消す Edit、確認の本文を書き換える Edit は止まった。

## Problem

- 課題1: 手で `asks_analyst: true` を書けば、段階の検査を通らずに確認待ちになる。印を書き換えれば、答えの付き先が変わる。
- 課題2: 止めた出来事を Edit で消すと、止めた分析が黙って再開する（ADR-0064 の 7 に反する）。
- 課題3: 今は SKILL.md の文だけが、手の書き込みから印を守っている。

扱わない範囲: 実行エージェントが journal を手で読んでから書き戻すまでの間のロック（[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md) の分担で扱う。Story 35.7 に渡す）。印の無い出来事の形を検査すること（journal は形を持たない）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | notebook と `/analysis-journal` が、印の無い出来事を足す道を止めない | Must | - | - | ADR-0062 の 2、PM の指示 |
| W1 | 手で印を足す・消す・書き換えることを止める | Want | 解決 | 高（人間） | 課題1、課題2、US-4 AC 5 |
| W2 | hook の守る範囲を広げる費用（ADR が1本、壊れた YAML の journal が書けなくなる） | Want | 費用 | 中（Claude の推測） | PM の指示 |

- 案A: hook が journal の Write・Edit・MultiEdit も見て、印を持つ出来事の並びが変わる書き込みを止める。
- 案B: 今のまま（API で拒むことと、SKILL.md の文）にする。Test Design Matrix に「API の道」と書き、issue を立てる。
- 何もしない: 案B から、issue と Matrix の注記を除いたもの。

| Must | 案A | 案B | 何もしない |
|---|---|---|---|
| M1 | 満たす（試した） | 満たす | 満たす |

| Want | 案A | 案B |
|---|---|---|
| W1 | 止める。ツールの書き込みのどの道からも、印は変わらない | 止めない。文に頼る |
| W2 | ADR が1本増える。壊れた YAML の journal は書けなくなる（守りが増える） | issue が1件増える |

- 差がつく基準: W1 と W2。
- 感度: W2 を高にして、hook の範囲を広げたくないと見るなら、案B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | 壊れた journal を手で直す途中の書き込みが止まる | 止めたときの文が YAML の誤りを出す。分析設計と同じ扱い |
| 案A | hook の不具合で journal が書けなくなる（fail-closed） | 検査は純粋な関数で、テストで守る |
| 案B | 手で印を足し消しして、段階が嘘になる | 抑えにくい |
| 何もしない | 案B と同じで、記録にも残らない | 無い |

## Decision

案A を採る（人間の判断、2026-11-27）。決め手は W1 である。

1. 検証 hook は `.insight/designs/*_journal.yaml` の Write・Edit・MultiEdit も検査する。
2. 検査するのは1つだけである。`metadata` に `asks_analyst`・`answers`・`stopped` のどれかを持つ出来事は、書き込みの前と後で同じでなければならない。印を持つ出来事を足す、消す、書き換える書き込みは止める。印の無い出来事は、足しても直しても通す。
3. 書き込みの後が journal として読めない（YAML でない、`events` がリストでない）なら止める。ディスク上の journal が読めないときは、印を持たないものとして比べる。
4. 印の一覧は `insight_blueprint.models.journal.JOURNAL_MARKS` の1か所に置き、hook の検査（`validate.validate_journal_change`）と分析の段階の規則が同じ一覧を読む。
5. `design_io` の命令は Python から書くので、hook を通らない。印を書く道は命令だけになる。

## Consequences

### Positive

- US-4 AC 5 が、文の約束ではなく仕組みで守られる。
- 止めた分析が手の書き込みで再開することが無くなる。

### Negative

- journal も fail-closed になる。hook の内側の不具合で、journal の手の書き込みが止まりうる。
- 壊れた YAML の journal は、ツールで書けなくなる。前は通っていた。
- `design_io.write_journal` のような Python の道は、hook を通らない。そこは `append_journal_event` の拒否と、命令の段階の検査に頼る。
- 印を持つ出来事を手で直したいときは、直せない。誤った確認は、答えるか止めるかで閉じる。

## Alternatives considered

- **journal の全体に形（pydantic のモデル）を持たせる** — journal は skill が自由な metadata を書く記録で、形を決めると、出来事の種類ごとの metadata の全部に波及する。守りたいのは印だけである。

## Related

- Epic: [#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[docs/design/epic-35-hand-over-questions.md](../design/epic-35-hand-over-questions.md)（US-4 AC 5）
- Story: [#286](https://github.com/etoyama/insight-blueprint-skills/issues/286)
- [ADR-0061](0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md)、[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)、[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md)
