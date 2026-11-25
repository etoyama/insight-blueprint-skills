# ADR-0054: review は結果も対象にし、review コメントを分析ノートと論点ツリーに出す

## Status

Accepted

## Context

Epic 33（[#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[DesignDoc](../design/epic-33-verdict-on-record.md)）の初版で決めた。
人間が ib-notebook の実データ（テーマ FRN）で使用感を確かめたとき（2026-11-25）、reflection が結果の review として勧めた `/analysis-review` について、「レビューって何してくれるの？」と聞き返した。
記録した7件の review コメントは、どれも分析設計の項目へのもので、分析ノートにも論点ツリーにも出なかった（[#237](https://github.com/etoyama/insight-blueprint-skills/issues/237) の F19 と F21）。

比較の土台にした事実（main 09fc48a）。

- review コメントが指せる対象（`ALLOWED_TARGET_SECTIONS`、`skills/_shared/design_io.py`）は、分析設計の12項目の閉じた集合である（コードを読んだ）。
- `review-batch` は、状態が `in_review` か `revision_requested` のときだけ記録できる。結果の review は `analyzing → in_review` に戻してから記録する（[ADR-0029](0029-analyzing-reaches-conclusion-directly.md)、`skills/analysis-review/SKILL.md` を読んだ）。
- `/analysis-revision` は、review コメントが指す分析設計の項目を `design_io update` で直す（`skills/analysis-revision/SKILL.md` を読んだ）。
- `{id}_reviews.yaml` を読むのは、`design_io` と、それを呼ぶ `/analysis-revision` と `/knowledge-extract` だけである。分析ノート・レポート・論点ツリー・reflection は読まない（`grep` で確かめた）。
- `ReviewBatch` と `BatchComment` は知らない項目を拒む（`extra="forbid"`。`src/insight_blueprint/models/review.py` を読んだ）。
- 論点ツリーの HTML は分析ノートを含み、`/tree-upload` で外へ送れる。送る前に KEEP ゲートで承認を待つ（[ADR-0037](0037-tree-upload-sends-the-design-notes.md)）。
- 分析を始めた検証の分析設計は、検証仮説・判定の基準・意図を変えない（[ADR-0053](0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)）。

## Problem

- 課題1: 結果の review がnotebook・verdict・図を指せない。notebook が基準を正しく写したかを、どの観点も拾わない。分析者は何を見てくれるのかを聞き返す。
- 課題2: ADR-0053 の固定で、結果の review の `revision_requested` から検証仮説を直す道が閉じる。何を直すのかを決めないと、revision が行き止まる。
- 課題3: review コメントは `{id}_reviews.yaml` にだけ残る。読み手には判定だけが届く。固定で直せずに残った review コメントが見えないと、固定の意味が半分になる。

扱わない範囲: review を必須にするか（ADR-0029 のまま任意）。review コメントへの対応の状況（`{id}_revision.yaml`）を出すこと。

## Decision Analysis

決めることは2つある。review の対象（D1）と、review コメントをどこに出すか（D2）。
重みを「Claude の推測」としたものは、人間が案を選んだ時点で追認している。

### D1: review の対象

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 結果の review の `revision_requested` に、直せるものがある | Must | - | - | 課題2 |
| W1 | notebook・verdict・図への review コメントを、対象つきで記録できる | Want | 解決 | 高（人間。F19 を Epic に入れた） | 課題1 |
| W2 | 分析者が覚える入口が増えない | Want | 費用 | 中（Claude の推測） | F19 |
| W3 | 保存済みの `{id}_reviews.yaml` が読める | Want | 費用 | 高（Claude の推測） | ADR-0047 |

| Must | A. 広げない（何もしない） | B. 同じ skill と同じ batch に対象を足す | C. 別の skill と別のファイルに分ける |
|---|---|---|---|
| M1 | 満たさない（結果そのものを指せず、直せるのは固定していない分析設計の項目だけになる） | 満たす | 満たす |

| Want | B | C |
|---|---|---|
| W1 | 記録できる。閉じた集合に3つ足す | 記録できる |
| W2 | 入口は `/analysis-review` のまま | skill が1つ増える |
| W3 | 読める。項目を足すだけである | 読める。ただし、表示する側が2つのファイルを読む |

- 差がつく基準: W2 と、W3 の読むファイルの数。
- 感度: どの重みを動かしても B のまま変わらない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | F19 が残る | なし |
| B | 1つの skill が設計と結果の両方を見て、観点が長くなる | verdict の有無で観点を切り替える |
| B | notebook を直して回し直すと、結果を見てからコードを変える道になる | 直すのは review コメントが指した所だけにする。線の定数は `comparison` から写し直す |
| C | 入口と記録が2つに割れる | なし |

### D2: review コメントをどこに出すか

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 分析ノートを読んだ人が、review コメントがあったと分かる | Must | - | - | 課題3 |
| W1 | 判定を見る所で、review コメントに気づける | Want | 解決 | 高（Claude の推測） | F21 |
| W2 | 外へ出る文書に、review コメントが意図せず載らない | Want | 費用 | 中（Claude の推測） | ADR-0019 |
| W3 | 作る量が小さい | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | A. 出さない（何もしない） | B. 分析ノートに節 | C. B と、論点ツリーに件数 | D. C と、レポートにも出す |
|---|---|---|---|---|
| M1 | 満たさない | 満たす | 満たす | 満たす |

| Want | B | C | D |
|---|---|---|---|
| W1 | 分析ノートを開かないと気づかない | 論点ツリーで、判定の横に件数が出る | レポートでも気づく |
| W2 | 論点ツリーの HTML は分析ノートを含むので、`/tree-upload` で外へ出る | B と同じ | レポートは `/report-export` で読み手に届く。データ由来の文が増える |
| W3 | 読む道が1つと、節が1つ | B に1行足す | レポートの型と escape の検査まで触る |

- 差がつく基準: W1 は D、C、B の順で、W3 は B、C、D の順である。
- 感度: W1 を最優先にすれば D に変わる。レポートは別の Epic に回せる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | F21 が残る | なし |
| B | 判定だけ見る人に届かない | なし |
| C | 分析を始める前に直した review コメントも件数に入り、未解決に見える | 件数は、分析を始めた後の review batch だけを数える |
| D | 範囲が広がり、Story が1本増える | 別の Epic に回す |

## Decision

人間が選んだ（2026-11-25、Epic 33 の DesignDoc 初版のセッションで直接）。D1 は B、D2 は C である。決め手は、D1 が W2、D2 が W1 と W3 の釣り合いである。

1. review コメントの対象に、`notebook`・`verdict`・`figures` を足す。分析設計の12項目はそのまま残す。
2. `/analysis-review` は、verdict があるとき、結果の観点で読む。観点は次の5つである。支持の線・棄却の線・指標の判定が `comparison` と合うか。値と判定が食い違わないか。図の軸の説明と読み方。guardrail の合否。cell ごとの責務。批評の前に、何を読むかを分析者に言う。
3. 結果の review の `revision_requested` で直すのは、notebook（直して回し直す）と、分析設計の固定していない項目である。固定した項目（ADR-0053 の3）への review コメントは、分析設計を直さない。分析者は理由を付けて対応しないか、派生を作るかを選ぶ。
4. review batch は分析を始めた後に書かれたかどうかを、書かれた時点で持つ。分析の印の時刻と batch の時刻を比べて導かない（DesignDoc の Decision `a-batch-holds-whether-it-came-after-the-analysis`）。保存済みの batch は持たず、読める。
5. 分析ノートは「レビュー」の節に、すべての review batch を新しい順に出す。batch ごとに、時刻、分析を始めた後かどうか、review の後の状態、review コメントと対象を、書かれたとおりに出す。
6. 論点ツリーは分析設計の行に、分析を始めた後の review batch の review コメントの件数を出す。0件のときは出さない。
7. レポートには review コメントを出さない。

## Consequences

### Positive

- 分析者が、結果の review が何を読むかを、聞き返さずに分かる。
- notebook が基準を写しまちがえたとき、拾う観点がある。
- 読み手が判定と並んで review コメントを読める。固定で直せなかった review コメントも残って見える。
- 保存済みの `{id}_reviews.yaml` は手を入れずに読める。

### Negative

- 論点ツリーの HTML を `/tree-upload` で外へ出すと、review コメントの文も一緒に出る。止めるのは、今ある KEEP ゲートである。
- 分析ノートは review コメントへの対応の状況を出さない。直した review コメントと、残した review コメントが、同じ見え方になる。
- 保存済みの review batch は分析を始めた後かどうかを持たない。分析ノートはその表示を出さず、論点ツリーは件数に数えない。
- レポートだけを読む人には、review コメントが届かない。
- 1つの skill が設計の観点と結果の観点の両方を持つ。
- 結果の review の後に notebook を直して回し直すと、verdict が変わりうる。前の verdict は残らない。

## Alternatives considered

- **review コメントを journal の出来事として記録する** — journal は分析者の推論の記録で、review は別の人の批評である（`/analysis-review` の When NOT to Use）。記録を混ぜると、reflection が自分の推論と批評を分けて読めなくなる。

## Related

- Epic: [#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)、[docs/design/epic-33-verdict-on-record.md](../design/epic-33-verdict-on-record.md)
- Issues: [#237](https://github.com/etoyama/insight-blueprint-skills/issues/237)（F19、F21）
- [ADR-0029](0029-analyzing-reaches-conclusion-directly.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0037](0037-tree-upload-sends-the-design-notes.md)、[ADR-0052](0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md)、[ADR-0053](0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)
- Supersedes: なし
