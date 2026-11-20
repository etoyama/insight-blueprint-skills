# ADR-0024: 論点ツリーの正本は YAML に置き、表示は正本から生成する HTML にする

## Status

Accepted

## Context

PRD の改訂（2026-11-20）で、テーマごとの論点ツリーを核に加えた（[docs/PRD.md](../PRD.md)、[epic-18](../design/epic-18-question-tree.md)）。
論点ツリーは、`/analysis-framing` が作り、`/analysis-reflection` が振り返りのたびに答えを足す。分析者と、引き継いだ人や顧客が読む。
人間が書いた Handoff は「出力は Markdown 1つ」と書いていた。壁打ちで、正本の置き場（判断2）と表示の形（判断2'）を分けて決めた。

比較の前提にした事実は次のとおり。

- 分析設計の検証は `src/insight_blueprint/validate.py` が正本で、`design_io` と pre-write hook（`hooks/validate-design.py`）の両方が使う。
  hook が捕まえるのは `*_hypothesis.yaml` だけ（[docs/ARCHITECTURE.md](../ARCHITECTURE.md) を読んで確かめた）。
- `.insight/` にテーマ単位のファイルは無い。`theme_id` は分析設計の id の接頭辞としてだけある（`skills/_shared/design_io.py:140`）。
- ホストの機能を使ってよいのは、無くても核が動く任意の機能だけ（[ADR-0015](0015-host-connectors-for-optional-features.md)）。
  `.insight/` の中身を外へ送るときは、KEEP ゲートで承認を待つ（[ADR-0016](0016-approval-before-external-send.md)）。`/report-upload` がこの2つに従う前例。
- Artifact は手元の HTML ファイルを公開する仕組みで、公開した直後は本人にしか見えない。外部の script は決まった CDN からしか読めない。
  どのホストやアカウントでも使えるかは未確認（このリポジトリを書いているセッションの Artifact ツールの説明で確かめた）。

## Problem

- 課題1: 振り返りでは「前回からの変更」と「根拠の参照切れ」を確かめる必要がある。正本が Markdown 1つだと、モデルが自分の書いた Markdown を読んで書き直すことになり、差分も参照も機械で検査できない。
- 課題2: 論点ツリーは全体像をつかむための道具で、見せ方の表現力が価値を左右する（人間の発言）。状態の区別、論点から根拠への掘り下げ、変わった答えの強調が要る。
- 課題3: 表示をモデルが毎回書き起こすと、正本と表示がずれる。#105 と同じ型の捏造になる。
- 課題4: 定例報告やレビューで、現在地を引き継いだ人や顧客に渡したい。

扱わない範囲: 論点ツリーのスキーマの細部（[epic-18](../design/epic-18-question-tree.md) の Domain Model）。答えの文の検査（[ADR-0025](0025-cited-answers-checked-after-writing.md)）。

## Decision Analysis

正本の置き場（判断2）。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | No daemon / No MCP / No SQLite を守る | Must | - | - | ADR-0015 |
| W1 | 前回からの変更と参照切れを機械で検査できる | Want | 解決 | 高（Claude の推測、人間が推奨を採った） | 課題1 |
| W2 | 増える部品が少ない | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | YAML を正本 | Markdown を正本 | 分析設計に欄を足して組み立てる | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |

| Want | YAML を正本 | Markdown を正本 | 分析設計に欄を足して組み立てる |
|---|---|---|---|
| W1 | 論点の id・親子・引用を検査できる。変更は git の差分で取れる。 | 検査できない。 | 引用は検査できるが、分析設計の無い未着手の論点を置く場所が無い。 |
| W2 | モデル、検証、`tree_io` が増える。 | 増えない。 | 分析設計のスキーマに1欄増えるだけ。 |

表示の形（判断2'）。正本は YAML とする。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | ホストの機能が無くても手元で読める | Must | - | - | ADR-0015 |
| M2 | 外へ送るのは KEEP ゲートで承認した後だけ | Must | - | - | ADR-0016 |
| W1 | 表現力（状態がひと目で分かる、根拠へ掘れる、変わった所が見える） | Want | 解決 | 高（人間） | 課題2 |
| W2 | 表示が正本とずれない | Want | 解決 | 高（Claude の推測） | 課題3 |
| W3 | URL で渡せる | Want | 解決 | 中（Claude の推測） | 課題4 |
| W4 | 作る・保守する部品の量 | Want | 費用 | 中（Claude の推測） | YAGNI |

