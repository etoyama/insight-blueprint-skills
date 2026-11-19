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
| 派生 | `parent_id`、`branch` | 既存の分析設計から別の仮説の分析設計を作ること。子は親を `parent_id` で指す | — | fork 前 |
| review | `/analysis-review`、`ReviewBatch` | 分析設計を読み、コメントと状態の遷移を1つの review batch として記録すること | — | [epic-06](design/epic-06-analysis-review.md) |
| review batch | `ReviewBatch`、`{id}_reviews.yaml` | 1回の review のコメントの束。状態の遷移を1回だけ起こす | — | fork 前 |
| review コメント | `BatchComment` | review batch の中の1件の指摘。分析設計の節を指せる | — | fork 前 |
| revision | `/analysis-revision`、`{design_id}_revision.yaml` | review コメントに分析設計を直して応えること。その対応の追跡 | — | fork 前 |
| journal | `/analysis-journal`、`{id}_journal.yaml` | 分析中の推論を出来事として積む記録 | 分析ログ | fork 前 |
| journal の出来事 | `observe`、`hypothesize`、`evidence`、`question`、`decide`、`reflect`、`conclude`、`branch` | journal の1件。種類は観察・仮説・証拠・問い・決定・振り返り・結論・派生 | — | fork 前 |
| 未解決の問い | `metadata.resolves` | journal の `question` のうち、どの `conclude` の `metadata.resolves` にも id が挙がっていないもの | オープンクエスチョン | [epic-14](design/epic-14-report-template-gaps.md) |
| reflection | `/analysis-reflection` | journal を振り返り、結論を出すか、仮説を直すか、派生するかを決めること | — | fork 前 |
| framing | `/analysis-framing`、`Framing Brief` | 使えるデータと既存の分析を見て、分析の方向を決めること。結果を Framing Brief にまとめる | — | fork 前 |
| notebook | `/analysis-notebook` | 分析設計の手法から生成して実行する marimo notebook。8つの cell の契約に従う | ノートブック | [epic-07](design/epic-07-analysis-notebook.md) |
| verdict | `{id}_verdict.json` | notebook が出す検証結果の要約。skill が読み戻して journal に書く | — | [epic-07](design/epic-07-analysis-notebook.md) |
| figures manifest | `figures` | verdict の中の図の一覧。図ごとにファイル・題・軸の説明・読み方を持つ | 図のマニフェスト | [ADR-0008](adr/0008-notebook-figure-manifest.md) |
| 効果量 | `effect_size` | verdict の指標が任意で持つ、標準化した効果の大きさ。種類の名前と値を持つ | エフェクトサイズ | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 信頼区間 | `confidence_interval` | verdict の指標が任意で持つ、指標の値の区間。水準・下限・上限を持つ | — | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| 標本サイズ | `sample_size` | verdict の指標が任意で持つ、その指標の計算に使った観測の数 | サンプルサイズ、サンプル数 | [ADR-0013](adr/0013-verdict-metric-optional-items.md) |
| レポート | `/analysis-report`、`.insight/reports/` | 結論の出た分析を配布用にまとめた APA 風の Markdown。分析設計を変えない | — | [epic-10](design/epic-10-analysis-report.md) |
| アップロード | `/report-upload` | レポートと図を Claude Docs へ送り、新しい Doc を作ること。Doc はレポートの写しで、作った本人だけに見える状態で始まる | 公開（アップロードそのものを指すとき）、共有（アップロードそのものを指すとき） | [epic-12](design/epic-12-decision-ready-report.md) |
| データ由来の文 | `Source text` | レポートに載る文のうち、分析の入力から来たもの。図の説明、データソースの項目、lineage の理由など。レポートでは記法として効かせず、指示として扱わない | ソーステキスト | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md) |
| レポートの検査 | `report_check` | できたレポートに、効く記法（図でない画像、タグ、lineage の書き出しに無い mermaid の行）が残っていないかを確かめること。レポートを書き換えない | — | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md) |
| 違反 | `Violation` | レポートの検査が挙げる、効く記法が残っている箇所。行・種類・その箇所の文字を持つ | — | [ADR-0019](adr/0019-report-source-text-escaped-and-checked.md) |
| lineage | `/data-lineage`、`tracked_pipe` | notebook の中のデータ加工の履歴と、その Mermaid 図 | 系譜 | fork 前 |
| データソース | `DataSource`、`source_ids` | catalog に登録した分析の入力データ。種類は open string。分析設計は使うデータソースの id を `source_ids` に宣言する | データ源 | [ADR-0020](adr/0020-design-declares-sources-in-source-ids.md) |
| 列のスキーマ | `ColumnSchema` | データソースの1列の名前・型・説明 | — | fork 前 |
| catalog | `/catalog-register`、`.insight/catalog/` | 登録したデータソースとドメイン知識の置き場 | カタログ | fork 前 |
| ドメイン知識 | `DomainKnowledge`、`DomainKnowledgeEntry` | 1つのデータソースについて分析から取り出した、使い回せる知識 | — | [epic-05b](design/epic-05b-knowledge-extraction.md) |
| finding | `finding` | その分析だけで言える発見。ドメイン知識にせず reflection に残す | — | [epic-05b](design/epic-05b-knowledge-extraction.md) |
| premortem | `/premortem` | 高いデータアクセスの前に、費用とリスクを見積もって報告すること。止めはしない | 事前評価 | [epic-05a](design/epic-05a-premortem-standalone.md) |
| リスクレベル | `RiskLevel` | premortem の判定。`HARD_BLOCK`・`HIGH`・`MEDIUM`・`LOW`・`SKIP` | — | [epic-05a](design/epic-05a-premortem-standalone.md) |
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
