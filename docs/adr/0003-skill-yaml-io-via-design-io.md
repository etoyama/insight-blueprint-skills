# ADR-0003: skill の設計書 I/O を design_io ヘルパに集約する

## Status

Accepted

## Context

ADR-0001 は MCPサーバを廃止し「skill が `.insight/` YAML を直接読み書きする」方向を決めた。E2 で検証は
`validate.py`＋pre-write hook に集約済み。E3 で実際に skill を MCP tool 依存から外すにあたり、調査で以下が判明した:

- 設計書 CRUD には MCP server（`core/designs.py` DesignService / `core/reviews.py` ReviewService）が
  担っていた非自明なロジックがある: ID 生成（max-N+1 `{theme}-H{nn}`）、theme_id 検証、`now_jst` timestamp、
  update の read-merge-write + `referenced_knowledge` ユニオン dedup、reviews.yaml の batch append。
- **pre-write hook は Claude の Write/Edit/MultiEdit ツールしか捕捉しない**。skill が Python で YAML を
  直接書く（`atomic_write_yaml`）と hook は発火せず、schema/transition 検証が抜ける。
- 上記ロジックを各 SKILL.md の自然言語手順で Claude に毎回手計算させるのは、ID 衝突・merge 漏れ・
  timestamp 揺れの温床になる（hook はこれらを捕捉しない）。
- 再利用可能な部品が既にある: `skills/_shared/_atomic.py`（atomic write）、`insight_blueprint.validate`
  （schema/transition）、`insight_blueprint.models`（AnalysisDesign / ReviewBatch）。

## Decision

skill の設計書 I/O を **薄い Python ヘルパ `skills/_shared/design_io.py`** に集約する。

- design_io は create/update/transition/load/list と reviews batch の読み書きを提供し、
  **書込前に `validate.py` を自前で呼ぶ**（schema、status 変更時は transition）。
- design_io は `core/designs.py` / `core/reviews.py` / `server.py` に依存しない。
  存続予定の `insight_blueprint.validate` と `insight_blueprint.models` のみ再利用する
  （E4 でサーバ層を消しても壊れない）。
- pre-write hook は「Write/Edit ツール経由の hypothesis 直接編集」を守るガードとして残す。
  **`validate.py` を design_io と hook の双方が呼ぶ二経路再利用**とし、検証の正本を 1 箇所に保つ。
- skill は MCP tool を呼ばず design_io を使う（CLI: `python -m skills._shared.design_io`）。
  read は Read/glob のままで可。
- 本 ADR は E3 を **設計書ライフサイクル**（design/journal/reflection/revision）に限定し、
  catalog/premortem/lineage の I/O 変換を **E3.5** として E4 の前に分離する（ロードマップ再シーケンス）。

## Consequences

### Positive

- ID 生成・merge・timestamp の非自明ロジックが 1 箇所に集約され、TDD で守られる。
- 検証の正本が `validate.py` のまま（design_io も hook も同じ関数を呼ぶ）。二重実装を避ける。
- design_io がサーバ層に依存しないため、E4 のサーバ削除が design_io を壊さない。

### Negative

- skill が Python ヘルパを CLI 経由で呼ぶ薄い実行面が増える（純粋な「skills + YAML」より一段増える）。
  ただし常駐プロセスではなく、ADR-0001 の「検証はライブラリ」と同じ埋め込み方針の範囲。
- python 直接書込が hook を迂回する事実は残る。design_io の自前検証で塞ぐが、design_io を介さない
  野良 python 書込はガード外（運用上の前提）。

## Alternatives considered

- **純プロンプト（コード追加なし）** — 各 SKILL.md が Read/Write で直接操作し Claude が id 生成・merge・
  timestamp を文脈計算。最小だが、hook が捕捉しない ID 衝突・merge 漏れの信頼性リスクが高く却下。
- **design_io を `src/insight_blueprint/` に置く** — validate.py と並ぶライブラリ化も検討したが、
  validate.py は I/O 無しの純関数という制約（CLAUDE.md §10）。I/O を持つ design_io は skill 付帯の
  `skills/_shared/` に置き、`_atomic` と同居させる。

## Related

- ADR: [ADR-0001](0001-drop-mcp-server-embed-validation.md)（廃止方針）, [ADR-0002](0002-trunk-based-epic-stacking.md)
- Epic: `docs/design/epic-03-skills-yaml-io.md`
- ロードマップ更新: E3（本 Epic）/ **E3.5 catalog・premortem・lineage の I/O 変換**（新設）/ E4 サーバ削除 /
  E5 catalog 柔軟化・premortem 自立化
