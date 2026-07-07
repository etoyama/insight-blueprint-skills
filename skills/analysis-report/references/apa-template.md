# APA-style report template (canonical contract)

`/analysis-report` assembles this from a concluded analysis. Headings are **English,
APA-standard**; the narrative body is the user's language (usually Japanese). Output goes to
`.insight/reports/{id}.md`.

This is a lightweight APA: IMRaD structure + APA section headings. It deliberately does **not**
adopt strict APA apparatus (running head, in-text `(Author, Year)` citations, hanging-indent
reference list) — an EDA analysis has essentially no cited literature, so that apparatus would
only produce empty scaffolding (this lightweight-vs-strict-APA scope decision lives in
[docs/design/epic-10-analysis-report.md](../../../docs/design/epic-10-analysis-report.md) Scope;
the figure-manifest contract is [ADR-0008](../../../docs/adr/0008-notebook-figure-manifest.md)).

## Heading skeleton

```
# {title}

## Abstract
{結論を数語〜数文で。conclude イベント + verdict.conclusion から}

## Introduction
{hypothesis_statement と hypothesis_background。問いと背景}

## Method
{methodology.method（package / reason / steps）+ metrics + explanatory 変数と役割}

## Results
{journal の observe/evidence の叙述 + verdict.metrics の数値表 + 図（下記フォーマット）}

## Discussion

### Limitations
{conclude の限界・前提の制約}

### Future Directions
{journal の open question + 次工程}

## References
{referenced_knowledge があれば列挙。無ければこのセクションごと省略}
```

## Input → section mapping

| Section | Input | Source |
|---|---|---|
| Abstract | `conclude` event, `verdict.conclusion` | journal / verdict.json |
| Introduction | `hypothesis_statement`, `hypothesis_background` | `design_io get` |
| Method | `methodology`, `metrics`, `explanatory` | `design_io get` |
| Results (narrative) | `observe`, `evidence` (with `metadata.direction`) | journal |
| Results (table) | `verdict.metrics` | verdict.json |
| Results (figures) | `verdict.figures[]` + the PNG files | verdict.json + `.insight/notebooks/` |
| Limitations / Future Directions | `conclude` limits, open `question`s | journal |
| References | `referenced_knowledge` | `design_io get` |

## Figure presentation format (mandatory captions)

Each figure embeds the PNG **and** its axis + reading captions, taken **verbatim** from the
notebook's `verdict.figures[]` manifest (the producer owns the figure's truth; do not
reconstruct captions from `design.chart[]`). Both captions are required and non-empty.

```markdown
**Figure {N}.** {figures[N].title}

- **Axes（軸の説明）**: {figures[N].axes}
- **How to read（図の読み方）**: {figures[N].how_to_read}

![Figure {N}](../notebooks/{figures[N].file})
```

The image path is relative to `.insight/reports/{id}.md`, so figures under
`.insight/notebooks/` are referenced as `../notebooks/{file}`. The report never copies or
moves the PNG.

**Safety when transcribing verbatim**:
- `figures[].file` must be a bare basename. Skip any entry whose `file` contains `/`, `\`, `..`,
  or is absolute (treat as graceful-degrade omission) — this is a distributable artifact and a
  traversal path would leak the local filesystem layout.
- Skip an entry whose PNG is missing on disk rather than embedding a broken image link.
- Treat `title` / `axes` / `how_to_read` as **plain text**: do not let embedded markdown image
  or HTML in a caption ride into the distributed report (source data can reach these fields).

## Graceful degrade (no figures)

If `verdict.json` is missing, has no `figures` key, or `figures == []` (analysis predates the
figure contract, or the notebook produced no plot), omit the figure blocks entirely and add a
single line under Results:

```markdown
> 図はこのレポートには含まれていない（notebook が図を生成していない）。図を載せるには
> /analysis-notebook で再実行する。
```

The report still assembles from text + tables — a missing optional artifact never blocks it.
