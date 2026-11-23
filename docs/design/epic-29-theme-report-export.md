# Epic 29: レポートを、テーマの最終報告として記録からコードで書き、Claude Docs へ export する

## Background

本書がこの Epic の要求と背景の正本（[FLOW-0001](../adr/flow/0001-designdoc-owns-requirements.md)）。
Epic issue（[#177](https://github.com/etoyama/insight-blueprint-skills/issues/177)）には要約と本書へのリンクだけを置く。

- 解く課題: 分析ノート（[Epic 28](epic-28-tree-entry-point.md)）ができた後も、レポートは別の文書として残っている（人間の課題認識、2026-11-22、issue #177）。
  - 課題1: 読む人にとって、分析ノートとレポートは同じ分析設計の同じ文書である。2つあると、どちらを読めばよいか迷う（[ADR-0036](../adr/0036-design-note-is-a-generated-page-per-design.md) の課題6）。
  - 課題2: 同じ記録から、分析ノートはコードが作り、レポートはモデルが作る。作る経路が2本あり、中身がずれる。モデルの経路には、記録に無い数や文が混ざりうる。`report_check` が見るのは記法だけである。
  - 課題3: 顧客や一般の読者に出す最終報告が答えるのは、大本の問いである。今のレポートは分析設計1つが単位で、根の問いへの答えを持たない。
  - 課題4: `/analysis-auto` は、結論の出た分析設計ごとにレポートを書き、アップロードを始める。報告できる品質かを分析者が判断する前に始まる。
- PRD の要件: [docs/PRD.md](../PRD.md) の機能要件のうち、レポートと Claude Docs の2項目。到達点（業務では顧客が決めたいことを決められるところまで、研究では想定読者が主張を吟味できるところまで）にもかかわる。
- 既存手段が不十分な理由: `/analysis-report`（[Epic 10](epic-10-analysis-report.md)、[Epic 12](epic-12-decision-ready-report.md)）は、分析設計1つをモデルが APA 風の Markdown に組み立てる。
  PRD は「レポートは分析設計1つを単位にしており、同じテーマの複数の分析設計を束ねて見る場所が無い」と書いている。束ねる場所は論点ツリーにできたが、レポートは論点ツリーを読まない。

### 求める運用（人間、2026-11-23、DesignDoc 初版のセッション）

- 調査や検証を詰める間は、分析者だけで論点ツリーと分析ノートを読む。読む面はこの1つにする。
- 顧客への中間報告には論点ツリーと分析ノートの HTML（手元のファイルと Artifact）をそのまま使う。
- 報告できる品質だと分析者が判断したときに、Claude Docs へ export する。export に求めるのは、「大本の問いへの答えは何か」に答える最終報告のレポートである。
- 文言の細かい直しは Docs の上で行い、PDF にして顧客や一般の読者に届ける。
- 分析設計単位の出力は分析ノートで足りるので、分析設計単位の export は要らない。

### 前提にした事実（main の c2af3c6、2026-11-23）

- 分析ノートは結論の後の節まで記録から埋まる。`/tree-upload` が、分析ノートを含む論点ツリーの HTML を1ファイルのまま Artifact に送る（ADR-0036、[ADR-0037](../adr/0037-tree-upload-sends-the-design-notes.md)、`skills/_shared/design_note.py` を読んだ）。
- 現時点の答えは、テーマの振り返りが論点ごとに書く。文ごとに種類と、引用する journal の出来事を持つ。ツリーの検査が引用先の実在と、文に書いた数が引用先の本文にあることを確かめる
  （[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md)、`skills/analysis-reflection/SKILL.md` の T2 から T4 を読んだ）。
- Claude Docs のコネクタが本文として受けるのは Markdown かブロックで、HTML は受けない。本文はツール呼び出しの引数に載る（コネクタの guide を読んだ）。
- plugin の基本の env に、Markdown を HTML にするライブラリは無い（`bin/*` は extras なしの `uv run` で動く）。
- 古いレポートに依るものは次のとおり（`git ls-tree` と `git grep` で洗った）。
  `skills/analysis-report/`、`skills/report-upload/`、`skills/_shared/report_check.py`、`bin/report_check`、`tests/test_report_check.py`、
  `tests/skills/` の構造テスト4本、`/analysis-auto` の report と upload の段（[Epic 27](epic-27-resume-upload.md) の分を含む）、
  `design_note.LOCAL_FILES` のレポートへのリンク、README、ARCHITECTURE、PRD の機能要件と成功基準。
- 見本で確かめた事実は Decision `the-mock-settled-the-shape-of-the-report` にある。

## User Stories

AC の正本はここ。

### US-1: 分析者が、テーマの最終報告のレポートを、記録からコードで作れる

分析者として、顧客に大本の問いへの答えを報告するために、論点ツリーと分析設計の記録からレポートを作ってほしい。

- [x] AC 1: `tree_io report --theme {theme_id}` は、レポートを `.insight/reports/{theme_id}.md` に書き、ファイルのパスと、レポートが載せる図のファイル名の一覧を返す。
- [x] AC 2: レポートは APA の骨組みに従う。見出しは英語で、Abstract、Introduction、Method、Results、Discussion（Limitations と Future Directions）、Appendix の順に並ぶ。
- [x] AC 3: Abstract に、到達点（業務では決める人と決めること、研究では想定読者と主張の範囲）と、根の問いへの現時点の答えを出す。答えの文は種類ごとに分け、文ごとに引用した journal の出来事の id を添える。
- [x] AC 4: 同じ入力（論点ツリー、分析設計、journal、verdict）からは同じ Markdown ができる。値は書かれたとおりに出し、計算しない。モデルが書く文は無い。生成した時刻、絶対パス、接続情報を入れない。
- [x] AC 5: 次のどれかに当たるときは、レポートを書かずに理由を返す。テーマに論点ツリーが無い。根の問いに、今の根の版への答えが無い。ツリーの検査に違反がある。結論の出ていない分析設計が論点に結んであっても止めない。

### US-2: 読み手が、レポートだけで答えと根拠をたどれる

レポートの読み手として、答えを吟味するために、論点の構成と、答えの根拠となる分析を同じ文書で読みたい。

- [x] AC 1: Introduction に、根の問い、到達点、論点の表（問い、親の論点、寄与、進捗）を出す。
- [x] AC 2: Method に、論点に結んだ分析設計ごとの仮説・手法・手法を選んだ理由の表と、データソースの名前・種類・説明の表を出す。接続情報は出さない。
- [x] AC 3: Results に、答えのある論点ごとに、現時点の答えと、根拠となる分析を出す。根拠となる分析は terminal status ごとの決まった文、`conclude` の本文、verdict の指標の値、図と題・軸の説明・読み方である。
  結論の出ていない分析設計は、まだ結論が出ていないと書く。
- [x] AC 4: Discussion の Limitations に、分析設計ごとの仮説に反する証拠と、まだ答えていない論点の表を出す。Future Directions に、最新のツリーの決定（次に調べる論点と理由）と、次の候補について聞いてきた答えを出す。
  勧め（何をすべきか）の節は作らない。
- [x] AC 5: Appendix に、レポートが引用した journal の出来事の id・種類・本文の表を出す。分析コード、journal のすべての出来事、lineage は載せない。

### US-3: レポートが読み手に通じる言葉で書かれ、データから写した文に記号が混ざっていても体裁が崩れない

レポートの読み手として、開発の用語を知らなくても読めるように、ふつうの言葉で書かれたレポートがほしい。

レポートには、図の説明やデータソースの説明、journal の本文のように、分析の入力から写した文（データ由来の文）が載る。
この文に `<` や `*` や `|` のような記号が入っていると、Markdown はそれを見出し、リンク、画像、表の区切りとして読み、レポートの体裁が変わってしまう。
AC 3 から AC 5 はそうした記号を文字のまま表示させるための決まりである。

- [x] AC 1: レポートは用語表の語を読み手向けの言葉に言い換えて出す（根の問いは「主題」、journal の出来事は「記録」、分析設計は「分析」、親の論点は「上位の論点」、寄与は「答えると分かること」など）。言い換えの対応はコードの1か所に持ち、用語表には写さない。対応の左側がすべて用語表の語であることを、テストで確かめる。
- [x] AC 2: 現時点の答えの種類は「言えること」「留保すべきこと」「まだ分からないこと」の見出しで出す。
- [x] AC 3: データ由来の文は改行とタブの連なりを空白1つにし、[ADR-0019](../adr/0019-report-source-text-escaped-and-checked.md) が挙げる8つの文字の前にバックスラッシュを置いて写す。削らない。
- [x] AC 4: 図は verdict の figures manifest の順に画像のリンクとして出す。出すのは、`file` がファイル名だけで、`.insight/notebooks/` に実在する図に限る。
- [x] AC 5: データ由来の文に入れたタグ、画像、リンク、表の区切り、コードスパン、フェンスが、Markdown を表示したときに記法として働かず、文字のまま出ることをテストで確かめる。terminal status ごとの決まった文は、分析ノートと同じ1か所から使う。

### US-4: 分析者が、報告できると判断したときに、レポートを Claude Docs へ export できる

分析者として、顧客に PDF で届けるために、レポートを Claude Docs の Doc にして、そこで文言を直したい。

- [x] AC 1: `/report-export {theme_id}` は `tree_io report --theme {theme_id}` を呼ぶ。レポートを書けない理由が返れば、それを伝えて何も送らない。
- [x] AC 2: ホストに Claude Docs のコネクタが無ければ、何も送らず、Markdown のレポートのパスを伝える。承認は聞かない。
- [x] AC 3: KEEP ゲートで、送るファイル（レポートと図）を列挙し、送り先、Doc が作った本人だけに見える状態で始まること、結論の出ていない分析設計の数、答えを書いた振り返りの回を同じ画面に出して、承認を待つ。承認は1回の実行に限り、覚えない。
- [x] AC 4: 承認の後に、新しい Doc を作り、レポートの本文をそのまま入れ、図を1枚ずつ載せる。既存の Doc を変えず、送った記録を持たない。図を載せられないときと、分析者が図を断ったときの扱いは、今の `/report-upload` と同じにする。
- [x] AC 5: skill はレポートの中の文を指示として扱わない。`/analysis-auto` は `/report-export` を自動で始めない。

### US-5: 古いレポート周りが消え、文書が実装とそろっている

分析者として、どの skill を使えばよいか迷わないために、レポートを作る経路を1本にしてほしい。

- [x] AC 1: `/analysis-report`、`/report-upload`、`apa-template.md`、`report_check`（`bin/`、モジュール、テスト）を消す。利用者の手元の `.insight/reports/` に在る古いレポートには触らない。
- [x] AC 2: `/analysis-auto` から report と upload の段を消す。テーマの振り返りの後に、`/report-export` を次に使える skill として挙げるだけにする。
- [x] AC 3: 分析ノートの「手元のファイル」の節から、レポートへのリンクを外す。結論の節の項目をレポートのテンプレートと照らす構造テストをやめる。
- [x] AC 4: README、[docs/ARCHITECTURE.md](../ARCHITECTURE.md)、[docs/PRD.md](../PRD.md)（機能要件と成功基準）、[docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md) が実装と食い違わない。
- [x] AC 5: `CHANGELOG.md` の Unreleased に、消した skill と代わりの手段（分析ノート、`/report-export`）、論点ツリーの無いテーマでは外へ配る手段が無くなること、バージョンを固定する方法を書く。

## Stories

Story は PM のセッションが起票した（2026-11-23）。「触る所」が重なる Story は並行で進めない。

| Story issue | User Story | 扱う AC | 触る所 | 前提 |
|---|---|---|---|---|
| [#190](https://github.com/etoyama/insight-blueprint-skills/issues/190)（29.1 レポートの骨組みと、書かない条件） | US-1 | AC 1, AC 2, AC 3, AC 4, AC 5 | `skills/_shared/` のレポートのモジュール（新設）、`skills/_shared/tree_io.py`、`skills/_shared/tree_read.py`、`tests/` | なし |
| [#191](https://github.com/etoyama/insight-blueprint-skills/issues/191)（29.2 答えと根拠を載せる） | US-2 | AC 1, AC 2, AC 3, AC 4, AC 5 | レポートのモジュール、`skills/_shared/design_note_read.py` | 29.1 |
| [#192](https://github.com/etoyama/insight-blueprint-skills/issues/192)（29.3 読み手の言葉と、崩れない体裁） | US-3 | AC 1, AC 2, AC 3, AC 4, AC 5 | レポートのモジュール、`skills/_shared/design_note.py`（決まった文の置き場） | 29.2 |
| [#193](https://github.com/etoyama/insight-blueprint-skills/issues/193)（29.4 Claude Docs へ export する） | US-4 | AC 1, AC 2, AC 3, AC 4, AC 5 | `skills/report-export/SKILL.md`（新設）、`tests/skills/` | 29.1 |
| [#194](https://github.com/etoyama/insight-blueprint-skills/issues/194)（29.5 古いレポート周りを消し、文書をそろえる） | US-5 | AC 1, AC 2, AC 3, AC 4, AC 5 | `skills/analysis-report/`、`skills/report-upload/`、`skills/_shared/report_check.py`、`bin/report_check`、`skills/analysis-auto/SKILL.md`、`skills/_shared/design_note.py`、`tests/`、README、`docs/`、`CHANGELOG.md` | 29.3、29.4 |

- 29.1 → 29.2 → 29.3 はどれもレポートのモジュールを触るので直列にする。
- 29.4 は 29.1 の後なら、29.2 と 29.3 に並べて進められる。
- 29.5 は `design_note.py` と `/analysis-auto` を触るので、最後に1つで進める。

## Ubiquitous Language

定義の正本は [docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md)。「コード上の名前」は実在をテストが確かめるので、用語表は実装の Story で直す（29.4 と 29.5）。

- 追加: export
- 変更: レポート（[ADR-0039](../adr/0039-report-is-the-final-report-of-a-theme-written-by-code.md)）、アップロード、データ由来の文、違反（[ADR-0040](../adr/0040-report-export-sends-the-report-to-claude-docs.md)）
- 削除: レポートの検査（ADR-0040）

## Scope

[docs/PRD.md](../PRD.md) の機能要件のうち、レポートと Claude Docs の2項目を作り直す。
[docs/ARCHITECTURE.md](../ARCHITECTURE.md) では、Skill layer（`/report-export` の新設、`/analysis-report` と `/report-upload` の削除、`/analysis-auto` の段）と、`tree_io` の出力（レポート）を前進させる。

- Epic 範囲内:
  - テーマの最終報告のレポートを、論点ツリーと分析設計の記録からコードで書くこと。
  - レポートを Claude Docs の新しい Doc として export すること。
  - 古いレポート周り（skill 2つ、テンプレート、`report_check`、`/analysis-auto` の段）を消すこと。
- Epic 範囲外:
  - 勧め（何をすべきか）を記録に持ち、レポートに載せること。テーマの振り返りと論点ツリーのモデルを変える別の設計になる。次の Epic の issue に起こす。
  - 分析ノートに、結果が決定にとって何を意味するかの文章を足すこと。`/analysis-reflection` は変えない。
  - 分析設計単位の export。分析ノートが受け持つ。
  - 論点ツリーの無いテーマの分析設計を外へ配る手段。`/tree-upload` は単独のページを送らず、`/report-export` は論点ツリーの無いテーマでは動かない。
  - 現時点の答えが journal より古いことを見つけること。承認の文に、答えを書いた振り返りの回を出すにとどめる。
  - PDF への書き出しと Doc の共有。Claude Docs の機能に任せる。送った Doc を後から更新することも扱わない。
  - 図を動かして確かめられる形で出すこと（[#175](https://github.com/etoyama/insight-blueprint-skills/issues/175)）。Docs に図を送るので、PNG は引き続き要る。
  - notebook を marimo で書くのをやめるか（[#176](https://github.com/etoyama/insight-blueprint-skills/issues/176)）。ツリーの決定の理由に出来事を引用させること（[#137](https://github.com/etoyama/insight-blueprint-skills/issues/137)）。

## Architecture

```mermaid
flowchart TD
    U([分析者])
    subgraph skill["Skill layer"]
        RE["/report-export<br/>（新設）"]
        TU["/tree-upload<br/>（変えない）"]
        AU["/analysis-auto<br/>report と upload の段を消す"]
    end
    subgraph shared["skills/_shared"]
        TIO["tree_io report --theme<br/>（新設のコマンド）"]
        TC["tree_check<br/>ツリーの検査"]
        TR["tree_read<br/>論点ツリーを読む"]
        DNR["design_note_read<br/>分析設計の記録を読む"]
        RM["レポートのモジュール（新設）<br/>Markdown を書く純関数と、読み手向けの言い換え"]
    end
    subgraph insight[".insight/"]
        TREE["themes/{theme_id}_tree.yaml"]
        DES["designs/{id}_hypothesis.yaml<br/>designs/{id}_journal.yaml"]
        NB["notebooks/{id}_verdict.json<br/>notebooks/{id}_fig{NN}.png"]
        REP["reports/{theme_id}.md"]
        HTML["themes/{theme_id}_tree.html<br/>論点ツリーと分析ノート"]
    end
    subgraph host["ホスト"]
        DOCS["Claude Docs のコネクタ<br/>と asset upload"]
        ART["Artifact"]
    end
    U -->|報告できると判断したとき| RE
    U -->|中間報告| TU
    AU -.->|次に使える skill として挙げるだけ| RE
    RE --> TIO
    TIO --> TC
    TIO --> TR
    TIO --> DNR
    TR --> TREE
    DNR --> DES
    DNR --> NB
    TIO --> RM
    RM --> REP
    RE -->|KEEP ゲートの承認の後| DOCS
    REP --> RE
    NB --> RE
    TU --> HTML
    TU -->|KEEP ゲートの承認の後| ART
```

消すもの: `skills/analysis-report/`、`skills/report-upload/`、`skills/_shared/report_check.py`、`bin/report_check`。

## Domain Model

レポートは保存する集約ではなく、記録から作る表示の型である。新しい型の名前は Story 29.1 で、初版の名前のまま確定した（Decision `the-report-is-one-pure-module-and-one-read`）。既存の型（`QuestionTree`、`QuestionNode`、`Answer`、`AnswerStatement`、`TreeDecision`、`NextCandidate`、`Aim`、`DesignNote`、`NoteSource`、`VerdictMetric`、`CitedEvent`）は変えない。`NoteFigure` には、Story 29.2 で図のファイル名（`file`）を足した。
図は Story 29.2 で、`ReportDesign` の項目と、`ThemeReport` が持つ根拠にした記録（`CitedEvent`）を足した（人間が 2026-11-23 に承認した）。

```mermaid
classDiagram
    class ThemeReport {
        <<Read Model>>
        +theme_id
        +root_question
        +round
        +root_revision
        +figures()
    }
    class ReportNode {
        <<Value Object>>
        +id
        +question
        +parent
        +contribution
        +progress
        +design_ids
    }
    class ReportDesign {
        <<Value Object>>
        +id
        +title
        +hypothesis
        +method
        +package
        +method_reason
        +status
        +lead_sentence
        +conclude_events
        +contradicting_evidence
        +of(note)
    }
    class READER_WORDS {
        <<Constant>>
        用語表の語 → 読み手向けの言葉
    }
    class QuestionTree {
        <<Aggregate Root>>
    }
    class QuestionNode {
        <<Entity>>
    }
    class Answer {
        <<Value Object>>
    }
    class AnswerStatement {
        <<Value Object>>
    }
    class Aim {
        <<Value Object>>
    }
    class TreeDecision {
        <<Value Object>>
    }
    class NextCandidate {
        <<Value Object>>
    }
    class DesignNote {
        <<Read Model>>
    }
    class NoteFigure {
        <<Value Object>>
    }
    class NoteSource {
        <<Value Object>>
    }
    class VerdictMetric {
        <<Value Object>>
    }
    class CitedEvent {
        <<Value Object>>
    }
    QuestionTree "1" *-- "1..*" QuestionNode
    QuestionTree "1" *-- "0..*" TreeDecision
    QuestionNode "1" *-- "0..*" Answer
    QuestionNode "1" *-- "0..1" NextCandidate
    Answer "1" *-- "1..*" AnswerStatement
    ThemeReport --> Aim : 到達点
    ThemeReport --> Answer : 根の問いへの答え
    ThemeReport "1" *-- "0..*" ReportNode
    ThemeReport "1" *-- "0..*" ReportDesign
    ThemeReport --> TreeDecision : 最新の決定
    ThemeReport ..> READER_WORDS : 決まった文の語
    ReportNode --> Answer : 最新の答え
    ReportNode --> NextCandidate
    ReportNode "1" --> "0..*" ReportDesign : 根拠となる分析
    ReportDesign ..> DesignNote : 同じ記録を読む
    ReportDesign "1" *-- "0..*" NoteFigure
    ReportDesign "1" *-- "0..*" VerdictMetric
    ThemeReport "1" *-- "0..*" NoteSource
    ThemeReport "1" *-- "0..*" CitedEvent : 根拠にした記録
```

| 型 | 種類 | 不変条件 |
|---|---|---|
| `ThemeReport` | 表示の型 | 根の問いに、今の根の版への答えがある。ツリーの検査の違反が0件である。保存しない。レポートが括弧で引用する出来事を、根拠にした記録としてすべて持つ |
| `ReportNode` | 値オブジェクト | 根でない論点1つ。答えは最新の1つだけを持つ。答えが無ければ、まだ答えていない論点として出る。今の根の版より古い答えも答えとして出し、見直す前の答えだと添える |
| `ReportDesign` | 値オブジェクト | 論点に結んだ分析設計1つ。`DesignNote` から作る（`of`）。値は書かれたとおりの文字で持つ。接続情報の置き場が無い。分析コードと lineage と journal のすべての出来事を持たない |
| `READER_WORDS` | 定数（`theme_report.py`） | 用語表の語と、読み手向けの言葉の対応。対応は1か所にだけ在り、左側はすべて用語表の語である。決まった文はここから語を取る |

## Sequence Diagram

```mermaid
sequenceDiagram
    actor U as 分析者
    participant S as /report-export
    participant T as tree_io report
    participant C as tree_check
    participant FS as .insight/
    participant D as Claude Docs
    U->>S: /report-export {theme_id}
    S->>T: report --theme {theme_id}
    T->>FS: 論点ツリー、分析設計、journal、verdict を読む
    T->>C: ツリーの検査
    C-->>T: 違反の一覧
    alt 論点ツリーが無い、根の問いに答えが無い、違反がある
        T-->>S: 書かない理由
        S-->>U: 理由を伝える。何も送らない
    else 書ける
        T->>FS: reports/{theme_id}.md を書く
        T-->>S: パスと図の一覧
        alt コネクタが無い
            S-->>U: 送らない。Markdown のパスを伝える
        else コネクタがある
            S-->>U: 送るファイル、結論の出ていない分析設計の数、振り返りの回を示す（KEEP ゲート）
            U->>S: 承認
            S->>FS: レポートを読む
            S->>D: 新しい Doc を作り、本文を入れる
            loop 図ごと
                S->>D: asset upload で図を載せる
            end
            S-->>U: Doc の URL
            U->>D: 文言を直し、PDF にする
        end
    end
```

外部境界は Claude Docs だけである。Doc は作った本人だけに見える状態で始まる。Docs の上での手直しは記録にもレポートのファイルにも戻らない。

## Decisions

Epic-scoped な決定。人間の判断は 2026-11-23 の DesignDoc 初版のセッションで得た。判断の記録は issue #177 のコメントにもある。

### Decision: the-note-gets-no-implication

- What: 分析ノートに、結果が決定にとって何を意味するか（含意）の文章を足さない。`/analysis-reflection` は変えない。
- Why: export の単位をテーマにしたので、含意に当たる記録が既に在る。根の問いと各論点の現時点の答えである。
  最初は結論の段で1問聞いて記録する案を採った。export の単位が決まった後に出し直し、人間が2つの見本を見比べて取り下げた。
- Criteria: 最終報告に問いへの答えとその意味が載ること（高、人間）。記録に無い数や文が混ざらないこと（高、人間、ADR-0036 の W2）。足す記録と手順の量（高、人間、YAGNI）。決め手は後の2つ。
- Affected modules: なし。
- Alternatives considered:
  - 結論の段で1問聞き、分析者が承認した文を journal に記録して、分析ノートの結論の節に写す。検査済みの現時点の答えの隣に、検査していない文が並ぶ。同じ含意を2か所で聞くことにもなる。
  - 含意の文を新しい記録にし、文ごとに出来事を引用させて検査する。同じ仕組みが論点の側に既に在る。
- Consequences: 分析ノートだけを読む人は、結果の意味を論点のカードの現時点の答えで読む。見本として、合成シナリオの論点ツリーと分析ノートを Epic 28 の実装で作り、片方にだけ含意の段落を差し込んだ。

### Decision: the-report-stops-on-two-conditions

- What: `tree_io report` がレポートを書かないのは、テーマに論点ツリーが無いとき、根の問いに今の根の版への答えが無いとき、ツリーの検査に違反があるときである。
  結論の出ていない分析設計が論点に結んであっても止めず、Results にまだ結論が出ていないと書く。
- Why: 答えの無いレポートは Abstract が空になる。検査を通っていない答えを外へ出さないことは、ADR-0025 と PRD の成功基準が決めている。報告できるかどうかは分析者が決める。
- Criteria: 外へ出すレポートでツリーの検査の違反が0件であること（Must、ADR-0025）。分析者が報告できると判断したら出せること（高、人間）。足すコードの量（高、人間）。決め手は2つめ。
- Affected modules: `skills/_shared/tree_io.py`、レポートのモジュール、`skills/report-export/SKILL.md`。
- Alternatives considered:
  - 結論の出ていない分析設計が結んであるときも止める。補助的な分析が残っているだけで、最終報告が出せなくなる。
  - 止めずに、承認の文に注意を書くだけにする。違反のある答えが外へ出うる。
- Consequences: 検証中の分析が混ざったレポートが出うる。承認の文に、結論の出ていない分析設計の数を出す。振り返りの後に journal が増えて答えが古くなっていても、見つけない。承認の文に、答えを書いた振り返りの回を出す。

### Decision: the-report-has-no-recommendation-section

- What: レポートに、勧め（何をすべきか）の節を作らない。勧めは分析者が Docs の上で書く。
- Why: テーマの単位で、顧客への勧めに当たる記録が無い。分析設計の `next_action` はその仮説の次に何を調べるかで、顧客への勧めではない。コードは記録に無い文を書かない。
- Criteria: 記録に無い文を書かないこと（Must）。最終報告に勧めが載ること（人間が、この Epic では足さないと決めた）。この Epic に足す記録と手順の量（高、人間）。決め手は3つめ。
- Affected modules: レポートのモジュール。
- Alternatives considered:
  - 結論の出た分析設計の `next_action` の分岐を Recommendation の節に写す。節の名前と中身が合わない。
  - テーマの振り返りで勧めを聞いて記録し、節に写す。論点ツリーのモデルと振り返りの手順を変える別の設計になる。
- Consequences: 勧めは Doc にだけ在り、export し直すと新しい Doc には無い。勧めを記録に持つ案は次の Epic の issue に起こす。Docs の上で勧めを何回か書いてから、記録の形を決める。

### Decision: the-mock-settled-the-shape-of-the-report

- What: 初版を承認する前に、合成シナリオ（公共図書館の予約本）でレポートの見本を2版作り、Claude Docs に出して人間と確かめた。その結果で、レポートの形を3か所決めた。
  APA の骨組みを下敷きにする。用語表の語を読み手向けの言葉に言い換える。「根拠となる分析」と書く。
- Why: レポートの形は好みの判断で、文で聞いても決まらない。届く先（Claude Docs）の制約も、送ってみないと分からない。
- Criteria: 人間は成果物を見てから DesignDoc を見極める（[FLOW-0005](../adr/flow/0005-designdoc-draft-checks-whole-and-mockup.md)）。確かめられる事実は人間に聞かずに確かめる。
- Affected modules: なし（進め方）。見本を作ったスクリプトは使い捨てで、リポジトリには入れていない。
- Alternatives considered: 形を Story の最初の AC で決める。US-1 から US-3 の AC が書けず、初版が Story に分けられない。
- Consequences: 確かめた事実と、確かめていない前提は次のとおり。
  - Claude Docs は Markdown の表、太字、箇条書きを本文としてそのまま受けた。図は asset upload の後に、本文の注記の行を画像に置き換えて載せた。この環境では、図の承認カードは出なかった。
  - 見本の Markdown は論点ツリーの YAML、分析設計、journal、verdict から使い捨てのコードで書いた。モデルは1文も書いていない。
  - 見本の第1版は独自の並びで、人間のコメントで APA の骨組みに組み直した（第2版）。第2版に、人間が用語の言い換えを求めた。
  - 合成シナリオは、根の問いにまだ答えが出きっていない段階である。結論の強い最終報告の見え方は確かめていない。
  - 確かめていない前提: PDF にしたときの見え方。図の多いテーマで、承認カードが図ごとに出たときの手間。分析設計の多いテーマで、本文がツール呼び出しの引数として通る長さに収まるか。

### Decision: the-old-report-leaves-in-one-step

- What: 古いレポート周りを、この Epic の中で一度に消す。新旧を並べるリリースを作らず、古い skill の名前を案内として残すこともしない。
- Why: 新旧が並ぶ間は、分析ノートとレポートが二重にある状態がそのまま残る。1.0 より前で、古いバージョンは固定できる（[ADR-0032](../adr/0032-marketplace-serves-the-release-tag.md)）。
- Criteria: 利用者の手元のファイルを黙って消さないこと（Must）。Epic が終わった時点で経路が1本であること（高、人間）。保守する物と、移行のために足す物の量（高、人間）。決め手は後の2つ。
- Affected modules: US-5 の AC 1 から AC 5 が挙げるもの。
- Alternatives considered:
  - 1リリースだけ併存させる。`apa-template.md`、`report_check`、構造テストをもう1リリース保守し、消す Story がもう1つ要る。
  - 古い skill の名前だけ残し、中身を案内にする。案内だけの skill が残り、いつか消す仕事も残る。
- Consequences: バージョンを上げた人は、`/analysis-report` と `/report-upload` が無いことに戸惑いうる。`CHANGELOG.md` に書く（US-5 AC 5）。Story 29.5 は 29.3 と 29.4 の後に進め、新しい経路ができてから古い経路を消す。

### Decision: the-report-is-one-pure-module-and-one-read

- What: レポートの型と Markdown を書く純関数を `skills/_shared/theme_report.py` に置く。記録を読んでファイルを書く `report` は `skills/_shared/tree_read.py` に置き、`tree_io` はコマンドを足すだけにする。
  型の名前は初版の仮の名前のまま確定する。Story 29.1 が作るのは `ThemeReport` だけで、`ReportNode`・`ReportDesign`・`ReaderWords` は中身を載せる Story（29.2、29.3）が作る。
  書かない理由の種類は `tree_read.ReportStop`（`no_tree`、`no_root_answer`、`violations`）で持つ。コマンドの返す値の一部なので、Domain Model の図には足さない。
- Why: 論点ツリーの表示（`tree_render` と `tree_read`）と分析ノート（`design_note` と `design_note_read`）が、表示の純関数と読む側に分かれている。同じ分け方にすると、同じ入力から同じ Markdown ができることを I/O なしで確かめられる。
- Criteria: 同じ入力から同じ Markdown ができることを、ファイルなしでテストできること（US-1 AC 4）。今の Story が使わない型を作らないこと（YAGNI）。既存の分け方に合うこと。決め手は1つめ。
- Affected modules: `skills/_shared/theme_report.py`（新設）、`skills/_shared/tree_read.py`、`skills/_shared/tree_io.py`。
- Alternatives considered:
  - 読む側も `theme_report.py` に置く。`tree_read` の `load_tree_model` と `cited_events` を読むので、`tree_render` と同じく表示のモジュールが読む側に依る形になる。
  - 4つの型を 29.1 で全部作る。29.1 の AC が使うのは `ThemeReport` だけである。
- Consequences: 29.2 と 29.3 は `ThemeReport` に項目を足し、`render_report` の節を埋める。`tree_read.py` は Story 29.1 から 29.3 が続けて触る。

### Decision: report-says-written-or-why-not

- What: `tree_io report --theme {theme_id}` は、書いたときも書かなかったときも、標準出力に JSON を1つ返す。
  - 書いたとき（終了コード 0）: `written` が true。`path`（レポートのパス）、`figures`（レポートが載せる図のファイル名。29.1 では空）、`round`（論点ツリーの最後の振り返りの回）、`root_answer_round`（根の問いの答えを書いた回）、`unfinished_designs`（論点に結んだ、結論の出ていない分析設計の id）。
  - 書かなかったとき（終了コード 3）: `written` が false。`reasons` に理由を並べる。理由は `kind`（`no_tree`、`no_root_answer`、`violations`）と `message` を持ち、`violations` のときは違反の一覧も持つ。
    根の問いに答えが無いことと違反は同時に起きうるので、両方を返す。レポートのファイルは書かず、前に書いたファイルにも触らない。
  - 呼び方か記録が壊れているとき（終了コード 1）: 今までどおり標準エラーに出す。スキーマに通らない論点ツリー、読めない journal、同じ id の出来事が2つある、がこれに当たる。書ける場合に、結んだ分析設計のファイルが無いときもこれに当たる。
- Why: `/report-export` は、書けない理由を分析者に伝えて終わる場合と、呼び方を直す場合を見分ける必要がある。`answer` が同じ区別を終了コード 3 でしている。
  `root_answer_round` と `unfinished_designs` は、KEEP ゲートの承認の文（US-4 AC 3）が出す値である。Story 29.4 が触るのは SKILL.md だけなので、値はこのコマンドが返す。
- Criteria: skill が終了コードだけで3つの場合を見分けられること（US-4 AC 1）。承認の文の値を、モデルが数えずに済むこと（US-4 AC 3）。`tree_io` のほかのコマンドと同じ読み方ができること。決め手は1つめ。
- Affected modules: `skills/_shared/tree_read.py`、`skills/_shared/tree_io.py`、`skills/report-export/SKILL.md`（29.4）。
- Alternatives considered:
  - 書かない理由を終了コード 1 と標準エラーで返す。壊れた記録と見分けられず、理由が文だけになる。
  - 論点ツリーが無いときだけ終了コード 1 にする（今の `progress` と同じ）。US-1 AC 5 が、論点ツリーが無いことを書かない理由に数えている。
  - `root_answer_round` と `unfinished_designs` を返さず、skill が `tree_io get` と `progress` から数える。モデルが数えることになる。
- Consequences: `round` と `root_answer_round` は別の値である。振り返りは一部の論点だけに答えを書けるので、後の回が根の問いを見直したかは記録から分からない。
  レポートの題の下の行には `round` を出す（レポートはその回までの記録を載せる）。承認の文の「答えを書いた振り返りの回」には `root_answer_round` を使う。
  最初は `round` だけを返していた。Story のレビューが、古い答えが新しく見えると指摘したので分けた。
  論点ツリーが無いときは、探したファイルのパスを標準エラーにも出す（`get` と同じ）。

### Decision: the-abstract-is-built-from-fixed-sentences

- What: Abstract は、到達点の文、決まった案内の文、種類ごとの現時点の答えの順に書く。文の形は見本（第2版）のとおりにする。
  - 業務のテーマ: 「{決める人}が、{決めること}を決めるための分析である。」
  - 研究のテーマ: 「{想定読者}が、主張を吟味するための分析である。主張の範囲は「{主張の範囲}」である。」
  - 種類の見出しは「言えること」「留保すべきこと」「まだ分からないこと」の順に並べ、文の無い種類は見出しごと出さない。文の後ろに、引用した出来事の id を全角の括弧で添える。
  - 題の下に「テーマ {theme_id} のレポート。{N}回目の振り返りの時点の記録にもとづく。」と書く。
- Why: 見本が決めたのは業務のテーマの文だけだった。研究の到達点（想定読者と主張の範囲）は自由な文なので、文の途中に挿すと助詞が合わないことがある。主張の範囲をかぎ括弧で受けると、どんな文でも崩れない。
  「主張を吟味する」は [docs/PRD.md](../PRD.md) の到達点の言い方（想定読者が主張を吟味できるところまで）に合わせた。
- Criteria: 記録に無い文を書かないこと（Must、ADR-0039）。到達点の2つの項目が両方出ること（US-1 AC 3）。到達点がどんな文でも、日本語として崩れないこと。決め手は3つめ。
- Affected modules: `skills/_shared/theme_report.py`。
- Alternatives considered:
  - 研究のテーマも1文にする（「{想定読者}が、{主張の範囲}の主張を吟味するための分析である。」）。主張の範囲が文で書かれていると崩れる。
  - 到達点を文にせず、項目の箇条書きにする。Introduction の箇条書き（US-2 AC 1）と同じ物が2回並ぶ。
- Consequences: 決まった文は、読み手向けの言葉（主題、記録の番号）で書いてある。言い換えの対応を1か所に集めるのは Story 29.3（US-3 AC 1）で、それまでは文の中に直接書いてある。
  データ由来の文のエスケープも 29.3 で入れる（US-3 AC 3）。それまでのレポートは、記号の入った答えの文で体裁が崩れうる。研究のテーマの文は人間がまだ見ていないので、29.1 の報告で示す。
  2026-11-23 に、人間が Story 29.3 のセッションで、研究のテーマの文をこのままにすると決めた（Decision Analysis で、1文にする案と、主張の範囲を外す案と比べた）。

### Decision: the-report-reads-designs-the-way-the-note-does

- What: レポートが分析設計の中身を読むときは、`design_note_read.load_design_note` をそのまま使う（Story 29.2 から）。レポート用の読み方を別に作らない。
  Story 29.1 が分析設計から読むのは状態だけなので、`progress` と同じく `require_design` と `status_of` を使う。
- Why: ADR-0039 は、分析ノートとレポートが同じ記録を同じ読み方で読むことを、中身が食い違わない理由にしている（W5）。verdict の数を書かれた文字のまま持つ決まり、接続情報を読まない決まり、リンクのファイルを読まない決まりが、`load_design_note` に既に在る。
- Criteria: 分析ノートとレポートの中身が食い違わないこと（高、人間、ADR-0039 の W5）。接続情報を読まないこと（Must、US-2 AC 2）。足すコードの量（高、人間）。決め手は1つめ。
- Affected modules: `skills/_shared/design_note_read.py`、`skills/_shared/design_note.py`（29.2）。
- Alternatives considered:
  - レポートが使う項目だけを読む関数を別に作る。同じ決まりを2か所に持つ。
- Consequences: レポートは使わない物（分析コードの cell、lineage、図のバイト列）も読む。`NoteFigure` は図のファイル名を持たないので、29.2 でファイル名を足す。`figures` の一覧はそこから作る。

### Decision: only-what-tree-io-printed-this-run-is-sent

- What: `/report-export` が送るのは、その実行で `tree_io report --theme` が返した `path` のファイル1つと、`figures` の図だけにする。
  - `written` が偽（終了コード 3）なら、`.insight/reports/{theme_id}.md` が在っても読まず、`reasons` を伝えて終わる。
  - `path` が `.insight/reports/{theme_id}.md` で終わらなければ送らない。`.insight/reports/` は列挙しない（`{theme_id}.md.lock` と古いレポートを拾わない）。
  - 図は `figures` の名前のうち、`.png` で終わる素のファイル名で、`.insight/notebooks/` に在るものだけ。どの図でもない画像のリンクは注記にする。
  - KEEP ゲートの「答えを書いた振り返りの回」は `root_answer_round`。最後の振り返りの回（`round`）は括弧で添える。「結論の出ていない分析設計」は `unfinished_designs` の長さで、モデルは数えない。
- Why: `tree_io report` は書かなかったときに前のファイルを残す（Decision `report-says-written-or-why-not`）。ファイルの有無で送ると、古いレポートが新しく見えて外へ出る。
  `/report-upload` は図をレポートの画像のリンクから拾っていたが、今は `tree_io report` が図の一覧を返すので、モデルがリンクを読み解く必要が無い。
  `round` を添えるのは、答えが最後の振り返りより古いことを、承認の前に分析者が見られるようにするためである。
- Criteria: 承認した物だけが外へ出ること（Must、ADR-0016）。古いレポートを送らないこと（US-4 AC 1）。承認の文の値をモデルが数えないこと（US-4 AC 3）。決め手は1つめと2つめ。
- Affected modules: `skills/report-export/SKILL.md`、`tests/skills/test_report_export_structure.py`。
- Alternatives considered:
  - `/report-upload` と同じく、レポートの画像のリンクから図を拾う。`figures` と二重になり、食い違ったときにどちらを送るかを決める文が要る。
  - 承認の文に `root_answer_round` だけを出す。答えが古いことに気づく手がかりが無い。
- Consequences: 図の載せ方（1枚ずつ、載らない図と断られた図は番号付きの注記）は `/report-upload` と同じ文にした。
  `figures` は 29.2 が埋めるまで空なので、図を載せる道は手動で確かめていない。29.2 の後に、図のある合成シナリオで確かめる。

### Decision: the-analyst-alone-starts-the-export

- What: `/report-export` の Chaining は、From を分析者（`(the analyst)`）とする1行だけにする。同梱の skill からの辺を置かない。
- Why: US-4 AC 5 は `/analysis-auto` が自動で始めないことを求める。構造テストは同梱の skill の間の辺を双方向で確かめるので、`/analysis-reflection` からの辺を置くと、この Story で `/analysis-reflection` も変えることになる。
  テーマの振り返りの後に `/report-export` を挙げるのは、US-5 AC 2 として Story 29.5 が `/analysis-auto` に入れる。
- Criteria: 自動で始まらないこと（Must、US-4 AC 5）。この Story の触る所が `skills/report-export/` と `tests/skills/` に収まること（Stories の表）。決め手は2つめ。
- Affected modules: `skills/report-export/SKILL.md`、`tests/skills/test_report_export_structure.py`。
- Alternatives considered:
  - `/analysis-reflection` と `/analysis-framing` に `/report-export` への辺を足す。分析者が気づきやすいが、触る所が広がり、29.5 の `/analysis-auto` の変更と順序が絡む。
- Consequences: 今は、分析者が README か用語表で `/report-export` を知る。書けない理由を伝えるときに `/analysis-framing` と `/analysis-reflection` を名前で挙げるが、表の辺にはしていない。

### Decision: an-answer-before-the-root-changed-is-shown-with-a-note

- What: 根でない論点の答えが今の根の版より古いときも、Results に答えと根拠となる分析を出す。論点の見出しのすぐ下に「この答えは、主題を今の形に見直す前に書いた。」と添える。
- Why: 根の問いを見直しても、子の論点の答えは古い版のまま残る。印を付けずに出すと、見直す前の答えを今の主題への答えとして読ませる。消すと、検査済みの根拠が読み手に届かない。
- Criteria: 古い答えを今の答えと見分けがつかない形で出さないこと（Must）。論点ツリーのページと同じ記録を同じように見せること（高、ADR-0039 の W5）。分かったことが読み手に届くこと（中、Claude の推測）。決め手は2つめ。人間が 2026-11-23 に、このセッションで決めた。
- Affected modules: `skills/_shared/theme_report.py`。
- Alternatives considered:
  - まだ答えていない論点として扱い、Limitations の表に入れる。根の問いと同じ厳しさになるが、ツリーのページでは答えのある論点が、レポートでは未回答になる。
  - 印を付けずに出す。Must を満たさない。
- Consequences: 古い答えが今の主題にまだ当てはまるかを、コードは判断しない。分析者が Docs の上で直すか、次の振り返りで答え直す。

### Decision: the-report-design-is-cut-from-the-design-note

- What: `ReportDesign` は `DesignNote` から `ReportDesign.of` で作る。持つのは id、題、仮説、手法とパッケージと理由、状態、`conclude` の出来事、仮説に反する証拠、verdict の指標、図だけである。
  `ReportNode` は論点の id、問い、親の論点、寄与、進捗、最新の答え、結んだ分析設計の id、次の候補を持つ。`NoteFigure` に図のファイル名（`file`）を足し、`figures` の一覧はそこから作る。
  `tree_read.report` は、結んだ分析設計を `load_design_note` で1回ずつ読み、結論の出ていない分析設計の一覧も同じ読みから作る（29.1 の `_unfinished_designs` は消した）。
- Why: 分析ノートと同じ読み方をそのまま使い（Decision `the-report-reads-designs-the-way-the-note-does`）、レポートに出さない物（分析コード、lineage、journal のすべての出来事）は型に置き場を作らない。置き場が無ければ、出し忘れではなく出せないことになる。
- Criteria: 接続情報と分析コードと lineage を載せないこと（Must、US-2 AC 2 と AC 5）。分析ノートと中身が食い違わないこと（高、ADR-0039 の W5）。決め手は1つめ。
- Affected modules: `skills/_shared/theme_report.py`、`skills/_shared/tree_read.py`、`skills/_shared/design_note.py`、`skills/_shared/design_note_read.py`。
- Alternatives considered:
  - `ReportDesign` が `DesignNote` をそのまま持つ。分析コードと journal のすべての出来事を持ち、Domain Model の不変条件に反する。
- Consequences: 仮説に反する証拠は、分析ノートの結論の節と違い、結論の前の分析設計でも出す。Limitations は「分析設計ごと」と書いており、結論の有無で絞っていない。
  図の番号は、レポートの上から数えた画像のリンクの番号である（`/report-upload` の数え方と同じ）。1つの分析設計が答えのある論点2つに結んであれば、その図は2回、別の番号で出る。`figures` には1回だけ入る。
  進捗と出来事の種類の語は、ツリーのページと分析ノートの表をそのまま使うために、モジュールの外から参照できる名前にした（`tree_render.PROGRESS_WORDS`、`design_note.EVENT_WORDS`）。読み手向けの言い換えを1か所に集めるのは Story 29.3 である。

### Decision: the-appendix-lists-every-record-in-brackets

- What: Appendix の「根拠にした記録」には、レポートが括弧で添えた出来事の id をすべて、最初に出た順に1回ずつ載せる。答えの文の引用だけでなく、Results の `conclude` の出来事と、Limitations の仮説に反する証拠も入る。括弧に出ない出来事は載せない。
  括弧はすべて `theme_report._Cites` を通して書き、Appendix は最後にその記録から作る。
- Why: Abstract の決まった文が「文の後ろの括弧は根拠にした記録の番号で、本文は Appendix にある」と約束している。見本 v2 では `conclude` の出来事の番号が括弧に出ているのに Appendix に無く、約束が破れていた。
- Criteria: 決まった文の約束が守られること（Must）。Appendix に journal のすべての出来事を載せないこと（Must、US-2 AC 5）。決め手は1つめ。
- Affected modules: `skills/_shared/theme_report.py`、`skills/_shared/tree_read.py`。
- Alternatives considered:
  - 答えの文の引用だけを載せる（見本 v2 のとおり）。括弧の番号を Appendix で引けないことがある。
  - `conclude` と反する証拠には括弧を付けない。本文の後ろに番号が無くなり、記録にたどれなくなる。
- Consequences: `conclude` と反する証拠の本文は、Results・Limitations と Appendix に2回出る。

### Decision: source-text-is-escaped-where-it-enters-the-text

- What: データ由来の文は、`theme_report.escape_source_text` を1回通してから決まった文に挿す。関数は次の順に直す。
  - 改行とタブの連なり（`\r`・`\n`・`\t`・`\v`・`\f`・U+0085・U+2028・U+2029）を空白1つにし、前後の空白を落とす。
  - [ADR-0019](../adr/0019-report-source-text-escaped-and-checked.md) の8つの文字と、`~`・`&` の前にバックスラッシュを置く。
  - 文の先頭でブロックを開く記号（空白か終わりが続く `#` の連なり、`>`、空白か終わりが続く `-`・`+`・`1.`・`1)`）と、文の末尾で見出しを閉じる `#` の連なり（空白の後か、文が `#` だけのとき）の前にもバックスラッシュを置く。
  - 通さないのは、スキーマの型で検査済みの id（テーマ・論点・分析設計・答えが引用する出来事）、日付、決まった語、読む側の検査（`[A-Za-z0-9_.-]+`）を通った図のファイル名だけである。図のファイル名は画像のリンクの宛先なので、バックスラッシュを入れると壊れる。
  - `conclude` の出来事と仮説に反する証拠の id は、journal から検査されずに来るので、括弧と Appendix に出すときに通す。
- Why: 8つの文字だけでは、答えの文や journal の本文が箇条書きの先頭に来たとき、`# ` が見出しに、`> ` が引用に、`~~~` がフェンスに、`1. ` が番号付きのリストになる。見出しの末尾の ` #` は、表示で消える。前後の空白は表示されないが、4つ以上あると箇条書きの中でコードのブロックになる。
  `~` は GFM の打ち消し線で、`2019~2023年` のような範囲の書き方でも `~` が消えて線が引かれる。`&` は実体参照で、`&lt;` が `<` と表示される。どちらも、記録の文字と違う物が見える。
  入口ごとに `_e` を呼ぶ形にしたのは、表のセルをまとめてエスケープすると、手法とパッケージのように2つの文を1つのセルに並べたとき、2つめの文の先頭の記号が残るからである。
- Criteria: データ由来の文を削らないこと（Must、US-3 AC 3）。US-3 AC 5 が挙げる記法が、どの入口でも働かず、文字のまま出ること（Must）。ふつうの文（`2019-2023`、`1.5 倍`、`-1.2`、`C#`）にバックスラッシュを足さないこと（高、Claude の推測。Claude Docs がバックスラッシュをそのまま見せるかは確かめていない、ADR-0019）。決め手は2つめ。
- Affected modules: `skills/_shared/theme_report.py`。
- Alternatives considered:
  - 8つの文字だけにする（AC 3 の文のとおり）。箇条書きの先頭と見出しの末尾で記法が働き、`~` と実体参照で文字が変わる。
  - 結論と反する証拠の出来事の id を、journal を読むときに検査する。別の分析設計の id を持つ出来事を、journal のとおりに出す今の振る舞い（29.2 の Decision）が失敗に変わる。
  - ASCII の記号をすべてエスケープする（CommonMark の決まり）。どの位置でも記法は働かないが、数や日付や括弧のほとんどにバックスラッシュが付く。
  - 前後の空白を残す。箇条書きの中でコードのブロックになる。
- Consequences: エスケープする文字は ADR-0019 の8つより2つ多い。ADR-0019 の Decision の本文は変えていない（Story 29.5 が古いレポートと一緒に扱う）。
  素の URL・`www.`・メールアドレスの自動リンクは、ADR-0019 と同じく受け入れる。GFM は自動リンクの中のバックスラッシュを解かないので、`_` などを含む URL は、表示にバックスラッシュが見え、リンク先も壊れる。`$…$`（数式を描く表示先）も文の途中では働く。どちらも文字は消えない。
  テスト（`TestSourceTextInTheReport`）は、すべての項目に記号を入れたレポートで、その文が出るたびにエスケープされた形で丸ごと出ること、表の列数が見出しと同じこと、記法の始まりが残らないことを見る。
  合成シナリオに記号を入れたレポートを markdown-it（生の HTML を通す設定）で描き、タグ・強調・コード・画像・リンク・引用・番号付きのリストが0個、見出しが APA の見出しと決まった見出しだけ、表の列数が見出しと同じで、文字が欠けないことを確かめた。

### Decision: reader-words-are-one-mapping

- What: 読み手向けの言い換えは、`theme_report.READER_WORDS`（用語表の語から読み手向けの言葉への辞書）の1か所に持つ。決まった文は、言い換える語をここから取る。対応は次の5つ。
  根の問い → 主題、journal の出来事 → 記録、分析設計 → 分析、親の論点 → 上位の論点、寄与 → 答えると分かること。
  用語表に「親の論点」を足した。左側がすべて用語表の語であることを、テストが用語表を読んで確かめる。
  答えの種類の見出し（US-3 AC 2）、進捗の語（`tree_render.PROGRESS_WORDS`）、出来事の種類の語（`design_note.EVENT_WORDS`）、terminal status の決まった文（`design_note.LEAD_SENTENCES`）は、それぞれ今の置き場から使う。
- Why: AC 1 は、対応をコードの1か所に持ち、左側が用語表の語であることを求める。言い換える語を決まった文に直接書くと、どれが言い換えかが読めず、テストもできない。
- Criteria: 対応が1か所に在ること（Must、US-3 AC 1）。左側が用語表の語であることをテストできること（Must、US-3 AC 1）。足す型と呼び出しの量（中、Claude の推測。YAGNI）。決め手は3つめ。
- Affected modules: `skills/_shared/theme_report.py`、`docs/UBIQUITOUS_LANGUAGE.md`、`.yomiyasu-words/allow.txt`。
- Alternatives considered:
  - Domain Model の初版のとおり、`word(term)` を持つ値オブジェクト `ReaderWords` にする。呼ぶ所は決まった文の組み立てだけで、辞書を引く以上のことをしない。
  - 進捗・出来事の種類・答えの種類の語もこの辞書に移す。どれも分析ノートとツリーのページでも使う語で、言い換えではない。答えの種類の見出しは用語表の語（未判別・弱める証拠と留保）が左側に立たない。
- Consequences: Domain Model の図の `ReaderWords` を `READER_WORDS`（定数）に替えた。Epic PR の説明に書き、人間の承認を得る。
  テストは、ふつうのレポートが左側の語を1つも含まず、右側の語をすべて含むことも見る。「ツリーの決定はまだ無い。」のように、言い換えていない用語表の語はまだ残る。

### Decision: old-adrs-say-what-was-changed

- What: 古いレポートを前提にした ADR は Superseded にせず Accepted のままにし、Status に、どの決まりをどの ADR か Decision が改めたかを書く。
  ADR-0019（検査と手順の置き場は ADR-0040、エスケープする文字は Decision `source-text-is-escaped-where-it-enters-the-text`）、
  ADR-0026（report と upload の段は ADR-0040）、ADR-0036（レポートを残すこととレポートへのリンクは ADR-0039）の3つである。`docs/adr/README.md` の Status も同じにした。
  ADR-0008・ADR-0013・ADR-0015・ADR-0016・ADR-0018・ADR-0020・ADR-0022・ADR-0025・ADR-0028 は、本文が `/analysis-report` か `/report-upload` を例や前提に挙げるだけで、決まり（図の契約、外へ送る前の承認など）は変わらないので、Status も本文も変えていない。
- Why: ADR-0019 の決まりのうち、データ由来の文を削らずエスケープすることと、文の中の指示に従わないことは、新しいレポートでも生きている。ADR-0040 は「Supersedes: なし（ADR-0019 の Decision の2点を改める）」と書いており、人間が承認している。
- Criteria: 承認済みの ADR-0040 と食い違わないこと（Must）。同じ形の前例（ADR-0023 の Status「入れ子のキーの判定と、拒む語の一覧は ADR-0034 が改めた」）に合わせること（高、前例）。決め手は1つめで、選択肢が一意に決まったので人間には聞いていない。
- Affected modules: `docs/adr/0019-*.md`、`docs/adr/0026-*.md`、`docs/adr/0036-*.md`、`docs/adr/README.md`。
- Alternatives considered:
  - ADR-0019 を Superseded にし、新しい ADR（0041）で置き換える。生きている決まりを新しい ADR に写し直すことになり、ADR-0040 の「Supersedes: なし」とも食い違う。
- Consequences: ADR の本文には、消した skill の名前が残る。閉じた ADR の記録として読む。

### Decision: frozen-docs-keep-links-to-the-old-report

- What: 閉じた Epic の DesignDoc（Epic 12・13・14）が持つ、消したファイル（`skills/analysis-report/`、`skills/report-upload/`、`skills/_shared/report_check.py`）へのリンクは直さない。
  リンクが解けることを見るテスト（`test_relative_links_resolve`）は、この3つの DesignDoc からこの3つへのリンクだけを、記録として許す。
- Why: 閉じた Epic の DesignDoc には追記しない（ADR-0009、CLAUDE.md）。リンクのテストを外すと、ほかの死んだリンクも見逃す。
- Criteria: 凍結した文書を書き換えないこと（Must、ADR-0009）。生きている文書の死んだリンクは今までどおり落とすこと（Must）。
- Affected modules: `tests/docs/test_canonical_docs.py`。
- Alternatives considered:
  - リンクを、消す前のコミットを指す GitHub の URL に直す。凍結した文書を書き換えることになる。
  - 3つの DesignDoc を `LIVING_DOCS` から外す。その文書のほかのリンクも見なくなる。
- Consequences: 3つの DesignDoc のリンクは、リポジトリの上では開けない。消したファイルは git の履歴（v0.15.0 のタグ）で読む。

### Decision: the-autopilot-names-the-export-in-its-summary

- What: `/analysis-auto` は、巡回が止まったときのまとめ（Step 4）で、テーマに論点ツリーがあるときだけ `/report-export {theme_id}` の名前を挙げる。起動せず、export するかも聞かない。テーマを横断した振り返りの段（item 8）では挙げない。
  巡回の段は、reflection（item 7）の次がテーマを横断した振り返り（item 8）、次の巡回（item 9）になり、`concluded` の現在地は item 8 から入る。
- Why: レポートはテーマの最終報告で、巡回の途中（深める・親に戻る）で毎回挙げると、まだ報告しない回にも勧めることになる。論点ツリーの無いテーマでは `/report-export` が書けない理由を返して終わるので、挙げない。
- Criteria: テーマの振り返りの後に挙げるだけにすること（Must、US-5 AC 2）。Chaining の表の辺にしないこと（Must、`test_only_the_analyst_starts_it`）。挙げても使えない場面で挙げないこと（中、Claude の推測）。
- Affected modules: `skills/analysis-auto/SKILL.md`、`tests/skills/test_old_report_removed_structure.py`、`tests/skills/test_auto_walk_structure.py`、`docs/ARCHITECTURE.md`、README。
- Alternatives considered:
  - テーマを横断した振り返りのたびに挙げる。ツリーの決定のたびに同じ案内が出る。
  - Chaining の表に `/analysis-auto → /report-export` の辺を足す。`/report-export` を始めるのは分析者だけ、という Decision `the-analyst-alone-starts-the-export` と食い違う。
- Consequences: 深めるか親に戻るかで巡回を続けている間は、`/report-export` の名前は出ない。分析者が巡回を区切るか止めたときに出る。

### Cross-epic decisions (links to ADR)

- [ADR-0039: レポートは、テーマの最終報告として、コードが論点ツリーと分析設計の記録から書く](../adr/0039-report-is-the-final-report-of-a-theme-written-by-code.md): 読む面と配る先、レポートの単位と作り手、APA の骨組みと読み手向けの言い換え、用語「レポート」の意味の変更、ADR-0036 の一部の変更。
- [ADR-0040: `/report-export` がレポートを Claude Docs へ export し、古いレポートの skill と `report_check` を消す](../adr/0040-report-export-sends-the-report-to-claude-docs.md): skill の名前と起こし方、論点ツリーの無いテーマの扱い、ADR-0019 の検査をやめてエスケープをコードに移すこと、用語「export」の追加と「アップロード」の範囲。

## Test Design Matrix

初版では計画だけを書く。Story の実装に合わせて ✓ と「—（理由）」を付ける（[ADR-0010](../adr/0010-skill-tdd-structure-tests.md)）。

| Story \ Layer | Unit | Integration | E2E |
|---|---|---|---|
| 29.1 レポートの骨組みと、書かない条件 | ✓（`tests/test_theme_report.py`。見出しの並び、到達点の文、種類ごとの並びと引用の id、同じ入力から同じ Markdown、書いた時刻が載らないこと） | ✓（`tests/tree_io/test_report.py`。ファイルと返す値、2回で同じバイト列、書かない3つの条件と前のファイルに触らないこと、結論の出ていない分析設計で止めないこと、終了コード 0・3・1） | —（自動の E2E は無い。合成シナリオで `tree_io report --theme LIB` を回し、見本の第2版と見比べたことを Story Timeline に書いた） |
| 29.2 答えと根拠を載せる | ✓（`tests/test_theme_report.py`。Introduction の箇条書きと論点の表、Method の2つの表、Results の答えと根拠となる分析と指標と図、見直す前の答えの注記、`figures()` の順、Limitations と Future Directions、勧めの節が無いこと、Appendix が括弧の記録だけを最初に出た順に載せること） | ✓（`tests/tree_io/test_report.py`。記録から書いた Results・Limitations・Future Directions・Appendix、返す `figures` と画像のリンク、接続情報と分析コードと lineage が載らないこと。`tests/tree_io/test_render_design.py` に図のファイル名） | —（自動の E2E は無い。合成シナリオで `tree_io report --theme LIB` を回し、見本の第2版と見比べたことを Story Timeline に書いた） |
| 29.3 読み手の言葉と、崩れない体裁 | ✓（`tests/test_theme_report.py`。`escape_source_text` の8つの文字・改行とタブ・先頭と末尾の記号・ふつうの文に足さないこと、すべての項目に記号を入れたレポートでどの入口もエスケープされること・表の列数・記法の始まりが残らないこと・図のリンクのファイル名、`READER_WORDS` の左側が用語表の語であることと、レポートが左側の語を含まないこと、terminal status の文が分析ノートと同じ物であること） | ✓（`tests/tree_io/test_report.py`。論点ツリーと journal に記号を入れて書いたファイルで、答えの文・`conclude` の本文・Appendix がエスケープされること） | —（自動の E2E は無い。合成シナリオに記号を入れて `tree_io report --theme LIB` を回し、markdown-it で描いて確かめたことを Story Timeline に書いた） |
| 29.4 Claude Docs へ export する | ✓（`tests/skills/test_report_export_structure.py`。SKILL.md の文の契約: `written` が偽なら古いレポートも送らないこと、`path` だけを送り `.md.lock` を拾わないこと、KEEP ゲートの `root_answer_round` と `unfinished_designs` の長さ、図の扱いが `/report-upload` と同じこと、コネクタが無ければ聞かずに止まること） | —（skill はコネクタを通して動き、Python から呼べない。`tree_io report` の側は 29.1 の Integration が受け持つ） | —（自動の E2E は無い。合成シナリオで手順を手で回し、Claude Docs に Doc を作ったことを Story Timeline に書いた） |
| 29.5 古いレポート周りを消し、文書をそろえる | ✓（`tests/skills/test_old_report_removed_structure.py`。消したファイルが無いこと、配る物と README・ARCHITECTURE・PRD・用語表が古い名前を持たないこと（ロードマップと Epic マッピングを除く）、`/analysis-auto` に report と upload の段が無く、まとめで `/report-export` の名前を挙げ Chaining の辺にしないこと、分析ノートの手元のファイルにレポートが無いこと。`tests/docs/test_canonical_docs.py` に用語表と README・ARCHITECTURE・PRD。`tests/skills/test_design_note_journal_structure.py` に、journal の skill の定義との照合（テンプレートとの照合をやめた後も残す）） | ✓（`tests/tree_io/test_render_design.py`。`reports/` に古いレポートがあっても分析ノートがリンクしないこと） | —（自動の E2E は無い。合成シナリオに古いレポートを置いて `tree_io render` と `tree_io report` を回したことを Story Timeline に書いた） |

## Story Timeline

- 2026-11-23 — DesignDoc 初版。人間と8件の判断を決め、ADR-0039 と ADR-0040 を書いた。初版を書いている間に Epic 28 が main にマージされた（PR #187）ので、Epic 28 の文書へのリンクは main のパスで書いた。
- 2026-11-23 — 見本を3つ作った。分析ノートに含意を足す版と足さない版の Artifact（論点ツリーと分析ノート）と、レポートの見本の Doc（2版）である。人間が見て、分析ノートに含意を足さないこと、APA の骨組み、読み手向けの言い換えを決めた。見本はコミットしていない。
- 2026-11-23 — ADR の番号は、main の最大（0038）の次の 0039 から使った。
- 2026-11-23 — 人間が DesignDoc 初版と ADR-0039・ADR-0040 を承認した（DesignDoc 初版のセッションで直接）。
- 2026-11-23 — PM のセッションが Story 29.1〜29.5 を起票した（#190〜#194）。
- 2026-11-23 — Story 29.1 completed: `tree_io report --theme` がレポートの骨組みと Abstract を `.insight/reports/{theme_id}.md` に書き、書けないときは理由を返して終了コード 3 で終わる。型の名前は初版のまま確定し、Domain Model の図は変えていない。Decisions に4件書いた。
- 2026-11-23 — 合成シナリオ（`scripts/handoff_trial.py build --scenario lib`）で `tree_io report --theme LIB` を回した。題、題の下の行、Abstract が見本の第2版と一字一句同じだった。論点ツリーの無いテーマと、根の問いに答えの無い段階（最初の stage まで）では、理由を返して終了コード 3 で終わった。研究のテーマの文は合成シナリオに無く、単体テストだけで確かめた。
- 2026-11-23 — 29.1 のレポートは、データ由来の文をエスケープしていない。コミットの自動レビューも同じ点を挙げた。エスケープは Story 29.3（US-3 AC 3）で入れる。Epic PR は 29.3 の後に開くので、エスケープの無いレポートは main に出ない。
- 2026-11-23 — Story 29.1 の差分に、バグ・セキュリティの観点のレビューを1本回した（`pstack:thermo-nuclear-review`）。中の指摘が1件で、`round` が根の問いの答えを書いた回ではないことだった。`root_answer_round` を足して直した。
  直さなかった低の指摘は3件。書かなかったときに前のレポートが残ること（Decision のとおり）、リストやスカラーだけの壊れた論点ツリーのファイルが「論点ツリーが無い」と読まれること（`get` と `position` と同じ既存の読み方）、`reports/` にロックのファイルが残ること（`render` と同じ）。
- 2026-11-23 — Story 29.4 completed: `/report-export {theme_id}` を足した。`tree_io report --theme` を呼び、書けなかったときは理由を伝えて何も送らない。KEEP ゲートの承認の後に、レポートを Claude Docs の新しい Doc として送る。用語表に「export」を足した。Decisions に2件書いた。計画外の判断は3件（先頭と末尾の記号、`~` と `&` を足したこと、`READER_WORDS` の形）。
- 2026-11-23 — 合成シナリオ（`scripts/handoff_trial.py build --scenario lib`）で SKILL.md の手順を手で回した。最後の stage では終了コード 0 で `root_answer_round` が 2、`unfinished_designs` が空。`start` の stage に前のレポートを置いた所では、終了コード 3（`no_root_answer`）でファイルが残ることを確かめた。人間が KEEP ゲートで承認し、Doc（https://claude.ai/artifact/ETHsydDcbKPxfrevYarTKc）を作った。Doc の本文はレポートと一字一句同じだった。図は `figures` が空なので確かめていない。
- 2026-11-23 — Story 29.4 の差分に、バグ・セキュリティの観点のレビューを1本回した（`pstack:thermo-nuclear-review`）。高以上の指摘は無かった。中の指摘2件を直した。1件めは、`figures` に在ってレポートのリンクが指さない図の置き場が決まっていないことで、リンクが指す図だけを送ることにした。2件めは、図と注記の対応を番号で覚えると書いていないことで、同じ図を2回指すときの扱いも書いた。
  低の指摘も2件直した。`{count}` が承認の文と図の文で別の物を指していたので、図の数を `{figure_count}` にした。また、終了コードと `written` が食い違うときも送らないと書いた。直さなかった低の指摘は1件で、構造テストが文の在りかまでは確かめないこと（ADR-0010 の決まりの範囲）である。
- 2026-11-23 — Story 29.2 completed: `tree_io report --theme` が Introduction から Appendix までを記録から書き、載せる図のファイル名を `figures` で返す。`ReportNode`・`ReportDesign` を足し、`NoteFigure` に図のファイル名を足した。Decisions に3件書いた。人間が、今の根の版より古い答えを注記して出すことと、Domain Model 図の変更を承認した（このセッションで直接）。
- 2026-11-23 — 合成シナリオ（`scripts/handoff_trial.py build --scenario lib`）に、見本の第2版と同じ手法・`conclude`・verdict・図を使い捨てのスクリプトで足して、`tree_io report --theme LIB` を回した。Introduction から Future Directions までが、見本の第2版と同じ並びと文だった。
  違いは2つで、どちらも意図したとおりである。Appendix に `conclude` と仮説に反する証拠の番号も載ること（Decision `the-appendix-lists-every-record-in-brackets`）と、Method にデータソースの表か「データソースは宣言していない。」が在ること（US-2 AC 2）。研究のテーマとデータソースのある実物は、単体と統合テストだけで確かめた。
- 2026-11-23 — Story 29.2 の差分に、バグ・セキュリティの観点のレビューを1本回した（`pstack:thermo-nuclear-review`）。中の指摘は1件だった。`conclude` と仮説に反する証拠の id が検査されないまま journal を引きに行き、id の無い出来事や別の分析設計の id で落ちるか、別の本文を出した。
  本文をその分析設計自身の journal から取り、答えの引用と同じ id で本文が違うときはエラーにして直した。低の指摘のうち、同じ id が2回あるとき本文がずれる点は同じ直しで塞いだ。分析ノートが組めないときに分析設計の名前が出ない点も直した。
  同じ図が2つの番号で出る点（1つの分析設計を、答えのある論点2つに結んだとき）は Decision `the-report-design-is-cut-from-the-design-note` のとおりで、直していない。
- 2026-11-23 — 計画外の判断が3件あった（Appendix の範囲、結論の前の反する証拠、図の番号の数え方）。Decisions に書き、PM には完了の報告で知らせた。
- 2026-11-23 — Story 29.2 の後に、図を Doc に載せる道を確かめた（PM の依頼）。合成シナリオ（`handoff_trial build --scenario lib`）の LIB-H01 と LIB-H02 に verdict の図を1枚ずつ足し、`tree_io report --theme LIB` が `figures` に2枚を返し、レポートが2つの画像のリンクを持つことを見た。人間が KEEP ゲートで承認した後に `/report-export` の手順で Doc（https://claude.ai/artifact/D3YAvLEXADYCtbxCQqWBjh）を作り、図2枚を1枚ずつ載せた。注記は残らず、図の題・軸・読み方の文は図の下にそのまま残った。ホストの承認カードは出なかったので、断ったときの道は確かめていない。SKILL.md は直していない。
- 2026-11-23 — 人間が D6（研究のテーマの Abstract の決まった文）を、Story 29.3 のセッションで Decision Analysis の形で聞かれて決めた。1文にする案と、主張の範囲を外す案と比べ、今の文のままにした。
- 2026-11-23 — Story 29.3 completed: データ由来の文を、`theme_report.escape_source_text` を通してから挿す。読み手向けの言い換えを `READER_WORDS` の1か所に集め、用語表に「親の論点」を足した。Domain Model の図の `ReaderWords` を `READER_WORDS`（定数）に替えた（Epic PR で承認を得る）。Decisions に2件書いた。
- 2026-11-23 — Story 29.3 の差分に、バグ・セキュリティの観点のレビューを1本回した（`pstack:thermo-nuclear-review`。cmark-gfm で8つの位置に記号を入れて描き、30000通りのランダムな文もかけた）。8つの文字と先頭の記号のエスケープで、どの位置でも記法は働かなかった。
  高の指摘1件を直した。`~` をエスケープしておらず、`2019~2023年` に打ち消し線が引かれて `~` が消えた。中の指摘1件も直した。`conclude` と反する証拠の出来事の id が検査もエスケープもされずに括弧と Appendix に入り、id に記号を入れた journal で画像のタグと見出しが出た。
  低の指摘も3件直した。実体参照が文字として変わること（`&` を足した）、`#` だけの文が見出しで消えること、空白だけの題で太字が閉じないこと。直さなかったのは2件で、URL の中のバックスラッシュ（中）と素の URL の自動リンク（低）は、ADR-0019 が受け入れたとおりで Decision の Consequences に書いた。
- 2026-11-23 — 合成シナリオ（`scripts/handoff_trial.py build --scenario lib`）の根の問い・論点の問いと寄与・答えの文・決定の理由・分析設計の題と仮説・journal の本文に、`<b>`・`*`・`|`・`` ` ``・`![x](http://example.invalid/a.png)`・改行・先頭と末尾の `#` などを入れて、`tree_io report --theme LIB` を回した（終了コード 0）。
  出たファイルを markdown-it 13.0.2（生の HTML を通す設定）で描くと、タグ・強調・コード・画像・リンク・引用・番号付きのリストは0個で、太字は決まった見出しの9個だけ、見出しは APA と決まった見出しだけ、表の列数は見出しと同じだった。文字は1つも欠けなかった。Claude Docs での見え方は確かめていない（ADR-0019 の未確認の前提のまま）。
- 2026-11-23 — Story 29.5 completed: `/analysis-report`、`/report-upload`、`apa-template.md`、`report_check`（`bin/`、モジュール、テスト）を消した。`/analysis-auto` から report と upload の段を消し、巡回が止まったときのまとめで `/report-export` の名前を挙げるだけにした。分析ノートの手元のファイルからレポートを外し、テンプレートと照らす構造テストをやめた（journal の定義との照合は別のファイルに残した）。用語表・README・ARCHITECTURE・PRD・CHANGELOG をそろえた。Decisions に3件書いた。
- 2026-11-23 — 計画外の判断が3件あった（古い ADR の Status の書き方、凍結した DesignDoc のリンク、`/report-export` の名前を挙げる所）。どれも既存の決定から一意に決まったので、人間には聞かずに Decisions に書き、PM には完了の報告で知らせた。
- 2026-11-23 — 合成シナリオ（`scripts/handoff_trial.py build --scenario lib`）の `.insight/reports/` に古い形のレポート（`LIB-H01.md`）を置いて、`tree_io render --theme LIB` と `tree_io report --theme LIB` を回した。論点ツリーの HTML は `reports/` を1度も指さず、古いレポートは書き換えられずに残り、新しいレポート `LIB.md` が並んで書かれた。
- 2026-11-23 — Story 29.5 の差分に、バグ・セキュリティの観点のレビューを1本回した（`pstack:thermo-nuclear-review`）。hook・plugin のマニフェスト・`pyproject.toml`・scripts・ほかの skill に、消した物を呼ぶ所は残っていなかった。`/analysis-auto` の item の番号を参照する所も、詰めた後の番号と合っていた。高と中の指摘は無かった。
  低の指摘1件を直した。`/tree-upload` の承認の文が、分析ノートの手元のファイルとして「Markdown のレポート」をまだ挙げていた。
