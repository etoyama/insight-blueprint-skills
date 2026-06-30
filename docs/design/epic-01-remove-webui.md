# Epic 01: WebUI / REST 削除

/ ADR-0001 の解体ロードマップ E1。MCP 機能を温存したまま WebUI と REST 層を撤去する。

## Acceptance Criteria

- [x] AC1: `frontend/` と static 配信コードが削除され、WebUI 起動経路が存在しない
- [x] AC2: REST API (`src/insight_blueprint/web.py`) が削除され、MCP tool 群は影響を受けない
- [x] AC3: WebUI/REST に依存するテストが削除/修正され、`pytest` が全緑（889 passed）
- [x] AC4: CI から frontend ビルド・npm 関連ジョブが削除される
- [x] AC5: `pyproject.toml` から fastapi 依存と frontend ビルドタスクが削除される
  （uvicorn は MCP SSE / headless mode のため保持）

## Glossary

| Term | Meaning |
|---|---|
| WebUI | `frontend/` の React アプリ（design overview / review confirmation / catalog browsing） |
| REST API | `web.py` の FastAPI エンドポイント群（`/api/*`） |
| MCP server | `server.py` の FastMCP。**本 Epic では温存**（削除は E4） |

## Architecture

削除前: `cli.py` が `full` / `server` / `headless` モードで FastAPI(`web.py`) と MCP を起動。
`full` は WebUI + MCP stdio、`server` は FastAPI に MCP SSE をマウント、`headless` は MCP SSE のみ。

削除後: WebUI / REST を撤去。MCP の起動経路（stdio）は残す（E4 まで）。
REST と MCP は同じ core サービス層（`_registry.py`）を共有するが、コードは独立しているため
`web.py` 削除は MCP tool に影響しない（ADR-0001 の調査で確認済み）。

## Module Responsibilities（削除 / 変更）

- `frontend/` — 削除
- `src/insight_blueprint/web.py` — 削除（REST API 全体 + static マウント）
- `src/insight_blueprint/cli.py` — WebUI 起動（`full` mode のブラウザオープン等）を除去。
  MCP stdio 起動は残す。`server` mode の MCP SSE 扱いは ## Decisions 参照
- `pyproject.toml` — `fastapi` / `uvicorn` 依存、static artifacts 設定、
  poe tasks（`install-frontend` / `build-frontend` / `build` / `ci` / `release-dry-run` /
  `verify-wheel`）の frontend 部分
- `scripts/verify_wheel.py` — static assets 検証部分
- `.github/workflows/ci.yml` — `frontend` ジョブ、`build-check` の frontend ステップ
- `.github/workflows/publish.yml` — frontend ビルドステップ
- `.github/dependabot.yml` — npm（`/frontend`）ブロック
- `.gitignore` — frontend / static 関連行
- `tests/test_web.py`, `tests/test_web_cli.py`, `tests/test_web_integration.py` — 削除
- `tests/test_reviews.py::TestSectionDefinitionSync`（:1254）— 削除（`frontend/.../sections.ts` を直接パースする契約テスト）
- `tests/test_packaging.py::TestStaticAssets`, `tests/test_verify_wheel.py` — 削除/修正
- `tests/test_cli.py` — WebUI 起動（`_start_server_mode` 等）のテストを修正

## Story 分解

各 Story はコードとテストを同じ単位で扱い、完了時に `pytest` 緑を確認する。

- **Story 1.1**: `frontend/` 削除 + `TestSectionDefinitionSync` 削除 + `.gitignore` の frontend/static 行削除
- **Story 1.2**: `web.py` 削除 + `cli.py` の WebUI 起動除去 + `test_web*.py` 3本削除 + `test_cli.py` の WebUI 部分修正
- **Story 1.3**: `pyproject.toml` クリーンアップ（fastapi/uvicorn 依存・artifacts・poe tasks）+ `scripts/verify_wheel.py` + `test_packaging.py` / `test_verify_wheel.py` 対応
- **Story 1.4**: CI クリーンアップ（`ci.yml` / `publish.yml` / `dependabot.yml`）

## Decisions

### Decision: server mode の MCP SSE 扱い

- **What**: `cli.py` の `server` mode（FastAPI に MCP SSE をマウント）は、`web.py` 削除に伴い
  扱いを決める。本 Epic では **MCP stdio 起動のみ残し、`server`/`full` mode の WebUI・FastAPI
  依存部分を除去**する。SSE 専用エンドポイントが必要かは実装時に `cli.py` を読んで判断し、
  不要なら mode を整理する。
- **Why**: WebUI を消すと `full` mode の存在意義が消える。MCP server 自体は E4 まで残すため、
  stdio 起動経路は維持する。
- **Affected modules**: `cli.py`, `web.py`
- **Consequences**: MCP は stdio で従来通り利用可。SSE 利用者がいた場合は E1 で影響が出るため、
  実装時に SSE 参照箇所を確認する。

### Cross-epic decisions (links to ADR)

- [ADR-0001](../adr/0001-drop-mcp-server-embed-validation.md) — MCPサーバ廃止・検証の埋め込み化

## Test Design Matrix

| Story \ Layer | Unit | Integration | E2E |
|---|---|---|---|
| Story 1.1 | ✓ | — | (frontend E2E 消滅) |
| Story 1.2 | ✓ | ✓ | — |
| Story 1.3 | ✓ | ✓ | — |
| Story 1.4 | — | ✓ (CI) | — |

完了時に ✓。pytest 全緑が Epic PR レビューゲート。

## Story Timeline

- 2026-06-29 — Epic 01 完了: WebUI/REST 削除（889 passed, 1 skipped）。
  Story 1.1 frontend削除 / 1.2 web.py+cli整理(stdio/headless mode) /
  1.3 pyproject+verify_wheel+packaging / 1.4 CI。MCP 機能は温存（削除は E4）。
