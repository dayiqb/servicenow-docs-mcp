"""ServiceNow documentation MCP server — stdio entry point.

Tools (all read-only):
    snow_docs_search   hybrid (semantic + keyword) search with reranking over the ServiceNow
                       product docs, per release (australia, brazil)
    snow_docs_read     the full section behind a search hit
    snow_docs_status   setup/update progress per release, and where data lives

Prompt:
    answer             answer a question from the docs, with citations

Answers are written by the Claude that calls these tools; the server only retrieves. The
rules it should follow are sent as server instructions (ANSWER_RULES).

Console script `snow-docs-mcp`:
    snow-docs-mcp                       serve MCP over stdio (what Claude apps launch)
    snow-docs-mcp setup [RELEASE|all]   download docs index(es) and models now, with progress

stdout (fd 1) is the protocol wire: nothing but JSON-RPC frames may reach it; all logging
goes to stderr. Background setup starts from the server's lifespan, i.e. inside the SDK's
serving window, where stray fd-1 writes are already diverted to stderr.

Configuration (env vars): see snow_docs_mcp.config (SNOW_DOCS_HOME, SNOW_DOCS_RELEASE, ...),
plus
    SNOW_DOCS_LOG_LEVEL               Root log level, default "INFO" (stderr only).
    SNOW_DOCS_TEST_STDOUT_NOISE       Test-only. "1" makes the server write stray text to
                                      stdout before serving and during a tool call.
    SNOW_DOCS_TEST_DISABLE_STDOUT_GUARD
                                      Test-only. "1" disables the startup stdout guard (the
                                      mutation control for the stdio test). Never in production.
"""

from __future__ import annotations

import contextlib
import difflib
import logging
import os
import sys
import threading
from collections.abc import AsyncIterator
from dataclasses import asdict

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from snow_docs_mcp import config, sections, setup, store
from snow_docs_mcp.read import ReadResult as _ReadResult
from snow_docs_mcp.read import not_an_id, read_section
from snow_docs_mcp.search import make_id, parse_id, run_search, snippet

logger = logging.getLogger(__name__)

__version__ = config.VERSION

ANSWER_RULES = """\
You have tools for the official ServiceNow product documentation, for the australia and brazil
releases (snow_docs_search's `release` argument; australia unless the user's instance runs brazil).
When answering a ServiceNow question with them:
1. Call snow_docs_search first (rephrase and search again if results look off-topic).
2. Answer ONLY from the passages the tools returned; do not fill gaps from memory.
3. Cite every factual claim with the passage id in square brackets, e.g. [australia:markdown/...md::Heading]; when a result has a url, you may also link it.
4. Before giving step-by-step instructions, call snow_docs_read on the id to get the full section.
5. If the docs do not cover the question, or only cover a different release or product, say so plainly.
6. If two sources disagree, point out the conflict and cite both."""

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)


@contextlib.asynccontextmanager
async def _lifespan(_server: MCPServer) -> AsyncIterator[dict]:
    # Inside the SDK's stdio serving window: safe to start work that may print.
    setup.start()
    yield {}


mcp = MCPServer(
    name="servicenow-docs",
    title="ServiceNow Docs",
    version=__version__,
    instructions=ANSWER_RULES,
    lifespan=_lifespan,
)


# --- result models ------------------------------------------------------------------------


class Hit(BaseModel):
    id: str = Field(description="Pass to snow_docs_read; cite it as [id].")
    release: str
    page_title: str
    url: str = Field("", description="The page on docs.servicenow.com, when known.")
    heading_path: str
    product: str
    snippet: str
    score: float = Field(description="Reranker relevance; higher is better.")


class SearchResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    hits: list[Hit] = []


class ReadResult(BaseModel):
    ok: bool
    message: str
    id: str = ""
    title: str = ""
    url: str = ""
    heading_path: str = ""
    content: str = ""
    truncated: bool = False


class ReleaseStatus(BaseModel):
    release: str
    state: str
    message: str
    progress: float
    snapshot: str = Field("", description="Docs snapshot in use (date of the docs commit).")
    chunks: int | None = None


class StatusResult(BaseModel):
    ok: bool = Field(description="True when the default release can be searched.")
    default_release: str
    releases: list[ReleaseStatus]
    models: str
    update_note: str = ""
    data_folder: str
    server_version: str = __version__


