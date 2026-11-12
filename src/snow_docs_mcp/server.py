"""ServiceNow documentation MCP server — stdio entry point.

Tools (all read-only):
    snow_docs_search   hybrid (semantic + keyword) search with reranking over the ServiceNow
                       product docs, per release (australia, brazil)
    snow_docs_read     the full section behind a search hit
    snow_docs_compare  what changed between the australia and brazil docs for a topic or page
    snow_docs_api      a class's methods, or a method's parameters and return type, exactly
    snow_docs_status   setup/update progress per release, and where data lives

Prompt:
    answer             answer a question from the docs, with citations
    upgrade_review     a cited checklist for upgrading one product from Australia to Brazil

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
import json
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

from snow_docs_mcp import api_table, config, identifiers, models, products, sections, setup, store
from snow_docs_mcp.compare import compare_pages
from snow_docs_mcp.read import ReadResult as _ReadResult
from snow_docs_mcp.read import not_an_id, page_url, read_section
from snow_docs_mcp.search import ID_SEPARATOR, make_id, parse_id, run_search, snippet, strip_blurb

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
6. If two sources disagree, point out the conflict and cite both.
7. For a question about what changes between Australia and Brazil (an upgrade, what's new),
   call snow_docs_compare first. Lead with its release notes, then the changed sections; cite
   ids as usual, and say that small rewordings are not listed.
8. Before writing or reviewing ServiceNow script code, check each class and method with
   snow_docs_api. If it answers not_found, do not use that method; say so, and offer the
   closest documented one."""

# The upgrade review recipe: the `upgrade_review` prompt, manifest.json and the
# servicenow-upgrade-review skill carry this text word for word (tests keep them in step).
UPGRADE_REVIEW_RULES = """\
Write an upgrade review: what to check for one ServiceNow product when upgrading from
Australia to Brazil. Use only the ServiceNow docs tools; do not fill gaps from memory.
1. Call snow_docs_compare with the product name as `query`. `release_notes` has one passage
   per page; each page is "Combined <application> release notes for upgrades from Australia to
   Brazil". Release notes are per application, so a product often has several pages (the
   application, its workspace, its AI skills): use every page that belongs to what the user
   asked about, and name the pages you used. `more_release_notes` lists further pages whose
   application name shares a word with the query (the docs may call the product something
   else): use those that belong, too. If none fits, try the product's other names once
   (abbreviation, old name). If there is still none, say that the release notes have no page for
   this product, and stop.
2. For each page, call snow_docs_read with the passage's id cut off after "::" (this returns
   the whole page). If the result is truncated, read it again with max_chars 100000.
3. Write the checklist in these parts, in this order, one line per item, each ending with its
   citation [id]:
   - Before and after the upgrade (the page's "Important information for upgrading")
   - New features to evaluate ("New features")
   - Changed behavior ("Changes")
   - Removed and deprecated ("Removed", "Deprecations")
   - Activation and requirements ("Activation information", "Additional requirements")
   Take items only from the Brazil rows of the page. Where the page says
   "No updates for this release", write that for the part instead of leaving it out.
4. Add a part "Changed in the documentation" with the `changed_pages` from step 1, if there are
   any, and say that small rewordings are not listed.
5. If a tool for the user's own ServiceNow instance is connected, ask before using it. With a
   yes, look up the instance's release and installed applications, and mark the items that
   apply to this instance.
6. End with what the review does not cover: customizations, integrations and other products.
Answer in the user's language; keep product, feature and field names as the docs write them."""

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


class SectionDiff(BaseModel):
    heading_path: str
    change: str = Field(description="added, removed or changed (australia -> brazil).")
    changed_words: int
    australia_id: str = Field("", description="Pass to snow_docs_read; empty when added.")
    brazil_id: str = Field("", description="Pass to snow_docs_read; empty when removed.")
    australia_excerpt: str = ""
    brazil_excerpt: str = ""


