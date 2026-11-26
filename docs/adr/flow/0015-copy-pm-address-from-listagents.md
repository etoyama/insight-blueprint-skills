# FLOW-0015: ブリーフに書く PM の宛先は ListAgents から写し、PM のシステムプロンプトの宛先と置き場は写さない

## Status

Accepted

## Context

PM セッション（[FLOW-0006](0006-pm-session-and-board.md)）は、子や単発のセッションのブリーフに、
報告の宛先として PM 自身を書く。共有ノートの置き場は [FLOW-0012](0012-shared-notes-in-app-folder-checked-by-path.md) で、
「ブリーフにはパスを書かず、子が自分のシステムプロンプトの Shared notes folder を使う」と決めた。

このテンプレートの派生先の Epic 32（etoyama/insight-blueprint-skills、[#217](https://github.com/etoyama/insight-blueprint-skills/issues/217)、2026-11-25）で、
PM はブリーフに自分を立てたセッション（前の Epic の PM）の id を書き、宛先と共有ノートの置き場を2つとも間違えた（#217 の振り返りのコメント）。

確かめた事実は次のとおり。

- `get_session` で PM #217 を引くと、`parentSessionId` は前の Epic の PM で、`detached: true` だった。
  [pm-session §8](../../../.claude/skills/pm-session/SKILL.md) は、次の PM を前の PM から立てて切り離す。こうして立てた PM は、親を持つ子として始まる。
- 子のシステムプロンプトは自分を立てたセッションの id を宛先として、そのセッションの置き場を Shared notes folder として示す。
  この ADR を書いたセッション（PM #217 の子）のシステムプロンプトで確かめた。そこでは、どちらも PM #217 のものだった。
- `ListAgents` の先頭の行は「This session is <名前> [<ref>]」で、呼んだセッション自身の宛先を示す。この ADR を書いたセッションで確かめた。
- `get_session` に `"self"` を渡すと、自分の `sessionId`（`local_…`）が返る（道具の説明による）。

PM #217 のシステムプロンプトに、親の id と親の置き場が書かれていたかは見ていない。上の事実からの推測である。

## Problem

- 課題1: PM が記憶やシステムプロンプトで自分の宛先を書くと、切り離された PM は親の id を書く。子の報告が終わった前の Epic の PM に届く。
- 課題2: 同じ理由で、PM が自分のシステムプロンプトの置き場を写すと、子が前の Epic の置き場に書く。

扱わない範囲: 置き場の実体の確かめ方（FLOW-0012 のまま）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 切り離された PM でも、自分の宛先を正しく書ける | Must | - | - | 課題1 |
| M2 | 子が使う置き場が、PM の子の置き場になる | Must | - | - | 課題2 |
| W1 | ブリーフを書く手間が増えない | Want | 費用 | 中（Claude の推測） | - |

| Must | A. 宛先は `ListAgents` の「This session is …」から写す。置き場は子が自分のシステムプロンプトから取る | B. 宛先も置き場も PM のシステムプロンプトから写す | 何もしない（記憶で書く） |
|---|---|---|---|
| M1 | 満たす | 満たさない（親の id になる） | 満たさない |
| M2 | 満たす（FLOW-0012 のまま） | 満たさない（親の置き場になる） | 満たさない |

| Want | A |
|---|---|
| W1 | ブリーフを書くターンで `ListAgents` を1回呼ぶ。置き場は今までどおりパスを書かない |

- 差がつく基準: M1 と M2。
- 感度: Must で決まるので、W1 の重みでは変わらない。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 名前が同じセッションがあり、名前だけでは届かない | `[ref]` まで写す。`local_…` の id で書くなら `get_session` の `"self"` から写す |
| A | 人間がセッションの名前を変えて、写した名前が古くなる | ブリーフを書くターンで毎回呼ぶ。前のブリーフから写さない |

## Decision

A を採る。手順の正本は `.claude/skills/pm-session/SKILL.md` の §4 のブリーフの型に置く。

- ブリーフに書く PM の宛先は、そのターンで呼んだ `ListAgents` の「This session is …」の行から、名前と `[ref]` を写す。
  `local_…` の id で書くなら、`get_session` に `"self"` を渡して返った `sessionId` を写す。
- PM のシステムプロンプトにある宛先の id と Shared notes folder は、ブリーフに写さない。PM が別のセッションから立てられていると、どちらも親のものになる。
- 共有ノートの置き場は、FLOW-0012 のとおり、子が自分のシステムプロンプトの Shared notes folder から取る。ブリーフにはパスを書かない。

人間が束 A として採った（派生先の Epic 32 の振り返り、2026-11-25）。決め手は M1 と M2。

## Consequences

### Positive

- 切り離された PM でも、子の報告が自分に届く。
- 子が書く置き場と、PM が `board/summary` の `notes_dir` で確かめる置き場が一致する。

### Negative

- PM のシステムプロンプトの中身は見ていない。親の id と置き場が書かれているという前提は推測である。
- ブリーフの書き手が PM ではなく人間や別のセッションのときには、この手順は効かない。

## Alternatives considered

- **ブリーフに PM の宛先を書かず、子が `list_sessions` の `startedBy` から取る** — 単発のセッションを人間が立てたときなど、立てた側が PM と限らない。

## Related

- [FLOW-0006](0006-pm-session-and-board.md)（PM セッション）
- [FLOW-0012](0012-shared-notes-in-app-folder-checked-by-path.md)（共有ノートの置き場）
- 派生先の先行例: etoyama/insight-blueprint-skills の Epic 32（#217）の振り返り
