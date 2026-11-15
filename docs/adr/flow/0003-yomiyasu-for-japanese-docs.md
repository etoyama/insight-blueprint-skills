# FLOW-0003: 日本語の文書を yomiyasu で推敲する

## Status

Accepted（導入方法の決定は [FLOW-0004](0004-decision-analysis-plugin.md) で置き換えた）

## Context

日本語の文章を整えるルールがなかった。CLAUDE.md の `## 8. Language` は見出しだけだった。
AI が書いた文書には、日常の日本語から外れた表現が残っていた。配布元の文書が読みにくいと、
配布先の AI もその文体をまねる。

[yomiyasu](https://github.com/nanaism/yomiyasu) は、AI が書いた日本語の不自然な比喩・主述の
曖昧さ・過剰な装飾を、意味を保ったまま直すスキルである（MIT ライセンス）。自動では起動せず、
名前を指定したときだけ使われる。作者の検証では、時間と費用が約4倍になった。

## Decision

- 推敲の対象は `docs/` 配下の文書、issue 本文、PR 説明とする。コード、コードコメント、
  mermaid の中身は対象外。
- 推敲は DesignDoc 初版を出す前と、Epic PR を開く前に行う。一文ごとの編集では行わない。
- CLAUDE.md の `## 8. Language` に、`yomiyasu:yomiyasu` で推敲することと、文書の種類の対応を書く。
- 節名は英語のままにする。日本語でも日常的に使われる語や専門用語も英語でよい。推敲でも訳さない。
- `docs/UBIQUITOUS_LANGUAGE.md` の「用語」を yomiyasu の `.yomiyasu-words/allow.txt` に、
  「使わない言い換え」を `flag.txt` に書き出す。正本は UBIQUITOUS_LANGUAGE.md だけで、
  `.yomiyasu-words/` は生成物として扱う。
- yomiyasu は外部のプラグインなので、`scripts/bootstrap.sh` で導入を案内する。
- `yomiyasu_lint.py` などの機械的な検査を CI に入れるかは、運用してから決める。

## Consequences

### Positive

- 文書の読みやすさを、人間の指示なしで一定に保てる。
- 推敲でドメイン用語が言い換えられるのを防げる。

### Negative

- 推敲のたびに時間と費用がかかる。
- 外部プラグインに依存する。導入していない環境では推敲されない。
- yomiyasu は事実誤認や情報の欠落を直さない。内容のレビューは別に要る。

## Alternatives considered

- 推敲ルールを CLAUDE.md に自前で書く: 単語を禁止するだけでは、別の曖昧な表現に置き換わる。
  yomiyasu は文の構造から直す。
- すべての編集で推敲する: かかる時間と費用に見合わない。

## Related

- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)
- [ALGO ARTIS: yomiyasu の解説記事（Zenn）](https://zenn.dev/algoartis/articles/0b1c731881b25c)
- 関連: [FLOW-0002](0002-ubiquitous-language.md)
