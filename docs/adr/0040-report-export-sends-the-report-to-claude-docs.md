# ADR-0040: `/report-export` がレポートを Claude Docs へ export し、古いレポートの skill と `report_check` を消す

## Status

Accepted

## Context

[Epic 29](../design/epic-29-theme-report-export.md) はレポートをテーマの最終報告に改め、コードが記録から書くと決めた（[ADR-0039](0039-report-is-the-final-report-of-a-theme-written-by-code.md)）。
この ADR はそのレポートを Claude Docs に送る skill と、古いレポート周りの扱いを決める。2026-11-23 に、DesignDoc 初版のセッションで人間と決めた。

比較の前提にした事実と、確かめた方法は次のとおり。

- 今は `/analysis-report {design_id}` がレポートを書き、`/report-upload {design_id}` が Claude Docs に送る。`/analysis-auto` は、結論の出た分析設計ごとにレポートを AUTO で書き、アップロードを始める
  （`skills/analysis-auto/SKILL.md` の item 8 と 9、[Epic 27](../design/epic-27-resume-upload.md)）。
- 人間は、報告できる品質だと分析者が判断したときに export すると述べた。「upload」より「export」という呼び方が合うとも述べた（2026-11-23）。
- `/tree-upload` は、`tree_io render` が書いたファイルを、書き換えずにそのまま Artifact に送る（[ADR-0037](0037-tree-upload-sends-the-design-notes.md)）。レポートは Markdown として送り、送った先で手直しする。
- Claude Docs の本文は、モデルがツール呼び出しの引数として渡す。コードが書いた Markdown は、手元のファイルとして置き、skill がそれを読んで送る（コネクタの guide を読んだ）。
- 論点ツリーは `/analysis-framing` が作る。`/analysis-design` を直接使うと、論点ツリーの無いテーマの分析設計ができる（両方の `SKILL.md` を読んだ）。
  その分析ノートは単独のページで、Artifact に送る手段が無い（[ADR-0036](0036-design-note-is-a-generated-page-per-design.md) の Negative）。
- `report_check` は、モデルが書いた Markdown に、記法として働く記号が残っていないかを確かめる（[ADR-0019](0019-report-source-text-escaped-and-checked.md)）。
- 古いレポートに依るものは、main（c2af3c6）を `git ls-tree` と `git grep` で洗った。一覧は Epic 29 の Background にある。
- marketplace はリリースのタグを配る。古いバージョンを使い続ける人は、バージョンを固定できる（[ADR-0032](0032-marketplace-serves-the-release-tag.md)）。
- 新しいレポートのファイル名はテーマの id で、古いレポートは分析設計の id である。同じ `.insight/reports/` に置いても、名前は重ならない。

## Problem

- 課題1: レポートを書くのがコードになり、単位がテーマになった。今の2つの skill はどちらも今の形では要らない。
- 課題2: `/analysis-auto` が巡回のたびにレポートを書いて送り始める。報告できるかを分析者が判断する前に始まる。
- 課題3: skill の名前と用語は、配った後で変えにくい。同じ名前のまま引数の意味を変えると、利用者は知らないうちに違う動きに当たる。
- 課題4: 古い skill を消すと、論点ツリーの無いテーマの分析設計は、外へ配る手段が無くなる。
- 課題5: 新旧が並ぶ間は、分析ノートとレポートが二重にある状態が残る。

扱わない範囲: レポートの中身と形（ADR-0039）。リリースのバージョン番号と時期。送った Doc の更新と共有。

## Decision Analysis

skill の名前と形。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 外へ送るのは、KEEP ゲートの承認の後だけである | Must | - | - | [ADR-0016](0016-approval-before-external-send.md) |
| M2 | export を始めるのは分析者で、巡回が自動で始めない | Must | - | - | 課題2、人間の発言 |
| W1 | 名前が、することを言い当てる | Want | 解決 | 中（人間の感触） | 課題1 |
| W2 | 既存の利用者が、同じ名前で違う動きに当たらない | Want | 解決 | 中（Claude の推測） | 課題3 |
| W3 | skill の数と手順 | Want | 費用 | 高（人間） | YAGNI |

| Must | N1: `/report-export` を1つ新設する | N2: 今の2つの名前を残す | N3: `/tree-export` を1つ新設する | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |
| M2 | 満たす | 満たす | 満たす | 満たさない（巡回がアップロードを始める） |