| Must | Markdown と mermaid | 生成する HTML | 生成する HTML と任意の Artifact | Claude Docs を主な表示に | モデルが毎回書く |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たさない（コネクタが無いと読めない） | 満たす |
| M2 | 満たす | 満たす | 満たす | 満たす | 満たす |

| Want | Markdown と mermaid | 生成する HTML | 生成する HTML と任意の Artifact |
|---|---|---|---|
| W1 | 状態は色で出せるが、掘り下げと変わった所の強調はほぼ出せない。 | 折りたたみ、状態、根拠一覧、変わった所の強調を出せる。 | 生成する HTML と同じ。 |
| W2 | 生成するのでずれない。 | ずれない。 | 手元と同じファイルを送るのでずれない。 |
| W3 | git か貼り付けで渡す。 | ファイルで渡す。 | URL で渡せる。 |
| W4 | 最も少ない。 | HTML を作るコードが増える。 | HTML を作るコードと、公開の手順1つが増える。 |

- 差がつく基準: 正本では W1。表示では W1・W3・W4。
- 感度: 表示の W1 を中に下げると Markdown と mermaid が残る。W3 を低に下げると、生成する HTML だけで足りる。
  「モデルが毎回書く」は W2 で、どの重みでも生成する案に負ける。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| YAML を正本 | `.insight/` の構成と hook の対象が増える | 検証は `validate.py` に足し、正本を1つに保つ |
| Markdown を正本 | 参照切れと捏造を止められない | （抑えられない） |
| Markdown と mermaid | 表現力が足りず、ツリーが読まれなくなる | （課題2 そのもの） |
| 生成する HTML | HTML を作るコードが膨らむ | 表示の要件を epic-18 の US-5 の AC に縛る。描画ライブラリを入れない |
| 生成する HTML と任意の Artifact | Artifact が使えないアカウントがある。分析の中身を claude.ai に置く | 公開は任意。KEEP ゲートで送るファイルを列挙する。使えなければ手元の HTML で終わる |
| Claude Docs を主な表示に | コネクタが無いとツリーを読めない | （M1 で却下） |

## Decision

正本は YAML、表示は正本から生成する HTML、Artifact は承認の後の任意の手順とする（人間の判断2・2'、2026-11-20）。決め手は、正本では W1（検査できること）、表示では W1（表現力）と W3（URL で渡せること）。

- 論点ツリーの正本は `.insight/themes/{theme_id}_tree.yaml` に置く。1テーマに1ファイル。
- 形の検証は `validate.py` に足す。`tree_io` は書く前に、pre-write hook は `*_tree.yaml` への直接の書き込みで、同じ検証を通す。
- 表示は `tree_io render` が作る自己完結の HTML（`.insight/themes/{theme_id}_tree.html`）。外部の script と stylesheet を読まない。同じ正本からは同じ HTML ができる。モデルに HTML を書かせない。
- Markdown 版の表示は作らない。読む面が2つあると、どちらが正か迷うため（人間の判断）。
- Artifact で渡すのは任意。送るファイルを列挙して KEEP ゲートで承認を待ち、送るのは手元の HTML と同じファイルにする。Artifact が使えないホストでは、手元の HTML のパスを案内して終わる。
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の `.insight/` の構成、hook の対象、KEEP ゲートの一覧は、Epic 18 の Story で実装と同じ PR で直す。

## Consequences

### Positive

- 振り返りの差分と参照切れを、git の差分と検査で確かめられる。
- 分析者、引き継いだ人、顧客が同じ図を読む。図と正本はずれない。

### Negative

- wheel に入る `src/insight_blueprint` のモデルと `validate.py` が増え、公開の契約が広がる（追加だけで、既存の形は変えない）。
- 手元の HTML を開く手段は分析者の環境に任せる。Claude Code のチャットの中では図を出せず、文字の要約になる。
- Artifact が使えるかはホストとアカウントによる。使えない利用者は URL で渡せない。

## Alternatives considered

- **HTML の中で mermaid を CDN から読む** — 手元で開くときにネットワークを要求し、ホストの機能が無くても読めるという M1 の精神に反するので落とした。

## Related

- Epic: [#116](https://github.com/etoyama/insight-blueprint-skills/issues/116)、[epic-18](../design/epic-18-question-tree.md)
- 関係する ADR: [ADR-0015](0015-host-connectors-for-optional-features.md)、[ADR-0016](0016-approval-before-external-send.md)、[ADR-0025](0025-cited-answers-checked-after-writing.md)
