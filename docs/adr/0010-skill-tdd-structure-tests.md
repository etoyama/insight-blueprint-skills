# ADR-0010: skill の TDD は構造テストを先に書くことと読む

## Status

Accepted

## Context

[coding-principles](../../.claude/rules/coding-principles.md) は TDD を必須とし、
「DesignDoc の Test Design Matrix に ✓ を付けてよいのは、その層のテストが Red → Green を経て存在するとき」と定める。
このリポジトリの成果物の多くは SKILL.md で、Claude が読んで動く文章である。
Python のテストランナーは文章の解釈を実行できない。repo-template（[ADR-0009](0009-adopt-repo-template-flow.md) で採用）は、
文章を主な成果物とするリポジトリでの TDD の読み方を定めていない。

2026-11-15 に人間が D6 として決めた（準拠作業の論点番号）。比較の前提にした事実は次のとおり。

- SKILL.md は14本・2,608行、Python は2,151行ある（判断時の調査による。`wc -l` で数えた）。
- `tests/skills/` に SKILL.md の構造テストがある。必須の節、chaining の表、skill 間の整合を確かめる
  （`tests/skills/test_skill_structure.py` を読んだ）。
- Epic 10 までの Test Design Matrix の ✓ は、自動テスト・文書の更新・手動確認が混ざっている。「—」のセルもある
  （判断時の調査による。たとえば [epic-10](../design/epic-10-analysis-report.md) の Matrix は、
  Integration の ✓ が「apa-template.md を正本化」という文書の更新を指している）。
- `tests/e2e/` に headless 実行の harness とスタブがあるが、今も使えるかは確かめていない。

## Problem

- 課題1: repo-template の規則（✓ は Red → Green を経たテストがあるときだけ）と、今の ✓ の付け方が食い違う。
- 課題2: SKILL.md が壊れても pytest では気づけない。
- 課題3: ✓ の意味が曖昧だと、Test Design Matrix のレビューゲートが形だけになる。

扱わない範囲: skill の解釈そのもの（Claude が SKILL.md をどう読むか）の自動検査。既存の DesignDoc の Matrix の書き直し（ADR-0009 で凍結）。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | TDD を無効化しない | Must | - | - | coding-principles |
| M2 | ✓ は自動テストがある層にだけ付く | Must | - | - | 課題3、coding-principles |
| W1 | skill の振る舞いの退行に気づける | Want | 解決 | 高（Claude の推測） | 課題2 |
| W2 | テストを書いて回す費用 | Want | 費用 | 高（Claude の推測。人間が A を選んで追認） | YAGNI |
| W3 | Matrix から未検証の層が分かる | Want | 解決 | 中（Claude の推測） | 課題3 |

| Must | 何もしない | A. 構造テスト先行 | B. skill は TDD の対象外 | C. headless 実行の E2E を必須 | D. 手動確認も ✓ |
|---|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない | 満たす | 満たす |
| M2 | 満たさない（手動確認や文書の更新にも ✓ が付く） | 満たす | 満たす | 満たす | 満たさない |

| Want | A. 構造テスト先行 | C. headless 実行の E2E を必須 |
|---|---|---|
| W1 | 節や表の欠落、skill 間の食い違いには気づける。解釈の退行には気づけない | 実際に動かすので、解釈の退行にも気づける |
| W2 | 既存の `tests/skills/` と同じ型で足せ、数秒で回る | Story ごとに harness とスタブが要り、実行に課金があり、結果が揺れる |
| W3 | ✓ と「—（理由）」で、自動で検査していない層が読める | ✓ がほぼすべての層に付く |

- 差がつく基準: W1 は C、W2 は A が勝つ。決め手は W2。C は、必要な skill にだけあとから足せる。
- 感度: 課金と結果の揺れを許容するなら C に変わる。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 構造テストは通るのに、skill が意図と違う動きをする | 手動確認を Story Timeline に日付つきで残す。退行が見つかった skill には C を足す |
| C | E2E が不安定で、ゲートが常に赤くなるか、無視される | なし |

## Decision

A を採る。決め手は W2。

- Python（`validate.py`・`design_io`・models など）は、これまでどおり TDD 必須とする。
- SKILL.md と文書は、構造テストを先に書いて Red にし、本文を書いて Green にすることを TDD とする。
  構造テストは既存の `tests/skills/`（SKILL.md）と `tests/docs/`（正本の文書）と同じ型で足す。
- Test Design Matrix の ✓ は、Red → Green を経た自動テストがある層にだけ付ける。
  文書の更新と手動確認では ✓ を付けない。
- 自動テストがない層のセルには「—（理由）」と書く。レビューゲートは「— 以外がすべて ✓」と読む。
- 手動確認は Story Timeline に日付つきで残す。

## Consequences

### Positive

- ✓ の意味が1つになり、Matrix を見れば自動で検査している層と、していない層が分かる。
- skill の構造の退行（節の欠落、chaining の食い違い）は、`uv run poe all` で捕まる。

### Negative

- skill の解釈の退行は自動では捕まらない。手動確認の記録に頼る。
- 「—」を書けばゲートを通せるので、理由が弱い「—」をレビューで見抜く必要がある。
- 「—」の数え方は repo-template にない解釈である。repo-template に返すまで、ここだけの読み方になる。

## Alternatives considered

なし。検討した案はすべて Decision Analysis の表に入れた。

## Related

- Epic: [epic-11](../design/epic-11-repo-template-compliance.md)（Story #59）
- 関連: [ADR-0009](0009-adopt-repo-template-flow.md)、[coding-principles](../../.claude/rules/coding-principles.md)
- Supersedes: なし
