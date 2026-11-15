#!/usr/bin/env bash
# この clone に Claude Code のプラグインを入れる。clone ごとに1回実行する。冪等。
# どのプラグインを使うかの宣言は .claude/settings.json にある（docs/adr/flow/0004）。
# 宣言だけではプラグインは入らないので、ここで marketplace の追加と導入を行う。
# 使い方: ./scripts/install-plugins.sh
set -uo pipefail

if ! command -v claude >/dev/null 2>&1; then
  echo "skip: claude CLI が見つからない。Claude Code の /plugin を開き、Errors に出るプラグインを入れる" >&2
  exit 0
fi

failed=0
install_plugin() {
  # $1: marketplace の GitHub repo、$2: <plugin>@<marketplace>
  if claude plugin marketplace add "$1" --scope project && claude plugin install "$2" --scope project; then
    return
  fi
  echo "warn: $2 を入れられなかった。Claude Code の /plugin から入れる" >&2
  failed=1
}

# 第三者のプラグインは tag で固定する。上げるときは .claude/settings.json の ref と一緒に変える（docs/adr/flow/0004）。
install_plugin "nanaism/yomiyasu#v3.1.0" "yomiyasu@yomiyasu"
install_plugin "etoyama/decision-analysis" "decision-analysis@decision-analysis"

if [ "$failed" -eq 0 ]; then
  echo "plugins done: yomiyasu / decision-analysis（次に Claude Code を起動したときに読み込まれる）"
fi
