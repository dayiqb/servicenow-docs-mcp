"""ServiceNow documentation MCP server — stdio entry point.

Tools (all read-only):
    snow_docs_search   hybrid (semantic + keyword) search with reranking over the ServiceNow
                       product docs, per release (australia, brazil)
    snow_docs_read     the full section behind a search hit
    snow_docs_compare  what changed between the australia and brazil docs for a topic or page
    snow_docs_api      a class's methods, or a method's parameters and return type, exactly
    snow_docs_check_script  which calls and tables in a script the docs do not have
    snow_docs_browse   the docs as a tree: product areas, folders and pages
    snow_docs_open     show a page to the user as a document (in the panel)
    snow_docs_diagram  show a process from the docs as a flow or swimlanes (in the panel)
    snow_docs_sdk_status   whether the ServiceNow SDK is set up, and for which instances
    snow_docs_sdk_explain  the SDK's own documentation (Fluent), for the installed version
    snow_docs_status   setup/update progress per release, and where data lives

Prompt:
    answer             answer a question from the docs, with citations
    upgrade_review     a cited checklist for upgrading one product from Australia to Brazil
    setup_checklist    a cited, ordered checklist for setting up one feature

Answers are written by the Claude that calls these tools; the server only retrieves. The
rules it should follow are sent as server instructions (ANSWER_RULES).

Console script `snow-docs-mcp`:
    snow-docs-mcp                       serve MCP over stdio (what Claude apps launch)
    snow-docs-mcp setup [RELEASE|all]   download docs index(es) and models now, with progress
    snow-docs-mcp search "QUERY" | read ID | compare [QUERY] | api NAME | check-script FILE |
                  browse [PRODUCT] | status | sdk-status | sdk-explain [TOPIC]
                                        the tools from a terminal: one JSON result on stdout
                                        (see snow_docs_mcp.cli; as a library: snow_docs_mcp.api)
    snow-docs-mcp check-index --australia PATH --brazil PATH
                                        count what the tools find in an index (maintainers)

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
import hashlib
import itertools
import json
import logging
import os
import re
import sys
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.types import ToolAnnotations

from snow_docs_mcp import (
    api_table,
    config,
    diagram,
    entry,
    identifiers,
    models,
    products,
    script_check,
    sdk,
    sections,
    setup,
    store,
    tables,
)
from snow_docs_mcp.compare import compare_pages
from snow_docs_mcp.notes import RELEASE_NOTES_PREFIX
from snow_docs_mcp.notes import by_name as notes_by_name
from snow_docs_mcp.read import ReadResult as _ReadResult
from snow_docs_mcp.read import not_an_id, page_url, read_section
from snow_docs_mcp.results import (
    ApiClass,
    ApiEndpoint,
    ApiMethod,
    ApiParam,
    ApiResult,
    BrowseFolder,
    BrowsePage,
    BrowseResult,
    ChangedPage,
    CompareResult,
    DiagramLane,
    DiagramLink,
    DiagramResult,
    DiagramStep,
    Hit,
    OpenResult,
    ReadResult,
    ReleaseStatus,
    ScriptCheckResult,
    ScriptFinding,
    SdkExplainResult,
    SdkInstance,
    SdkStatusResult,
    SdkTopic,
    SearchResult,
    SectionDiff,
    StatusResult,
)
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
   ids as usual. A section marked `small` is a rewording of a few words: give it one line,
   because a changed number or a "not" can be what matters.
8. Writing or reviewing ServiceNow script code is a docs question too: search for what the
   script relies on (when it runs, what the platform does by default) and do not state such
   behavior from memory, in the answer or in code comments. Check each class and method with
   snow_docs_api. If it answers not_found, do not use that method; say so, and offer the
   closest documented one. After writing or changing a script, pass the whole script to
   snow_docs_check_script and act on what it finds before showing the code.
9. Table and field names depend on the instance. If the ServiceNow SDK (now-sdk) or another
   tool for the user's own instance is available, offer to check them there, and ask before
   anything that queries the instance; otherwise say they are unverified.
10. For code written with the ServiceNow SDK or Fluent, read snow_docs_sdk_explain: it is the
   documentation of the SDK version installed on this computer. snow_docs_sdk_status shows
   whether the SDK is set up and for which instances. After changing a Fluent file, suggest
   `now-sdk build`, which type-checks it locally.
11. To show something to the user rather than read it yourself: snow_docs_open displays a page
   as a document, and snow_docs_diagram draws a process as a flow, or as swimlanes when
   several roles take part. Draw a diagram when a lifecycle, a procedure with decisions or a
   hand-off is easier to see than to read; take every step from the docs you read and give
   its source id. Clients without panels get the diagram as Mermaid text."""

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
   the whole page). If the result is truncated, read it again with max_chars 100000. If you
   still do not have every part of the page in front of you, read it part by part: the id
   of a part is the page id followed by the page title, " > " and the part's heading (for
   example "… > New features"). Do not write the checklist from a page you read only partly.
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
   any. Give a section marked `small` one line: a changed number or a "not" can be what
   matters.
