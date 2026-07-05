# ADR-0007: 上流の認識論的判断ゲート（`/analysis-auto` の design ビート化 + data-extraction ゲート）

## Status

Accepted

## Context

[ADR-0005](0005-selective-autonomous-chaining.md) は `/analysis-auto`（guided autopilot）のゲートを
**コスト・副作用・不可逆性の境界**に配置した — premortem の `HARD_BLOCK`/`HIGH`、データソース登録、
notebook の非 allowlist / 宣言 source 以外の外部通信、reflection の結論づけ。自律オートパイロットの
定番ヒューリスティック（「高コスト/不可逆な所で止める」）に沿った配置である。

実運用でユーザーがフィードバックを寄せた（引き金: 本 ADR を伴うセッション、`/analysis-auto` の試用）:

- framing の方向性 AskUserQuestion 一発で design を通過してしまい、手法・指標・explanatory ロールの
  確認機会がほぼない。
- 手法・図（`chart[]`）にフィードバックする席がない。
- **どのデータをどう引くか（SQL / 抽出プラン）の確認が一切ない。** 宣言済み source の読取は AUTO の
  ため、`methodology.steps` に自動生成されたクエリ（`/analysis-design` Step 2.6）も notebook cell 2 で
  実体化されるクエリも、ユーザーの目に触れないまま実行される。

構造的な原因は2つ:

1. **ゲート遵守の崩れ** — design ゲートは紙の上では「hypothesis + methodology + metrics + roles +
   intent をまとめて確認」という KEEP だったが、この *一枚岩の指示* が実行時に方向性確認へ圧縮された。
2. **設計上の穴** — ADR-0005 のコスト軸ゲート配置が、分析における *安いが決定的な上流*（手法・指標・
   ロール・データの取り方＝認識論的判断）を過小評価していた。間違った手法は安く・自信満々に間違った
   結果を生む。判断点は「金がかかる所」ではなく「正しさが決まる所」にある。

## Decision

`/analysis-auto` のゲート配置を、コスト境界だけでなく **認識論的判断点**にも従わせる。具体的には:

- **design 一括ゲートを、順序づいた4つの確認ビートに分割**する。各ビートは独立した AskUserQuestion で
  提示し、`design_io create` の前（したがって premortem の前）に走らせる:
  1. hypothesis（statement + background）
  2. methodology + metrics + explanatory roles + intent
  3. **data-extraction（新設）** — データ取得プラン。SQL source は `methodology.steps` の実クエリ、
     CSV 等は file + columns + filter を提示し、想定グレイン・ざっくり行数を添える。SQL の無い source
     でも「データ取得プラン」ビートの席を持つ。
  4. charts（`chart[]` の intent / type / x / y）
- **data-extraction ゲートは premortem より前**に置く。クエリを確定させてから premortem に渡すことで、
  コスト見積もりが確定クエリと一致し、notebook は以降 AUTO に保てる。
- 個々の skill（`/analysis-design`・`/analysis-notebook`・`/premortem`）の **単体対話フローは不変**。
  自律性は `/analysis-auto` 起動時のみ、という ADR-0005 の scoped autonomy を維持する。

これは ADR-0005 を **amend（精緻化）**するものであり、supersede しない。ADR-0005 の Decision
（selective autonomy / driver によるゲート駆動 / notebook 実行ポリシー）はそのまま有効で、本 ADR は
その «ゲートをどこに置くか» の基準に「認識論的判断点」を追加する。

## Consequences

### Positive

- 上流の手法・図・SQL に確認とフィードバックの席ができる。「安いが決定的な」判断がユーザーの目を通る。
- 順序づいた番号ビートは、曖昧な「full design をまとめて確認」より実行時に圧縮されにくく、ADR-0005 が
  Negative で認めた「ゲート遵守は Claude の SKILL 追従依存」という弱点を緩和する。
- SQL 確認を設計時（premortem 前）に前倒しするため、premortem が確定クエリでコスト見積もりでき、
  notebook 実行は AUTO のまま摩擦を増やさない。

### Negative

- design ステップの停止回数が 1 → 4 に増える。上流の摩擦は意図的に増やしている（それが要求）。
- ゲートが prose オーケストレーションである点は不変で、ビート遵守は依然 Claude の SKILL 追従に依存する
  （機械的強制ではない）。番号ビート化は緩和策であって保証ではない。

## Alternatives considered

- **notebook を plan/execute に二分割し、実行直前に SQL+図を提示（案B）** — 変更は狭いが、手法・指標・
  ロールへのフィードバック不足が直らず、SQL 確認が premortem 通過後になり見積もりとズレうる。却下。
- **対話粒度ダイヤル（rich/balanced/minimal 引数, 案C）** — 直交ノブとして有用だが、ビートの実体
  （本 ADR）が無いと空回りする。本 ADR 適用後の拡張候補として保留。
- **ADR-0005 を supersede して書き直す** — Decision の骨子（selective autonomy / driver / 実行ポリシー）
  は有効なままなので、全面置換は過剰。amend に留める。

## Related

- Epic: #34 / `docs/design/epic-08-analysis-auto.md`
- Builds on / amends: [ADR-0005](0005-selective-autonomous-chaining.md)（selective autonomous chaining）
- Skills: `/analysis-auto`（gate policy + design ビート）、`/analysis-design`（Step 2.6 のクエリ提示前提）、
  `/analysis-notebook`（cell 2 が確定クエリと乖離しない）
