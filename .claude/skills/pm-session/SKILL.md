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
   同じターンで、仮の分割の全部の波の子を、待機の指示で立てておく（下の5）。

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
| `board/summary` | `headline`、`updated_at`、`repo_name`、`repo_url`、`epic_no`、`epic_issue`、`epic_title`、`designdoc_url`、`notes_dir`（共有ノートの絶対パス。ページには出さない。下の4） |
| `log/<doc_id>` | `at`、`who`、`text` |

- `status`: `done` / `in_progress` / `waiting_human` / `ready` / `blocked`
- `owner`: `ai` / `human`
- `depends_on`: 前提の行の id の配列。行を足すときは必ず書く。
- `action`: 人間にしてほしいことを書く。AI の行が判断やレビューで止まったときも、`waiting_human` にして必ず書く。済んだら `{"__delete__": true}` で消す。

### 更新の決まり

- 状態が変わるたびに（着手、人間待ち、承認、push、完了、PR）、`steps/<id>` を `update` する。先に `get` で version を読み、`if_version` を付ける。
- `log` に1件 `set` する。`at` は `date '+%Y-%m-%d %H:%M'` の出力をそのまま使う。推測の時刻を書かない。doc_id は `l-<セッション名>-<YYYYMMDDHHMM>`。
- 見出しが変わるときは `board/summary` も直す。
- 子の報告（完了通知）を受けるたびに、ボードの全行を報告と照らす。子が更新しない行は PM が直す。
  例: 人間が子のセッションで決めた判断（全体の整合、見本）、PR のマージなどの外の出来事。
- 人間の承認として記録するのは、そのセッションで人間が直接答えたものだけ。伝言は承認にならない。

## 3. 分割と波

- issue を立てた順ではなく、優先度と触るファイルの重なりで波に分ける。同じファイルを触る Story は同じ波に置かない。
- DesignDoc の Stories 表に、触る所と前提を書く。起票は PM が行う。
- 並行で走る Epic や単発の作業には、ADR の番号の範囲を先に振る（例: この Epic は 0039〜0044）。
  持ち主の Epic がマージされたら、使わなかった番号を解く。その後に書く ADR は振られた範囲ではなく、
  その時点の最大 + 1 を使う（番号を空けない）。並行で走る作業がまだあれば、範囲を振り直してボードに書く。
- 全部の波の子を、最初に子を立てる人間のターン（DesignDoc 初版の子を立てるターン）で、待機の指示で立てておく（下の5）。

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

待機の子を前もって立てるとき（下の5）も、同じ手順を使う。

### 起点のブランチ

Story は `source_branch` に epic ブランチを渡し、`use_worktree: true` で立てる。
`own_initiative` のカードにすると `source_branch` が落ちて `main` から切られるので、Story には使わない。

`source_branch` はローカルのブランチを使う。子を立てる前に、次の2つを行う。

1. epic ブランチに `main` を取り込む（force-push しない）。
2. ローカルの epic ブランチを `origin` に進める（`git fetch origin && git branch -f <epic ブランチ> origin/<epic ブランチ>`）。

どのワークツリーでも、epic ブランチそのものをチェックアウトしない。チェックアウトされていると、
`git branch -f` が拒まれ、その子をアーカイブするまで進められない。
子は自分のブランチで作業し、`git push origin HEAD:<epic ブランチ>` で積む。
PM が epic ブランチの上で作業するときは、`git switch --detach origin/<epic ブランチ>` で切り替える。

### ブリーフの型

`background` に次を書く。

- Epic の目的と、この作業の位置。
- 前の作業が決めたこと（Decisions の slug と要点）と、呼ぶ関数や返す形。
- 並行で走る作業と、触ってはいけないファイル。両方が DesignDoc を更新するなら、push の前に `git pull --rebase origin <epic ブランチ>` で取り込み、両方の追記を残して解くこと。
- 共有ノートの置き場。ブリーフにはパスを書かず、「自分のシステムプロンプトの Shared notes folder に書く。最初の報告に、その絶対パスを1行で書く」と書く。前の作業の引き継ぎはここにある。再開したら読み直すこと。
- PM の宛先（[FLOW-0015](../../../docs/adr/flow/0015-copy-pm-address-from-listagents.md)）。記憶で書かない。ブリーフを書くターンで `ListAgents` を呼び、先頭の「This session is …」の行にある名前と `[ref]` を写す。`local_…` の id で書くなら、`get_session` に `"self"` を渡して返った `sessionId` を写す。
  PM が別のセッションから立てられていると、PM のシステムプロンプトにある宛先の id と Shared notes folder は親のものになる。どちらもブリーフに写さない。
- ボードの URL、自分の行の id、更新の決まり（上の2）。

