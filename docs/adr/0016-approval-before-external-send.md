# ADR-0016: skill が `.insight/` の中身を外部へ送るときは、KEEP ゲートで承認を待つ

## Status

Accepted

## Context

[Epic 12](../design/epic-12-decision-ready-report.md) の Story
[#67](https://github.com/etoyama/insight-blueprint-skills/issues/67)（US-4）は、
レポートと図を Claude Docs にアップロードする skill `/report-upload` を足す。
skill が `.insight/` の中身を利用者の手元の外へ送るのは、これが初めてである。
`.insight/` には手法・指標・journal の文があり、機密や個人情報を含みうる。

2026-11-15 に、Story #67 の中で人間が決まりを決めた（issue #67 のコメント）。比較の前提にした事実は次のとおり。

- [ADR-0005](0005-selective-autonomous-chaining.md) は、notebook が宣言したデータソース以外と通信するときに
  KEEP ゲートで止めると決めた。skill 自身が外部へ送る場合は決めていない（ADR-0005 の Decision を読んだ）。
- guided autopilot（`/analysis-auto`）は skill を順に動かし、KEEP ゲートでだけ止まる。
  Epic 12 では、driver がレポートを作った後に `/report-upload` を起動する（Epic 12 の Sequence Diagram）。
  このとき、分析者は `/report-upload` を自分では起動していない。
- アップロードで作った Doc は、作った本人だけが見える状態で始まる（Epic 12 の Decision `skill-name-report-upload`）。
- ホストがツールの呼び出しごとに承認を出すかどうかは、環境と利用者の設定で変わる。skill からは決められない。

## Problem

- 課題1: 分析者が知らないうちに、`.insight/` の中身が外部へ出る。とくに guided autopilot の中では、
  分析者が送信を承認する場面が無い。出た後では取り消せない。
- 課題2: 決まりが `/report-upload` だけのものだと、次に外部へ送る skill を書く人が気づかない。
  skill ごとに守りが違う状態になる。

扱わない範囲: 送る中身に機密や個人情報があるかの検査（分析者が自分で見る）。
notebook の外部通信（ADR-0005）。Doc を作った後の共有（Claude Docs の上で分析者が行う）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 外部へ送るのは、送る物を見た分析者が承認した後だけである。guided autopilot の中でも同じ | Must | - | - | 課題1、US-4 AC 2、ADR-0005 |
| W1 | 将来の skill も同じ守りを持つ | Want | 解決 | 高（人間） | 課題2 |
| W2 | 分析者の手順の数 | Want | 費用 | 中（Claude の推測。人間が A を選んで追認） | Epic 12 US-5 AC 2「聞かれるのは1回だけ」 |
| W3 | 決まりを保つ費用（文書・テスト・設定） | Want | 費用 | 低（Claude の推測） | YAGNI |

案は次の5つ。

- A. 一般の決まりにする。外部へ送る skill はすべて、送るファイルを列挙して KEEP ゲートで承認を待つ。承認は覚えない。
- B. `/report-upload` だけの決まりにする。中身は A と同じ。
- C. A に加えて、設定での許可も必須にする（設定で許可した利用者だけが送れる）。
- D. skill の起動を承認とみなす。
- 何もしない: ホストの承認に任せる。

| Must | A. 一般の決まり | B. `/report-upload` だけ | C. 設定での許可も必須 | D. 起動を承認とみなす | 何もしない |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たさない（guided autopilot の中では driver が起動するので、分析者の承認が無い） | 満たさない（ホストの承認は設定で出なくなる。送る物の一覧も出ない） |

| Want | A. 一般の決まり | B. `/report-upload` だけ | C. 設定での許可も必須 |
|---|---|---|---|
| W1 | ARCHITECTURE の KEEP ゲートの一覧に載り、次の skill を書く人が読む | SKILL.md の中にだけあり、次の skill を書く人は気づかない | A と同じ |
| W2 | 承認の1回だけ | 承認の1回だけ | 初回に設定が要る。設定の場所と形を覚えることになる |
| W3 | ADR 1本と ARCHITECTURE の1行 | SKILL.md の中だけ | A に加えて、設定の形・読み方・テストが要る |

- 差がつく基準: W1 は A と C が勝つ。W2 と W3 は A と B が勝つ。決め手は W1。A と C の差は W2 で、A が勝つ。
- 感度: 承認を読まずに押す事故が実際に起きたら、W2 の重みを下げて C に変える。設定での許可は後から足せる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 承認を読まずに押す癖がつき、守りが形だけになる | 列挙を短く保つ。送り先と「Doc は自分だけに見える状態で作られる」ことを同じ画面に書く |
| B | 次に外部へ送る skill が、承認なしで作られる | レビューで気づくしかない |
| C | 初回の手順が増え、アップロードが使われなくなる | 設定の案内を承認の文に入れる |
| D | guided autopilot が、分析者の知らないうちにレポートを送る | 抑えられない |
| 何もしない | ホストの承認を常に許可にした利用者は、何も見ずに送ることになる | 抑えられない |

## Decision

A を採る。決め手は W1。

> skill が `.insight/` の中身を外部へ送るときは、送るファイルを列挙して KEEP ゲートで承認を待つ。
> `/analysis-auto` の中でも自動にしない。承認は1回の実行に限り、覚えない。

- 「外部へ送る」は `.insight/` の中身を利用者の手元の外（ホストのコネクタ、ネットワークの先）へ渡すことを指す。
- 列挙は送るファイルのパスで行う。送り先と、送った物が誰に見える状態になるかを、同じ画面に書く。
- 承認はその実行で列挙したファイルにだけ効く。設定・ファイル・メモリに残さず、次の実行ではまた聞く。
- 承認が無ければ何も送らない。skill の起動、先に出したほかの承認、ホストの承認は、この承認の代わりにならない。
- guided autopilot では、driver は「送るか」を別に聞かない。送る skill の KEEP ゲートがただ1回の問いになる。
- 設定での許可は入れない。必要になったら、この ADR を改めて足す。
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) の KEEP ゲートの一覧に1行足す。

## Consequences

### Positive

- `.insight/` の中身は、分析者が送る物を見て承認した後にだけ外へ出る。guided autopilot の中でも変わらない。
- 次に外部へ送る skill を書く人は、KEEP ゲートの一覧からこの決まりを読める。
- ADR-0005 の「宣言したデータソース以外との通信は KEEP ゲートで止める」が、notebook から skill 自身にも広がる。

### Negative

- 承認を読まずに押す癖がつくと、守りは形だけになる。列挙を短く保つことでしか抑えられない。
- 送る中身に機密や個人情報があるかは、分析者が自分で見るしかない。skill は検査しない。
- KEEP ゲートを守るかどうかは SKILL.md を読むモデルに頼る。機械では強制できない（ADR-0005 と同じ限界）。
  構造テストは、SKILL.md に決まりが書いてあることまでを確かめる。
- ホストも呼び出しごとに承認を出す環境では、分析者は2度聞かれる。

## Alternatives considered

- **送る前に機密や個人情報を機械で検査する** — 何が機密かは分析ごとに違い、検査の誤りが「検査を通ったから安全」という思い込みを生む。

## Related

- Epic: [epic-12](../design/epic-12-decision-ready-report.md)（Story #67）
- 関連: [ADR-0005](0005-selective-autonomous-chaining.md)（KEEP ゲートと notebook の外部通信）、
  [ADR-0007](0007-upstream-judgment-gates.md)（上流の KEEP ゲート）、
  [ADR-0015](0015-host-connectors-for-optional-features.md)（ホストのコネクタの使い方）
- Supersedes: なし
