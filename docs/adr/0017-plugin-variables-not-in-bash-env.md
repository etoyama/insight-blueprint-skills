# ADR-0017: plugin の変数は skill の本文で使い、bin ラッパーは自分の場所から plugin のルートを求める

## Status

Accepted

## Context

[ADR-0006](0006-plugin-execution-model.md) は、plugin のパスを実行時の変数で解決すると決めた。
`bin/` のラッパーは `cd "${CLAUDE_PLUGIN_ROOT}"` し、`CLAUDE_PLUGIN_DATA` があれば venv をそこに置く。
テスト（`tests/integration/test_bin_wrappers.py`）は「`CLAUDE_PLUGIN_ROOT` が無ければ落ちる」を仕様にしていた。

2026-11-18 に、Epic 12 をリリースできるか判断する材料をそろえるため、plugin として入れたセッションで skill を起動した。
そこで `design_io` が `CLAUDE_PLUGIN_ROOT is not set` で落ちた。`bin/` は v0.8.0 から変わっていない。
Epic 09 から壊れていたが、これまでの確認は変数を手で渡すか、SKILL.md をなぞるものだったので見つからなかった。
直したのは [PR #78](https://github.com/etoyama/insight-blueprint-skills/pull/78) である。

比較の前提にした事実と、確かめた方法は次のとおり。どれも Claude Code 2.1.227 で、`claude -p --plugin-dir <checkout>` で起動したセッションで確かめた。

- Bash ツールの環境に `CLAUDE_PLUGIN_ROOT`・`CLAUDE_PLUGIN_DATA`・`CLAUDE_PROJECT_DIR` は無い。
  plugin の `bin/` は PATH に載っている（Bash ツールで `printenv` を実行した）。
- SKILL.md の本文に書いた `${CLAUDE_PLUGIN_ROOT}` は、plugin のルートの絶対パスに置き換わってモデルに届く
  （`/analysis-notebook` を起動したセッションに、`uv run --project` の行を引用させた）。
- ADR-0006 は [ADR-0009](0009-adopt-repo-template-flow.md) で旧形式のまま凍結されていて、本文を書き換えられない。

確かめていないこと: marketplace から入れた plugin でも同じか。`references/` の下のファイルに書いた変数も置き換わるか。
`hooks/hooks.json` の変数が実行時に展開されるか。

## Problem

- 課題1: 分析者が plugin を入れても、`design_io`・`catalog_io`・`premortem` が落ちる。
  分析設計の作成・状態遷移・catalog の読み書き・premortem が、どれも動かない。
- 課題2: ADR-0006 には、bin ラッパーが変数に頼ると書いてある。これを読んで plugin の変数に頼るコードを書くと、また同じ穴に落ちる。
  ADR-0006 は書き換えられないので、ADR-0006 を読んだ人が今の決まりに辿り着けない。

扱わない範囲: `CLAUDE_PLUGIN_DATA` が無いときの venv の置き場。`references/` の下のファイルが変数をどう扱うかの確認と修正。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | Bash ツールから呼んだラッパーが、変数を渡さなくても動く | Must | - | - | 課題1 |
| M2 | ラッパーが動くのは、ラッパー自身が置かれた plugin の環境だけである | Must | - | - | ADR-0006（ラッパーは plugin 自身の uv 環境で動く） |
| W1 | plugin の変数がどこで効き、どこで効かないかを、次に書く人が読める | Want | 解決 | 高（人間が「ADR を足して」と決めた） | 課題2 |
| W2 | 変数がある環境では、今までの動きを変えない | Want | 費用 | 中（Claude の推測） | ADR-0006 |

案は次の3つ。

- A. ラッパーは `CLAUDE_PLUGIN_ROOT` があればそこへ、無ければ自身の場所（`bin/` の1つ上）へ移動する。
- B. ラッパーは変数を見ず、いつも自身の場所から plugin のルートを求める。
- 何もしない: 変数に頼ったままにする。

| Must | A. 変数を優先し、無ければ自身の場所 | B. いつも自身の場所 | 何もしない |
|---|---|---|---|
| M1 | 満たす | 満たす | 満たさない（落ちる） |
| M2 | 満たす | 満たす | 満たす |

| Want | A. 変数を優先し、無ければ自身の場所 | B. いつも自身の場所 |
|---|---|---|
| W1 | 変数が効くのは skill の本文、効かないのは Bash ツールの環境、と書ける | A と同じ |
| W2 | 変数がある環境（手で渡したとき、将来ホストが渡すようになったとき）では今までと同じ | 変数があっても無視するので、変数と自身の場所が違う環境では動きが変わる |

- 差がつく基準: W2。A が勝つ。
- 感度: 変数と自身の場所が食い違う環境が実際に無いと分かれば、W2 は効かなくなり、短い B でもよい。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| A | 変数が別の plugin を指していると、そちらで動く | 変数はホストが設定する。別の値が入るのは、利用者が手で渡したときに限られる見込みである |
| B | ホストが変数で別の場所を指したとき、それに従わない | 今その例は無い |
| 何もしない | plugin を入れた分析者の手元で核が動かない | なし |

## Decision

A を採る。決め手は W2。ADR-0006 の bin ラッパーの決まりを、次のとおり改める。

- bin ラッパーは、`CLAUDE_PLUGIN_ROOT` があればそこへ、無ければラッパー自身の場所の1つ上へ移動し、plugin の uv 環境で動く。
- `CLAUDE_PROJECT_DIR` が無いときは cwd を利用者のプロジェクトとみなす（ADR-0006 のままで、変えない）。
  `.insight` の base の検査も変えない。
- plugin の変数（`${CLAUDE_PLUGIN_ROOT}` など）を使ってよいのは、ホストが置き換える場所だけである。
  置き換わると確かめた場所は、SKILL.md の本文しかない。変数は Bash ツールの環境に来ないので、`bin/` のスクリプトなど Bash から動くコードは変数に頼らない。
- ADR-0006 は凍結のまま変えない。bin ラッパーの解決順はこの ADR が正本になる。
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) のパス解決機構に、この ADR を指す1行を足す。

## Consequences

### Positive

- plugin を入れた分析者の手元で、`design_io`・`catalog_io`・`premortem` が変数なしで動く。
- 次に Bash から動くコードを書く人は、ARCHITECTURE とこの ADR から「変数は Bash ツールの環境に来ない」と読める。

### Negative

- `CLAUDE_PLUGIN_DATA` も Bash ツールの環境に来ないので、ADR-0006 の「更新の間で venv を保つ」は効いていない。
  venv は plugin のルートの `.venv` にでき、plugin を更新するたびに作り直される。この ADR では塞がない。
- `skills/analysis-notebook/references/notebook-contract.md` は、コマンドの中に `${CLAUDE_PLUGIN_ROOT}` を書いている。
  `references/` の下でも置き換わるかは確かめていない。置き換わらなければ、そのコマンドは notebook の経路で落ちる。
- 確かめたのは `--plugin-dir` で入れた場合だけである。marketplace から入れた場合は確かめていない。

## Alternatives considered

- **ラッパーの中で plugin のルートを探す（`plugin.json` を上へ辿る）** — `bin/` が plugin のルートの直下にあることは配布物の構成で決まっている。探す処理は要らない。

## Related

- Epic: [epic-09](../design/epic-09-installable-plugin.md)（ラッパーを入れた Epic）
- PRs: [#78](https://github.com/etoyama/insight-blueprint-skills/pull/78)
- 改める ADR: [ADR-0006](0006-plugin-execution-model.md)（凍結のまま。bin ラッパーの解決順だけを改める）
