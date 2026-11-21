# ADR-0032: marketplace は plugin をリリースのタグから配る

## Status

Accepted

## Context

plugin はこのリポジトリの `.claude-plugin/marketplace.json` を marketplace として配っている。
plugin の `source` は相対パスの `"./"` だった。
v0.10.0 の実機確認（2026-11-20）で、同じ版番号 `0.10.0` の中身が2つあると分かった（#106）。
タグは `fabe076` を指し、marketplace から入れた cache は `main` の `b67a741` で、リリース前の Epic 14 を含んでいた。

[WORKFLOW §5](../WORKFLOW.md) は「`main` へのマージはリリースを意味しない」と定めている。
配り方はこの決まりに合っていなかった。

比較の前提にした事実と、確かめた方法は次のとおり。実機の観察はどれも Claude Code 2.1.227 で、
`CLAUDE_CONFIG_DIR` を scratch に向けて行った（2026-11-22）。

- 相対パスの `source` は marketplace の clone からそのまま読まれる。clone は既定のブランチを追う
  （公式ドキュメント [marketplace-reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md) と
  [loading](https://code.claude.com/docs/en/plugins/loading.md)。`~/.claude/plugins/known_marketplaces.json` でも、
  この marketplace は git の clone として記録されていた）。
- `github`・`url`・`git-subdir` の `source` は `ref`（ブランチかタグ）と `sha` を持てる。相対パスは持てない（同じドキュメント）。
- 版は `plugin.json` の `version` で決まり、cache は版ごとに作られる。版が変わらないかぎり、入れてある plugin は更新されない（同じドキュメント）。
- `source` を `{"source": "github", "repo": "etoyama/insight-blueprint-skills", "ref": "v0.12.0"}` にした marketplace から入れると、
  cache は `0.12.0` になり、記録の commit はタグ `v0.12.0` の `e1b98db` だった。
  `ref` を `v0.13.0` に変えて `claude plugin update` すると `0.13.0` に上がり、cache の中身は `git archive v0.13.0` と一致した（`diff -rq` で差なし）。
- `ref` が無いタグ（`v9.9.9`）を指すと、install も update も `Remote branch v9.9.9 not found` で失敗した。入れてあった `0.12.0` はそのまま残った。
- 同じリポジトリの marketplace が自分自身をタグで指す形は、公式ドキュメントに書かれていない。上の観察はローカルのディレクトリに置いた marketplace で行った。

## Problem

- 課題1: 互換を壊す変更が、Upgrade note を出す前に新しく入れた人へ届く。リリースを待たずに `main` の中身が配られるためである。
- 課題2: 不具合の報告に版番号が書いてあっても、どの中身かが決まらない。同じ版番号に、入れた時期の数だけ中身がある。

扱わない範囲: すでに `0.13.0` を `main` の途中の commit から入れた cache の入れ直し（次の版で揃う）。
リリース前の中身を試したい人のための配り方（`--plugin-dir` を使う）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | marketplace から入る中身は、その版番号のタグの commit である | Must | - | - | 課題1、課題2、WORKFLOW §5 |
| M2 | 入れた人は、次のリリースを手を動かさずに受け取れる | Must | - | - | RELEASE.md（版が上がると既存の install が更新される） |
| W1 | リポジトリに増えるもの（ブランチ、ファイル、利用者の手順） | Want | 費用 | 高（人間が「リポジトリをシンプルに保ちたい」と言った） | 人間の発言（2026-11-22） |
| W2 | リリースの手順に増える手数と、間違えたときの気づきやすさ | Want | 費用 | 中（Claude の推測） | 課題1 |

案は次の4つ。

- A. plugin の `source` を、このリポジトリのタグを `ref` で指す `github` source にする。リリースのたびに `ref` を版と一緒に上げる。
- B. リリース用のブランチ（`stable`）を置き、利用者には `owner/repo#stable` で marketplace を足してもらう。
- C. 利用者に `owner/repo#vX.Y.Z` で marketplace を足してもらう（README に書く）。
- 何もしない: `"./"` のままにし、「`main` にマージしたものは新しく入れる人に届く」と RELEASE.md に書いて、互換を壊す変更はマージとリリースを続けて行う。

| Must | A. タグを指す `source` | B. リリース用のブランチ | C. 利用者がタグで足す | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす（`stable` をタグと同じ commit に進めるかぎり） | 満たす | 満たさない（リリースの間は `main` が配られる） |
| M2 | 満たす（marketplace の更新で新しい `ref` が届く） | 満たす | 満たさない（足したときのタグに留まる） | 満たす |

| Want | A. タグを指す `source` | B. リリース用のブランチ |
|---|---|---|
| W1 | 増えるのは `marketplace.json` の3行だけ。利用者の手順は変わらず、すでに marketplace を足した人にも効く | ブランチが1本増える。README の手順が変わり、すでに足した人は足し直さないと `main` を追い続ける |
| W2 | 版を上げる箇所が2つから3つになる。上げ忘れは構造テストが落とす。マージからタグまでの間は install が失敗する（黙って別の中身が入ることはない） | リリースのたびに `stable` を進める手順が増える。進め忘れても何も落ちず、古い中身が配られ続ける |

- 差がつく基準: W1 と W2 の両方。どちらも A が勝つ。
- 感度: どの重みを動かしても変わらない。マージからタグまでの失敗を許せないなら、B に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 版を上げる PR をマージしてからタグを push するまで、新しい install と update が失敗する | RELEASE.md に、マージの直後にタグを push すると書く。失敗は `Remote branch vX.Y.Z not found` と出るので、原因が読める |
| A | push したタグを消すか動かすと、install が失敗するか、同じ版の中身がまた2つになる | RELEASE.md の Troubleshooting に書く |
| A | 自分自身をタグで指す形は公式ドキュメントに無く、Claude Code の更新で動きが変わりうる | リリースの確認（RELEASE.md の Step 4 の前後）で、marketplace から入る版を見る |
| B | `stable` の進め忘れで、古い中身が配られ続ける | 手順に書くしかない |
| C | 利用者が古い版に留まり、直した不具合が届かない | なし |
| 何もしない | 課題1と課題2が残る | マージとリリースを続けて行う（v0.11.0 でやった。仕組みでは塞がない） |

## Decision

A を採る。決め手は W1（リポジトリに増えるものが最も少なく、すでに marketplace を足した人にも効く）。

- `.claude-plugin/marketplace.json` の plugin の `source` を、
  `{"source": "github", "repo": "etoyama/insight-blueprint-skills", "ref": "vX.Y.Z"}` にする。
- `ref` は `plugin.json` の `version` に `v` を付けたものにする。`tests/test_plugin_structure.py` が、ずれを落とす。
- リリースでは版を上げる PR で `ref` も上げ、マージの直後にタグを push する。タグを打つのは人間のままである。
- push したタグは動かさない。

## Consequences

### Positive

- 版番号が1つの中身を指す。不具合の報告の版番号から、中身が決まる。
- `main` へのマージは次のリリースまで誰にも届かない。互換を壊す変更を、Upgrade note と一緒に届けられる。
- 利用者の手順（`/plugin marketplace add` と `/plugin install`）は変わらない。

### Negative

- 版を上げる PR をマージしてからタグを push するまで、新しい install と update が失敗する。入れてある plugin は動き続ける。
- この checkout をローカルの marketplace として足しても、入るのはタグの中身である。手元の変更を試すときは `--plugin-dir` を使う。
- すでに `0.13.0` を `main` の途中の commit から入れた cache は、次の版まで入れ替わらない。
- 自分自身をタグで指す形は公式ドキュメントに無い。git から足した marketplace での動きは、この PR のブランチを marketplace として足して確かめた（PR 説明に書く）。

## Alternatives considered

- **`plugin.json` の `version` を消す** — 版が commit の SHA になり、`main` の commit ごとに別の版になる。同じ版に中身が2つある状態は無くなるが、全員が `main` を追うので課題1が残る。版番号も利用者から読めなくなる。
- **`source` に `sha` も書く** — タグを動かしても中身が変わらなくなる。ただし squash merge の SHA は、版を上げる PR の中では分からない。リリースが2本の PR になる。

## Related

- Issue: #106
- 関連: [ADR-0002](0002-trunk-based-epic-stacking.md)（タグ駆動のリリース）、[ADR-0012](0012-single-pr-scope.md)（単発の PR）、[RELEASE.md](../RELEASE.md)
- Supersedes: なし