class ChangedPage(BaseModel):
    page: str = Field(description="The page's path; pass it as `page` to compare it alone.")
    page_title: str
    product: str
    australia_url: str = ""
    brazil_url: str = ""
    sections: list[SectionDiff] = []
    minor_changes: int = Field(0, description="Small rewordings, counted but not listed.")
    sections_left_out: int = Field(0, description="Dropped to keep the result short.")


class NotesPage(BaseModel):
    id: str = Field(description="Pass to snow_docs_read for the whole release-notes page.")
    application: str


class CompareResult(BaseModel):
    ok: bool
    message: str
    australia_snapshot: str = ""
    brazil_snapshot: str = ""
    release_notes: list[Hit] = Field(
        [], description="ServiceNow's own release notes for upgrades from Australia to Brazil."
    )
    more_release_notes: list[NotesPage] = Field(
        [],
        description="Other release-notes pages whose application name shares a word with the query.",
    )
    changed_pages: list[ChangedPage] = []
    only_in_australia: list[str] = []
    only_in_brazil: list[str] = []


class ApiParam(BaseModel):
    name: str
    type: str
    description: str


class ApiClass(BaseModel):
    class_name: str = Field(description='As the docs write it, e.g. "Scoped GlideRecord".')
    members: list[str] = Field(description="Signatures of its methods; properties by name.")
    page_ids: list[str] = Field(description="The class's page(s); pass to snow_docs_read.")


class ApiMethod(BaseModel):
    class_name: str
    name: str
    kind: str
    signature: str
    parameters: list[ApiParam] = []
    returns: str = ""
    returns_description: str = ""
    description: str = ""
    example: str = ""
    id: str = Field(description="Pass to snow_docs_read for the full section; cite it as [id].")
    url: str = ""


class ApiResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    kind: str = Field("", description="class, method or not_found")
    classes: list[ApiClass] = []
    methods: list[ApiMethod] = []
    suggestions: list[str] = []


def _not_ready(release: str) -> str:
    st = setup.status(release)
    if setup.index_ready(release) and not setup.models_on_disk():
        models = setup.models_status()
        if models.state == "error":
            return (
                f"{models.message}. It retries the next time it's used. Help: {config.README_URL}"
            )
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
            len(diff) == 2
            and diff[1] == diff[0] + 1
            and a[diff[0]] == b[diff[1]]
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
                    db,
                    q,
                    top_k=max(lim + 5, models.RERANK_POOL),
                    source_filter=prefix,
                    query_text=q,
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


# --- compare ------------------------------------------------------------------------------

FROM_RELEASE, TO_RELEASE = "australia", "brazil"
# ServiceNow's combined release notes for upgrades from Australia to Brazil (Brazil docs only).
RELEASE_NOTES_PREFIX = "markdown/delta-australia-brazil/"
RELEASE_NOTES_HITS = 5  # pages: release notes are per application, a product often has several
COMPARE_CANDIDATE_PAGES = 15  # pages a query compares: the top search hits of both releases
COMPARE_MAX_CHARS = 12000  # the whole result, as JSON
_SHORT_EXCERPT = 150


_DOCS_URL = re.compile(r"^https?://[^/]+/docs/(?:r/)?", re.IGNORECASE)


def _page_path(value: str) -> str:
    """A `page` argument as a file path: a hit id, a docs page address, or a path with or
    without the release, 'markdown/' and '.md' ('' when nothing is left)."""
    v = value.strip().replace("\\", "/")
    url = _DOCS_URL.match(v)
    if url:
        v = v[url.end() :].split("#", 1)[0].split("?", 1)[0]
        v = re.sub(r"\.html?$", "", v, flags=re.IGNORECASE)
        for rel in config.RELEASES:
            v = v.removeprefix(f"{rel}/")
    else:
        v = v.split("::", 1)[0]
        for rel in config.RELEASES:
            if v.lower().startswith(f"{rel}:"):
                v = v[len(rel) + 1 :]
    v = re.sub(r"\.md$", "", v.strip("/"), flags=re.IGNORECASE)
    if not v:
        return ""
    return (v if v.startswith("markdown/") else "markdown/" + v) + ".md"


