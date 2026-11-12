"""snow_docs_compare's page comparison against real indexes (skipped unless
SNOW_DOCS_TEST_AUSTRALIA_DB and SNOW_DOCS_TEST_BRAZIL_DB name them): it must not report rendering differences as changes, and stay fast."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from snow_docs_mcp.compare import PageDiff, compare_pages

# Point these at real index files to run the check, e.g. the active ones in the data folder.
DBS = {
    r: Path(os.environ.get(f"SNOW_DOCS_TEST_{r.upper()}_DB", "/nonexistent"))
    for r in ("australia", "brazil")
}
pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in DBS.values()),
    reason="set SNOW_DOCS_TEST_AUSTRALIA_DB and SNOW_DOCS_TEST_BRAZIL_DB",
)


def _doc(release: str, path: str) -> str:
    con = sqlite3.connect(f"file:{DBS[release]}?mode=ro", uri=True)
    try:
        return con.execute("SELECT content FROM documents WHERE file_path = ?", (path,)).fetchone()[
            0
        ]
    finally:
        con.close()


def _shared_paths() -> list[str]:
    sets = []
    for db in DBS.values():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        sets.append({r[0] for r in con.execute("SELECT file_path FROM documents")})
        con.close()
    return sorted(p for p in sets[0] & sets[1] if not p.startswith("markdown/delta-"))


def test_real_indexes_noise_and_speed():
    sample = _shared_paths()[::250][:200]
    assert len(sample) >= 150
    pages = [(_doc("australia", p), _doc("brazil", p)) for p in sample]
    t = time.monotonic()
    changed = [p for p, (a, b) in zip(sample, pages, strict=True) if compare_pages(a, b).sections]
    assert time.monotonic() - t < 5.0
    assert len(changed) <= 10, changed


def test_real_known_unchanged_page():
    path = "markdown/acct-lifecycle-events/account-lifecycle-360-view-reco-actions.md"
    assert compare_pages(_doc("australia", path), _doc("brazil", path)) == PageDiff([], 0)