def _not_ready(release: str) -> str:
    st = setup.status(release)
    if setup.index_ready(release) and not setup.models_on_disk():
        models = setup.models_status()
        if models.state == "error":
            return f"{models.message}. It retries the next time it's used. Help: {config.README_URL}"
        return (
            "The ServiceNow docs server is downloading its search models (first run only). "
            "Try again in a minute or two; snow_docs_status shows progress."
        )
    if st.state in ("error", "unavailable"):
        return st.message
    if st.state in ("idle", "ready"):  # nothing running: the index went missing
        return (
            f"The {release} docs index is missing; setting it up again. Try again in a minute "
            "or two; snow_docs_status shows progress."
        )
    return (
        f"The {release} docs are still being set up. {st.message} "
        "Try again in a minute or two; snow_docs_status shows progress."
    )


def _snapshot_of(release: str) -> str:
    act = setup.active_installed(release)
    return act.snapshot if act else ""


def _release_unused_indexes() -> None:
    """Free the memory of indexes searches no longer use (after a snapshot switch)."""
    store.retain({p for r in config.RELEASES if (p := setup.active_index(r)) is not None})


def _unknown_release(value: str) -> str:
    return f"Unknown release '{value}'. Available: {', '.join(config.RELEASES)}."


# --- tools --------------------------------------------------------------------------------


@mcp.tool(name="snow_docs_search", annotations=READ_ONLY)
def snow_docs_search(
    query: str, limit: int = 5, product: str | None = None, release: str | None = None
) -> SearchResult:
    """Search the official ServiceNow product documentation.

    Use this for any question about how ServiceNow works, how to configure it, or what a
    feature does. Returns the most relevant documentation passages, best first. Each hit's
    `id` can be passed to snow_docs_read for the full section, and should be cited as [id].

    Args:
        query: A natural-language question or keywords, e.g. "how are incident priorities
            calculated".
        limit: Number of passages to return, 1-20 (default 5).
        product: Optional top-level docs area to search within, e.g.
            "it-service-management", "now-platform", "platform-security". An unknown value
            returns the list of valid ones.
        release: ServiceNow release: "australia" or "brazil". Defaults to the configured
            release (australia unless SNOW_DOCS_RELEASE says otherwise).
    """
    try:
        q = (query or "").strip()
        if not q:
            return SearchResult(
                ok=False, message="The query is empty. Pass a question or keywords."
            )
        rel = config.normalize_release(release)
        if rel is None:
            return SearchResult(ok=False, message=_unknown_release(str(release)))
        if not setup.search_ready(rel):
            setup.request(rel)
            return SearchResult(ok=False, release=rel, message=_not_ready(rel))
        db = setup.active_index(rel)
        if db is None:  # vanished between the check and here
            setup.request(rel)
            return SearchResult(ok=False, release=rel, message=_not_ready(rel))
        _release_unused_indexes()

        notes = []
        lim = max(1, min(int(limit), 20))
        if lim != limit:
            notes.append(f"limit adjusted to {lim} (allowed: 1-20)")

        prefix = None
        if product and product.strip():
            wanted = product.strip().strip("/").lower()
            known = store.products(db)
            if wanted not in known:
                close = difflib.get_close_matches(wanted, known, n=3, cutoff=0.5)
                hint = f"Did you mean: {', '.join(close)}? " if close else ""
                return SearchResult(
                    ok=False,
                    release=rel,
                    message=f"Unknown product '{product}' in the {rel} docs. {hint}Valid "
                    "products: " + ", ".join(known) + ". Or omit `product` to search everything.",
                )
            prefix = f"markdown/{wanted}/"

        # Another Claude app may switch to a newer snapshot (and delete this one) mid-search:
        # re-resolve the index once and retry before giving up.
        for attempt in range(2):
            try:
                hits = run_search(db, q, top_k=lim, source_filter=prefix, query_text=q)
                pages: dict[str, str] = {}
                for h in hits:
                    if h.file_path not in pages:
                        pages[h.file_path] = store.get_document(db, h.file_path) or ""
                break
            except FileNotFoundError:
                newer = setup.active_index(rel)
                if attempt == 1 or newer is None or newer == db:
                    setup.request(rel)
                    return SearchResult(ok=False, release=rel, message=_not_ready(rel))
                db = newer
                _release_unused_indexes()

        def page(file_path: str) -> str:
            return pages.get(file_path, "")

        out = [
            Hit(
                id=make_id(
                    rel,
                    h.file_path,
                    h.heading_path,
                    sections.occurrence_of(page(h.file_path), h.heading_path, h.byte_offset),
                ),
                release=rel,
                page_title=sections.front_matter_value(page(h.file_path), "title"),
                url=sections.front_matter_value(page(h.file_path), "canonical_url"),
                heading_path=h.heading_path,
                product=store.product_of(h.file_path),
                snippet=snippet(h.content, h.context_chars),
                score=round(float(h.score), 4),
            )
            for h in hits
        ]
        if out:
            msg = (
                f"{len(out)} passages from the {rel} docs. Answer only from these, cite as "
                "[id], and call snow_docs_read(id) for the full section before quoting steps."
            )
        else:
            msg = "No passages matched. Try other wording, or drop the product filter."
        if notes:
            msg += " Note: " + "; ".join(notes) + "."
        return SearchResult(ok=True, message=msg, release=rel, snapshot=_snapshot_of(rel), hits=out)
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_search failed")
        if not setup.models_on_disk():
            setup.request(config.default_release())
        return SearchResult(ok=False, message=f"Search failed: {e}")