| Want | N1 | N2 | N3 |
|---|---|---|---|
| W1 | 言い当てる。レポートを export する。 | 「upload」のままで、人間の感触と合わない。 | 送る物は論点ツリーの写しではなく、レポートである。 |
| W2 | 古い名前は無くなり、打てば無いと分かる。 | 同じ名前で、引数の意味と中身が変わる。 | N1 と同じ。 |
| W3 | 1つ。 | 2つ。書くだけの段は、コードを1回呼ぶだけになる。 | 1つ。 |

- 差がつく基準: W1 は N1、W2 と W3 は N1 と N3 が勝つ。
- 感度: 論点ツリーの系列の skill として並べることを重く見るなら N3 になる。

論点ツリーの無いテーマ。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| W4 | 論点ツリーの無い分析設計にも、外へ配る手段が残る | Want | 解決 | 低（人間） | 課題4 |
| W5 | レポートの形が1つである | Want | 解決 | 高（人間） | ADR-0039 |
| W6 | 足すコードと手順 | Want | 費用 | 高（人間） | YAGNI |

| Want | T1: 何も足さない | T2: `/tree-upload` が単独のページも送る | T3: `/report-export` を論点ツリー無しでも動かす |
|---|---|---|---|
| W4 | 残らない。今できていることが、できなくなる。 | 分析ノートの形で残る。 | 残る。 |
| W5 | 1つ。 | 1つ。 | 2つになる。 |
| W6 | 無し。 | 小さい。 | レポートの形がもう1つ要る。 |

- 差がつく基準: W4 は T2 と T3、W5 は T1 と T2、W6 は T1 が勝つ。
- 感度: W4 が中以上なら T2 になる。

古いレポート周りの消し方。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M3 | 利用者の手元のファイルを、黙って消したり書き換えたりしない | Must | - | - | 課題3 |
| W7 | Epic が終わった時点で、レポートの経路が1本である | Want | 解決 | 高（人間） | 課題5 |
| W8 | 既存の利用者が、変更に気づける | Want | 解決 | 中（Claude の推測） | 課題3 |
| W9 | 保守する物と、移行のために足す物の量 | Want | 費用 | 高（人間） | YAGNI |

| Must | G1: 一度に消す | G2: 1リリース併存させる | G3: 名前だけ残して案内にする | 何もしない |
|---|---|---|---|---|
| M3 | 満たす | 満たす | 満たす | 満たす |

| Want | G1 | G2 | G3 |
|---|---|---|---|
| W7 | 1本になる。 | ならない。 | 1本になる。 |
| W8 | リリースノートで気づく。 | 予告の文で気づく。 | 古い名前を打つと案内が出る。 |
| W9 | 一番小さい。 | テンプレート、`report_check`、構造テストをもう1リリース保守する。 | 案内だけの skill が残る。 |

- 差がつく基準: W7 と W9 は G1、W8 は G3 が勝つ。
- 感度: W8 を高にすると G3 になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| N1 | 「レポート」の意味が変わり、古い文書と食い違う | ADR-0039 に用語の変更を書く。凍結した DesignDoc は直さない |
| N2 | 利用者が分析設計の id を渡して、エラーか別物を受け取る | 抑えにくい |
| N3 | `/tree-upload` と紛れる | 説明で分ける |
| T1 | 分析設計1つの軽い分析で、配るために論点ツリーを作ることになる | リリースノートに書く。要る声が出たら T2 を足す |
| T2 | `/tree-upload` の名前と送る物が合わなくなる | 説明に書く |
| T3 | 形が2つになる | 抑えにくい |
| G1 | バージョンを上げた人が、古い skill が無いことに戸惑う。`report_check` が無くなった後に、エスケープの漏れで、データ由来の文が Docs で記法として働く | リリースノートに書く。エスケープのテストを、ADR-0019 が挙げた記法から書く |
| G2 | 併存の間に、古いレポートに依る物がまた増える | 抑えにくい |
| G3 | 案内だけの skill が消されずに残る | 消すバージョンを決めて書く |
| 何もしない | 課題1 から課題5 が残る | なし |

## Decision

N1、T1、G1 を採る（人間の判断、2026-11-23）。決め手は名前では W1 と W2、論点ツリーの無いテーマでは W6、消し方では W7 と W9。

- `/report-export {theme_id}` を新設する。`tree_io report --theme {theme_id}` でレポートを書き、KEEP ゲートの承認の後に、Claude Docs の新しい Doc として送る。
- 外へ送るときの決まり（ADR-0016）は変えない。送るファイル（レポートと図）を列挙し、承認を待つ。承認は1回の実行に限り、覚えない。
  同じ画面に、結論の出ていない分析設計の数と、答えを書いた振り返りの回を出す。
