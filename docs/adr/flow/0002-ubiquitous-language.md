# FLOW-0002: ユビキタス言語の正本を置き、コード・テスト・図をその語で書く

## Status

Accepted

## Context

用語の表は Epic ごとの DesignDoc の `## Glossary` にしかなかった。この表は略語の説明で止まり、
別の Epic や次の Claude セッションからは参照されなかった。用語とクラス名を対応づける場所もなかった。

AI はセッションをまたぐと前回の言葉選びを覚えていない。そのため同じ概念が別の言葉で書かれ、
人間は統一を指示するコストを払っていた。DesignDoc の図も構成図とシーケンス図だけで、
ドメインの概念と関係を描く図がなかった。

## Decision

- `docs/UBIQUITOUS_LANGUAGE.md` を新設し、用語の正本にする。冒頭にコンテキスト名と目的を書き、
  本体に「用語・コード上の名前・定義・使わない言い換え・初出」の表を置く。
- クラス名・型名・テスト名と、図の登場人物・ラベルは、この表の語だけを使う。
- AI は文書やコードを書く前にこのファイルを読む。表にない概念を使うときは、同じ PR で表に足す。
  用語の改名や意味の変更は ADR を伴う。
- DesignDoc の `## Glossary` は `## Ubiquitous Language` に改め、その Epic で追加・変更した語への
  リンクだけを置く。
- DesignDoc の `## Data Model` を `## Domain Model`（mermaid `classDiagram`）に置き換え、
  初版の必須項目にする。Story の実装中に追加・修正してもよいが、PR 説明に変更を書き、
  人間の承認を得る。状態遷移図とドメインイベント一覧は、必要なときだけ書く。
- ユビキタス言語は境界づけられたコンテキストごとに1つ持つ。最初は1ファイルで始め、次の兆候が
  出たら ADR を書いて `docs/domain/<コンテキスト>/UBIQUITOUS_LANGUAGE.md` に分ける。
  - 同じ語に2つ目の定義が要る。
  - 利用者のグループによって、同じものを指す言葉が変わる。
  - 同じ概念でも、グループごとに必要な属性や振る舞いが違う。
- コンテキストを分けたら、`docs/ARCHITECTURE.md` にコンテキストマップを描く。関係は
  ddd-crew の Context Mapping のパターン名で書く。

## Consequences

### Positive

- セッションや Epic をまたいでも、語の選び方がリポジトリ内の1ファイルで決まる。
- 図の箱・用語・クラス名・テスト名が一致し、人間と AI が同じものを指して話せる。

### Negative

- 表を保守する手間が増える。表と実態がずれると、かえって混乱を招く。
- 初版の DesignDoc でドメインモデル図を描く分、初版が重くなる。

## Alternatives considered

- Epic ごとの Glossary を続ける: Epic やセッションをまたぐと語が揺れる問題が残る。
- リポジトリ全体で語の意味を1つに統一する: コンテキストごとに意味が違う語を無理にまとめると、
  モデルが実態と合わなくなる。
- 用語集（GLOSSARY.md）という名前にする: 辞書として扱われ、コードや図に反映されにくい。

## Related

- [Martin Fowler: BoundedContext](https://martinfowler.com/bliki/BoundedContext.html)
- [Martin Fowler: UbiquitousLanguage](https://martinfowler.com/bliki/UbiquitousLanguage.html)
- [ddd-crew/bounded-context-canvas](https://github.com/ddd-crew/bounded-context-canvas)
- [ddd-crew/context-mapping](https://github.com/ddd-crew/context-mapping)
- 関連: [FLOW-0001](0001-designdoc-owns-requirements.md)、[FLOW-0003](0003-yomiyasu-for-japanese-docs.md)
