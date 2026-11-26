# 開発フロー正典（Epic / Story / DesignDoc / ADR）

このリポジトリが配布する開発フローの正本。CLAUDE.md には要約とポインタのみを置き、
フローの定義は本書を正とする。

## 1. 背景

要件全体を設計しきってから実装する仕様駆動開発では、仕様文書と生成コードが長くなり、
レビューする人間の理解が追いつかなくなる。このフローは要件を**動作確認できる最小単位**
（Story）に分割し、そのまとまり（Epic）ごとの DesignDoc を開発しながら詳細化する。
こうして、AI が作ろうとしているもの・作ったものと、人間が理解している内容とのずれを小さくする。
一度に精査する情報量を絞ることが目的であり、文書を書くこと自体は目的ではない。

経験上、特に効果が高い次の2つを、このフローの必須要素とする。

- ADR: 設計判断を1決定1ファイルで記録し、「なぜこうなっているか」を後から追える
- シーケンス図（mermaid `sequenceDiagram`）: 誰がどの順で何を呼ぶかを人間が一目で検証できる

あわせて、DesignDoc だけを読めば要求から設計までをたどれること（[FLOW-0001](adr/flow/0001-designdoc-owns-requirements.md)）と、
文書・コード・テスト・図が同じ語で書かれていること（[FLOW-0002](adr/flow/0002-ubiquitous-language.md)）を守る。

## 2. 文書階層と正本ルール

```mermaid
flowchart TD
    PRD["docs/PRD.md<br/>なぜ・何を（要件の正本）"]
    ARCH["docs/ARCHITECTURE.md<br/>全体のどう（構成の正本）"]
    UL["docs/UBIQUITOUS_LANGUAGE.md<br/>用語の正本"]
    DD["docs/design/epic-NN-*.md<br/>Epic の要求と詳細設計（開発時に詳細化）"]
    ADR["docs/adr/NNNN-*.md<br/>cross-epic の個別決定"]
    CL["CLAUDE.md<br/>要約とポインタのみ（正本を持たない）"]
    PRD --> ARCH --> DD
    UL -.->|語を使う| DD
    UL -.->|語を使う| ARCH
    DD <--> ADR
    CL -.->|参照| PRD
    CL -.->|参照| ARCH
    CL -.->|参照| ADR
```

| 文書 | 正本として持つもの | 持たないもの |
|---|---|---|
| `docs/PRD.md` | ビジョン、コアバリュー、機能/非機能要件、スコープ外、Epic ロードマップ、成功基準 | 実現方法 |
| `docs/ARCHITECTURE.md` | 不変条件、全体構成図、コンテキストマップ、コンポーネント責務、ディレクトリ構成 | Epic 固有の詳細 |
| `docs/UBIQUITOUS_LANGUAGE.md` | 用語・コード上の名前・定義・使わない言い換え | 設計の説明 |
| `docs/design/epic-NN-*.md` | Epic の背景・ユーザーストーリー・AC・Scope・構成図・ドメインモデル図・シーケンス図・責務表・Epic-scoped な決定・Test Design Matrix | cross-epic の決定（→ ADR）、用語の定義（→ UBIQUITOUS_LANGUAGE） |
| `docs/adr/NNNN-*.md` | cross-epic 決定・長期制約・ARCHITECTURE への変更 | Epic 内で完結する決定（→ DesignDoc） |
| `CLAUDE.md` | AI への行動指示と各正本へのポインタ | 上記すべての実体 |

**ルール: 同じ情報を2箇所に正本として書かない**。要約とポインタは書いてよいが、実体を複製してはいけない。
CLAUDE.md の肥大化はこのルールで構造的に防ぐ。

## 3. Issue の2階層

| | Epic | Story |
|---|---|---|
| label | `type:epic` | `type:story` |
| 単位 | まとまった価値への一歩。DesignDoc を必ず伴う | **動作確認可能な最小単位**。0.5–3日 |
| issue に書くこと | 1〜2行の要約と DesignDoc へのリンク | 親 Epic、対応するユーザーストーリーへのリンク、やること |
| Acceptance Criteria | DesignDoc の User Stories に書く（正本） | 扱う AC は **5個以下**。超えたら Story を分割 |
| 起票フォーム | `.github/ISSUE_TEMPLATE/epic.yml` | `.github/ISSUE_TEMPLATE/story.yml` |

分割の判定基準は「レビューする人間が、その単位の DesignDoc と差分を**一度に読んで
精査しきれるか**」。迷ったら小さくする。

## 4. ライフサイクル

```mermaid
flowchart LR
    A["Epic 起票<br/>(type:epic)"] --> B["DesignDoc 初版<br/>背景 / ユーザーストーリー /<br/>構成図 / ドメインモデル図 /<br/>シーケンス図"]
    B --> B2["全体の整合 / 見本<br/>→ 人間の承認"]
    B2 --> C["Story 分割<br/>(type:story, AC≤5)"]
    C --> D["Story 実装"]
    D --> E["DesignDoc 詳細化<br/>Decisions / Timeline /<br/>Test Matrix ✓"]
    E -->|次の Story| D
    E --> F["Test Design Matrix 全✓"]
    F --> T["実データで使ってみる<br/>→ findings を人間が仕分ける"]
    T --> G["Epic PR →<br/>人間レビュー・人間マージ"]
    G --> H["振り返り<br/>→ 反映の束を人間が選ぶ"]
```