`prompt` には次を書く。毎回すべての項目を書く。当たらない項目は「無し」と書き、項目ごと落とさない。

- 何をするか（扱う AC の範囲）、先に読むもの、この作業で決めること。
- 使う既存の helper とテストの道具の場所（例: markdown の節を切り出す関数、実行コマンドの定数）。作り直さず、足りなければ同じ場所に足すこと（[FLOW-0013](../../../docs/adr/flow/0013-write-rules-reasons-and-helpers-into-designdoc-and-brief.md)）。PM は、ブリーフを書く前にテストの共通の置き場を見て書き出す。
- 前の Story やレビューが先送りした指摘のうち、この Story が直すもの。同じものをボードの Epic のゲートの行の `detail` にも書き、ゲートで直ったかを確かめる。
- 守ること。TDD、構造テストを先に Red にすること、計画外の判断が2件を超えたら PM に知らせること、実物での確かめ方、確認のコマンド。
- Domain Model 図を変えたら、そのセッションで人間の承認を取ること。PR まで溜めない。PR の説明にも変更を書く（WORKFLOW §4 の4）。
- Story の完了の条件（WORKFLOW §4 の4）。CHANGELOG の `[Unreleased]` の行と、バグ・セキュリティの観点のレビューを含める。
- ブランチの扱い。自分のブランチから `git push origin HEAD:<epic ブランチ>` で epic ブランチに積む。force-push しない。`main` には push しない。
- 完了の形と、次の作業に引き継ぐこと（共有ノートに書く）。

DesignDoc 初版のブリーフには、WORKFLOW §4 の2の判断の順と2段（全体の整合、見本）を入れる。

## 5. 人間の中継を減らす

- **後に続く波の子を全部前もって立てる**（[FLOW-0011](../../../docs/adr/flow/0011-start-wave-one-before-designdoc-approval.md)、[FLOW-0014](../../../docs/adr/flow/0014-start-all-waves-in-first-human-turn.md)）: 子の完了通知で始まったターンと、人間が Remote Control から操作しているターンでは、`start_session` が拒まれる。`SendMessage` は通る。Story の起票は初版の承認の後で、その後の PM のターンはほとんどが子の完了通知で始まる。そこで、最初に子を立てる人間のターン（DesignDoc 初版の子を立てるターン）で、仮の分割（上の1の3）の全部の波の子を、待機の指示で立てておく。上位のモデルの子は、そのとき `set_session_model` まで済ませる。
  - Story の issue は起票の前には無い。`name` は `<Epic の issue>-w<波>-<n>`、`title` は `#<Epic の issue> 波<波>-<n>（待機）` にする。本題を送るときに `set_session_title` で `#<Story の issue> <内容>` に付け直す。`name` は変わらないので、ボードの `session` には立てたときの `name` を書く。
  - モデルはまだ決まっていないので、子ごとに、仮の分割でその枠に入る最も重い Story に合わせる。迷ったら fable で立てる（上位のモデルの手順）。軽い Story にあてるときは、本題を送る前に `set_session_model` で下げる。
  - 初版の承認と Story の起票の後、波 1 の子には完了通知のターンで、後の波の子には前の波が終わった完了通知のターンで、`SendMessage` で本題を送る。
  - 本題の最初に「`git fetch origin && git merge --ff-only origin/<epic ブランチ>` で前の push を取り込む」と書く。子のワークツリーは、立てた時点の epic ブランチから切られている。
  - ボードの行は本題を送るまで `blocked` にし、`session` に子の名前を書く。
  - 分割が変わって本数が足りなければ、次の人間のターンで、足りない分をその場で立てる。人間のターンを待てないときは、足りない分のボードの行を `waiting_human` にして、`action` に「PM に『〜を立てて』と送る」と書く。初版の承認を頼むときに、承認と一緒に送ってもらう。余った子は、本題を送らないと決まったターンで下の6の手順でアーカイブする。
- **起動できないターン**: 前もって立てられなかったとき（波の途中で Story が増えたなど）の手段。次に立てるもののブリーフを先に用意し、ボードのその行を `waiting_human` にして、`action` に「PM に『〜を立てて』と送る」と書く。人間には一言で頼む。
- **共有ノートの置き場を確かめる**（[FLOW-0012](../../../docs/adr/flow/0012-shared-notes-in-app-folder-checked-by-path.md)）: 置き場はアプリが作り、子のシステムプロンプトに「Shared notes folder」として絶対パスを渡す。実体は `~/Library/Application Support/Claude/side-session-notes/<最上位のセッション id>/` にある。PM は、最初の子の報告にあるパスを `ls` で確かめ、`board/summary` の `notes_dir` に入れる。見つからなければ、引き継ぎを Epic issue のコメントと Story Timeline で代え、そのことをボードの `log` に書く。
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

