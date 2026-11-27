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

# commit の前に lint・typecheck・test を、push の前に uv run poe all を回す。
# hook は clone の .git に入るので、同じ clone のワークツリーすべてに効く
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
CHANGELOG を見る構造テストは、`## [Unreleased]` や版の見出しを名指しせず、`tests/docs/_changelog.py` の `changelog_entry` で本文の語句から節を引く（リリースで節が移っても書き換えずに済む）。

### Trying an Epic branch in another project

Epic PR を出す前に、実データを持つ分析を行うプロジェクトで、Epic ブランチの plugin を試す手順。
`<N>` は Epic の issue 番号、`<clone>` は Epic ブランチを clone したフォルダの絶対パス、
`<project>` は試す側のプロジェクトのフォルダ（ワークツリーで試すならそのワークツリー）を指す。

アプリのセッションでは `claude --plugin-dir <clone>` を使えない（CLI では効く）。そこで、
clone をそのまま marketplace として local の範囲に入れる。
`<project>/.claude/settings.local.json` の `extraKnownMarketplaces` に clone を書き足すだけでは、plugin は読まれない。

#### Prepare

1. Epic ブランチを clone し、`<project>/.claude/settings.local.json` の写しを取っておく。

   ```bash
   git clone -b epic/<N>-<slug> https://github.com/etoyama/insight-blueprint-skills.git <clone>
   cp <project>/.claude/settings.local.json <clone>/settings.local.json.bak
   ```

2. `<clone>/.claude-plugin/marketplace.json` を手元だけで書き換える。コミットはしない。
   `name` を `insight-blueprint-epic<N>` に、plugin の `source` を `"./"` にする。
3. `<project>` で marketplace と plugin を local の範囲に入れる。

   ```bash
   cd <project>
   claude plugin marketplace add <clone> --scope local
   claude plugin install insight-blueprint@insight-blueprint-epic<N> --scope local
   ```

4. リリース版が同時に読まれないように、`<project>/.claude/settings.local.json` の `enabledPlugins` で
   `insight-blueprint@insight-blueprint-marketplace` を `false` にする。
5. 新しいセッションを `<project>` で立てる。

#### Trying in a worktree

`<project>` がワークツリーのときは、その git の本体のフォルダを `<main>` と書く。
ワークツリーで 3 を走らせても、`--scope local` が書く先は `<main>/.claude/settings.local.json` だった
（2026-11-28、Claude Code 2.1.332）。一方、ワークツリーで立てたセッションは
`<project>/.claude/settings.local.json` を読む。そこで、次のように準備する。

1. Prepare の 1 で、`<main>` の設定の写しも取っておく。

   ```bash
   cp <main>/.claude/settings.local.json <clone>/main.settings.local.json.bak
   ```

2. Prepare の 4 は `<main>/.claude/settings.local.json` で行う。その後、`<main>` の設定の
   `enabledPlugins` と `extraKnownMarketplaces` を、`<project>/.claude/settings.local.json` にそのまま写す。
   ファイルが無ければ、この2つのキーだけのファイルを作る。
3. `<project>` で `claude plugin list` を走らせ、`insight-blueprint@insight-blueprint-epic<N>` が
   enabled、リリース版が disabled と出ることを確かめる。

#### Check

skill の一覧で確かめてはいけない。skill はどれも `disable-model-invocation: true` なので、
読まれていても Claude の skill 一覧には出ない。代わりに、`<project>` のセッションで次を走らせる。

```bash
which design_io   # <clone>/bin か、~/.claude/plugins/cache/insight-blueprint-epic<N>/ の下を指せば読まれている
```

人間が確かめるなら、`/` の候補に `/analysis-design` が出るかを見る。

試すセッションに渡す指示（PM のブリーフなど）にも、skill の一覧で確かめない、と書く。
確かめ方はこの節から写す。skill はどれも Claude からは起動できないので、
`/insight-blueprint:analysis-auto` などは人間がセッションに打つ。

#### Undo

```bash
cd <project>
claude plugin uninstall insight-blueprint@insight-blueprint-epic<N> --scope local
claude plugin marketplace remove insight-blueprint-epic<N>
rm -rf ~/.claude/plugins/cache/insight-blueprint-epic<N>
cp <clone>/settings.local.json.bak <project>/.claude/settings.local.json
rm -rf <clone>
```

ワークツリーで試したなら、uninstall と marketplace の remove は `<main>` で走らせる。
`rm -rf <clone>` の前に、`<main>` の設定を写しから戻す。`<project>` の設定は Prepare の 1 の写しから戻す。

```bash
cp <clone>/main.settings.local.json.bak <main>/.claude/settings.local.json
```

アプリで、他のセッションのワークツリーを cwd にして立てたセッションは、アーカイブしない。
アーカイブはセッションのワークツリーを片付けることがあり、試した分析のワークツリーまで消えうる。
サイドバーから人間が消す。

## Security Checklist

PR を出す前に確かめる。

- [ ] API キー・パスワード・秘密情報をハードコードしていない
- [ ] 秘密の値は環境変数から読む
- [ ] `.env` をコミットしていない
- [ ] 外部からの入力を検証している（Pydantic のモデルを使う）
- [ ] 利用者に見せるエラーメッセージが内部の詳細を出さない
- [ ] ログに秘密情報が出ない
