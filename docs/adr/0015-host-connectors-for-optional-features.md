# ADR-0015: 不変条件を「同梱しない」と書き、ホストのコネクタは任意の機能に限って使う

## Status

Accepted

## Context

[Epic 12](../design/epic-12-decision-ready-report.md) の Story
[#67](https://github.com/etoyama/insight-blueprint-skills/issues/67)（US-4）は、
レポートを Claude Docs にアップロードする skill `/report-upload` を足す。
Claude Docs への書き込みは、ホスト（Claude Code）が持つコネクタを通る。コネクタの実体は MCP のツールである。

一方、[docs/ARCHITECTURE.md](../ARCHITECTURE.md) の不変条件は
「No daemon / No MCP server / No SQLite。常駐プロセスを持たない」と書いていた。
字面どおりに読むと、MCP のツールを使う skill は不変条件に反する。

2026-11-15 に、Story #67 の中で人間が文を決めた（issue #67 のコメント）。比較の前提にした事実は次のとおり。

- [ADR-0001](0001-drop-mcp-server-embed-validation.md) が廃止したのは、plugin が自分で立てる MCP サーバである。
  分析設計の検証をサーバの中から埋め込みのライブラリへ移した（ADR-0001 の Decision を読んだ）。
  ホストが持つコネクタには触れていない。
- [epic-11](../design/epic-11-repo-template-compliance.md) の US-4 は配布物から `.mcp.json` を消した。
  `tests/test_plugin_structure.py` の `TestMcpJson` が、`.mcp.json` が無いことを確かめている（同じファイルを読んだ）。
- スパイク（Epic 12 の Decision `spike-constraints`）で、コネクタの無い環境ではモデルが「無い」と判定して止まれることを確かめた。
- `/analysis-report` は Markdown のレポートを `.insight/reports/` に書く。Claude Docs が無くてもレポートは出る
  （Epic 12 の Decision `publish-as-separate-skill`）。
- ADR-0001 は旧形式のまま凍結している（[ADR-0009](0009-adopt-repo-template-flow.md)）。

## Problem

- 課題1: 次に外部のコネクタを使いたい人が、使ってよいかを不変条件から読めない。
  字面は禁じ、実態は `/report-upload` が使っている。食い違った不変条件はやがて守られなくなる。
- 課題2: 歯止めなしにコネクタを使うと、コネクタの無い環境で核（分析設計・notebook・journal / reflection・premortem）が動かなくなる。
  PRD の「Claude Code plugin として配布・利用できる」が崩れる。

扱わない範囲: 「核」の範囲を列挙して固定すること。個々のコネクタを使ってよいかの判断（そのつど、この ADR の条件に照らす）。
外部へ送る前の承認（[ADR-0016](0016-approval-before-external-send.md)）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | plugin は MCP サーバを同梱も設定もしない | Must | - | - | ADR-0001、epic-11 US-4 |
| M2 | 計画外の設計判断を黙って進めない | Must | - | - | CLAUDE.md §5 |
| W1 | 不変条件を1か所読めば、コネクタを使ってよいかが分かる | Want | 解決 | 高（人間） | 課題1 |
| W2 | コネクタが無くても核が動くことを、文が保証する | Want | 解決 | 高（人間） | 課題2 |
| W3 | 文書の変更の量 | Want | 費用 | 低（Claude の推測） | YAGNI |

案は次の3つ。

- A. ARCHITECTURE の不変条件の文を直し、この ADR に理由を書く。
- B. ARCHITECTURE の文は変えず、この ADR にだけ読み方を書く。
- 何もしない: 読み方を書かずに `/report-upload` を実装する。

| Must | A. 文を直す | B. ADR にだけ書く | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たす |
| M2 | 満たす | 満たす | 満たさない（判断がどこにも残らない） |

| Want | A. 文を直す | B. ADR にだけ書く |
|---|---|---|
| W1 | 不変条件の文そのものが答えになる | 不変条件を読んだ人は禁じられていると読む。ADR を探し当てた人だけが読み方を知る |
| W2 | 「無くても核が動く任意の機能に限る」が不変条件の文に入る | 条件は ADR にあり、不変条件からは読めない |
| W3 | ARCHITECTURE の1行と ADR 1本 | ADR 1本 |

- 差がつく基準: W1 と W2 は A が勝つ。W3 は B が1行ぶん少ない。決め手は W1。
- 感度: どの重みを動かしても変わらない。W3 の差は1行で、W1 と W2 を覆すほどの費用ではない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 「任意の機能」を広く読み、核に近い機能までコネクタに頼る skill が出る | 条件を文に入れる。コネクタを使う skill は、無い環境で何も壊さずに終わることを構造テストで確かめる |
| B | 不変条件と実態が食い違ったまま残り、不変条件が読まれなくなる | 抑えられない |
| 何もしない | 次の人が、前例だけを根拠にコネクタを核に使う | 抑えられない |

## Decision

A を採る。決め手は W1。[docs/ARCHITECTURE.md](../ARCHITECTURE.md) の不変条件の文を次に直す。

> plugin は常駐プロセス・MCP サーバ・SQLite を同梱しない。ホストが持つコネクタは、無くても核が動く任意の機能に限って使ってよい。

- plugin は MCP サーバを同梱も設定もしない。`.mcp.json` を配らず、利用者の環境にコネクタを入れることも設定することもしない。
- ホストが持つコネクタを使ってよいのは、無くても核が動く任意の機能だけである。
  核は PRD の「守る核」（分析設計、marimo notebook の契約、journal / reflection、premortem）と、その検証を指す。
- コネクタを使う skill は、コネクタが無い環境では何もせずに案内して終わる。
- SKILL.md にコネクタのツール名を書かない。接頭辞が環境ごとに違うので、「Claude Docs のコネクタ」のように働きで呼ぶ。
- ADR-0001 は凍結のまま変えない。この ADR は ADR-0001 を覆さず、不変条件の文を実態に合わせる。

## Consequences

### Positive

- コネクタを使ってよいかを、不変条件の1文で判断できる。
- コネクタの無い環境でも、核とレポートはこれまでどおり動く。
- `/report-upload` は不変条件の範囲に収まる。

### Negative

- 「核」の範囲は文で決めるしかない。境界の事例（たとえば catalog の登録をコネクタから行う）が出たら、また判断が要る。
- 「コネクタが無い」ことの判定は、SKILL.md を読むモデルに頼る。機械では確かめられない。
- CLAUDE.md と PRD は「No daemon / No MCP server / No SQLite」を見出しとして残す。正本は ARCHITECTURE の文で、
  見出しだけを読んだ人には条件が伝わらない。

## Alternatives considered

- **ADR-0001 を書き換える** — ADR-0001 は凍結している（ADR-0009）。廃止した対象も plugin が立てるサーバで、今も正しい。
- **コネクタを使う機能を別の plugin に分ける** — skill 1本のために配布物が2つになる。コネクタが無ければ何もしない、という条件で同じ守りが得られる。

## Related

- Epic: [epic-12](../design/epic-12-decision-ready-report.md)（Story #67）
- 関連: [ADR-0001](0001-drop-mcp-server-embed-validation.md)（MCP サーバの廃止）、
  [ADR-0016](0016-approval-before-external-send.md)（外部へ送る前の承認）、
  [epic-11](../design/epic-11-repo-template-compliance.md)（US-4: `.mcp.json` の削除）
- Supersedes: なし
