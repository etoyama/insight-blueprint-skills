# Docs Review — Epic 09 (installable plugin execution model)

Branch `epic/9-installable-plugin` vs `main`. Reviewed: README.md, CLAUDE.md,
docs/ARCHITECTURE.md, docs/adr/0006-plugin-execution-model.md, docs/adr/README.md,
docs/design/epic-09-installable-plugin.md, and changed skills/*/SKILL.md.

新実行モデル（bin ラッパー / `INSIGHT_BASE_DIR` / hook 同梱）への整合性を検証した。
おおむね整合しているが、canonical docs に旧記述の取り残しが 2 件（うち 1 件は High）。

---

## Findings

### F1 [High] README の add-knowledge 例が旧コマンドのまま — canonical doc

- **File/section**: `README.md:172`（"Capturing knowledge (`/knowledge-extract`)" セクション）
- **What**: コードブロックが `... | uv run python -m skills._shared.catalog_io add-knowledge --id <source_id>`
  のまま。Epic 09 の AC3（素の `python -m skills._shared` 廃止・wrapper 名へ統一）に反する。
  README は canonical doc かつ新規ユーザーが最初に読む場所なので影響が大きい。
- **確認**: `add-knowledge` は `catalog_io` のサブコマンドとして実在（`skills/_shared/catalog_io.py:341,373`）。
  bin ラッパー `catalog_io` はサブコマンドをそのまま `"$@"` で渡すので、`catalog_io add-knowledge` で動く。
- **Suggested update**:
  ```bash
  ...]}' | catalog_io add-knowledge --id <source_id>
  ```
  （`uv run python -m skills._shared.catalog_io` → `catalog_io` に置換）

### F2 [High] analysis-design/SKILL.md が旧 hook パスを参照 — canonical skill doc

- **File/section**: `skills/analysis-design/SKILL.md:295`
- **What**: 本文が `pre-write hook (.claude/hooks/validate-design.py)` のまま。Epic 09 で hook は
  `hooks/validate-design.py`（plugin 同梱）へ移設済み。README/CLAUDE/ARCHITECTURE は更新されているのに、
  この SKILL 本文だけ旧パスが残っている。SKILL は配布物（利用者環境で読まれる）なので canonical 扱い。
- **Suggested update**: `.claude/hooks/validate-design.py` → `hooks/validate-design.py`。
  （必要なら「plugin 同梱、利用者プロジェクトでも効く」の一言を添えると ARCHITECTURE/CLAUDE と揃う）

### F3 [Medium] README「Optional: Python package」と self-provide の依存ストーリーが半矛盾

- **File/section**: `README.md` "Quickstart"（15–17行）＋ "Optional: Python package (for lineage)"（68–79行）
- **What**: ADR-0006 / Epic 09 の肝は「plugin が `insight_blueprint` と `skills._shared` を **self-provide**、
  利用者は core に何も install 不要」。README もその方向に見えるが、依存ストーリーが 2 箇所に散って読者が混乱しうる:
  - Quickstart は "skills shell out to `uv run …`, which resolves dependencies automatically — nothing to
    `pip install`" と言う（正しい。ただし self-provide が **plugin の uv env** 経由である点が明示されていない）。
  - "Optional: Python package (for lineage)" は `uv add insight-blueprint-lineage` を「optional but recommended
    for analysis-pipeline transparency」と案内。しかし notebook（lineage を使う唯一の経路）は Epic 09 で
    `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook` に変わり、**plugin env が lineage を供給**する
    （`skills/analysis-notebook/SKILL.md` 参照）。つまり「利用者が自プロジェクトに `uv add` する」ケースは、
    自前の notebook/script に `tracked_pipe` を書く場合に限られる。
- **矛盾の芯**: "optional vs required" の直接矛盾ではない（両方とも「必須ではない」で一貫）が、
  「何のために・どの経路で必要になるか」が新モデルとズレている。読者は「lineage を使うには自分で `uv add`
  すべき」と誤解しうる。実際は skill 経由（/analysis-notebook）なら install 不要。
- **Suggested update**: "Optional" セクションを「skill 経由の notebook は plugin env が lineage を供給するので
  install 不要。自分で書いた notebook/script から直接 `tracked_pipe` を使いたいときだけ `uv add
  insight-blueprint-lineage`」と用途を限定して書き直す。Quickstart 側に「core は plugin の uv env が自給する」
  の一言を足すと ADR-0006 と揃う。

### F4 [Low] Quickstart Prerequisites が uv の役割を旧モデルの粒度で説明

- **File/section**: `README.md:15-17`
- **What**: "The skills shell out to `uv run …`, which resolves the Python dependencies automatically" は
  正しいが、新モデルでは **plugin 自身の uv project**（`cd ${CLAUDE_PLUGIN_ROOT}` → `uv run`）で解決する点が
  肝。現文面はどの env で解決されるか曖昧で、F3 の誤解を助長する。
- **Suggested update**: "…which resolves dependencies from the **plugin's own environment**（利用者プロジェクトに
  install 不要）" のように env の所在を明示。

### F5 [Low] analysis-notebook が新機構 `.insight/rules/package_allowlist.yaml` を導入 — 出典が本文のみ

- **File/section**: `skills/analysis-notebook/SKILL.md`（Prerequisites 改訂部）
- **What**: 「methodology 固有ライブラリ（scikit-learn 等）は `.insight/rules/package_allowlist.yaml` に置き、
  plugin env に随時追加」と書かれた。これは Epic 09 diff で新規に現れた仕組みだが、ADR-0006・Epic 09 doc・
  ARCHITECTURE のいずれにも `package_allowlist.yaml` の記述がない。cross-consistency の穴。
- **Suggested update**: Epic 09 doc（範囲内なら）か ADR に一行触れるか、SKILL 本文で「どう plugin env に
  追加するのか（`uv add --project ${CLAUDE_PLUGIN_ROOT}`?）」の具体手順を明示する。手順が曖昧なままだと
  利用者は allowlist に書いても実際に env へ入れられない。

---

## Historical docs（旧 hook パスを保持 — これは正しい。修正不要）

以下は point-in-time record として旧 `.claude/hooks/validate-design.py` を保持しており、
歴史記録なので更新しないのが正。フラグのみ:

- `CHANGELOG.md:24`（0.7.0 の Added、当時のパス記録）
- `docs/design/epic-02-validate-lib.md`（複数箇所）— Epic 02 の設計記録
- `docs/design/epic-03-skills-yaml-io.md:23,132` — Epic 03 の設計記録
- `docs/adr/0001-drop-mcp-server-embed-validation.md:41` — ADR-0001（当時の決定）
- `docs/adr/0003-skill-yaml-io-via-design-io.md:33` — 旧 CLI 形式 `python -m skills._shared.design_io`
  （ADR-0003 当時の記録。歴史なので保持で可）

補足: CHANGELOG の `[Unreleased]` は空。0.7.1 patch のエントリ（hook 移設 / bin ラッパー / install 経路修正）は
release 時に追記される想定と読めるが、Epic 09 doc は「マージ後 0.7.1 patch release」と明記しているので、
CHANGELOG 更新漏れというより release 待ちと解釈。念のため軽微フラグ。

---

## 整合性が取れている点（合格）

- **hook パス更新（canonical）**: README:84 / CLAUDE.md:112 / ARCHITECTURE.md:48,64 すべて
  `hooks/validate-design.py`（plugin 同梱）に更新済み。F2 の SKILL 1 箇所を除き網羅。
- **hooks.json ↔ ADR ↔ 実ファイル**: `hooks/hooks.json` の command
  （`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/hooks/validate-design.py"`）が
  ADR-0006 の記述と一致。`.claude/settings.json` は dev 用に `uv run python hooks/validate-design.py` を配線 —
  ADR・CLAUDE・ARCHITECTURE の「dev 用に同スクリプトを配線」と整合。
- **bin ラッパー ↔ ADR ↔ SKILL**: `bin/design_io`・`catalog_io`・`premortem` の中身
  （`cd ${CLAUDE_PLUGIN_ROOT}` / `INSIGHT_BASE_DIR=${CLAUDE_PROJECT_DIR}/.insight` / `mkdir -p` /
  `UV_PROJECT_ENVIRONMENT`）が ADR-0006 の Decision と一致。SKILL 群のコマンドも wrapper 名に統一済み
  （F1・F2 を除く）。base 系の `python -m skills._shared` は SKILL からは一掃されている。
- **framing の陳腐化 init 廃止**: `skills/analysis-framing/SKILL.md` から `insight-blueprint init` 案内は
  完全削除され、「`.insight/` が無くても OK、wrapper が初回書込時に自動作成」に置換。整合的で良い。
  リポジトリ全体でも `insight-blueprint init` の残存はゼロ。
- **notebook 実行形**: `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook …`（cwd=利用者、env=plugin）に
  Step 4・Prerequisites・optional HTML export まで一貫して置換済み。
- **ADR-0006**: template 準拠（Status/Context/Decision/Consequences/Alternatives/Related すべて有り、断定形、
  引き金 Epic #38 を引用）。docs/adr/README.md の索引に 0006 追記済み。Status Accepted。
- **Epic 09 doc**: design-doc-template 準拠（AC / Glossary / Scope / Architecture(mermaid) /
  Module Responsibilities(表) / Sequence Diagram / Data Model / Decisions(ADR リンク) / Test Design Matrix /
  Story Timeline すべて有り）。AC ↔ ADR ↔ 実 bin/hooks がクロスで一致。
- **`--base-dir` の残存**: skills/_shared/*.py（実装・docstring）と premortem/cli.py のみ。これは後方互換の
  引数で ADR-0006 が「維持（tests は従来どおり）」と明言済み。canonical prose には残っていない。正しい。

---

## 新規ユーザー視点の判定

install 手順（`/plugin marketplace add` → `/plugin install`）と「起動不要・`.insight/` は初回自動作成」は
README で明快。core は install 不要という self-provide の恩恵も伝わる。ただし **F3/F4 の依存ストーリーの
散在**が唯一の引っかかり — 「lineage を使うには自分で `uv add` すべきか？」が読者に曖昧。F1（動かないコマンド例）
と併せて直せば、docs だけで新規ユーザーが迷わず install→実行できる状態になる。

## 推奨対応順

1. F1（動かないコマンド例、canonical）
2. F2（旧 hook パス、canonical skill）
3. F3（依存ストーリーの整理）
4. F4/F5（補強）