@mcp.tool(name="snow_docs_read", annotations=READ_ONLY)
def snow_docs_read(id: str, max_chars: int = 20000) -> ReadResult:
    """Read the full documentation section behind a snow_docs_search hit.

    Use this before quoting procedures, field lists or step-by-step instructions, since
    search snippets are cut short. Pass an id exactly as snow_docs_search returned it;
    an id ending in "::" returns the whole page.

    Args:
        id: A hit id, e.g. "australia:markdown/.../page.md::Page title > Section".
        max_chars: Maximum characters to return (500-100000, default 20000).
    """
    try:
        parsed = parse_id(id)
        if parsed is None:
            return ReadResult(**asdict(not_an_id(id)))
        rel_raw, file_path, heading_path, occurrence = parsed
        rel = config.normalize_release(rel_raw)
        if rel is None:
            return ReadResult(ok=False, message=_unknown_release(str(rel_raw)))
        db = setup.active_index(rel)
        if db is None:
            setup.request(rel)
            return ReadResult(ok=False, message=_not_ready(rel))
        result: _ReadResult = read_section(db, rel, file_path, heading_path, occurrence, max_chars)
        return ReadResult(**asdict(result))
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_read failed")
        return ReadResult(ok=False, message=f"Read failed: {e}")


@mcp.tool(name="snow_docs_status", annotations=READ_ONLY)
def snow_docs_status() -> StatusResult:
    """Show whether the ServiceNow docs server is ready, setup or update progress per
    release, which docs snapshot is in use, and where its data lives. Call it when search
    reports that setup is still running or failed."""
    if os.environ.get("SNOW_DOCS_TEST_STDOUT_NOISE") == "1":
        # Noise DURING serving: the SDK diverts fd 1 to stderr for the serving window.
        sys.stdout.write("stray-print-during-call\n")
        sys.stdout.write("\rdownloading model 45%")
        sys.stdout.flush()
    default = config.default_release()
    releases = []
    for rel in config.RELEASES:
        st = setup.status(rel)
        if rel == default and not setup.search_ready(rel):
            setup.request(rel)  # recover a missing index/models; no-op while one is running
            st = setup.status(rel)
        act = setup.active_installed(rel)
        chunks = None
        if act:
            with contextlib.suppress(Exception):
                chunks = int(store.meta(act.db_path).get("chunk_count", "0")) or None
        state, message = st.state, st.message
        if act and state in ("idle", "ready", "queued", "waiting"):
            state, message = "ready", "Ready."
        elif not act and state == "idle":
            state, message = "not_installed", "Downloads the first time this release is searched."
        releases.append(
            ReleaseStatus(
                release=rel,
                state=state,
                message=message,
                progress=round(st.progress, 3),
                snapshot=act.snapshot if act else "",
                chunks=chunks,
            )
        )
    models = "ready" if setup.models_on_disk() else (setup.models_status().message or "missing")
    notes = [setup.update_note()]
    legacy = setup.legacy_files()
    if legacy:
        notes.append(
            "the first version's docs index is still in the data folder ("
            + ", ".join(p.name for p in legacy)
            + "); delete it once that version is uninstalled, to free about 1.3 GB"
        )
    return StatusResult(
        ok=setup.search_ready(default),
        default_release=default,
        releases=releases,
        models=models,
        update_note="; ".join(n for n in notes if n),
        data_folder=str(config.data_home()),
    )


