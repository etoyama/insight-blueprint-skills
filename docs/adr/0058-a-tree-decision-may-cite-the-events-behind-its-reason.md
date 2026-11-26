# ADR-0058: ツリーの決定は、理由の根拠にした出来事を引用できる

## Status

Accepted

## Context

Epic 34（[#249](https://github.com/etoyama/insight-blueprint-skills/issues/249)、[DesignDoc](../design/epic-34-what-moved-the-answer.md)）の初版で決めた。
Story 18.8 の引き継ぎの試行で、読み手は次に調べる論点を当てた。一方、それを選ぶ理由の元になった出来事は取り違えた（[#137](https://github.com/etoyama/insight-blueprint-skills/issues/137)）。
人間は#137 を Epic 34 に入れると決めた。あわせて、決める場面に「主題そのものを見直す」を並べると決めた（2026-11-26）。

比較の土台にした事実（epic ブランチ dc785c4）。

- `TreeDecision` は `round`・`kind`・`node_id`・`reason`・`created_at` を持ち、知らない項目を拒む（`src/insight_blueprint/models/tree.py` を読んだ）。既定値つきの項目を足せば、保存済みの YAML はそのまま読める。
- HTML の「ツリーの決定」は種類・回・論点・理由の文だけを出す（架空のシナリオを通して読んだ）。
- 試行の記録 9 本のうち、問い 5 を外したのは sonnet の 2 本である（`docs/handoff-trials/` を読んだ）。外れた答えは理由の元として、次の論点の発見元の出来事だけを挙げた。
- 正解の鍵は問い 5 の理由の出来事だけを人が手で決めている。鍵は、挙げてもよい出来事（`also_allowed`）を別に持つ（`tests/fixtures/handoff/lib/key.yaml`）。
- `tree_io revise-root` は主題の版を上げ、理由を残す。分析者に聞く手順は `/analysis-framing` の Step 4c にある。`/analysis-reflection` の決める場面（Step T7）は、3つの種類を表で出し、主題を変える道は最後の案内の1行で示す。
- 確かめていないこと: #137 の原因が「理由が出来事を引用しないこと」であるか。人の読み手で同じ外れ方が出るか。

## Problem

- 課題1: HTML だけを読む人は決定の理由の根拠を、近くにある「発見元」の表示から推し量り、取り違える。
- 課題2: 調べた結果、主題そのものが違っていたと分かったとき、決める場面にその道が並んでいない。分析者は3つのどれかを選ぶ。

扱わない範囲: 主題を見直した理由（`RootRevision.reason`）の引用。引用を持たない理由に書いた数の検査。

## Decision Analysis

| # | 基準 | 区分 | 分類 | 重み（決めた人） | 出典 |
|---|---|---|---|---|---|
| M1 | 保存済みの論点ツリーの YAML がそのまま読める | Must | - | - | 不変条件（正本は YAML） |
| M2 | 引用した出来事は記録にある | Must | - | - | [ADR-0025](0025-cited-answers-checked-after-writing.md) |
| W1 | HTML だけの読み手が、理由の根拠を取り違えない | Want | 解決 | 高（人間） | 課題1 |
| W2 | 根拠の出来事が無い決定に、無理に引用させない | Want | 費用 | 高（人間が案A を選んだ） | 実測（区切る理由には、証拠を持たないものがある） |
| W3 | 書き手と検査の手間 | Want | 費用 | 中（Claude の推測） | ADR-0025 の Negative |

- 案A: `TreeDecision` に任意の引用を足す。引用があれば検査する。
- 案B: 最初の論点を選ぶ決定を除き、新しい決定は引用を1つ以上持つ。
- 案C: YAML は変えず、決定の回に主題の答えが新しく引用した証拠を、決定の横に並べる。
- 何もしない。

| Must | 案A | 案B | 案C | 何もしない |
|---|---|---|---|---|
| M1 | 満たす | 満たす（読むときは空を許す） | 満たす | 満たす |
| M2 | 満たす | 満たす | 引用を持たないので当たらない | 当たらない |

| Want | 案A | 案B | 案C |
|---|---|---|---|
| W1 | 引用した決定では取り違えない。引用が無い決定も、無いと分かる | 取り違えない | 弱い。並ぶのは同じ回に出た証拠で、理由の根拠とは限らない |
| W2 | 無理強いしない | 無理強いする。関係の薄い出来事を引かせる | 当たらない |
| W3 | 引用を付けるぶん増える。検査は答えのものを使い回す | 案A と同じ。加えて引用を探す手間がある | 手間なし |

- 差がつく基準: W1（案C が落ちる）と W2（案B が落ちる）。
- 感度: W2 を低にすると案B になる。無理に引かせた引用は根拠に見えるぶん、無いより悪い。

| 案 | 起きうる悪い結果 | 抑え方 |
|---|---|---|
| 案A | 書き手が引用を付けず、何も変わらない | skill で、元になった出来事があれば引用させる。HTML が「引用していない」と出すので、読み手に見える |
| 案A | 引用を持たない理由に数を書いても、検査されない | この決定では塞がない |
| 案B | 関係の薄い引用が根拠に見える | 無い |
| 案C | 推し量りを表示が固定する | 無い |
| 何もしない | #137 が残る | 無い |

## Decision

案A を採る（人間の判断、2026-11-26）。決め手は W1 と W2 の両立である。

1. `TreeDecision` は、理由の根拠にした journal の出来事の id を0個以上持てる（`cites`。既定は空）。持たない保存済みの決定は、空として読む。
2. 引用を持つ決定は書く前に検査する。次のどれかなら、`tree_io decide` は何も書かず、違反を返す。
   - 引用先の出来事が journal に無い。
   - 引用先が論点ツリーのどの論点にも結んでいない分析設計の出来事である。
   - 理由の文に出てくる数が引用した出来事の本文に無い。
3. 決定が引用できるのは、論点ツリーのどこかの論点に結んだ分析設計の出来事である。答えの文より広い。決定はある論点の結果を根拠に、別の論点へ進むからである。
4. HTML は決定の理由の下に、引用した出来事の id・分析設計・本文を出す。引用を持たない決定は引用していないことを文で出す。最初の論点を選ぶ決定にはその文を出さない。
5. `/analysis-reflection` は、分析者が挙げた理由の元になった出来事があれば、引用に入れる。元になった出来事が無い決定は、引用なしで書く。
6. `/analysis-reflection` の決める場面は深める・親に戻る・区切るに並べて「主題そのものを見直す」を出す。選ぶと、`/analysis-framing` の主題の版を上げる手順へ進む。版を上げた後は同じ場面に戻り、次に調べる論点を選ぶ。
7. ツリーの決定の種類（`TreeDecisionKind`）は4つのままにする。主題を見直すことは、次に調べる論点を指す決定ではない。
8. 引用を持つ合成シナリオでは、正解の鍵の問い 5 の理由の出来事を、テストが論点ツリーから導き直す。

## Consequences

### Positive

- 引用した決定では、HTML だけの読み手が根拠の出来事をその場で読める。
- 正解の鍵から、人が手で決める所が減る。
- 主題を見直す道が決める場面で目に入る。

### Negative

- 引用は任意なので、書き手が付けなければ効かない。
- 引用を持たない理由に書いた数は、検査されない。
- 主題を見直した理由は引用を持たない。
- #137 の原因は推測のままである。引用を足して問い 5 の正答が上がるかは、[ADR-0059](0059-the-handoff-trial-has-a-second-scenario-and-a-sixth-question.md) の試行で確かめる。
- [ADR-0026](0026-analysis-auto-walks-the-question-tree.md) の KEEP ゲート「根の版を上げるかどうか」は変えない。決める場面から、その聞き方へ進む道が増えるだけである。

## Alternatives considered

- **`TreeDecisionKind` に「主題を見直す」を足す** — 決定は次に調べる論点を指す。主題を見直す決定は論点を指さず、種類ごとの順の検査（`_check_decision_after`）にも合わない。今ある `revise-root` が理由と版を残す。

## Related

- Epic: [#249](https://github.com/etoyama/insight-blueprint-skills/issues/249)、[docs/design/epic-34-what-moved-the-answer.md](../design/epic-34-what-moved-the-answer.md)
- Issues: [#137](https://github.com/etoyama/insight-blueprint-skills/issues/137)
- [ADR-0024](0024-question-tree-yaml-and-generated-html.md)、[ADR-0025](0025-cited-answers-checked-after-writing.md)、[ADR-0026](0026-analysis-auto-walks-the-question-tree.md)、[ADR-0035](0035-handoff-trial-records-keep-their-score.md)、[ADR-0055](0055-the-root-question-is-shown-as-the-subject.md)
- Supersedes: なし
