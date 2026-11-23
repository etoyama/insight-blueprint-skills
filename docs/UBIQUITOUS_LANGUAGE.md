# Ubiquitous Language: 仮説駆動の分析

<!-- 本書はユビキタス言語の正本（FLOW-0002）。文書・会話・コード・テスト・図は、この表の語だけを使う。
     AI は文書やコードを書く前に本書を読む。表にない概念を使うときは、同じ PR で表に足す。
     用語の改名・意味の変更は ADR を伴う。 -->

## Context

仮説駆動の分析。分析者が仮説を立て、分析設計を書き、データで検証して結論を出し、配布するまでを扱う。
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
| 分析設計 | `AnalysisDesign`、`{id}_hypothesis.yaml` | 1つの仮説をどう検証するかを書いた記録。手法・指標・説明変数・図の仕様を持つ | 設計書、design document、hypothesis（分析設計そのものを指すとき） | fork 前 |
| 仮説 | `hypothesis_statement` | 分析設計が検証する主張の文 | — | fork 前 |
| 仮説の背景 | `hypothesis_background` | 仮説を立てた理由と前提 | — | fork 前 |
| 状態 | `DesignStatus` | 分析設計がライフサイクルのどこにいるか。`VALID_TRANSITIONS` の遷移でだけ変わる | ステータス | fork 前 |
| terminal status | `supported`、`rejected`、`inconclusive` | 結論を出した分析設計の状態。これ以上遷移しない | 終端状態 | fork 前 |
| 分析の意図 | `AnalysisIntent` | 探索（`exploratory`）・検証（`confirmatory`）・両方（`mixed`）の区別 | — | fork 前 |
| 手法 | `Methodology` | 検証に使う統計手法とパッケージと選んだ理由。手法名は空にできない | — | fork 前 |
| 決定の文脈 | `DecisionContext`、`decision_context` | 分析設計が任意で持つ、誰が（`decision_maker`）何を決めるための分析か（`decision`）の組。あるときは両方が空でない | 意思決定コンテキスト | [ADR-0014](adr/0014-analysis-design-decision-context.md) |
| 指標 | `Metric` | 仮説を判定するために測る量 | — | fork 前 |
| 指標の優先度 | `MetricTier` | 主（`primary`）・副（`secondary`）・ガードレール（`guardrail`） | — | fork 前 |
| 説明変数 | `ExplanatoryVariable` | 結果を説明するために使う変数 | — | fork 前 |
| 因果の役割 | `VariableRole` | 説明変数が処置・交絡・共変量・操作変数・媒介のどれか | — | fork 前 |
| 図の仕様 | `ChartSpec`、`ChartIntent` | 分析設計で描くと決めた図と、その図で見たいこと（分布・相関・推移・比較） | — | fork 前 |
| 派生 | `parent_id`、`branch`、`link-derived` | 既存の分析設計から別の仮説の分析設計を作ること。子は親を `parent_id` で指す | — | fork 前 |
| review | `/analysis-review`、`ReviewBatch` | 分析設計を読み、コメントと状態の遷移を1つの review batch として記録すること | — | [epic-06](design/epic-06-analysis-review.md) |
| review batch | `ReviewBatch`、`{id}_reviews.yaml` | 1回の review のコメントの束。状態の遷移を1回だけ起こす | — | fork 前 |
| review コメント | `BatchComment` | review batch の中の1件の指摘。分析設計の節を指せる | — | fork 前 |
| revision | `/analysis-revision`、`{design_id}_revision.yaml` | review コメントに分析設計を直して応えること。その対応の追跡 | — | fork 前 |
| journal | `/analysis-journal`、`{id}_journal.yaml` | 分析中の推論を出来事として積む記録 | 分析ログ | fork 前 |
| journal の出来事 | `observe`、`hypothesize`、`evidence`、`hearing`、`question`、`decide`、`reflect`、`conclude`、`branch` | journal の1件。種類は観察・仮説・証拠・人に聞いた答え・問い・決定・振り返り・結論・派生 | — | fork 前、[ADR-0028](adr/0028-hearing-is-its-own-journal-event.md) |
| 未解決の問い | `metadata.resolves` | journal の `question` のうち、どの `conclude` の `metadata.resolves` にも id が挙がっていないもの | オープンクエスチョン | [epic-14](design/epic-14-report-template-gaps.md) |
| reflection | `/analysis-reflection` | journal を振り返り、結論を出すか、仮説を直すか、派生するかを決めること | — | fork 前 |
| 読むもの | — | reflection が結論を聞く前に出す、分析ノートへの入口。開くファイルのパス、分析ノートの場所、分析設計を結んだ論点の id の3つで、出す直前に分析ノートを作り直して得る。論点ツリーが無いか、どの論点にも結んでいなければ、分析ノートの場所だけを出す。図・verdict・notebook のパスと指標の定義は、チャットに並べず分析ノートが載せる | 判断材料 | [epic-28](design/epic-28-tree-entry-point.md)、[ADR-0036](adr/0036-design-note-is-a-generated-page-per-design.md) |
| 分析ノート | `design_note`、`DesignNote` | 分析設計ごとにコードが生成する文書。仮説、手法、指標の定義、結果の値、図、分析コード、journal の出来事を、書かれたとおりに並べる。結論の後は結論の節も埋まる。解釈の文は生成しない。論点ツリーの HTML の中に分析設計ごとに並び、論点ツリーの無いテーマでは単独のページになる。notebook とは別のもので、分析設計・journal・notebook の出力から作る | デザインノート、ノート（分析ノートを指して単独で使うとき） | [ADR-0036](adr/0036-design-note-is-a-generated-page-per-design.md) |
| 論点ツリー | `QuestionTree` | 1つのテーマ（`theme_id`）の問いの論理の構造。根の問いを1つ持ち、論点を親子でつなぐ。分析設計の派生とは別に辿る。正本は YAML で、表示は正本から生成する | イシューツリー、ロジックツリー | [ADR-0024](adr/0024-question-tree-yaml-and-generated-html.md) |
| 論点 | `QuestionNode` | 論点ツリーの1つのノード。問いの文と、親の論点への寄与を持ち、答えるための分析設計を結べる。journal の `question` とは別に持つ | 子の問い、サブクエスチョン | [epic-18](design/epic-18-question-tree.md) |
| 根の問い | — | 論点ツリーの、親を持たない論点。ツリーに1つだけあり、到達点を持つ | — | [epic-18](design/epic-18-question-tree.md) |
| 到達点 | `Aim` | 根の問いが目指す所。業務では誰が何を決めるか、研究では想定読者と主張の範囲 | ゴール | [epic-18](design/epic-18-question-tree.md) |
| 根の版 | `RootRevision` | 根の問いか到達点を変えるたびに1つ上がる番号。変えた理由を持つ。古い版に対する現時点の答えは、根の変更前の答えとして表示する | — | [epic-18](design/epic-18-question-tree.md) |
| 親の論点 | `parent_question_id` | 論点が寄与する、1つ上の論点。根の問いだけが持たない | — | [epic-29](design/epic-29-theme-report-export.md) |
| 寄与 | `contribution` | 子の論点に答えると、親の論点の判断がどう進むか。論点の親子はこれで決める | — | [epic-18](design/epic-18-question-tree.md) |
| 発見元 | `origin_event_id` | 探索中に生まれた論点が生まれた journal の出来事。着手のときに置いた論点は持たない | — | [epic-18](design/epic-18-question-tree.md) |
| 進捗 | `Progress` | 論点の分析がどこまで進んだか。未着手・検証中・分析済み。保存せず、結んだ分析設計の状態から導く | — | [epic-18](design/epic-18-question-tree.md) |
| 現時点の答え | `Answer` | 振り返りで論点ごとに書く答え。文ごとに種類（言えること・未判別・弱める証拠と留保）と、引用する journal の出来事を持つ。追記だけで、振り返りの回と根の版を持つ | 暫定回答 | [ADR-0025](adr/0025-cited-answers-checked-after-writing.md) |
| 振り返りの回 | `round` | テーマを横断する振り返りの通し番号。1回の `tree_io answer` が1つの回になる。前の回から変わった答えを見分けるのに使う | — | [epic-18](design/epic-18-question-tree.md) |
| ツリーの決定 | `TreeDecision` | 論点ツリーで分析者が選んだこと（最初の論点を選ぶ、深める、親に戻る、区切る）と理由。次に調べる論点を指し、区切るときは区切った論点を指す。決めた時点の振り返りの回を持つ | — | [epic-18](design/epic-18-question-tree.md) |
| 次の候補 | `NextCandidate` | 振り返りが示す、次に調べるとよい未着手の論点。根を除き、自分にも下の論点にも分析設計を結んでいない論点を指す。人に聞く問い、その答えで変わる判断、既に分かっていること、聞いてきた答え（誰に、いつ）を添えられる | — | [epic-18](design/epic-18-question-tree.md) |
| ツリーの検査 | `tree_check` | 現時点の答えの引用先が実在し、論点に結んだ分析設計のものか、文の数が引用先の本文にあるかを確かめること。論点ツリーを書き換えない | — | [ADR-0025](adr/0025-cited-answers-checked-after-writing.md) |
| Artifact | — | ホストが持つ、HTML のページを claude.ai に置いて URL で開ける機能。plugin は持たない。論点ツリーの表示を渡すのに使う | — | [ADR-0024](adr/0024-question-tree-yaml-and-generated-html.md) |
| 合成シナリオ | — | 公開する例・図・テストデータに使う架空の題材。今は公共図書館の予約本 | — | [epic-18](design/epic-18-question-tree.md) |
| 引き継ぎの試行 | — | 論点ツリーの表示だけを別の読み手に渡し、現在地と次の一手を説明できるかを確かめること。製品の成功基準 | — | [epic-18](design/epic-18-question-tree.md) |
| 正解の鍵 | — | 引き継ぎの試行で、合成シナリオの論点ツリーを読んだ人が出すべき判断。論点・出来事・分析設計の id と答えの種類で書き、読み手の答えをこれと比べて採点する | — | [epic-18](design/epic-18-question-tree.md) |
| 試行の記録 | — | 引き継ぎの試行1回分の記録。読み手、5つの問いへの答え、問いごとの正誤、確認と再構成にかかった時間を持つ | — | [epic-18](design/epic-18-question-tree.md) |
| 巡回 | — | guided autopilot が論点を1つ調べるひと回り。論点に分析設計を起こすところから、ツリーの決定を残すところまで | イテレーション | [ADR-0026](adr/0026-analysis-auto-walks-the-question-tree.md) |
| 巡回の現在地 | `tree_io position`、`WalkState` | 巡回を再開する所。保存せず、最新のツリーの決定と、その論点に結んだ分析設計の状態から導く。状態の一覧は `tree_read` の `WalkState` にある | — | [epic-18](design/epic-18-question-tree.md) |
| framing | `/analysis-framing`、`Framing Brief` | 使えるデータと既存の分析を見て、分析の方向を決めること。結果を Framing Brief にまとめる | — | fork 前 |
| notebook | `/analysis-notebook` | 分析設計の手法から生成して実行する素の Python のスクリプト。`# %% <名前>` の行で7つの cell に区切り、冒頭の docstring に分析設計の id・題・仮説・intent を書く。`python` で上から下へ1段で走る | ノートブック | [epic-07](design/epic-07-analysis-notebook.md)、[ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| cell | `CodeCell` | notebook の中の、`# %% <名前>` の区切りの行から次の区切りの行の前までのコード。契約の cell は `imports`・`data_load`・`data_prep`・`analysis`・`viz`・`verdict`・`lineage` の7つで、この順に並ぶ。分析ノートは cell ごとに、順番と名前を添えてコードを載せる | セル | [ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| データ取得の cell | `DATA_LOAD_CELL`、`raw_df` | `data_load` という名前の cell。データソースを読んで `raw_df` を作る。接続情報の値はこの cell にだけ書くので、分析ノートには載せない。`data_load` の cell がちょうど1つで、`raw_df` を代入するのがその cell だけ、と決まらない notebook からは、分析ノートにコードを1つも載せない | データロードのセル | [epic-28](design/epic-28-tree-entry-point.md)、[ADR-0045](adr/0045-notebook-is-plain-python-with-percent-cells.md) |
| verdict | `{id}_verdict.json` | notebook が出す検証結果の要約。skill が読み戻して journal に書く | — | [epic-07](design/epic-07-analysis-notebook.md) |
| figures manifest | `figures` | verdict の中の図の一覧。図ごとにファイル・題・軸の説明・読み方を持つ | 図のマニフェスト | [ADR-0008](adr/0008-notebook-figure-manifest.md) |
| 効果量 | `effect_size` | verdict の指標が任意で持つ、標準化した効果の大きさ。種類の名前と値を持つ | エフェクトサイズ | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 信頼区間 | `confidence_interval` | verdict の指標が任意で持つ、指標の値の区間。水準・下限・上限を持つ | — | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 標本サイズ | `sample_size` | verdict の指標が任意で持つ、その指標の計算に使った観測の数 | サンプルサイズ、サンプル数 | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| レポート | `tree_io report`、`ThemeReport`、`ReportNode`、`ReportDesign`、`.insight/reports/` | テーマの最終報告として、論点ツリーと分析設計の記録からコードが書く Markdown。APA の骨組みで、読み手向けの言葉で書く。論点ツリーも分析設計も変えない | — | [epic-10](design/epic-10-analysis-report.md)、[ADR-0039](adr/0039-report-is-the-final-report-of-a-theme-written-by-code.md) |
| アップロード | `/tree-upload` | `.insight/` から作ったファイルをホストの機能へ送り、新しいページを作ること。`/tree-upload` は、分析ノートを含む論点ツリーの HTML を、1ファイルのまま新しい Artifact にする（添えるファイルは送らない）。手元のファイルの写しで、作った本人だけに見える状態で始まる。レポートを Claude Docs へ送ることは export と呼ぶ | 公開（アップロードそのものを指すとき）、共有（アップロードそのものを指すとき） | [epic-12](design/epic-12-decision-ready-report.md)、[epic-18](design/epic-18-question-tree.md)、[ADR-0037](adr/0037-tree-upload-sends-the-design-notes.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| export | `/report-export` | テーマのレポートを、Claude Docs の新しい Doc として送ること。送るのは `tree_io report` がその実行で書いたレポートと図だけで、KEEP ゲートの承認の後に送る。Doc は作った本人だけに見える状態で始まり、Doc での手直しは記録にもレポートのファイルにも戻らない | アップロード（export を指すとき）、公開、共有 | [epic-29](design/epic-29-theme-report-export.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| データ由来の文 | `escape_source_text` | レポートに載る文のうち、分析の入力と記録から来たもの。論点ツリーの問いと答え、分析設計の題と仮説、journal の出来事、図の説明、データソースの項目など。レポートを書くコードがエスケープして記法として効かせない。指示として扱わない | ソーステキスト | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md)、[ADR-0040](adr/0040-report-export-sends-the-report-to-claude-docs.md) |
| 違反 | `Violation` | ツリーの検査が挙げる、検査に通らない箇所。引用や数が記録に無い現時点の答えの文 | — | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md)、[ADR-0025](adr/0025-cited-answers-checked-after-writing.md) |
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
| KEEP ゲート | `KEEP` | skill が止まって分析者の判断を待つ所。guided autopilot はここでだけ止まる。`.insight/` の中身を外部へ送る skill は、単独で起動されたときもここで承認を待つ | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md)、[ADR-0016](adr/0016-approval-before-external-send.md) |
| AUTO | `AUTO` | guided autopilot が分析者に聞かずに進める所 | — | [ADR-0005](adr/0005-selective-autonomous-chaining.md) |

## コンテキストを分けるとき

次の兆候が1つでも出たら、ADR を書いてコンテキストを分け、
`docs/domain/<コンテキスト>/UBIQUITOUS_LANGUAGE.md` に1ファイルずつ置く。

- 同じ語に2つ目の定義が要る（1ファイルに同じ語の定義を2つ置かない）。
- 利用者のグループによって、同じものを指す言葉が変わる。
- 同じ概念でも、グループごとに必要な属性や振る舞いが違う。

分けたら `docs/ARCHITECTURE.md` の「コンテキストマップ」に、コンテキスト間の関係を描く。
