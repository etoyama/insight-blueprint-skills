"""How a skill runs the notebook, shared by the structure tests of every skill that runs it.

/analysis-notebook and /data-lineage run the same notebook in the plugin env. Both test
files assert against these constants, so a drift between the two skills fails a test.
"""

from __future__ import annotations

import re

RUN = (
    'uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook '
    "python .insight/notebooks/{id}.py"
)
# `--with insight-blueprint-lineage` would layer the frozen PyPI copy over the plugin's
# own source, so each place that tells when to pass `--with` names the exclusion.
WITH_SCOPE = "in neither the `notebook` extra nor the default allowlist"
WITH_EXCLUSION = (
    "never pass a default-allowlist package such as `insight_blueprint` to `--with`"
)


def commands(markdown: str) -> list[str]:
    """The shell commands of the bash blocks, with ``\\`` continuations joined."""
    blocks = re.findall(r"```bash\n(.*?)```", markdown, re.DOTALL)
    joined = [re.sub(r"\\\n\s*", "", block) for block in blocks]
    return [
        line.strip()
        for block in joined
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
