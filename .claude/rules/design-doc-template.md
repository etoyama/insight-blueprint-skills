# Design Doc Template

コピー先: `docs/design/epic-NN-<topic>.md`。
`NN` は Epic Issue ID とは独立のゼロ詰め連番（`01`, `02`, …）。

---

# Epic NN: <Title>

## Acceptance Criteria

Epic Issue body から転記する。

- [ ] AC 1
- [ ] AC 2

## Glossary

| Term | Meaning |
|---|---|
| <略語 or ドメイン用語> | <説明; 本文で略語を単独参照しない> |

## Architecture

<図（ASCII or リンク画像）または構成を説明するテキスト。
既存の関数・ファイルはパスで参照する。>

## Module Responsibilities

- `<path>::<function>` — <責務>

## Data Flow

<シーケンス or データフローの説明。外部境界（ファイルシステム, ネットワーク, 外部API）を含める。>

## Data Model

| Field | Type | Purpose | Example |
|---|---|---|---|
| ... | ... | ... | ... |

## Decisions

このセクションは **Epic-scoped** な決定のみ置く（効果がこの Epic を超えないもの）。
cross-epic な決定（長期制約・アーキテクチャ変更・ライブラリ選定・公開API契約変更・
AC再解釈）は `docs/adr/` の ADR に置く。
[.claude/rules/adr-template.md](adr-template.md) と CLAUDE.md の ADR ハードルールを参照。

### Decision: <kebab-case-slug>

- **What**: <決定>
- **Why**: <動機>
- **Affected modules**: <一覧>
- **Alternatives considered**: <一覧と簡潔な理由>
- **Consequences**: <正負の含意>

### Cross-epic decisions (links to ADR)

- [ADR-NNNN: <title>](../adr/NNNN-<slug>.md) — 一行サマリ

## Test Design Matrix

| Story \ Layer | Unit | Integration | E2E |
|---|---|---|---|
| Story N.M | ☐ | ☐ | ☐ |

完了時に ✓ を付ける。このマトリクスが Epic PR のレビューゲート。

## Story Timeline

Story 完了とキーイベントの追記専用ログ。

- YYYY-MM-DD — Story N.M completed: <一行サマリ>
