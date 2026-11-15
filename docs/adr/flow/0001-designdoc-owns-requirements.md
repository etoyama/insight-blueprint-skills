# FLOW-0001: 要求と背景の正本を DesignDoc に置く

## Status

Accepted

## Context

これまでのフローでは、Epic の目的・背景・AC を Epic issue に書き、DesignDoc には AC を
転記するだけだった。Story issue には「やること」と AC だけを書き、誰の何のための Story かを
書く欄がなかった。

その結果、DesignDoc は「どう作るか」から始まり、読んだだけでは「なぜ作るのか」が分からなかった。
人間は DesignDoc のレビューのたびに、背景とユーザーストーリーを書き直すよう AI に指示していた。
また AC が issue と DesignDoc の2箇所にあり、WORKFLOW §2 の「同じ情報を2箇所に正本として
書かない」ルールに反していた。

## Decision

- 背景・ユーザーストーリー・AC の正本は DesignDoc に置く。
- DesignDoc テンプレートの先頭に `## Background`・`## User Stories`・`## Stories` を置く。
  AC は独立した節にせず、ユーザーストーリーの下に書く。
- Epic issue は1〜2行の要約と DesignDoc へのリンクだけを持つ。
- Story issue は対応するユーザーストーリー（DesignDoc の節）へのリンクを必須にする。
  AC は DesignDoc に1回だけ書く。
- DesignDoc 初版の必須項目に Background と User Stories を加える。初版を出す前に、AI は
  「DesignDoc だけを読んだ人が、誰のどんな課題を解くのか説明できるか」を確かめる。

## Consequences

### Positive

- DesignDoc だけを読めば、要求から設計までをたどれる。
- レビューで背景を書き直させる指示が、初版のチェック項目に置き換わる。
- AC の正本が1箇所になる。

### Negative

- GitHub の issue 一覧だけでは、AC の中身が見えない。
- 既存の Epic issue にある背景と AC は、手で DesignDoc に移す必要がある。

## Alternatives considered

- issue を正本のままにし、DesignDoc に転記する: 2箇所を同期させ続けることになり、ずれる原因が残る。
- issue に背景をすべて残し、DesignDoc から参照する: DesignDoc だけで完結しないという問題が残る。

## Related

- Supersedes: なし
- 関連: [FLOW-0002](0002-ubiquitous-language.md)
