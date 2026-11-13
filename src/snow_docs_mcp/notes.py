"""ServiceNow's release notes for upgrades from Australia to Brazil, by application and by
product family.

Search misses a release-notes page when the docs call the product something else ("Flow
Designer" is under "Flows, subflows, and actions"), and one product often has several pages.
The pages are therefore also found by name: every page's application comes from its title,
the product families from the breadcrumbs of the per-application release notes, and each
application's product area from where its own docs are.
"""

from __future__ import annotations

import re

from snow_docs_mcp import products, sections, store
from snow_docs_mcp.results import NotesPage
from snow_docs_mcp.search import make_id

RELEASE = "brazil"  # the release whose docs hold the combined release notes
RELEASE_NOTES_PREFIX = "markdown/delta-australia-brazil/"
_WORD = re.compile(r"\w+")
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
_cache: dict[str, tuple[dict, dict, dict]] = {}


def _phrase(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def _build_index(
    db,
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, set[str]], dict[str, set[str]]]:
    """(application phrase -> its pages as (page path, application name), family phrase ->
    application phrases, application phrase -> the product areas its own docs are in) for the
    release-notes pages. An application can have two pages (one named with its abbreviation);
    both are kept, in path order. An application's own docs are the pages titled with its name; their
    top folder is the product area. Families come from the breadcrumb of the
    per-application release notes: "<application> release notes" under "<family> release
    notes" (more than one level, e.g. Workflow Studio under App development and low-code)."""
    apps: dict[str, list[tuple[str, str]]] = {}
    chains: list[list[str]] = []
    for path in sorted(store.page_paths(db)[0]):  # sorted: the same answer every start
        if path.startswith(RELEASE_NOTES_PREFIX):
            page = store.get_document(db, path) or ""
            m = _NOTES_TITLE.match(sections.front_matter_value(page, "title"))
            if m:
                name = sections.unescape_markdown(m.group(1))
                apps.setdefault(_phrase(_PARENS.sub("", name)), []).append((path, name))
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
    return apps, families, areas


def index(
    db,
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, set[str]], dict[str, set[str]]]:
    """The release-notes pages of an index by application and family (see
    `_build_index`), read once per index file."""
    return store.per_index(_cache, db, _build_index)


def _families_documented_in(
    folder: str, families: dict[str, set[str]], areas: dict[str, set[str]]
) -> set[str]:
    """The families whose applications have their own docs in a product folder: most of the
    members whose product area is known. The folder is often not named like the family
    (governance-risk-compliance holds "Governance, Risk, and Compliance"; security-management
    holds "Security Operations")."""
    out = set()
    for family, members in families.items():
        known = [areas[a] for a in members if areas.get(a)]
        if known and sum(folder in area for area in known) * 2 > len(known):
            out.add(family)
    return out


def by_name(db, q: str, already: set[str]) -> list[NotesPage]:
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
    apps, families, areas = index(db)
    phrase = _phrase(q)
    if not phrase:
        return []
    folder, how = products.resolve(q, store.products(db))
    family_names = {phrase}
    if how in ("exact", "alias") and folder:
        family_names |= {_phrase(folder)} | _families_documented_in(folder, families, areas)
    members = {a for f in family_names for a in families.get(f, ())}

    def abbreviations(name: str) -> set[str]:
        return {_phrase(x) for x in _PARENS.findall(name)}

    names_one = phrase in apps or any(
        phrase in abbreviations(n) for pages in apps.values() for _, n in pages
    )
    words = {w for w in phrase.split() if len(w) > 1 and w not in _GENERIC_WORDS}
    has = {
        a: {
            w
            for w in words
            if any(n.startswith(w) for _, name in pages for n in _phrase(name).split())
        }
        for a, pages in apps.items()
    }
    if names_one and not members:
        named = {
            a
            for a, pages in apps.items()
            if f" {phrase} " in f" {a} " or any(phrase in abbreviations(n) for _, n in pages)
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
        (-len(has[a]), name, path)
        for a in members | named
        for path, name in apps[a]
        if f"{RELEASE}:{path}" not in already
    )
    return [
        NotesPage(id=make_id(RELEASE, path, ""), application=name)
        for _, name, path in found[:MORE_RELEASE_NOTES]
    ]