5. If a tool for the user's own ServiceNow instance is connected, ask before using it. With a
   yes, look up the instance's release and installed applications, and mark the items that
   apply to this instance.
6. End with what the review does not cover: customizations, integrations and other products.
Answer in the user's language; keep product, feature and field names as the docs write them."""

# The setup checklist recipe: the `setup_checklist` prompt, manifest.json and the
# servicenow-setup-checklist skill carry this text word for word (tests keep them in step).
SETUP_CHECKLIST_RULES = """\
Write a setup checklist: the steps to set up one ServiceNow feature, in order, taken from
the docs. Use only the ServiceNow docs tools; do not fill gaps from memory.
1. Find the pages. Call snow_docs_search with the feature and words such as "set up",
   "configure" and "activate". If the feature is a product or an application, also call
   snow_docs_browse for its folder and pick the setup, configuration, installation and
   administration pages by title.
2. Read every page you take a step from with snow_docs_read (the section, or the whole page
   with the id cut off after "::"). Follow "Before you begin" and "What to do next" to the
   pages they name, and read those too.
3. Write the checklist in these parts, in this order, each item ending with its citation [id]:
   - Before you start: plugins or store applications to activate, licenses, the roles needed
     to do the setup, and other features it depends on.
   - Steps: numbered, in the order the docs give, one action per step, with the navigation
     path and the role where the docs state them.
   - Check that it works: how the docs say to verify the result. If they do not say, write
     that.
   - Next: optional configuration the docs point to.
4. Where the docs for the user's release (Australia unless they say Brazil) lack a step, say
   so instead of filling it in. If two pages disagree, show both.
5. If a tool for the user's own ServiceNow instance is connected, ask before using it. With a
   yes, look up which plugins are active and which roles the user has, and mark the items
   that are already done.
Answer in the user's language; keep navigation paths, field names and role names as the docs
write them."""

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)


@contextlib.asynccontextmanager
async def _lifespan(_server: MCPServer) -> AsyncIterator[dict]:
    # Inside the SDK's stdio serving window: safe to start work that may print.
    setup.start()
    yield {}


# The results panel (MCP Apps): a host that supports it shows this page next to the result of
# a search or a comparison; every other client just gets the result. One self-contained HTML
# file, because the host's sandbox allows no external script, style, font or request.
def panel_html() -> str:
    return (Path(__file__).parent / "ui" / "panel.html").read_text(encoding="utf-8")


def panel_uri(html: str) -> str:
    """The address the panel is served at. A host keeps the page it fetched under its address
    and does not ask for it again, not even after the extension is replaced. So the address is
    made from the page itself: a panel that has changed is a page the host has never seen."""
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    return f"ui://servicenow-docs/panel-{digest}.html"


PANEL_URI = panel_uri(panel_html())
_PANEL_META = {"ui": {"resourceUri": PANEL_URI}}


_apps = Apps()
_apps.add_html_resource(
    PANEL_URI,
    panel_html(),
    name="ServiceNow Docs results",
    description="Search results and release comparisons from the ServiceNow docs, to read in place.",
    prefers_border=True,
)

