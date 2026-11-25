# FLOW-0013: DesignDoc とブリーフには、守りたい規則、触らない理由、使う既存の道具を書く

## Status

Accepted

## Context

DesignDoc のテンプレート（`.claude/rules/design-doc-template.md`）は、AC の置き場と Scope の節を持つ。
AC の書き方と、範囲外の書き方は決めていない。PM セッションのブリーフの型（`.claude/skills/pm-session/SKILL.md` §4）は、
Story の子に渡す項目を決めている。すでにあるテストの helper の場所を書く項目は無い。

このテンプレートの派生先の Epic 31（etoyama/insight-blueprint-skills、[#207](https://github.com/etoyama/insight-blueprint-skills/issues/207)、2026-11-25）で、
次の3つが起きた。振り返り（#207 のコメント）で確かめた。

- AC を「〜が無い」（消したファイルや job が無い）と書いた。Story は、消した物の不在や旧い語を固定するテストを書いた。
  Epic のゲートのレビューで、守りたい規則（どの workflow も publish の action を使わない、など）の検査に絞り直した。
- DesignDoc が「この Epic では `skills/analysis-notebook/SKILL.md` に触らない」と書いた。理由は「別の単発の PR（#215）が同じファイルを触っている」だったが、
  その PR は Epic の途中でマージされた。理由が消えた後も「触らない」だけが残った。ゲートで見つかった穴を同じファイルでも塞ぐかが、計画外の判断になった。
- Story の子が、すでにあるテストの helper（`tests/skills/_markdown.py` の `section` と、実行コマンドの定数）を作り直した。

3つとも、DesignDoc かブリーフに書かれていなかったことを、後の作業が補った所で起きた。

## Problem

- 課題1: AC が不在で書かれると、テストが不在を固定する。同じ穴が別の名前で開いても見つからず、名前を変えるたびにテストが壊れる。
- 課題2: 理由の無い「触らない」は、理由が消えても残る。ゲートで計画外の判断が増える。
- 課題3: 既存の helper を知らない子が作り直し、重複が増える。ゲートで直す手間がかかる。

扱わない範囲: テストの書き方そのもの（[.claude/rules/coding-principles.md](../../.claude/rules/coding-principles.md) のまま）。helper の置き場の決め方。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 3つの課題のそれぞれに、書く場所が1つ決まっている | Must | - | - | 課題1〜3 |
| W1 | 1つのセッションで DesignDoc を書く環境にも届く | Want | 解決 | 中（Claude の推測） | FLOW-0009 の W3 |
| W2 | テンプレートとブリーフが長くなりすぎない | Want | 費用 | 中（Claude の推測） | - |

| Must | A. AC と Scope はテンプレートに、helper はブリーフの型に書く | B. 3つともブリーフの型に書く | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない |

| Want | A | B |
|---|---|---|
| W1 | AC と Scope の書き方は、PM を使わない初版にも効く | PM が子に渡すときだけ効く |
| W2 | テンプレートに3行と1行、ブリーフに1項目 | ブリーフに3項目 |

- 差がつく基準: W1。
- 感度: W1 を低くしても、W2 の差は小さいので A のまま。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 規則で書いた AC が抽象的になり、確かめ方が分からない | 例を添える（「どの workflow も publish の action を使わない」） |
| A | helper の項目に「無し」が並び、形だけになる | PM がブリーフを書く前にテストの共通の置き場を見ると書く |
| B | 1つのセッションで書く初版では、同じことが起きる | なし |
| 何もしない | Epic 31 の3つが繰り返される | ゲートで拾えるが、直しの手間がかかる |

## Decision

A を採る。

- DesignDoc のテンプレートの User Stories に、「AC は、何が無いかではなく、守りたい規則で書く」と例を足す。
- DesignDoc のテンプレートの Scope に「触らない所」の行を足し、理由を必ず書くとする。理由が消えたら触ってよい。触ると決めたら Decisions に書く（[docs/WORKFLOW.md](../WORKFLOW.md) §6 の2）。
- PM のブリーフの型の `prompt` に、「使う既存の helper とテストの道具の場所」の項目を足す。

人間が束 C として採った（派生先の Epic 31 の振り返り、2026-11-25）。決め手は W1。

## Consequences

### Positive

- テストが規則を検査するので、名前を変えても壊れず、別の名前で開いた穴も見つかる。
- 「触らない」の理由が消えたかを、ゲートで一目で確かめられる。
- 子が既存の helper を使うので、重複が減る。

### Negative

- AC を規則で書くのは、不在で書くより考える手間がかかる。
- helper の場所は PM が調べて書く。PM が見落とすと、同じ重複が起きる。
- 根拠は1件（Epic 31）だけである。

## Alternatives considered

- **不在を固定するテストを禁じる規則を coding-principles に足す** — テストの書き方の前に、AC の書き方が原因になっている。原因の側で直す。

## Related

- [FLOW-0001](0001-designdoc-owns-requirements.md)（DesignDoc が要求の正本）、[FLOW-0006](0006-pm-session-and-board.md)（PM セッション）、[FLOW-0009](0009-designdoc-decisions-scope-first.md)（初版の判断の順）
- 派生先の先行例: etoyama/insight-blueprint-skills の Epic 31（#207）の振り返り
