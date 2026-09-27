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
import re
import sys
import threading
from collections.abc import AsyncIterator
from dataclasses import asdict

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from snow_docs_mcp import config, identifiers, models, products, sections, setup, store
from snow_docs_mcp.read import ReadResult as _ReadResult
from snow_docs_mcp.read import not_an_id, page_url, read_section
from snow_docs_mcp.search import make_id, parse_id, run_search, snippet, strip_blurb

logger = logging.getLogger(__name__)

__version__ = config.VERSION

ANSWER_RULES = """\
You have tools for the official ServiceNow product documentation, for the australia and brazil
releases (snow_docs_search's `release` argument; australia unless the user's instance runs brazil).
When answering a ServiceNow question with them:
1. Call snow_docs_search first, with the query in English using ServiceNow's own terms: the docs
   are English-only, so translate a question asked in another language (and still answer in
   the user's language). Rephrase and search again if results look off-topic or weak.
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
    url: str = Field(
        "", description="The page on docs.servicenow.com when the docs name it, else its source."
    )
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


# A best reranker score below this means nothing really matched. Measured on the Australia
# index: Norwegian questions top out between -9.4 and -4.9; even vague one-word English
# queries ("index", "update") reach -0.0 or more.
WEAK_SCORE = -2.0


# Code-like names in a query: camelCase (setMandatory), snake_case (sys_id) or dotted
# (g_form.setMandatory, $sp.getParameter). A misspelt one ("setMandatroy") still scores
# above WEAK_SCORE because the rest of the query ("client script") matches, so the score
# alone can't catch it. Checked instead: does the name occur in any candidate passage?
_NAME_RE = re.compile(r"[$A-Za-z_][\w$]*(?:\.[$A-Za-z_][\w$]*)*")
_CAMEL_RE = re.compile(r"[a-z][A-Z]")


def _code_names(query: str) -> list[str]:
    """The code-like parts of a query, e.g. 'g_form.setMandatory' -> ['g_form', 'setMandatory'].
    Names starting u_ or x_ are the customer's own (ServiceNow's convention): never in the docs."""
    names: list[str] = []
    for token in _NAME_RE.findall(query):
        for part in token.split("."):
            bare = part.lstrip("$")
            code_like = _CAMEL_RE.search(bare) or "_" in bare.strip("_")
            custom = bare.lower().startswith(("u_", "x_"))
            if len(bare) >= 5 and code_like and not custom and part not in names:
                names.append(part)
    return names


def _missing_names(query: str, candidates: list) -> list[str]:
    """Code-like names from the query that occur, as written, in none of the candidates."""
    names = _code_names(query)
    if not names:
        return []
    text = sections.unescape_markdown(" ".join(c.content for c in candidates))
    return [n for n in names if not sections.name_pattern(n).search(text)]


_CODE_WORD_RE = re.compile(r"[$A-Za-z_][\w$]*")


def _one_edit(a: str, b: str) -> bool:
    """a and b differ by one insertion, deletion, substitution or swap of neighbours."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (
            len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]]
            and a[diff[1]] == b[diff[0]]
        )
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def _closest(name: str, words) -> str:
    """The word `name` most likely misspells: difflib ratio >= 0.85, or one edit away
    ('g_from' -> 'g_form'). '' when nothing is that close."""
    for word in difflib.get_close_matches(name, words, n=5, cutoff=0.75):
        if word != name and (
            difflib.SequenceMatcher(None, name, word).ratio() >= 0.85 or _one_edit(name, word)
        ):
            return word
    return ""


def _did_you_mean(names: list[str], candidates: list, more=lambda: ()) -> dict[str, str]:
    """For each misspelt code name, the closest code-like word ('setMandatroy' ->
    'setMandatory'): first from the candidate passages, then from `more()` (e.g. every code
    name in the index's section headings)."""
    words = {
        w
        for c in candidates
        for w in _CODE_WORD_RE.findall(sections.unescape_markdown(c.content))
        if len(w) >= 5 and (_CAMEL_RE.search(w) or "_" in w.strip("_"))
    }
    out = {}
    for name in names:
        close = _closest(name, words) or _closest(name, more())
        if close:
            out[name] = close
    return out


MAX_NAMED = 3  # a pasted script names every local variable: list at most this many


