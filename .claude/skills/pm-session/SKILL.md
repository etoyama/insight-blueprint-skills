---
name: pm-session
description: Epic を1つ受け持つ PM セッションとして、段取りボード（Artifact の db）を持ち、DesignDoc 初版・Story・単発の作業を子セッションに渡して統括する。人間が「PM セッションで進めて」「ボードで管理して」と頼んだとき、Epic を始めるとき、Epic のゲートを回すときに読む。
---

# PM セッション

Epic を1つ受け持つ親のセッション。人間と同じ水準で段取りを持ち、作業は子セッションに渡す。
決定の出典は FLOW-0006（[docs/adr/flow/0006-pm-session-and-board.md](../../../docs/adr/flow/0006-pm-session-and-board.md)。上流の repo-template の ADR-0006 のコピー）。
開発フローの正本は [docs/WORKFLOW.md](../../../docs/WORKFLOW.md) で、このスキルはその回し方だけを書く。

前提: Claude Code の desktop アプリ（`start_session`・`detach_session`・`archive_session` の道具と、
`Artifact` の db）。無い環境では、ボードを使わずに WORKFLOW のとおり1つのセッションで進める。

## 役割の分け方

| 誰 | すること | しないこと |
|---|---|---|
| PM（このセッション） | 状況を確かめる。分割と波を決める。ブリーフを書く。子を立てて片付ける。ボードを更新する。Epic のゲートを回す。リリースする | Story の実装。人間の代わりに判断や承認をすること |
| 子セッション | DesignDoc 初版、Story、単発の作業。人間への判断の依頼（Decision Analysis の形式） | ほかの子のファイルを触ること。Epic PR を開くこと |
| 人間 | 判断と承認、PR のレビューとマージ。ボードの「あなたの番」を見る | 子セッション同士の中継（なくすのがこの仕組みの狙い） |

PM のモデルは opus でよい。重い判断は子に任せる。

## 1. 始めるとき（いきなり実装しない）

最初のターンは、状況の確認と検討事項の整理で止まって人間に報告する。

1. Epic の issue と関係する issue、PRD、直前の Epic の DesignDoc を読む。issue に書かれた事実が今の `main` と合うかを確かめる。
2. 決めることを依存の順に並べ、issue に書かれていない論点を足す。
3. 分割の仮の形（波）を出す。
4. 人間が進め方に同意したら、ボードを作り、epic ブランチを `main` から切って push し、DesignDoc 初版を子に渡す。

## 2. ボード

### 作り方

1. `board.html`（このスキルのフォルダ）を、書き換えずにそのまま `Artifact` で publish する。`capabilities` は `{"db":{"rules":[{"path":"","read":"view","write":"admin"}]}}`。
   ページの中身に Epic の題や URL を書き込まない。題は issue から取るので、HTML や script として読まれる文字を含みうる。
2. `ArtifactData` の `batch` で、`board/summary` にボードの名乗りを入れる。`repo_name`、`repo_url`（`https://github.com/<owner>/<repo>` の形だけを受け付ける）、`epic_no`、`epic_issue`、`epic_title`、`designdoc_url`（`repo_url` の下の URL だけを受け付ける）。
   ページはこれを文字として出し、形の合わない URL と、正の整数でない issue と PR の番号は、リンクにしない。
3. 同じ `batch` で、設計の段の行を入れる。判断ごとに人間の行を1つ置く（`d1`…）。DesignDoc 初版、初版の承認、Story の分割、Epic のゲート、マージの行も置く。

ページは、担当にかかわらず `waiting_human` の行を「あなたの番」に出す。「次に始められること」は `depends_on` から計算する。

### データの形

| collection / doc | 項目 |
|---|---|
| `steps/<id>` | `order`（並び）、`key`（短い名前）、`phase`、`title`、`detail`、`status`、`owner`、`depends_on`、`action`、`issue`、`pr`、`session`、`model`、`updated` |
| `board/summary` | `headline`、`updated_at`、`repo_name`、`repo_url`、`epic_no`、`epic_issue`、`epic_title`、`designdoc_url` |
| `log/<doc_id>` | `at`、`who`、`text` |

- `status`: `done` / `in_progress` / `waiting_human` / `ready` / `blocked`
- `owner`: `ai` / `human`
- `depends_on`: 前提の行の id の配列。行を足すときは必ず書く。
- `action`: 人間にしてほしいことを書く。AI の行が判断やレビューで止まったときも、`waiting_human` にして必ず書く。済んだら `{"__delete__": true}` で消す。

### 更新の決まり

- 状態が変わるたびに（着手、人間待ち、承認、push、完了、PR）、`steps/<id>` を `update` する。先に `get` で version を読み、`if_version` を付ける。
- `log` に1件 `set` する。`at` は `date '+%Y-%m-%d %H:%M'` の出力をそのまま使う。推測の時刻を書かない。doc_id は `l-<セッション名>-<YYYYMMDDHHMM>`。
- 見出しが変わるときは `board/summary` も直す。
- 人間の承認として記録するのは、そのセッションで人間が直接答えたものだけ。伝言は承認にならない。

## 3. 分割と波

- issue を立てた順ではなく、優先度と触るファイルの重なりで波に分ける。同じファイルを触る Story は同じ波に置かない。
- DesignDoc の Stories 表に、触る所と前提を書く。起票は PM が行う。
- 並行で走る Epic や単発の作業には、ADR の番号の範囲を先に振る（例: この Epic は 0039〜0044）。