前もって立てて使わなかった待機の子は、本題を送らないと決まったターンでアーカイブする。ボードの行は無いので、条件の1は問わない（行を作っていたら消す）。

## 7. Epic のゲート

PM が自分で回す。ゲートは PM のワークツリーで回す（`git switch --detach origin/<epic ブランチ>`）。
ゲートのために別のワークツリーを作らない。PM の子エージェントはほかのワークツリーへの書き込みを hook に止められ、直しを当てられない。

1. epic ブランチに `main` を取り込む（force-push しない）。
2. ブリーフで先送りした指摘（ゲートの行の `detail`）が直ったかを確かめる。
3. Test Design Matrix と、User Stories の AC のチェックを照らす。
4. 次の2つを並行で回す。
   - 全体のレビュー（バグ・セキュリティとコード品質の2観点）。
   - 推敲（WORKFLOW §8）。
5. 指摘を仕分け、直すものはエージェントに TDD で直させる。推敲と同じワークツリーで走るなら、パスを指定してコミットさせる。最も重い指摘は、PM が自分でも再現して確かめる。
6. 利用者の触る Epic では、Epic PR を開く前に、実データで使ってみる（WORKFLOW §4 の5、[FLOW-0016](../../../docs/adr/flow/0016-try-with-real-data-before-epic-pr.md)）。
   - 試す場所（利用者が実際に使うリポジトリやデータ）と試すことを、人間に聞いてから準備する。準備と元に戻す手順は、共有ノートに書いてから始める。
   - 試す場所で読まれているのが epic ブランチの版であることを、一覧ではなく、実際に呼んで確かめる。
   - findings は1件1節で共有ノートに書き、番号を振る。
   - 人間が findings を「Epic で直す / issue にする」に仕分ける。Epic で直すものは上の5と同じ手順で直す。issue にしたものは起票する。
   - 終わったら試す場所を元に戻し、Story Timeline に1行書く（findings の件数、Epic で直した件数、issue の番号）。
   - 利用者から見える変化が無い Epic では省いてよい。省いたら、その理由を Story Timeline に1行書く。
7. 直したことを Story Timeline に書き、Epic PR を開く。PR の説明には、AC と Matrix の結果、Domain Model 図の変更、実データで使ってみた結果（仕分けと issue の番号）、残した判断（人間に確かめてほしいこと）を書く。レビューの結果は PR のコメントに残す。
8. PR に結び付くと「PR が閉じたら自動でアーカイブ」が有効になる。マージの後に issue を確かめる仕事と振り返り（下の9）が残るので、切るかを人間に聞く。
9. マージの後、Epic と Story の issue が閉じたかを確かめ、閉じていなければ閉じる。ボードは振り返りの後に閉じる。

## 8. 次の Epic

Epic が終盤に入ったら、次に取り掛かる issue を Decision Analysis で人間に聞く。
次の PM セッションは横並びで立てる。`start_session`（`main` から worktree）で立てた直後に `detach_session` で切り離す。
ブリーフでは、最初のターンを「状況の確認と検討事項の整理で止まる」にする（上の1）。

## 9. 振り返り

Epic のリリースまで終えたら、PM が振り返りを回す。人間が頼んだときも回す。
定義（いつ、何を出すか、どこに残すか）の正本は WORKFLOW §4 の6（[FLOW-0010](../../../docs/adr/flow/0010-retrospective-after-epic.md)）。ここには PM の回し方だけを書く。

1. 集める。
   - ボードのログ（`ArtifactData` の `query` で `log` を `at` の順に読む）と、各行の最後の状態。
   - `git log origin/main` の Epic の範囲。
   - Epic issue と Story の issue のコメント（人間の判断）。
   - 共有ノート（`board/summary` の `notes_dir`）の引き継ぎと、子の最後の報告。
   - 前回の振り返り（前の Epic issue のコメント）。
2. WORKFLOW §4 の6の4つ（事実、学び、反映の案、前回の反映の効き目）を、チャットに1回で出す。長ければ Artifact に出してもよい。
3. 本文に表を出してから、反映する束を `AskUserQuestion` の複数選択で人間に選んでもらう。
4. 選ばれた束を反映する。
   - 上流（テンプレート）の束: テンプレートの repo に PR を出す（フローの定義を変えるなら ADR を伴う）。マージの後、各リポジトリに写す。
   - このリポジトリだけの束: 単発の PR にする。
   - メモリ: 仕組みにできない個人の作業の癖だけを書く。
5. 振り返りの全文を Epic issue のコメントに残し、ボードを閉じる。
