# ADR-0037: `/tree-upload` は、論点ツリーと一緒に分析ノートを Artifact に送る

## Status

Accepted

## Context

[Epic 28](../design/epic-28-tree-entry-point.md) は論点ツリーの HTML から分析ノートへリンクを張る（[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)）。
`/tree-upload` は、論点ツリーの HTML を Artifact に送る skill である（[Epic 18](../design/epic-18-question-tree.md) の US-6）。
送った先で分析ノートへのリンクをどう扱うかを、2026-11-22 に DesignDoc 初版のセッションで人間と決めた。
人間は最初に「手元の HTML だけを入口にする」と答え、分析ノートの形が決まった後に「全部 Artifact にしてリンクしてはまずいか」と問い直した。

比較の前提にした事実と、確かめた方法は次のとおり。

- `/tree-upload` は、`tree_io render` が書いた1ファイルだけを、書き換えずに送る（`skills/tree-upload/SKILL.md`、Epic 18 の US-6 AC 3）。
- Artifact はページに添える別の HTML や画像を一緒に受け取り、ページから相対パスで参照させる。1回に 255 ファイルまで送れる（このセッションの Artifact ツールの説明を読んだ）。
- 未確認: 論点ツリーの HTML が手元で使う相対リンク（`../notes/{design_id}.html`）が、Artifact の上でもそのまま開けるか。ほかのホストの Artifact が添えるファイルを受けるか。
- 分析ノートは図・指標の値・journal のすべての出来事・分析コードを載せる。データ取得のコードと接続情報の値は載せない（ADR-0036）。
  今の論点ツリーの HTML が載せるのは、問い・答え・引用した出来事の本文・分析設計の題と状態までである。
- 外へ送るときは、送るファイルを列挙して KEEP ゲートで承認を待つ。列挙を短く保つことが、読まずに承認する事故の抑えになっている（[ADR-0016](0016-approval-before-external-send.md)）。
- 製品の成功基準は、論点ツリーの表示を渡された読み手が、現在地と次の一手を説明できることである（[docs/PRD.md](../PRD.md)、引き継ぎの試行）。

## Problem

- 課題1: Artifact で論点ツリーを受け取った人は、論点から根拠へたどれない。分析ノートへのリンクは開けない。
- 課題2: 分析ノートを送ると、外へ出る中身が広がる。図、指標の値、journal のすべての出来事、分析コードが出る。

扱わない範囲: notebook の `.py`・verdict・レポートを Artifact に送ること。論点ツリーの無いテーマの分析ノートを送ること。Artifact を作った後の共有。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 外へ送るのは、列挙を見た承認の後だけである | Must | - | - | ADR-0016 |
| M2 | 送るのは `tree_io render` が書いたファイルそのものである | Must | - | - | Epic 18 の US-6 AC 3、[ADR-0024](0024-question-tree-yaml-and-generated-html.md) |
| W1 | 渡した相手も根拠へたどれる | Want | 解決 | 高（人間） | 課題1 |
| W2 | 承認の列挙が読める長さで、何が出るかが分かる | Want | 解決 | 高（Claude の推測） | 課題2、ADR-0016 |
| W3 | Epic に足す量と、未確認の事実への依存 | Want | 費用 | 中（Claude の推測） | [docs/WORKFLOW.md](../WORKFLOW.md) §3 |

| Must | u1: 手元だけ | u2: 一緒に送る | u3: 配置だけ両対応にする | k2: リンクを出さない HTML を別に作って送る | 何もしない |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす | 満たす |
| M2 | 満たす | 満たす | 満たす | 満たさない（手元と違うファイルになる） | 満たす |

| Want | u1 | u2 | u3 |
|---|---|---|---|
| W1 | たどれない。読み方に「リンクは手元でだけ開ける」と書く。 | たどれる。 | この Epic ではたどれない。 |
| W2 | 今と同じ1行。 | 分析設計の数だけ行が増える。図を分析ノートに埋め込めば、図の数だけは増えない。 | 今と同じ。 |
| W3 | 文を2か所に足す。 | `/tree-upload` の手順とテストを直す。リンクが通るかの確認に依存する。 | 図の埋め込みだけ。 |