1. Epic 起票: issue には1〜2行の要約だけを書く。背景・AC は DesignDoc に書く。
2. DesignDoc 初版: [.claude/rules/design-doc-template.md](../.claude/rules/design-doc-template.md)
   を `docs/design/epic-NN-<topic>.md` にコピーして書く。初版で埋めるのは Background・
   User Stories（AC を含む）・Stories・Ubiquitous Language・Scope・Architecture 図・
   Domain Model 図・シーケンス図まで。**全節を最初に埋めきらない**。開発しながら詳細化することが、
   このフローの核になる。
   初版を出す前に、「この DesignDoc だけを読んだ人が、誰のどんな課題を解くのか説明できるか」を確かめ、
   §8 の推敲を行う。Epic issue に DesignDoc へのリンクを書く。
   初版の判断は次の順で人間に聞く（決定: [FLOW-0009](adr/flow/0009-designdoc-decisions-scope-first.md)）。
   - 成果物の単位と範囲を決める判断（何を単位に作るか、誰に届けるか）を、中身を決める判断より先に聞く。
   - 中身の判断で迷ったら、決める前に、案ごとの見本を見比べてもらう。下の「見本」の段は判断の途中にも使える。
   人間に初版の承認を求める前に、次の2段を行う（決定: [FLOW-0005](adr/flow/0005-designdoc-draft-checks-whole-and-mockup.md)）。
   - **全体の整合**: 個別の判断がそろったら、全体を見渡して確かめる。判断どうしが矛盾していないか、
     AC・Scope・既存の ADR とかみ合うかを見る。直す点があれば、人間に示して決め直す。
   - **見本**: 利用者が触る成果物（画面、HTML、レポート、CLI の出力、API、生成されるファイルなど）の見本を作り、
     人間とイメージを合わせる。置き場は問わない。成果物が実際に届く場所があればそこに置き、
     そのホストの制約も確かめる。見本はコミットしない。分かった事実と、確かめていない前提を、
     DesignDoc か ADR に書き戻す。利用者から見える変化がない Epic では省いてよい。
     省いたら、その理由を Story Timeline に1行書く。
3. Story 分割: ユーザーストーリーに沿って Story を起票し、DesignDoc の Stories 表に追記する。
4. Story 実装: TDD（Red → Green → Refactor、
   [.claude/rules/coding-principles.md](../.claude/rules/coding-principles.md)）で実装する。
   Story の AC がテストリストの種になる。実装のたびに、次のように DesignDoc を詳細化する。
   計画外の判断は Decisions（Epic-scoped）か ADR（cross-epic）へ、完了は Story Timeline へ、
   テストは Test Design Matrix へ反映する。新しい語は §7 に従って UBIQUITOUS_LANGUAGE に足す。
   Domain Model 図を追加・修正したら、PR 説明に変更を書いて人間の承認を得る。
   Story を完了にする前に、次の2つを行う（決定: [FLOW-0007](adr/flow/0007-story-done-includes-release-note-and-bug-review.md)）。
   - 利用者に効く変更があれば、リリースノートに1行書く。このリポジトリでは CHANGELOG の `[Unreleased]` に書く。
   - Story の差分に、バグ・セキュリティの観点のレビューを1本回す。直すものは Story の中で直す。
     コード品質の観点は、Epic 完了の前にまとめて見る。
