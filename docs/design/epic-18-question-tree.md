# Epic 18: テーマごとの論点ツリー

## Background

本書がこの Epic の要求と背景の正本（[FLOW-0001](../adr/flow/0001-designdoc-owns-requirements.md)）。
Epic issue（[#116](https://github.com/etoyama/insight-blueprint-skills/issues/116)）には要約と本書へのリンクだけを置く。

- 解く課題: 分析者は合意した問いを1つ AI に委ねたあと、親の問いにどこまで答えられたかを把握できない。
  - 課題1: reflection とレポートは分析設計1つを単位にしている。同じテーマに属する複数の分析設計を束ねて、
    親の問いへの答えがどう動いたかを見る場所が無い。分析設計の `parent_id` は派生の履歴であり、問いの論理の親子ではない。
  - 課題2: 着手のときに、全体像と「なぜこの論点から調べるか」が残らない。framing の Framing Brief は方向を1つ渡して終わる。
    経験の浅い分析者は、何が未着手で何が分析済みなのに未判別なのかを区別できない。
  - 課題3: 複数の分析設計を統合する文をモデルに書かせると、記録に無い数や結論が混ざる。
    `/analysis-report` は「Never compute」の決まりがあっても、Implications で入力に無い比を書いた（[#105](https://github.com/etoyama/insight-blueprint-skills/issues/105)）。
  - 課題4: 引き継いだ人や顧客に、現在地を渡す手段が無い。全体像はビジュアルで見せる価値が大きい（人間の発言、2026-11-20）。
- PRD の要件: [docs/PRD.md](../PRD.md) のビジョンの「問いを委ね、到達を把握し、次の一手を選ぶ」と、
  機能要件の論点ツリーの5項目、非機能要件の「記録に書いてあるものに限る」「表示は正本から決定的に生成する」。
- 既存手段が不十分な理由: `theme_id` は分析設計の id の接頭辞にあるだけで、テーマ単位の記録は無い。
  `DecisionContext` は分析設計ごとに持つ。RQ Brief は想定読者を検討するが（`/rq-problematization` の Step 8）、出力に想定読者の欄が無い。

この Epic の要求は、人間が書いた Handoff（リポジトリ外のメモ）と、2026-11-20 の壁打ちの判断1〜5 から作った。
判断の記録は「Decisions」と [ADR-0024](../adr/0024-question-tree-yaml-and-generated-html.md)・[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md) にある。
分析者の入口を `/analysis-auto` ひとつにする判断は、初版のシーケンス図を見た人間が同じ日に足した（[ADR-0026](../adr/0026-analysis-auto-walks-the-question-tree.md)）。

### 前提にした事実

確かめた方法を添える。

- `theme_id` は `AnalysisDesign` の項目で、分析設計の id は `{theme_id}-H{nn}` になる（`src/insight_blueprint/models/design.py:144`、`skills/_shared/design_io.py:140`）。
- journal の出来事の id は `{design_id}-E{nn}`。`evidence` は `metadata.direction` に `supports` か `contradicts` を持つ（`skills/analysis-journal/SKILL.md` の表）。
- 分析設計の検証は `src/insight_blueprint/validate.py` が正本で、pre-write hook（`hooks/validate-design.py`）は `*_hypothesis.yaml` だけを捕まえる（`docs/ARCHITECTURE.md` の L55〜74）。
- 書いた後の検査には前例がある。`report_check` は `skills/_shared/report_check.py` にあり、`bin/report_check` から呼ぶ。違反があれば終了コード 1 を返す。
- `/analysis-framing` の Step 2（探索）は、Epic 17（PR #114、2026-11-20 にマージ）が書き換えた。データソースは `catalog_io list` で読み、`connection` の値がモデルの文脈に入るのは `/analysis-notebook` だけになった（[ADR-0022](../adr/0022-connection-reaches-only-the-notebook.md)）。この Epic が触るのは Step 4・5 と Framing Brief である（`git diff 905e456 origin/main -- skills/analysis-framing/SKILL.md` で確かめた）。
- Artifact は手元の HTML ファイルを公開する仕組みで、公開した直後は本人にしか見えない。どのホストやアカウントでも使えるかは未確認。

### 未決事項

- 数を含まない言い過ぎ（「原因は通知の遅れだ」）は、ツリーの検査では止まらない。今の手は答えの文に種類を宣言させることと、引き継ぎの試行で人が読むこと。
- RQ Brief に想定読者の欄を足すか。この Epic では framing が直接聞く（US-1 AC 4）。
- 分析設計の `DecisionContext` と、根の到達点の関係。根の値を分析設計に写すのか、別々に持つのか。
- 人が確認・再構成に費やす時間の目標値。基準値が取れてから決める（[docs/PRD.md](../PRD.md) の成功基準）。
- 1つのテーマに論点ツリーを2つ以上持つ必要が出るか。この Epic では1テーマ1ツリーにする。
- `/rq-problematization` の先行研究の収集を、検索の記録、採否の基準、文献ごとの質の評価を残すラピッドレビューに強めるか。
- 結果を別のソースや別の条件で確かめる skill が要るか（業務工程の 6）。

## User Stories

AC の正本はここ。

### US-1: 分析者が、全体像を見て最初に委ねる論点を選べる

分析者として、最初に AI に委ねる論点を納得して選ぶために、着手のときに根の問いと到達点、暫定の第一階層、最初の論点とそれを選んだ理由を論点ツリーに残したい。

- [ ] AC 1: `/analysis-framing` は、合意した方向から論点ツリーを作る。ツリーは根の問い、到達点、第一階層の論点を持ち、各論点は問いの文と寄与を持つ。
  到達点は業務なら `decision_maker` と `decision`、研究なら想定読者と主張の範囲である。
- [ ] AC 2: `/analysis-framing` は、最初に調べる論点と選んだ理由をツリーの決定（種類 `start`）として残す。第二階層が空でもツリーを作れる。
- [ ] AC 3: Framing Brief に `theme_id` と最初の論点の id を載せる。`/analysis-design` は、その論点に作った分析設計を結ぶ。
- [ ] AC 4: 研究で RQ Brief から来たとき、RQ Brief に想定読者が無ければ、`/analysis-framing` が分析者に聞いて到達点に入れる。
- [ ] AC 5: 根の問いか到達点を変えられるのは `/analysis-framing` の再実行だけである。変えるときは根の版を上げるかを分析者に聞き、上げたら版と理由を残す。

### US-2: 分析者が、論点から分析設計と証拠へ辿れる

分析者として、どこを調べていて何が未判別かを把握するために、各論点の進捗と、ひもづく分析設計を見たい。

- [ ] AC 1: 進捗は保存しない。ひもづく分析設計の状態から導く。分析設計が無ければ未着手、terminal status でないものが1つでもあれば検証中、すべて terminal status なら分析済み。unit test で確かめる。
- [ ] AC 2: journal の `question` を論点に昇格できる。昇格した論点は発見元としてその出来事の id を持つ。着手のときに置いた論点は発見元を持たない。
- [ ] AC 3: 1つの分析設計を複数の論点に結べる。
- [ ] AC 4: 論点ツリーの書き込みは `tree_io` を通す。`validate.py` が形を検証し、pre-write hook は `*_tree.yaml` への直接の書き込みも検証する。

### US-3: 分析者が、テーマを横断して現時点の答えと次の一手を把握できる

分析者として、同じ論点を深めるか、親に戻るか、区切るかを決めるために、テーマに属する分析設計を横断した現時点の答えと次の候補を見たい。

- [ ] AC 1: `/analysis-reflection` はテーマを渡されると、論点ごとに、ひもづく分析設計とその journal を読んで現時点の答えを書く。答えの文はそれぞれ、種類（言えること・未判別・弱める証拠と留保）と、引用する journal の出来事の id を1つ以上持つ。
- [ ] AC 2: 親の論点の答えは子の論点の進捗の数から推定しない。子孫の論点にひもづく分析設計の出来事を引用して書く。
- [ ] AC 3: 現時点の答えは追記だけで、振り返りの回と根の版を持つ。前の回と答えが変わった論点を分析者に示す。
- [ ] AC 4: 次の候補として、未着手の論点を示す。候補には、人に聞く問い、その答えで変わる判断、catalog とドメイン知識から分かっていることを添えられる。分析者が聞いてきた答えは、誰に聞いたかと日付を添えて次の候補に残せる。その論点に分析設計を起こすとき、答えを journal に写す。データソースは `catalog_io list` で読み、`connection` の値を論点ツリーに書かない（[ADR-0022](../adr/0022-connection-reaches-only-the-notebook.md)）。
- [ ] AC 5: 分析者が選んだ決定（`deepen`・`return`・`close`）と理由を、ツリーの決定として残す。

### US-4: 分析者に届く答えに、記録に無い数と参照が混ざらない

分析者として、答えを信じて次の判断をするために、現時点の答えに記録に無い数や存在しない参照が混ざっていたら、届く前に止まってほしい。

- [ ] AC 1: ツリーの検査（`tree_check`）は次を違反として挙げる。引用した出来事が無い。引用先の分析設計が、その論点か子孫の論点にひもづいていない。文に出てくる数が、引用した出来事の本文に無い。unit test で確かめる。
- [ ] AC 2: `/analysis-reflection` は答えを書いた後にツリーの検査を回す。違反があれば分析者に届ける前に直し、直せなければその文を除いて、除いたことを伝える。
- [ ] AC 3: #105 と同じ型の再現を持つ。合成シナリオで、引用した2つの出来事の数から作った比を含む文を、ツリーの検査が違反にする。

### US-5: 分析者と引き継いだ人が、ツリーを図で読める

分析者として、全体像と現在地をひと目でつかむために、論点ツリーを手元の図で読みたい。

- [ ] AC 1: `tree_io render` は、正本から自己完結の HTML（`.insight/themes/{theme_id}_tree.html`）を作る。外部の script や stylesheet を読まず、同じ正本からは同じ HTML ができる。
- [ ] AC 2: 各論点に、進捗と現時点の答えを文字で出す。色だけで区別しない。
- [ ] AC 3: 論点を選ぶと、答えの各文と、引用した出来事（本文、分析設計の id、`direction`）が開く。
- [ ] AC 4: 最新の振り返りの回で変わった答えと、根の版が古い答え（根の変更前の答え）を、それと分かるように出す。
- [ ] AC 5: 論点の親子（寄与）と、分析設計の派生（`parent_id`）を別々に辿れる。

### US-6: 分析者が、承認した後に限りツリーを Artifact で渡せる

分析者として、定例報告やレビューで現在地を見せるために、論点ツリーの図を URL で渡したい。

- [ ] AC 1: Artifact として渡す手順は、送るファイルを列挙して KEEP ゲートで承認を待つ。承認は覚えない（[ADR-0016](../adr/0016-approval-before-external-send.md)）。
- [ ] AC 2: Artifact が使えないホストでは、何も送らず、手元の HTML のパスを案内して終わる（[ADR-0015](../adr/0015-host-connectors-for-optional-features.md)）。
- [ ] AC 3: 送るのは、手元で生成した HTML と同じファイルである。モデルに HTML を書かせない。

### US-7: 開発者が、引き継ぎで判断が伝わるかを試せる

開発者として、論点ツリーが判断の質を上げたかを確かめるために、合成シナリオで引き継ぎの試行を繰り返したい。

- [ ] AC 1: 合成シナリオ（公共図書館の予約本）の fixture を持つ。着手時に分かっていた情報と、その後の観察を順に足す段階に分けてある。
- [ ] AC 2: 文脈を持たない別の Claude セッションに HTML だけを渡し、[docs/PRD.md](../PRD.md) の成功基準の5つの問いに答えさせる手順がある。採点は文言でなく判断の一致で行う。
- [ ] AC 3: 人による試行の記録の型がある。5つの問いへの答え、正誤、確認と再構成にかかった時間を残す。

### US-8: 分析者が、`/analysis-auto` ひとつから論点を順に調べられる

分析者として、skill の名前と順番を覚えずに問いを委ねるために、`/analysis-auto` ひとつから着手し、論点を1つずつ調べて、次の論点を選ぶところまで進めたい。

- [ ] AC 1: `/analysis-auto` はテーマを受けると、論点ツリーが無ければ `/analysis-framing` で作り、あれば最新のツリーの決定が指す論点から再開する。研究で RQ がまだ無ければ、framing の前に `/rq-problematization` を呼ぶ。論点ツリーが無いテーマの `design_id` を渡されたら、ツリーを作って巡回に入るか、その分析設計だけを流すかを聞く。ツリーを作るときは、既にある分析設計をどの論点に結ぶかを framing で分析者と決める。
- [ ] AC 2: 1回の巡回は、論点に分析設計を起こし、premortem、notebook、journal、分析設計の振り返り、レポート、テーマを横断した振り返りを経て、ツリーの決定を残すまでである。
- [ ] AC 3: 分析者に聞くのは KEEP ゲートだけである。guided autopilot の今のゲートに、根の問いと到達点、最初に調べる論点、ツリーの決定、根の版を上げるかどうか、ツリーの無いテーマでツリーを作るかどうかの5つを足す。
- [ ] AC 4: 分析設計の結論が出たら（terminal status）、聞かずにレポートを書いて `/report-upload` を始める。ツリーの決定を聞くときは、レポートのパスと論点ツリーの HTML のパスを一緒に示す。結論が出ていない回はレポートを書かない。
- [ ] AC 5: 分析者がツリーの決定で区切るを選ぶか、止めると言うまで巡回を続ける。巡回に使う skill は、それぞれ単独でも起動できる。

## Stories

初版に合意した Story から起票した（人間の判断、2026-11-20）。18.5 と 18.9 は、形に効く未決事項を決めてから起票した（Decisions の判断A・B）。1つの Story が扱う AC は5個以下。

| Story issue | User Story | 扱う AC |
|---|---|---|
| [#119](https://github.com/etoyama/insight-blueprint-skills/issues/119)（18.1 正本と `tree_io`） | US-1、US-2 | US-1 AC 5、US-2 AC 1〜4 |
| [#120](https://github.com/etoyama/insight-blueprint-skills/issues/120)（18.2 framing で着手） | US-1 | AC 1〜4 |
| [#121](https://github.com/etoyama/insight-blueprint-skills/issues/121)（18.3 ツリーの検査） | US-4 | AC 1、AC 3 |
| [#122](https://github.com/etoyama/insight-blueprint-skills/issues/122)（18.4 横断の振り返り） | US-3、US-4 | US-3 AC 1〜3、US-4 AC 2 |
| [#126](https://github.com/etoyama/insight-blueprint-skills/issues/126)（18.5 次の候補とツリーの決定） | US-3 | AC 4、AC 5 |
| [#123](https://github.com/etoyama/insight-blueprint-skills/issues/123)（18.6 HTML の表示） | US-5 | AC 1〜5 |
| [#124](https://github.com/etoyama/insight-blueprint-skills/issues/124)（18.7 Artifact で渡す） | US-6 | AC 1〜3 |
| [#125](https://github.com/etoyama/insight-blueprint-skills/issues/125)（18.8 引き継ぎの試行） | US-7 | AC 1〜3 |
| [#127](https://github.com/etoyama/insight-blueprint-skills/issues/127)（18.9 `/analysis-auto` から巡回する） | US-8 | AC 1〜5 |

## Ubiquitous Language

この Epic で追加・変更した語。定義の正本は
[docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md)。

- 追加: 論点ツリー、論点、根の問い、到達点、根の版、寄与、発見元、進捗、現時点の答え、振り返りの回、ツリーの決定、次の候補、ツリーの検査、Artifact、合成シナリオ、引き継ぎの試行、巡回
- 変更: アップロード（Story 18.7。`/tree-upload` も指す）、journal の出来事（[ADR-0028](../adr/0028-hearing-is-its-own-journal-event.md)。`hearing` を足した）、違反（[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md)。ツリーの検査も挙げる）

## Scope

- Epic 範囲内:
  - 論点ツリーの正本（`.insight/themes/{theme_id}_tree.yaml`）、そのモデルと `validate.py` の検証、`tree_io`。
  - `/analysis-framing` の Step 4・5 と Framing Brief、`/analysis-design` が分析設計を論点に結ぶ1手順。
  - `/analysis-reflection` のテーマを横断する振り返り。分析設計1つの振り返りは今のまま残す。
  - ツリーの検査（`tree_check`）、HTML の表示（`tree_io render`）、Artifact で渡す手順。
  - 合成シナリオの fixture と引き継ぎの試行。
  - `/analysis-auto` を分析者の入口にし、論点ごとの巡回をさせること（[ADR-0026](../adr/0026-analysis-auto-walks-the-question-tree.md)）。
- Epic 範囲外:
  - `/analysis-report` の Implications の数（#105）。この Epic のツリーの検査の型を流用できるかは、#105 の側で決める。
  - RQ Brief の欄の変更と、`/rq-problematization` の先行研究の集め方の変更（未決事項）。
  - レポートを論点ツリーの単位で書くこと。レポートは分析設計1つの単位のまま（#76）。
  - 施策の実行、承認のシステム化、継続運用の監視、ヒアリングそのもの（[docs/PRD.md](../PRD.md) のスコープ外）。

## Architecture

```mermaid
flowchart TD
    U[分析者]
    AUTO["/analysis-auto<br/>skills/analysis-auto/SKILL.md"]
    RQ["/rq-problematization"]
    RP["/analysis-report・/report-upload"]
    FR["/analysis-framing<br/>skills/analysis-framing/SKILL.md"]
    DS["/analysis-design"]
    RF["/analysis-reflection<br/>skills/analysis-reflection/SKILL.md"]
    TIO["tree_io（新設）<br/>skills/_shared/tree_io.py + bin/tree_io"]
    TC["tree_check（新設）<br/>skills/_shared/tree_check.py + bin/tree_check"]
    VAL["validate.py<br/>src/insight_blueprint/validate.py"]
    HOOK["pre-write hook<br/>hooks/validate-design.py"]
    DIO["design_io"]
    TREE[(".insight/themes/{theme_id}_tree.yaml<br/>正本")]
    HTML[(".insight/themes/{theme_id}_tree.html<br/>生成物")]
    DES[(".insight/designs/<br/>*_hypothesis.yaml / *_journal.yaml")]
    TU["/tree-upload（新設）<br/>skills/tree-upload/SKILL.md"]
    ART["Artifact（ホストの機能。任意）"]

    U -->|入口| AUTO
    AUTO -->|研究で RQ が無いとき| RQ
    RQ -->|RQ Brief| FR
    AUTO -->|着手、根の変更| FR
    AUTO -->|論点ごと| DS
    AUTO -->|論点ごと| RF
    AUTO -->|結論が出たら| RP
    U -.->|単独でも起動できる| FR
    U -.->|単独でも起動できる| RF
    FR -->|create / add-node / decide / revise-root| TIO
    DS -->|link| TIO
    RF -->|answer / decide| TIO
    RF -->|書いた後に検査| TC
    TIO -->|検証| VAL
    HOOK -->|"*_tree.yaml を検証"| VAL
    TIO --> TREE
    TIO -->|render| HTML
    TC -->|読む| TREE
    TC -->|読む| DES
    RF --> DIO
    DIO --> DES
    FR -->|render| TIO
    RF -->|render| TIO
    U -.->|図を渡したいとき| TU
    TU -->|render| TIO
    TU -->|KEEP ゲートの後| ART
    HTML -.->|同じファイルを送る| ART
```

## Domain Model

クラス名は Story 18.1 の最初に人間が決めた（Decisions の `tree-type-names`）。
Story 18.1 が実装したのは `QuestionTree`・`RootRevision`・`Aim`・`QuestionNode`・`Progress` で、[docs/ARCHITECTURE.md](../ARCHITECTURE.md) の全体図にも載せた。
Story 18.2 は `TreeDecision` と `decisions` を足した。種類は `start` だけで、残りの3つは Story 18.5 で足す（Decisions の `start-is-the-only-decision-kind-for-now`）。
Story 18.3 は `Answer`・`AnswerStatement`・`StatementKind` と `answers` を足した（Decisions の `answer-types-land-with-the-check`）。Story 18.4 は答えを書く手段（`tree_io answer`）と `current_round()` を足した（Decisions の `answers-are-checked-before-they-land`・`one-answer-call-is-one-round`）。
Story 18.5 は `NextCandidate` と `next_candidate` を足し、ツリーの決定に `deepen`・`return`・`close` を足した（Decisions の `next-candidates-are-untouched-nodes`・`decision-carries-the-last-round-and-is-tied-to-its-node`）。
モデルに無い項目は検証で拒む。
[docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md) の「コード上の名前」は、名前がコードに実在する語から埋める。

```mermaid
classDiagram
    class QuestionTree {
        <<Aggregate Root>>
        +theme_id
        +root_revisions: list~RootRevision~
        +nodes: list~QuestionNode~
        +decisions: list~TreeDecision~
        +current_revision()
        +current_round()
        +designs_by_branch()
        +untouched_nodes()
    }
    class RootRevision {
        <<Value Object>>
        +revision: int
        +question
        +aim: Aim
        +reason
        +created_at
    }
    class Aim {
        <<Value Object>>
        +kind: business | research
        +decision_maker
        +decision
        +audience
        +claim_scope
    }
    class QuestionNode {
        <<Entity>>
        +id: THEME-Qnn
        +question
        +parent_question_id
        +contribution
        +origin_event_id
        +design_ids: list
        +answers: list~Answer~
        +next_candidate: NextCandidate
    }
    class Answer {
        <<Value Object>>
        +round: int
        +root_revision: int
        +statements: list~AnswerStatement~
        +created_at
    }
    class AnswerStatement {
        <<Value Object>>
        +kind: StatementKind
        +text
        +cites: list~event_id~
    }
    class StatementKind {
        <<enumeration>>
        claim
        undetermined
        weakening
    }
    class NextCandidate {
        <<Value Object>>
        +ask
        +changes_if
        +known
        +answer
        +answered_by
        +answered_at
    }
    class TreeDecision {
        <<Value Object>>
        +round: int
        +kind: start | deepen | return | close
        +node_id
        +reason
        +created_at
    }
    class Progress {
        <<enumeration>>
        not_started
        investigating
        analyzed
    }
    class AnalysisDesign {
        <<Aggregate Root（既存）>>
    }
    class JournalEvent {
        <<既存>>
    }

    QuestionTree "1" *-- "1..*" RootRevision
    QuestionTree "1" *-- "1..*" QuestionNode
    QuestionTree "1" *-- "0..*" TreeDecision
    RootRevision --> Aim
    QuestionNode "1" *-- "0..*" Answer
    QuestionNode --> NextCandidate
    Answer "1" *-- "1..*" AnswerStatement
    AnswerStatement --> StatementKind
    QuestionNode ..> AnalysisDesign : design_ids
    AnswerStatement ..> JournalEvent : cites
    QuestionNode ..> JournalEvent : origin_event_id
    QuestionNode ..> Progress : 導く
```

| 型 | 種類 | 不変条件 |
|---|---|---|
| `QuestionTree` | 集約ルート | 1テーマに1つ。根の問い（`parent_question_id` を持たない論点）はちょうど1つで、その文は今の根の版の問いと同じ。論点の親は同じツリーの中にあり、循環しない。根の版は1から1ずつ増え、今の版より前の版は書き換えも削除もできない。ツリーの決定の `node_id` は実在する。`start` の決定は1つまでで、最初の決定は `start` である。決定の回は並びの順に減らず、ツリーの最後の振り返りの回を超えない。直前の決定の論点に対して、`deepen` はその論点か子孫を、`return` はそれ以外を、`close` は同じ論点を指す。モデルに無い項目を持てない |
| `RootRevision` | 値オブジェクト | 版2以降は理由が空でない |
| `Aim` | 値オブジェクト | `kind` に応じた2項目がどちらも空でない |
| `QuestionNode` | エンティティ | id は `{theme_id}-Q{nn}` で、ツリーの中で重ならない。根以外は寄与が空でない。発見元はあれば同じテーマの `{design_id}-E{nn}` の形。結ぶ分析設計は同じテーマの `{theme_id}-H{nn}` で、同じものを2度結ばない |
| `Answer` | 値オブジェクト | 現時点の答えの1回分。文を1つ以上持つ。追記だけで、最後の要素が今の答え。`root_revision` は今の根の版以下。回は1以上で、1つの論点の中で増え続ける |
| `AnswerStatement` | 値オブジェクト | 文は空でない。`cites` は1つ以上で、どれも同じテーマの `{design_id}-E{nn}` の形。引用先の実在、引用先と論点の対応、数の一致は `validate.py` でなくツリーの検査が確かめる（Decisions の `tree-check-reads-the-last-answer-and-compares-values`） |
| `NextCandidate` | 値オブジェクト | 次の候補に添えるメモ。人に聞く問い・その答えで変わる判断・分かっていることのどれかを持つ。その答えで変わる判断と聞いてきた答えは、人に聞く問いがあるときだけ持てる。答え・誰に聞いたか・日付は3つ揃えて持つ。書き換えられる |
| `TreeDecision` | 値オブジェクト | 理由が空でない。`start` の回は 0。ほかの種類の回は、決めた時点の最後の振り返りの回。`node_id` は次に調べる論点で、`close` では区切った論点。追記だけで、書き換えも削除もできない |
| `Progress` | 導出する列挙 | 保存しない。`design_ids` の分析設計の状態から導く（US-2 AC 1） |

### 正本の形（合成シナリオ）

公共図書館の予約本の架空の例。最初の振り返りの後の状態を、形を示すために縮めて書く。

```yaml
theme_id: LIB
root_revisions:
  - revision: 1
    question: 取り置き期限を延ばす試行をするか
    aim: {kind: business, decision_maker: 図書館員, decision: 取り置き期限を延ばす試行を始めるか}
nodes:
  - {id: LIB-Q01, question: 取り置き期限を延ばす試行をするか}
  - id: LIB-Q02
    question: 期限切れを一貫して数えられるか
    parent_question_id: LIB-Q01
    contribution: 予約取消が混ざると、延長で改善しうる件数が変わる
    design_ids: [LIB-H01]
    answers:
      - round: 1
        root_revision: 1
        statements:
          - {kind: claim, text: 状態の履歴から取消を除き、期限を迎えた予約同士を比べられた, cites: [LIB-H01-E01]}
  - id: LIB-Q05
    question: 通知から期限まで何日開館していたか
    parent_question_id: LIB-Q04
    contribution: 通知の遅れと、来館できる日の少なさを見分ける
    origin_event_id: LIB-H02-E03
    next_candidate:
      ask: 本を確保してから実際に通知するまで、曜日によって手順は変わりますか
      changes_if: 変わるなら通知の時点を調べる論点に進み、変わらないなら開館日数の論点を深める
      known: 今の抽出表に送信日時は無い
      answer: 金曜の夕方に確保した本は、月曜の朝にまとめて通知している
      answered_by: 予約担当の図書館員
      answered_at: 2026-11-20
decisions:
  - {round: 0, kind: start, node_id: LIB-Q02, reason: 取消が混ざると延長で改善しうる件数が変わるため}
  - {round: 1, kind: return, node_id: LIB-Q05, reason: 数え方は定まった。通知から期限までの開館日数を先に確かめる}
```

## Module Responsibilities

| モジュール / 関数 | 責務（する） | 境界（しない → 委譲先） |
|---|---|---|
| `src/insight_blueprint/models/`（論点ツリーのモデル） | 論点ツリーの形と、ファイル1つで判定できる不変条件を型で表す | ファイルをまたぐ参照は確かめない → `tree_check` |
| `src/insight_blueprint/validate.py` | 論点ツリーの YAML を検証する純関数を足す | I/O をしない → `tree_io`・hook |
| `hooks/validate-design.py` | `*_tree.yaml` への直接の書き込みも検証する | 何を書くかは決めない |
| `skills/_shared/tree_io.py`（新設） | ツリーの作成、論点の追加と昇格、分析設計を結ぶ、答えの追記、ツリーの決定、次の候補の列挙とメモ、聞いてきた答えの記録と journal への写し、根の版の更新、HTML の生成 | 答えの中身を考えない → `/analysis-reflection`。引用先と数を自分では判定しない → `tree_check`（`answer` は書く前に `tree_check` の検査を呼び、違反があれば書かない） |
| `skills/_shared/tree_render.py`（新設） | 論点ツリー、テーマの分析設計、引用した出来事を受け取り、HTML の文字列を返す純関数。進捗と、答えに付ける印を導く。ページに入る文字をすべてエスケープする | ファイルを読まない、書かない → `tree_io render`。引用の正しさは確かめない → `tree_check`（`tree_io render` が検査を回し、違反を渡す） |
| `skills/_shared/tree_check.py`（新設） | 現時点の答えの引用の実在、引用先と論点の対応、文の数が引用先の本文にあるかを確かめ、違反を挙げる | ツリーを書き換えない |
| `/analysis-auto` | 分析者の入口。論点ツリーの有無で着手か再開かを決め、論点ごとの巡回を進め、KEEP ゲートでだけ止まる。結論が出たらレポートを書かせる | skill の中身を持たない → 各 skill。ツリーを直接書かない → `tree_io` を使う各 skill |
| `/rq-problematization` | （変えない）先行研究を集め、前提を問い直し、RQ Brief を出す | 論点ツリーを作らない → `/analysis-framing` |
| `/analysis-framing` | 根の問い・到達点・第一階層・最初の論点と理由を分析者と決め、`tree_io` で残す。再実行では次に設計する論点を分析者に聞き、最新の決定と違えば決定を残す。Framing Brief に `theme_id` と論点の id を載せる | データの探索のやり方は変えない（Step 2 は Epic 17 の領分）。仮説の文を作らない → `/analysis-design` |
| `/analysis-design` | 作った分析設計を、Framing Brief の論点に結ぶ。結んだ後に `tree_io copy-hearing` を呼ぶ | 論点を作らない → `/analysis-framing`。聞いてきた答えを打ち直さない → `tree_io copy-hearing` |
| `/analysis-reflection` | テーマを横断して現時点の答えを書き、ツリーの検査を通し、次の候補とツリーの決定を残す | 分析設計1つの振り返りは今のまま。HTML を書かない → `tree_io render` |
| `/tree-upload`（新設） | 分析者が頼んだときに、`tree_io render` が書いた HTML を列挙して KEEP ゲートで承認を待ち、承認の後に新しい Artifact として送る。Artifact が無いホストでは手元のパスを伝える | HTML を書かない → `tree_io render`。いつ渡すかは決めない → 分析者。framing と reflection は案内するだけで起動しない |
| `/analysis-report`・`/report-upload` | （変えない）結論の出た分析設計のレポートを書き、承認の後に Claude Docs へ送る | いつ書くかは決めない → `/analysis-auto` |
| `/analysis-journal` | `question` の出来事を残す。人に聞いた答えを `hearing` として残せる（[ADR-0028](../adr/0028-hearing-is-its-own-journal-event.md)） | 論点への昇格は `tree_io`。次の候補の答えを写すのは `tree_io copy-hearing` |

## Sequence Diagram

分析者の入口は `/analysis-auto` ひとつにする（[ADR-0026](../adr/0026-analysis-auto-walks-the-question-tree.md)）。
auto は論点ツリーを作り、論点を1つずつ巡回する。研究で RQ がまだ無いときは、ツリーを作る前に `/rq-problematization` で先行研究を集め、前提を問い直して RQ を立てる。
1回の巡回は分析設計、premortem、notebook、journal、分析設計の振り返り、レポート、テーマを横断した振り返り、ツリーの決定の順に進む。
分析者は、レポートと論点ツリーの両方を見てからツリーの決定をする（人間の発言、2026-11-20）。
分析者とのやり取りは KEEP ゲートだけで起きる。図では、分析者が答えるメッセージに G1〜G14 の番号を振った。G14 は後から足したゲートで、位置は図の上の方にある。
各 skill は今までどおり単独でも起動できる（[ADR-0005](../adr/0005-selective-autonomous-chaining.md)）。

```mermaid
sequenceDiagram
    actor U as 分析者
    participant A as /analysis-auto
    participant Q as /rq-problematization
    participant F as /analysis-framing
    participant D as /analysis-design・/analysis-review
    participant P as /premortem
    participant N as /analysis-notebook・/analysis-journal
    participant R as /analysis-reflection
    participant T as tree_io・tree_check
    participant O as /analysis-report・/report-upload・/tree-upload

    U->>A: テーマ（theme_id）と、顧客が決めたいこと、または研究テーマ
    A->>T: ツリーを読む
    alt ツリーが無い
        opt design_id を渡された
            A-->>U: ツリーを作って巡回に入るか、この分析設計だけを流すか
            U->>A: G14 どちらにするか
            Note over A,O: 分析設計だけを流すなら、今までどおり1つを最後まで進めて終わる
        end
        opt 研究で、RQ がまだ無い
            Note over U,O: 研究の上流 ラピッドレビュー、問題化、RQ の設定
            A->>Q: 研究テーマを任せる
            Q-->>U: 前提の一覧を途中で確認するか
            U->>Q: G1 確認する、または最後まで進める
            Q->>Q: 先行研究を集めて検証の状態を付け、既存の理論をまとめる（AUTO）
            Q->>Q: 前提を5つの類型で抜き出し、批判役の agent と詰める（AUTO）
            opt G1 で確認を選んだ
                Q-->>U: 詰めた前提の一覧
                U->>Q: G2 問い直す前提を選ぶ、直す
            end
            Q->>Q: 前提を評価し、代わりの前提から RQ を立て、想定読者を検討する（AUTO）
            Q-->>A: RQ Brief と、文献と前提の整理を書いたファイルのパス
        end

        Note over U,O: 工程1 相談・課題の定義、工程2 分析・収集の設計
        A->>F: framing に任せる（RQ Brief があれば渡す）
        F->>F: データと既存の分析を探索する（AUTO）
        F-->>U: Data Map、根の問いと到達点の案
        U->>F: G3 根の問いと到達点を決める（研究では、検証する RQ、想定読者、主張の範囲）
        F-->>U: 暫定の第一階層、各論点の寄与と優先の理由
        U->>F: G4 最初に調べる論点を選ぶ（理由つき）
        F->>T: create、decide start、render
        F-->>A: Framing Brief（theme_id、論点の id）
    else ツリーがある
        T-->>A: 最新のツリーの決定と、次に調べる論点
    end

    loop 論点ごとの巡回（区切るまで）
        Note over U,O: 工程2 分析・収集の設計
        A->>D: 論点から分析設計を起こす（AUTO で下書き）
        D-->>U: 仮説、手法、データの取り方、図の案
        U->>D: G5 4つの確認（仮説と決定の文脈、手法、データの取り方、図）
        D->>T: link（分析設計を論点に結ぶ）
        D->>T: copy-hearing（人に聞いた答えがあれば journal に hearing として写す。AUTO）
        opt レビューを頼まれた
            D-->>U: レビューの指摘
            U->>D: G6 判定
        end

        Note over U,O: 工程3 データ取得・理解・整備
        A->>P: premortem
        alt HARD_BLOCK か HIGH
            P-->>U: リスク（未登録のデータソース、費用、許可リスト外のパッケージ）
            U->>A: G7 進める、分析設計を直す、/catalog-register で登録する
        end

        Note over U,O: 工程4 探索・仮説の更新、工程5 推定・モデル構築
        A->>N: notebook を作って実行する
        opt 宣言外の送受信、許可リスト外のパッケージ、ほかの副作用
            N-->>U: 副作用の中身
            U->>N: G8 進めてよいか
        end
        N->>N: observe・evidence・question を journal に残す（AUTO）

        Note over U,O: 工程6 妥当性検証・レビュー、工程7 解釈・報告・意思決定支援
        A->>R: 分析設計の振り返り
        R-->>U: 証拠のまとめ
        U->>R: G9 結論（conclude・refine・branch）と状態の遷移
        alt G9 で結論が出た（分析設計が terminal status）
            A->>O: /analysis-report でレポートを書く（AUTO）、続けて /report-upload
            O-->>U: Claude Docs へ送るファイルの一覧
            U->>O: G10 送るかどうか
        else refine か branch
            Note over A,O: レポートは書かない（/analysis-report は terminal status を求める）
        end
        A->>R: テーマを横断した振り返り
        R->>R: 論点ごとに現時点の答えを書く（文ごとに種類と引用）
        R->>T: answer（検査を通るまで正本に書かない）
        T-->>R: 違反の一覧
        opt 違反がある
            R->>T: 直すか除いて、もう一度 answer（AUTO）
        end
        R->>T: tree_check（書いた後の検査）
        R->>T: candidates、candidate（次の候補と、人に聞く問い）
        R->>T: render
        R-->>U: レポートのパスと Doc の URL、ツリーの HTML のパス、変わった答え、未判別の論点、次の候補（人に聞く問いと、その答えで変わる判断）
        U->>R: G11 深める・親に戻る・区切る と理由、次に調べる論点、人に聞いてきた答え
        R->>T: hear（聞いてきた答え）、decide、render

        opt 根の問いか到達点を変える（工程1へ戻る。研究では前提の問い直しへ戻ることもある）
            A->>F: framing を再実行する
            F-->>U: 根の版を上げるか
            U->>F: G12 版を上げるかと、その理由
            F->>T: revise-root、render
        end
        opt 図を渡したい（定例報告やレビュー）
            U->>O: /tree-upload
            O->>T: render
            O-->>U: Artifact で送るファイルの一覧と、誰に見えるか
            U->>O: G13 送るかどうか
        end
        break G11 で区切るを選んだ
            A-->>U: 実行の要約（止まった所と理由、ツリーの HTML のパス）
        end
    end
```

人に聞く問いへの答えを集めるヒアリングは plugin の外で行う（[docs/PRD.md](../PRD.md) のスコープ外）。
分析者は答えを持って G11 で次の論点を選ぶ。
Artifact はホストの機能で、plugin は持たない。使えるかどうかはそのセッションのツールで判断する。使えなければ、何も送らずに手元の HTML のパスを伝える（G13 は起きない）。

### 業務工程と skill の対応

工程は、人間が渡した資料「良い分析者を支える能力・手続き・態度」（ラピッドレビュー、2026-11-18、3頁）の8工程に従う。
資料の8工程は業務の分析を想定しているので、研究では工程1の前に上流工程を3つ足す（人間の発言、2026-11-20）。
資料は工程どうしを一方向に並べず、探索と検証の結果に応じて前の工程へ戻るとしている。上の図では論点ごとの巡回と、工程1へ戻る `revise-root` がこれにあたる。

| 工程 | 担う skill | 分析者とのやり取り | 足りない所 |
|---|---|---|---|
| 研究 a ラピッドレビュー | `/rq-problematization` の Step 2・3（先行研究を集めて検証の状態を付け、既存の理論をまとめる） | なし | 引用の検証はあるが、検索の記録、採否の基準、文献ごとの質の評価、レビューの限界を残す手順は無い |
| 研究 b 問題化 | `/rq-problematization` の Step 4〜6（前提の抜き出し、批判役との詰め、評価） | G1、G2 | — |
| 研究 c RQ の設定 | `/rq-problematization` の Step 7・8 と RQ Brief | G3 | RQ Brief に想定読者の欄が無い。framing が G3 で聞く（US-1 AC 4） |
| 1 相談・課題の定義 | `/analysis-framing`（根の問い、到達点） | G3、G12、G14 | ヒアリングそのものは扱わない。AI が出すのは人に聞く問いの案まで |
| 2 分析・収集の設計 | `/analysis-framing`（第一階層、最初の論点）、`/analysis-design`、`/analysis-review` | G4、G5、G6 | — |
| 3 データ取得・理解・整備 | `/premortem`、`/catalog-register`、`/analysis-design` のデータの取り方、`/analysis-notebook` のリネージ | G5、G7 | データの発生源を担当者に確かめる手順は無い。次の候補の「人に聞く問い」で代える |
| 4 探索・仮説の更新 | `/analysis-notebook`、`/analysis-journal`（`observe`・`question`）、`question` の論点への昇格 | G8、G11 | — |
| 5 推定・モデル構築 | `/analysis-notebook` | G8 | — |
| 6 妥当性検証・レビュー | `/analysis-journal` の `evidence`（`contradicts`）、ツリーの検査 | G9 | `/analysis-review` は実行する前の分析設計を見る。結果を別のソースや別の条件で確かめる skill は無い |
| 7 解釈・報告・意思決定支援 | `/analysis-reflection`（分析設計1つと、テーマの横断）、`/analysis-report`、`/report-upload`、`tree_io render`、`/tree-upload` | G9〜G11、G13 | 結論が出ていない分析設計（refine・branch）にはレポートを書かない（人間の判断、2026-11-20）。そのときのツリーの決定は、ツリーと journal だけを見てする |
| 8 導入・監視・改善・引き継ぎ | 論点ツリーの HTML、`/knowledge-extract` | なし | 導入と監視はスコープ外（[docs/PRD.md](../PRD.md)）。扱うのは引き継ぎだけ |

## Decisions

### Decision: one-tree-per-theme

- What: 1つのテーマ（`theme_id`）に論点ツリーを1つだけ持つ。
- Why: テーマは分析設計の id の接頭辞として既にあり、新しい束ね方の単位を作らずに済む。
- Criteria: 課題1、YAGNI（[.claude/rules/coding-principles.md](../../.claude/rules/coding-principles.md)）。決め手は新しい単位を作らないこと。
- Affected modules: `tree_io`、`/analysis-framing`、`/analysis-reflection`。
- Alternatives considered: テーマの下に複数のツリーを持つ。必要になった例が無いので落とした（未決事項に残す）。
- Consequences: 同じテーマで根の問いが変わるときは、根の版を上げて扱う。

### Decision: progress-is-derived

- What: 論点の進捗は保存せず、ひもづく分析設計の状態から導く。
- Why: 保存すると、分析設計の状態と論点の進捗という2つの正本ができ、いずれずれる。
- Criteria: 課題2。principle「Model the Domain」。決め手は正本を1つにすること。
- Affected modules: `tree_io render`、`/analysis-reflection`。
- Alternatives considered: 論点に進捗を保存する。分析設計を遷移させるたびにツリーも直す手順が増えるので落とした。
- Consequences: 論点に分析設計が無い限り、進捗は未着手のままになる。「分析は済んだが未判別」は、進捗が分析済みで、答えに種類が未判別の文があることで表す。

### Decision: root-revision-marks-stale-answers

- What: 根の問いか到達点を変えるときは根の版を上げる。古い版に対する答えは消さず、表示で「根の変更前の答え」と出す（判断4、2026-11-20）。
- Why: 古い根に対する答えが黙って残ると、引き継いだ人が誤読する。消すと、どの証拠で答えが変わったかを辿れなくなる。
- Criteria: Must は「根が変わったことと理由が残る」（Handoff の受入条件5）。Want は「古い答えがそれと分かる」（高、Claude の推測）と「部品が増えない」（中、Claude の推測）。決め手は前者。
- Affected modules: `tree_io`、`/analysis-framing`、`tree_io render`。
- Alternatives considered: 根が変わったら答えを消す（受入条件5 と両立しない）。この Epic では扱わない（試行で根が変わると受入条件5 を満たせない）。
- Consequences: 言い換え程度の変更でも版が上がると、全論点が「変更前」になる。版を上げるかは分析者に聞く。

### Decision: inquiry-answer-copied-to-journal

- What: 次の候補に、分析者が聞いてきた答え、誰に聞いたか、日付を残せるようにする。その論点に分析設計を起こすとき、答えを journal の出来事として写す（判断A、2026-11-20）。
- Why: 聞いてきた答えは次の論点を選ぶ根拠になる。残す場所が無いと、選んだ理由が辿れない。答えを現時点の答えの根拠に使うには、引用できる記録になっている必要がある（[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md)）。
- Criteria: Must は「現時点の答えの文に入るものは、引用できる記録にある」（ADR-0025）。Want は「聞いてきた答えが図で見える」（高、Claude の推測）、「後で根拠に使える」（中、Claude の推測）、「足す量が少ない」（中、Claude の推測）。決め手は後の2つの釣り合い。人間が推奨を採った。
- Affected modules: 論点ツリーのモデル（`NextCandidate`）、`tree_io`、`/analysis-reflection`、`/analysis-design`、`tree_io render`。
- Alternatives considered: 欄を足すだけ（根拠に使えない）。論点ツリーに自分の出来事を持たせる（ADR-0025 を改め、検査の対象が2種類になる）。何もしない（ツリーの決定の理由欄に文で書くことになり、図で探せない）。
- Consequences: 同じ答えが論点ツリーと journal の2か所に載る。論点ツリーの側を元とし、journal の側には写した元の論点の id を書く。分析設計を起こすまでは、答えを現時点の答えの根拠に使えない。

### Decision: ask-once-for-treeless-design

- What: 論点ツリーが無いテーマの `design_id` を `/analysis-auto` に渡されたら、ツリーを作って巡回に入るか、その分析設計だけを流すかを KEEP ゲートで聞く。ツリーがあるテーマでは聞かない（判断B、2026-11-20）。
- Why: 既にある利用者は、論点ツリーの無い分析設計を持っている。聞かずに動きを分けると、入口をひとつにした auto が、渡した引数で別物になる。
- Criteria: Must は「既にある分析設計を途中から再開できる」（[ADR-0005](../adr/0005-selective-autonomous-chaining.md)）。Want は「auto の動きが引数で黙って変わらない」（高、Claude の推測）と「今の使い方をしている人が余計な手順を踏まない」（中、Claude の推測）。決め手は前者。人間が推奨を採った。
- Affected modules: `/analysis-auto`、`/analysis-framing`。
- Alternatives considered: ツリーを作らず今までどおり流す（動きが黙って分かれる）。必ず framing でツリーを作る（再開したいだけの人も根の問いと到達点を決めることになる）。
- Consequences: ゲートが1つ増える。答えは論点ツリーの有無として残るので、覚える仕組みは要らない。ツリーを作るときは、既にある分析設計をどの論点に結ぶかを framing で決める。

### Decision: tree-type-names

- What: Domain Model の型名を3つ変える。`Inquiry` を `NextCandidate`（項目は `next_candidate`）、`CurrentAnswer` を `Answer`、`Destination` を `Aim`（項目は `aim`）にする。`QuestionTree` と `QuestionNode` は変えない（人間の判断、2026-11-20、Story 18.1）。
- Why: 初版の名前には気になる点が3つあった。「問い」に当たる名前が3つある。`CurrentAnswer` が過去の回も持つ。`Destination` が送り先と読める。
- Criteria: Must は「用語表の『使わない言い換え』を英語にした名前でない」（[docs/WORKFLOW.md](../WORKFLOW.md) §7）。Want は「名前だけで別の概念と取り違えない」（高、Claude の推測）、「名前が中身と食い違わない」（高、Claude の推測）、「用語表の語と1対1で対応する」（中、Claude の推測）、「YAML のキーを大きく変えない」（低、Claude の推測）。決め手は順に、`Inquiry` が `skills/analysis-journal/SKILL.md` の「Inquiry Board」と衝突すること、履歴の要素に current が付くこと、`skills/report-upload/SKILL.md` が destination を送り先の意味で使うこと。人間が3つとも推奨を採った。
- Affected modules: 論点ツリーのモデル、`tree_io`、正本の YAML のキー、[docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md) の「コード上の名前」。
- Alternatives considered: `QuestionNode` を `TreeNode` にする（何のノードかが名前から分からなくなる）。`AnswerRound`（「振り返りの回」と紛れる）。`RootDestination`（送り先の語感が残る）。`IssueTree` と `Goal` は、用語表が禁じた言い換えなので落とした。
- Consequences: journal の `question` と `QuestionNode` の近さは残る。前者は出来事の種類の文字列、後者は型で、`origin_event_id` がつなぐ。`Aim` は研究の目的と読まれうるので、docstring に「誰が何を決めるか、誰に何を主張するか」と書いた。答えを聞き終えた論点にも `next_candidate` が残る点は、Story 18.5 で見直せる。

### Decision: tree-schema-rejects-unknown-fields

- What: 論点ツリーのモデルは、モデルに無い項目を拒む（pydantic の `extra="forbid"`）。分析設計のモデル（`extra="allow"`）とは逆にする。
- Why: 進捗を保存しないこと（US-2 AC 1）を、モデルの形で守る。`progress` や `status` を論点に書いた正本は、`tree_io` でも pre-write hook でも通らない。
- Criteria: US-2 AC 1、principle「Type System Discipline」（不正な状態を表せなくする）。決め手は、直接の書き込みでも進捗を保存できないこと。
- Affected modules: `src/insight_blueprint/models/tree.py`、`validate.py`、pre-write hook。
- Alternatives considered: `extra="allow"` にして `progress` だけを名指しで拒む（拒む名前の一覧が増えていく）。
- Consequences: 後の Story は、項目を正本に書く前にモデルへ足す必要がある。項目名の打ち間違いも止まる。

### Decision: root-question-is-held-twice-and-kept-equal

- What: 根の問いの文は、根の版（`root_revisions[].question`）と根の論点（`nodes[].question`）の両方にある。検証で、根の論点の文が今の根の版の文と同じことを求める。書き換えは `tree_io revise-root` が両方を一度に行う。
- Why: 初版の「正本の形」が両方に文を持つ。片方だけを直接書き換えると、表示と履歴がずれる。
- Criteria: US-1 AC 5（根を変える手段を1つにする）。決め手は、ずれた正本が書き込めないこと。
- Affected modules: 論点ツリーのモデル、`tree_io`。
- Alternatives considered: 根の論点に文を持たせない（根だけ形が変わり、表示と検査が根を特別扱いする）。同じであることを求めない（ずれに気づけない）。
- Consequences: 根の問いを直接の書き込みで直すときは、2か所を同時に直す必要がある。

### Decision: revise-root-rewords-in-place-without-a-bump

- What: `tree_io revise-root` は `bump` を必ず受け取る。`true` なら新しい根の版を理由つきで足す。`false` なら今の版の問いと到達点をその場で書き換え、版は上げない。
- Why: US-1 AC 5 は、版を上げるかを分析者に聞くとしている。上げないと答えたときの書き込み先が要る。
- Criteria: US-1 AC 5、Decision `root-revision-marks-stale-answers` の Consequences（言い換え程度で全論点を「変更前」にしない）。
- Affected modules: `tree_io`、`/analysis-framing`（Story 18.2）。
- Alternatives considered: 常に版を上げる（AC 5 と合わない）。版を上げない変更を禁じる（言い換えを直せない）。
- Consequences: 版を上げない書き換えは、元の文を正本に残さない。残るのは git の差分だけになる。意味が変わる変更を `bump: false` で書けてしまう点は、`tree_io` では止めない。版を上げるかを聞くのは `/analysis-framing` の KEEP ゲートである。

### Decision: link-and-promotion-check-the-other-file

- What: `tree_io link` は、分析設計が実在し、その `theme_id` がツリーのテーマと同じことを確かめる。`tree_io add-node` は、発見元を渡されたら、その出来事が journal にあり種類が `question` であることを確かめる。`tree_io progress` は、結んだ分析設計が無くなっていたらエラーにする。
- Why: 論点ツリーは1つのテーマの分析設計を束ねる（課題1）。別のテーマや実在しない分析設計を結べると、進捗と横断の振り返りが、気づかないうちに誤る。
- Criteria: US-2 AC 1・AC 2、principle「Boundary Discipline」（ファイルをまたぐ確認は I/O を持つ側でする）。
- Affected modules: `tree_io`。`validate.py` は純関数のままにする。
- Alternatives considered: 何も確かめず `tree_check` に任せる（`tree_check` は現時点の答えの引用を見るもので、結びつきは見ない）。
- Consequences: pre-write hook を通る直接の書き込みでは、実在の確認は効かない。hook が見るのはファイル1つの形だけである。テーマが同じことは id の形で分かるので、モデルでも確かめる（結んだ分析設計は `{theme_id}-H{nn}`、発見元は `{theme_id}-H{nn}-E{nn}`）。1つの `question` を2つの論点に昇格することは止めない。1つの問いが2つの論点に分かれることがあるためである。

### Decision: earlier-root-revisions-are-history

- What: 検証は、書き込む前の正本と比べて、根の版が減っていないことと、今の版より前の版が変わっていないことを確かめる。今の版だけは書き換えられる（`bump: false` の言い換え）。版を足す書き込みでは、それまでの版をすべて変えられない。書き込む前の正本と比べるのは pre-write hook である。`tree_io` は形だけを検証し、`revise-root` は版を足すか今の版を書き換えるだけである（Story 18.2 のレビューで訂正。初めは `tree_io` にも効くと書いていた）。
- Why: 根の版は、どの答えがどの根に対するものかを示す（Decision `root-revision-marks-stale-answers`）。直接の書き込みで版を減らせると、Story 18.4 で入る答えの `root_revision` が指す版が無くなる。
- Criteria: US-1 AC 5（上げた版と理由を残す）。分析設計の検証が、書き込む前の状態と比べて遷移を確かめている前例（`validate_design_change`）。決め手は、残した版と理由が直接の書き込みでも消えないこと。レビュー（thermos）の指摘で足した。
- Affected modules: `validate.py`（`validate_tree` の `current`）、pre-write hook。
- Alternatives considered: 形だけを見る（版を減らす書き込みが通る）。今の版の書き換えも禁じる（言い換えができなくなる）。
- Consequences: 今の版の問いと到達点は、直接の書き込みでも書き換えられる。根を変えるのを `/analysis-framing` に限ることは、hook では守れない。書き込む前の正本が検証に通らない形なら、比べずに通す。壊れた正本を直す書き込みを止めないためで、分析設計の検証（`validate_design_change`）と同じ扱いである。Bash からの書き込みは hook を通らない（分析設計と同じ）。

### Decision: start-is-the-only-decision-kind-for-now

- What: Story 18.2 が入れるツリーの決定の種類は `start` だけにする。`deepen`・`return`・`close` は Story 18.5 で足す。`start` の回は 0 で、モデルはそれ以外の回を拒む。`tree_io decide` は回を受け取らず、0 を書く。`start` は1つのツリーに1つまでで、モデルは2つめを拒む。
- Why: 振り返りの回は Story 18.4 で入る。それまでは、回を数える元が無い。
- Criteria: YAGNI（[.claude/rules/coding-principles.md](../../.claude/rules/coding-principles.md)）、US-1 AC 2。決め手は今のコードで意味を持たない値を正本に書けないこと。
- Affected modules: `src/insight_blueprint/models/tree.py`（`TreeDecisionKind`）、`tree_io decide`、`/analysis-framing`。
- Alternatives considered: 4種類を今から受け付ける（回の決め方が無いまま `deepen` を書ける）。
- Consequences: Story 18.5 は種類を足し、回を現時点の答えから決める。それまで、1つのツリーが持てる決定は1つである。`start` が根の問いを指すことは拒まない。

### Decision: decisions-are-append-only

- What: 検証は書き込む前の正本と比べ、ツリーの決定が減っていないことと、既にある決定が変わっていないことを確かめる。できるのは足すことだけである。書き込む前の正本と比べるのは pre-write hook である。`tree_io` は形だけを検証し、決定を足す書き込みしかしない。
- Why: US-1 AC 2 は最初の論点と理由を残すとしている。直接の書き込みで消せると、なぜその論点から調べたかを辿れなくなる（課題2）。
- Criteria: US-1 AC 2。根の版と同じ扱いにすること（Decision `earlier-root-revisions-are-history`）。
- Affected modules: `validate.py`（`validate_tree` の `current`）、pre-write hook。
- Alternatives considered: 形だけを見る（決定を消す書き込みが通る）。
- Consequences: 書き間違えた決定は直せない。種類が `start` だけの間は次の決定も足せないので、誤った `start` は Story 18.5 まで残る。書き込む前の正本が検証に通らない形なら、根の版と同じく比べずに通す。根の版と決定は同じ形の比較を2つ持つ。追記だけの項目が3つめ（現時点の答え）になるとき、1つにまとめる。

### Decision: framing-brief-carries-node-id

- What: Framing Brief の「推奨方向」に、`node_id`（論点の id）と「論点」（問いの文）の行を足す。`theme_id` は提案ではなく、論点ツリーのテーマそのものにする。`/analysis-design` は `design_io create` の後に `tree_io link` を呼ぶ。`node_id` が無い Framing Brief では、結ばずに分析設計を作る。分析者がテーマを変えたときも結ばない。
- Why: US-1 AC 3。項目名は `TreeDecision` の `node_id` と `tree_io link --node` に合わせた。
- Criteria: US-1 AC 3。`/analysis-design` の Step 1.5 が今の Framing Brief を検出できること。決め手は後者。
- Affected modules: `/analysis-framing`（Step 5）、`/analysis-design`（Step 1.5、Step 3、Step 4）。
- Alternatives considered: `question_id`（journal の `question` と紛れる）。`node_id` を必須にする（framing を通さない使い方と、古い Framing Brief が止まる）。
- Consequences: 論点に結ばれていない分析設計ができうる。そのとき論点の進捗は未着手のままになる。`/analysis-framing` は `tree_io decide` が通るまで Framing Brief を出さない。到達点が決まらないと、framing は Framing Brief を出さずに止まる。

### Decision: meaning-change-raises-the-root-revision

- What: `/analysis-framing` の再実行で根の問いか到達点を変えるとき、skill は `bump` を自分で決めず、既定値も置かない。新旧を並べて分析者に聞く。意味が変わる変更は版を上げる。意味が変わるとは、問いが別のことを聞く、決める役割か決める内容が変わる、想定読者か主張の範囲が動く、のどれかである。分析者が「上げない」と答え、skill がその変更を意味の変更と読んだときは、どこが変わったかと、これまでの答えが新しい根への答えとして読まれることを伝え、もう一度だけ聞く。2度目の答えに従う。
- Why: `tree_io` は意味の変更を見分けられない（Decision `revise-root-rewords-in-place-without-a-bump`）。人間がこの穴を Story 18.2 の KEEP ゲートで止めると決めた（PR #128 のコメント、2026-11-20）。
- Criteria: US-1 AC 5。決め手は版を上げない書き換えが分析者の明示の答えなしに起きないこと。
- Affected modules: `/analysis-framing`（Step 4c）。
- Alternatives considered: 到達点の項目が変わったら必ず版を上げる（言い換えでも全論点が「変更前」になる）。skill が意味の変更と読んだら `bump: false` を拒む（決めるのは分析者で、skill の読みが外れたときに直せない）。
- Consequences: 止めるのは手順で、コードではない。構造テストは文があることを確かめるだけで、モデルが従うかは確かめない。分析者が2度「上げない」と答えれば、意味の変わる書き換えも通る。

### Decision: answer-types-land-with-the-check

- What: Story 18.3 を Story 18.4 より先に実装する。`Answer`・`AnswerStatement` の型と、`QuestionNode` の `answers` の項目は Story 18.3 で入れる。形は Domain Model のとおりにする（`cites` は1つ以上、`root_revision` を持つ、追記だけ）。Stories 表の AC の割り当ては変えない（人間の判断、2026-11-21、[PR #128 のコメント](https://github.com/etoyama/insight-blueprint-skills/pull/128#issuecomment-7049465133)）。
- Why: 18.3 と 18.4 はお互いを前提にしていた。18.4 は答えを書いた後にツリーの検査を回す（US-4 AC 2）。18.3 は答えを検査するので、答えの型が要る。
- Criteria: 答えを書き始める時点で検査がもうあること（[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md)、#105）。型が先に入り、18.4 と 18.6 を並行して進められること。1つの Story が扱う AC は5個以下という決まり。決め手は前の2つ。
- Affected modules: `src/insight_blueprint/models/tree.py`、`validate.py`、`skills/_shared/tree_check.py`。
- Alternatives considered: 18.4 を先にして US-4 AC 2 を 18.3 に移す（検査を通らない答えが epic ブランチに残る）。18.3 と 18.4 を1つにまとめる（AC が6個になる）。
- Consequences: 答えを書く手段（`tree_io answer`）は 18.4 まで無いので、18.3 の間に答えを持つ正本は、テストが直接書いたものだけである。18.4 で答えを書いてみて型の項目が足りないと分かったら、計画外の判断として人間に出す。追記だけの項目が3つめになるので、根の版・ツリーの決定・現時点の答えの比較を1つにまとめる（Decision `decisions-are-append-only` の Consequences）。

### Decision: tree-check-reads-the-last-answer-and-compares-values

- What: ツリーの検査（`tree_check`）の細部を次のように決める。
  - 検査するのは、各論点の最後の答え（今の答え）だけである。
  - 数は値で比べる。全角と半角、桁区切り、`1.90` と `1.9` は同じ数として扱う。単位は見ない。`34.6％`・`34.6%`・`34.6パーセント` は同じ数である。
  - はっきりした符号は、数の一部として比べる（Story 18.4 で改めた。人間の承認、2026-11-21、[PR #128 のコメント](https://github.com/etoyama/insight-blueprint-skills/pull/128#issuecomment-7050086010)）。符号とみなすのは、直前が半角の英数字でない `+` と、負の記号である。負の記号は、ハイフンとダッシュ（`-`・`‐`・`‒`・`–`・`—`・`―`・`−`）と三角（`▲`・`△`・`▼`・`▽`）で、どれも同じ負の符号として扱う。全角の `－` と `＋` も同じである。符号と数字の間に空白があってもよい（`- 3.2`）。範囲や日付や id のハイフン（`10-20`、`2026-11-21`、`LIB-H01`、`A-3`）は符号にしない。記号と空白の扱いは、コミットの自動レビューの指摘を受けて、人間が同じ日にこのセッションで広げた。
  - 換算した値と丸めた値は別の数である。記録が `34.6%` のとき、`0.346` と `35` は違反になる。
  - id や日付に見える数にも例外を置かない。文に出てくる数字の並びは、すべて数として拾う。
  - 引用先の分析設計が論点か子孫に結んであるかは、モデルでなくツリーの検査が確かめる。引用の id の形と、テーマが同じことは、モデルが確かめる。
  - 出来事は、その id が指す分析設計の journal にあるときだけ数える。別の分析設計の journal に同じ id の出来事があっても、引用した出来事は無いものとして扱う。
  - 出来事の本文が文字列でない値（`content: 34.6`）なら、その値を文字にして読む。本文が無ければ、数を持たないものとして扱う。
  - 終了コードは、違反なしが 0、違反ありが 1、検査できないが 2 である。検査できないのは、テーマの id が不正、正本が無い、正本が形の検証に通らない、正本の `theme_id` がファイル名と違う、YAML を読めない、引用した id の出来事が journal に2つある、のどれかである。予期しない失敗も 2 にする。Python は捕まえなかった例外を 1 で終えるので、そのままだと違反ありと見分けられない。
- Why: US-4 AC 1 と [ADR-0025](../adr/0025-cited-answers-checked-after-writing.md) は、何を違反にするかを決めているが、どの答えを見るかと、数をどう比べるかは決めていない。
- Criteria: 記録に無い数が届く前に止まること（US-4、#105）。表記の揺れで誤検知しないこと（ADR-0025 の抑え方）。迷ったら違反に倒すこと（`report_check` の前例）。追記だけの答えは直せないこと（Domain Model の `Answer`）。決め手は最初の2つ。
- Affected modules: `skills/_shared/tree_check.py`、`src/insight_blueprint/models/tree.py`。
- Alternatives considered:
  - すべての回の答えを検査する。前の回は追記だけで直せないので、一度違反が残ると検査が通らなくなる。
  - 単位の一致も求める。`34.6 %` と `34.6パーセント` のような揺れで誤検知する。
  - 符号を見ない（Story 18.3 の初めの形）。記録が「3.2」のとき、答えの「−3.2」が通る。増減の向きは記録に無い主張の中心なので、人間が落とした（2026-11-21）。
  - `%` と比の換算（`34.6%` と `0.346`）を同じ数として扱う。換算は計算であり、どこまでを同じとみなすかの線が引けない。
  - 引用先と論点の対応をモデルで拒む。正本1つで判定できるが、US-4 AC 1 がツリーの検査の違反として挙げると決めている。モデルで拒むと、その正本は検査まで届かず、他の違反と一緒に挙げられない。
- Consequences:
  - 記録の数と値が同じなら、単位の意味が違っても通る（記録が「35件」で、答えが「35%」）。数を含まない言い過ぎと同じ種類の穴で、この Epic では塞がない（未決事項）。
  - 数は、記録と同じ符号で書いたときだけ通る。記録が「3.2ポイント減った」と言葉で向きを書いていると、答えの「−3.2ポイント」は違反になる。記録が「−3.2」なら、答えの「3.2」も「+3.2」も違反になる。記録が符号なしの「3.2」なら、答えの「+3.2」は違反になる。違反を受けたら、記録の書き方に合わせて書き直す。Story 18.4 の手順にこのことを書く。
  - 言葉で書いた向き（「減った」「増えた」）は見ない。記録が「−3.2」で、答えが「−3.2 増えた」でも通る。数を含まない言い過ぎと同じ穴である。
  - 空白をはさんだ範囲（`10 - 20`）と、箇条書きの先頭のハイフン（`- 3件`）は、負の数として読む。記録と答えが同じ書き方なら通り、片方だけなら違反になる。
  - 波ダッシュ（`〜`）は範囲にしか使わないので、符号にしない。括弧で書いた負の数（`(3.2)`）と `±` も符号として読まない。長音記号（`ー`）、絵文字の `➖`、下向きの矢印（`↓`）も符号として読まない。記録が「3.2」で、答えが「ー3.2」なら通る（レビューの指摘）。
  - 漢数字（「約二倍」）は拾わない。`1e3` や `½` のような表記は別の数に分かれるので、記録にその数があれば通る。
  - 桁を表す語は見ない。`3万件` は 3 として拾うので、記録が「3件」なら通る。値が1万倍違っても止まらない。
  - 先頭の 0 を省いた小数（`.5`）は 5 として拾う。記録に 5 があれば通り、記録が `0.5` なら違反になる。
  - 出来事の種類は見ない。`hypothesize` や `question` の出来事にある数も、記録にある数として数える。
  - `152/80` のように、記録の2つの数を並べただけの文は通る。新しい数を作っていないので、写しとして扱う。
  - 答えの文に論点や出来事の id、日付を書くと、その数字が違反になる。文には id を書かず、`cites` に書く。Story 18.4 の手順にこのことを書く。
  - 前の回の答えは検査しない。前の回に違反があっても、今の答えが通れば検査は通る。
  - 「ファイル1つで判定できる不変条件はモデルが持つ」（Module Responsibilities）から、引用先と論点の対応だけが外れる。
  - 追記だけの比較とツリーの検査は、どちらも答えを振り返りの回で指す（`LIB-Q02.answers: the answer of round 3 is history and cannot change`）。Story 18.3 では追記だけの比較が並びの中の位置を出していて、回とずれていた。論点は毎回答えを持つとは限らないので、位置は別の答えを指しうる。Story 18.4 で回に揃えた（人間の判断、2026-11-21、Story 18.4 のセッション）。根の版は版の番号で、ツリーの決定は番号を持たないので位置で指す。
  - 符号の読みは記録の側と答えの側で同じである。そのため、記録が箇条書きの「- 20件」や範囲の「10 - 20」を持つと、答えの「−20」が通る。答えが「A-3.2」と書くと符号なしとして読まれ、記録の「3.2」に通る。コミットの自動レビューが挙げた。人間が決めた線引きの内側なので、Story 18.4 では塞いでいない。

### Decision: answers-are-checked-before-they-land

- What: 現時点の答えを書く道は `tree_io answer` だけにする。`tree_io answer` は、答えを足した後のツリーをメモリの上で作り、ツリーの検査にかける。書こうとしている論点に違反が1つでもあれば、どの論点の答えも書かずに違反を返す（終了コード 3）。違反が無ければ正本に書く（人間の判断、2026-11-21、Story 18.4 のセッション）。
- Why: 答えは追記だけで、既にある答えは書き換えられない（Decision `answer-types-land-with-the-check`）。正本に書いた後で違反が見つかると、直す手段が無い。直した答えを次の回として足すと、記録に無い数が正本に残り、回が「前の回から変わった答え」の目印として使えなくなる。
- Criteria: Must は「違反のある答えが分析者に届かない」（US-4 AC 2）と「既にある答えを書き換えない」（US-3 AC 3）。Want は「記録に無い数が正本に残らない」（高、Claude の推測）、「回が変わった答えの目印として使える」（高、Claude の推測）、「手順を守るかどうかにモデルを頼らない」（中、Claude の推測、#105）、「既存の境界と文書を変える量」（中、Claude の推測）。決め手は3つめ。決まりを文で書くだけでは守られないと #105 で分かっている。人間が推奨を採った。
- Affected modules: `skills/_shared/tree_io.py`（`answer`）、`skills/_shared/tree_check.py`（`check_tree`）、`/analysis-reflection`。
- Alternatives considered:
  - `tree_check` に書く前の候補を検査する入口を足し、`tree_io answer` は検査しない。境界は変わらないが、skill が先の検査を飛ばすと違反が正本に入る。
  - 違反した答えも追記し、直した答えを次の回として追記する。記録に無い数が正本に残り、前の回との比較の相手が違反した下書きになる。
  - 同じ回の間は最後の答えを書き換えてよいことにする。追記だけの不変条件が破れる。
- Consequences:
  - US-4 AC 2 と [ADR-0025](../adr/0025-cited-answers-checked-after-writing.md) の「書いた後に検査する」は、「モデルが文を書いた後、正本に入る前に検査する」と読む。`/analysis-reflection` は書いた後にも `tree_check` を回す。そこで見つかるのは、前の回の答えが、後から journal が変わって違反になった場合である。その論点に新しい答えを書いて直す。
  - `tree_io` が `tree_check` を呼び、`tree_check` が `tree_io` を読む。`tree_io answer` は関数の中で `tree_check` を読み込む。違反を判定するのは `tree_check` だけである。
  - `tree_io answer` が止めるのは、その呼び出しで書く論点の違反だけである。ほかの論点の今の答えに違反があっても、書き込みは止めない。
  - 終了コード 3 は `answer` だけが返す。1 は「呼び出しが誤りか、ファイルを読めない」で、`tree_check` の 2（検査できない）とは番号が違う。1 のときに答えを書き直すかどうかは、stderr の文で分ける。payload の誤りなら直して送り直し、正本や journal を読めないなら分析者に伝えて止まる（レビューの指摘で `/analysis-reflection` の手順に足した）。
  - 前の回の答えが後から違反になり、その論点に引用できる出来事が残っていないと、直す手段が無い。答えは取り下げられないからである。`/analysis-reflection` はその論点を「Stale answers」として違反と一緒に示し、答えは示さず、ほかの論点を届ける。正本と HTML には、その答えが今の答えとして残る。取り下げを記録する手段は、この Epic では持たない。
  - `tree_io answer` が受け取る項目は `node_id` と `statements` だけである。`round` などを渡した呼び出しは拒む。
  - Write や Edit で正本に直接書いた答えは、この検査を通らない。pre-write hook が見るのは形と追記だけである。`/analysis-reflection` の手順で直接の書き込みを禁じ、書いた後の `tree_check` で見つける。

### Decision: one-answer-call-is-one-round

- What: 1回の `tree_io answer` が、その振り返りで答える全論点の答えを受け取り、1つの振り返りの回にする。回は「ツリーの中で最大の回 + 1」（`QuestionTree.current_round()` + 1）を、根の版は今の版を、`tree_io` が振る。呼ぶ側は回も根の版も渡さない。今の答えと文が同じで、今の答えが今の根の版のものである論点は、書かない。文が同じでも、今の答えが前の根の版のものなら書く。
- Why: US-3 AC 3 は、答えが振り返りの回を持ち、前の回と答えが変わった論点を示すとしている。回を呼ぶ側に決めさせると、同じ振り返りの答えが別の回になりうる。
- Criteria: US-3 AC 3、用語表の「振り返りの回」（テーマを横断する振り返りの通し番号）。決め手は「その回の答えを持つ論点」がそのまま「その回で変わった論点」になること。表示（Story 18.6）は答えの回の最大値で「この回で変わった」を決めていて、同じ読みになる。
- Affected modules: `skills/_shared/tree_io.py`（`answer`）、`src/insight_blueprint/models/tree.py`（`current_round`）、`/analysis-reflection`。
- Alternatives considered: 論点ごとに1回ずつ呼ぶ（回を揃える手段が要る）。変わらない答えも毎回書く（どの論点が変わったかを、文を比べて導くことになる）。
- Consequences:
  - 論点の答えの回は連番とは限らない（回 1 の次が回 3 になりうる）。
  - すべての論点が変わらなければ、何も書かず、回も進まない。
  - 「変わった」は文の並びが1字でも違うことである。言い換えただけの答えも、変わった答えとして回を持つ。
  - `tree_io answer` は、書いた論点（`written`）に、それまでの答えの回（`previous_round`。初めての答えなら無い）と、文が前と同じか（`restated`）を添えて返す。`/analysis-reflection` はこれで「初めての答え」「変わった答え」「根の版が上がり、同じ文で書き直した答え」を分けて示す。表示（Story 18.6）は、文が前と違うときだけ「この回で変わった」の印を付けるので、書き直した答えには印が付かない。両方とも、文が同じ答えを「変わった」とは呼ばない。
  - 結果の `round` は、呼び出しの後にツリーが持つ最後の回である。違反で止まったときは前の回のままで、違反のほうが、書こうとした回を持つ。
  - 違反で止まった呼び出しは何も書かないので、回を使わない。
  - Story 18.5 は、ツリーの決定の回を `current_round()` から決められる。

### Decision: tree-html-is-static-and-marks-are-derived

- What: 論点ツリーの HTML（`tree_io render`）の細部を次のように決める。
  - script を1つも書かない。開閉は `<details>` で、スタイルはページの中の `<style>` 1つである。画像と外部への参照も出さない。
  - 生成した時刻、絶対パス、乱数をページに入れない。論点は正本の並びの順に、分析設計は id の順に出す。
  - HTML を作る純関数は `skills/_shared/tree_render.py` に置く。`tree_io render` はファイルを読んで渡し、結果を書く。
  - 「この回で変わった」の印は、今の答えの回がツリーで最も新しい回で、1つ前の答えと文（種類・本文・引用）が違う論点に付ける。最も新しい回で初めて答えた論点には「この回で初めて答えた」を付ける。
  - 「根の変更前の答え」の印は、今の答えの `root_revision` が今の根の版より小さい論点に付ける。根の版が2つ以上あれば、版ごとの問い・到達点・理由を履歴として出す。
  - 論点ごとの開閉の中に、今の答えの各文と引用した出来事（id、分析設計の id、種類、`direction`、本文）、前の回の答え、結んだ分析設計を出す。引用した出来事は、すべての回の答えについて読む。
  - 引用した出来事が journal に無ければ「journal に見つからない出来事」と出し、同じ id が2つあれば先のものを出す。どちらも表示は止めない。
  - 結んだ分析設計が無くなっていたらエラーにして、何も書かない（`tree_io progress` と同じ）。結んだ分析設計の状態が既知の値でないときも、その id を添えてエラーにする。
  - 分析設計はファイル名の id で引き、ファイルの中の `id` は読まない（`tree_io progress` と同じ）。読むのはそのテーマのファイル（`{theme_id}-H{nn}_hypothesis.yaml`）だけである。
  - 最も新しい回は、答えの回の最大値である。ツリーの決定の回は数えない。
  - 分析設計の派生は、論点ツリーとは別の節に、テーマの分析設計を `parent_id` で入れ子にして出す。論点に結んでいない分析設計も出す。親がテーマの中に無ければ最上位に置き、派生元の id を添える。
  - ページに入る文字（問い、寄与、理由、答えの文、出来事の本文、分析設計の題と状態、id）は、すべてエスケープする。
- Why: US-5 と [ADR-0024](../adr/0024-question-tree-yaml-and-generated-html.md) は、何を出すかと、外部を読まないことを決めている。開閉の手段、「変わった」の判定、検査が違反にする正本をどう表示するかは決めていない。
- Criteria: 外部の script と stylesheet を読まず、同じ正本から同じ HTML ができること（US-5 AC 1）。色だけで区別しないこと（AC 2）。正本の文は分析者とモデルが書くので信頼しないこと（Story 18.6 の指示）。検査が違反にする正本でも図は読めること（違反を直す人が図を見るため）。決め手は最初の1つで、script を書かなければ決定的であることと自己完結であることが同時に満たせる。
- Affected modules: `skills/_shared/tree_render.py`、`skills/_shared/tree_io.py`。
- Alternatives considered:
  - ページの中に script を書いて開閉する。外部は読まないが、Artifact として渡すときにホストの制約を受けうる。`<details>` で足りるので落とした。
  - 「変わった」を、最も新しい回に答えがあるかだけで決める。毎回すべての論点に同じ答えを書き足す運用だと、全論点に印が付く。
  - 引用した出来事が無いときにエラーにする。ツリーの検査が違反として挙げる正本を、図で確かめられなくなる。
  - HTML を作る関数を `tree_io.py` の中に置く。I/O と表示が1つのファイルに混ざり、ファイルを用意しないと表示を試せない。
- Consequences:
  - すべての論点を一度に開く手段は無い。開閉の状態は覚えない。
  - 最初の振り返りの回では、答えのある論点すべてに「この回で初めて答えた」が付く。
  - 根の問いに分析設計を結ばない限り、根の進捗は未着手と出る（Decision `progress-is-derived`）。答えがあって未着手と出るので、読み方の節に、進捗は結んだ分析設計から導くと書いた。引き継ぎの試行（Story 18.8）で誤読が出るかを見る。
  - 次の候補とツリーの決定の残りの種類は、Story 18.5 が型を足すときに表示へ足す。
  - 最も新しい回に答えを1つも書かず、決定だけを残す運用になると、1つ前の回の印が残る。決定の回を数えるかは、Story 18.5 が決定に回を持たせるときに決める。
  - 写して作った分析設計のファイルに元の `id` が残っていても、表示はファイル名の id で出す。中身の `id` との食い違いは表示では知らせない。
  - 別のテーマの分析設計のファイルが壊れていても、表示は止まらない。同じテーマの分析設計か、引用した出来事の journal が YAML として読めなければ、メッセージを出して終了コード 1 で終わる。
  - 引用した出来事を journal から読む手順（出来事はその id が指す分析設計の journal にあるときだけ数える）と、正本を読んで検証する手順は、`tree_io` に1つずつ置き、ツリーの検査と共有した。同じ id の出来事が2つあるときの扱いだけが違う。検査はエラーにし、表示は先のものを出す。
  - HTML は生成物で、pre-write hook は見ない。手で書き換えても、次の `render` が上書きする。
  - `/analysis-framing` と `/analysis-reflection` が `render` を呼ぶ手順は、この Story では足していない。framing の側は未割り当てである。

### Decision: next-candidates-are-untouched-nodes

- What: 次の候補は保存せず、正本から導く。根を除き、自分にも子孫の論点にも分析設計を結んでいない論点が次の候補である（`QuestionTree.untouched_nodes()`、`tree_io candidates`）。「論点かその下に結んだ分析設計」は `QuestionTree.designs_by_branch()` が1か所で導き、ツリーの検査も同じものを使う。`next_candidate` が持つのは、候補に添えるメモ（人に聞く問い、その答えで変わる判断、分かっていること）と、聞いてきた答えだけである。メモは `tree_io candidate` で、答えは `tree_io hear` で書く。
- Why: US-3 AC 4 は「未着手の論点を示す」としている。進捗の未着手は「分析設計を結んでいない」ことなので、根と、下の論点を調べている途中の親も未着手と出る。それらを次の候補に並べると、分析者は調べている枝をもう一度選ぶことになる。
- Criteria: US-3 AC 4、Decision `progress-is-derived`（導ける状態を保存しない）。決め手は、候補かどうかを正本1つから導けること。
- Affected modules: `src/insight_blueprint/models/tree.py`、`skills/_shared/tree_io.py`、`skills/_shared/tree_render.py`、`/analysis-reflection`、`/analysis-framing`。
- Alternatives considered: 候補かどうかの印を論点に保存する（分析設計を結ぶたびに直す手順が要る）。進捗が未着手の論点をそのまま並べる（根と、調べている枝の親が並ぶ）。
- Consequences:
  - 分析設計を結ぶと、その論点と祖先は次の候補から外れる。メモと聞いてきた答えは論点に残り、図では論点の中に出る。
  - 人に聞く問いは、答えを記録した後は変えられない。答えは前の問いへの答えだからである。答えは記録し直せる。
  - メモはツリーの検査の対象でない。`/analysis-reflection` は、読んでいないことを「分かっていること」に書かない決まりと、`connection` の値を書かない決まり（[ADR-0022](../adr/0022-connection-reaches-only-the-notebook.md)）を手順に持つ。守るのは文で、コードではない。
  - 着手した論点にも `tree_io candidate` と `tree_io hear` は通る。分析設計を起こした後に答えを聞いてきたときは、その分析設計が terminal status でなければ、`tree_io copy-hearing` をもう一度呼べば journal に写る。terminal status なら写らず、その論点に次に起こす分析設計に写す（下の Decision `hearing-is-copied-by-tree-io`）。

### Decision: hearing-is-copied-by-tree-io

- What: 次の候補の答えを journal に写すのは `tree_io copy-hearing` である。`/analysis-design` は `tree_io link` が通るたびに呼ぶ。出来事の種類は `hearing` で、本文は答えの文そのまま、`metadata` に元の論点の id、人に聞いた問い、誰に聞いたか、日付を持つ。同じ答えが journal にあれば書かない。答えが無ければ、何も書かずに終了コード 0 で返す。
- Why: 写すのをモデルに任せると、答えの文や数が打ち直しで変わりうる（#105 と同じ型）。答えは現時点の答えの根拠になるので、変わってはいけない。
- Criteria: Decision `inquiry-answer-copied-to-journal`、[ADR-0025](../adr/0025-cited-answers-checked-after-writing.md)（引用できる記録）、#105（決まりを文で書くだけでは守られない）。決め手は、写しがコードで決まること。種類は人間が決めた（[ADR-0028](../adr/0028-hearing-is-its-own-journal-event.md)）。
- Affected modules: `skills/_shared/tree_io.py`、`/analysis-design`、`/analysis-journal`。
- Alternatives considered: `/analysis-design` が journal に直接書く（文が変わりうる）。`tree_io link` の中で写す（結ぶことと journal を書くことが1つのコマンドに混ざり、結ぶだけの呼び出しが journal を作る）。
- Consequences:
  - コードが journal を書く。これまで journal を書くのは skill だけだった。出来事の id の採番と追記は `design_io.append_journal_event` が持ち、journal が無ければ `/analysis-journal` と同じ見出しで作る。最上位が mapping でない journal と、`events` が list でない journal には書かず、エラーにする（レビューの指摘。読めたふりをして上書きすると、出来事が消える）。
  - 写すのは、答えを持つ論点そのものに結んだ分析設計の journal だけである。親の論点で答えを聞き、その子の論点に分析設計を起こすと、答えは journal に写らず、引用できない。この Story では塞いでいない。
  - 答えを記録し直してから写すと、新しい出来事が足される。前の出来事は消えない。
  - 写し先の分析設計が terminal status なら、写さずにエラーにする（人間の判断、2026-11-21、[PR #128 のコメント](https://github.com/etoyama/insight-blueprint-skills/pull/128#issuecomment-7056358577)。Story 18.9 の最初のコミットで入れた）。結論を出して閉じた分析の journal に、あとから人の答えを足すと、閉じた時点の記録が変わるため。答えは論点に残り、その論点に次に起こす分析設計の `copy-hearing` で写る。同じ答えが既に journal にあるときと、写す答えが無いときは、terminal status でも今までどおり終了コード 0 で返す（書くものが無いので、エラーにしない）。
  - 写した出来事は `evidence_refs` と `parent_event_id` を持たない。
  - 論点ツリーの側が元である。journal の出来事を手で直しても、論点ツリーの答えは変わらない。
  - ツリーの検査は `hearing` の数を記録にある数として通す。答えを本当に人から聞いたかは、コードでは確かめない。図は、引用した出来事がすべて `hearing` の文に「人に聞いた答えによる」と添える（人間の判断、2026-11-21。[ADR-0028](../adr/0028-hearing-is-its-own-journal-event.md) の Negative）。

### Decision: decision-carries-the-last-round-and-is-tied-to-its-node

- What: `deepen`・`return`・`close` の回は、決めた時点の最後の振り返りの回（`current_round()`）を `tree_io decide` が振る。呼ぶ側は回を渡さない。表示の「最も新しい回」は答えの回の最大値のままで、決定の回は数えない。`node_id` は次に調べる論点を指し、`close` では区切った論点を指す。直前の決定の論点を今の論点として、`deepen` は今の論点かその子孫、`return` はそれ以外、`close` は今の論点だけを指せる。最初の決定は `start` でなければならない（人間の判断、2026-11-21、Story 18.5 のセッション）。
- Why: Decision `start-is-the-only-decision-kind-for-now` は、回の決め方を Story 18.5 に残した。決定は追記だけで直せないので、種類と論点が食い違う決定は、書けないようにしておく。
- Criteria: Must は「回を呼ぶ側に決めさせない」（Decision `one-answer-call-is-one-round`）。Want は「決定が、どの答えを見て下したものか辿れる」（高、Claude の推測）、「『この回で変わった』の印が誤読されない」（中、Claude の推測）、「回の意味と既存の正本を変えない」（中、Claude の推測）。決め手は1つめと3つめ。人間が推奨を採った。
- Affected modules: `src/insight_blueprint/models/tree.py`、`skills/_shared/tree_io.py`、`skills/_shared/tree_render.py`、`/analysis-reflection`、`/analysis-framing`。
- Alternatives considered: 決定も回を進める（答えが変わらない振り返りでは、決定の回に対応する答えが無い。18.4 と 18.6 の回の読みを直すことになる）。決定から回を外す（どの答えを見た決定かを日時で突き合わせることになる）。
- Consequences:
  - 同じ回に決定が2つ以上並びうる。並びの順が時系列である。
  - 印は回を名指して出す（「回 N で変わった」「回 N で初めて答えた」）。答えが1つも変わらない振り返りの後も、印は前の回のまま残るが、どの回のことかは読める。
  - `start` の無いツリーには、ほかの決定を書けない。`/analysis-reflection` は `/analysis-framing` を案内する。
  - `close` の後も決定を足せる。次の決定は、区切った論点を今の論点として検証する。
  - 別の枝へ移るのも、親に戻るのも `return` である。2つを分けていない。
  - Story 18.9 の「最新のツリーの決定が指す論点から再開する」は、`decisions` の最後の要素の `node_id` で読める。
  - 図は、決定に「回 N の振り返りの後」と添える。振り返りの前の決定（回 0）には「振り返りの前」と添える。`/analysis-framing` が残した決定も、その時点の最後の回を持つ。

### Decision: framing-rerun-asks-for-the-next-node

- What: `/analysis-framing` の再実行は、決定のあるツリーでは必ず KEEP ゲート（Step 4d）を通る。最新の決定が指す論点を、進捗と結んだ分析設計を添えて示し、次の候補を並べて、次に設計する論点を分析者に聞く。答えるまで Framing Brief を出さない。選んだ論点に分析設計がもう結んであれば、もう1本起こすかを確かめる。最新の決定と違う論点なら、理由を聞いて `deepen` か `return` を残す。同じ論点なら決定を書かない。`close` は書かない（人間の判断、2026-11-21、Story 18.5 のセッション）。
- Why: Story 18.2 の手動確認で、再実行した Framing Brief が、分析設計を結び済みの `start` の論点を、聞かずに次の論点として出した（[#126](https://github.com/etoyama/insight-blueprint-skills/issues/126) のコメント）。決定を残さずに論点だけ変えると、Framing Brief の論点と最新の決定がずれ、`/analysis-auto` が古い論点から再開する（US-8 AC 1）。
- Criteria: Must は「次の論点を分析者に聞かずに出さない」（人間の判断、#126）。Want は「次の論点の出どころが1つになる」（高、Claude の推測）と「分析者の手間」（中、Claude の推測）。決め手は前者。人間が推奨を採った。
- Affected modules: `/analysis-framing`（Step 4c・4d・5a）。
- Alternatives considered: 聞くが決定は残さない（最新の決定とずれる）。framing では選ばせず、`/analysis-reflection` で決定を残すよう案内する（論点を変えるだけのために横断の振り返りを回す）。
- Consequences:
  - 決定を書く skill が、`/analysis-reflection` と `/analysis-framing` の2つになる。書く道は `tree_io decide` ひとつで、種類と論点の関係はモデルが確かめる。
  - Step 4c の「既に決定があれば `tree_io decide` を呼ばない」という手順は、「2つめの `start` を送らない」に改めた。
  - 止めるのは手順で、コードではない。`/analysis-design` は、Framing Brief の `node_id` が最新の決定の論点かどうかを確かめない。

### Decision: stale-violations-are-marked-on-the-page

- What: 後から違反になった答えは、取り下げとして保存しない。`tree_io render` がツリーの検査を回し、今の答えに違反がある論点に「記録と合わない答え」の印を出す。その論点では、答えの文を今の答えとして出さず、違反の中身を出して、文は閉じた開閉の中に畳む。検査ができないとき（同じ id の出来事が2つある、など）は、図を作ったうえで、答えを記録と照らせなかったことを図の上に出す（人間の判断、2026-11-21、Story 18.5 のセッション）。
- Why: Decision `answers-are-checked-before-they-land` は、直せない古い違反の答えが今の答えとして正本と HTML に残る穴を残した。HTML だけを渡された人は、記録と合わない答えを今の答えとして読む。
- Criteria: Must は「既にある答えを書き換えない」（US-3 AC 3）。Want は「HTML を読む人に、違反の答えが今の答えとして届かない」（高、Claude の推測）、「正本の形と不変条件を増やさない」（中、Decision `progress-is-derived`）、「この Story に足す量」（中、Claude の推測）。決め手は2つめ。違反は正本と journal から導けるので、進捗と同じく保存しない。人間が推奨を採った。
- Affected modules: `skills/_shared/tree_io.py`（`render`）、`skills/_shared/tree_render.py`。
- Alternatives considered: 文を持たず理由を持つ答えを追記して取り下げを表す（`Answer` の不変条件が変わり、journal が後で直っても取り下げが残る）。`close` の決定で取り下げを表す（`close` は巡回を区切る決定で、意味が2つになる）。この Story では扱わない（穴が残る）。
- Consequences:
  - 正本の YAML を直接読む人には、印が見えない。その答えは今の答えのままである。`tree_check` を回せば分かる。
  - journal が直って違反が消えれば、次の `render` で印も消える。
  - `render` をし直すまで、HTML は古いままである。`/analysis-reflection` は振り返りのたびに `render` する。
  - 印が付くのは古い違反に限らない。正本に直接書いた答えの違反にも付く。
  - `tree_render` は違反を引数で受け取り、検査はしない。`tree_io render` が `tree_check` を読み込む。`tree_io answer` と同じく、関数の中で読み込む。
  - `/analysis-reflection` の「Stale answers」の扱いは変えていない。直せない答えは示さず、ほかの論点を届ける。

### Decision: an-empty-get-says-where-it-looked

- What: `tree_io get` は、論点ツリーが見つからないとき、今までどおり `{}` を終了コード 0 で返す。あわせて、見た正本の絶対パスを stderr に1行出す（`tree_io: no tree at {path}`）。`/analysis-framing` の Step 4a と `/analysis-reflection` の Step T1 は、そのパスがプロジェクトの `.insight` の下かを確かめ、`tree_io` の前に `cd` しない（人間の判断、2026-11-21、Story 18.5 のセッション）。
- Why: Story 18.5 の手動確認で、モデルが plugin のルートへ `cd` してから `tree_io get` を呼んだ。ラッパーは `CLAUDE_PROJECT_DIR` が無ければ `$PWD` をプロジェクトとして扱うので、plugin の中の `.insight/` を読み、`{}` を返した。skill は、あるツリーを「無い」と答えて終わった。「まだ無い」と「見ている場所が違う」が同じ出力だった（[#88 のコメント](https://github.com/etoyama/insight-blueprint-skills/issues/88#issuecomment-7054224892)）。
- Criteria: Must は「新しいテーマで framing がツリーを作れる」（US-1 AC 1）。Want は「無いと場所が違うを出力から見分けられる」（高、Claude の推測）、「間違った場所への書き込みが止まる」（中、Claude の推測）、「直す手順とテストの量、ほかの `*_io` との揃い方」（中、Claude の推測）。決め手は1つめと3つめ。人間が推奨を採った。
- Affected modules: `skills/_shared/tree_io.py`（`get`）、`/analysis-framing`、`/analysis-reflection`。
- Alternatives considered: 見つからなければ終了コード 1 にする（「無い」と「場所が違う」はやはり同じ結果になる。手順2つを書き換え、`design_io`・`catalog_io` の `get` と揃わなくなる）。触らずに #88 に任せる（それまで同じ取り違えが起きる）。
- Consequences:
  - 原因はラッパーにある。この決定は見分ける手がかりを足すだけで、間違った場所への書き込み（plugin の中の `.insight/` への `tree_io create`）は止めない。#88 で扱う。
  - stderr の1行をモデルが読み飛ばせば、気づかない。止めるのは手順で、コードではない。
  - `design_io get` と `catalog_io get` は変えていない。同じ取り違えは、そちらでも起きうる。

### Decision: tree-upload-is-its-own-skill

- What: 論点ツリーの HTML を Artifact で渡す手順は、新しい skill `/tree-upload` に置く。細部は次のとおり。
  - `disable-model-invocation: true` にする。`/analysis-framing` と `/analysis-reflection` は HTML のパスを出した後に `/tree-upload {theme_id}` を1行で案内し、起動はしない。
  - 送る前に `tree_io render` を通し、それが出力した `path` のファイルだけを送る。モデルは HTML を書かず、写しも作らない。
  - 毎回新しい Artifact を作る。前の Artifact を更新しない。Artifact の URL を覚えると、承認を覚えない決まり（ADR-0016）と別の状態を持つことになるため。
  - `theme_id` は `^[A-Z][A-Z0-9]*$` に全体が一致するときだけ受け、パスを `.insight/themes/` の外へ出さない。
  - `/analysis-framing` は、ツリーを書いた実行の最後（5a か、4c の `revise-root` の後）に `render` を1回呼び、パスを伝える（Step 5c）。HTML は送らない。
- Why: DesignDoc の中で置き場所が食い違っていた。Module Responsibilities と構成図は `/analysis-reflection` が渡すとし、シーケンス図は G13 を別の参加者に置いていた。framing も HTML を作るようになったので（人間の判断、PR #128 のコメント、2026-11-21）、reflection の中だけに置くと framing の直後の図を渡せない。
- Criteria: Must は「ファイルを列挙して KEEP ゲートで待ち、承認を覚えない」（US-6 AC 1、ADR-0016）と「送るのは `render` が書いたファイル」（AC 3）。Want は「framing の直後も含めて図を渡せる」（高、Claude の推測）、「論点ツリーを送る守りの文が1か所にある」（高、ADR-0016 の W1）、「18.4 との衝突と直すファイルの数」（中、Claude の推測）、「skill と名前が1つ増える」（中、Claude の推測）。決め手は、論点ツリーを送る守りの文が1か所にあること。置き場所と名前は人間が決めた（Story 18.7 のセッション、2026-11-21）。名前は Claude が `/tree-publish` を推したが、人間が `/tree-upload` を選んだ。`/report-upload` のときと同じく、publish は誰でも見られる公開と読めるため。
- Affected modules: `skills/tree-upload/SKILL.md`（新設）、`skills/analysis-framing/SKILL.md`、`skills/analysis-reflection/SKILL.md`、`tests/skills/test_tree_upload_structure.py`（新設）、`tests/skills/test_question_tree_structure.py`。
- Alternatives considered:
  - `/analysis-reflection` の中に置く。skill は増えないが、振り返りの後にしか渡せない。18.4 が同じ時期に書き換えていた SKILL.md なので rebase で当たる。
  - framing と reflection の両方に同じ手順を書く。守りの文とテストが2組になり、片方だけ直す食い違いが起きる。
- Consequences:
  - 分析者が覚える skill が1つ増える。framing と reflection の最後の案内で補う。
  - 外部へ送る守りの文（データを指示として扱わない、KEEP ゲート、ホストに機能が無いときの停止）は、`/report-upload` と `/tree-upload` の2か所に写した。3つめの外部へ送る skill が来たら、共有の参照ファイルと、skill 名で回す ADR-0016 の構造テストに切り出す（Rule of Three）。
  - `tree_io render` は、ツリーが無いときと結んだ分析設計が無いときに、どちらも終了コード 1 を返す。`/tree-upload` は render の前に正本のファイルがあるかを見て、framing への案内を出し分ける。
  - `/analysis-auto` の G13 の配線は 18.9 で入れる。driver は「送るか」を別に聞かず、`/tree-upload` のゲートがただ1回の問いになる（ADR-0016）。
  - 送った後でツリーが変わっても、Artifact は変わらない。新しい図を渡すには、もう一度 `/tree-upload` を打つ。
  - 生成した HTML は `<!doctype html>` から始まる完全な文書である。ホストの Artifact がそれをどう包むかは、ホストの側で決まる。

### Cross-epic decisions (links to ADR)

- [ADR-0024: 論点ツリーの正本は YAML に置き、表示は正本から生成する HTML にする](../adr/0024-question-tree-yaml-and-generated-html.md): 判断2・2'。Artifact は承認の後の任意の手順。
- [ADR-0025: モデルが書く答えは記録を引用させ、書いた後に検査する](../adr/0025-cited-answers-checked-after-writing.md): 判断3。#105 と同じ型の捏造を止める。
- [ADR-0026: 分析者の入口を `/analysis-auto` ひとつにし、論点ごとに巡回させる](../adr/0026-analysis-auto-walks-the-question-tree.md): レポートはツリーの決定の前に書く。研究では上流に `/rq-problematization` を置く。
- [ADR-0028: 人に聞いた答えは、journal の出来事 `hearing` として残す](../adr/0028-hearing-is-its-own-journal-event.md): 次の候補の答えを journal に写すときの種類。`observe` にするとレポートの Results に混ざる。

## Test Design Matrix

| Story \ Layer | Unit | Integration | E2E |
|---|---|---|---|
| Story 18.1 | ✓ | ✓ | — （skill を通らない） |
| Story 18.2 | ✓（`tests/test_tree_models.py` の `TestTreeDecision`、`tests/test_tree_io.py` の `TestDecide`） | ✓（`tests/skills/test_question_tree_structure.py`。SKILL.md に書いたコマンドを `tree_io` に通す。`tests/test_validate_hook.py` は決定を消す書き込みを hook が止めることを確かめる） | —（headless 実行の E2E は [ADR-0010](../adr/0010-skill-tdd-structure-tests.md) で必須にしていない。skill を通した手動確認は Story Timeline の 2026-11-21 に記録した） |
| Story 18.3 | ✓（`tests/test_tree_models.py` の `TestAnswer`、`TestValidateTree`。`tests/test_tree_check.py` の `TestNumbersIn`、`TestFindViolations`、`TestTheNumberThatWasNeverRecorded`） | ✓（`tests/test_tree_check.py` の `TestCheckTheme`・`TestMain` は正本と journal のファイルを読ませる。`tests/integration/test_bin_wrappers.py` は `bin/tree_check` を別の cwd から通す。`tests/test_validate_hook.py` は答えを書き換える Edit を hook が止めることを確かめる） | — （CLI だけ） |
| Story 18.4 | ✓（`tests/test_tree_io.py` の `TestAnswer`。US-3 AC 2 は `test_a_parent_may_cite_an_event_of_a_design_linked_below_it` と `test_citing_a_design_linked_only_to_a_sibling_branch_writes_nothing`、AC 3 は回と根の版と変わらない答えのテスト、US-4 AC 2 は違反があれば何も書かないテスト。`tests/test_tree_models.py` の `TestCurrentRound`。`tests/test_tree_check.py` の `TestCheckTree` と、符号の `TestNumbersIn`・`TestFindViolations`。`tests/test_tree_models.py` の `TestValidateTree` は答えを回で名指す） | ✓（`tests/skills/test_theme_reflection_structure.py`。SKILL.md に書いた `tree_io answer` を、合成の正本と journal に通す。US-3 AC 1 は `TestThemeReflectionWritesCitedAnswers`、AC 2 は `TestParentAnswersCiteDescendants`、AC 3 は `TestAnswersGoThroughTreeIo`、US-4 AC 2 は `TestViolationsAreFixedBeforeTheAnalystSeesThem`。`tests/test_tree_io.py` の `TestCli` は終了コード 0・1・3 を別プロセスで確かめる） | —（headless 実行の E2E は [ADR-0010](../adr/0010-skill-tdd-structure-tests.md) で必須にしていない。skill を通した手動確認は Story Timeline の 2026-11-21 に記録した） |
| Story 18.5 | ✓（`tests/test_tree_models.py` の `TestNextCandidate`・`TestUntouchedNodes`・`TestDecisionKinds`。`tests/test_tree_io.py` の `TestNextCandidates`・`TestHear`・`TestCopyHearing`・`TestDecideAfterTheStart`。`tests/test_tree_render.py` の `TestNextCandidates`・`TestDecisionRounds`・`TestViolatingAnswers`・`TestCheckCouldNotRun`。US-3 AC 4 は次の候補、聞いてきた答え、journal への写しのテスト、AC 5 は決定の種類と回のテスト） | ✓（`tests/skills/test_next_candidate_structure.py`。SKILL.md に書いた `tree_io candidate`・`hear`・`decide`・`copy-hearing` を、合成の正本に通す。US-3 AC 4 は `TestReflectionShowsTheNextCandidates`・`TestReflectionKeepsWhatTheAnalystHeard`・`TestDesignCopiesWhatTheAnalystHeard`、AC 5 は `TestReflectionRecordsTheDecision`。再実行の framing は `TestFramingAsksWhichNodeComesNext`。`tests/test_tree_io.py` の `TestRender` は古い違反の答えに印が付くことを、`tests/integration/test_bin_wrappers.py` は `bin/tree_io candidates` を別の cwd から確かめる） | —（headless 実行の E2E は [ADR-0010](../adr/0010-skill-tdd-structure-tests.md) で必須にしていない。skill を通した手動確認は Story Timeline の 2026-11-21 に記録した） |
| Story 18.6 | ✓（`tests/test_tree_render.py`。AC 1 は `TestSelfContained`、AC 2 は `TestProgress`・`TestCurrentAnswer`、AC 3 は `TestEvidence`、AC 4 は `TestMarks`・`TestHeader`、AC 5 は `TestStructure`。エスケープは `TestEscaping`） | ✓（`tests/test_tree_io.py` の `TestRender` は正本、分析設計、journal のファイルを読ませて HTML を書かせる。`tests/integration/test_bin_wrappers.py` は `bin/tree_io render` を別の cwd から通す） | —（CLI だけ。ブラウザで開いた手動確認は Story Timeline の 2026-11-21 に記録した） |
| Story 18.7 | —（SKILL.md だけ。構造テストは Integration に置く） | ✓（`tests/skills/test_tree_upload_structure.py`。AC 1 は `TestApprovalGate`、AC 2 は `TestArtifactIsOptional`、AC 3 は `TestTheRenderedFileIsTheOnlySource`。framing の render は `tests/skills/test_question_tree_structure.py` の `TestFramingRendersTheTree` が、SKILL.md に書いたコマンドを `tree_io` に通す） | —（headless 実行の E2E は [ADR-0010](../adr/0010-skill-tdd-structure-tests.md) で必須にしていない。Artifact へ送った手動確認は Story Timeline の 2026-11-21 に記録した） |
| Story 18.8 | — （試行の手順） | ☐ | ☐ |
| Story 18.9 | — （SKILL.md だけ。構造テストは Integration に置く） | ☐ | ☐ |

完了時に ✓ を付ける。このマトリクスが Epic PR のレビューゲート。

## Story Timeline

- 2026-11-20 — PRD の改訂と DesignDoc の初版（判断1〜5）。
- 2026-11-20 — 入口を `/analysis-auto` ひとつにし、シーケンス図を1枚に統合（ADR-0026、US-8）。
- 2026-11-20 — 初版に合意。Story 18.1〜18.4、18.6〜18.8 を起票（#119〜#125）。
- 2026-11-20 — PR #117 を main にマージ。未決事項2つを決め（判断A・B）、Story 18.5 と 18.9 を起票（#126、#127）。
- 2026-11-20 — Story 18.1 completed: 型名を決め（`NextCandidate`・`Answer`・`Aim`）、論点ツリーのモデル、`validate_tree`、`tree_io`（create・add-node・link・revise-root・get・progress）、`*_tree.yaml` を検証する pre-write hook、`bin/tree_io` を入れた。
- 2026-11-20 — Story 18.2 completed: `/analysis-framing` の Step 4・5 が根の問い、到達点、第一階層の論点を分析者と決めて `tree_io` で書き、最初に調べる論点と理由をツリーの決定（`start`）として残す。Framing Brief に `theme_id` と `node_id` を載せ、`/analysis-design` が `tree_io link` で結ぶ。`TreeDecision` と `tree_io decide` を足した。レビュー（thermos）の指摘で、2つめの `start` をモデルで拒むようにし、再実行の手順の食い違いを直した。`tree_io render` は Story 18.6 で入るので、framing はまだ HTML を作らない。
- 2026-11-21 — Story 18.2 を手動で確認した。合成データのプロジェクトにプラグインを読み込み、headless の Claude Code（sonnet）で `/analysis-framing` と `/analysis-design` を実行した。新しいテーマでは、論点ツリーの正本に根の版 1 と `start` の決定が1件書かれた。`/analysis-design` は `tree_io link` で分析設計を論点に結び、`node_id` の無い Framing Brief では結ばずに作った。根の変更では、意味の変わる変更に「上げない」と答えると1回だけ聞き直し、2回目の答えに従った。言い換えは1回の確認で済んだ。pre-write hook は、決定を消す Edit と前の根の版を変える Edit を拒んだ。意味の変わる変更に「上げる」と答える経路は、skill を通しては確かめていない。
- 2026-11-21 — 手動確認で、根の変更の聞き方が分析者の答えを誘導していると分かった。`/analysis-framing` の Step 4c を直し、版を上げるかは両方の答えとその結果を並べて聞き、skill の読みは分析者が答えるまで出さないようにした。同じやり方で、意味の変わる変更と言い換えの2本を再実行して確かめた。
- 2026-11-21 — Story 18.3 completed: 現時点の答えの型（`Answer`・`AnswerStatement`・`StatementKind`）と `answers` を入れ、答えを追記だけにした。追記だけの比較（根の版、ツリーの決定、現時点の答え）は1つにまとめた。ツリーの検査（`tree_check`、`bin/tree_check`）は、引用した出来事が無い、引用先の分析設計が論点か子孫に結んでいない、文の数が引用した出来事の本文に無い、の3つを違反として挙げる。#105 と同じ型（2つの出来事の数から作った比）を合成シナリオで違反にした。合成のプロジェクトに `bin/tree_check` を通して、違反の出力と終了コード 1、正本が変わらないことを確かめた。レビュー（thermos）の指摘で、別の分析設計の journal に書いた出来事を引用の根拠に数えないようにし、検査できない場合は必ず終了コード 2 にした。18.3 を先にする決定は人間がした（PR #128 のコメント、2026-11-21）。
- 2026-11-21 — Story 18.6 completed: `tree_io render` が、正本から自己完結の HTML（`.insight/themes/{theme_id}_tree.html`）を作る。HTML を作る純関数は `skills/_shared/tree_render.py` に置いた。script は書かず、開閉は `<details>` で行う。各論点に進捗と現時点の答えを文字で出し、開くと答えの各文、引用した出来事、前の回の答え、結んだ分析設計が出る。最も新しい回で変わった答えと、根の変更前の答えに印を付ける。分析設計の派生は別の節に出す。合成のプロジェクトで `bin/tree_io render` を2回通し、同じバイト列になることを確かめた。built-in browser で開き、script・画像・外部への要求が0件であること、論点の開閉、出来事の本文に入れた `<script>` が文字として出ること、幅 375px で横にはみ出さないこと、暗い配色でも読めることを確かめた。答えを書く手段はまだ無いので、答えは合成の正本に直接書いた。
- 2026-11-21 — Story 18.6 のレビュー（thermos）の指摘を直した。分析設計をファイルの中の `id` で引いていたので、写して作った分析設計があると進捗と題が `tree_io progress` と食い違った。ファイル名の id で引くようにした。別のテーマの壊れた分析設計で表示が止まらないようにし、読めない YAML では traceback でなくメッセージを出す。引用した出来事を読む手順と正本を読む手順は、ツリーの検査と共有した。表示の言葉と読み方の説明は1つの表から出すようにした。HTML に文字がエスケープされずに入る経路と、外部を読む経路は見つからなかった。
- 2026-11-21 — Story 18.4 completed: `/analysis-reflection` はテーマの id を渡されると、論点ごとに、結んだ分析設計の journal を読んで現時点の答えを書く。文はそれぞれ種類と引用を持ち、親の論点は子孫の分析設計の出来事を引用する。答えを書く道は `tree_io answer` だけで、検査を通るまで正本に書かない。1回の呼び出しが1つの振り返りの回になり、変わらない答えは書かない。書いた後に `tree_check` を回し、`tree_io render` で HTML を作り直す。ツリーの検査は、はっきりした符号を数の一部として比べるようにした。追記だけの比較は、答えを回で名指す。人間がこのセッションで3つを決めた（検査を通るまで書かない、答えは回で名指す、符号の線引きを広げる）。レビュー（thermos）の指摘で、`tree_io answer` の入力を型で受け、読めないファイルを終了コード 1 の文で返し、直せない古い違反を「Stale answers」として示す出口を足した。分析設計1つの振り返りは変えていない。
- 2026-11-21 — Story 18.4 を手動で確認した。合成データのプロジェクト（論点4つ、分析設計2つ）にプラグインを読み込み、headless の Claude Code（sonnet）で `/analysis-reflection LIB` を4回実行した。1回目は、3つの論点に回 1 の答えが書かれ、根の問いの答えは子の分析設計の出来事を引用し、分析設計の無い論点は答えを持たなかった。2回目は、割合と倍率を答えに入れるよう頼んだが、計算せず「記録されていない」と未判別の文で書いた。3回目は、journal に出来事を1つ足すと、その論点と根だけが回 3 になり、変わらない論点は回 2 のまま変化なしと示された。4回目は、最初の呼び出しに計算した割合（65.5%）をわざと入れさせた。`tree_io answer` は終了コード 3 で違反を返して何も書かず、skill はその文を除いて送り直し、除いた文と違反を分析者に示した。正本に 65.5 は残らなかった。4回目だけがレビューの指摘を直した後の手順で、1〜3回目はその前の手順で実行した。根の版が上がった後の書き直し（`restated`）と、古い違反（Stale answers）の経路は、skill を通しては確かめていない。長い payload をシェルの文字列で渡すとホストが拒むことがあったので、一時ファイルから渡す書き方を手順に足した。
- 2026-11-21 — Story 18.7 completed: 論点ツリーの HTML を Artifact で渡す手順を、新しい skill `/tree-upload` に置いた（置き場所と名前は人間の判断）。`tree_io render` が書いたファイルだけを列挙し、KEEP ゲートで承認を待ち、承認は覚えない。Artifact が無いホストでは何も送らず、手元のパスを伝える。`/analysis-framing` は、ツリーを書いた実行の最後に `render` を呼んでパスを伝える（Step 5c）。レビュー（thermos）の指摘で、ツリーの有無を stderr の文言でなく正本のファイルで分け、framing の `render` に `</dev/null` を付けた（#129）。
- 2026-11-21 — Story 18.7 を手動で確かめた。合成のプロジェクトで framing の 5a・5c のコマンドを `bin/tree_io` に通し、`render` を2回通して同じバイト列になること、問いに入れた `<script>` が文字として出ること、ツリーの無いテーマと `../x` が終了コード 1 で何も書かないことを確かめた。人間の承認を得て、生成した HTML を手を加えずに Artifact へ送った。ホストはページを自分の雛形で包み、完全な文書が入れ子になる。包んだ後の HTML を手元で開くと、ページのスタイルと題が効き、script は0件で、論点の開閉と幅 375px の表示も崩れなかった。claude.ai の上で直接開く確認と、暗い配色の確認はしていない（組み込みブラウザが claude.ai にサインインしていない）。
- 2026-11-21 — Story 18.5 completed: `/analysis-reflection` は現時点の答えの後に、次の候補（根を除き、自分にも下の論点にも分析設計を結んでいない論点）を示し、人に聞く問い、その答えで変わる判断、分かっていることを添える。分析者が聞いてきた答えは、誰に聞いたかと日付を添えて残す。KEEP ゲートで、深める・親に戻る・区切ると理由、次に調べる論点を聞き、ツリーの決定として残す。`/analysis-design` は分析設計を論点に結んだ後、聞いてきた答えを journal の `hearing` として写す。再実行した `/analysis-framing` は、次に設計する論点を必ず聞く。図には次の候補、決定の回、記録と合わない答えの印が出る。人間がこのセッションで4つを決めた（`hearing` の種類、決定の回、再実行の framing、古い違反の扱い）。
- 2026-11-21 — Story 18.5 のレビュー（thermos）の指摘を直した。`tree_io copy-hearing` は、最上位が mapping でない journal を空と読んで上書きし、出来事を消していた。`events` が list でない journal では traceback を出していた。どちらも書かずにエラーにする。journal への追記は `design_io.append_journal_event` に移した。「論点かその下に結んだ分析設計」の計算は、次の候補とツリーの検査で別々に持っていたので、モデルの1か所に寄せた。図は、振り返りの前の決定に「回 0 の答えを見て」と出していたので、「振り返りの前」に直した。`deepen` と `return` を論点から導く案は採らなかった（種類は分析者が選ぶ）。
- 2026-11-21 — Story 18.5 を手動で確認した。合成データのプロジェクト（論点4つ、分析設計1つ、`connection` を持つデータソース1つ）にプラグインを読み込み、headless の Claude Code（sonnet）で5回実行した。(1) 答えを渡さない `/analysis-reflection LIB` は、回 1 の答えを書き、次の候補を2つ示して、聞いてきた答えと決定の2つを聞いて止まった。決定は書かなかった。人に聞く問いは、データで答えられない論点にだけ付いた。`connection` のパスは正本にも HTML にも入らなかった。(2) 答えを渡した2回目は、聞いてきた答えを誰に・いつと一緒に残し、`return` の決定を回 1 で書いた。(3) 答えを渡さない `/analysis-framing LIB` の再実行は、最新の決定の論点と次の候補を並べて聞き、Framing Brief も決定も出さずに止まった。(4) `/analysis-design` は分析設計を論点に結び、聞いてきた答えを journal の `hearing` として1字も変えずに写した。(5) 再実行で別の論点を答えると、理由つきの `return` を残し、その論点の `node_id` で Framing Brief を出した。図には次の候補、決定と回、聞いてきた答えが出た。journal の数を書き換えて `tree_io render` を通すと、その論点に「記録と合わない答え」の印が出て、答えの文は畳まれた（skill は通していない）。最初の1回は、headless のセッションが `.insight` を見つけられずに終わった。同じ場所でやり直すと読めたので、原因は分かっていない。`deepen` と `close` の決定、結び済みの論点を選んだときの確認、`tree_io` が決定を拒んだときの聞き直しは、skill を通しては確かめていない。
- 2026-11-21 — 手動確認の最初の1回の原因を確かめた。モデルが plugin のルートへ `cd` してから `tree_io get` を呼び、ラッパーが `$PWD` をプロジェクトとして plugin の中の `.insight/` を読んでいた。再現の手順と原因は #88 に書いた。ラッパーは直していない。`tree_io get` は、見つからないときに見た正本のパスを stderr に出すようにした（人間の判断）。push の自動セキュリティレビューが、`hear` で書いた答えを写して引用すれば数の検査を通せると指摘した。人間の判断で、検査は変えず、引用がすべて `hearing` の文に図で「人に聞いた答えによる」と添えるようにした。残る穴は ADR-0028 の Negative に書いた。