- 差がつく基準: 3つとも。W1 は u2、W2 と W3 は u1 と u3 が勝つ。
- 感度: W2 を最も重く見るなら u3 になる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| u1 | 受け取った人が開けないリンクを踏む。課題1 が残る | 読み方の1行 |
| u2 | 分析ノートを読まずに承認し、図やコードを意図せず渡す。リンクが Artifact で通らない | 承認の文に、載る中身を書く。「ツリーだけ送る」と答えられるようにする。通らなければ u3 に落とす |
| u3 | 送る話が先送りになる | issue に起こす |
| k2 | 手元と Artifact の図が別物になる | 抑えにくい |
| 何もしない | 受け取った人が戸惑う | なし |

## Decision

u2 を採る（人間の判断、2026-11-22）。決め手は W1。

- `/tree-upload` は、論点ツリーの HTML と、そのテーマの分析設計すべての分析ノートを、1つの Artifact として送る。論点に結んでいない分析設計の分析ノートも送る。
  論点ツリーの「分析設計の派生」の節からもリンクするためである。
- 送るのは `tree_io render` が書いたファイルそのものである。モデルは書き換えず、写しも作らない。
- 図は分析ノートに埋め込んであるので（ADR-0036）、列挙するのは論点ツリーの HTML と分析ノートのパスである。
- 承認の文に、分析ノートに載る中身（図、指標の値、journal のすべての出来事、分析コード）を書く。分析者が「ツリーだけ送る」と答えたら、論点ツリーの HTML だけを送る。
- notebook の `.py`・verdict・レポート・notebook の HTML は送らない。接続情報の値が外へ出るためである（[ADR-0022](0022-connection-reaches-only-the-notebook.md)）。
- 実装の最初に、相対リンクが Artifact の上で開けるかを確かめる。開けなければ u3 に落とす。
  その場合は論点ツリーの HTML だけを送り、読み方に「分析ノートへのリンクは手元でだけ開ける」と書いて、送る件を issue に起こす。確かめた結果は Epic 28 の DesignDoc の Decisions に残す。
- 承認の決まり（ADR-0016）は変えない。承認は1回の実行に限り、覚えない。
- 「アップロード」の定義と [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の KEEP ゲートの一覧は、実装の Story で直す。

## Consequences

### Positive

- Artifact で論点ツリーを受け取った人も、論点から分析ノートへたどり、結果と図とコードを確かめられる。
- 手元と Artifact で同じファイルを読む。

### Negative

- 外へ出る中身が広がる。機密や個人情報が無いかは、分析者が送る前に分析ノートを開いて確かめるしかない（ADR-0016 と同じ限界）。
- 承認の列挙が分析設計の数だけ伸びる。分析設計の多いテーマでは、読まずに承認する恐れが増す。
- 分析ノートの「手元のファイル」の節のリンクは、Artifact では開けない。
- 論点ツリーの無いテーマの分析ノートは、Artifact に送る手段が無い。
- 相対リンクが Artifact で開けるかは確かめていない。開けなければ、この決定のうち送る部分は次の Epic に回る。

## Alternatives considered

- **notebook の `.py` と verdict も Artifact に送る** — データ取得の cell の接続情報の値が外へ出る（ADR-0022）。
- **図を分析ノートに埋め込まず、添えるファイルとして送る** — 列挙が図の数だけ伸び、ADR-0016 の「列挙を短く保つ」が崩れる。

## Related

- Epic: [#173](https://github.com/etoyama/insight-blueprint-skills/issues/173)、[epic-28](../design/epic-28-tree-entry-point.md)
- 関係する ADR: [ADR-0015](0015-host-connectors-for-optional-features.md)、[ADR-0016](0016-approval-before-external-send.md)、[ADR-0022](0022-connection-reaches-only-the-notebook.md)、[ADR-0024](0024-question-tree-yaml-and-generated-html.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)
- Supersedes: なし
