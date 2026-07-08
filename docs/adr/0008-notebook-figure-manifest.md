# ADR-0008: notebook 図マニフェスト（verdict.figures[]）— 図の真実は生産者が持つ

## Status

Accepted

## Context

Epic 10（`/analysis-report`、issue #47）で、分析成果を配布可能な APA 風 Markdown レポートに畳む
スキルを新設する。要求の一つに「各図に**軸の説明（Axes）**と**図の読み方（How to read）**を必ず添える」
がある（配布先が図を誤読しないため）。

ここで「図のキャプション（軸・読み方）を**誰が持つか**」が設計の要石になった。現状:

- notebook の 8-cell 契約（[notebook-contract.md](../../skills/analysis-notebook/references/notebook-contract.md)）
  の viz cell(5) は `plt.gcf()` を返すだけで **PNG を保存していない**。図は `.html` 内に埋まる。
- 機械可読な副作用は verdict cell(6) が書く `.insight/notebooks/{id}_verdict.json`
  （`conclusion` / `evidence_summary` / `open_questions`）で、**図のメタ情報を持たない**。
- `design.chart[]` は分析設計時の *計画*（intent / type / x / y / description）であり、実際に
  レンダリングされた図とはズレうる。

report 側が `design.chart[]` からキャプションを再構成すると、「計画の説明」を「実物の図」に貼ることに
なり、**誤読を防ぐどころか誤読を作り込む**。軸ラベル（xlabel/ylabel）や実際の描画内容の真実を持つのは、
図をレンダリングする notebook（生産者）だけである。

## Decision

**図の真実（PNG + そのキャプション）は生産者である `/analysis-notebook` が持ち、消費者である
`/analysis-report` はそれを読むだけにする。** 具体的には notebook 8-cell 契約を拡張する:

- viz cell(5) は図を `.insight/notebooks/{id}_fig{NN:02d}.png` に保存する（連番、複数可）。
- verdict cell(6) は `verdict.json` に `figures[]` 配列を追記する:

  ```json
  {
    "conclusion": "...",
    "evidence_summary": ["..."],
    "open_questions": ["..."],
    "figures": [
      {
        "file": "FP-H01_fig01.png",
        "title": "施策前後の売上推移",
        "axes": "横軸=年月, 縦軸=売上(円)",
        "how_to_read": "施策投入月の前後で水準の段差に注目。段差=処置効果"
      }
    ]
  }
  ```

新規の副作用ファイルは作らず、**既存の verdict.json を enrich する**（機械可読な副作用を1ファイルに保つ）。
report は `figures[].file` を読むため、PNG 命名規約を report 側が知る必要はない。figures[] が無い旧分析に
対しては report が graceful degrade（図ブロック省略 + 一行注記）する。

これは公開契約（8-cell 責務 + verdict.json スキーマ）への変更であり、`/analysis-notebook` と
`/analysis-report` の双方が依存するため、Epic の Design Doc `## Decisions` ではなく ADR として記録する
（CLAUDE.md §5）。

## Consequences

### Positive

- 図の軸・読み方が生産時（実際の描画コンテキスト）に確定するため、誤読リスクを構造的に排除できる。
- 生産者/消費者の分離が保たれる（コンパイラがバイナリ + デバッグシンボルを吐き、デバッガがシンボルを
  読むのと同じ構図）。report は notebook を再実行しない冪等・低リスクな純消費者に保てる。
- 副作用は verdict.json 1ファイルのまま。読み側の分岐が増えない。

### Negative

- 8-cell 契約が太る（cell5 に savefig、cell6 に figures[] 記録）。公開契約変更なので
  `notebook-contract.md` とサンプル `tests/integration/fixtures/sample_notebook.py` の更新を伴う。
- 契約変更前に実行された旧分析には figures[] / PNG が無く、レポートに図を載せるには notebook 再実行が
  必要（graceful degrade で吸収）。

## Alternatives considered

- **report が design.chart[] + verdict から LLM 生成** — notebook 契約を触らずに済むが、計画(chart)と
  実物の図がズレると誤読を作り込む。要求（誤読防止）と正面衝突するため却下。
- **notebook が別 JSON（`{id}_figures.json`）に分離** — verdict を汚さないが、機械可読な副作用ファイルが
  2つに増え、消費側の分岐が増える。verdict enrich の方が単純なため却下。

## Related

- Epic: #47 / `docs/design/epic-10-analysis-report.md`
- Stories: 10.1（notebook 契約拡張）, 10.2（report skill）
- Affected: `skills/analysis-notebook/references/notebook-contract.md`（8-cell 契約 + verdict schema）、
  `skills/analysis-report/`（消費者）、`tests/integration/fixtures/sample_notebook.py`
