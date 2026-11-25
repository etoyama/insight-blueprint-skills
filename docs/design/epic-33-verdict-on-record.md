# Epic 33: 検証の判定を記録で守る

## Background

本書がこの Epic の要求と背景の正本（[FLOW-0001](../adr/flow/0001-designdoc-owns-requirements.md)）。
Epic issue（[#242](https://github.com/etoyama/insight-blueprint-skills/issues/242)）には要約と本書へのリンクだけを置く。

- 解く課題: Epic 32 は「検証は基準を先に固定して判定する」と決めた。しかし、記録の上ではその決まりを破れる。分析者と読み手は、判定がどの基準で出たか、基準が結果の前に置かれたかを、記録から確かめられない。
  - 課題1: verdict の指標は基準の線を1本（`threshold`）と合否（`pass`）しか持てない。基準が「2.0 日以上なら支持。1.0 日未満なら棄却。その間は結論しない」のとき、棄却の線が表に出ない。`pass: false` が棄却なのか、結論しないなのかも読めない（[#235](https://github.com/etoyama/insight-blueprint-skills/issues/235)）。
  - 課題2: verdict の区間は `confidence_interval` という名前で、種類を書く場所が無い。ベイズの HDI を入れると、分析ノートは「信頼区間」と出す（[#237](https://github.com/etoyama/insight-blueprint-skills/issues/237) の F17）。
  - 課題3: 群ごとに値を持つ指標は群を名前に入れて平たく並べるしかない。分析ノートの指標の表が101行になった（#237 の F09）。
  - 課題4: 分析を始めた後でも、検証仮説と判定の基準と意図を書き換えられる。結果の review で `in_review` に戻すと、Epic 32 が入れた意図の固定も外れる（[#234](https://github.com/etoyama/insight-blueprint-skills/issues/234)）。
  - 課題5: reflection が結果の review として勧める `/analysis-review` は、分析設計の項目しか見ない。notebook が基準を正しく写したかを、どの観点も拾わない（#237 の F19）。
  - 課題6: 記録した review コメントは `{id}_reviews.yaml` にだけ残る。読み手には判定だけが届く（#237 の F21）。
- PRD の要件: [docs/PRD.md](../PRD.md) のコアバリュー「notebook 契約 & lineage」「分析設計」「journal / reflection」と、非機能要件「分析者に届く数と結論は、記録に書いてあるものに限る」。
- 既存手段が不十分な理由: Epic 32（[ADR-0048](../adr/0048-intent-decides-the-form-and-the-end-of-a-design.md)、[ADR-0050](../adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md)）は、基準を書く場所と意図の固定を決めた。固定は状態だけを見るので、結果の review で外れる。verdict の形は Epic 32 の前のままである。

### 起票の経緯

Epic 32 の Epic PR の前に、人間が ib-notebook の実データ（テーマ FRN）で使用感を確かめた（2026-11-25）。
そこで見つかった気づきのうち、Epic 32 の範囲の外のものが #235 と #237 になった。#234 は Story 32.1 のレビューで見つかり、人間が後で決めると言った。
人間は 2026-11-25 に、#235・#234 と、#237 の F21・F19・F17・F09 を1つの Epic にまとめると決めた。

### 前提にした事実（main 09fc48a、2026-11-25）

- verdict を書くのは notebook だけである。notebook は契約（`skills/analysis-notebook/references/notebook-contract.md`）の文に従って AI が生成する。`src/insight_blueprint/validate.py` は verdict を検査しない。
- verdict を読むのは `skills/_shared/design_note_read.py` の `_metric` だけである。読んだ値は `VerdictMetric`（`skills/_shared/design_note.py`）になり、分析ノートの表とレポートの表（`skills/_shared/theme_report.py`）が出す。読み手は計算しない（[ADR-0013](../adr/0013-verdict-metric-optional-items.md)）。
- 保存済みの verdict には次の形がある。`metrics` が無い。`p` と `p_value` のどちらかを持つ。任意の3項目が無いか、欠けている。探索なのに `threshold` と `pass` を持つ。`threshold` が数・文字・その他の JSON である。`pass` が真偽でない。`mixed` と意図なしの分析設計の verdict である。
- ib-notebook の FRN の verdict 5本は、`value`・`threshold`（数）・`pass`・`confidence_interval`・`sample_size` だけを持つ（実物を読んだ）。FRN-H05 の guardrail は `pass` だけを持つ。
- FRN-H05 の基準は「ρ の 95% HDI の上端が 0.70 未満なら支持。HDI の下端が 0.90 を超えるなら棄却。それ以外は結論できず」である。線に当てるのは、値ではなく区間の端である。
- `analyzing` は review の承認で入る状態で、notebook を回す前に付く。結果の review（[ADR-0029](../adr/0029-analyzing-reaches-conclusion-directly.md)）は `analyzing → in_review` に戻す。
- `validate_update`（`validate.py`）は、意図と形の変更だけを状態で止める。変えられるのは `in_review` と `revision_requested` の間である。検証仮説・背景・指標の `comparison` は、どの状態でも書き換えられる。
- hook（`hooks/validate-design.py`）は `design_io` と同じ `validate_update` を使う（Epic 32 の Decision `hook-checks-updates-like-design-io`）。hook が守るのは `_hypothesis.yaml` と `_tree.yaml` だけで、verdict は守らない。
- 分析は notebook を通さず、`/analysis-journal` だけでも進められる。そのとき verdict は無い。
- `{id}_reviews.yaml` を読むのは、`skills/_shared/design_io.py` と、それを呼ぶ `/analysis-revision` と `/knowledge-extract` だけである。分析ノート・レポート・論点ツリーは読まない（`grep` で確かめた）。
- `ALLOWED_TARGET_SECTIONS`（`design_io.py`）は分析設計の12項目の閉じた集合である。
- FRN の H01〜H03 は1つのコミットで入っている。分析の後に検証仮説を書き換えた記録があるかは、git の履歴からは分からない（未確認）。
- model の形は公開の契約ではない。守るのは、`.insight/` に保存済みの YAML と verdict が読めることである（[ADR-0047](../adr/0047-stop-publishing-to-pypi.md)）。

## User Stories

AC の正本はここ。

### US-1: 読み手が、検証の基準の2本の線と指標の判定を表から読める

読み手として、判定がどの基準で出たかを確かめるために、支持の線・棄却の線・指標の判定を、分析ノートとレポートの表で読みたい。

- [x] AC 1: notebook の契約は検証の notebook に次を書かせる。判定の基準を持つ primary の指標は、`comparison` から写した支持の線と棄却の線（`support_line`・`reject_line`。少なくとも一方）と、指標の判定（`judgment`。`supported`・`rejected`・`inconclusive` のどれか）を持つ。3つの判定を `pass` で表さない。
- [x] AC 2: secondary と guardrail の指標は、合否を `threshold` と `pass` で持つ。探索の指標は線も判定も合否も持たない。
- [ ] AC 3: 分析ノートの指標の表は支持の線・棄却の線・判定を、それぞれの列に出す。判定は「支持」「棄却」「結論しない」と出す。
- [x] AC 4: レポートの指標の表はAC 3 と同じ列と言葉で出す。
- [ ] AC 5: 新しい項目を持たない保存済みの verdict は、この Epic の前と同じ列と値で出る。

### US-2: 読み手が、区間の種類と群ごとの値を表から読める

読み手として、区間を取り違えず、群ごとの値を見比べるために、区間の種類と、群を軸にした表を読みたい。

- [x] AC 1: notebook の契約は指標の値の区間を `interval`（`kind`・`level`・`lower`・`upper`）に書かせる。`kind` は区間の種類の名前で、open string である。
- [ ] AC 2: 分析ノートとレポートの表は、区間を「区間」の列に、種類と水準を添えて出す。保存済みの `confidence_interval` は信頼区間として出す。
- [x] AC 3: notebook の契約は群ごとに値を持つ指標を、軸の名前（`by`）と群の行（`groups`）で書かせる。群の行は値と任意の項目を持ち、判定と合否を持たない。群を指標の名前に埋めない。
- [ ] AC 4: 分析ノートは群を持つ指標を指標ごとの表に出す。軸が2つで、群の行が値だけを持つときは、軸を縦と横に置く。それ以外は群の列を持つ縦の表にする。値は並べ替えるだけで、計算しない。
- [x] AC 5: レポートは群を持つ指標を AC 4 と同じ分け方で出す。

### US-3: 分析を始めた検証の分析設計は、検証仮説・判定の基準・意図が変わらない

読み手として、基準が結果の前に置かれたと信じられるように、分析を始めた後は、検証仮説と判定の基準と意図が記録の上で変わらないでほしい。

- [x] AC 1: 分析設計が初めて `analyzing` か terminal status に入るとき、分析の印（`analysis_started_at`）が分析設計に残る。印は、状態が `in_review` や `revision_requested` に戻っても残り、消す書き込みも変える書き込みも通らない。
- [x] AC 2: 分析を始めた検証・旧形式の探索・`mixed` の分析設計では、検証仮説、primary の指標の組（`target` と `comparison`。足す・消す・`tier` を変えることを含む）、意図を変える書き込みが通らない。拒む文は派生の分析設計を作るよう案内する。分析を始めた探索の分析設計では、意図と形を変える書き込みが通らない。
- [x] AC 3: 分析を始めた後でも、AC 2 に挙げていない項目（背景、secondary と guardrail の指標、説明変数、図の仕様、手法、決定の文脈、`next_action`）を変える書き込みは通る。
- [x] AC 4: 検証・旧形式の探索・`mixed` の分析設計が `analyzing` に入る書き込みは、primary の指標があり、その `comparison` が空でないときだけ通る。
- [x] AC 5: AC 1〜AC 4 は`design_io` と直書き（hook）の両方に同じ検査で効く。分析の印を持たない保存済みの分析設計は読め、状態が `analyzing` か terminal status なら、分析を始めたものとして扱う。旧形式の探索を `confirmatory` に直す例外（[ADR-0049](../adr/0049-legacy-exploration-stays-readable-and-is-marked.md) の6）は残る。

### US-4: 結果の review が notebook・verdict・図を見て、review コメントが読み手に届く

分析者として、結果の review が何を見るかを聞き返さずに分かり、notebook・verdict・図への review コメントを記録したい。読み手として、判定と並んで review コメントを読みたい。

- [ ] AC 1: review コメントは分析設計の項目に加えて、notebook・verdict・図（`notebook`・`verdict`・`figures`）を対象にできる。review batch は分析を始めた後に書かれたかどうかを自分で持つ。保存済みの `{id}_reviews.yaml` は読める。
- [ ] AC 2: `/analysis-review` は、verdict があるとき、結果の観点で読む。観点は、支持の線・棄却の線・指標の判定が `comparison` と合うか、値と判定が食い違わないか、図の軸の説明と読み方、guardrail の合否、cell ごとの責務である。批評の前に、何を読むかを分析者に言う。
- [ ] AC 3: 結果の review が `revision_requested` で終わったとき、`/analysis-revision` は、notebook・verdict・図への review コメントでは、notebook を直して回し直す道を案内する。US-3 が固定する項目への review コメントでは、分析設計を直さず、理由を付けて対応しないか、派生を作るかを選ばせる。
- [ ] AC 4: 分析ノートは「レビュー」の節に、すべての review batch を新しい順に出す。batch ごとに、時刻、分析を始めた後かどうか、review の後の状態、review コメントと対象を、書かれたとおりに出す。分析を始めた後かどうかを持たない保存済みの batch では、その表示を出さない。
- [ ] AC 5: 論点ツリーは分析設計の行に、分析を始めた後の review batch の review コメントの件数を出す。0件のときは出さない。

## Stories

Story は PM のセッションが起票した（2026-11-25）。「触る所」が重なる Story は同じ波に置かない。

| Story issue | User Story | 扱う AC | 触る所 | 前提 |
|---|---|---|---|---|
| #243 33.1 verdict の契約と読み | US-1、US-2 | US-1 AC 1, AC 2, AC 5、US-2 AC 1, AC 3 | `skills/analysis-notebook/references/notebook-contract.md`、`skills/analysis-notebook/SKILL.md`、`skills/_shared/design_note_read.py`、`skills/_shared/design_note.py` の `VerdictMetric`、`tests/integration/fixtures/sample_notebook.py`、`tests/integration/test_analysis_notebook_contract.py`、`tests/test_design_note_read.py`、`docs/UBIQUITOUS_LANGUAGE.md`、`.yomiyasu-words/` | — |
| #245 33.2 分析ノートの表 | US-1、US-2 | US-1 AC 3, AC 5、US-2 AC 2, AC 4 | `skills/_shared/design_note.py` の指標の表、`tests/test_design_note.py`、`tests/tree_io/test_render_*.py` | 33.1 |
| #246 33.3 レポートの表 | US-1、US-2 | US-1 AC 4, AC 5、US-2 AC 2, AC 5 | `skills/_shared/theme_report.py`、`tests/test_theme_report.py`、`tests/tree_io/test_report.py` | 33.1 |
| #244 33.4 分析の印と固定 | US-3 | AC 1, AC 2, AC 3, AC 4, AC 5 | `src/insight_blueprint/models/design.py`、`src/insight_blueprint/validate.py`、`skills/_shared/design_io.py` の update と遷移、`skills/analysis-design/SKILL.md`、`skills/analysis-reflection/SKILL.md`、`docs/ARCHITECTURE.md`、`tests/test_validate.py`、`tests/test_validate_hook.py` | — |
| #247 33.5 結果の review | US-4 | AC 1, AC 2, AC 3 | `skills/analysis-review/SKILL.md`、`skills/analysis-revision/SKILL.md`、`skills/_shared/design_io.py` の review batch、`src/insight_blueprint/models/review.py`、`tests/skills/`、`docs/UBIQUITOUS_LANGUAGE.md`、`.yomiyasu-words/` | 33.4 |
| #248 33.6 review コメントの表示 | US-4 | AC 4, AC 5 | `skills/_shared/design_note_read.py`、`skills/_shared/design_note.py`、`skills/_shared/tree_render.py`、`skills/_shared/tree_read.py`、`tests/test_design_note.py`、`tests/test_tree_render.py` | 33.2、33.5 |

- 波 1 は 33.1 と 33.4 で、並行で進められる。触る所は重ならない。
- 波 2 は 33.2・33.3・33.5 で、並行で進められる。33.2 と 33.3 は、33.1 が広げた `VerdictMetric` を読む。33.5 は、33.4 が入れた分析の印を review batch に写す。
- 波 3 は 33.6 である。33.2 が直した `design_note.py` に節を足し、33.5 が広げた review batch を読む。
- どの Story も `CHANGELOG.md` の `[Unreleased]` に1行足す。重なるのはそこだけである。
- 用語集は 33.1（verdict の語）と 33.5（分析の印と review の語）が直す。コード上の名前が実在することをテストが確かめるので、名前を入れた Story の後になる。分析の印の語は、33.4 が名前を入れた後の 33.5 で足す。
- PM の仮の形（6本）のままである。波ごとの本数も変わらない。

## Ubiquitous Language

この Epic で追加・変更する語。定義の正本は [docs/UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md) で、表は Story 33.1 と 33.5 が直す。
語は人間が選んだ（2026-11-25）。別の意味が浸透した既存の語を避け、分析者に見せる語は比喩を避けた。

- 追加: 支持の線（`support_line`）、棄却の線（`reject_line`）、結論しない範囲、指標の判定（`judgment`）、値の区間（`interval`）、群の行（`groups`）、分析の印（`analysis_started_at`）
- 変更: 信頼区間（値の区間の種類の1つ。保存済みの `confidence_interval` の読み方）、verdict、review（結果も対象にする）、review コメント（notebook・verdict・図を指せる）、review batch（分析を始めた後かどうかを持つ）、検証仮説（分析を始めた後は変わらない）、分析の意図（変えられる間の境目が分析の印になる）
- 変えない: しきい値と合否（secondary と guardrail の指標の、1本の線と通ったかどうか）

## Scope

[docs/PRD.md](../PRD.md) のコアバリュー「notebook 契約 & lineage」「分析設計」「journal / reflection」を前進させる。
[docs/ARCHITECTURE.md](../ARCHITECTURE.md) では、Validation library、Skill layer（`/analysis-notebook`・`/analysis-review`・`/analysis-revision`）、`tree_io render` と `tree_io report` の表示を直す。

- Epic 範囲内:
  - verdict の指標の形（[ADR-0052](../adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md)）と、分析ノートとレポートの表。
  - 分析の印と、分析を始めた後の固定（[ADR-0053](../adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md)）。
  - 結果の review と、review コメントの表示（[ADR-0054](../adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md)）。
- Epic 範囲外:
  - #237 の F03・F10・F11・F15。#237 に残す。
  - 分析設計の `comparison` を構造化すること。notebook は今までどおり文から線を写す。写しを機械で照らす検査は、写しまちがいが実際に起きてから足す（人間が決めた。ADR-0052）。
  - review コメントをレポートに出すこと。レポートは読み手に届く文書で、型と escape の検査を触ることになる。要るなら別の Epic で扱う（人間が決めた。ADR-0054）。
  - review コメントへの対応の状況（直した、直さない）を分析ノートに出すこと。
  - 探索の問いと背景を、分析を始めた後に固定すること。探索は判定しない。
  - 手法と、secondary・guardrail の指標を、分析を始めた後に固定すること。
  - review を必須にすること（ADR-0029 のまま任意）。
  - verdict 全体の判定（`results` の `hypothesis_direction`）を verdict に持たせること。
  - 実データで使ってみる段をどこで回すか。PM のセッションが人間に聞く。
- 触らない所:
  - `hooks/validate-design.py`（理由: hook は `design_io` と同じ `validate_update` を使う。検査を `validate.py` に足せば、hook の I/O は変えずに効く。verdict を hook で守らないと決めたので、守るファイルも増えない）。
  - `skills/_shared/tree_io.py` の `answer` と `tree_check`（理由: 現時点の答えの引用と検査は、review コメントを読まない）。
  - `skills/analysis-journal/SKILL.md`（理由: evidence の向きと探索の記録は Epic 32 が決めたままで、verdict の新しい項目を journal に写す決まりは足さない）。
  - Epic 32 までの DesignDoc（理由: 閉じた Epic の DesignDoc には追記しない。[ADR-0009](../adr/0009-adopt-repo-template-flow.md)）。

## Architecture

```mermaid
flowchart TD
    subgraph write["書く側"]
        NB["notebook<br/>.insight/notebooks/{id}.py"]
        DIO["design_io<br/>skills/_shared/design_io.py"]
        HOOK["hook<br/>hooks/validate-design.py"]
        RV["/analysis-review<br/>/analysis-revision"]
    end
    subgraph check["検査"]
        VAL["validate_update<br/>src/insight_blueprint/validate.py"]
    end
    subgraph records["記録（.insight/）"]
        VJ["verdict<br/>notebooks/{id}_verdict.json"]
        DY["分析設計<br/>designs/{id}_hypothesis.yaml"]
        RY["review batch<br/>designs/{id}_reviews.yaml"]
    end
    subgraph read["読む側"]
        DNR["design_note_read.py"]
        DN["分析ノート<br/>design_note.py"]
        TR["論点ツリー<br/>tree_render.py"]
        RP["レポート<br/>theme_report.py"]
    end
    CT["notebook の契約<br/>notebook-contract.md"] -.従う.-> NB
    NB -->|"支持の線・棄却の線・指標の判定・<br/>値の区間・群の行"| VJ
    DIO --> VAL
    HOOK --> VAL
    VAL -->|"分析の印と固定を確かめて通す"| DY
    RV -->|"review-batch"| DIO
    DIO --> RY
    RV -.結果の観点で読む.-> VJ
    RV -.読む.-> NB
    VJ --> DNR
    DY --> DNR
    RY --> DNR
    DNR --> DN
    DNR --> RP
    DN --> TR
    RY -->|"分析を始めた後の件数"| TR
```

- 検査は `validate_update` の1か所に足す。`design_io` と hook の両方に効く。
- verdict を読むのは `design_note_read.py` だけで、分析ノートとレポートは同じ `VerdictMetric` を出す。
- review batch を読む道が、`design_note_read.py`（分析ノートの節）と論点ツリー（件数）に増える。

## Domain Model

```mermaid
classDiagram
    class AnalysisDesign {
        <<Aggregate Root>>
        +status DesignStatus
        +analysis_intent AnalysisIntent
        +hypothesis_statement
        +metrics list~Metric~
        +analysis_started_at datetime 任意
        +form() DesignForm
    }
    class Metric {
        <<Value Object>>
        +target
        +tier MetricTier
        +comparison
    }
    class ReviewBatch {
        <<Entity>>
        +status_after DesignStatus
        +after_analysis_started bool 任意
        +comments list~BatchComment~
    }
    class BatchComment {
        <<Value Object>>
        +target_section 任意
        +target_content
        +comment
    }
    class VerdictMetric {
        <<Value Object>>
        +name
        +value
        +support_line
        +reject_line
        +judgment MetricJudgment
        +threshold
        +passed
        +interval ValueInterval
        +by
        +groups list~MetricGroup~
    }
    class MetricJudgment {
        <<enumeration>>
        supported
        rejected
        inconclusive
    }
    class ValueInterval {
        <<Value Object>>
        +kind
        +level
        +lower
        +upper
    }
    class MetricGroup {
        <<Value Object>>
        +group
        +value
        +interval ValueInterval
        +sample_size
    }
    AnalysisDesign "1" *-- "0..*" Metric
    AnalysisDesign "1" o-- "0..*" ReviewBatch : {id}_reviews.yaml
    ReviewBatch "1" *-- "1..*" BatchComment
    VerdictMetric --> MetricJudgment
    VerdictMetric --> "0..1" ValueInterval
    VerdictMetric "1" *-- "0..*" MetricGroup
    MetricGroup --> "0..1" ValueInterval
    AnalysisDesign ..> VerdictMetric : notebook が verdict に書く
```

`VerdictMetric` は verdict の JSON を読んだ値で、保存する model ではない。`MetricJudgment`・`ValueInterval`・`MetricGroup` と `after_analysis_started` は、この Epic が足す名前の案で、Story が確定する。

| 型 | 種類 | 不変条件 |
|---|---|---|
| `AnalysisDesign` | 集約ルート | 分析の印は、初めて `analyzing` か terminal status に入るときに付き、消えず、変わらない。分析を始めた検証・旧形式の探索・`mixed` は、検証仮説・primary の指標の組・意図が変わらない。分析を始めた探索は、意図と形が変わらない。検証・旧形式の探索・`mixed` は、primary の指標の `comparison` が空でないときだけ `analyzing` に入る |
| `Metric` | 値オブジェクト | `tier` が `primary` の指標の `comparison` が、判定の基準を文で持つ（ADR-0050 のまま） |
| `ReviewBatch` | エンティティ | 状態の遷移を1回だけ起こす。分析を始めた後かどうかは、書かれた時点で決まり、後から変わらない。古い batch は持たない |
| `BatchComment` | 値オブジェクト | 対象は、分析設計の12項目か、`notebook`・`verdict`・`figures` のどれか。対象を指すときは、指した内容も持つ |
| `VerdictMetric` | 値オブジェクト | 線と判定を持つのは、検証の primary の指標だけである。判定は3つの値のどれかで、それ以外は無いものとして読む。値を1つ持つか、群の行を持つかのどちらかである。数は verdict に書かれた文字のまま持つ |
| `ValueInterval` | 値オブジェクト | 4つの項目がそろって初めて有効である。保存済みの `confidence_interval` は、種類が信頼区間の値の区間として読む |
| `MetricGroup` | 値オブジェクト | 群の名前の数は、軸の名前（`by`）の数と同じである。判定と合否を持たない |

### State Diagram

分析の印が付く所と、固定が効く範囲を示す。状態の集合と遷移は Epic 32 のままで、変えない。

```mermaid
stateDiagram-v2
    state "in_review（印なし）" as in_review
    state "revision_requested（印なし）" as revision_requested
    state "analyzing（印あり）" as analyzing
    state "in_review（印あり。結果の review）" as result_review
    state "revision_requested（印あり）" as result_revision
    [*] --> in_review
    in_review --> revision_requested: review が修正を依頼する
    revision_requested --> in_review: revision
    in_review --> analyzing: 承認。分析の印が付く（検証は基準が空でないとき）
    revision_requested --> analyzing: 承認（同上）
    analyzing --> result_review: 結果の review を受ける
    result_review --> analyzing: 承認
    result_review --> result_revision: 修正を依頼する
    result_revision --> result_review: notebook を直して回し直す
    analyzing --> [*]: reflection が結論を出す
```

印なしの間は、意図と項目を直せる。印ありの間は、状態が `in_review` や `revision_requested` に戻っていても、検証仮説・判定の基準・意図は変わらない。
図は主な道だけを描いた。`in_review` と `revision_requested` から terminal status へ進む道（ADR-0029）も残り、そのときも分析の印が付く。

## Sequence Diagram

結果の review を受け、review コメントが分析ノートと論点ツリーに出るまでを示す。

```mermaid
sequenceDiagram
    actor A as 分析者
    participant RV as /analysis-review
    participant DIO as design_io
    participant VAL as validate_update
    participant FS as .insight/
    participant RS as /analysis-revision
    participant TI as tree_io render

    Note over FS: 分析設計は analyzing。分析の印あり。verdict あり
    A->>RV: /analysis-review {id}
    RV->>DIO: transition --target in_review
    DIO->>FS: 状態を in_review に書く（分析の印は残る）
    RV->>FS: 分析設計・notebook・verdict・図を読む
    RV-->>A: 何を読むかを言い、review コメントの下書きを見せる
    A->>RV: review コメントを確かめ、修正を依頼すると決める
    RV->>DIO: review-batch --status revision_requested
    DIO->>FS: review batch を書く（分析を始めた後、と持つ）
    A->>RS: /analysis-revision {id}
    RS-->>A: verdict への review コメント: notebook を直して回し直す
    RS-->>A: 検証仮説への review コメント: 対応しないか、派生を作るか
    A->>RS: 検証仮説を直したい
    RS->>DIO: update（hypothesis_statement）
    DIO->>VAL: 書き込む前と後の分析設計
    VAL-->>DIO: 拒む（分析を始めた後。派生を作る）
    DIO-->>RS: エラー
    RS-->>A: 派生を案内する
    A->>TI: tree_io render --design {id}
    TI->>FS: 分析設計・verdict・review batch を読む
    TI-->>A: 分析ノート（指標の表、レビューの節）と論点ツリー（件数）
```

- 外部境界はファイルシステム（`.insight/`）だけである。ネットワークは使わない。
- 直書きのときは、`design_io` の代わりに hook が `validate_update` を呼ぶ。拒む文は同じである。

## Decisions

### Decision: first-edition-choices-of-epic-33

- What: 初版で人間が選んだことを、3つの ADR に分けて書いた。verdict の形（ADR-0052）、分析の印と固定（ADR-0053）、結果の review と表示（ADR-0054）である。
- Why: どれも記録の形か、受け付ける書き込みを変えるので、効果がこの Epic を超える。
- Criteria: 人間の選択（2026-11-25、このセッションで直接）。範囲の判断（分析の印、固定、review の対象、表示）を先に聞き、中身の判断（verdict の形、用語）を見本と一緒に聞いた（[FLOW-0009](../adr/flow/0009-designdoc-decisions-scope-first.md)）。
- Affected modules: 上の Stories 表の「触る所」。
- Alternatives considered: 各 ADR の Decision Analysis にある。
- Consequences: 全体の整合の段で、基準を書かずに `analyzing` へ進んだ検証が固定で行き止まると分かった。人間が、`analyzing` に入る書き込みで基準が空でないことを確かめると決めた（ADR-0053 の4。ADR-0050 の5を改める）。

### Decision: a-batch-holds-whether-it-came-after-the-analysis

- What: review batch が分析を始めた後に書かれたかどうかは、batch 自身が書かれた時点で持つ。分析の印の時刻と batch の時刻を比べて導かない。
- Why: 分析の印を持たない保存済みの分析設計には、次の遷移で印が付く。その時刻は付けた時刻で、分析を始めた時刻ではない。時刻を比べると、それより前に書かれた結果の review（FRN-H05 の RB-f39e8e67）を「分析を始める前」と誤って出す。
- Criteria: 表示は記録に書いてあることだけを言う（PRD の非機能要件）。全体の整合の段で分かり、人間に知らせた。
- Affected modules: `src/insight_blueprint/models/review.py`、`skills/_shared/design_io.py`、`skills/_shared/design_note.py`、`skills/_shared/tree_render.py`。
- Alternatives considered: 時刻を比べる案（上の理由で落とした）。
- Consequences: 古い batch は分析を始めた後かどうかを出さず、論点ツリーの件数にも数えない。

### Decision: the-reader-holds-one-interval-and-the-tables-wait-for-the-kind

- What: `VerdictMetric` の `confidence_interval` を `interval`（`ValueInterval`）に置き換えた。保存済みの `confidence_interval` は、種類が `confidence` の値の区間として同じ項目に読む。分析ノートとレポートの表は、33.2 と 33.3 が列を直すまで、種類が `confidence` の値の区間だけを「信頼区間」の列に出す。
- Why: 区間を2つの項目で持つと、表が「どちらを出すか」を毎回決めることになる。1つにすれば、ADR-0052 の7（両方があれば `interval` を読む）は読み手の1か所で済む。列の見出しは 33.2 と 33.3 の領分なので、ここで直さない。直すまでの間に HDI を「信頼区間」の列に出すと、#237 の F17 と同じ誤りを Epic ブランチの上に作る。
- Criteria: Domain Model（`VerdictMetric` は `interval` を1つ持つ。人間が承認した）。PRD の非機能要件「分析者に届く数と結論は、記録に書いてあるものに限る」。決め手は後者で、出さないほうが、誤った名前で出すより害が小さい。
- Affected modules: `skills/_shared/design_note.py`、`skills/_shared/design_note_read.py`、`skills/_shared/theme_report.py`（表の1行ずつ）。
- Alternatives considered: `confidence_interval` を残して `interval` を足す（表が2つの項目を見比べることになる）。種類を問わず今の列に出す（HDI が「信頼区間」と出る）。
- Consequences: 33.2 と 33.3 が入るまで、種類が `confidence` でない値の区間・支持の線・棄却の線・指標の判定・群の行は、表に出ない。群だけを持つ指標は、値が「—」の行になる。Epic PR の前に 33.2 と 33.3 が直す。新しい項目には既定値（無い）を付けたので、表のテストが組む `VerdictMetric` は項目名の置き換えだけで通る。

### Decision: groups-that-do-not-fit-their-axes-read-as-no-groups

- What: 読み手は群の行を、全部読めるか、1つも読まないかのどちらかにする。`by` が名前の並びでない、`groups` が空か並びでない、行が object でない、行の `group` の数が `by` と違う、名前が `null` か入れ子、のどれかが1つでもあれば、その指標は `by` も `groups` も持たないものとして読む。群の名前と軸の名前は、文字・数・真偽を書かれた文字のまま読む。
- Why: 合わない行だけを落とすと、表は欠けたまま、そろった表に見える。読み手は何が落ちたかを知る手段を持たない。ADR-0013 の「項目がそろわなければ無いものとして読む」と同じ扱いにした。
- Criteria: Domain Model の不変条件（群の名前の数は、軸の名前の数と同じ）。PRD の非機能要件（届く数は、記録に書いてあるものに限る）。ADR-0013 の先例。決め手は不変条件で、破れた記録を部分的に出さない。
- Affected modules: `skills/_shared/design_note_read.py`。
- Alternatives considered: 合わない行だけを落とす（上の理由で落とした）。verdict 全体をエラーにする（1つの指標の書きまちがいで、分析ノートが作れなくなる）。
- Consequences: 行が1つ合わないと、その指標の群の値は表に出ない。指標が `value` も持っていれば、その値だけが出る。拾うのは結果の review（33.5）である。読み手は、指標が `value` と `groups` の両方を持っていても、書かれたとおりに両方を読む。どう出すかは 33.2 と 33.3 が決める。

### Decision: a-design-without-a-criterion-is-sent-by-where-it-stands

- What: 基準の無い検証を止めるときの案内を、分析設計の状態で分けた。まだ `in_review` の分析設計は `/analysis-design` で基準を書く。分析を始めた分析設計は基準を足せないので、派生を作る。契約の「`results` shape」は後者だけを言い、`/analysis-notebook` の Step 1 は両方を言う。
- Why: 33.4 の後、分析を始めた分析設計は primary の指標の組を変えられない（ADR-0053 の3）。「`/analysis-design` で書く」は行き止まりの案内になる。一方、Step 1 の検査は `analyzing` へ進める前に走るので、まだ直せる分析設計にも当たる。
- Criteria: 初版の引き継ぎ（案内を「派生を作る」に直す）。ADR-0053 の3と4。
- Affected modules: `skills/analysis-notebook/SKILL.md`、`skills/analysis-notebook/references/notebook-contract.md`。
- Alternatives considered: どちらも「派生を作る」だけにする（まだ直せる分析設計に、要らない派生を作らせる）。
- Consequences: 案内は 33.4 の検査を前提にする。33.4 が入る前の Epic ブランチでも、文は誤りにならない。

### Decision: primary-criteria-are-compared-as-a-set-of-pairs

- What: 分析を始めた分析設計の primary の指標は、`target` と `comparison` の組を並べ替えた列で比べる。文字は1字でも違えば変更とみなす。並び順と、primary の指標のほかの項目（`data_source`・`grouping`・`filter`・`aggregation`）は比べない。
- Why: ADR-0053 の3は、組を足す・消す・`tier` を変えることを拒むと決めた。比べ方は Story に委ねた。
- Criteria: 拒む範囲を、人間が決めた範囲より広げない（[FLOW-0008](../adr/flow/0008-ask-before-narrowing-what-worked.md)）。判定を左右するのは基準の文と、それが掛かる指標である。並び順は判定を変えない。誤字かどうかは機械で見分けられない（ADR-0053 の Alternatives）。
- Affected modules: `src/insight_blueprint/validate.py` の `_criteria` と `_held_errors`。
- Alternatives considered: 並び順も比べる案（判定に効かない並べ替えを拒む）。空白を詰めて比べる案（YAML の折り返しの違いは通るが、どこまでを同じとみなすかの線が増える）。
- Consequences: primary の指標の `filter` や `aggregation` は、分析を始めた後も変えられる。測り方を結果の後に変える道は残る（ADR-0053 の Negative と同じ穴）。YAML を手で折り返して `comparison` の空白が変わると拒まれる。

### Decision: a-started-design-never-reads-as-not-started

- What: 分析を始めた分析設計を、分析を始めていないと読める形にする書き込みを拒む。印の無い保存済みの分析設計が、印を持たずに `analyzing` を離れる直書きが当たる。`design_io` は、状態を変える書き込みで印を付ける（`transition`、状態を含む `update`、`review-batch`）。分析を始めていない分析設計に、状態を進めずに印だけを付ける書き込みも拒む。
- Why: AC 1 の「消す書き込みも変える書き込みも通らない」から導いた。印の無い記録は状態だけが跡なので、状態が戻ると跡が消える。逆に、先に付いた印は、後の review batch に「分析を始めた後」と誤って写る（Story 33.5）。
- Criteria: AC 1。印は記録に書いてあることだけを言う（PRD の非機能要件）。
- Affected modules: `src/insight_blueprint/validate.py` の `_mark_errors`、`skills/_shared/design_io.py` の `_with_analysis_mark`。
- Alternatives considered: 直書きで `analyzing` に入るときも印を求める案（新しいファイルへの直書きはスキーマだけを確かめるので、印の無い `analyzing` はどのみち作れる。ADR-0053 の Negative）。
- Consequences: 印の無い保存済みの分析設計を結果の review に戻すには、`design_io transition` を使う。拒む文がそう案内する。`transition` は `validate_update` を通るようになり、`update` と同じ検査を受ける。`review-batch` は batch を書く前に同じ検査をするので、拒まれた承認は batch を残さない。

### Decision: the-criterion-is-asked-on-the-first-entry-only

- What: `comparison` が空でないことを確かめるのは、分析を始めていない分析設計が `analyzing` に入る書き込みだけにする。分析を始めた分析設計が結果の review から `analyzing` に戻る書き込みでは確かめない。primary の指標が複数あれば、どれも空でないことを求める。
- Why: 分析を始めた検証は基準を書き足せない（ADR-0053 の3）。保存済みの、基準を持たない検証が結果の review に入ると、基準を求めるかぎり `analyzing` に戻れない。ADR-0053 の D3 の決め手は「書き忘れた分析者が、測る前に直せる」で、戻るときには直せるものが無い。
- Criteria: 拒む範囲を、人間が決めた範囲より広げない（FLOW-0008）。AC 4 の文は「`analyzing` に入る書き込み」で、戻る書き込みも含むと読める。狭く読んだので、PM に知らせ、Epic PR で人間に確かめる。
- Affected modules: `src/insight_blueprint/validate.py` の `_criterion_errors`。
- Alternatives considered: 戻る書き込みでも確かめる案（保存済みの基準なしの検証は、結果の review から結論へ直接進むか、派生を作るしかなくなる）。primary のどれか1つに基準があれば通す案（基準の無い primary の指標が判定に入る）。
- Consequences: 保存済みの基準なしの検証は、今までどおり `analyzing` と `in_review` を行き来できる。notebook は基準が無いと止まる（契約のまま）。基準の無い検証が `in_review` から結論へ直接進む書き込み（ADR-0029）は、今までどおり通る。ADR-0053 の4は `analyzing` に入る書き込みだけを決めたので、拒む範囲を広げるかは人間に聞く（FLOW-0008。Story のレビューで見つかった）。初めて付く印の時刻は確かめない。印の時刻は表示にも判定にも使わない（Decision `a-batch-holds-whether-it-came-after-the-analysis`）。

### Decision: the-report-gives-each-metric-of-groups-its-own-table

- What: レポートは、群を持つ指標を本の表の後に、指標ごとの表で出す。表の上に「指標名（軸 × 軸）」の行を置く。縦横の表にするのは、軸が2つ、どの群の行も値だけ、群の組が重ならない、の3つがそろうときだけである。組が重なれば、行を落とさずに縦の表にする。群だけを持つ指標（本の表の列に出すものが無い）は本の表に行を出さない。値や線も持つ指標は、本の表の行と群の表の両方に出す。表示の言葉（判定・区間の種類）と列の順は、33.2 と知らせ合って同じ規則にし、`theme_report.py` に自前で持つ。
- Why: 組が重なる群の行を縦横の表に入れると、1つのセルに1つしか入らず、値が黙って消える。値と群の両方を持つ指標は読み手が両方を読む（Decision `groups-that-do-not-fit-their-axes-read-as-no-groups`）ので、どちらかを捨てると記録にある数が届かない。
- Criteria: PRD の非機能要件「分析者に届く数と結論は、記録に書いてあるものに限る」。ADR-0052 の8と9。決め手は前者で、記録にある数を表から落とさない。
- Affected modules: `skills/_shared/theme_report.py`。
- Alternatives considered: 組が重なれば後の値で上書きする（数が黙って消える）。値と群の両方を持つ指標は群だけ出す（指標の値が消える）。表示の言葉を `design_note.py` と共通にする（33.2 と同じファイルを同時に触る。2か所なので Rule of Three に届かない。Epic のゲートで揃いを確かめる）。
- Consequences: 探索で出さない列（線・判定・しきい値・合否）は、`VERDICT_COLUMNS` に線と判定の3語を足した集合で決める。33.2 が `VERDICT_COLUMNS` に3語を足すと、足した分は重なるだけで振る舞いは変わらない。

### Cross-epic decisions (links to ADR)

- [ADR-0052: verdict の指標は支持の線と棄却の線、指標の判定、値の区間の種類、群の行を持つ](../adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md): #235・F17・F09 の形を1本にまとめた。
- [ADR-0053: 分析を始めた検証の分析設計は、検証仮説・判定の基準・意図を変えない](../adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md): 分析の印を残し、書き換えを機械で拒む。ADR-0048 の5と ADR-0050 の5を改める。
- [ADR-0054: review は結果も対象にし、review コメントを分析ノートと論点ツリーに出す](../adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md): 同じ skill と同じ batch に対象を足す。レポートには出さない。

## Test Design Matrix

| Story \ Layer | Unit | Integration | E2E |
|---|---|---|---|
| Story 33.1 | ✓（`tests/test_design_note_read.py`: 線・判定・値の区間・群の行の読み。`tests/skills/test_notebook_contract_structure.py`: 契約と SKILL.md の規則と例。`tests/docs/test_canonical_docs.py`: 用語） | ✓（`tests/integration/test_analysis_notebook_contract.py`: 検証と探索の fixture を走らせ、verdict を分析ノートの読み手で読み戻す。`tests/test_saved_verdicts.py`: 保存済みの verdict の8例が、Epic の前と同じ表で出る） | —（notebook を生成するのは AI で、構造テストが契約と SKILL.md の文を照らす。検証の fixture を契約のコマンド（`uv run --project … --extra notebook python`）で走らせ、verdict の JSON を読み手で読み戻して確かめた） |
| Story 33.2 | ☐ | ☐ | ☐ |
| Story 33.3 | ✓（`tests/test_theme_report.py`: 線・判定の列と言葉、区間の種類の言葉、群の縦横の表と縦の表、群の初出順、探索で線と判定を出さないこと、利用者の文の escape、保存済みの verdict の8例の表） | ✓（`tests/tree_io/test_report.py`: 線・判定・HDI・軸が2つの群を持つ verdict が、`tree_io report` の書いたファイルの表に出る） | —（レポートは code が書く Markdown で、統合テストがファイルの表を照らす。検証と探索の fixture を回して読んだ verdict と、保存済みの8例と、軸が2つの群（縦横と縦）のレポートの表を、ブラウザで目で確かめた） |
| Story 33.4 | ✓ | ✓ | —（分析者の入口の SKILL.md は対話で、自動で回せない。一時ディレクトリの `.insight/` で `design_io` の CLI を走らせ、基準の無い検証の `transition analyzing` が拒まれること、`analyzing` と結果の review の `in_review` で検証仮説と基準の書き換えが拒まれること、背景の直しが通ることを確かめた。hook にも同じ直書きを渡して確かめた） |
| Story 33.5 | ☐ | ☐ | ☐ |
| Story 33.6 | ☐ | ☐ | ☐ |

完了時に ✓ を付ける。このマトリクスが Epic PR のレビューゲート。

## Story Timeline

- 2026-11-25 — 初版: 範囲の判断（分析の印、固定、review の対象、表示）と中身の判断（verdict の形、用語）を人間が選んだ。全体の整合で、基準なしの検証が行き止まる穴と、review batch の前後の持ち方を直した。
- 2026-11-25 — 初版: 見本を Artifact で見せた（分析ノートの指標の表の案 A と案 B、値の区間、群の表、レビューの節、論点ツリーの行）。題材は合成シナリオで、コミットしていない。分かった事実: 線が数だけでも、同じページの `comparison` と並べれば読める、と人間が判断した。確かめていない前提: 実際の分析ノートの幅で、列が増えた表が読めるか。群の軸が3つ以上のときの表。
- 2026-11-25 — 初版を人間が承認した（Domain Model 図を含む。このセッションで直接）。
- 2026-11-25 — Story を起票した: #243（33.1）、#244（33.4）、#245（33.2）、#246（33.3）、#247（33.5）、#248（33.6）。
- 2026-11-25 — Story 33.1 completed: notebook の契約に支持の線・棄却の線・指標の判定・値の区間・群の行を足し、読み手（`VerdictMetric`）が読むようにした。US-1 AC 1・AC 2 と US-2 AC 1・AC 3 を満たした。US-1 AC 5 は、読み手と今の表について満たした（保存済みの verdict の8例を、Epic の前のコードが出す行で固定した）。新しい列が入った後の AC 5 は 33.2 と 33.3 が確かめるので、チェックは付けていない。
  Domain Model 図は変えていない。`MetricJudgment`・`ValueInterval`・`MetricGroup` は案の名前のまま使った。図が省いている項目は実装にもある（`VerdictMetric` の `p`・`effect_size`・`sample_size`、`MetricGroup` の `p`・`effect_size`）。
  計画外の判断は2件で、Decisions に書いた（値の区間を1つの項目で持ち、表は種類の表示を待つ。軸に合わない群の行は、群を持たないものとして読む）。案内の分け方（`in_review` は基準を書く、分析を始めた後は派生）も Decisions に書いた。
  Epic 32 のテストのうち、契約の文と fixture の形を固定していたものを、新しい契約に合わせて書き換えた（primary の `threshold` と `pass`、`confidence_interval`、基準が無いときの案内）。ADR-0052 が仕様を変えたためである。
  残したこと: `docs/ARCHITECTURE.md` の `.insight/` の表は、verdict の任意の項目を「効果量・信頼区間・標本サイズ」と書いたままである。33.4 が同じファイルを触るので、ここでは直していない。
  バグ・セキュリティの観点のレビューを1本回した（指摘2件、どちらも直した）。Python 3.11 では、指標の判定を持つ verdict を読むと `TypeError` で止まった（`in` で enum の値を照らしていた）。値を作ってみる書き方に直し、3.11 でも読み手と契約のテストを回した。「群を指標の名前に埋めない」の構造テストは、群を持つ指標の名前しか見ていなかったので、例のすべての指標の名前を見るように直した。

- 2026-11-25 — Story 33.4 completed: 分析の印（`analysis_started_at`）を分析設計に足し、`validate_update` が、分析を始めた検証の検証仮説・primary の指標の組・意図の変更と、基準の無い検証が `analyzing` に入る書き込みを拒むようにした。`design_io` は状態を変える書き込みで印を付け、`transition` と `review-batch` も同じ検査を通る。Domain Model 図は変えていない（分析を始めたかは `validate.py` の `analysis_started` が答える）。計画外の判断は3件で、Decisions に書いた（組の比べ方、印を先に付けない、基準を確かめるのは初めて入るときだけ）。`/analysis-review` と `/analysis-revision` の案内は 33.5 が直す。
- 2026-11-25 — Story 33.3 completed: レポートの指標の表に、支持の線・棄却の線・判定・区間の種類を出し、群を持つ指標を指標ごとの表（縦横か縦）で出すようにした（`theme_report.py` の `_metrics`・`_group_table`・`_cross_table`）。US-1 AC 4 と US-2 AC 5 を満たした。US-1 AC 5 と US-2 AC 2 は、レポートについて満たした（保存済みの verdict の8例を、Epic の前のコードが出した表で先に固定し、区間の列の見出しと種類の言葉だけを変えた）。分析ノートは 33.2 が確かめるので、チェックは付けていない。
  33.1 が置いた暫定の条件（種類が `confidence` の値の区間だけを「信頼区間」の列に出す）と、そのテストを消した。
  表示の言葉・区間の cell の形・列の順・群の表の規則は、33.2 と知らせ合って同じにした。計画外の判断は2件で、Decisions に1つにまとめて書いた（組が重なる群は縦の表、値と群の両方を持つ指標は両方を出す）。Domain Model 図は変えていない。
  バグ・セキュリティの観点のレビューを1本回した（中以上の指摘なし）。軽微な2件は直していない。escape すると同じ文字になる群の名前（`"a"` と `"a "`）は、見分けのつかない2つの列になる。値を1つも持たない群の行だけの指標は、縦横の表が「—」だけになる。Python 3.11 でもレポートのテストを回した。