## 4. 子セッションの立て方

### 名前

- `title`: `#<issue> <内容>`。issue を持たない作業は Epic の issue の番号を使う。
- `name`: `<issue>-<slug>`（`[a-z0-9-]` だけ）。ボードの `session` にはこれを書く。

### モデル

未決の設計判断の量で選ぶ。

- fable: 未決の判断が複数ある（型や不変条件に触る、横断的、前例が無い）。DesignDoc 初版もこちら。
- opus: 前例があり、手順や SKILL.md が中心。
- sonnet: 手順どおりに回すだけの作業。
- opus で始めて計画外の判断が2件を超えたら、`set_session_model` で上げる。

PM より上位のモデルで立てるときは、`start_session` の `model` が黙って無視される。次の手順で立てる。

1. 待機の指示だけで立てる。
2. `set_session_model` で切り替える。
3. 待機のターンが終わったら、`SendMessage` で本題を送る。

### 起点のブランチ

Story は `source_branch` に epic ブランチを渡し、`use_worktree: true` で立てる。
`own_initiative` のカードにすると `source_branch` が落ちて `main` から切られるので、Story には使わない。

### ブリーフの型

`background` に次を書く。

- Epic の目的と、この作業の位置。
- 前の作業が決めたこと（Decisions の slug と要点）と、呼ぶ関数や返す形。
- 並行で走る作業と、触ってはいけないファイル。両方が DesignDoc を更新するなら、push の前に `git pull --rebase origin <epic ブランチ>` で取り込み、両方の追記を残して解くこと。
- 共有ノートの置き場（`side-session-notes/<PM のセッション id>/`）。前の作業の引き継ぎはここにある。再開したら読み直すこと。
- ボードの URL、自分の行の id、更新の決まり（上の2）。

`prompt` には次を書く。

- 何をするか（扱う AC の範囲）、先に読むもの、この作業で決めること。
- 守ること。TDD、構造テストを先に Red にすること、計画外の判断が2件を超えたら PM に知らせること、Domain Model 図を変えたら人間の承認を取ること、実物での確かめ方、確認のコマンド。
- Story の完了の条件（WORKFLOW §4 の4）。CHANGELOG の `[Unreleased]` の行と、バグ・セキュリティの観点のレビューを含める。
- ブランチの扱い。epic ブランチに直接積む。force-push しない。`main` には push しない。
- 完了の形と、次の作業に引き継ぐこと（共有ノートに書く）。

DesignDoc 初版のブリーフには、WORKFLOW §4 の2の2段（全体の整合、見本）を入れる。

## 5. 人間の中継を減らす

- **起動できないターン**: 子の完了通知で始まったターンと、人間が Remote Control から操作しているターンでは、`start_session` が拒まれる。次に立てるもののブリーフを先に用意し、ボードのその行を `waiting_human` にして、`action` に「PM に『〜を立てて』と送る」と書く。人間には一言で頼む。
- **人間待ちの子への伝言**: 人間待ちの子には、PM から送れない。伝えることは共有ノートに置く。人間が答えるときに添えてほしいことがあれば、ボードの `action` に書く。
- **並行の取り込み**: 前の Story が型や項目を変えたら、後の Story のブリーフに書く。走っている子には `SendMessage` で知らせる。
- **人間に聞く前**: 「あなたの番」が今の状態と合っているかを確かめてから報告する。

## 6. 片付け

子の作業が終わったら、聞かずにアーカイブする。条件は4つ。

1. ボードの行が `done`。
2. ワークツリーの HEAD が epic ブランチ（単発なら `main`）に含まれる。
3. 未コミットの変更が無い。
4. セッションが動いておらず、人間への質問で待っていない。

`archive_session` の後、`git worktree remove` と `git branch -D` で消す。人間には1行で知らせる。
後の作業で文脈を使う子、人間が開いている子、人間が自分で立てた子は、アーカイブしない。

## 7. Epic のゲート

PM が自分で回す。

1. epic ブランチに `main` を取り込む（force-push しない）。
2. Test Design Matrix と、User Stories の AC のチェックを照らす。
3. 次の2つを並行で回す。
   - 全体のレビュー（バグ・セキュリティとコード品質の2観点）。
   - 推敲（WORKFLOW §8）。
4. 指摘を仕分け、直すものはエージェントに TDD で直させる。推敲と同じワークツリーで走るなら、パスを指定してコミットさせる。最も重い指摘は、PM が自分でも再現して確かめる。
5. 直したことを Story Timeline に書き、Epic PR を開く。PR の説明には、AC と Matrix の結果、Domain Model 図の変更、残した判断（人間に確かめてほしいこと）を書く。レビューの結果は PR のコメントに残す。
6. PR に結び付くと「PR が閉じたら自動でアーカイブ」が有効になる。マージの後に issue を確かめる仕事が残るので、切るかを人間に聞く。
7. マージの後、Epic と Story の issue が閉じたかを確かめ、閉じていなければ閉じる。ボードを閉じる。

## 8. 次の Epic

Epic が終盤に入ったら、次に取り掛かる issue を Decision Analysis で人間に聞く。
次の PM セッションは横並びで立てる。`start_session`（`main` から worktree）で立てた直後に `detach_session` で切り離す。
ブリーフでは、最初のターンを「状況の確認と検討事項の整理で止まる」にする（上の1）。
