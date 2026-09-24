"""Read-only access to the downloaded index: hybrid search, documents, metadata.

The index is one SQLite file:

    chunks(id, file_path, heading_path, content, byte_offset, embedding)
        content   = "<context line>\\n\\n<breadcrumb>\\n\\n<body>" — the context line is the
                    LLM-written situating sentence that makes contextual retrieval work
        embedding = float32 bytes of the L2-normalised bge-small vector of `content`
    chunks_fts   FTS5 (BM25) over chunks.content
    documents(file_path, content)   the full markdown of every indexed page
    meta(key, value)                provenance: snapshot, corpus commit, models, ...

Search is semantic (cosine over an in-memory matrix) + keyword (BM25), fused with
Reciprocal Rank Fusion. The matrix is loaded once per file mtime and cached.

The file is opened read-only (a `file:` URI with mode=ro; for Windows UNC/network paths,
which SQLite rejects as URIs, a plain path with `PRAGMA query_only`). The shipped index uses
a rollback journal and never needs WAL sidecars, so nothing is ever written next to it.

Newer indexes record each chunk's context-line length in `chunks.context_chars` (0 = the
chunk has no context line yet); older ones have no such column and every chunk has one.
"""

# Retrieval code copied (not imported) from the research spike's search module, with its
# constants unchanged, so rankings match the measured contextual-retrieval result. Local
# changes: read-only connections, no write/build helpers, plus products()/get_document()/meta().

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EMBED_DIM = 384

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF paper and the
# de-facto standard; it damps the influence of low ranks.
RRF_K = 60
# How many candidates to pull from each ranker before fusing — larger than any real top_k,
# so fusion has enough overlap to work with.
HYBRID_POOL = 100

_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class SearchHit:
    file_path: str
    heading_path: str
    content: str
    score: float  # cosine similarity; or reranker relevance after reranking
    byte_offset: int = 0  # where the chunk starts in its page (picks among repeated headings)
    context_chars: int | None = None  # length of the context-line prefix; None = unknown


def _connect(db_path: str | Path) -> sqlite3.Connection:
    """Open the index read-only. Each call opens (and the caller closes) its own connection,
    so no file handle stays open between calls (Windows can then delete old snapshots)."""
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"docs index not found: {path}")
    raw = str(path.resolve())
    if raw.startswith("\\\\"):  # Windows UNC path: SQLite rejects these as URIs
        conn = sqlite3.connect(raw, check_same_thread=False)
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False
        )
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


_has_context_col: dict[str, bool] = {}


def _context_column(db_path: str | Path) -> bool:
    key = str(Path(db_path).resolve())
    if key not in _has_context_col:
        conn = _connect(db_path)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(chunks)")}
        finally:
            conn.close()
        _has_context_col[key] = "context_chars" in cols
    return _has_context_col[key]


def forget(db_path: str | Path) -> None:
    """Drop everything cached for an index file (after switching to a newer snapshot)."""
    key = str(Path(db_path).resolve())
    with _cache_lock:
        _matrix_cache.pop(key, None)
    _has_context_col.pop(key, None)
    _products_cache.pop(key, None)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Return a unit-norm copy of `vectors`. Treats zero rows as zero (no NaN)."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    safe = np.where(norms == 0, 1.0, norms)
    return (vectors / safe).astype(np.float32, copy=False)


# --- Search-time matrix cache ---------------------------------------------------------

_cache_lock = threading.Lock()
# Held across a whole matrix load so parallel first searches load it once, not N times.
_load_lock = threading.Lock()
# key: resolved-absolute db_path string
# value: (db_mtime, ids ndarray, file_paths list, matrix ndarray, pos_by_id dict)
_matrix_cache: dict[str, tuple[float, np.ndarray, list[str], np.ndarray, dict]] = {}


def _db_mtime(db_path: str) -> float:
    times = [os.path.getmtime(db_path)]
    try:
        times.append(os.path.getmtime(db_path + "-wal"))
    except FileNotFoundError:
        pass
    return max(times)


