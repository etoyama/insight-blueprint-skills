# Technology Stack

## Project Type

MCP (Model Context Protocol) サーバー + React WebUI ダッシュボード。Claude Code と協働するデータ分析ワークフロー管理ツール。

## Core Technologies

### Primary Language(s)

- **Backend**: Python 3.11+ (3.11 / 3.12 / 3.13 対応)
- **Frontend**: TypeScript 5.7+
- **Runtime**: CPython, Node.js (frontend build)

### Key Dependencies/Libraries

#### Backend
- **FastMCP >= 2.0**: MCP サーバーフレームワーク。ツール定義とプロトコル処理
- **Pydantic >= 2.10**: データモデル定義、バリデーション、シリアライズ
- **ruamel.yaml >= 0.18**: YAML の読み書き（コメント保持、ラウンドトリップ対応）
- **FastAPI >= 0.115**: REST API サーバー（WebUI バックエンド）
- **uvicorn >= 0.41.0**: ASGI サーバー（FastAPI 用）
- **Click >= 8.1**: CLI エントリポイント
- **filelock >= 3.24.2**: ファイルレベルの排他制御
- **packaging >= 23.0**: バージョン比較ユーティリティ

#### Frontend
- **React 19**: UI フレームワーク
- **Tailwind CSS 4**: ユーティリティファーストCSS
- **Radix UI**: アクセシブルなヘッドレスUIコンポーネント
- **shadcn/ui**: Radix UI ベースのスタイル済みコンポーネント
- **Lucide React**: アイコンライブラリ
- **Vite 6**: ビルドツール + 開発サーバー

### Application Architecture

レイヤードアーキテクチャ + Service Locator パターン:

```
models/     → Pydantic データモデル（ドメインモデル）
storage/    → YAML / SQLite 永続化層
core/       → ビジネスロジック（Service 層）
server.py   → MCP ツール定義（MCP インターフェース）
web.py      → REST API エンドポイント（WebUI インターフェース）
cli.py      → エントリポイント + サービス配線
_registry.py → Service Locator（cli.py で配線、server.py/web.py で参照）
```

依存方向: `server.py / web.py → core/ → storage/ → models/`（逆方向の依存は禁止）

### Data Storage

- **Primary storage**: YAML ファイル（`.insight/` ディレクトリ配下）— Source of Truth
- **Search index**: SQLite FTS5（全文検索用の派生インデックス、YAML から再構築可能）
- **Atomic writes**: tempfile + `os.replace()` によるアトミック書き込み
- **File locking**: `filelock` による排他制御
- **Data formats**: YAML（永続化）、JSON（API レスポンス）

### External Integrations

- **Protocol**: MCP (Model Context Protocol) — Claude Code との通信
- **HTTP/REST**: FastAPI による REST API — WebUI との通信
- **Authentication**: なし（ローカルアクセス前提）

### Monitoring & Dashboard Technologies

- **Dashboard Framework**: React 19 + Tailwind CSS 4 + shadcn/ui
- **Real-time Communication**: ポーリングベース（WebSocket 未実装）
- **State Management**: React hooks（useState/useEffect）、サーバーサイドが Source of Truth
- **Hosting**: MCP サーバーと同プロセスでデーモンスレッド起動（`http://127.0.0.1:3000`）

## Development Environment

### Build & Development Tools

- **Package Management (Python)**: uv（pip 直接使用禁止）
- **Package Management (Frontend)**: npm
- **Build System**: hatchling（Python wheel）、Vite（frontend bundle）
- **Task Runner**: poethepoet（`poe lint`, `poe test`, `poe all` 等）
- **Frontend dev**: `npm --prefix frontend run dev`（Vite HMR）

### Code Quality Tools

- **Linter/Formatter**: ruff（Python）
- **Type Checker**: ty（Python、Astral 製 Rust ベース）
- **Testing**: pytest（Python 548+ tests）、Playwright（E2E）
- **Coverage**: pytest-cov

### Version Control & Collaboration

- **VCS**: Git
- **Branching Strategy**: GitHub Flow（main + feature branches）
- **Code Review**: spec-workflow ベースの承認フロー

## Deployment & Distribution

- **Target Platform**: ローカルマシン（macOS / Linux）
- **Distribution**: Claude Code plugin（marketplace 経由）+ optional な lineage ライブラリ `insight-blueprint-lineage`（PyPI）
- **Installation**: `/plugin marketplace add etoyama/insight-blueprint-skills` → `/plugin install insight-blueprint@insight-blueprint-marketplace`; lineage は `uv add insight-blueprint-lineage`
- **Entry point**: Claude Code の skills（`/analysis-*` 等）。専用 CLI は無い

## Technical Requirements & Constraints

### Performance Requirements

- MCP ツールのレスポンス: 500ms 以内（knowledge 100件以下の想定）
- SQLite FTS5 検索: 100ms 以内
- WebUI API レスポンス: 200ms 以内

### Compatibility Requirements

- **Python**: 3.11 / 3.12 / 3.13
- **OS**: macOS, Linux（Windows は未検証）
- **MCP Protocol**: FastMCP 2.0 互換

### Security & Compliance

- ローカルアクセス前提（認証なし）
- API キー等のシークレットは環境変数で管理
- ファイルシステムベースのデータ保護

## Development Principles

### TDD (テスト駆動開発)

t-wada 流の TDD を採用。Red-Green-Refactor サイクルを基本とする:

1. **Red**: 失敗するテストを先に書く（テストが仕様）
2. **Green**: テストを通す最小限の実装を書く
3. **Refactor**: テストが通った状態でリファクタリング

テストコードは正（仕様）として扱い、実装コードのみを修正対象とする。

### YAGNI (You Aren't Gonna Need It)

- 今必要でない機能は作らない
- 過剰な抽象化・汎用化を避ける
- 「将来使うかもしれない」は作らない理由になる
- 3回同じパターンが出るまで抽象化しない（Rule of Three）
- パターンが不要なら使わない。シンプルな実装を優先する

## Technical Decisions & Rationale

### Decision Log

1. **YAML as Source of Truth**: 人間が読める形式でデータを永続化。Git での diff/merge が容易。SQLite はあくまで検索用の派生インデックス
2. **Service Locator パターン**: DI コンテナの導入は過剰。`_registry.py` でシンプルに配線し、`cli.py` で初期化
3. **FastMCP**: MCP プロトコルの実装を抽象化し、ツール定義に集中できる
4. **StrEnum for all enums**: Python 3.11+ の StrEnum を全 enum に使用。シリアライズが自然で YAML との相性が良い
5. **Atomic YAML writes**: tempfile + `os.replace()` でデータ破損を防止

## Known Limitations

- **WebSocket 未実装**: ダッシュボードはポーリングベース。リアルタイム更新には対応していない
- **Single-user 前提**: 複数ユーザーの同時アクセスは想定していない
- **Windows 未検証**: macOS / Linux のみテスト済み
