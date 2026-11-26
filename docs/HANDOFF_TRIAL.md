# Handoff Trial

論点ツリーの表示だけで判断が引き継げるかを試す手順。
開発者が表示や skill を変えたあとに繰り返し回す（[Epic 18 の US-7](design/epic-18-question-tree.md#us-7-開発者が引き継ぎで判断が伝わるかを試せる)）。

## Purpose

[PRD の成功基準](PRD.md#成功基準)の「引き継ぎの試行」を確かめる。
合成シナリオの論点ツリーの HTML だけを、文脈を持たない読み手に渡し、次の6つを答えさせる。

1. 主題への現時点の答え
2. 未着手の論点と、分析は済んだが未判別の論点の区別
3. 現時点の答えを支える証拠と弱める証拠、それぞれの出所の分析設計と journal の出来事
4. 前回の振り返りから変わった答えと、変えた証拠
5. 次に調べる論点と、それを選ぶ理由
6. 答えも数値も変わっていないのに、上の論点の答えがその証拠を引用する文が変わった論点と、その証拠

1〜5 は PRD の成功基準の5項目である。6 は Epic 34 が足した（[ADR-0059](adr/0059-the-handoff-trial-has-a-second-scenario-and-a-sixth-question.md)）。

読み手は人と、文脈を持たない別の Claude セッションの両方とする。
採点は文言でなく判断の一致で行う（Step 4）。

## Scenario

合成シナリオは2本ある。名前と数はすべて架空である。

| シナリオ | 置き場所 | 題材 | 鍵の段階 |
|---|---|---|---|
| `lib` | `tests/fixtures/handoff/lib/` | 公共図書館の予約本。振り返りは2回 | `round-2` |
| `psy` | `tests/fixtures/handoff/psy/` | 心理的安全性と上司支援。振り返りは4回 | `round-4` |

`psy` は Epic 34 の表示が効いたかを測るために足した。次の2つを含む。

- 差が出なかった分析: 回 2 の検証は差が 0.02 で棄却に終わり、主題の答えは書き直していない。
- 答えも数値も変わらないまま、引用する文が変わる論点: 回 3 に答えた PSY-Q03 の 0.30 を、主題の答えは回 3 では上司への働きかけを優先する根拠として引用する。回 4 では業務負荷の軽減と分けられない変化として引用する。

止めた分析（分析設計が分析中のまま区切った論点）は、どちらのシナリオにも入れない。表示のテストで確かめる。

各シナリオのディレクトリは2つのファイルを持つ。

- `stages.yaml`: 段階ごとの操作の列。`start` は着手時に分かっていた情報（主題、到達点、第一階層の論点、最初の論点）を持つ。
  `round-N` はその後の観察（分析設計、journal の出来事、振り返りの答え、聞いてきた答え、ツリーの決定）を順に足す。
  各段階の `summary` は、その段階で何が分かったかを人向けに書いたものである。
- `key.yaml`: 最後の段階の HTML を読んだ人が出すべき判断（正解の鍵）。
  鍵の答えは、q5 の理由の出来事を除いて、`tests/test_handoff_trial.py` が作ったツリーから導き直して確かめる。そのため `stages.yaml` とずれない。
  q6 に該当する論点が無いシナリオ（`lib`）では、鍵の q6 は論点も出来事も空で、これも導き直して確かめる。
  ツリーの決定の理由は文で、出来事を引用しない。そのため q5 の理由の出来事だけは機械で導けず、鍵を書く人が決める。根拠は `key.yaml` のコメントに書く。

読み手に渡す問いと答えの形は `tests/fixtures/handoff/prompt.md` にある。全シナリオ共通で、人にも Claude にも同じものを渡す。

## Step 1: Build the HTML

`build` は段階の操作を `tree_io` と `design_io` に通して `.insight/` を作り、`tree_io render` で HTML を書く。
`stages.yaml` の step 名は呼ぶ関数の名前と同じである。
`--out` に空でないディレクトリを渡すと、`build` が前に作ったもの（目印の `.handoff-trial` がある）でない限り、何も消さずに止まる。
skill が書くのと同じ道を通るので、正本や表示が変われば、HTML も今の形でできる。

```bash
TRIAL=$(mktemp -d)
uv run python -m scripts.handoff_trial build --scenario lib --out "$TRIAL/insight"
```

出力は HTML のパスである。`psy` を試すときは `--scenario psy` にする。HTML は `themes/PSY_tree.html` に出る。
`--through round-1` のように段階を渡すと、その段階までで止める。
鍵は最後の段階のものだけなので、採点する試行では段階を渡さない。

## Step 2: Hand it to a Claude session with no context

headless の `claude -p` に、問いと HTML だけを標準入力で渡す。
ツールを1つも持たせず、MCP サーバ、plugin、設定ファイル、既定のシステムプロンプトを読み込ませない。
`--plugin-dir` と `--mcp-config` は渡さない。auto-memory も切る。
CLAUDE.md を拾わないように、空のディレクトリで実行する。

```bash
uv run python -m scripts.handoff_trial prompt --html "$TRIAL/insight/themes/LIB_tree.html" > "$TRIAL/input.txt"
mkdir "$TRIAL/empty" && cd "$TRIAL/empty"
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 claude -p --tools "" --strict-mcp-config --setting-sources "" --disable-slash-commands --no-session-persistence --model sonnet --system-prompt "Answer only from the text the user gives you." < "$TRIAL/input.txt" > "$TRIAL/reply.txt"
```

問いと HTML はモデルの API に届く。モデルの API 以外には送らない。Artifact や Claude Docs には何も送らない。
合成データだけなので、API に届いて困るものは無い。

これらのフラグでも、managed（組織の管理者が置く）設定と、その hook は外せない。
`--bare` なら hook と CLAUDE.md の探索まで切れるが、認証が API キーに限られる。

隔離が効いているかは、同じフラグに `--output-format json` を足して確かめる。`num_turns` が 1 なら、ツールは一度も呼ばれていない。
2026-11-21 の確認では `num_turns` は 1 だった。あわせて「呼べるツール、CLAUDE.md の中身、作業ディレクトリ」を聞くと、ツールは空、CLAUDE.md と memory は見えない、作業ディレクトリは分からない、と答えた。この答えはモデルの自己申告なので、証拠としては `num_turns` より弱い。

## Step 3: Hand it to a person

人の読み手には Step 1 の HTML をブラウザで開いてもらい、`prompt.md` の6つの問いを渡す。
読み手はこのリポジトリの文脈を持たない人がよい。
答えは `prompt.md` と同じ JSON の形でファイルに書いてもらう。説明は各問いの `note` に書く。

時間は2つに分けて計る。

- 確認: HTML を開いてから、現在地（1〜4 と 6 の問い）に答え終えるまで
- 再構成: 現在地に答えた後、次の一手（5 の問い）に答え終えるまで

## Step 4: Score

`record` が答えを鍵と比べ、問いごとに正誤を出す。
採点するのは id と区分だけで、`note` の文言は採点しない。
id の並びの順も採点に効かない。

| 問い | 正しいとする条件 |
|---|---|
| q1 | `verdict`（`claim` か `undetermined`）が鍵と同じ |
| q2 | `not_started` と `analyzed_undetermined` の論点の集合が、どちらも鍵と同じ |
| q3 | `supports` と `weakens` の出来事と分析設計の組の集合が、どちらも鍵と同じ。鍵は、主題の現時点の答えが引用する出来事を、引用した文の種類で分ける。「これまでわかっていること」が引用する出来事が `supports`、「注意すべきこと」が引用する出来事が `weakens` である。探索の証拠は journal の `direction` を持たないので、`direction` では分けない |
| q4 | `changed_nodes` と `evidence` の集合が、どちらも鍵と同じ |
| q5 | `node_id` が鍵と同じで、`reason_events` が鍵の出来事をすべて含み、鍵の出来事と `also_allowed` の外の出来事を含まない |
| q6 | `nodes` と `evidence` の集合が、どちらも鍵と同じ。該当が無ければ、どちらも空が正しい。鍵は、最後の回に答えを書き直していない論点が引用する出来事のうち、最後の回に書き直した上の論点の答えが、前の回と今の回の両方で引用し、引用する文（種類と本文）が違うものを挙げる。上の論点が引用をやめた出来事は挙げない |

q5 の理由だけは集合の一致で採点しない。HTML ではツリーの決定の理由は文で、出来事を引用しない。
そのため、読み手は理由の隣にある出来事（たとえば、次の論点の発見元）も挙げることがある。
鍵の `also_allowed` は挙げてもよい出来事である。挙げてもよい出来事だけを挙げた答えは誤になる。理由の文が述べる出来事を読み取れていないからだ。
出来事を全部挙げた答えも誤になる。

正誤が誤でも、`note` は人が読む。id は合っていて理由を取り違えている答えや、表示のどこで迷ったかは、`note` にしか出ない。

## Step 5: Keep the record

リポジトリのルートに戻ってから実行する。

```bash
uv run python -m scripts.handoff_trial record --scenario lib --answers "$TRIAL/reply.txt" --reader-kind claude --reader-name "sonnet (Claude Code 2.1.227)" --date 2026-11-21 --out docs/handoff-trials/2026-11-21-claude-sonnet.yaml
```

記録は1回の試行を1ファイルにし、`docs/handoff-trials/` にコミットする。合成データだけなので公開してよい。
記録の型は `scripts/handoff_trial.py` の `Record` で、次を持つ。

- `date`、`scenario`、`stage`（鍵の段階）
- `reader`: `kind`（`human` か `claude`）と `name`
- `minutes.confirm` と `minutes.reconstruct`: 確認と再構成にかかった分。人の試行では両方が要る。Claude の試行では空にする
- `answers`: 問いへの答え（`note` を含む）。q6 を足す前の記録は q6 を持たない
- `score`: 問いごとの正誤

人の試行では `--reader-kind human` にし、`--minutes-confirm` と `--minutes-reconstruct` を渡す。
記録の正誤は、その時点の鍵での採点として残す。CI は記録を今の鍵で採点し直さない（[ADR-0035](adr/0035-handoff-trial-records-keep-their-score.md)）。
鍵を直しても、過去の記録は書き換えない。鍵が変わる前と後の記録を比べるときは、記録の日付と鍵の git の履歴を見る。

時間の目標値は、既存のフローでの基準値が取れてから決める（[PRD の成功基準](PRD.md#成功基準)）。