def _same_name_page(path: str, dbs: dict) -> str | None:
    """The one page with this file name, when the path itself is unknown (a docs address
    names the product folder, not the subfolder the page is in)."""
    name = path.rsplit("/", 1)[-1]
    found = {p for db in dbs.values() for p in store.page_paths(db)[1].get(name, [])}
    return found.pop() if len(found) == 1 else None


def _close_pages(path: str, dbs: dict) -> list[str]:
    by_name: dict[str, list[str]] = {}
    for db in dbs.values():
        for name, paths in store.page_paths(db)[1].items():
            by_name.setdefault(name, []).extend(p for p in paths if p not in by_name.get(name, []))
    names = difflib.get_close_matches(path.rsplit("/", 1)[-1], list(by_name), n=3, cutoff=0.6)
    return [p for name in names for p in by_name[name]][:3]


def _changed_page(path: str, dbs: dict) -> tuple[str, ChangedPage | None]:
    """('both' | 'australia' | 'brazil' | 'none': where the page exists, its comparison when
    it is in both)."""
    old = store.get_document(dbs[FROM_RELEASE], path)
    new = store.get_document(dbs[TO_RELEASE], path)
    if old is None or new is None:
        where = FROM_RELEASE if old is not None else TO_RELEASE if new is not None else "none"
        return where, None
    diff = compare_pages(old, new)
    listed = [
        SectionDiff(
            heading_path=c.heading_path,
            change=c.change,
            changed_words=c.changed_words,
            australia_id=""
            if c.change == "added"
            else make_id(FROM_RELEASE, path, c.heading_path, c.old_occurrence),
            brazil_id=""
            if c.change == "removed"
            else make_id(TO_RELEASE, path, c.heading_path, c.occurrence),
            australia_excerpt=c.before,
            brazil_excerpt=c.after,
        )
        for c in diff.sections
    ]
    return "both", ChangedPage(
        page=path,
        page_title=sections.front_matter_value(new, "title"),
        product=store.product_of(path),
        australia_url=page_url(dbs[FROM_RELEASE], FROM_RELEASE, path, old),
        brazil_url=page_url(dbs[TO_RELEASE], TO_RELEASE, path, new),
        sections=listed,
        minor_changes=diff.minor,
    )


def _candidate_pages(dbs: dict, q: str, prefix: str | None) -> list[str]:
    """The pages a query is about: the top hits of both releases, interleaved by rank. The
    order within them doesn't matter (pages are ranked by how much changed), so no reranking."""
    ranked = [
        [
            h.file_path
            for h in run_search(db, q, top_k=30, source_filter=prefix, query_text=q, rerank=False)
        ]
        for db in dbs.values()
    ]
    out: list[str] = []
    for i in range(max(map(len, ranked), default=0)):
        for paths in ranked:
            if (
                i < len(paths)
                and paths[i] not in out
                and not paths[i].startswith("markdown/delta-")
            ):
                out.append(paths[i])
    return out[:COMPARE_CANDIDATE_PAGES]


_FIT_CHARS = COMPARE_MAX_CHARS - 800  # room for the message, written after fitting


def _size(result: CompareResult) -> int:
    """Length as the client receives it (JSON with non-ASCII escaped: the longest form)."""
    return len(json.dumps(result.model_dump()))


MORE_RELEASE_NOTES = 15
_NOTES_TITLE = re.compile(r"^Combined (.+) release notes for upgrades from Australia to Brazil$")
_NOTES_FOLDER = "markdown/release-notes/"
_BREADCRUMB = re.compile(r"^breadcrumb: \[(.*)\]\s*$", re.MULTILINE)
_FAMILY = re.compile(r"(.+?) release notes(?:, |$)")
_PARENS = re.compile(r"\s*\(([^()]*)\)")
# Words too common in application names to identify one.
_GENERIC_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
        "now",
        "servicenow",
        "service",
        "services",
        "management",
        "release",
        "notes",
        "upgrade",
        "application",
        "applications",
    ]
)
_notes_cache: dict[str, tuple[dict, dict, dict]] = {}


