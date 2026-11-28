# Ubiquitous Language: 仮説駆動の分析

<!-- 本書はユビキタス言語の正本（FLOW-0002）。文書・会話・コード・テスト・図は、この表の語だけを使う。
     AI は文書やコードを書く前に本書を読む。表にない概念を使うときは、同じ PR で表に足す。
     用語の改名・意味の変更は ADR を伴う。 -->

## Context

仮説駆動の分析。分析者が問いを立てて分析設計を書き、データで答えて結論を出し、配布するまでを扱う。
分析には探索と検証がある。探索は問いを測って答え、判定しない。検証は検証仮説と判定の基準を先に置き、データで判定する。
ドメインの語だけを載せ、実装の名前（`validate.py`、`design_io` など）と削除済みの機能の語は載せない
（[epic-11 の D4](design/epic-11-repo-template-compliance.md#decision-ubiquitous-language-first-editiond4)）。

## Terms

<!-- 1行1語。定義に出てくる語も、この表の語で書く。
     「使わない言い換え」は yomiyasu の flag.txt と検査スクリプトの元になる。
     初出は、その語を導入した Epic の DesignDoc か ADR。 -->

「初出」の「fork 前」は [insight-blueprint](https://github.com/etoyama/insight-blueprint) から引き継いだ語を表す。
「コード上の名前」は `tests/docs/test_canonical_docs.py` が `src/` と `skills/` に実在することを確かめる。

| 用語 | コード上の名前 | 定義 | 使わない言い換え | 初出 |
|---|---|---|---|---|
| 分析設計 | `AnalysisDesign`、`{id}_hypothesis.yaml` | 1つの問いにどう答えるかを書いた記録。探索は探索の問いを、検証は検証仮説を持つ。手法・指標・説明変数・図の仕様を持つ。id（`{theme}-H{nn}`）の `H` は分析設計の通し番号の記号で、ファイル名の `_hypothesis` と同じく、分析設計の形を表さない | 設計書、design document、hypothesis（分析設計そのものを指すとき） | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 仮説 | `hypothesize` | 問いに先に置く仮の答え。journal の `hypothesize` が記録する。探索で見つけたことから生まれ、次の論点や検証の分析設計のもとになる。分析設計の項目は検証仮説と呼ぶ | — | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 検証仮説 | `hypothesis_statement` | 検証の分析設計が判定する、問いへの仮の答えの文。分析の前に置き、判定の基準は primary の指標の `comparison` に文で書く。分析の印が付いた後は、検証仮説も primary の指標の `target`・`comparison`・`tier` も変わらない。探索の分析設計は持たない | 仮説（分析設計の項目を指すとき） | [ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md)、[ADR-0050](adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)、[ADR-0053](adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md) |
| 仮説の背景 | `hypothesis_background` | 検証仮説を置いた理由と前提 | — | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 探索の問い | `exploration_question` | 探索の分析設計が測って答える問いの文。論点ツリーの無いテーマでも、何に答えるかを分析設計だけで読めるように持つ。検証仮説と `next_action` は持たない | 問い（分析設計の項目を指すとき） | [ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 探索の問いの背景 | `exploration_background` | 探索の問いを立てた理由と前提 | — | [ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 分析設計の形 | `DesignForm` | 分析の意図と項目から導く分析設計の区別。探索（`exploration`）・検証（`confirmation`）・旧形式の探索（`legacy_exploration`）の3つで、保存しない。検査・遷移・表示は形を見て分ける | — | [ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 旧形式の探索 | `legacy_exploration` | 分析の意図が探索（`exploratory`）なのに検証仮説を持つ分析設計。分析設計の形が意図で決まる前に作られた。読めて、検証と同じ検査と遷移で判定で終わり、意図は「探索（旧形式）」と出す。新しく作れない。検証仮説とその背景が書かれていれば、`confirmatory` に直すことはどの状態でもできる | — | [ADR-0049](adr/0049-legacy-exploration-stays-readable-and-is-marked.md) |
| 状態 | `DesignStatus` | 分析設計がライフサイクルのどこにいるか。`VALID_TRANSITIONS` の遷移でだけ変わる | ステータス | fork 前 |
| terminal status | `explored`、`supported`、`rejected`、`inconclusive` | 結論を出した分析設計の状態。これ以上遷移しない。探索は `explored` でだけ終わり、判定しない。検証と旧形式の探索は判定の3つ（`supported`・`rejected`・`inconclusive`）でだけ終わる | 終端状態 | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 分析の意図 | `AnalysisIntent` | 探索（`exploratory`）・検証（`confirmatory`）・両方（`mixed`）の区別。分析設計の形を決める。`mixed` は新しく作れない。保存済みの `mixed` は検証として読む。意図を変えられるのは分析の印が付く前だけで、分析を始めた後は派生で別の意図の分析設計を作る。例外は旧形式の探索を `confirmatory` に直すことで、どの状態でもできる | — | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md)、[ADR-0053](adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md) |
| 分析の印 | `analysis_started_at`、`analysis_started` | 分析設計が初めて `analyzing` か terminal status に入ったときに残る時刻。一度付いたら消えず、結果の review で `in_review` に戻っても残る。印の無い保存済みの記録は、状態が `analyzing` か terminal status なら分析を始めたものとして読む | — | [ADR-0053](adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md) |
| 手法 | `Methodology` | 探索の問いに答えるか、検証仮説を判定するのに使う統計手法とパッケージと選んだ理由。手法名は空にできない | — | fork 前 |
| 決定の文脈 | `DecisionContext`、`decision_context` | 分析設計が任意で持つ、誰が（`decision_maker`）何を決めるための分析か（`decision`）の組。あるときは両方が空でない | 意思決定コンテキスト | [ADR-0014](adr/0014-analysis-design-decision-context.md) |
| 指標 | `Metric` | 探索では問いに答えるために、検証では検証仮説を判定するために測る量 | — | fork 前、[ADR-0050](adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md) |
| 指標の優先度 | `MetricTier` | 主（`primary`）・副（`secondary`）・ガードレール（`guardrail`） | — | fork 前 |
| 説明変数 | `ExplanatoryVariable` | 結果を説明するために使う変数 | — | fork 前 |
| 因果の役割 | `VariableRole` | 説明変数が処置・交絡・共変量・操作変数・媒介のどれか | — | fork 前 |
| 図の仕様 | `ChartSpec`、`ChartIntent` | 分析設計で描くと決めた図と、その図で見たいこと（分布・相関・推移・比較） | — | fork 前 |
| 派生 | `parent_id`、`branch`、`link-derived` | 既存の分析設計から別の分析設計を作ること。探索で見つけたことを検証するときと、分析の後に意図を変えるときも派生で作る。子は親を `parent_id` で指す | — | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| review | `/analysis-review`、`ReviewBatch` | 分析設計を読み、コメントと状態の遷移を1つの review batch として記録すること。分析の後は、notebook・verdict・図も読む（結果の review） | — | [epic-06](design/epic-06-analysis-review.md)、[ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md) |
| review batch | `ReviewBatch`、`{id}_reviews.yaml`、`after_analysis_started` | 1回の review のコメントの束。状態の遷移を1回だけ起こす。分析を始めた後に書かれたかどうかを、書かれた時点で持つ。保存済みの review batch は持たない | — | fork 前、[ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md) |
| review コメント | `BatchComment` | review batch の中の1件の指摘。分析設計の節か、結果（`notebook`・`verdict`・`figures`）を指せる | — | fork 前、[ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md) |
| revision | `/analysis-revision`、`{design_id}_revision.yaml` | review コメントに分析設計を直して応えること。その対応の追跡 | — | fork 前 |
| journal | `/analysis-journal`、`{id}_journal.yaml` | 分析中の推論を出来事として積む記録 | 分析ログ | fork 前 |
| journal の出来事 | `observe`、`hypothesize`、`evidence`、`hearing`、`question`、`decide`、`reflect`、`conclude`、`branch` | journal の1件。種類は観察・仮説・証拠・人に聞いた答え・問い・決定・振り返り・結論・派生 | — | fork 前、[ADR-0028](adr/0028-hearing-is-its-own-journal-event.md) |
| 未解決の問い | `metadata.resolves` | journal の `question` のうち、どの `conclude` の `metadata.resolves` にも id が挙がっていないもの。分析者の答えが付いた分析者への確認は数えない | オープンクエスチョン | [epic-14](design/epic-14-report-template-gaps.md) |
| 分析者への確認 | `asks_analyst`、`ask-analyst` | 任せた分析が、任せる前に分析者が読んだ内容を変えないと進めないときに、データに触る前に分析者へ聞くこと。journal の `question` に `metadata.asks_analyst` の印を付けて書く。印を持つ出来事を手で足す・消す・書き換えることは、検証 hook が止める。書けるのは分析の段階が進行中の分析だけである。答えの付いていない確認がある分析設計は、終わりの状態へ移せない（`transition`・`update`・`review-batch`） | — | [ADR-0064](adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) |
| 分析者の答え | `answers`、`answer-analyst` | 分析者への確認に、分析者が返した答え。journal の `decide` に、どの確認への答えかを `metadata.answers` に持って書く。1つの確認に答えは1つで、止めた分析には書けない | — | [ADR-0064](adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) |
| 止めた理由 | `stopped`、`stop` | 分析者が分析を止めた理由。journal の `decide` に `metadata.stopped` の印を付けて書く。分析設計の状態は変えない。止めた分析設計は、状態を変える書き込み（`transition`・`update`・`review-batch`）も、結果の追記（`journal-append`）も拒む。止めた分析は再開せず、やり直すときは派生で別の分析設計を作る。止められるのは、分析の段階が実行前・進行中・確認待ちの分析である | — | [ADR-0064](adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) |
| 分析の段階 | `AnalysisStage` | 1つの分析がどこまで進んだか。実行前（`before_run`）・進行中（`running`）・確認待ち（`awaiting_confirmation`）・止めた（`stopped`）・振り返り待ち（`awaiting_reflection`）・終わった（`finished`）の6つ。保存せず、分析設計の状態と分析の印と journal から、決まった順で導く。結果と数えるのは分析の印より後の出来事である。規則は `AnalysisStage.of` の1か所にある。分析者への確認・分析者の答え・止めた理由の印は専用の命令だけが書き、段階はその印を、印を書く種類の出来事の上でだけ読む | — | [ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md)、[ADR-0064](adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) |
| 段階の読み取り | `StageReading`、`design_io stage` | 1つの分析の段階に、結果が記録にあるか・答えの付いていない分析者への確認（`Ask`）・止めた理由を添えた値。保存せず、分析設計と journal から1回で読む。確認は確認待ちの分析だけが、止めた理由は止めた分析だけが持つ。結果が記録にあるかは段階に従わず、結果のレビューが分析設計を `in_review` に戻している間も真のままである。分析に入っていない分析設計は、journal に推論があっても結果を持たない。`design_io stage` も分析ノートもこの値を読み、skill は止めた理由や確認を journal から自分で読まない | — | [ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md)、[ADR-0064](adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md) |
| データの範囲 | `DataScope`、`data_scope` | 分析設計が任意で持つ、何を数える分析かの組。対象（`population`）・粒度（`grain`）・分母（`denominator`）を文で書き、あるときは3つとも空でない。持たない保存済みの分析設計はそのまま読める。分析ノートは手法の節に出す | — | [ADR-0066](adr/0066-a-design-may-state-its-population-grain-and-denominator.md) |
| 任せる前の確認 | `HandoverDesign`、`to_hand_over`、`tree_io handover` | まとめて任せる前に、分析者が任せる分析設計を1回、横に並べて読むこと。最新の論点ツリーの決定が指す論点に結んだ、実行前の分析設計を、論点ツリーの HTML の節に列で並べる。行は意図、何に答えるか、判定の基準、対象、粒度、分母、データソース、手法、主指標、抽出・加工条件、図。分析設計ごとにコメント欄があり、書いたコメントを分析設計の id を添えた1つの文にまとめて、ページに出す。ページは外へ何も送らない | — | [ADR-0063](adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md) |
| 結果のレビュー | — | 結果が記録にある分析設計を、結論を記録する前に批評すること。Claude が notebook・verdict・図・分析設計を読み、計算の点検が見ないことを批評し、コメントを残す。見るのは、値と判定の矛盾、図、guardrail、解釈と交絡（別の説明がつかないか、どこまで言えるか）である。notebook が写した判定の線と cell の並びは、計算の点検が見る。点検が済んでいない間は、写した判定の線もレビューが読む。受けるかは分析者が決める。勧める目安は判定で終わる（検証）ことと、数の照合がデータの中の足し上げだけであることの2つだけである。受けると、結論の記録はレビューの後になる。結論を記録した分析設計はもうレビューできない | — | [ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md)、[ADR-0071](adr/0071-a-difference-is-shown-before-reading-and-the-review-of-a-result-is-narrowed.md) |
| 計算の点検 | `DesignCheck`、`design_io check`、`{id}_check.yaml` | notebook が分析設計どおりに計算したかを、分析者が分析ノートを読む前に確かめること。分析設計・notebook・verdict を読み比べ、点検の項目ごとの結果を、分析設計ごとに1つ記録する。分析者には聞かず、データに触らない。数が正しいか、分析設計が妥当か、結果の解釈が妥当かは確かめない。記録は点検した verdict と分析設計を覚え、verdict の中身か、分析設計のうち点検の項目が読む欄が変わると、点検は済んでいないと読む。分析設計の状態が動いただけでは、済んだままである。点検し直すと前の記録を置き換える。分析設計の状態も分析の段階も変えない | — | [ADR-0070](adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md) |
| 点検の項目 | `CheckItem`、`CheckSubject` | 計算の点検が見比べる1つの事柄と、その結果。事柄は、対象・粒度・分母・抽出・加工条件・指標・比べ先・図・判定の基準・cell の並びの9つで、判定の基準は検証の分析設計だけが持つ。結果は、合っている（`agrees`）・食い違う（`differs`）・確かめられない（`not_checkable`）のどれか。指標・図・cell の並びはコードが決め、ほかは点検エージェントが読む | — | [ADR-0070](adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md) |
| 食い違い | `differs` | 点検の項目のうち、分析設計に書いたことと notebook の計算が違うもの。何が違うかの文と、根拠にした cell を持つ。cell の並びの食い違いだけは cell を持たない。コードは、分析設計の指標が verdict に同じ名前で無いこと、verdict の指標が分析設計に無いこと、verdict の図の数が分析設計の図の仕様の数と違うこと、cell が契約の7つの並びでないことを食い違いに挙げる | — | [ADR-0070](adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md) |
| 点検エージェント | `check_agent`、`CheckedBy` | 計算の点検で、コードが決めない点検の項目を読む、その notebook を書いていない同じセッションの中の Claude。何も書かない。立てられないホストでは同じセッション（`same_session`）が読み、誰が読んだかを記録に残す | — | [ADR-0070](adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md) |
| 比べ先 | — | 分析の結果を比べる相手。分析設計が比べると書いた行・群・期間など。任せる前に分析者が読む内容の1つで、実行エージェントは比べ先を足す・変えるとき、データに触る前に止まって分析者に確かめる | — | [epic-35](design/epic-35-hand-over-questions.md) |
| 分析間の違い | `differing_rows`、`COMPARED_ROWS` | 任せる前の確認で、対象・粒度・分母・データソースの値が分析設計の間で違う行に、コードが付ける印。値の文字が違えば付くので、同じ意味を違う言葉で書いた行にも付く | — | [ADR-0063](adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md) |
| reflection | `/analysis-reflection` | journal を振り返り、分析設計を結論で終えるか、直すか、派生するかを決めること。探索は `explored` で終え、判定しない | — | fork 前、[ADR-0048](adr/0048-intent-decides-the-form-and-the-end-of-a-design.md) |
| 読むもの | — | reflection が結論を聞く前に出す、分析ノートへの入口。開くファイルのパス、分析ノートの場所、分析設計を結んだ論点の id の3つで、出す直前に分析ノートを作り直して得る。論点ツリーが無いか、どの論点にも結んでいなければ、分析ノートの場所だけを出す。図・verdict・notebook のパスと指標の定義は、チャットに並べず分析ノートが載せる | 判断材料 | [epic-28](design/epic-28-tree-entry-point.md)、[ADR-0036](adr/0036-design-note-is-a-generated-page-per-design.md) |
| 分析ノート | `design_note`、`DesignNote`、`NoteReviewBatch` | 分析設計ごとにコードが生成する文書。探索の問いか検証仮説、手法、指標の定義、結果の値、図、review batch と review コメント、分析コード、journal の出来事を、書かれたとおりに並べる。結論の後は結論の節も埋まる。解釈の文は生成しない。論点ツリーの HTML の中に分析設計ごとに並び、論点ツリーの無いテーマでは単独のページになる。notebook とは別のもので、分析設計・journal・notebook の出力から作る | デザインノート、ノート（分析ノートを指して単独で使うとき） | [ADR-0036](adr/0036-design-note-is-a-generated-page-per-design.md)、[ADR-0054](adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md) |
| 論点ツリー | `QuestionTree` | 1つのテーマ（`theme_id`）の問いの論理の構造。主題を1つ持ち、論点を親子でつなぐ。分析設計の派生とは別に辿る。正本は YAML で、表示は正本から生成する | イシューツリー、ロジックツリー | [ADR-0024](adr/0024-question-tree-yaml-and-generated-html.md) |
| 論点 | `QuestionNode` | 論点ツリーの1つのノード。問いの文と、親の論点への寄与を持ち、答えるための分析設計を結べる。journal の `question` とは別に持つ | 子の問い、サブクエスチョン | [epic-18](design/epic-18-question-tree.md) |
| 主題 | — | 論点ツリーの、親を持たない論点。ツリーに1つだけあり、到達点を持つ。コード上の名前と YAML の項目名は root のままである | 根の問い | [epic-18](design/epic-18-question-tree.md)、[ADR-0055](adr/0055-the-root-question-is-shown-as-the-subject.md) |
| 到達点 | `Aim` | 主題が目指す所。業務では誰が何を決めるか、研究では想定読者と主張の範囲 | ゴール | [epic-18](design/epic-18-question-tree.md) |
| 主題の版 | `RootRevision` | 主題か到達点を見直すたびに1つ上がる番号。見直した理由を持つ。古い版に対する現時点の答えは、見直す前の主題への答えとして表示する。画面では版を番号で出さず、主題を見直した回数を言葉で言う | 根の版 | [epic-18](design/epic-18-question-tree.md)、[ADR-0055](adr/0055-the-root-question-is-shown-as-the-subject.md) |
| 親の論点 | `parent_question_id` | 論点が寄与する、1つ上の論点。主題だけが持たない | — | [epic-29](design/epic-29-theme-report-export.md) |
| 寄与 | `contribution` | 子の論点に答えると、親の論点の判断がどう進むか。論点の親子はこれで決める | — | [epic-18](design/epic-18-question-tree.md) |
| 発見元 | `origin_event_id` | 探索中に生まれた論点が生まれた journal の出来事。着手のときに置いた論点は持たない | — | [epic-18](design/epic-18-question-tree.md) |
| 進捗 | `Progress` | 論点の分析がどこまで進んだか。未着手・調べている・止めた・分析済み。保存せず、結んだ分析設計の分析の段階を畳んで導く。結んだ分析設計を全部止めた論点は止めた。止めた以外が1つでもあれば、止めた分析設計を数えずに決める。自分には分析設計を結ばず、下に置いた論点のどれかに結んでいる論点は進捗の言葉を持たず、下の論点の進捗を言葉ごとの数で出す。「進捗の数」はその論点を数えない。自分にも下にも分析設計が無い論点は未着手。規則は `QuestionTree.progress` の1か所にある | — | [epic-18](design/epic-18-question-tree.md)、[ADR-0057](adr/0057-a-question-without-a-design-shows-the-progress-below-it.md)、[ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| 現時点の答え | `Answer` | 振り返りで論点ごとに書く答え。文ごとに種類（これまでわかっていること `claim`・注意すべきこと `weakening`・まだ決められないこと `undetermined`）と、引用する journal の出来事を持つ。追記だけで、振り返りの回と主題の版を持つ。文は分析者の見立ての印を持てる | 暫定回答、言えること、弱める証拠と留保、未判別 | [ADR-0025](adr/0025-cited-answers-checked-after-writing.md)、[ADR-0068](adr/0068-an-answer-statement-may-be-the-analysts-view.md) |
| 分析者の見立て | `analyst_view` | 現時点の答えの文のうち、本文が分析者の言葉であるもの。文に印（`AnswerStatement` の `analyst_view`）を持つ。印は既定で無く、印の無い文はエージェントが書いた文である。印のある文も journal の出来事を1つ以上引用し、ツリーの検査を同じ規則で受ける。エージェントは印のある文を言い換えない。答えは追記だけなので、書いた文の印は後から変わらない | 分析者の読み | [ADR-0068](adr/0068-an-answer-statement-may-be-the-analysts-view.md) |
| 答えの変化 | `AnswerChange` | 論点の最後の現時点の答えと、その1つ前の答えを、引用する journal の出来事ごとに比べたもの。保存せず、論点ツリーだけから `tree_changes` が導く。答えが1つの論点には無い。画面では「前の回から変わったこと」と出す | 答えを動かした証拠、消えた主張 | [ADR-0056](adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md) |
| 証拠の変わり方 | `ChangeKind` | 答えの変化の中で、1つの出来事の使われ方。新しく引用した（`newly_cited`）・引用をやめた（`dropped`）・引用する文が変わった（`reworded`）・変わっていない（`unchanged`）の4つ。引用する文の種類と本文の集まりだけで決まる | — | [ADR-0056](adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md) |
| 上の論点での引用 | `CitedAbove` | 論点の現時点の答えが引用する出来事を、上の論点（直接の親に限らない）の現時点の答えも引用していること。上の論点がその出来事を引用する文を、この論点の答えより後の回で変えていれば、変えた回（`reworded_in`）を持つ。保存せず導く。画面では「この論点の分析結果を根拠にしている答え」と出す | — | [ADR-0056](adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md) |
| 引用していない下の結果 | `UncitedBelow` | 下の論点の現時点の答えが引用していて、その論点の現時点の答えが引用していない出来事。一度も引用していないものと、前の回までは引用していたもの（最後に引用した回 `last_cited_round` を持つ）に分ける。前の回の一覧にもあったか（`shown_before`）も持つ。保存せず導く。画面では「まだ答えに入れていない分析結果」と「前は答えの根拠にしていて、今は外している分析結果」と出す | 読み直し | [ADR-0056](adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md)、[ADR-0069](adr/0069-evidence-is-recommended-and-results-shown-before-are-folded.md) |
| 前の回に見せた結果 | `shown_before` | 引用していない下の結果のうち、前の回の一覧にもあったもの。論点ツリーの最後の振り返りの回より前の答えだけで同じ一覧を作り、そこにもあれば前の回に見せたと読む。その回より前に答えを持たない論点では、どの結果も前の回に見せていない。保存せず、論点ツリーだけから導く。`tree_io changes --with-answers` に書く前の答えを渡すと、その答えを書いた後の論点ツリーとして導く | — | [ADR-0069](adr/0069-evidence-is-recommended-and-results-shown-before-are-folded.md) |
| 根拠の推奨 | — | テーマの振り返りが答えを書く前に、この回に初めて一覧に入った引用していない下の結果を、答えの根拠に勧めるものと勧めないものに分け、勧めるものに理由を1行添えること。前の回に見せた結果は件数だけを出し、この回の結果で意味が変わるものだけを理由つきで勧める側に上げる。推奨と理由はエージェントが出し、記録には残さない。答えが引用するのは、分析者が確かめた結果だけである | — | [ADR-0069](adr/0069-evidence-is-recommended-and-results-shown-before-are-folded.md) |
| 振り返りの回 | `round` | テーマを横断する振り返りの通し番号。1回の `tree_io answer` が1つの回になる。前の回から変わった答えを見分けるのに使う | — | [epic-18](design/epic-18-question-tree.md) |
| 論点ツリーの決定 | `TreeDecision` | 論点ツリーで分析者が選んだこと（最初の論点を選ぶ、深める、親に戻る、区切る）と理由。次に調べる論点を指し、区切るときは区切った論点を指す。次に調べる論点に加えて、一緒に任せた論点を0個以上持てる。種類は、直前の決定が指した全部の論点を基準にする。決めた時点の振り返りの回を持つ。理由の根拠にした journal の出来事を0個以上引用できる（`cites`）。引用できるのは、論点ツリーのどこかの論点に結んだ分析設計の出来事である | ツリーの決定 | [epic-18](design/epic-18-question-tree.md)、[ADR-0058](adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md)、[ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| 一緒に任せた論点 | `with_node_ids` | 論点ツリーの決定が、次に調べる論点と一緒に任せた論点。論点ツリーにある論点で、互いにも次に調べる論点とも重ならない。区切る決定は持てない。決定の種類の検査は受けない。持たない保存済みの決定は空として読む | — | [ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| 次の候補 | `NextCandidate` | 振り返りが示す、次に調べるとよい未着手の論点。主題を除き、自分にも下の論点にも分析設計を結んでいない論点を指す。人に聞く問い、その答えで変わる判断、既に分かっていること、聞いてきた答え（誰に、いつ）を添えられる | — | [epic-18](design/epic-18-question-tree.md) |
| ツリーの検査 | `tree_check` | 現時点の答えの引用先が実在し、論点に結んだ分析設計のものか、文の数が引用先の本文にあるかを確かめること。引用を持つ論点ツリーの決定も、引用先が実在し、論点ツリーのどこかの論点に結んだ分析設計のものか、理由の数が引用先の本文にあるかを確かめる。論点ツリーにある論点・分析設計・出来事の id と、今の回以下の「N回目の振り返り」の N は、数として数えない。論点ツリーを書き換えない | — | [ADR-0025](adr/0025-cited-answers-checked-after-writing.md)、[ADR-0058](adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md)、[ADR-0065](adr/0065-ids-and-reflection-rounds-are-not-counted-as-numbers.md) |
| Artifact | — | ホストが持つ、HTML のページを claude.ai に置いて URL で開ける機能。plugin は持たない。論点ツリーの表示を渡すのに使う | — | [ADR-0024](adr/0024-question-tree-yaml-and-generated-html.md) |
| 合成シナリオ | — | 公開する例・図・テストデータに使う架空の題材。今は2本で、公共図書館の予約本と、心理的安全性と上司支援（Epic 34 で足した）である | — | [epic-18](design/epic-18-question-tree.md) |
| 引き継ぎの試行 | — | 論点ツリーの表示だけを別の読み手に渡し、現在地と次の一手を説明できるかを確かめること。製品の成功基準。問いは6つで、6つ目（答えも数値も変わっていないのに、上の論点の答えがその証拠を引用する文が変わった論点）は Epic 34 で足した | — | [epic-18](design/epic-18-question-tree.md) |
| 正解の鍵 | — | 引き継ぎの試行で、合成シナリオの論点ツリーを読んだ人が出すべき判断。論点・出来事・分析設計の id と答えの種類で書き、読み手の答えをこれと比べて採点する | — | [epic-18](design/epic-18-question-tree.md) |
| 試行の記録 | — | 引き継ぎの試行1回分の記録。読み手、6つの問いへの答え（6つ目を足す前の記録は5つ）、問いごとの正誤、確認と再構成にかかった時間を持つ。読み手が Claude なら、答えたモデルの ID も持つ（2026-11-26 までの記録は持たない） | — | [epic-18](design/epic-18-question-tree.md)、[ADR-0060](adr/0060-a-trial-record-names-the-model-that-read.md) |
| 巡回 | — | guided autopilot が、論点ツリーの決定が指す1つ以上の論点を調べるひと回り。論点に分析設計を起こすところから、論点ツリーの決定を残すところまで。決定が2つ以上の論点を指す巡回は、分析設計をまとめて任せる: 任せる前の確認を1回求め、分析設計ごとに実行エージェントへ渡す | イテレーション | [ADR-0026](adr/0026-analysis-auto-walks-the-question-tree.md)、[ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| 巡回の現在地 | `tree_io position`、`WalkState` | 巡回を再開する所。保存せず、最新の論点ツリーの決定が指す全部の論点と、そこに結んだ分析設計の分析の段階から導く。終わっていない分析が1つでもあれば、巡回が終わったとは返さない。決定の後の分析設計が無い論点があるときも返さない。止めた分析は終わっていない分析に数えない。論点ごとに、結んだ分析設計と分析の段階も返す。状態の一覧は `tree_read` の `WalkState` にある | — | [epic-18](design/epic-18-question-tree.md)、[ADR-0061](adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md) |
| framing | `/analysis-framing`、`Framing Brief` | 使えるデータと既存の分析を見て、分析の方向を決めること。結果を Framing Brief にまとめる | — | fork 前 |
| notebook | `/analysis-notebook` | 分析設計の手法から生成して実行する素の Python のスクリプト。`# %% <名前>` の行で7つの cell に区切り、冒頭の docstring に分析設計の id・題・探索の問いか検証仮説・intent を書く。`python` で上から下へ1段で走る | ノートブック | [epic-07](design/epic-07-analysis-notebook.md)、[ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| cell | `CodeCell` | notebook の中の、`# %% <名前>` の区切りの行から次の区切りの行の前までのコード。契約の cell は `imports`・`data_load`・`data_prep`・`analysis`・`viz`・`verdict`・`lineage` の7つで、この順に並ぶ。分析ノートは cell ごとに、順番と名前を添えてコードを載せる | — | [ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| データ取得の cell | `DATA_LOAD_CELL`、`raw_df` | `data_load` という名前の cell。データソースを読んで `raw_df` を作る。接続情報の値はこの cell にだけ書くので、分析ノートには載せない。`data_load` の cell がちょうど1つで、その cell が `raw_df` を代入し、ほかでは代入しない、と決まらない notebook からは、分析ノートにコードを1つも載せない | データロードのセル | [epic-28](design/epic-28-tree-entry-point.md)、[ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| verdict | `{id}_verdict.json` | notebook が出す結果の要約。探索は測った値だけを持つ。検証は primary の指標に支持の線・棄却の線・指標の判定を持ち、secondary と guardrail の指標にしきい値と合否を持つ。skill が読み戻して journal に書く。分析設計の指標は、その `target` を名前にして持つ（[ADR-0070](adr/0070-the-computation-is-checked-against-the-design-before-the-analyst-reads.md)） | — | [epic-07](design/epic-07-analysis-notebook.md)、[ADR-0050](adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)、[ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 支持の線 | `support_line` | 検証の primary の指標が持つ判定の基準のうち、検証仮説を支持する側の線。数で、notebook が分析設計の `comparison` から verdict に写す。基準が1本の線なら、支持の線だけを持つ | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 棄却の線 | `reject_line` | 検証の primary の指標が持つ判定の基準のうち、検証仮説を棄却する側の線。数で、notebook が分析設計の `comparison` から verdict に写す | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 結論しない範囲 | — | 支持の線と棄却の線の間。値がここに入ると、指標の判定は「結論しない」になる | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 指標の判定 | `judgment`、`MetricJudgment` | 検証の primary の指標が検証仮説に対して出す答え。支持（`supported`）・棄却（`rejected`）・結論しない（`inconclusive`）のどれかで、notebook が verdict に書く。合否では表さない | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| figures manifest | `figures` | verdict の中の図の一覧。図ごとにファイル・題・軸の説明・読み方を持つ | 図のマニフェスト | [ADR-0008](adr/0008-notebook-figure-manifest.md) |
| 効果量 | `effect_size` | verdict の指標が任意で持つ、標準化した効果の大きさ。種類の名前と値を持つ | エフェクトサイズ | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 値の区間 | `interval`、`ValueInterval` | verdict の指標と群の行が任意で持つ、値の区間。種類の名前・水準・下限・上限を持つ。種類の名前は notebook が書く（`confidence`・`hdi`・`eti` など） | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 信頼区間 | `confidence` | 値の区間の種類の1つ。保存済みの verdict の `confidence_interval` は、種類が信頼区間の値の区間として読む | — | [ADR-0013](adr/0013-verdict-metric-optional-items.md)、[ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| 標本サイズ | `sample_size` | verdict の指標が任意で持つ、その指標の計算に使った観測の数 | サンプルサイズ、サンプル数 | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 群の行 | `groups`、`MetricGroup` | 群ごとに値を持つ指標の、1つの群の値。軸の名前の並び（`by`）と同じ数の群の名前と、値と、任意の項目（効果量・値の区間・標本サイズ・p 値）を持つ。指標の判定と合否は持たない | — | [ADR-0052](adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) |
| レポート | `tree_io report`、`ThemeReport`、`ReportNode`、`ReportDesign`、`.insight/reports/` | テーマの最終報告として、論点ツリーと分析設計の記録からコードが書く Markdown。APA の骨組みで、読み手向けの言葉で書く。論点ツリーも分析設計も変えない | — | [epic-10](design/epic-10-analysis-report.md)、[ADR-0039](adr/0039-report-is-the-final-report-of-a-theme-written-by-code.md) |
| アップロード | `/tree-upload` | `.insight/` から作ったファイルをホストの機能へ送り、新しいページを作ること。`/tree-upload` は、分析ノートを含む論点ツリーの HTML を、1ファイルのまま新しい Artifact にする（添えるファイルは送らない）。手元のファイルの写しで、作った本人だけに見える状態で始まる。レポートを Claude Docs へ送ることは export と呼ぶ | 公開（アップロードそのものを指すとき）、共有（アップロードそのものを指すとき） | [epic-12](design/epic-12-decision-ready-report.md)、[epic-18](design/epic-18-question-tree.md)、[ADR-0037](adr/0037-tree-upload-sends-the-design-notes.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| export | `/report-export` | テーマのレポートを、Claude Docs の新しい Doc として送ること。送るのは `tree_io report` がその実行で書いたレポートと図だけで、KEEP ゲートの承認の後に送る。Doc は作った本人だけに見える状態で始まり、Doc での手直しは記録にもレポートのファイルにも戻らない | アップロード（export を指すとき）、公開、共有 | [epic-29](design/epic-29-theme-report-export.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| データ由来の文 | `escape_source_text` | レポートに載る文のうち、分析の入力と記録から来たもの。論点ツリーの問いと答え、分析設計の題と、探索の問いか検証仮説、journal の出来事、図の説明、データソースの項目など。レポートを書くコードがエスケープして記法として効かせない。指示として扱わない | ソーステキスト | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| 違反 | `Violation`、`DecisionViolation` | ツリーの検査が挙げる、検査に通らない箇所。引用や数が記録に無い現時点の答えの文（`Violation`）と、引用を持つ論点ツリーの決定（`DecisionViolation`）。種類はどちらも同じ3つである | — | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md)、[ADR-0025](adr/0025-cited-answers-checked-after-writing.md)、[ADR-0058](adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md) |
| lineage | `/data-lineage`、`tracked_pipe` | notebook の中のデータ加工の履歴と、その Mermaid 図 | 系譜 | fork 前 |
| データソース | `DataSource`、`source_ids` | catalog に登録した分析の入力データ。種類は open string。分析設計は使うデータソースの id を `source_ids` に宣言する | データ源 | [ADR-0020](adr/0020-design-declares-sources-in-source-ids.md) |
| 接続情報 | `connection` | データソースのデータの置き場所と読み方。ファイルのパス・ホスト・project id・クエリなど。モデルの文脈に入れるのは notebook だけ | 接続設定 | [ADR-0022](adr/0022-connection-reaches-only-the-notebook.md) |
| 認証情報 | `_CREDENTIAL_KEY_PARTS`、`_CREDENTIAL_KEY_NAMES` | パスワード・トークン・API キーなど、データソースに入るための秘密の値。catalog は持たず、環境変数に置く。接続情報には環境変数の名前だけを `*_env` のキーで書く | クレデンシャル、秘密情報 | [ADR-0023](adr/0023-catalog-holds-no-credentials.md)、[ADR-0034](adr/0034-credential-check-joins-nested-keys.md) |
| 取得スクリプト | — | 分析を行うプロジェクトが持つ、データソースからデータを取ってファイルに保存するスクリプト。認証情報は環境変数から読む。plugin は持たず、Claude は API を呼ばない | — | [#136](https://github.com/etoyama/insight-blueprint-skills/issues/136) |
| データソースの参照 | `{source:ID}` | 分析設計の `methodology.steps` でデータソースを指す書き方。notebook が接続情報の値で置き換える | — | [ADR-0022](adr/0022-connection-reaches-only-the-notebook.md) |
| 列のスキーマ | `ColumnSchema` | データソースの1列の名前・型・説明 | — | fork 前 |
| catalog | `/catalog-register`、`.insight/catalog/` | 登録したデータソースとドメイン知識の置き場 | カタログ | fork 前 |
| ドメイン知識 | `DomainKnowledge`、`DomainKnowledgeEntry` | 1つのデータソースについて分析から取り出した、使い回せる知識 | — | [epic-05b](design/epic-05b-knowledge-extraction.md) |
| finding | `finding` | その分析だけで言える発見。ドメイン知識にせず reflection に残す | — | [epic-05b](design/epic-05b-knowledge-extraction.md) |
| premortem | `/premortem` | 高いデータアクセスの前に、費用とリスクを見積もって報告すること。止めはしない | 事前評価 | [epic-05a](design/epic-05a-premortem-standalone.md) |
| リスクレベル | `RiskLevel` | premortem の判定。`HARD_BLOCK`・`HIGH`・`MEDIUM`・`LOW`・`SKIP` | — | [epic-05a](design/epic-05a-premortem-standalone.md) |
| パッケージ許可リスト | `package_allowlist.yaml`、`allowlist_ok` | notebook が import してよいパッケージの宣言。premortem と guided autopilot は、既定の許可リストにこれを足したものを、notebook へ進んでよいかの境界に使う。ファイルが無ければ既定の許可リストだけを使う | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md) |
| 既定の許可リスト | `notebook` extra | notebook の契約がすべての notebook で import するパッケージ。plugin の env に最初から入っている。パッケージ許可リストの有無や中身にかかわらず許す | — | [ADR-0021](adr/0021-default-package-allowlist.md)、[ADR-0027](adr/0027-default-allowlist-always-allowed.md) |
| guided autopilot | `/analysis-auto` | driver が既存の skill を順に動かし、KEEP ゲートでだけ止まる実行 | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md) |
| 対話エージェント | — | `/analysis-auto` を起動したセッションの Claude。分析者と話し、分析を任せ、論点ツリー・分析設計・論点ツリーの HTML を書く。まとめて任せた実行で、これらを書くのは対話エージェントだけである | — | [ADR-0062](adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md) |
| 実行エージェント | — | 対話エージェントが分析設計を1つ渡して実行させる、同じセッションの中の Claude。書くのは、渡された分析設計の notebook・verdict・journal だけである。journal は `design_io journal-append` と `design_io ask-analyst` を通して書く。分析者とは話さない | — | [ADR-0062](adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md) |
| KEEP ゲート | `KEEP` | skill が止まって分析者の判断を待つ所。guided autopilot はここでだけ止まる。まとめて任せる巡回では、任せる前の確認、任せた後の分析者への確認、戻った分析の終え方がこれに当たる。テーマの振り返りでは、主題への見立てと根拠の確認がこれに当たる。`.insight/` の中身を外部へ送る skill は、単独で起動されたときもここで承認を待つ | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md)、[ADR-0016](adr/0016-approval-before-external-send.md) |
| AUTO | `AUTO` | guided autopilot が分析者に聞かずに進める所 | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md) |

## Words shown to the analyst

文書・コード・テストは内側の用語を使い、分析者に見せる文（論点ツリーの表示、skill が分析者に出す文、レポート）は右の列の言葉を使う（[ADR-0055](adr/0055-the-root-question-is-shown-as-the-subject.md)）。
表には、内側と画面で言葉が違う語だけを置く。主題と、答えの文の種類の3語は、内側でも同じ語を使う用語で、上の表にある。主題の版と振り返りの回は内側の用語で、画面では表の言い方で出す。
YAML の項目名と値は変えない。表の正本は [Epic 34 の DesignDoc の US-5](design/epic-34-what-moved-the-answer.md#us-5-分析者が論点ツリーを内側の用語ではなく伝わる言葉で読む) で、ここに写す。

| 内側の用語（文書・コード） | 分析者に見せる言葉 |
|---|---|
| 引用する（`cites`） | 根拠にする |
| 答えが引用した journal の出来事 | 分析結果（`hearing` は「人に聞いた答え」） |
| 下の論点 | 使わない。「分析結果のうち」のように、分析結果を主語にして言う |
| 引用していない下の結果のうち、一度も引用していないもの | まだ答えに入れていない分析結果 |
| 引用していない下の結果のうち、前は引用していたもの | 前は答えの根拠にしていて、今は外している分析結果 |
| 振り返りの回（`round`）、回 N | N回目の振り返り |
| 主題の版（`RootRevision`） | 主題を見直した回数を言葉で言う（主題を1回見直した）。見直していない間は出さない |

## コンテキストを分けるとき

次の兆候が1つでも出たら、ADR を書いてコンテキストを分け、
`docs/domain/<コンテキスト>/UBIQUITOUS_LANGUAGE.md` に1ファイルずつ置く。

- 同じ語に2つ目の定義が要る（1ファイルに同じ語の定義を2つ置かない）。
- 利用者のグループによって、同じものを指す言葉が変わる。
- 同じ概念でも、グループごとに必要な属性や振る舞いが違う。

分けたら `docs/ARCHITECTURE.md` の「コンテキストマップ」に、コンテキスト間の関係を描く。
