"""Table names the docs mention.

The docs write a table as its label and name, "Incident [incident]". Every lowercase name in
square brackets across an index is collected (about 10,000; fields written the same way are
among them). It is only used to notice a table name that appears nowhere in the docs, so the
extra names do no harm. Reading every page takes a couple of seconds, so the list is kept in
the data folder, one small file per index.
"""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path

from snow_docs_mcp import config, store

_BRACKETED = re.compile(r"\\?\[([a-z][a-z0-9_\\]{2,})\\?\](?!\()")
_memory: dict[str, frozenset[str]] = {}


def scan(db_path: str | Path) -> frozenset[str]:
    return frozenset(
        m.group(1).replace("\\", "")
        for text in store.contents(db_path)
        for m in _BRACKETED.finditer(text)
    )


CACHE_PREFIX = "tables-"


def cache_file(db_path: str | Path) -> Path:
    """Where the names of one index are kept: `tables-<index file name>.json`."""
    return config.data_home() / f"{CACHE_PREFIX}{Path(db_path).stem}.json"


def forget(db_path: str | Path) -> None:
    """Drop the names of an index that is being deleted: from memory and from disk."""
    _memory.pop(str(db_path), None)
    with contextlib.suppress(OSError):
        cache_file(db_path).unlink(missing_ok=True)


def names(db_path: str | Path) -> frozenset[str]:
    """The names for one index: from memory, else its cache file, else a scan (cached)."""
    key = str(db_path)
    if key in _memory:
        return _memory[key]
    cache = cache_file(db_path)
    found: frozenset[str] | None = None
    with contextlib.suppress(OSError, ValueError, TypeError):
        found = frozenset(json.loads(cache.read_text(encoding="utf-8")))
    if not found:
        found = scan(db_path)
        with contextlib.suppress(OSError):  # the list still works without its cache
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(sorted(found)), encoding="utf-8")
            tmp.replace(cache)
    _memory[key] = found
    return found
