"""The two local ONNX models, loaded lazily as process-wide singletons.

    embedder  BAAI/bge-small-en-v1.5   (~64 MB)   turns the query into a 384-dim vector
    reranker  BAAI/bge-reranker-base   (~1.1 GB)  re-scores the top candidates jointly with
                                                   the query (more accurate, slower)

Both download from HuggingFace on first use into `<data folder>/models` (never a temp dir,
which macOS clears) and run on CPU. No LLM is involved at query time.
"""

# Model wrappers copied (not imported) from the research spike's embedder/reranker modules;
# local change: an explicit, persistent cache_dir, and warm_up().

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence

import numpy as np

from snow_docs_mcp.config import models_dir
from snow_docs_mcp.store import EMBED_DIM

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
RERANK_MODEL_NAME = "BAAI/bge-reranker-base"
# How many hybrid-search candidates the cross-encoder re-scores. Wider than any real top_k.
RERANK_POOL = 25
# Candidates per reranker batch. fastembed's default (64) scores all 25 in one padded batch,
# which grows onnxruntime's memory arena by ~1.3 GB; batches of 8 keep it to ~0.2 GB.
# Padding differs per batch, which moves scores by <1e-5 and no rankings (parity: 67/67
# identical top-10s against the research pipeline, max score difference 8.8e-6).
RERANK_BATCH_SIZE = 8

_embed_lock = threading.Lock()
_rerank_lock = threading.Lock()
# One rerank at a time: tools run in worker threads, and every concurrent rerank grows
# onnxruntime's memory arena (measured: 3 parallel searches 3.7 GB, 5 -> 4.6 GB, 8 -> 5.8 GB).
_rerank_run_lock = threading.Lock()
_embedder = None  # type: ignore[var-annotated]
_reranker = None  # type: ignore[var-annotated]


def _get_embedder():
    global _embedder
    if _embedder is None:
        with _embed_lock:
            if _embedder is None:
                from fastembed import TextEmbedding

                _embedder = TextEmbedding(model_name=EMBED_MODEL_NAME, cache_dir=str(models_dir()))
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _rerank_lock:
            if _reranker is None:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                _reranker = TextCrossEncoder(
                    model_name=RERANK_MODEL_NAME, cache_dir=str(models_dir())
                )
    return _reranker


def embed(texts: Iterable[str]) -> np.ndarray:
    """Embed texts. Returns a (N, EMBED_DIM) float32 array."""
    text_list: list[str] = list(texts)
    if not text_list:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    return np.asarray(list(_get_embedder().embed(text_list)), dtype=np.float32)


def embed_one(text: str) -> np.ndarray:
    """Embed one string. Returns a (EMBED_DIM,) float32 array."""
    return embed([text])[0]


def rerank(query: str, documents: Sequence[str]) -> list[float]:
    """Relevance of each document to `query`, in input order. Higher is more relevant."""
    docs = list(documents)
    if not docs:
        return []
    reranker = _get_reranker()
    with _rerank_run_lock:
        return list(reranker.rerank(query, docs, batch_size=RERANK_BATCH_SIZE))


def warm_up() -> None:
    """Download (first run only) and load both models, then run each once."""
    embed_one("warm up")
    rerank("warm up", ["warm up"])
