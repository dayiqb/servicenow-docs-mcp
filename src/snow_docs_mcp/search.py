"""Search orchestration and the helpers that turn stored chunks into what users see.

`run_search` reproduces the measured configuration exactly: embed the query, hybrid
retrieve (BM25 gets the raw query), then — with rerank on — re-score a pool of
RERANK_POOL candidates with the cross-encoder and reorder. The cross-encoder sees the
stored content INCLUDING its context line; that is what was measured. The context line is
only stripped from text shown to people (`strip_blurb`).
"""

# run_search copied (not imported) from the research spike's searcher module; the only
# change is the import of the model wrappers from this package.

from __future__ import annotations

import re
from pathlib import Path

from snow_docs_mcp import models
from snow_docs_mcp.store import SearchHit, search

ID_SEPARATOR = "::"


def run_search(
    db_path: str | Path,
    query: str,
    *,
    top_k: int = 5,
    source_filter: str | None = None,
    query_text: str | None = None,
    rerank: bool = True,
) -> list[SearchHit]:
    """Embed `query` and return up to `top_k` ranked hits.

    `query_text` feeds the BM25 half of hybrid search (None = semantic-only). With `rerank`
    a wider pool is retrieved and reordered by the cross-encoder, and each hit's `score`
    becomes the cross-encoder relevance.
    """
    query_vector = models.embed_one(query)

    if not rerank:
        return search(
            db_path,
            query_vector,
            top_k=top_k,
            file_path_prefix=source_filter,
            query_text=query_text,
        )

    hits = search(
        db_path,
        query_vector,
        top_k=max(top_k, models.RERANK_POOL),
        file_path_prefix=source_filter,
        query_text=query_text,
    )
    relevance = models.rerank(query, [h.content for h in hits])
    if len(relevance) != len(hits):
        raise ValueError(f"reranker returned {len(relevance)} scores for {len(hits)} candidates")
    for hit, score in zip(hits, relevance):
        hit.score = score
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def strip_blurb(content: str, context_chars: int | None = None) -> str:
    """Drop the machine-written context line from stored content.

    Stored content is "<context line>\n\n<breadcrumb>\n\n<body>". Newer indexes record the
    prefix length (`context_chars`, 0 = no context line); for older ones every chunk has a
    whitespace-collapsed one-line context, so the first "\n\n" always ends it.
    """
    if context_chars is not None:
        return content[context_chars:]
    _, sep, rest = content.partition("\n\n")
    return rest if sep else content


ID_PATTERN = re.compile(
    r"^(?:(?P<release>[a-z]+):)?(?P<file>markdown/[^\n]*?\.md)::(?P<rest>.*?)(?:::(?P<n>\d+))?$",
    re.ASCII | re.DOTALL,
)


def make_id(release: str, file_path: str, heading_path: str, occurrence: int = 1) -> str:
    """`release:file::heading`, plus `::N` for the Nth section when a page repeats a heading."""
    base = f"{release}:{file_path}{ID_SEPARATOR}{heading_path}"
    return f"{base}{ID_SEPARATOR}{occurrence}" if occurrence > 1 else base


def parse_id(doc_id: str) -> tuple[str | None, str, str, int] | None:
    """(release or None, file_path, heading_path, occurrence); None if it is not an id."""
    m = ID_PATTERN.match(doc_id.strip())
    if not m:
        return None
    occurrence = max(1, int(m.group("n"))) if m.group("n") else 1
    return m.group("release"), m.group("file"), m.group("rest").strip(), occurrence


_WS = re.compile(r"\s+")


_HEADER_FIELD = re.compile(r"([A-Za-z_]+):\s*(.*)")


def _readable_header(text: str) -> str:
    """A page's metadata header as "title: description", then the text after it. Works on
    a header the chunk boundary cut off too (long headers span two passages)."""
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    fields = {}
    for line in lines[1:end]:
        m = _HEADER_FIELD.fullmatch(line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"')
    title, description = fields.get("title", ""), fields.get("description", "")
    head = f"{title}: {description}" if title and description else title or description
    rest = "\n".join(lines[end + 1 :])
    return f"{head}\n{rest}" if head else (rest or text)


def snippet(content: str, context_chars: int | None = None, max_chars: int = 600) -> str:
    """Readable preview: context line removed, whitespace collapsed, cut on a word boundary.
    A page's opening passage starts with its metadata header: shown as "title: description"
    followed by the text, instead of the raw header."""
    text = strip_blurb(content, context_chars).lstrip()
    if text.startswith("---"):
        text = _readable_header(text)
    text = _WS.sub(" ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    space = cut.rfind(" ")
    if space > max_chars * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:") + " …"