def retain(db_paths: set[Path]) -> None:
    """Drop cached matrices (~0.4 GB each) of every index not in `db_paths`: after a switch
    to a newer snapshot, the old one's stays in memory otherwise, even while its file is
    still on disk (in use elsewhere, or a delete that Windows refused)."""
    keep = {str(Path(p).resolve()) for p in db_paths}
    with _cache_lock:
        stale = [k for k in _matrix_cache if k not in keep]
    for k in stale:
        forget(k)


def _load_matrix(db_path: str | Path) -> tuple[np.ndarray, list[str], np.ndarray, dict]:
    """Return (ids, file_paths, embeddings_matrix, pos_by_id), cached by mtime."""
    key = str(Path(db_path).resolve())
    mtime = _db_mtime(key)
    with _cache_lock:
        cached = _matrix_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2], cached[3], cached[4]

    with _load_lock:
        with _cache_lock:  # another thread may have loaded it while we waited
            cached = _matrix_cache.get(key)
            if cached and cached[0] == mtime:
                return cached[1], cached[2], cached[3], cached[4]
            # Before loading, drop matrices whose index file is gone (another Claude app
            # switched snapshots and deleted it), so two never sit in memory at the peak.
            for stale in [k for k in _matrix_cache if not os.path.exists(k)]:
                del _matrix_cache[stale]

        # Stream rows straight into preallocated arrays (same values and row order as a
        # fetchall + join, without holding every row and a joined copy at once: ~0.5 GB less).
        conn = _connect(db_path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            ids = np.empty((n,), dtype=np.int64)
            matrix = np.empty((n, EMBED_DIM), dtype=np.float32)
            file_paths: list[str] = []
            rows = conn.execute("SELECT id, file_path, embedding FROM chunks")
            for i, (cid, fp, emb) in enumerate(rows):
                ids[i] = cid
                file_paths.append(fp)
                matrix[i] = np.frombuffer(emb, dtype=np.float32)
        finally:
            conn.close()

        pos_by_id = {int(cid): i for i, cid in enumerate(ids)}

        with _cache_lock:
            _matrix_cache[key] = (mtime, ids, file_paths, matrix, pos_by_id)
    return ids, file_paths, matrix, pos_by_id


def _fts_query(text: str) -> str:
    """Build a safe FTS5 MATCH string: every word token quoted, OR-joined. "" if none."""
    tokens = _FTS_TOKEN_RE.findall(text)
    if not tokens:
        return ""
    return " OR ".join(f'"{tok}"' for tok in tokens)


def _bm25_search(
    db_path: str | Path,
    query_text: str | None,
    file_path_prefix: str | None,
    pos_by_id: dict,
    file_paths: list[str],
    limit: int,
) -> list[int] | None:
    """Return chunk ids ranked by BM25 (best first), or None to fall back to semantic-only."""
    if not query_text:
        return None
    match = _fts_query(query_text)
    if not match:
        return None

    # With a prefix filter we post-filter in Python, so over-scan to keep a useful pool.
    fetch = limit * 10 if file_path_prefix else limit
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY bm25(chunks_fts) LIMIT ?",
            (match, fetch),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

    bm25_ids = [int(r[0]) for r in rows]
    if file_path_prefix:
        bm25_ids = [
            cid
            for cid in bm25_ids
            if cid in pos_by_id and file_paths[pos_by_id[cid]].startswith(file_path_prefix)
        ][:limit]
    return bm25_ids


def _rrf_fuse(*rankings: Sequence[int]) -> list[int]:
    """Reciprocal Rank Fusion: score(id) = sum 1 / (RRF_K + rank). Best first."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(fused, key=lambda cid: fused[cid], reverse=True)


def _top_ids(score_array: np.ndarray, ids: np.ndarray, limit: int) -> list[int]:
    """Up to `limit` chunk ids by descending score; -inf entries (filtered out) excluded."""
    valid = int((score_array > -np.inf).sum())
    k = min(limit, valid)
    if k <= 0:
        return []
    top = np.argpartition(-score_array, k - 1)[:k]
    top = top[np.argsort(-score_array[top])]
    return [int(ids[i]) for i in top]


def _hydrate_hits(
    db_path: str | Path,
    ordered_ids: Sequence[int],
    scores: np.ndarray,
    pos_by_id: dict,
) -> list[SearchHit]:
    """Fetch chunk rows for `ordered_ids` and build SearchHits in that order."""
    if not ordered_ids:
        return []
    placeholders = ",".join(["?"] * len(ordered_ids))
    ctx = "context_chars" if _context_column(db_path) else "NULL"
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT id, file_path, heading_path, content, byte_offset, {ctx} FROM chunks "
            f"WHERE id IN ({placeholders})",
            list(ordered_ids),
        ).fetchall()
    finally:
        conn.close()

    by_id = {row[0]: row for row in rows}
    hits: list[SearchHit] = []
    for cid in ordered_ids:
        row = by_id.get(cid)
        if row is None:
            continue
        pos = pos_by_id.get(cid)
        score = float(scores[pos]) if pos is not None else 0.0
        hits.append(
            SearchHit(
                file_path=row[1],
                heading_path=row[2],
                content=row[3],
                score=score,
                byte_offset=row[4],
                context_chars=row[5],
            )
        )
    return hits


def search(
    db_path: str | Path,
    query_vector: np.ndarray,
    *,
    top_k: int = 5,
    file_path_prefix: str | None = None,
    query_text: str | None = None,
) -> list[SearchHit]:
    """Hybrid search: cosine + (when `query_text` is given) BM25, fused with RRF.

    `score` on each hit is always the cosine similarity, however the order was produced.
    """
    if query_vector.shape != (EMBED_DIM,):
        raise ValueError(f"query_vector must be shape ({EMBED_DIM},), got {query_vector.shape}")
    ids, file_paths, matrix, pos_by_id = _load_matrix(db_path)
    if len(ids) == 0:
        return []

    query_vec = _l2_normalize(query_vector.reshape(1, -1).astype(np.float32))[0]
    scores = matrix @ query_vec  # (N,) cosine similarities (vectors are L2-normalised)

    if file_path_prefix:
        mask = np.fromiter(
            (fp.startswith(file_path_prefix) for fp in file_paths),
            dtype=bool,
            count=len(file_paths),
        )
        if not mask.any():
            return []
        masked_scores = np.where(mask, scores, -np.inf)
    else:
        masked_scores = scores

    pool = max(HYBRID_POOL, top_k)
    semantic_ids = _top_ids(masked_scores, ids, pool)
    if not semantic_ids:
        return []

    bm25_ids = _bm25_search(db_path, query_text, file_path_prefix, pos_by_id, file_paths, pool)
    if bm25_ids is None:
        ranked_ids = semantic_ids[:top_k]
    else:
        ranked_ids = _rrf_fuse(semantic_ids, bm25_ids)[:top_k]

    return _hydrate_hits(db_path, ranked_ids, scores, pos_by_id)


# --- Everything else the tools need ---------------------------------------------------

_products_cache: dict[str, tuple[float, list[str]]] = {}


def products(db_path: str | Path) -> list[str]:
    """Top-level product folders present in the index (the `product` filter's values)."""
    key = str(Path(db_path).resolve())
    mtime = _db_mtime(key)
    cached = _products_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    _, file_paths, _, _ = _load_matrix(db_path)
    names = sorted({product_of(fp) for fp in file_paths} - {""})
    _products_cache[key] = (mtime, names)
    return names


def product_of(file_path: str) -> str:
    """'markdown/<product>/page.md' -> '<product>'; '' when the path has no product folder."""
    parts = file_path.split("/")
    if len(parts) >= 3 and parts[0] == "markdown":
        return parts[1]
    return ""


def get_document(db_path: str | Path, file_path: str) -> str | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT content FROM documents WHERE file_path = ?", (file_path,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def chunk_count(db_path: str | Path) -> int:
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    finally:
        conn.close()


def meta(db_path: str | Path) -> dict[str, str]:
    conn = _connect(db_path)
    try:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
