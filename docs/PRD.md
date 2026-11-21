# PRD: insight-blueprint-skills

仮説駆動 EDA プラットフォームを **Claude Code skill plugin** として提供するプロダクトの
要件定義。詳細なアーキテクチャは [ARCHITECTURE.md](ARCHITECTURE.md)、個別の設計判断は
[docs/adr/](adr/) を正とする。本書は「なぜ・何を」を簡潔に示す上位ドキュメント。

## ビジョン / 解く課題

分析者が「仮説 → 設計 → 検証 → 結論」のサイクルを、加工の透明性とリネージを保ったまま
回せるようにする。本家 insight-blueprint は MCP 常駐サーバ + WebUI + SQLite で同じ価値を
提供してきたが、運用の実態は Claude Code との対話に寄り、サーバ/WebUI のメンテ・オンボーディング
コストが正味の負債になっていた（[ADR-0001](adr/0001-drop-mcp-server-embed-validation.md)）。

本プロダクトはその核を **skills + YAML + 埋め込み検証ライブラリ**で再構成し、常駐プロセスを
持たない軽量な plugin として同じ価値を届ける。

その上で、分析者が合意した問いを1つ AI に委ね、親の問いにどこまで答えられたかを把握して、
次の一手を自分で選べるようにする。今の reflection とレポートは分析設計1つを単位にしており、
同じテーマの複数の分析設計を束ねて「親の問いへの答えがどう動いたか」を見る場所が無い。
論点ツリーがその場所になる。

- 利用者: 経験のある分析者と、経験の浅い分析者の両方。
- 到達点: 業務では、顧客が決めたいことを決められるところまで。研究では、想定読者が主張とその成立範囲を吟味できるところまで。
  どちらも初版から扱う。

## コアバリュー（温存すべき核）

- marimo notebook 契約 & lineage — データ加工の透明性・追跡可能性
- 分析設計（`*_hypothesis.yaml`）と、それを生成する skills
- journal / reflection — 結果の解釈と結論づけ
- premortem — 高コストなデータアクセス前の費用・リスク評価
- 論点ツリー — テーマの問いの構造と、親の問いへの現時点の答え

## 主要要件

### 機能要件

- 分析設計の整合性を**サーバを常駐させずに**強制する（スキーマ + 状態遷移）
- 分析設計・journal・reflection・revision を skill 経由の対話で作成・更新できる
- データ加工をリネージとして記録し Mermaid 図で出力できる
- データソースを catalog として登録・検索できる
- 結論の出た分析を、読者がそれだけで判断できるレポートにまとめられる
  （決定の文脈、データの素性、効果の大きさと確かさ、推奨を載せる）
- レポートを Claude Docs にアップロードし、読者がコメントできる形で渡せる。
  送るのは分析者が承認した後だけで、ホストに Claude Docs のコネクタが無くてもレポートは残る
- テーマごとに論点ツリーを持てる。着手時には、根の問い、暫定の第一階層、最初に調べる論点と
  それを選んだ理由を示す。第二階層が空でも着手できる
- 論点ツリーの根に到達点を持てる。業務では誰が何を決めるか、研究では想定読者と主張の範囲。
  到達点を変えたときは、変えた理由が残り、変える前の到達点に対する答えはそれと分かる
- 振り返りでは、テーマに属する複数の分析設計を横断し、論点ごとに現時点の答え、それを弱める証拠と留保、
  前回からの変更、次の候補を示せる。同じ論点を深めるか、親に戻るか、区切るかと、その理由を残せる
- 現時点の答えの各文から、根拠にした journal の出来事と分析設計へ戻れる。
  探索中に生まれた論点は生まれた出来事へ戻れる
- 論点ツリーを手元で読める表示にできる。分析者が承認した後に限り、ホストの Artifact として渡せる

### 非機能要件

- 常駐プロセス・MCP サーバ・SQLite を同梱しない（No daemon / No MCP server / No SQLite）。
  ホストが持つコネクタは、無くても核が動く任意の機能に限って使う（[ADR-0015](adr/0015-host-connectors-for-optional-features.md)）
- 検証ロジックは I/O を持たない純関数ライブラリに集約し、単一正本とする
- Claude Code plugin として配布・利用できる
- リリースは tag 駆動（`v*`）。トランク（main）へのマージは publish を起こさない
- 分析者に届く数と結論は、記録に書いてあるものに限る。モデルに書かせた文は書いた後に機械で検査する
  （レポートは `report_check`、論点ツリーはツリーの検査）
- 論点ツリーの表示は正本から決定的に生成する。モデルに表示を書かせない

## スコープ外

- 分析設計の全文検索（旧 FTS5 機能の再構築。現状コアは非対象）
- WebUI / REST API
- MCP 常駐サーバ
- 施策の実行と、承認のシステム化
- 分析の継続運用の監視
- 顧客や現場へのヒアリングそのもの。AI は質問の案づくりと既知の情報の整理までを担う

## ロードマップ