mcp = MCPServer(
    name="servicenow-docs",
    title="ServiceNow Docs",
    version=__version__,
    instructions=ANSWER_RULES,
    lifespan=_lifespan,
    extensions=[_apps],
)


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
    wanted = products.normalize(product)
    for other_rel in config.RELEASES:
        other_db = setup.active_index(other_rel) if other_rel != rel else None
        if other_db is not None and wanted in store.products(other_db):
            return (
                f"The {rel} docs have no '{wanted}' folder; the {other_rel} docs do. Call again "
                f"with release '{other_rel}'."
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


@mcp.tool(name="snow_docs_search", annotations=READ_ONLY, meta=_PANEL_META)
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
            small=c.small,
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
        result.more_release_notes = notes_by_name(dbs[TO_RELEASE], q, kept)
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
        msg += f" No documentation changes found {scope}."
    for rel in (FROM_RELEASE, TO_RELEASE):
        only = getattr(result, f"only_in_{rel}")
        if only:
            msg += f" {_count(len(only), 'page')} only in the {rel} docs."
    if minor and result.changed_pages:
        msg += (
            f" {_count(minor, 'small rewording')} among the sections, marked `small`: a changed "
            'number or a "not" can still matter.'
        )
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


@mcp.tool(name="snow_docs_compare", annotations=READ_ONLY, meta=_PANEL_META)
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
    links are ignored. A rewording of a few words is marked `small` and shown by the words
    around it. Both releases' docs must be installed; the result says so when one is missing.

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
API_ENDPOINTS_SHOWN = 6
API_BODY_PARAMS = 40
_API_EXAMPLE_CHARS = 1500
_api_tables: dict[str, api_table.ApiTable] = {}


def _api_table(db) -> api_table.ApiTable:
    """The index's API reference as a table, parsed once per index file (well under a second)."""
    return store.per_index(_api_tables, db, lambda path: api_table.load(path))


def _member_id(rel: str, m: api_table.Member) -> str:
    return make_id(rel, m.file_path, m.heading_path, m.occurrence)


@mcp.tool(name="snow_docs_api", annotations=READ_ONLY)
def snow_docs_api(name: str, release: str | None = None) -> ApiResult:
    """Look up a ServiceNow scripting class or method in the API reference, exactly.

    Use this to check that a method exists before writing or reviewing script code, to get its
    parameters and return type, or to list what a class offers. Unlike snow_docs_search it
    answers from a table of every documented method, so "not_found" means the API reference of
    that release does not document it. Covers the server and client scripting APIs (GlideRecord,
    GlideSystem, GlideForm, ...) and the REST APIs; for how to use an API, search instead.

    Args:
        name: A class ("GlideRecord", "Scoped GlideRecord", or the variable it is usually in:
            "gs", "g_form", "current", "$sp", ...), a method with its class
            ("GlideRecord.addEncodedQuery", "g_form.setMandatory", "$sp.getParameter"), a chain
            of calls ("gs.getUser().getName()"), or a method name alone ("addEncodedQuery").
            A namespace in front is fine ("sn_ws.RESTMessageV2"). Class names are matched in
            any case, method names exactly. For REST: an API ("Table API"), or an endpoint as
            a path with or without its verb ("POST /api/now/table/incident", "/now/table"); a
            whole instance URL with its query string works too.
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
        elif kind == "rest_api":
            for api_name, listed in found.items():
                pages = list(dict.fromkeys(make_id(rel, e.file_path, "") for e in listed))
                result.classes.append(
                    ApiClass(
                        class_name=api_name,
                        members=[f"{e.verb} {e.path}" for e in listed],
                        page_ids=pages,
                    )
                )
            result.message = (
                f"{_count(len(result.classes[0].members), 'endpoint')} in the {api_name} REST API "
                f'({rel} API reference). Look up "VERB /path" for an endpoint\'s parameters.'
            )
        elif kind == "endpoint":
            for e in found[:API_ENDPOINTS_SHOWN]:
                page = store.get_document(db, e.file_path) or ""
                result.endpoints.append(
                    ApiEndpoint(
                        api=e.api,
                        verb=e.verb,
                        path=e.path,
                        default_url=e.default_url,
                        description=e.description,
                        path_parameters=[ApiParam(**asdict(x)) for x in e.path_params],
                        query_parameters=[ApiParam(**asdict(x)) for x in e.query_params],
                        body_parameters=[
                            ApiParam(**asdict(x)) for x in e.body_params[:API_BODY_PARAMS]
                        ],
                        id=make_id(rel, e.file_path, e.heading_path, e.occurrence),
                        url=page_url(db, rel, e.file_path, page),
                    )
                )
            result.message = (
                f"{_count(len(found), 'endpoint')} for '{wanted}' in the {rel} API reference"
                + (
                    f" (the first {API_ENDPOINTS_SHOWN} shown)"
                    if len(found) > API_ENDPOINTS_SHOWN
                    else ""
                )
                + ". Parameter descriptions are shortened; snow_docs_read(id) gives the full "
                "section with status codes and examples."
            )
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
                f"methods and properties, {len(table.endpoints):,} REST endpoints).{hint} "
                "Do not use it in code unless another source "
                "confirms it; snow_docs_search may find it outside the API reference."
            )
        return result
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_api failed")
        return ApiResult(ok=False, message=f"API lookup failed: {e}")


@mcp.tool(name="snow_docs_check_script", annotations=READ_ONLY)
def snow_docs_check_script(code: str, release: str | None = None) -> ScriptCheckResult:
    """Check ServiceNow script code against the docs: every method call on an object whose
    class can be told, and every table name it opens.

    Call this with the whole script after writing or changing ServiceNow script code, before
    showing it to the user. It follows `new GlideRecord(...)`, return types of documented
    methods, JSDoc and TypeScript types, the platform's variables (gs, current, g_form, ...)
    and the usual names (gr, gdt). A finding means the API reference does not document the
    method, or the docs never mention the table: fix it, or tell the user it could not be
    verified (custom tables and undocumented methods exist). Field names are not checked:
    they depend on the instance.

    Args:
        code: The script (JavaScript or TypeScript).
        release: "australia" or "brazil". Defaults to the configured release.
    """
    try:
        if not (code or "").strip():
            return ScriptCheckResult(ok=False, message="The code is empty. Pass the script.")
        rel = config.normalize_release(release)
        if rel is None:
            return ScriptCheckResult(ok=False, message=_unknown_release(str(release)))
        db = setup.active_index(rel)
        if db is None:
            setup.request(rel)
            return ScriptCheckResult(ok=False, release=rel, message=_not_ready(rel))
        _release_unused_indexes()
        found = script_check.review(code, _api_table(db), tables.names(db), limit=30)
        result = ScriptCheckResult(
            ok=True,
            message="",
            release=rel,
            snapshot=_snapshot_of(rel),
            checked_calls=found.checked_calls,
            checked_tables=found.checked_tables,
            findings=[
                ScriptFinding(kind=f.kind, name=f.call, line=f.line, suggestions=f.suggestions)
                for f in found.findings
            ],
        )
        what = f"{_count(found.checked_calls, 'call')} and {_count(found.checked_tables, 'table name')}"
        if not found.checked_calls and not found.checked_tables:
            result.message = (
                "Nothing to check: the code has no calls on objects whose class can be told, "
                "and opens no table by name. Field names are never checked."
            )
        elif result.findings:
            result.message = (
                f"Checked {what}: {len(result.findings)} of them are not in the {rel} docs. "
                "Look methods up with snow_docs_api; fix mistakes, and tell the user about "
                "anything that could not be verified. Field names are not checked."
            )
        else:
            result.message = (
                f"Checked {what} against the {rel} docs: all documented. Field names are not "
                "checked; they depend on the instance."
            )
        return result
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_check_script failed")
        return ScriptCheckResult(ok=False, message=f"Script check failed: {e}")


# --- ServiceNow SDK -----------------------------------------------------------------------

SDK_TOPICS_SHOWN = 40


@mcp.tool(name="snow_docs_sdk_status", annotations=READ_ONLY)
def snow_docs_sdk_status() -> SdkStatusResult:
    """Show whether the ServiceNow SDK (now-sdk) is set up on this computer: its version and
    the instances it has credentials for (alias, address, kind of sign-in, which is default).

    Read-only: it runs `now-sdk --version` and `now-sdk auth --list`, contacts no instance and
    shows no user name or secret. Use it before suggesting now-sdk commands, to know which
    instance alias to name. Adding or removing an instance is done by the user in a terminal
    (`now-sdk auth --add <instance> --type oauth`), never through this tool.
    """
    try:
        found = sdk.status()
        if not found.installed:
            return SdkStatusResult(ok=True, installed=False, message=found.message)
        if found.error:
            return SdkStatusResult(
                ok=False,
                installed=True,
                version=found.version,
                message=(
                    f"ServiceNow SDK {found.version or '(unknown version)'} is installed, but "
                    f"its instances could not be read: {found.error}. Which instances are "
                    "configured is unknown; the user can run the command in a terminal to see "
                    "why."
                ),
            )
        instances = [SdkInstance(**asdict(i)) for i in found.instances]
        default = next((i for i in instances if i.default), None)
        if not instances:
            tail = (
                "No instance is configured. The user adds one in a terminal with "
                "`now-sdk auth --add <instance> --type oauth`."
            )
        elif default:
            tail = (
                f"{_count(len(instances), 'instance')} configured; the default is "
                f"{default.alias} ({default.host})."
            )
        else:
            tail = (
                f"{_count(len(instances), 'instance')} configured, none as default; the user "
                "sets one with `now-sdk auth --use <alias>`."
            )
        return SdkStatusResult(
            ok=True,
            installed=True,
            version=found.version,
            instances=instances,
            message=f"ServiceNow SDK {found.version or '(unknown version)'} is installed. {tail}",
        )
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_sdk_status failed")
        return SdkStatusResult(ok=False, message=f"SDK status failed: {e}")


def _sdk_topic(wanted: str, known: list[sdk.Topic]) -> tuple[str, list[sdk.Topic]]:
    """(the topic a name or keyword means, or "", the topics it could mean)."""
    low = wanted.strip().lower()
    by_name = {t.name.lower(): t for t in known}
    if low in by_name:
        return by_name[low].name, []
    exact = [t for t in known if low in {k.strip().lower() for k in t.keywords.split(",")}]
    loose = exact or [t for t in known if low in t.name.lower() or low in t.keywords.lower()]
    if len(loose) == 1:
        return loose[0].name, []
    apis = [t for t in exact if t.name.endswith("-api")]
    if len(apis) == 1:  # "BusinessRule" names the API page; its guide is listed beside it
        return apis[0].name, [t for t in loose if t is not apis[0]]
    return "", loose


@mcp.tool(name="snow_docs_sdk_explain", annotations=READ_ONLY)
def snow_docs_sdk_explain(topic: str | None = None, max_chars: int = 20000) -> SdkExplainResult:
    """Read the ServiceNow SDK's own documentation (`now-sdk explain`): Fluent APIs and guides,
    for the SDK version installed on this computer.

    Use this for anything written with the ServiceNow SDK or Fluent (BusinessRule, Table, Acl,
    Flow, AI agents, now.config.json, ...): it is more exact for the installed version than the
    product docs. Without `topic` it lists the topics. With a topic name ("businessrule-api"),
    a Fluent name ("BusinessRule") or a keyword ("business rule") it returns that topic's
    documentation, or the topics that match when there are several. Read-only and local.

    Args:
        topic: A topic name, a Fluent API name or a keyword. Omit to list all topics.
        max_chars: Maximum characters of documentation to return (500-100000, default 20000).
    """
    try:
        if not sdk.installed():
            return SdkExplainResult(ok=False, message=sdk.NOT_INSTALLED)
        version = sdk.version()
        known = sdk.topics()
        result = SdkExplainResult(ok=True, message="", version=version)
        wanted = (topic or "").strip()
        if not wanted:
            result.topics = [SdkTopic(name=t.name) for t in known]
            result.message = (
                f"{_count(len(known), 'topic')} in the documentation of ServiceNow SDK "
                f"{version}. Pass a name as `topic` to read it, or a keyword to narrow "
                "the list."
            )
            return result
        name, others = _sdk_topic(wanted, known)
        if not name:
            if others:
                result.topics = [
                    SdkTopic(name=t.name, keywords=t.keywords) for t in others[:SDK_TOPICS_SHOWN]
                ]
                result.message = (
                    f"{_count(len(others), 'topic')} match '{wanted}'"
                    + (
                        f" (the first {SDK_TOPICS_SHOWN} shown)"
                        if len(others) > SDK_TOPICS_SHOWN
                        else ""
                    )
                    + ". Pass one of the names as `topic`."
                )
            else:
                close = difflib.get_close_matches(
                    wanted.lower(), [t.name for t in known], n=3, cutoff=0.5
                )
                hint = f" Closest: {', '.join(close)}." if close else ""
                result.message = (
                    f"No topic for '{wanted}' in the documentation of ServiceNow SDK "
                    f"{version}.{hint} Call without `topic` to list them all."
                )
            return result
        text = sdk.explain(name)
        if text is None:
            return SdkExplainResult(ok=False, message=f"now-sdk could not show the topic '{name}'.")
        limit = max(500, min(int(max_chars), 100000))
        result.topic = name
        result.truncated = len(text) > limit
        result.content = text[:limit]
        result.topics = [
            SdkTopic(name=t.name, keywords=t.keywords) for t in others[:SDK_TOPICS_SHOWN]
        ]
        result.message = (
            f"The '{name}' topic from the documentation of ServiceNow SDK {version}."
            + (" Cut short; pass a larger max_chars for the rest." if result.truncated else "")
            + (f" Related: {', '.join(t.name for t in others[:5])}." if others else "")
        )
        return result
    except sdk.SdkError as e:
        return SdkExplainResult(
            ok=False, message=f"The SDK's documentation could not be read: {e}."
        )
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_sdk_explain failed")
        return SdkExplainResult(ok=False, message=f"SDK explain failed: {e}")


# --- browse -------------------------------------------------------------------------------

BROWSE_PAGES_SHOWN = 100
_titles: dict[str, dict[str, str]] = {}


def _page_titles(db) -> dict[str, str]:
    return store.per_index(_titles, db, lambda path: store.titles_by_path(path))


@mcp.tool(name="snow_docs_browse", annotations=READ_ONLY, meta=_PANEL_META)
def snow_docs_browse(
    product: str | None = None,
    folder: str | None = None,
    release: str | None = None,
    offset: int = 0,
) -> BrowseResult:
    """Browse the ServiceNow docs as a tree instead of searching them.

    Use this to see what the docs have on a product: its sub-areas and the pages in each, by
    title. Without arguments it lists the product areas. With `product` it lists that area's
    folders (with page counts) and its own pages; with `folder` it goes further down. Open a
    page with snow_docs_read(id). Good for "what is documented about X", for finding a page
    whose words you do not know, and for the release notes (product "release-notes"; the
    combined notes for upgrades from Australia are "delta-australia-brazil", with release
    "brazil").

    Args:
        product: A product area, as in snow_docs_search ("it-service-management", "itsm", ...).
        folder: A folder inside the product ("incident-management"), or a whole path as a
            listing returned it ("it-service-management/incident-management"); its first part
            may be an abbreviation ("itsm/incident-management").
        release: "australia" or "brazil". Defaults to the configured release.
        offset: Skip this many pages of a long folder (the message says when there are more).
    """
    try:
        rel = config.normalize_release(release)
        if rel is None:
            return BrowseResult(ok=False, message=_unknown_release(str(release)))
        db = setup.active_index(rel)
        if db is None:
            setup.request(rel)
            return BrowseResult(ok=False, release=rel, message=_not_ready(rel))
        _release_unused_indexes()
        parts: list[str] = []
        if product and product.strip():
            known = store.products(db)
            top, how = products.resolve(product, known)
            if how not in ("exact", "alias"):
                return BrowseResult(
                    ok=False, release=rel, message=_product_problem(product, top, rel, db, known)
                )
            parts.append(top)
        parts += [p for p in (folder or "").replace("\\", "/").strip("/").split("/") if p]
        if parts[:1] == ["markdown"]:
            parts = parts[1:]
        if len(parts) > 1 and parts[0] == parts[1] and product:  # folder given as a whole path
            parts = parts[1:]
        titles = _page_titles(db)
        if parts and not (product and product.strip()):
            # a path given whole may start with an abbreviation: itsm/incident-management
            tops = sorted({p.split("/", 2)[1] for p in titles if p.count("/") >= 2})
            top, how = products.resolve(parts[0], tops)
            if how == "alias":
                parts[0] = top
        path = "/".join(parts)
        prefix = f"markdown/{path}/" if path else "markdown/"
        under = sorted(p for p in titles if p.startswith(prefix))
        if not under:
            parent = "/".join(parts[:-1])
            parent_prefix = f"markdown/{parent}/" if parent else "markdown/"
            siblings = sorted(
                {
                    p[len(parent_prefix) :].split("/", 1)[0]
                    for p in titles
                    if p.startswith(parent_prefix) and "/" in p[len(parent_prefix) :]
                }
            )
            close = difflib.get_close_matches(parts[-1], siblings, n=3, cutoff=0.6)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            return BrowseResult(
                ok=False,
                release=rel,
                message=f"No folder '{path}' in the {rel} docs.{hint} "
                + (
                    f"Browse '{parent}' to see what is there."
                    if parent
                    else "Browse without arguments to see the product areas."
                ),
            )
        counts: dict[str, int] = {}
        own: list[str] = []
        for p in under:
            rest = p[len(prefix) :]
            if "/" in rest:
                name = rest.split("/", 1)[0]
                counts[name] = counts.get(name, 0) + 1
            else:
                own.append(p)
        result = BrowseResult(
            ok=True, message="", release=rel, snapshot=_snapshot_of(rel), path=path
        )
        result.folders = [
            BrowseFolder(name=n, path=f"{path}/{n}" if path else n, pages=c)
            for n, c in sorted(counts.items())
        ]
        listed = sorted(
            ((titles[p] or p.rsplit("/", 1)[-1], p) for p in own), key=lambda x: x[0].lower()
        )
        start = max(0, int(offset))
        result.pages = [
            BrowsePage(title=sections.unescape_markdown(t), id=make_id(rel, p, ""))
            for t, p in listed[start : start + BROWSE_PAGES_SHOWN]
        ]
        result.pages_left_out = max(0, len(listed) - start - BROWSE_PAGES_SHOWN)
        if not path:
            result.message = (
                f"{_count(len(result.folders), 'product area')} in the {rel} docs, with their "
                "page counts. Pass `product` to open one."
            )
        else:
            result.message = (
                f"{path}: {_count(len(result.folders), 'folder')} and "
                f"{_count(len(listed), 'page')} ({rel} docs)."
            )
            if result.pages_left_out:
                result.message += (
                    f" {_count(result.pages_left_out, 'more page')} after these: call again "
                    f"with offset={start + BROWSE_PAGES_SHOWN}."
                )
            elif start and not result.pages:
                result.message += (
                    f" No pages shown: offset {start} is past the last of them; the last "
                    f"listing starts at offset={max(0, (len(listed) - 1) // BROWSE_PAGES_SHOWN) * BROWSE_PAGES_SHOWN}."
                )
            result.message += (
                " Pass a folder's `path` as `folder` to go deeper; read a page with "
                "snow_docs_read(id)."
            )
        return result
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_browse failed")
        return BrowseResult(ok=False, message=f"Browse failed: {e}")


# --- views for the user -------------------------------------------------------------------

OPEN_HEADINGS = 120


@mcp.tool(name="snow_docs_open", annotations=READ_ONLY, meta=_PANEL_META)
def snow_docs_open(id: str) -> OpenResult:
    """Show a documentation page to the user as a readable document, in the panel.

    Use this when the user wants to see or read a page themselves ("show me that page", "open
    the docs on X"). It displays the page with its table of contents, starting at the section
    the id names, and returns only the page's title and section list: the text is not added
    to your context. To read a page yourself, use snow_docs_read. In a client that shows no
    panel, give the user the returned `url` instead.

    Args:
        id: A hit id from snow_docs_search or snow_docs_browse; an id ending in "::" opens the
            page at the top.
    """
    try:
        parsed = parse_id(id)
        if parsed is None:
            return OpenResult(ok=False, message=not_an_id(id).message)
        rel_raw, file_path, heading_path, occurrence = parsed
        rel = config.normalize_release(rel_raw)
        if rel is None:
            return OpenResult(ok=False, message=_unknown_release(str(rel_raw)))
        db = setup.active_index(rel)
        if db is None:
            setup.request(rel)
            return OpenResult(ok=False, message=_not_ready(rel))
        found = read_section(db, rel, file_path, heading_path, occurrence, 500)
        if not found.ok:
            return OpenResult(ok=False, message=found.message)
        page = store.get_document(db, file_path) or ""
        headings = sections.headings(page)
        title = found.title or file_path.rsplit("/", 1)[-1]
        return OpenResult(
            ok=True,
            id=make_id(rel, file_path, ""),
            focus=heading_path,
            title=title,
            url=found.url,
            release=rel,
            product=store.product_of(file_path),
            headings=headings[:OPEN_HEADINGS],
            message=f"Showing '{title}' ({_count(len(headings), 'section')}, {rel} docs) to the user "
            "in the panel. Its text is not in your context: call snow_docs_read(id) if you need "
            "it. If this client shows no panel, give the user the url.",
        )
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_open failed")
        return OpenResult(ok=False, message=f"Open failed: {e}")


@mcp.tool(name="snow_docs_diagram", annotations=READ_ONLY, meta=_PANEL_META)
def snow_docs_diagram(
    title: str,
    steps: list[DiagramStep],
    links: list[DiagramLink] | None = None,
    lanes: list[DiagramLane] | None = None,
) -> DiagramResult:
    """Show a process from the docs to the user as a diagram, in the panel: a flow, or
    swimlanes when several roles, teams or systems take part.

    Use this when a picture explains better than text: a lifecycle, a procedure with
    decisions, an approval, a hand-off between roles. First read the docs (snow_docs_search,
    snow_docs_read), then pass the steps exactly as the docs give them, each with the
    `source_id` of the passage it comes from; the user can open that passage from the step.
    Do not add steps the docs do not have. The diagram is checked before it is shown: ids
    of steps and of lanes must be unique, links must join existing steps, and every source id
    must be a real page.

    Args:
        title: What the diagram shows, e.g. "Incident lifecycle".
        steps: The steps, in reading order (2 to 40). `kind` is "start", "step", "decision"
            or "end". Give `lane` when you pass `lanes`.
        links: The arrows between steps; a decision's paths carry a `label` ("Yes", "No").
            Omit it for a straight sequence: each step then leads to the next.
        lanes: For swimlanes: the roles, teams or systems, left to right.
    """
    try:
        lanes = lanes or []
        if links is None:
            links = [DiagramLink(source=a.id, target=b.id) for a, b in itertools.pairwise(steps)]
        problems = diagram.problems(steps, links, lanes)
        if problems:
            return DiagramResult(
                ok=False,
                message="The diagram was not shown: "
                + "; ".join(problems)
                + ". Fix these and call again.",
            )
        unsourced = sum(1 for s in steps if not s.source_id and s.kind in ("step", "decision"))
        kind = "swimlane" if lanes else "flow"
        message = (
            f"The {kind} diagram '{title.strip()}' with {_count(len(steps), 'step')}"
            + (f" in {_count(len(lanes), 'lane')}" if lanes else "")
            + " is shown to the user in the panel."
        )
        if unsourced:
            verb = "has" if unsourced == 1 else "have"
            message += f" {_count(unsourced, 'step')} {verb} no source: say which steps are your own summary."
        message += " If this client shows no panel, show the `mermaid` text in a code block."
        return DiagramResult(
            ok=True,
            message=message,
            title=title.strip(),
            kind=kind,
            lanes=lanes,
            steps=steps,
            links=links,
            mermaid=diagram.mermaid(title, lanes, steps, links),
        )
    except Exception as e:  # tools report errors, never raise
        logger.exception("snow_docs_diagram failed")
        return DiagramResult(ok=False, message=f"Diagram failed: {e}")


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


@mcp.prompt(name="setup_checklist", title="Setup checklist for a feature")
def setup_checklist(feature: str) -> str:
    """Write a cited, ordered checklist for setting up a ServiceNow feature."""
    return f"{SETUP_CHECKLIST_RULES}\n\nFeature: {feature}"


# --- process entry points -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Entry point: `snow-docs-mcp` serves MCP over stdio; `snow-docs-mcp setup` downloads."""
    args = sys.argv[1:] if argv is None else argv
    entry.configure_logging()
    entry.use_system_certificates()

    if args[:1] == ["setup"]:
        sys.exit(entry.run_setup_cli(args[1:]))
    if args:
        from snow_docs_mcp import cli

        if args[0] in cli.COMMANDS:
            sys.exit(cli.run(args))
    if args[:1] == ["check-index"]:
        from snow_docs_mcp import health

        sys.exit(health.run_cli(args[1:]))
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
            entry.noisy_startup_probe()
    else:
        # fd-level guard over the startup window: point fd 1 at stderr while initialising,
        # then restore the real wire before mcp.run() (the SDK claims fd 1 inside it).
        # Catches Python prints, carriage-return bars and raw os.write(1, ...).
        wire_fd = os.dup(1)
        os.dup2(2, 1)
        try:
            if noise:
                entry.noisy_startup_probe()
        finally:
            sys.stdout.flush()
            os.dup2(wire_fd, 1)
            os.close(wire_fd)

    logger.info("snow-docs-mcp %s serving over stdio (data: %s)", __version__, config.data_home())
    mcp.run()


if __name__ == "__main__":
    main()
