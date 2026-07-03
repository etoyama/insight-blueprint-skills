# Architecture Decision Records

cross-epic な設計判断・長期制約・`docs/ARCHITECTURE.md` への変更を記録する。
新規は [.claude/rules/adr-template.md](../../.claude/rules/adr-template.md) をコピーし、
確定後この索引に追記する。1ファイル1決定、`NNNN` は4桁ゼロ詰め連番。

| ADR | Title | Status |
|---|---|---|
| [0001](0001-drop-mcp-server-embed-validation.md) | MCPサーバを廃止し、設計書検証を埋め込みライブラリ＋pre-write hook に移す | Accepted |
| [0002](0002-trunk-based-epic-stacking.md) | `dev` を廃止しトランクベース（main）+ stacked Epic に移行する | Accepted |
| [0003](0003-skill-yaml-io-via-design-io.md) | skill の設計書 I/O を design_io ヘルパに集約する | Accepted |
| [0004](0004-open-string-catalog-taxonomy.md) | catalog の taxonomy を open string にする | Accepted |
| [0005](0005-selective-autonomous-chaining.md) | selective autonomous chaining（/analysis-auto driver） | Accepted |
