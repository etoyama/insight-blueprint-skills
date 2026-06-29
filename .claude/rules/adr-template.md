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
引用する。半年後の読者が会話を読み返さずに状況を再構成できる程度に書く。>

## Decision

<何を決めたか。断定形で書く（「〜する」）。>

## Consequences

### Positive

- ...

### Negative

- ...

## Alternatives considered

- **<案1>** — <却下理由>
- **<案2>** — <却下理由>

## Related

- Epic: #N or `docs/design/epic-NN-*.md`
- Stories: ...
- PRs: ...
- Supersedes: ADR-MMMM (該当時)