E1〜E5 は [ADR-0001 §Related](adr/0001-drop-mcp-server-embed-validation.md) の解体計画に対応する。
Epic 06 からは軽量版の上に分析の能力を足していく。

| Epic | DesignDoc | 内容 | 状態 |
|---|---|---|---|
| E1 | [epic-01](design/epic-01-remove-webui.md) | WebUI / REST 削除 | 完了 |
| E2 | [epic-02](design/epic-02-validate-lib.md) | `validate.py` 抽出 + pre-write hook 新設 | 完了 |
| E3 | [epic-03](design/epic-03-skills-yaml-io.md) | skill を YAML 直接 I/O（分析設計のライフサイクル） | 完了 |
| E3.5 | [epic-3.5](design/epic-3.5-remaining-yaml-io.md) | catalog / premortem / lineage の MCP→YAML 変換 + batch-analysis 撤去 | 完了 |
| E4 | [epic-04](design/epic-04-remove-mcp-server.md) | MCPサーバ層削除 | 完了 |
| E5a | [epic-05a](design/epic-05a-premortem-standalone.md) | premortem 自立化（report-only 化） | 完了 |
| E5b | [epic-05b](design/epic-05b-knowledge-extraction.md) | knowledge 抽出強化（Claude-native + source-scoped） | 完了 |
| E5c | [epic-05c](design/epic-05c-catalog-flexibility.md) | catalog 柔軟化（open string taxonomy） | 完了 |
| Epic 06 | [epic-06](design/epic-06-analysis-review.md) | `/analysis-review`（レビューの生産者） | 完了 |
| Epic 07 | [epic-07](design/epic-07-analysis-notebook.md) | `/analysis-notebook`（methodology から marimo notebook を生成・実行） | 完了 |
| Epic 08 | [epic-08](design/epic-08-analysis-auto.md) | `/analysis-auto`（guided autopilot） | 完了 |
| Epic 09 | [epic-09](design/epic-09-installable-plugin.md) | plugin をインストール先で動かす（execution model） | 完了 |
| Epic 10 | [epic-10](design/epic-10-analysis-report.md) | `/analysis-report`（APA 風レポート） | 完了 |
| Epic 11 | [epic-11](design/epic-11-repo-template-compliance.md) | repo-template の開発フローへの準拠 | 完了 |
| Epic 12 | [epic-12](design/epic-12-decision-ready-report.md) | 意思決定に使えるレポートと Claude Docs へのアップロード | 完了 |
| Epic 13 | [epic-13](design/epic-13-report-source-text.md) | レポートに写すデータ由来の文の扱い | 完了 |
| Epic 14 | [epic-14](design/epic-14-report-template-gaps.md) | レポートのテンプレートに書いていない所を決める | 完了 |
| Epic 15 | [epic-15](design/epic-15-declared-source-ids.md) | 分析設計が使うデータソースを `source_ids` に宣言する | 完了 |
| Epic 16 | [epic-16](design/epic-16-default-allowlist.md) | パッケージ許可リストが無いプロジェクトでは既定の許可リストを使う | 完了 |
| Epic 17 | [epic-17](design/epic-17-connection-boundary.md) | 接続情報を notebook の外に出さず、認証情報を catalog に入れない | 完了 |
| Epic 18 | [epic-18](design/epic-18-question-tree.md) | テーマごとの論点ツリー | 完了 |
| Epic 19 | [epic-19](design/epic-19-direct-conclusion.md) | analyzing から結論の status へ直接遷移する | 完了 |
| Epic 26 | [epic-26](design/epic-26-reflection-materials.md) | reflection が結論の前に図・指標・notebook の場所を出す | 完了 |

各 Epic の DesignDoc は `## Scope` 節で、本書のどの要件と
ARCHITECTURE のどのコンポーネントを前進させるかを示す。

## 成功基準

### 製品

- 引き継ぎの試行: 合成シナリオの論点ツリーの表示だけを渡された別の読み手が、次を説明できる。
  読み手は人と、文脈を持たない別の Claude セッションの両方とし、正誤は文言でなく判断の一致で採点する。
  - 親の問いへの現時点の答え
  - 未着手の論点と、分析は済んだが未判別の論点の区別
  - 現時点の答えを支える証拠と弱める証拠、それぞれの出所の分析設計と journal の出来事
  - 前回の振り返りから変わった答えと、変えた証拠
  - 次に調べる論点と、それを選ぶ理由
- 分析者に届けた論点ツリーとレポートで、ツリーの検査と `report_check` の違反が0件
- 人が確認・再構成に費やした時間は試行ごとに記録する。目標値は、既存のフローでの基準値が取れてから決める

### 移行期（達成済み）

- 検証の正本が `validate.py` 1 箇所に集約され、hook と skill の双方から再利用される
- 移行の各段階で `pytest` が全緑を保つ（挙動の非回帰）
- 常駐プロセス・WebUI・SQLite 依存が消え、plugin として動作する
- コアバリュー（marimo 契約 / 分析設計 / journal・reflection / premortem）が維持される
