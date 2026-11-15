# ADR Template

Architecture Decision Records (ADRs) は cross-epic な設計判断・長期制約・
`docs/ARCHITECTURE.md` に記述されたアーキテクチャへの変更を記録する。
決定の効果が現在の Epic を超えて持続する場合に使う。

コピー先: `docs/adr/NNNN-<kebab-slug>.md`

`NNNN` は4桁ゼロ詰めの連番（次のID = 既存最大 + 1）。1ファイル1決定。
確定後 `docs/adr/README.md` に追記する。

Epic 内で完結し他 Epic に影響しない決定は、ADR にせず Epic の Design Doc の
`## Decisions` セクションに残す。

---

# ADR-NNNN: <Title>

## Status

Proposed | Accepted | Deprecated | Superseded by ADR-MMMM

## Context

<どんな力学が働いているか。何の調査が引き金か。決定を促した Story / Epic / PR を
引用する。半年後の読者が会話を読み返さずに状況を再構成できる程度に書く。
比較の土台にした事実と、それを確かめた方法（読んだファイル、実行したコマンド）も書く。>

## Problem

- 課題1: <誰が、何に困るか。放置するとどうなるか>
- 課題2: <…>

扱わない範囲: <この ADR で解かないこと>

## Decision Analysis

<形式の正本は decision-analysis plugin の `decision-analysis` スキル
（[FLOW-0004](../../docs/adr/flow/0004-decision-analysis-plugin.md)）。書く前に読む。>

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | <…> | Must | - | - | <課題1> |
| W1 | <…> | Want | <解決 / 費用> | <高（人間）> | <課題2> |

| Must | <案A> | <案B> | 何もしない |
|---|---|---|---|
| M1 | <満たす> | <満たす> | <満たさない> |

| Want | <案A> | <案B> |
|---|---|---|
| W1 | <文で書く> | <文で書く> |

- 差がつく基準: <Wn>
- 感度: <Wn の重みが X なら結論は Y に変わる>

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| <案A> | <…> | <…> |

## Decision

<何を決めたか。断定形で書く（「〜する」）。決め手になった基準も書く。>

## Consequences

### Positive

- ...

### Negative

- <残るリスクと、この決定では塞がない穴も書く>

## Alternatives considered

<評価の前に落とした案だけを書く。Decision Analysis の表に入れた案は書かない。>

- **<案>** — <落とした理由>

## Related

- Epic: #N or `docs/design/epic-NN-*.md`
- Stories: ...
- PRs: ...
- Supersedes: ADR-MMMM (該当時)
