# ADR-0004: catalog の taxonomy を open string にする

## Status

Accepted

## Context

軽量版の公開契約は、MCP サーバ撤去（[ADR-0001](0001-drop-mcp-server-embed-validation.md)）
後に生き残った `insight_blueprint.models`（Pydantic モデル）である。その catalog モデルは
種別を閉じた `StrEnum` で固定していた:

- `SourceType` = `csv` / `api` / `sql`
- `KnowledgeCategory` = `methodology` / `caution` / `definition` / `context` / `finding`

これが Epic 5c の調査で痛点になった。parquet / Google Sheets / BigQuery / GraphQL の
ような source 種別や、`data-quality` / `regulatory` / `seasonality` のような分野固有の
knowledge category を登録するには **enum を編集してライブラリをリリースし直す**必要があった。
これは「skills が YAML を管理し、ライブラリは薄い検証だけを持つ」という本プロジェクトの
不変条件（ARCHITECTURE.md）と正面から衝突する。E5b で `add-knowledge`（write パス）を
入れた直後だけに、書き込める語彙が5語に縛られる歪みが顕在化した。

引き金: Epic 5c 調査 / Story 5c.1。方針は AskUserQuestion で「A: free str + 既知定数 +
`extra=allow`」を選択（代替 B: validator ハイブリッド、C: `extra` のみ は却下）。

## Decision

catalog の**分類は open string** にする。`SourceType` / `KnowledgeCategory` の `StrEnum` を
廃し、`DataSource.type` / `DomainKnowledgeEntry.category` を非空の `str`
（`Field(min_length=1)`）にする。

- 慣習値は検証にではなく **UX ヒント**に使う。モジュール定数
  `KNOWN_SOURCE_TYPES` / `KNOWN_KNOWLEDGE_CATEGORIES` として公開し、skill が候補提示に用いる。
- 特別扱いのある唯一の category `finding` は `FINDING` 定数で保持する
  （findings は catalog でなく reflection に残す — E5b）。
- `ColumnSchema` と `DataSource` は `model_config = ConfigDict(extra="allow")` にし、
  ドメイン固有メタ（列の `pii` / `source_system` 等）が read/write の往復で保持されるようにする。
- `KnowledgeImportance`（`high` / `medium` / `low`）は**閉じた enum のまま**残す。順序尺度で
  ソート・UX を駆動するため、自由値は意味を持たない。

タイポ耐性（"csvv" を弾く等）は**ライブラリで拘束せず、skill の候補提示で誘導**する。

## Consequences

### Positive

- 新しい source 種別・knowledge category を **YAML だけ**で追加でき、ライブラリ改変+リリースが不要。
- `extra="allow"` によりドメイン固有メタをモデル改変なしに持ち回れる。
- ライブラリはさらに薄くなる（enum coercion の分岐が消える）。
- `KNOWN_*` 定数で「慣習値」の発見可能性は維持される。

### Negative

- 検証が弱まる: "csvv" のようなタイポや無意味な category が受理される（非空チェックのみ）。
  緩和策は skill 側の候補提示に依存する。
- 公開契約の破壊的変更: `SourceType` / `KnowledgeCategory` を import していたコードは壊れる
  （本リポジトリ内は Story 5c.1 で `KNOWN_*` 定数へ移行済み）。

## Alternatives considered

- **B: reserved+free（validator でハイブリッド）** — 未知値を warn しつつ通す。弾かない以上
  タイポは結局通り、validator の分岐が増える割にメリットが薄い。却下。
- **C: `ColumnSchema` の `extra="allow"` のみ、enum 据え置き** — 安全だが source type /
  category の硬さという本丸が残り「柔軟化」を達成できない。却下。
- **enum 拡張のみ** — 値を足すたびリリースが要る。缶を蹴るだけ。却下。

## Related

- Epic: `docs/design/epic-05c-catalog-flexibility.md`
- Stories: 5c.1（モデル緩和）/ 5c.2（skill 汎用化・docs）
- PRs: E5c
- Supersedes: なし（[ADR-0001](0001-drop-mcp-server-embed-validation.md) のロードマップ E5 最終段）