5. Epic 完了: Test Design Matrix 全✓ が Epic PR のレビューゲート。PR を開く前に §8 の推敲を行う。
   利用者が触る Epic では、ゲートのレビューと直しの後、Epic PR を開く前に、**実データで使ってみる**
   （決定: [FLOW-0016](adr/flow/0016-try-with-real-data-before-epic-pr.md)）。
   利用者が実際に使う場所（リポジトリ、データ、環境）で、epic ブランチの成果物を使う。
   このリポジトリでは、実際の分析のリポジトリで epic ブランチの plugin を使う。手順は
   [CONTRIBUTING の「Trying an Epic branch in another project」](../CONTRIBUTING.md#trying-an-epic-branch-in-another-project)。
   出た findings は、人間が「Epic で直す / issue にする」に仕分ける。Epic で直すものは PR を開く前に直す。
   利用者から見える変化がない Epic では省いてよい。省いたら、その理由を Story Timeline に1行書く。
   **AI アシスタントは Epic PR をマージしない**。人間がレビューしてマージする。
6. 振り返り: Epic のリリースまで終えたら、振り返りを1回回す（決定: [FLOW-0010](adr/flow/0010-retrospective-after-epic.md)）。
   人間が頼んだときも回す。下敷きは Derby と Larsen の5段（場を作る、データを集める、洞察を出す、
   何をするか決める、閉じる）で、場を作る段と閉じる段はそれぞれ1行にする。次の4つを1回で出す。
   - 事実: 時刻つきの流れ、人間が決めたことの一覧、起きたこと（詰まり、やり直し、うまくいったこと）。
     人を責めず、手順と仕組みの言葉で書く（blameless）。推測は推測と書く。
   - 学び: 1件ごとに根拠の事実を指す。続けること（うまくいったこと）も入れる。
   - 反映の案: 束ごとに、置き場（テンプレートのフロー、このリポジトリだけ、個人のメモリ）と中身を表にする。
   - 前回の振り返りで反映したことが効いたかを、1件ずつ1行で書く。

   反映する束は人間が選ぶ。フローの定義を変える束は ADR を伴う。
   振り返りの全文は Epic issue のコメントに残し、ファイルとしてはコミットしない。

## 5. ブランチモデル

トランクベースに Epic stacking を組み合わせる。

- `main` がトランク。`dev` などの統合ブランチは置かない。
- Epic: `epic/<issue番号>-<slug>` を `main` から切る。Epic PR は `main` 向き。
- Story: 既定では Epic ブランチに直接コミットする。独立してレビューする価値がある Story だけ
  `(feat|fix|chore|refactor)/<issue番号>-<slug>` を Epic ブランチから切り、
  Epic ブランチへ PR を出す（stacked PR）。
- リリースをタグ駆動（`v*`）にする場合、`main` へのマージはリリースを意味しない。

## 6. ADR 運用（ハードルール）

Story 実装中に、承認済みの計画が想定していなかった設計判断が出たら、PR マージ前に
必ず次のいずれかを行う。

1. **ADR を作る**（既定。アーキテクチャ・ライブラリ選定・公開契約の変更など非自明な判断）。
2. DesignDoc の `## Decisions` に書く（効果がその Epic を超えない場合のみ）。
3. PR 説明に明記して人間に確認する（1 も 2 も過剰といえる小さな判断のみ）。

判断の Consequences に、既存の入力や利用の場面が失敗に変わること（受け付けていた入力を拒む、
失敗の範囲が広がる）があれば、2 の Decisions に書くだけでなく、人間に聞いてから先へ進む
（決定: [FLOW-0008](adr/flow/0008-ask-before-narrowing-what-worked.md)）。

黙って判断して先へ進むことを禁止する。テンプレートは
[.claude/rules/adr-template.md](../.claude/rules/adr-template.md)、索引は
[docs/adr/README.md](adr/README.md)。

ADR の Problem と Decision Analysis、および人間に判断を仰ぐときの提示は、
[decision-analysis](https://github.com/etoyama/decision-analysis) プラグインの
`decision-analysis` スキルの形式に従う（決定: [FLOW-0004](adr/flow/0004-decision-analysis-plugin.md)）。
プラグインは `.claude/settings.json` で宣言し、clone ごとに `scripts/install-plugins.sh` で入れる。形式の正本はスキルにあり、本書には写さない。
提示が足りなかったときは、人間が「DA で」と言うか、理由を聞き返せば出し直される。

## 7. ユビキタス言語

用語の正本は [docs/UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md)
（決定: [FLOW-0002](adr/flow/0002-ubiquitous-language.md)）。

- 文書・会話・クラス名・型名・テスト名・図のラベルは、この表の語だけを使う。
- AI は文書やコードを書く前にこのファイルを読む。表にない概念を使うときは、同じ PR で表に足す。
- 用語の改名・意味の変更は ADR を伴う。新語の追加だけなら PR 説明への明記でよい。
- ユビキタス言語は境界づけられたコンテキストごとに1つ持つ。分ける基準は
  UBIQUITOUS_LANGUAGE.md の「コンテキストを分けるとき」に従う。分けたら
  ARCHITECTURE のコンテキストマップを更新する。

## 8. 日本語の文書の推敲

日本語の文書は [yomiyasu](https://github.com/nanaism/yomiyasu) で推敲する
（決定: [FLOW-0003](adr/flow/0003-yomiyasu-for-japanese-docs.md)。導入は `scripts/install-plugins.sh`、
[FLOW-0004](adr/flow/0004-decision-analysis-plugin.md)）。

| 項目 | 内容 |
|---|---|
| 対象 | `docs/` 配下の文書、issue 本文、PR 説明。コード、コードコメント、mermaid の中身は対象外 |
| タイミング | DesignDoc 初版を出す前と、Epic PR を開く前。一文ごとの編集では行わない |
| 文書の種類 | DesignDoc・ADR・ARCHITECTURE・PRD は proposal、WORKFLOW は manual、PR 説明は pr。読者は expert |
| 英語の扱い | 節名は英語のまま。日常的に使われる語や専門用語も英語でよく、推敲でも訳さない |
| 用語 | UBIQUITOUS_LANGUAGE の「用語」を `.yomiyasu-words/allow.txt` に、「使わない言い換え」を `flag.txt` に書き出す。正本は UBIQUITOUS_LANGUAGE |