def _phrase(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def _notes_index(
    db,
) -> tuple[dict[str, tuple[str, str]], dict[str, set[str]], dict[str, set[str]]]:
    """(application phrase -> (page path, application name), family phrase -> application
    phrases, application phrase -> the product areas its own docs are in) for the
    release-notes pages. An application's own docs are the pages titled with its name; their
    top folder is the product area. Families come from the breadcrumb of the
    per-application release notes: "<application> release notes" under "<family> release
    notes" (more than one level, e.g. Workflow Studio under App development and low-code)."""
    key = str(db)
    if key not in _notes_cache:
        apps: dict[str, tuple[str, str]] = {}
        chains: list[list[str]] = []
        for path in store.page_paths(db)[0]:
            if path.startswith(RELEASE_NOTES_PREFIX):
                page = store.get_document(db, path) or ""
                m = _NOTES_TITLE.match(sections.front_matter_value(page, "title"))
                if m:
                    name = sections.unescape_markdown(m.group(1))
                    apps[_phrase(_PARENS.sub("", name))] = (path, name)
            elif path.startswith(_NOTES_FOLDER):
                page = (store.get_document(db, path) or "")[:3000]
                crumbs = _BREADCRUMB.search(page)
                if crumbs:
                    # family crumbs come first; the generic ones start at "Features and changes"
                    head = crumbs.group(1).split("Features and changes", 1)[0]
                    title = sections.unescape_markdown(sections.front_matter_value(page, "title"))
                    chain = _FAMILY.findall(f"{title}, {head}")
                    chains.append([_phrase(_PARENS.sub("", c)) for c in chain])
        families: dict[str, set[str]] = {}
        for chain in chains:
            for i, name in enumerate(chain):
                if name in apps:
                    for family in chain[i + 1 :]:
                        families.setdefault(family, set()).add(name)
        areas: dict[str, set[str]] = {}
        for title, paths in store.page_titles(db, "markdown/delta-").items():
            name = _phrase(_PARENS.sub("", sections.unescape_markdown(title)))
            if name in apps:
                found = {store.product_of(p) for p in paths if not p.startswith(_NOTES_FOLDER)}
                areas.setdefault(name, set()).update(found - {""})
        _notes_cache[key] = (apps, families, areas)
    return _notes_cache[key]


def _notes_by_name(db, q: str, already: set[str]) -> list[NotesPage]:
    """Release-notes pages found by name rather than by search: search misses a page when
    the docs call the product something else ("Flow Designer" is under "Flows, subflows, and
    actions"), and one product often has several pages.

    - The query names a product family (HR Service Delivery, Workflow Studio, or an
      abbreviation such as ITSM): the family's applications.
    - The query names one application (or its abbreviation in brackets): only pages whose name
      has the whole query, so "Document Intelligence" does not bring in "Document Services".
    - Otherwise: pages that contain the rarest query word found in any name. A query word
      matches a name word it begins (hr -> HRSD, flow -> Flows).
    With a family, pages are also taken by word or by the family's initials (HRSD), since the
    breadcrumbs do not list every application, but never a page that belongs to another family
    or whose own docs are in another product area than the family's.
    """
    apps, families, areas = _notes_index(db)
    phrase = _phrase(q)
    if not phrase:
        return []
    folder, how = products.resolve(q, store.products(db))
    family_names = {phrase} | ({_phrase(folder)} if how in ("exact", "alias") and folder else set())
    members = {a for f in family_names for a in families.get(f, ())}

    def abbreviations(name: str) -> set[str]:
        return {_phrase(x) for x in _PARENS.findall(name)}

    names_one = phrase in apps or any(phrase in abbreviations(n) for _, n in apps.values())
    words = {w for w in phrase.split() if len(w) > 1 and w not in _GENERIC_WORDS}
    has = {
        a: {w for w in words if any(n.startswith(w) for n in _phrase(name).split())}
        for a, (_, name) in apps.items()
    }
    if names_one and not members:
        named = {
            a
            for a, (_, name) in apps.items()
            if f" {phrase} " in f" {a} " or phrase in abbreviations(name)
        }
    else:
        in_names = {w: sum(w in h for h in has.values()) for w in words}
        counts = [n for n in in_names.values() if n]
        rarest = {w for w, n in in_names.items() if counts and n == min(counts)}
        named = {a for a, h in has.items() if h & rarest}
    if members:
        initials = "".join(w[0] for w in phrase.split())
        named |= {a for a in apps if len(initials) > 2 and initials in a.split()}
        elsewhere = {a for f, group in families.items() if f not in family_names for a in group}
        home = {area for a in members for area in areas.get(a, ())}
        elsewhere |= {a for a in named if home and areas.get(a) and not areas[a] & home}
        named -= elsewhere - members
    found = sorted(
        (-len(has[a]), apps[a][1], apps[a][0])
        for a in members | named
        if f"{TO_RELEASE}:{apps[a][0]}" not in already
    )
    return [
        NotesPage(id=make_id(TO_RELEASE, path, ""), application=name)
        for _, name, path in found[:MORE_RELEASE_NOTES]
    ]


def _fit(result: CompareResult) -> tuple[bool, int]:
    """Shrink `result` to the size limit: shorter excerpts first, then fewer sections per
    page, then fewer pages (the least-changed last). Returns (sections were dropped, pages
    dropped)."""
    if _size(result) <= _FIT_CHARS:
        return False, 0
    for page in result.changed_pages:
        for sec in page.sections:
            for field in ("australia_excerpt", "brazil_excerpt"):
                text = getattr(sec, field)
                if len(text) > _SHORT_EXCERPT:
                    setattr(sec, field, text[:_SHORT_EXCERPT].rstrip() + "…")
    sections_dropped, pages_dropped = False, 0
    while _size(result) > _FIT_CHARS and result.changed_pages:
        page = max(result.changed_pages, key=lambda p: len(p.sections))
        if len(page.sections) > 1:
            page.sections.remove(min(reversed(page.sections), key=lambda s: s.changed_words))
            page.sections_left_out += 1
            sections_dropped = True
        else:
            result.changed_pages.pop()
            pages_dropped += 1
    return sections_dropped, pages_dropped


def _count(n: int, what: str) -> str:
    return f"{n} {what}" if n == 1 else f"{n} {what}s"


def _compare(q: str, page: str, product: str | None, limit: int, dbs: dict) -> CompareResult:
    notes: list[str] = []
    result = CompareResult(
        ok=True,
        message="",
        australia_snapshot=_snapshot_of(FROM_RELEASE),
        brazil_snapshot=_snapshot_of(TO_RELEASE),
    )
    if page:
        path = _page_path(page)
        where, changed = _changed_page(path, dbs) if path else ("none", None)
        if where == "none" and path and (same := _same_name_page(path, dbs)):
            path = same
            where, changed = _changed_page(path, dbs)
        if where == "none":
            close = _close_pages(path, dbs) if path else []
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            return CompareResult(
                ok=False,
                message=f"No page '{path or page}' in the australia or brazil docs.{hint} Pass "
                "a hit id or a page path from snow_docs_search.",
            )
        compared = 1
        pages = [changed] if changed else []
        if where != "both":
            getattr(result, f"only_in_{where}").append(path)
    else:
        lim = max(1, min(int(limit), 20))
        if lim != limit:
            notes.append(f"limit adjusted to {lim} (allowed: 1-20)")
        prefix = None
        if product and product.strip():
            for rel in (FROM_RELEASE, TO_RELEASE):  # a docs area may exist in one release only
                folder, how = products.resolve(product, store.products(dbs[rel]))
                if how in ("exact", "alias"):
                    break
            if how not in ("exact", "alias"):
                db = dbs[FROM_RELEASE]
                known = store.products(db)
                folder, how = products.resolve(product, known)
                problem = _product_problem(product, folder, FROM_RELEASE, db, known)
                return CompareResult(
                    ok=False,
                    message=re.sub(
                        r"Search with release '(\w+)' for these\.",
                        r"So these can't be compared; search release '\1' instead.",
                        problem,
                    ),
                )
            if how == "alias":
                notes.append(f"compared the {folder} docs for '{product.strip()}'")
            prefix = f"markdown/{folder}/"
        note_hits = run_search(
            dbs[TO_RELEASE],
            q,
            top_k=models.RERANK_POOL,
            source_filter=RELEASE_NOTES_PREFIX,
            query_text=q,
        )
        seen_pages: set[str] = set()
        for h in _distinct_hits(dbs[TO_RELEASE], TO_RELEASE, note_hits, len(note_hits)):
            note_page = h.id.split(ID_SEPARATOR, 1)[0]
            if h.score >= WEAK_SCORE and note_page not in seen_pages:  # the best passage per page
                seen_pages.add(note_page)
                result.release_notes.append(h)
        del result.release_notes[RELEASE_NOTES_HITS:]
        kept = {h.id.split(ID_SEPARATOR, 1)[0] for h in result.release_notes}
        result.more_release_notes = _notes_by_name(dbs[TO_RELEASE], q, kept)
        candidates = _candidate_pages(dbs, q, prefix)
        compared = len(candidates)
        pages = []
        for path in candidates:
            where, changed = _changed_page(path, dbs)
            if changed:
                pages.append(changed)
            elif where != "none":
                getattr(result, f"only_in_{where}").append(path)
        pages.sort(key=lambda p: -sum(s.changed_words for s in p.sections))
        pages = [p for p in pages if p.sections][:lim] + [p for p in pages if not p.sections]

    result.changed_pages = [p for p in pages if p.sections]
    minor = sum(p.minor_changes for p in pages)
    left_out, pages_left_out = _fit(result)

    parts = []
    by_name = len(result.more_release_notes)
    if result.release_notes:
        parts.append(_count(len(result.release_notes), "release-notes page"))
        if by_name:
            parts.append(
                f"{_count(by_name, 'more release-notes page')} by name (more_release_notes)"
            )
    elif by_name:
        parts.append(f"{_count(by_name, 'release-notes page')} found by name (more_release_notes)")
    elif not page:
        parts.append("No release-notes pages matched")
    if result.changed_pages:
        parts.append(_count(len(result.changed_pages), "changed page"))
    listed = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else "".join(parts)
    msg = listed + f" ({FROM_RELEASE} -> {TO_RELEASE})." if parts else ""
    scope = "on this page" if page else f"among the {_count(compared, 'page')} that match"
    if not result.changed_pages and not (page and where != "both"):
        msg += (
            f" {_count(minor, 'small rewording')} {scope} (not listed); nothing else changed."
            if minor
            else f" No documentation changes found {scope}."
        )
    for rel in (FROM_RELEASE, TO_RELEASE):
        only = getattr(result, f"only_in_{rel}")
        if only:
            msg += f" {_count(len(only), 'page')} only in the {rel} docs."
    if minor and result.changed_pages:
        msg += f" {_count(minor, 'small rewording')} not listed."
    if pages_left_out:
        msg += (
            f" {_count(pages_left_out, 'more changed page')} left out to keep this short; "
            "narrow the topic or use `product`."
        )
    if left_out:
        msg += (
            " Some sections were left out to keep this short; compare a single page to see "
            "more of them, or read the sections with snow_docs_read."
        )
    if result.release_notes or result.more_release_notes or result.changed_pages:
        has_notes = result.release_notes or result.more_release_notes
        lead = "Lead with the release notes, cite" if has_notes else "Cite"
        msg += f" {lead} ids as [id], and call snow_docs_read(id) for a full section."
    if notes:
        msg += " Note: " + "; ".join(notes) + "."
    result.message = msg.strip()
    return result


@mcp.tool(name="snow_docs_compare", annotations=READ_ONLY)
def snow_docs_compare(
    query: str | None = None,
    page: str | None = None,
    product: str | None = None,
    limit: int = 5,
) -> CompareResult:
    """Show what changed in the ServiceNow docs between the Australia and Brazil releases.

    Use this for questions about what is new or different in Brazil, typically before an
    upgrade from Australia. Returns ServiceNow's own release notes for that upgrade first
    (`release_notes`, one passage per page; `more_release_notes` lists further pages whose
    application name matches the query), then the documentation pages whose text really changed, section by
    section with an excerpt from each release (`changed_pages`). Differences in metadata and
    links are ignored, and small rewordings are counted but not listed. Both releases' docs
    must be installed; the result says so when one is missing.

    Args:
        query: A topic in English, using ServiceNow's terms, e.g. "document intelligence" or
            "flow designer error handling". Translate a question asked in another language.
        page: Compare one page instead: a hit id from snow_docs_search (either release), a
            page path such as "markdown/it-service-management/incident-management.md", or
            the page's address on www.servicenow.com.
            Pass either `query` or `page`, not both.
        product: Optional docs area for `query`, as in snow_docs_search (e.g. "itsm").
        limit: Changed pages to return for `query`, 1-20 (default 5).
    """
    try:
        q, pg = (query or "").strip(), (page or "").strip()
        if bool(q) == bool(pg):
            return CompareResult(
                ok=False,
                message="Pass either `query` (a topic) or `page` (a hit id or page path), "
                "not both and not neither.",
            )

        def not_ready(releases) -> CompareResult:
            for r in releases:
                setup.request(r)
            why = list(dict.fromkeys(_not_ready(r) for r in releases))  # one sentence, once
            return CompareResult(
                ok=False,
                message="Comparing needs both the australia and brazil docs. " + " ".join(why),
            )

        both = (FROM_RELEASE, TO_RELEASE)
        for _attempt in range(2):
            ready = setup.search_ready if q else (lambda r: setup.active_index(r) is not None)
            dbs = {r: setup.active_index(r) for r in both}
            missing = [r for r in dbs if dbs[r] is None or not ready(r)]
            if missing:
                return not_ready(missing)
            _release_unused_indexes()
            try:
                return _compare(q, pg, product, limit, dbs)
            except FileNotFoundError:  # a newer snapshot replaced an index mid-call: once more
                continue
        return not_ready(both)
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_compare failed")
        if not setup.models_on_disk():
            setup.request(config.default_release())
        return CompareResult(ok=False, message=f"Compare failed: {e}")


# --- API table -----------------------------------------------------------------------------

API_METHODS_SHOWN = 12  # methods returned in full for one name (overloads, several classes)
_API_EXAMPLE_CHARS = 1500
_api_tables: dict[str, api_table.ApiTable] = {}


def _api_table(db) -> api_table.ApiTable:
    """The index's API reference as a table, parsed once per index file (well under a second)."""
    key = str(db)
    if key not in _api_tables:
        pages = store.documents(db, api_table.API_PREFIX)
        members = [m for path, text in pages for m in api_table.parse_page(path, text)]
        _api_tables.clear()  # one index at a time is enough; a new snapshot replaces the old
        _api_tables[key] = api_table.ApiTable(members)
    return _api_tables[key]


def _member_id(rel: str, m: api_table.Member) -> str:
    return make_id(rel, m.file_path, m.heading_path, m.occurrence)


@mcp.tool(name="snow_docs_api", annotations=READ_ONLY)
def snow_docs_api(name: str, release: str | None = None) -> ApiResult:
    """Look up a ServiceNow scripting class or method in the API reference, exactly.

    Use this to check that a method exists before writing or reviewing script code, to get its
    parameters and return type, or to list what a class offers. Unlike snow_docs_search it
    answers from a table of every documented method, so "not_found" means the API reference of
    that release does not document it. Covers the server and client scripting APIs (GlideRecord,
    GlideSystem, GlideForm, ...), not REST endpoints; for how to use an API, search instead.

    Args:
        name: A class ("GlideRecord", "Scoped GlideRecord", or the variable it is usually in:
            "gs", "g_form", "g_user"), a method with its class ("GlideRecord.addEncodedQuery",
            "g_form.setMandatory"), or a method name alone ("addEncodedQuery").
        release: "australia" or "brazil". Defaults to the configured release.
    """
    try:
        wanted = (name or "").strip()
        if not wanted:
            return ApiResult(ok=False, message="The name is empty. Pass a class or method name.")
        rel = config.normalize_release(release)
        if rel is None:
            return ApiResult(ok=False, message=_unknown_release(str(release)))
        db = setup.active_index(rel)
        if db is None:
            setup.request(rel)
            return ApiResult(ok=False, release=rel, message=_not_ready(rel))
        _release_unused_indexes()
        table = _api_table(db)
        kind, found = table.find(wanted)
        result = ApiResult(ok=True, message="", release=rel, snapshot=_snapshot_of(rel), kind=kind)
        if kind == "class":
            for class_name in sorted(found):
                listed = found[class_name]
                pages = list(dict.fromkeys(make_id(rel, m.file_path, "") for m in listed))
                result.classes.append(
                    ApiClass(
                        class_name=class_name,
                        members=[m.signature for m in listed],
                        page_ids=pages,
                    )
                )
            total = sum(len(c.members) for c in result.classes)
            result.message = (
                f"{_count(len(result.classes), 'class')} named '{wanted}' with "
                f"{_count(total, 'member')} in the {rel} API reference. Look up "
                "Class.method for a method's parameters and return type."
            ).replace("classs", "classes")
        elif kind == "method":
            for m in sorted(found, key=lambda m: (m.class_name, m.name))[:API_METHODS_SHOWN]:
                example = m.example
                if len(example) > _API_EXAMPLE_CHARS:
                    example = example[:_API_EXAMPLE_CHARS].rstrip() + "\n…"
                page = store.get_document(db, m.file_path) or ""
                result.methods.append(
                    ApiMethod(
                        class_name=m.class_name,
                        name=m.name,
                        kind=m.kind,
                        signature=m.signature,
                        parameters=[ApiParam(**asdict(p)) for p in m.params],
                        returns=m.returns,
                        returns_description=m.returns_description,
                        description=m.description,
                        example=example,
                        id=_member_id(rel, m),
                        url=page_url(db, rel, m.file_path, page),
                    )
                )
            result.message = (
                f"{_count(len(found), 'entry')} for '{wanted}' in the {rel} API reference"
                + (
                    f" (the first {API_METHODS_SHOWN} shown)"
                    if len(found) > API_METHODS_SHOWN
                    else ""
                )
                + ". Cite ids as [id]; snow_docs_read(id) gives the full section."
            ).replace("entrys", "entries")
        else:
            result.suggestions = list(found)
            hint = f" Closest names: {', '.join(result.suggestions)}." if result.suggestions else ""
            result.message = (
                f"'{wanted}' is not in the {rel} API reference ({len(table):,} documented "
                f"methods and properties).{hint} Do not use it in code unless another source "
                "confirms it; snow_docs_search may find it outside the API reference."
            )
        return result
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_api failed")
        return ApiResult(ok=False, message=f"API lookup failed: {e}")


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
    models_state = (
        "ready" if setup.models_on_disk() else (setup.models_status().message or "missing")
    )
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


@mcp.prompt(name="upgrade_review", title="Upgrade review: Australia to Brazil")
def upgrade_review(product: str) -> str:
    """Write a cited checklist of what to check for a product when upgrading to Brazil."""
    return f"{UPGRADE_REVIEW_RULES}\n\nProduct: {product}"


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