def _names_message(rel: str, db, query: str, candidates: list, gap_note: bool) -> str:
    """A note on code names in the query that none of the candidate passages contain: either
    they appear nowhere in the release (a typo, or a custom name), or elsewhere in it."""
    missing = _missing_names(query, candidates)
    if not missing:
        return ""
    known = {n: store.mentions(db, n) for n in missing}
    nowhere = [n for n in missing if not known[n]][:MAX_NAMED]
    elsewhere = [n for n in missing if known[n]][:MAX_NAMED]
    msg = ""
    if nowhere:
        close = _did_you_mean(nowhere, candidates, lambda: store.heading_code_names(db))
        named = ", ".join(
            f"'{n}'" + (f" (did you mean '{close[n]}'?)" if n in close else "") for n in nowhere
        )
        verb = "appears" if len(nowhere) == 1 else "appear"
        why = "a typo, or a custom name?"
        if gap_note:
            why = "a typo, a custom name, or part of an area these docs lack (see the note)?"
        msg += (
            f" {named} {verb} nowhere in the {rel} docs: {why} These passages may be about "
            "something else."
        )
    if elsewhere:
        named = ", ".join(f"'{n}'" for n in elsewhere)
        verb = "is" if len(elsewhere) == 1 else "are"
        msg += (
            f" {named} {verb} in the {rel} docs but not in these passages; if the question is "
            "about it, search for it by name."
        )
    return msg


def _product_problem(product: str, folder: str, rel: str, db, known: list[str]) -> str:
    """Why a `product` value can't be searched in this release, and what to do instead."""
    gaps, other = setup.coverage_gaps(rel)
    gap = next((g for g in gaps if g.product == (folder or products.normalize(product))), None)
    if gap and other:
        have = "no" if gap.pages == 0 else f"only {gap.pages:,}"
        return (
            f"The {rel} docs snapshot has {have} {gap.title} pages ({gap.of:,} in {other}). "
            f"Search with release '{other}' for these."
        )
    if folder:  # an abbreviation for a folder this release doesn't have
        return (
            f"'{product}' means the {folder} docs, which the {rel} docs don't include. Omit "
            "`product` to search everything, or pick one of: " + ", ".join(known) + "."
        )
    close = products.suggestions(product, known, store.page_paths(db)[0])
    hint = f"Did you mean: {', '.join(close)}? " if close else ""
    return (
        f"Unknown product '{product}' in the {rel} docs. {hint}Valid products: "
        + ", ".join(known)
        + ". Abbreviations such as itsm, csm, hrsd or cmdb work too. Or omit `product` to "
        "search everything."
    )


def _gaps_note(rel: str, folder: str | None = None) -> str:
    """Which docs areas this release's snapshot lacks (only `folder`'s, for a filtered
    search), if latest.json lists any."""
    gaps, other = setup.coverage_gaps(rel)
    if folder is not None:
        gaps = tuple(g for g in gaps if g.product == folder)
    if not gaps or not other:
        return ""
    parts = [
        g.title if g.pages == 0 else f"most of {g.title} ({g.pages:,} of {g.of:,} pages)"
        for g in gaps
    ]
    lacks = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"this {rel} docs snapshot lacks {lacks}; for those, search release '{other}'"


_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_WORD_RE = re.compile(r"\w+")
SAME_TEXT = 0.8  # word overlap (Jaccard) above which two passages count as one


def _words(content: str, context_chars: int | None) -> frozenset[str]:
    """A passage's words, ignoring its context line, front matter and link targets: what
    differs between two published copies of one page."""
    text = strip_blurb(content, context_chars).lstrip()
    text = _LINK_RE.sub(r"\1", sections.strip_front_matter(text))
    return frozenset(_WORD_RE.findall(text.lower()))


