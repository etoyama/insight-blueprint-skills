# Handoff Trial

論点ツリーの表示だけで判断が引き継げるかを試す手順。
開発者が、表示や skill を変えたあとに繰り返し回す（[Epic 18 の US-7](design/epic-18-question-tree.md#us-7-開発者が引き継ぎで判断が伝わるかを試せる)）。

## Purpose

[PRD の成功基準](PRD.md#成功基準)の「引き継ぎの試行」を確かめる。
合成シナリオの論点ツリーの HTML だけを、文脈を持たない読み手に渡し、次の5つを答えさせる。

1. 親の問いへの現時点の答え
2. 未着手の論点と、分析は済んだが未判別の論点の区別
3. 現時点の答えを支える証拠と弱める証拠、それぞれの出所の分析設計と journal の出来事
4. 前回の振り返りから変わった答えと、変えた証拠
5. 次に調べる論点と、それを選ぶ理由

読み手は人と、文脈を持たない別の Claude セッションの両方とする。
採点は文言でなく判断の一致で行う（Step 4）。

## Scenario

合成シナリオは公共図書館の予約本で、名前と数はすべて架空である。
置き場所は `tests/fixtures/handoff/lib/` にある。

- `stages.yaml`: 段階ごとの操作の列。`start` は着手時に分かっていた情報（根の問い、到達点、第一階層の論点、最初の論点）を持つ。
  `round-1` と `round-2` は、その後の観察（分析設計、journal の出来事、振り返りの答え、聞いてきた答え、ツリーの決定）を順に足す。
  各段階の `summary` は、その段階で何が分かったかを人向けに書いたものである。
- `key.yaml`: `round-2` の HTML を読んだ人が出すべき判断（正解の鍵）。
  鍵の各答えは `tests/test_handoff_trial.py` が作ったツリーから導き直して確かめるので、`stages.yaml` とずれない。

読み手に渡す問いと答えの形は `tests/fixtures/handoff/prompt.md` にある。人にも Claude にも同じものを渡す。

## Step 1: Build the HTML

`build` は、段階の操作を `tree_io` と `design_io` に通して `.insight/` を作り、`tree_io render` で HTML を書く。
skill が書くのと同じ道を通るので、正本や表示が変われば、HTML も今の形でできる。

```bash
TRIAL=$(mktemp -d)
uv run python scripts/handoff_trial.py build --scenario lib --out "$TRIAL/insight"
```

出力は HTML のパスである。`--through round-1` のように段階を渡すと、その段階までで止める。
鍵は `round-2` のものだけなので、採点する試行では段階を渡さない。

## Step 2: Hand it to a Claude session with no context

headless の `claude -p` に、問いと HTML だけを標準入力で渡す。
ツールを1つも持たせず、MCP サーバ、plugin、設定ファイル、既定のシステムプロンプトを読み込ませない。
`--plugin-dir` と `--mcp-config` は渡さない。auto-memory も切る。
CLAUDE.md を拾わないように、空のディレクトリで実行する。

```bash
uv run python scripts/handoff_trial.py prompt --html "$TRIAL/insight/themes/LIB_tree.html" > "$TRIAL/input.txt"
mkdir "$TRIAL/empty" && cd "$TRIAL/empty"
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 claude -p --tools "" --strict-mcp-config --setting-sources "" --disable-slash-commands --no-session-persistence --model sonnet --system-prompt "Answer only from the text the user gives you." < "$TRIAL/input.txt" > "$TRIAL/reply.txt"
```

手元で実行するだけで、HTML も答えも外には送らない。
Artifact や Claude Docs には何も送らない。

隔離が効いているかは、同じフラグで「呼べるツール、CLAUDE.md の中身、作業ディレクトリ」を聞いて確かめられる。
2026-11-21 の確認では、ツールは空で、CLAUDE.md と memory は見えず、作業ディレクトリは分からないと答えた。

## Step 3: Hand it to a person

人の読み手には、Step 1 の HTML をブラウザで開いてもらい、`prompt.md` の5つの問いを渡す。
読み手はこのリポジトリの文脈を持たない人がよい。
答えは `prompt.md` と同じ JSON の形でファイルに書いてもらう。説明は各問いの `note` に書く。

時間は2つに分けて計る。

- 確認: HTML を開いてから、現在地（1〜4 の問い）に答え終えるまで
- 再構成: 1〜4 に答えた後、次の一手（5 の問い）に答え終えるまで

## Step 4: Score

`record` が答えを鍵と比べ、問いごとに正誤を出す。
採点するのは id と区分だけで、`note` の文言は採点しない。
id の並びの順も採点に効かない。

| 問い | 正しいとする条件 |
|---|---|
| q1 | `verdict`（`claim` か `undetermined`）が鍵と同じ |
| q2 | `not_started` と `analyzed_undetermined` の論点の集合が、どちらも鍵と同じ |
| q3 | `supports` と `weakens` の出来事と分析設計の組の集合が、どちらも鍵と同じ |
| q4 | `changed_nodes` と `evidence` の集合が、どちらも鍵と同じ |
| q5 | `node_id` が鍵と同じで、`reason_events` が鍵の出来事をすべて含む |

q5 の理由だけを「含む」で採点する。HTML ではツリーの決定の理由は文で、出来事を引用しない。
そのため、読み手は理由の元になった出来事を鍵より多く挙げることがある。

正誤が誤でも、`note` は人が読む。id は合っていて理由を取り違えている答えや、表示のどこで迷ったかは、`note` にしか出ない。

## Step 5: Keep the record

リポジトリのルートに戻ってから実行する。

```bash
uv run python scripts/handoff_trial.py record --scenario lib --answers "$TRIAL/reply.txt" --reader-kind claude --reader-name "sonnet (Claude Code 2.1.227)" --date 2026-11-21 --out docs/handoff-trials/2026-11-21-claude-sonnet.yaml
```

記録は1回の試行を1ファイルにし、`docs/handoff-trials/` にコミットする。合成データだけなので公開してよい。
記録の型は `scripts/handoff_trial.py` の `Record` で、次を持つ。

- `date`、`scenario`、`stage`（鍵の段階）
- `reader`: `kind`（`human` か `claude`）と `name`
- `minutes.confirm` と `minutes.reconstruct`: 確認と再構成にかかった分。人の試行では両方が要る。Claude の試行では空にする
- `answers`: 5つの問いへの答え（`note` を含む）
- `score`: 問いごとの正誤

人の試行では `--reader-kind human` にし、`--minutes-confirm` と `--minutes-reconstruct` を渡す。
`tests/test_handoff_trial.py` は、記録がすべて型に合い、保存した正誤が採点し直した結果と同じことを確かめる。

時間の目標値は、既存のフローでの基準値が取れてから決める（[PRD の成功基準](PRD.md#成功基準)）。
