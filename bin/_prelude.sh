# Shared prelude of the bin/ wrappers. Sourced, never run: no exec bit, so the PATH
# lookup that finds the wrappers skips it.
#
# Plugin skill commands run in the user's project cwd, but `skills._shared` and
# `insight_blueprint` live in the plugin. A wrapper runs its module from the plugin's
# own uv project (which self-provides both) and points it at the user's project
# `.insight/` via INSIGHT_BASE_DIR. See docs/adr/0006-plugin-execution-model.md.
#
# The wrapper sets before sourcing:
#   name        its own name, for error messages
#   setup_exit  exit code when setup fails (2 for the checkers, where 1 means "violations found")

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
# Claude Code puts bin/ on the Bash tool's PATH but does not export CLAUDE_PLUGIN_ROOT
# there, so fall back to the wrapper's own plugin (bin/ sits directly under the root).
# ADR-0017.
cd "${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}"

# Anchor the data base before it becomes a read/write root (defense in depth, ADR-0006 M1).
# proj must be an existing directory and the base must live at <proj>/.insight — reject
# anything else rather than mkdir/write under an attacker-influenced path.
[ -d "$proj" ] || { echo "$name: project dir '$proj' does not exist" >&2; exit "$setup_exit"; }
export INSIGHT_BASE_DIR="$proj/.insight"
case "$INSIGHT_BASE_DIR" in
  */.insight) ;;
  *) echo "$name: refusing base '$INSIGHT_BASE_DIR' (must end in /.insight)" >&2; exit "$setup_exit";;
esac

# Persist the uv venv across plugin updates when a data dir is available.
if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
  export UV_PROJECT_ENVIRONMENT="$CLAUDE_PLUGIN_DATA/uv-venv"
fi
