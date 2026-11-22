# Architecture Decision Records

cross-epic な設計判断・長期制約・`docs/ARCHITECTURE.md` への変更を記録する。
新規は [.claude/rules/adr-template.md](../../.claude/rules/adr-template.md) をコピーし、
確定後この索引に追記する。1ファイル1決定、`NNNN` は4桁ゼロ詰め連番。

| ADR | Title | Status |
|---|---|---|
| [0001](0001-drop-mcp-server-embed-validation.md) | MCPサーバを廃止し、設計書検証を埋め込みライブラリ＋pre-write hook に移す | Accepted |
| [0002](0002-trunk-based-epic-stacking.md) | `dev` を廃止しトランクベース（main）+ stacked Epic に移行する | Accepted |
| [0003](0003-skill-yaml-io-via-design-io.md) | skill の設計書 I/O を design_io ヘルパに集約する | Accepted |
| [0004](0004-open-string-catalog-taxonomy.md) | catalog の taxonomy を open string にする | Accepted |
| [0005](0005-selective-autonomous-chaining.md) | selective autonomous chaining（/analysis-auto driver） | Accepted |
| [0006](0006-plugin-execution-model.md) | plugin execution model（bin ラッパー + env で自己完結） | Accepted |
| [0007](0007-upstream-judgment-gates.md) | 上流の認識論的判断ゲート（analysis-auto の design ビート化 + data-extraction ゲート） | Accepted |
| [0008](0008-notebook-figure-manifest.md) | notebook 図マニフェスト（verdict.figures[]）で生産者が図の真実を持つ | Accepted |
| [0009](0009-adopt-repo-template-flow.md) | repo-template の開発フローを採用する | Accepted |
| [0010](0010-skill-tdd-structure-tests.md) | skill の TDD は構造テストを先に書くことと読む | Accepted |
| [0011](0011-domain-model-overview-in-architecture.md) | Domain Model の全体図を ARCHITECTURE に置く | Accepted |
| [0012](0012-single-pr-scope.md) | Epic 以外の PR は、定めた振る舞いを変えない変更に限る | Accepted |
| [0013](0013-verdict-metric-optional-items.md) | verdict の指標に、任意の効果量・信頼区間・標本サイズを持たせる | Accepted |
| [0014](0014-analysis-design-decision-context.md) | 分析設計に、任意の決定の文脈を入れ子の型で持たせる | Accepted |
| [0015](0015-host-connectors-for-optional-features.md) | 不変条件を「同梱しない」と書き、ホストのコネクタは任意の機能に限って使う | Accepted |
| [0016](0016-approval-before-external-send.md) | skill が `.insight/` の中身を外部へ送るときは、KEEP ゲートで承認を待つ | Accepted |
| [0017](0017-plugin-variables-not-in-bash-env.md) | plugin の変数は skill の本文で使い、bin ラッパーは自分の場所から plugin のルートを求める | Accepted |
| [0018](0018-catalog-io-omits-connection-by-default.md) | `catalog_io` は、頼まれない限りデータソースの `connection` を返さない | Accepted |
| [0019](0019-report-source-text-escaped-and-checked.md) | レポートに写すデータ由来の文は、削らずエスケープし、できたレポートをコードで検査する | Accepted |
| [0020](0020-design-declares-sources-in-source-ids.md) | 分析設計が使うデータソースは `source_ids` に宣言し、下流の skill はそこだけを読む | Accepted |
| [0021](0021-default-package-allowlist.md) | パッケージ許可リストが無いときは、plugin の既定の許可リストを使う | Accepted（ファイルがあるときの扱いは ADR-0027 が改めた） |
| [0022](0022-connection-reaches-only-the-notebook.md) | `connection` の値をモデルの文脈に入れるのは `/analysis-notebook` だけにする | Accepted |
| [0023](0023-catalog-holds-no-credentials.md) | catalog は認証情報を持たない | Accepted（入れ子のキーの判定と拒む語は ADR-0034 が改めた） |
| [0024](0024-question-tree-yaml-and-generated-html.md) | 論点ツリーの正本は YAML に置き、表示は正本から生成する HTML にする | Accepted |
| [0025](0025-cited-answers-checked-after-writing.md) | モデルが書く答えは記録を引用させ、書いた後に検査する | Accepted |
| [0026](0026-analysis-auto-walks-the-question-tree.md) | 分析者の入口を `/analysis-auto` ひとつにし、論点ごとに巡回させる | Accepted |
| [0027](0027-default-allowlist-always-allowed.md) | 既定の許可リストは常に許し、パッケージ許可リストのファイルはそこにパッケージを足す | Accepted |
| [0028](0028-hearing-is-its-own-journal-event.md) | 人に聞いた答えは、journal の出来事 `hearing` として残す | Accepted |
| [0029](0029-analyzing-reaches-conclusion-directly.md) | analyzing から結論の status へ直接遷移できるようにする | Accepted |
| [0032](0032-marketplace-serves-the-release-tag.md) | marketplace は plugin をリリースのタグから配る | Accepted |
| [0033](0033-derived-design-inherits-the-nodes-of-its-source.md) | 派生の分析設計は、派生元が結ばれている論点に聞かずに結ぶ | Accepted |
| [0034](0034-credential-check-joins-nested-keys.md) | 認証情報の判定は、入れ子のキーを親とつないで見て、`authorization` と `sas` を名前全体で拒む | Accepted |
| [0035](0035-handoff-trial-records-keep-their-score.md) | 引き継ぎの試行の記録は、その時点の鍵での採点として残し、CI で採点し直さない | Accepted |
| [0036](0036-design-note-is-a-generated-page-per-design.md) | 分析ノートは、分析設計ごとにコードが生成し、論点ツリーの HTML の中に並べる | Accepted |
| [0037](0037-tree-upload-sends-the-design-notes.md) | `/tree-upload` は、分析ノートを含む論点ツリーの HTML を、1ファイルのまま Artifact に送る | Accepted |

- ADR-0001〜0008 は旧形式のまま残す。ADR-0009 からは新形式（Problem と Decision Analysis の節を持つ）で書く。
- 開発フローの決定の出典は [flow/](flow/README.md) にある。repo-template の ADR のコピーで、`FLOW-000N` と表記する。
  このリポジトリで行った決定は、フローに関するものも含めてこの索引に載せる。
