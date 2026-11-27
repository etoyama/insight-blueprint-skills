"""Atomic YAML / text write helpers with file-lock protection.

Pattern adapted from ``src/insight_blueprint/storage/yaml_store.py``
(copied, not imported — CR-2 / CR-3 compliance).
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from filelock import FileLock
from ruamel.yaml import YAML


def _make_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def atomic_write_yaml(path: Path, data: Any) -> None:
    """Write *data* to *path* as YAML, atomically.

    * tempfile is created in the **same directory** (cross-device rename
      avoidance).
    * ``filelock.FileLock`` serialises concurrent / cross-process writes.
    * Parent directories are created on demand.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lock = FileLock(str(path) + ".lock")
    with lock:
        yaml = _make_yaml()
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically (same guarantees as YAML variant)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lock = FileLock(str(path) + ".lock")
    with lock:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


# One lock per .insight base dir, kept for the life of the process: a FileLock
# instance counts how often its holder took it, so a writer that calls another
# writer under the lock takes it again instead of waiting on itself.
_WRITE_LOCKS: dict[Path, FileLock] = {}
# Two threads that met a new base dir at once would each build a FileLock, and
# a nested writer of the first would then wait on the second: on its own lock.
_WRITE_LOCKS_GUARD = threading.Lock()

WRITE_LOCK_NAME = ".write.lock"


@contextmanager
def write_lock(base_dir: Path) -> Iterator[None]:
    """Hold the lock of *base_dir* from reading a record to writing it back (ADR-0062).

    The lock of ``atomic_write_yaml`` covers only the moment of the write: two
    processes that read the same highest id both write it. Every writer of
    ``design_io`` and ``tree_io`` takes this one lock per ``.insight``, so no
    two writers interleave and no order of locks can deadlock.
    """
    path = Path(base_dir).resolve() / WRITE_LOCK_NAME
    with _WRITE_LOCKS_GUARD:
        lock = _WRITE_LOCKS.get(path)
        if lock is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = _WRITE_LOCKS[path] = FileLock(str(path))
    with lock:
        yield