@mcp.prompt(name="answer", title="Answer from the ServiceNow docs")
def answer(question: str) -> str:
    """Answer a ServiceNow question from the official docs, with citations."""
    return f"{ANSWER_RULES}\n\nQuestion: {question}"


# --- process entry points -----------------------------------------------------------------


def _configure_logging() -> None:
    """Send all logging to stderr; stdout belongs to the MCP wire."""
    # force=True is REQUIRED: MCPServer() installs a root StreamHandler at construction
    # (import time here), and basicConfig is a no-op once the root logger has handlers.
    level = logging.getLevelName((os.environ.get("SNOW_DOCS_LOG_LEVEL") or "INFO").strip().upper())
    logging.basicConfig(
        level=level if isinstance(level, int) else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _noisy_startup_probe() -> None:
    """Emit the three stdout-noise shapes that corrupt stdio framing. Test-only."""
    print("stray-print-before-serve")
    sys.stdout.write("\rFetching model 10%")
    sys.stdout.flush()
    os.write(1, b"c-level-write-to-fd1\n")


def _run_setup_cli(args: list[str]) -> int:
    """`snow-docs-mcp setup [RELEASE|all]`: download in the foreground, with progress."""
    target = (args[0].lower() if args else config.default_release()).strip()
    releases = list(config.RELEASES) if target == "all" else [target]
    if any(r not in config.RELEASES for r in releases):
        print(
            f"unknown release {target!r}; use one of: {', '.join(config.RELEASES)}, all",
            file=sys.stderr,
        )
        return 2
    logging.getLogger("snow_docs_mcp.setup").setLevel(logging.WARNING)
    print(f"ServiceNow docs MCP {__version__}: setting up in {config.data_home()}", file=sys.stderr)
    worst = 0
    for rel in releases:
        done = threading.Event()
        result: dict = {}

        def run(rel: str = rel, result: dict = result, done: threading.Event = done) -> None:
            result["s"] = setup.ensure(rel)
            done.set()

        threading.Thread(target=run, daemon=True).start()
        last = ""
        while not done.wait(0.5):
            st = setup.status(rel)
            line = f"[{rel}] {st.state}: {st.message}"
            if line != last:
                print(line, file=sys.stderr)
                last = line
        st = result["s"]
        print(f"[{rel}] {st.state}: {st.message}", file=sys.stderr)
        if st.state != "ready":
            worst = 1
    return worst


def _use_system_certificates() -> None:
    """Trust the OS certificate store for all HTTPS (index, latest.json, model downloads),
    so corporate proxies that re-sign TLS with their own root certificate work."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception as e:  # noqa: BLE001 - fall back to the bundled certificates
        logger.warning("could not use the system certificate store (%s)", e)


def main(argv: list[str] | None = None) -> None:
    """Entry point: `snow-docs-mcp` serves MCP over stdio; `snow-docs-mcp setup` downloads."""
    args = sys.argv[1:] if argv is None else argv
    _configure_logging()
    _use_system_certificates()

    if args[:1] == ["setup"]:
        sys.exit(_run_setup_cli(args[1:]))
    if args[:1] in (["-h"], ["--help"]):
        print(__doc__, file=sys.stderr)
        return
    if args:
        print(f"unknown arguments {args!r}; run `snow-docs-mcp --help`", file=sys.stderr)
        sys.exit(2)

    noise = os.environ.get("SNOW_DOCS_TEST_STDOUT_NOISE") == "1"
    guard_disabled = os.environ.get("SNOW_DOCS_TEST_DISABLE_STDOUT_GUARD") == "1"

    if guard_disabled:
        # Mutation control for the stdio test only: with the guard off the wire MUST corrupt.
        if noise:
            _noisy_startup_probe()
    else:
        # fd-level guard over the startup window: point fd 1 at stderr while initialising,
        # then restore the real wire before mcp.run() (the SDK claims fd 1 inside it).
        # Catches Python prints, carriage-return bars and raw os.write(1, ...).
        wire_fd = os.dup(1)
        os.dup2(2, 1)
        try:
            if noise:
                _noisy_startup_probe()
        finally:
            sys.stdout.flush()
            os.dup2(wire_fd, 1)
            os.close(wire_fd)

    logger.info("snow-docs-mcp %s serving over stdio (data: %s)", __version__, config.data_home())
    mcp.run()


if __name__ == "__main__":
    main()
