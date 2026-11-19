"""The id pattern every CLI checks before it builds a path from an id.

An id is interpolated into paths such as ``{id}_hypothesis.yaml`` and
``reports/{id}.md``, so anything that could leave the directory (a separator,
``..``, a space) is rejected. This module imports nothing else, so a read-only
command can use it without loading the pydantic models.
"""

from __future__ import annotations

import re

SAFE_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")
