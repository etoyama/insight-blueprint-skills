# Contributing to insight-blueprint-skills

このリポジトリに固有の、環境構築・コマンド・テスト・セキュリティの確認だけを書く。
ほかの規約は次の正本にある。

- 開発フロー（Epic / Story / DesignDoc / ADR、ブランチ、PR）: [docs/WORKFLOW.md](docs/WORKFLOW.md)
- AI と人間への行動指示、言語、レビュー: [CLAUDE.md](CLAUDE.md)
- YAGNI と TDD: [.claude/rules/coding-principles.md](.claude/rules/coding-principles.md)
- 用語: [docs/UBIQUITOUS_LANGUAGE.md](docs/UBIQUITOUS_LANGUAGE.md)

貢献したコードは [MIT License](LICENSE) で公開される。

## Setup

Python 3.11 以上と [uv](https://docs.astral.sh/uv/) を使う（pip は直接使わない）。

```bash
git clone https://github.com/etoyama/insight-blueprint-skills.git
cd insight-blueprint-skills

# --all-extras がないと ruff・ty・pytest・poe が入らない
uv sync --all-extras

# commit の前に lint・typecheck・test を回す
uv run pre-commit install

# .claude/settings.json で宣言したプラグイン（yomiyasu・decision-analysis）を入れる
./scripts/install-plugins.sh
```

## Common Commands

```bash
uv run poe lint            # lint と format の検査（ruff）
uv run poe format          # lint の自動修正と format
uv run poe typecheck       # 型検査（ty）
uv run poe test            # テスト（pytest）
uv run poe all             # lint + typecheck + test。PR の前に必ず通す
```

## Testing

```bash
uv run pytest tests/test_validate.py -v           # 1ファイル
uv run pytest tests/test_validate.py::test_name   # 1テスト
uv run pytest --cov=src --cov-report=term-missing # カバレッジつき
```

TDD の進め方は [coding-principles](.claude/rules/coding-principles.md)、SKILL.md と文書の TDD の読み方は
[ADR-0010](docs/adr/0010-skill-tdd-structure-tests.md) にある。
skill の構造テストは `tests/skills/`、正本の文書の構造テストは `tests/docs/` に置く。

## Security Checklist

PR を出す前に確かめる。

- [ ] API キー・パスワード・秘密情報をハードコードしていない
- [ ] 秘密の値は環境変数から読む
- [ ] `.env` をコミットしていない
- [ ] 外部からの入力を検証している（Pydantic のモデルを使う）
- [ ] 利用者に見せるエラーメッセージが内部の詳細を出さない
- [ ] ログに秘密情報が出ない
