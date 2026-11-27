# ADR-0061: 論点ツリーの決定は一緒に任せた論点を持てて、分析の段階は記録から導く

## Status

Accepted（[ADR-0026](0026-analysis-auto-walks-the-question-tree.md) の「1回の巡回は論点を1つ調べる」を置き換える）

## Context

Epic 35（[#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[DesignDoc](../design/epic-35-hand-over-questions.md)）の初版で決めた。
分析者は互いの結果を待たない論点をまとめてエージェントに任せたい（[#250](https://github.com/etoyama/insight-blueprint-skills/issues/250)）。
ADR-0026 は巡回を「論点を1つ調べるひと回り」と決め、決定と現在地はその前提で作られている。

比較の土台にした事実（main 9d26c39、図書館の合成シナリオに、互いを待たない分析設計を2つ足して試した。各1回）。

- `TreeDecision` は論点を1つ指す（`node_id`）。`tree_read.position` は最新の決定の論点に結んだ分析設計だけを見る。
- 片方の分析設計を `explored` にすると、もう片方が `analyzing` でも、`position` は `concluded` と返した。
- `TreeDecision` に既定値つきの項目を足しても、保存済みの論点ツリーは読め、書き戻しても同じ内容になった。
- 決定が指す論点の並びを読み、分析設計の状態と journal だけから、進行中・確認待ち・止めた・振り返り待ち・終わったを導けた（試作。確認待ちと止めたは journal に仮の印を置いた）。
- 論点ツリーの YAML を変えずに、同じ回に論点ごとの決定を並べても、今の検査は通る。`position` は最後の1つしか見ない。
- `DesignStatus` と `TERMINAL_STATUSES` を参照する所は 10 ファイル 58 か所ある（grep）。
- 実データで手で通したとき、計算が終わって振り返りを待つ分析も、ページには「検証中」と出た。
- 確かめていないこと: 実行エージェントが journal に確認を書く運用が回るか（[ADR-0064](0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) で扱う）。

## Problem

- 課題1: 分析者が3つの論点を任せても、記録に残るのは1つである。残りは「次に調べる論点」にも、`/analysis-auto` の再開先にも出ない。
- 課題2: 席を外した分析者が戻っても、どの分析が走り、どれが確認を待ち、どれが止まり、どれが計算を終えたかを見分けられない。
- 課題3: 進み具合を出す所は画面・コマンド・レポート・skill の文に分かれている。Epic 34 では決まりを画面だけに入れ、ほかに入れ忘れた。
- 課題4: 「ツリーの決定」という語は、何のツリーかが読めない（人間の指摘、2026-11-27）。

扱わない範囲: 確認と止めた理由の記録の形（ADR-0064）。誰が書くか（[ADR-0062](0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md)）。前の分析が終わったら始める分析（次の Epic）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの論点ツリーと分析設計がそのまま読める | Must | - | - | 不変条件（正本は YAML） |
| M2 | 進行中・確認待ち・止めた・振り返り待ちを見分けられる | Must | - | - | 課題2 |
| W1 | 任せた範囲を1つの記録から読め、画面・コマンド・レポートが同じ規則を使える | Want | 解決 | 高（人間が案A を選んだ） | 課題1、課題3 |
| W2 | 前の分析を待つことを、後から足せる | Want | 解決 | 中（Claude の推測） | #250 |
| W3 | 変える所が少ない | Want | 費用 | 中（Claude の推測） | YAGNI |

- 案A: 論点ツリーの決定が次に調べる論点に加えて、一緒に任せた論点を持つ。分析の段階は保存せず、分析設計の状態と journal から導く。
- 案B: 論点ツリーに、決定とは別の「任せた範囲」の一覧を足す。分析の段階は案A と同じく導く。
- 案C: YAML は変えない。同じ回に、論点ごとの決定を並べる。
- 案D: 範囲は案A。分析の段階は分析設計の状態の値を増やして保存する。
- 何もしない。

| Must | 案A | 案B | 案C | 案D | 何もしない |
|---|---|---|---|---|---|
| M1 | 満たす（試した） | 満たす | 満たす | 満たす | 満たす |
| M2 | 満たす（試作で導けた） | 満たす | 満たす | 満たす | 満たさない |

| Want | 案A | 案B | 案C | 案D |
|---|---|---|---|---|
| W1 | 任せる選択が決定1つに収まる。理由と引用も、任せた全部の理由になる | 決定と範囲の2つの記録ができ、どちらが新しいかの決まりと、ずれの検査が要る | 範囲は同じ回に並んだ決定から推し量る。区切った後に同じ回で次を選ぶ流れと見分けが付かない | 範囲は案A と同じ。段階は値を読むだけで済むが、理由は journal にも要るので2か所に持つ |
| W2 | 待つ相手は、分析設計の側に後から足せる | 範囲の記録に足せる | 足す所が無い | 案A と同じ |
| W3 | モデルに項目1つと、導く関数1つ | モデルに型1つと検査と、現在地の決まり | モデルは変えない。現在地の推し量りが増える | 58 か所の参照、遷移の表、形ごとの終わり方（[ADR-0048](0048-intent-decides-the-form-and-the-end-of-a-design.md)）に波及する |

- 差がつく基準: W1（案C が落ちる）と W3（案D が落ちる）。案A と案B の差は、記録が1つか2つかである。
- 感度: W2 を高にすると案B が並ぶ。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | 一緒に任せた論点は、決定の種類（深める・親に戻る）と合わなくても通る | 一緒に任せた論点は、論点ツリーにあることと重ならないことだけを検査する |
| 案A | 進捗を導くのに journal を読むので、journal が壊れていると進捗が出ない | 今の現在地と同じく、壊れた分析設計を名指しして止まる |
| 案A | 「進行中」は記録から導くので、実行エージェントが落ちても進行中のまま出る | `/analysis-auto` の再開が現在地を読み、結果の記録が無い分析をもう一度渡す |
| 案B | 決定と範囲がずれる | 検査を足す |
| 案C | 推し量りを外し、任せていない論点が進行中に見える | 抑えにくい |
| 案D | 状態の値が増え、既存の検査と表示の全部に場合分けが入る | 抑えにくい |
| 何もしない | 課題1〜3 が残る | 無い |

## Decision

案A を採る（人間の判断、2026-11-27）。決め手は W1 である。

1. `TreeDecision` は、一緒に任せた論点の id を0個以上持てる（`with_node_ids`。既定は空）。持たない保存済みの決定は、空として読む。
2. 一緒に任せた論点は論点ツリーにある論点で、互いにも `node_id` とも重ならない。区切る決定（`close`）は持てない。
3. 決定の種類の検査は、前の決定が指した全部の論点（`node_id` と `with_node_ids`）を基準にする。深めるは、そのどれかの中へ進む。親に戻るは、そのどれの中でもない所へ進む。区切るは、そのどれかで区切る。種類（`TreeDecisionKind`）は4つのままにする。
4. 1回の巡回は論点を1つ以上調べるひと回りとする。
5. 巡回の現在地（`tree_io position`）は、最新の決定が指す全部の論点について、結んだ分析設計と分析の段階を返す。終わっていない分析が1つでもあれば、巡回が終わったとは返さない。
6. 分析の段階（`AnalysisStage`）は保存しない。分析設計の状態と journal から、次の順で導く。
   1. 分析設計が terminal status なら、終わった（`finished`）。
   2. journal に止めた印があれば、止めた（`stopped`）。
   3. journal に、答えの付いていない分析者への確認があれば、確認待ち（`awaiting_confirmation`）。
   4. 分析設計が `analyzing` で、journal に `hearing`・分析者への確認・その答え以外の出来事が、分析の印（`analysis_started_at`、[ADR-0053](0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)）より後にあれば、振り返り待ち（`awaiting_reflection`）。印の無い保存済みの記録と、時刻を印と比べられない出来事は、時刻を問わず数える（2026-11-27 に追記。下の「追記」）。
   5. 分析設計が `analyzing` なら、進行中（`running`）。
   6. それ以外は実行前（`before_run`）。
7. 論点の進捗（`Progress`）は結んだ分析設計の分析の段階から導く。進捗の言葉に「止めた」（`stopped`）を足す（人間の判断、2026-11-27）。結んだ分析設計が全部止めた論点は止めたと出し、止めた以外の分析設計が1つでもあれば、止めた分析設計を数えずに決める。下の論点の進捗の数（[ADR-0057](0057-a-question-without-a-design-shows-the-progress-below-it.md)）にも、止めたを数える。ページ、`tree_io position`、`tree_io progress`、レポート、skill は同じ規則を使う。
8. 用語「ツリーの決定」を「論点ツリーの決定」に改名する。用語集、画面の見出し、この Epic 以降の文書と skill の文を直し、旧い語は使わない言い換えに置く。コード上の名前（`TreeDecision`）と YAML の項目名は変えない。閉じた Epic の文書は直さない。

### 追記（2026-11-27、Story 35.2）

Decision 6.4 は、もとは分析の印を見ず、`hearing`・確認・答え以外の出来事が1つでもあれば振り返り待ちとしていた。
Story 35.2 のレビューで、次のことがわかった。`/analysis-design` は分析設計を作った直後に `/analysis-journal` を案内する（`skills/analysis-design/SKILL.md`）。
その journal に `hypothesize` や `decide` が書いてあると、`analyzing` に入った瞬間に振り返り待ちになる。
試すと、`AnalysisStage.of('analyzing', [hypothesize])` は `awaiting_reflection` を返した。
すると、分析者への確認も止めることも拒まれ、何も走っていないのに「計算が終わり、振り返りを待っている」と出る。

人間は Decision Analysis で次の2つの案から A を選んだ（2026-11-27）。

- 案A: 分析の印より後に作られた出来事だけを数える。
- 案B: 数える種類を `observe` と `evidence` に絞る。

決め手は2つあった。案B は、notebook が未解決の問い（`question`）だけを書いた分析を、進行中のまま残す。実行の前に手で書いた `observe` も、結果と読む。
この追記で、Domain Model の `AnalysisStage.of` は分析の印を引数に取る（`of(status, events, started_at)`）。

## Consequences

### Positive

- 任せる選択、その理由、根拠の引用が、決定1つに収まる。
- 分析の段階を2か所に持たない。記録が変われば、表示も変わる。
- 1つだけ任せる巡回は、一緒に任せた論点が空の決定で、今と同じに動く。

### Negative

- 一緒に任せた論点は決定の種類の言葉と合わないことがある。「親に戻る」が親でない論点へ移るときにも出ること（手で通した記録の F7）と同じ原因で、この決定では直さない。
- 分析の段階は journal の印の書き方に頼る。印は専用の命令だけが書く（ADR-0064）。
- 進行中は「任せて、まだ結果の記録が無い」ことで、実行エージェントが今動いていることは保証しない。
- 閉じた Epic の文書には「ツリーの決定」が残る。
- 任せた範囲に持たせたい中身が増えたら（次の Epic の「前の分析を待つ」など）、決定の項目が増えていく。そのときに別の型に分けるかを決める。

## Alternatives considered

- **決定を論点ごとに `node_ids` の並び1つにまとめ、`node_id` を消す** — 保存済みの論点ツリーの移行が要り、M1 を満たさない。

## Related

- Epic: [#284](https://github.com/etoyama/insight-blueprint-skills/issues/284)、[docs/design/epic-35-hand-over-questions.md](../design/epic-35-hand-over-questions.md)（US-1、US-3）
- Issues: [#250](https://github.com/etoyama/insight-blueprint-skills/issues/250)
- [ADR-0024](0024-question-tree-yaml-and-generated-html.md)、[ADR-0026](0026-analysis-auto-walks-the-question-tree.md)、[ADR-0057](0057-a-question-without-a-design-shows-the-progress-below-it.md)、[ADR-0058](0058-a-tree-decision-may-cite-the-events-behind-its-reason.md)
- Supersedes: ADR-0026 の一部（巡回は論点を1つ調べる、現在地は最新の決定の論点から導く）