- コネクタが無ければ送らず、Markdown のレポートのパスを伝える（[ADR-0015](0015-host-connectors-for-optional-features.md)）。
- いつも新しい Doc を作る。既存の Doc を変えず、送った記録を持たない。図は1枚ずつ載せる。載せられない図と、分析者が断った図の扱いは、今の `/report-upload` と同じにする。
- `/analysis-auto` は `/report-export` を自動で始めない。report と upload の段を消し、テーマの振り返りの後に、次に使える skill として名前を挙げるだけにする。
- 論点ツリーの無いテーマには外へ配る手段を足さない。`/report-export` はレポートを書けない理由を伝えて終わる。配るには `/analysis-framing` で論点ツリーを作る。
- `/analysis-report`、`/report-upload`、`apa-template.md`、`report_check`（`bin/`、モジュール、テスト）を、Epic 29 の中で一度に消す。利用者の手元の古いレポートには触らない。
- ADR-0019 の Decision のうち、`report_check` ができたレポートを検査することと、手順の正本を `apa-template.md` に置くことは、やめる。レポートを書くのがコードになり、検査の対象が無くなるためである。
  データ由来の文の写し方（改行とタブの連なりを空白1つにし、8つの文字の前にバックスラッシュを置く。削らない）は、レポートを書くコードが受け持つ。
  データ由来の文の中の指示に従わない決まりは変えない。`/report-export` は、レポートの中の文を指示として扱わない。
- 用語「export」を足す。レポートを Claude Docs の新しい Doc として送ることを指す。「アップロード」は `/tree-upload` だけを指す語にする。
  「レポートの検査」は用語表から消し、「違反」はツリーの検査が挙げるものだけを指す語にする。「データ由来の文」の定義から、レポートの検査への言及を外す。用語表は実装の Story で直す。
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の KEEP ゲートの一覧とシーケンス図、[docs/PRD.md](../PRD.md) の機能要件と成功基準（`report_check` の違反が0件）は、実装の Story で直す。
- `CHANGELOG.md` に、消した skill と代わりの手段、論点ツリーの無いテーマでは外へ配る手段が無くなること、バージョンを固定する方法を書く。

## Consequences

### Positive

- レポートを作って送る経路が1本になる。skill は1つで、始めるのは分析者である。
- `/analysis-auto` の巡回が短くなる。巡回のたびにアップロードの承認を聞かれることが無くなる。
- 保守する物が減る。`report_check` と、その検査が見ていた記法の決まりが要らなくなる。

### Negative

- 配っている skill が2つ無くなる。バージョンを上げた人は、打った skill が無いことで変更を知る。
- 論点ツリーの無いテーマの分析設計は、外へ配る手段が無くなる。この決定の前はレポートを Claude Docs に送れた。
- できたレポートを後から検査するものが無くなる。エスケープの正しさは、コードとそのテストだけが支える。
- `/report-export` は本文をモデルが引数として渡す。モデルが本文を書き換えないことは、skill の文の決まり頼みである（今の `/report-upload` と同じ限界）。
- 利用者の手元に、古い形のレポート（`.insight/reports/{design_id}.md`）が残る。新しいレポートと同じフォルダに並ぶ。
- [Epic 12](../design/epic-12-decision-ready-report.md) の US-4、[Epic 13](../design/epic-13-report-source-text.md)、[Epic 27](../design/epic-27-resume-upload.md) の DesignDoc の記述は、この ADR で古くなる。凍結しているので直さない。

## Alternatives considered

- **`/report-export` を2段に分け、書く skill と送る skill にする** — 書く段は `tree_io report` を1回呼ぶだけで、skill にする中身が無い。
- **`report_check` を、コードが書いたレポートの後検査として残す** — 検査が見る形（図でない画像、lineage の mermaid の行）は古いレポートの形で、新しいレポートに合わせて作り直すことになる。エスケープはテストで確かめるほうが軽い。

## Related

- Epic: [#177](https://github.com/etoyama/insight-blueprint-skills/issues/177)、[epic-29](../design/epic-29-theme-report-export.md)
- 関係する ADR: [ADR-0015](0015-host-connectors-for-optional-features.md)、[ADR-0016](0016-approval-before-external-send.md)、[ADR-0019](0019-report-source-text-escaped-and-checked.md)、[ADR-0032](0032-marketplace-serves-the-release-tag.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0037](0037-tree-upload-sends-the-design-notes.md)、[ADR-0039](0039-report-is-the-final-report-of-a-theme-written-by-code.md)
- Supersedes: なし（ADR-0019 の Decision の2点を改める）
