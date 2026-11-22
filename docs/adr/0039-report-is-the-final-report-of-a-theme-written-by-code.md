# ADR-0039: レポートは、テーマの最終報告として、コードが論点ツリーと分析設計の記録から書く

## Status

Accepted

## Context

[Epic 28](../design/epic-28-tree-entry-point.md) は、分析設計ごとの分析ノートをコードが生成するようにした（[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)）。
ADR-0036 は Markdown のレポートを分析ノートに一本化するかを範囲の外に置き、[#177](https://github.com/etoyama/insight-blueprint-skills/issues/177) に回した。
[Epic 29](../design/epic-29-theme-report-export.md) がそれを扱う。2026-11-23 に、DesignDoc 初版のセッションで人間と決めた。
途中で、合成シナリオ（公共図書館の予約本）の見本を Artifact と Claude Docs に出し、人間が見て確かめた。

比較の前提にした事実と、確かめた方法は次のとおり。

- 分析ノートは結論の後の節まで、journal と分析設計から書かれたとおりに埋まる。`/tree-upload` が、分析ノートを含む論点ツリーの HTML を1ファイルのまま Artifact に送る
  （ADR-0036、[ADR-0037](0037-tree-upload-sends-the-design-notes.md)、`skills/_shared/design_note.py` を読んだ）。
- 今のレポートは、モデルが `apa-template.md` に従って、分析設計1つの記録から組み立てる。`report_check` が見るのは効く記法だけで、数が入力にあるかは見ない（`skills/analysis-report/SKILL.md`、ADR-0036 の Context）。
- レポートにあって分析ノートに無いのは、モデルが書く文（Abstract の要約、Implications、Recommendation の勧める文、Results の語り直し、限界の抜き出し）と、References、行数の表である（`apa-template.md` と `design_note.py` を照らした）。
- [docs/PRD.md](../PRD.md) は、レポートが分析設計1つを単位にしていて、同じテーマの複数の分析設計を束ねて見る場所が無いと書いている。
- 現時点の答えは、テーマの振り返りが論点ごとに書く。文ごとに種類と、引用する journal の出来事を持つ。ツリーの検査が引用先の実在と、文の数が引用先の本文にあることを確かめる
  （[ADR-0025](0025-cited-answers-checked-after-writing.md)、`skills/analysis-reflection/SKILL.md` の T2 から T4 を読んだ）。
- Artifact にはコメントの機能がある。Claude Docs にしか無いのは、Word・PDF への書き出しと、Doc の上での手直しである（ホストのツールの説明を読んだ）。
- Claude Docs のコネクタが本文として受けるのは Markdown かブロックで、HTML は受けない（コネクタの guide を読んだ）。plugin の基本の env に、Markdown を HTML にするライブラリは無い。
- 使い捨てのコードで、合成シナリオの論点ツリー・分析設計・journal・verdict から Markdown を書き、Claude Docs に送った。表、太字、箇条書きはそのまま載り、図は asset upload で載った（2026-11-23 に実行した）。

## Problem

- 課題1: 読む人にとって、分析ノートとレポートは同じ分析設計の同じ文書である。2つあると、どちらを読めばよいか迷う（ADR-0036 の課題6、人間の発言）。
- 課題2: 同じ記録から、コードとモデルの2本の経路で文書を作っている。中身がずれ、モデルの経路には記録に無い数や文が混ざりうる。
- 課題3: 顧客や一般の読者に出す最終報告が答えるのは、大本の問いである。分析設計1つのレポートは根の問いへの答えを持たない。
- 課題4: 顧客は開発の用語（根の問い、journal の出来事、分析設計）を知らない。そのまま出すと通じない（人間の発言、レポートの見本へのコメント）。

扱わない範囲: レポートを Claude Docs へ送る skill と、古いレポート周りの消し方（[ADR-0040](0040-report-export-sends-the-report-to-claude-docs.md)）。勧め（何をすべきか）を記録に持つこと。
分析ノートに含意の文章を足すか（Epic 29 の Decision `the-note-gets-no-implication`）。図を動かせる形で出すこと（[#175](https://github.com/etoyama/insight-blueprint-skills/issues/175)）。

## Decision Analysis

配る物の行き先。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | コネクタが無い環境でも、配る物が手元に残る | Must | - | - | [ADR-0015](0015-host-connectors-for-optional-features.md) |
| W1 | 読む面が1つである | Want | 解決 | 高（人間） | 課題1 |
| W2 | 読み手が Word・PDF で受け取れる | Want | 解決 | 高（人間。最終報告のときに限る） | 課題3 |
| W3 | 分析者が配る前に文章を手直しできる | Want | 解決 | 中（Claude の推測） | [Epic 10](../design/epic-10-analysis-report.md) の目標 |
| W4 | 保守する形と検査の数 | Want | 費用 | 高（人間） | 課題2、YAGNI |

| Must | P1: Artifact だけ | P2: Artifact と Claude Docs | P3: Artifact と手元の Markdown | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす | 満たす | 満たす |

| Want | P1 | P2 | P3 |
|---|---|---|---|
| W1 | 1つになる。 | 詰める間は1つ。最終報告のときだけ Doc が増える。 | 2つ残る。Markdown は読み手に渡す手段が手作業に戻る。 |
| W2 | 受け取れない。 | 受け取れる。 | Markdown を自分で変換する。 |
| W3 | できない。 | Doc の上でできる。 | Markdown でできる。 |
| W4 | 形と検査が1つ。 | Docs に送る物の形が残る。 | Markdown の形と `report_check` が残る。 |

- 差がつく基準: W1 と W4 は P1、W2 と W3 は P2 が勝つ。
- 感度: W2 が要らなければ P1 になる。人間は、詰める間は P1、最終報告のときだけ Docs へ export すると答えた。

レポートの本文を誰が何から作るか。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| W5 | 分析ノートとレポートの中身が食い違わない | Want | 解決 | 高（人間） | 課題1、課題2 |
| W6 | 記録に無い数や文が混ざらない | Want | 解決 | 高（人間） | 課題2、ADR-0036 の W2 |
| W7 | レポートが、細かい手直しで顧客に出せる | Want | 解決 | 中（Claude の推測） | 人間の発言「文言の細かい直しは Docs の上で」 |
| W4 | 保守する形と検査の量 | Want | 費用 | 高（人間） | YAGNI |

| Want | R1: モデルがテンプレートに従って組み立てる | R2: コードが記録から Markdown を書く | R3: コードが書いた物を、モデルが全文書き直す |
|---|---|---|---|
| W5 | 経路が2本のまま。文面はずれる。 | 同じ記録を同じ読み方で読むので、作りとして食い違わない。 | 土台は同じだが、書き直しで離れる。 |
| W6 | 混ざりうる。文の決まり頼み。 | 混ざらない。コードは書かれた値を並べるだけ。 | 混ざりうる。検査が全文に要る。 |
| W7 | 一番読みやすい。 | 硬い。記録の写しが並ぶ。 | 読みやすい。 |
| W4 | テンプレート、`report_check`、データ由来の文の決まりが残る。 | Markdown を書く関数とテストが増え、テンプレートとモデルの手順が消える。 | R2 の全部に、書き直しの決まりと検査が足される。 |

- 差がつく基準: W5・W6・W4 は R2、W7 は R1 と R3 が勝つ。
- 感度: 全文が読み物でないと顧客に出せないなら R3 になる。

レポートの単位。

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| W8 | 顧客が受け取る物が、決めたいことへの答えとして1つにまとまっている | Want | 解決 | 高（人間） | 課題3 |
| W5 | 分析ノートと中身が食い違わない | Want | 解決 | 高（人間） | 課題1 |
| W9 | Epic に足す設計と実装の量 | Want | 費用 | 高（人間） | YAGNI |

| Want | U1: 分析設計ごと | U2: テーマごと | U3: 両方 |
|---|---|---|---|
| W8 | 分析設計1つの仮説への答えにとどまる。 | 根の問いへの答えとしてまとまる。 | 場面で選べる。 |
| W5 | 食い違わない。 | 分析設計の部分は食い違わない。ツリーの部分は、論点ツリーの表示と同じ記録から書く。 | U2 と同じ。 |
| W9 | 小さい。 | テーマ単位の文書の形を新しく決める。 | 一番大きい。 |

- 差がつく基準: W8 は U2 と U3、W9 は U1 が勝つ。
- 感度: W8 を中に下げると U1 になる。人間は、分析設計単位の出力は分析ノートで足りるとして U2 を選び、U1 を作らないと決めた。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| P1 | Word・PDF を求める読み手に渡せない | 最終報告のときだけ Docs へ export する（P2 に近づく） |
| P2 | Docs に送る物が、別の文書として育つ | 送る物をコードが記録から書き、モデルに書かせない（R2） |
| P3 | 読み手に渡す手段の無い Markdown が残る | 抑えにくい |
| R1 | 一本化が名前だけになり、レポートと分析ノートが別に育つ | 抑えにくい |
| R2 | 記録の写しだけでは、Docs での手直しが大きくなる。エスケープを誤り、データ由来の文が記法として効く | 見本で手直しの量を確かめる。エスケープのテストを書く（ADR-0040） |
| R3 | 検査が全文に要り、Epic が倍になる | 範囲を絞る（R2 に近づく） |
| U1 | 顧客に出す物を、毎回 Docs の上で束ね直す | テーマ単位を後で足す |
| U2 | 現時点の答えが薄いテーマでは、レポートも薄い。勧めの文が無い | 根の問いに答えが無ければ書かない。勧めは Docs の上で書く |
| U3 | 2つの形を同時に保守する | U2 だけにする |
| 何もしない | 課題1 から課題4 が残る | なし |

## Decision

行き先は P2 を最終報告に限って採り、本文は R2、単位は U2 を採る（人間の判断、2026-11-23）。決め手は行き先では W1 と W2、本文では W5 と W6、単位では W8。

- 調査や検証を詰める間に読む面は、論点ツリーと分析ノートの1つである。中間報告には論点ツリーの HTML（手元のファイルと Artifact）をそのまま使う。
- レポートはテーマの最終報告である。根の問いへの答えを、根拠と一緒に1つの文書にする。分析設計単位のレポートは作らない。
- レポートは、コードが論点ツリー・分析設計・journal・verdict から Markdown として書く。値は書かれたとおりに出し、計算しない。モデルが書く文は載せない。
  同じ入力からは同じ Markdown ができる。置き場は `.insight/reports/{theme_id}.md` である。
- レポートは APA の骨組みに従う。見出しは英語で、Abstract、Introduction、Method、Results、Discussion（Limitations と Future Directions）、Appendix の順に並ぶ。
  Abstract は到達点と、根の問いへの現時点の答えである。Results は論点ごとの現時点の答えと、根拠となる分析である。
- レポートに載せる分析設計の中身は、仮説、手法、データソースの名前・種類・説明、結論、指標の値、図、仮説に反する証拠である。分析コード、journal のすべての出来事、lineage は載せない。分析ノートで読める。
- レポートは用語表の語をそのまま出さず、読み手向けの言葉に言い換える。根の問いは「主題」、journal の出来事は「記録」、分析設計は「分析」と書く。言い換えの対応はコードの1か所に持つ。
  文書・コード・テスト・図が用語表の語だけを使う決まり（[FLOW-0002](flow/0002-ubiquitous-language.md)）は、顧客に出すレポートの文面には当てはめない。
- レポートを書かない条件は、Epic 29 の Decision `the-report-stops-on-two-conditions` に置く。勧めの節を作らないことは、Decision `the-report-has-no-recommendation-section` に置く。
- 用語「レポート」はテーマの最終報告を指す語に改める。今の定義（結論の出た分析を配布用にまとめた APA 風の Markdown）は、分析設計1つを単位にしていた。用語表は実装の Story で直す。
- ADR-0036 の Decision のうち、「Markdown のレポートと Claude Docs へのアップロードは、今のまま残す」と、分析ノートからレポートへ相対リンクを張ることは、この ADR で改める。分析ノートのほかの決まりは変えない。
- [docs/PRD.md](../PRD.md) の機能要件と成功基準、[docs/ARCHITECTURE.md](../ARCHITECTURE.md) の `.insight/` の構成は、実装の Story で直す。

## Consequences

### Positive

- 分析ノートとレポートが、同じ記録から同じ決まりで作られる。モデルが書く経路が無くなり、記録に無い数や文が混ざる口が無くなる。
- 顧客に出す最終報告が根の問いへの答えを持つ。答えの文はツリーの検査を通ったものだけである。
- 保守する形が減る。`apa-template.md` と、モデルが組み立てる手順が要らなくなる。

### Negative

- レポートは記録の写しで、読み物としては硬い。要約、含意、勧めの文は無い。分析者が Docs の上で書く。Docs で書いた文は記録に戻らず、export し直すと消える。
- レポートは、テーマの振り返りが書いた現時点の答えに依る。答えが薄いテーマではレポートも薄い。振り返りの後に journal が増えても、答えが古いことは見つけない。
- 分析設計単位のレポートが無くなる。論点ツリーの無いテーマではレポートを作れない（ADR-0040）。
- レポートの文面は用語表の語と違う語で書かれる。言い換えの対応を1か所に持たないと、文面と用語表がずれる。
- 表の形を分析ノート（HTML）とレポート（Markdown）の2つの出力に持つ。
- 文の後ろに添える出来事の id は、顧客には記号に見える。根拠へたどる手がかりとして残した。
- [Epic 10](../design/epic-10-analysis-report.md)・[Epic 12](../design/epic-12-decision-ready-report.md)・[Epic 14](../design/epic-14-report-template-gaps.md) の DesignDoc にあるレポートの形の記述は、この ADR で古くなる。凍結しているので直さない。
- PDF にしたときの見え方、図の多いテーマでの手間、分析設計の多いテーマで本文が引数として通る長さに収まるかは、確かめていない。

## Alternatives considered

- **Markdown のレポートを HTML に変換して、分析ノートに取り込む** — Markdown を HTML にするライブラリが要り、モデルが書いた文が分析ノートに載る（ADR-0036 の U2）。
- **分析ノートの HTML をそのまま Claude Docs に送る** — コネクタが HTML を受けない。
- **モデルが、記録を読んで Doc の上に直接書く** — ファイルが残らず、R1 と同じ経路から検査だけが無くなる。

## Related

- Epic: [#177](https://github.com/etoyama/insight-blueprint-skills/issues/177)、[epic-29](../design/epic-29-theme-report-export.md)
- 関係する ADR: [ADR-0015](0015-host-connectors-for-optional-features.md)、[ADR-0019](0019-report-source-text-escaped-and-checked.md)、[ADR-0025](0025-cited-answers-checked-after-writing.md)、[ADR-0036](0036-design-note-is-a-generated-page-per-design.md)、[ADR-0037](0037-tree-upload-sends-the-design-notes.md)、[ADR-0040](0040-report-export-sends-the-report-to-claude-docs.md)
- Supersedes: なし（ADR-0036 の Decision の2点を改める）