def _distinct_hits(db, rel: str, hits: list, limit: int) -> list[Hit]:
    """The best `limit` hits, one per section. Parts of one long section share an id, and
    ServiceNow publishes some pages under two product folders (same file name and headings,
    nearly the same text: the header's breadcrumb and link targets differ)."""
    pages: dict[str, str] = {}
    seen_ids: set[str] = set()
    kept_words: dict[tuple[str, str], list[frozenset[str]]] = {}
    out: list[Hit] = []
    for h in hits:
        if len(out) >= limit:
            break
        if h.file_path not in pages:
            pages[h.file_path] = store.get_document(db, h.file_path) or ""
        page = pages[h.file_path]
        hit_id = make_id(
            rel,
            h.file_path,
            h.heading_path,
            sections.occurrence_of(page, h.heading_path, h.byte_offset),
        )
        if hit_id in seen_ids:
            continue
        same_place = (h.file_path.rsplit("/", 1)[-1], h.heading_path)
        words = _words(h.content, h.context_chars)
        if any(
            len(words & w) >= SAME_TEXT * max(1, len(words | w))
            for w in kept_words.get(same_place, [])
        ):
            continue
        seen_ids.add(hit_id)
        kept_words.setdefault(same_place, []).append(words)
        out.append(
            Hit(
                id=hit_id,
                release=rel,
                page_title=sections.front_matter_value(page, "title"),
                url=page_url(db, rel, h.file_path, page),
                heading_path=h.heading_path,
                product=store.product_of(h.file_path),
                snippet=snippet(h.content, h.context_chars),
                score=round(float(h.score), 4),
            )
        )
    return out


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
    feature does. Returns the most relevant documentation passages, best first (a section
    whose own heading names a method or other code name from the query comes first even when
    its score is a little lower). Each hit's `id` can be passed to snow_docs_read for the full
    section, and should be cited as [id].

    Args:
        query: A question or keywords in English, using ServiceNow's terms, e.g. "how are
            incident priorities calculated". The docs are English-only: translate a question
            asked in another language first (e.g. "katalogvariabel" -> "catalog variable").
        limit: Number of passages to return, 1-20 (default 5).
        product: Optional top-level docs area to search within, e.g.
            "it-service-management", "servicenow-platform", "platform-security"; common
            abbreviations work too ("itsm", "csm", "hrsd", "cmdb", "ui builder"). An unknown
            value returns suggestions and the list of valid ones.
        release: ServiceNow release: "australia" or "brazil". Defaults to the configured
            release (australia unless SNOW_DOCS_RELEASE says otherwise). The result says
            when that release's docs lack an area (e.g. brazil's have no API reference yet).
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

        prefix = folder = None
        if product and product.strip():
            known = store.products(db)
            folder, how = products.resolve(product, known)
            if how not in ("exact", "alias"):
                return SearchResult(
                    ok=False, release=rel, message=_product_problem(product, folder, rel, db, known)
                )
            if how == "alias":
                notes.append(f"searched the {folder} docs for '{product.strip()}'")
            prefix = f"markdown/{folder}/"

        # Another Claude app may switch to a newer snapshot (and delete this one) mid-search:
        # re-resolve the index once and retry before giving up.
        for attempt in range(2):
            try:
                # The reranker always scores the whole pool, so taking all of it costs nothing
                # extra and leaves room to drop duplicates and still return `lim` passages.
                hits = run_search(
                    db, q, top_k=max(lim + 5, models.RERANK_POOL), source_filter=prefix, query_text=q
                )
                hits = identifiers.prefer_exact(q, hits)
                out = _distinct_hits(db, rel, hits, lim)
                gaps = _gaps_note(rel, folder)
                names_note = _names_message(rel, db, q, hits, bool(gaps)) if out else ""
                break
            except FileNotFoundError:
                newer = setup.active_index(rel)
                if attempt == 1 or newer is None or newer == db:
                    setup.request(rel)
                    return SearchResult(ok=False, release=rel, message=_not_ready(rel))
                db = newer
                _release_unused_indexes()

        if out:
            msg = (
                f"{len(out)} passages from the {rel} docs. Answer only from these, cite as "
                "[id], and call snow_docs_read(id) for the full section before quoting steps."
            )
        else:
            msg = "No passages matched. Try other wording, or drop the product filter."
        if out and max(h.score for h in out) < WEAK_SCORE:
            msg += (
                " These matches look weak. The docs are in English: if the question isn't, "
                "search again with English ServiceNow terms; otherwise try other wording."
            )
        msg += names_note
        if gaps:
            notes.append(gaps)
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
    models_state = "ready" if setup.models_on_disk() else (setup.models_status().message or "missing")
    notes = [setup.update_note()]
    legacy = setup.legacy_files()
    if legacy:
        notes.append(
            "the first version's docs index is still in the data folder ("
            + ", ".join(p.name for p in legacy)
            + "); this version doesn't need it. Delete it once that version is uninstalled "
            "(after the next docs update it would otherwise keep about 1.3 GB in use)"
        )
    return StatusResult(
        ok=setup.search_ready(default),
        default_release=default,
        releases=releases,
        models=models_state,
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
