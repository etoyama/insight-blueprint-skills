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
| [0006](0006-plugin-execution-model.md) | plugin execution model（bin ラッパー + env で自己完結） | Accepted（notebook の実行の行は ADR-0045 が改めた。`python` の1段で、marimo を使わない。PyPI の公開は ADR-0047 がやめた） |
| [0007](0007-upstream-judgment-gates.md) | 上流の認識論的判断ゲート（analysis-auto の design ビート化 + data-extraction ゲート） | Accepted |
| [0008](0008-notebook-figure-manifest.md) | notebook 図マニフェスト（verdict.figures[]）で生産者が図の真実を持つ | Accepted |
| [0009](0009-adopt-repo-template-flow.md) | repo-template の開発フローを採用する | Accepted |
| [0010](0010-skill-tdd-structure-tests.md) | skill の TDD は構造テストを先に書くことと読む | Accepted |
| [0011](0011-domain-model-overview-in-architecture.md) | Domain Model の全体図を ARCHITECTURE に置く | Accepted |
| [0012](0012-single-pr-scope.md) | Epic 以外の PR は、定めた振る舞いを変えない変更に限る | Accepted |
| [0013](0013-verdict-metric-optional-items.md) | verdict の指標に、任意の効果量・信頼区間・標本サイズを持たせる | Accepted（区間の項目は ADR-0052 が改めた。新しい verdict は `interval` に種類つきで書く） |
| [0014](0014-analysis-design-decision-context.md) | 分析設計に、任意の決定の文脈を入れ子の型で持たせる | Accepted |
| [0015](0015-host-connectors-for-optional-features.md) | 不変条件を「同梱しない」と書き、ホストのコネクタは任意の機能に限って使う | Accepted |
| [0016](0016-approval-before-external-send.md) | skill が `.insight/` の中身を外部へ送るときは、KEEP ゲートで承認を待つ | Accepted |
| [0017](0017-plugin-variables-not-in-bash-env.md) | plugin の変数は skill の本文で使い、bin ラッパーは自分の場所から plugin のルートを求める | Accepted |
| [0018](0018-catalog-io-omits-connection-by-default.md) | `catalog_io` は、頼まれない限りデータソースの `connection` を返さない | Accepted |
| [0019](0019-report-source-text-escaped-and-checked.md) | レポートに写すデータ由来の文は、削らずエスケープし、できたレポートをコードで検査する | Accepted（検査と手順の置き場は ADR-0040 が、エスケープする文字は Epic 29 が改めた） |
| [0020](0020-design-declares-sources-in-source-ids.md) | 分析設計が使うデータソースは `source_ids` に宣言し、下流の skill はそこだけを読む | Accepted（Context の「model の形は公開の契約」は ADR-0047 が改めた） |
| [0021](0021-default-package-allowlist.md) | パッケージ許可リストが無いときは、plugin の既定の許可リストを使う | Accepted（ファイルがあるときの扱いは ADR-0027 が改めた。既定の許可リストの中身は ADR-0046 が改め、marimo を外した） |
| [0022](0022-connection-reaches-only-the-notebook.md) | `connection` の値をモデルの文脈に入れるのは `/analysis-notebook` だけにする | Accepted |
| [0023](0023-catalog-holds-no-credentials.md) | catalog は認証情報を持たない | Accepted（入れ子のキーの判定と拒む語は ADR-0034 が改めた。Context の「model の形は公開の契約」は ADR-0047 が改めた） |
| [0024](0024-question-tree-yaml-and-generated-html.md) | 論点ツリーの正本は YAML に置き、表示は正本から生成する HTML にする | Accepted |
| [0025](0025-cited-answers-checked-after-writing.md) | モデルが書く答えは記録を引用させ、書いた後に検査する | Accepted |
| [0026](0026-analysis-auto-walks-the-question-tree.md) | 分析者の入口を `/analysis-auto` ひとつにし、論点ごとに巡回させる | Accepted（レポートとアップロードの段は ADR-0040 が消した） |
| [0027](0027-default-allowlist-always-allowed.md) | 既定の許可リストは常に許し、パッケージ許可リストのファイルはそこにパッケージを足す | Accepted（既定の許可リストの中身は ADR-0046 が改め、marimo を外した） |
| [0028](0028-hearing-is-its-own-journal-event.md) | 人に聞いた答えは、journal の出来事 `hearing` として残す | Accepted |
| [0029](0029-analyzing-reaches-conclusion-directly.md) | analyzing から結論の status へ直接遷移できるようにする | Accepted |
| [0032](0032-marketplace-serves-the-release-tag.md) | marketplace は plugin をリリースのタグから配る | Accepted（publish の失敗でタグを打ち直す決まりは ADR-0047 が改めた。タグは動かさず、版を上げる） |
| [0033](0033-derived-design-inherits-the-nodes-of-its-source.md) | 派生の分析設計は、派生元が結ばれている論点に聞かずに結ぶ | Accepted |
| [0034](0034-credential-check-joins-nested-keys.md) | 認証情報の判定は、入れ子のキーを親とつないで見て、`authorization` と `sas` を名前全体で拒む | Accepted |
| [0035](0035-handoff-trial-records-keep-their-score.md) | 引き継ぎの試行の記録は、その時点の鍵での採点として残し、CI で採点し直さない | Accepted |
| [0036](0036-design-note-is-a-generated-page-per-design.md) | 分析ノートは、分析設計ごとにコードが生成し、論点ツリーの HTML の中に並べる | Accepted（レポートを残すこととレポートへのリンクは ADR-0039 が改めた。cell の形（`@app.cell`）と notebook の HTML の書き出しは ADR-0045 が改めた。cell は `# %% <名前>` で区切り、notebook の HTML は書き出さない） |
| [0037](0037-tree-upload-sends-the-design-notes.md) | `/tree-upload` は、分析ノートを含む論点ツリーの HTML を、1ファイルのまま Artifact に送る | Accepted |
| [0038](0038-designdoc-draft-checks-whole-and-mockup.md) | DesignDoc 初版では、全体の整合を確かめ、成果物の見本を見せてから承認を求める | Superseded by FLOW-0005 |
| [0039](0039-report-is-the-final-report-of-a-theme-written-by-code.md) | レポートは、テーマの最終報告として、コードが論点ツリーと分析設計の記録から書く | Accepted |
| [0040](0040-report-export-sends-the-report-to-claude-docs.md) | `/report-export` がレポートを Claude Docs へ export し、古いレポートの skill と `report_check` を消す | Accepted |
| [0045](0045-notebook-is-plain-python-with-percent-cells.md) | notebook は `# %%` で cell を区切る素の Python にし、marimo の書式をやめる | Accepted |
| [0046](0046-marimo-leaves-the-plugin-env-and-the-default-allowlist.md) | plugin の env と既定の許可リストから marimo を外す | Accepted |
| [0047](0047-stop-publishing-to-pypi.md) | `insight-blueprint-lineage` を PyPI に公開するのをやめ、`/data-lineage` を plugin の env で走らせる | Accepted |
| [0048](0048-intent-decides-the-form-and-the-end-of-a-design.md) | 分析の意図が、分析設計の形と終わり方を決める | Accepted（意図を変えられる間の境目は ADR-0053 が改めた。状態ではなく、分析の印で区切る） |
| [0049](0049-legacy-exploration-stays-readable-and-is-marked.md) | 旧形式の探索は読めるままにし、印を付ける | Accepted |
| [0050](0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md) | 探索は予想を持たずに測った値を残し、検証は基準を分析設計に書く | Accepted（primary の指標が写すのは支持の線と棄却の線だと ADR-0052 が改めた。基準が空でないことは、`analyzing` に入るときに確かめると ADR-0053 が改めた） |
| [0051](0051-designs-nest-under-their-question-and-state-is-worded-by-role.md) | 論点ツリーは分析設計を論点の下の枝に出し、状態を役割つきの言葉で言う | Accepted |
| [0052](0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md) | verdict の指標は、支持の線と棄却の線、指標の判定、値の区間の種類、群の行を持つ | Accepted |
| [0053](0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md) | 分析を始めた検証の分析設計は、検証仮説・判定の基準・意図を変えない | Accepted |
| [0054](0054-review-covers-the-result-and-its-comments-reach-the-reader.md) | review は結果も対象にし、review コメントを分析ノートと論点ツリーに出す | Accepted |
| [0055](0055-the-root-question-is-shown-as-the-subject.md) | 分析者に見せる言葉を内側の用語と分け、「根の問い」を「主題」と呼ぶ | Accepted |
| [0056](0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md) | 答えの変化は引用の差から導き、上の論点と先の論点の両方のカードに出す | Accepted |
| [0057](0057-a-question-without-a-design-shows-the-progress-below-it.md) | 分析設計を直接結ばない論点は、下の論点の進捗を数で出す | Accepted |
| [0058](0058-a-tree-decision-may-cite-the-events-behind-its-reason.md) | ツリーの決定は、理由の根拠にした出来事を引用できる | Accepted |
| [0059](0059-the-handoff-trial-has-a-second-scenario-and-a-sixth-question.md) | 引き継ぎの試行に、2本目の合成シナリオと6つ目の問いを足す | Accepted |

- ADR-0001〜0008 は旧形式のまま残す。ADR-0009 からは新形式（Problem と Decision Analysis の節を持つ）で書く。
- 開発フローの決定の出典は [flow/](flow/README.md) にある。repo-template の ADR のコピーで、`FLOW-000N` と表記する。
  このリポジトリで行った決定は、フローに関するものも含めてこの索引に載せる。
