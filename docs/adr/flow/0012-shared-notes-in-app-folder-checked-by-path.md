# FLOW-0012: 共有ノートはアプリの置き場に置き、子が報告した絶対パスを PM が確かめてボードに残す

## Status

Accepted

## Context

PM セッション（[FLOW-0006](0006-pm-session-and-board.md)）は、子セッションどうしの引き継ぎを共有ノートで渡す。
スキル `.claude/skills/pm-session/SKILL.md` のブリーフの型は、置き場を `side-session-notes/<PM のセッション id>/` と書いていた。

このテンプレートの派生先の Epic 31（etoyama/insight-blueprint-skills、[#207](https://github.com/etoyama/insight-blueprint-skills/issues/207)、2026-11-25）で、
PM はこの置き場の実体を見つけられなかった。`~/.claude` の下と scratchpad を探し、引き継ぎは issue のコメントと DesignDoc の Story Timeline で代えた（#207 の振り返りのコメント）。

確かめた事実は次のとおり。

- 実体は `~/Library/Application Support/Claude/side-session-notes/<最上位のセッション id>/` にある。`ls` で5つの置き場を確かめた。
  そのうちの1つには、派生先の Epic 1 の引き継ぎが9件ある。子から書き込めている。
- Claude Code の desktop アプリは、子のシステムプロンプトにこの絶対パスを「Shared notes folder」として渡し、追加の作業ディレクトリにも入れる。
  この ADR を書いたセッション（子）のシステムプロンプトで確かめた。

最上位のセッション（PM）自身にこのパスが渡るかは確かめていない。

## Problem

- 課題1: スキルが書く置き場は相対の形で、実在を確かめる手順が無い。PM は置き場を見つけられない。
- 課題2: 子の再開や振り返り（[FLOW-0010](0010-retrospective-after-epic.md)）で引き継ぎを読めないと、同じ調査をやり直すことになる。

扱わない範囲: ノートに書く中身の型。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 書く前と読む前に、実在を確かめる手順がある | Must | - | - | 課題1 |
| W1 | 子が許可を求められずに書ける | Want | 費用 | 高（Claude の推測） | 課題2 |
| W2 | PM と人間が後から読める | Want | 解決 | 高（Claude の推測） | 課題2、FLOW-0010 |
| W3 | desktop アプリの外でも成り立つ | Want | 解決 | 低（Claude の推測） | FLOW-0006 の W3 |

| Must | A. アプリの置き場。子が絶対パスを報告し、PM が確かめる | B. リポジトリの外の決まった場所を PM が作る | C. issue のコメントと Story Timeline | 何もしない |
|---|---|---|---|---|
| M1 | 満たす（報告のパスを `ls`） | 満たす（`mkdir -p` と `ls`） | 満たす | 満たさない |

| Want | A | B | C |
|---|---|---|---|
| W1 | 追加の作業ディレクトリなので、許可なしで書ける。Epic 1 で実績がある | 作業ディレクトリの外なので、書くたびに許可を求められうる（確かめていない） | 外への投稿なので、毎回許可が要る |
| W2 | ボードの `board/summary` に `notes_dir` を残すので、たどれる | ブリーフに書いたパスでたどれる | issue にあるので一番たどりやすい。ただ、大きな調査メモで issue が埋まる |
| W3 | アプリに依存する。スキル自体もアプリを前提にしている | どこでも成り立つ | どこでも成り立つ |

- 差がつく基準: W1 と W2。
- 感度: W3 を高くすれば B に変わる。ただ、アプリの外では子セッション自体が無い。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | アプリが置き場の仕組みを変える。最初の報告より前に PM が読もうとする | 報告のパスを `ls` で確かめる。見つからなければ C に落ち、ボードの `log` に書く |
| B | 許可を求められて子が止まる | 許可の設定を足す（設定の変更になる） |
| C | 調査メモが issue に溜まり、読みにくくなる | 要約だけを投稿する |
| 何もしない | Epic 31 と同じことがまた起きる | なし |

## Decision

A を採る。手順の正本は `.claude/skills/pm-session/SKILL.md` の §4（ブリーフの型）と §5 に置く。

- ブリーフには置き場のパスを書かない。子は、システムプロンプトの「Shared notes folder」に書き、最初の報告にその絶対パスを1行で書く。
- PM は、そのパスを `ls` で確かめ、`board/summary` の `notes_dir` に入れる。ページには出さない。
- 見つからなければ、引き継ぎを Epic issue のコメントと Story Timeline で代え、そのことをボードの `log` に書く。

人間が選んだ（2026-11-25）。決め手は W1。

## Consequences

### Positive

- 置き場を推測で探さなくなる。振り返りでは `notes_dir` から集められる。
- 子は許可なしで書ける。

### Negative

- 最初の子の報告が届くまで、PM は置き場を知らない。PM 自身にパスが渡るかは確かめていない。
- 置き場の場所はアプリの仕組みに依存する。仕組みが変わったら、スキルの §5 の実体のパスを直す。

## Alternatives considered

- **ブリーフに絶対パスを書く** — PM がパスを知らないことが今回の原因なので、書けない。子のシステムプロンプトに正しいパスが既にある。

## Related

- [FLOW-0006](0006-pm-session-and-board.md)（PM セッション）、[FLOW-0010](0010-retrospective-after-epic.md)（振り返り）
- 派生先の先行例: etoyama/insight-blueprint-skills の Epic 31（#207）の振り返り
