"""Markdown section splitting, used to cut one section out of a full docs page.

A section opens at every H2/H3 heading (H1 resets the breadcrumb). A search hit's
`heading_path` is the " > "-joined breadcrumb of the section it came from, so the same
walk that produced it at index time finds it again here.
"""

# Section walk copied (not imported) from the research spike's chunker, and
# extract_section from its server's read tool; unchanged apart from "\n" for os.linesep.

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


# Some pages write a heading on the same line as the end of a table: "</table>## New features".
_GLUED_RE = re.compile(r"^(</table>[ \t]*)(#{1,6}\s.*)$", re.DOTALL)


@dataclass
class Section:
    heading_path: list[str]
    body: str
    byte_offset: int
    # Its heading was written on the same line as a table's end. The index did not see such
    # headings: it filed the text under the section before, and nested later sections as if
    # the heading were not there. `index_path` is the breadcrumb the index gives the section
    # this text is in, which is what a passage's id carries; `heading_line` is the glued
    # heading as written, for when its text is read as part of that section.
    glued: bool = False
    heading_line: str = ""
    index_path: list[str] | None = None

    def __post_init__(self) -> None:
        if self.index_path is None:
            self.index_path = list(self.heading_path)


def split_into_sections(text: str) -> list[Section]:
    """Walk the markdown line by line, opening a new section at each H1, H2 and H3, also one
    written on the same line as a table's end."""
    lines = text.splitlines(keepends=True)
    heading_stack: list[str | None] = [None] * 6  # one slot per H1..H6 level
    index_stack: list[str | None] = [None] * 6  # the same, as the index walked it
    sections: list[Section] = []
    current_lines: list[str] = []
    current_offset = 0
    section_start_offset = 0
    glued = False  # the section being collected was opened by a glued heading
    opened_by = ""  # that heading, as written

    def _close() -> None:
        nonlocal current_lines
        if current_lines:
            sections.append(
                Section(
                    [h for h in heading_stack if h],
                    "".join(current_lines),
                    section_start_offset,
                    glued,
                    opened_by,
                    [h for h in index_stack if h],
                )
            )
            current_lines = []

    for line in lines:
        m = HEADING_RE.match(line)
        after_table = None
        if m is None and (found := _GLUED_RE.match(line)):
            heading = HEADING_RE.match(found.group(2))
            if heading and len(heading.group(1)) <= 3:
                m, after_table = heading, found
                # the table's end belongs to the section it closes; the heading opens the next
                current_lines.append(found.group(1).rstrip() + "\n")
        level = len(m.group(1)) if m else 0
        if m and 1 <= level <= 3:
            _close()
            for stack in (heading_stack,) if after_table else (heading_stack, index_stack):
                stack[level - 1] = m.group(2).strip()
                for deeper in range(level, 6):
                    stack[deeper] = None
            section_start_offset = current_offset + len(line)
            glued = after_table is not None
            opened_by = after_table.group(2) if after_table else ""
        else:
            current_lines.append(line)
        current_offset += len(line)

    _close()
    return sections


def _crumb(path: list[str] | None) -> str:
    return " > ".join(path or [])


def extract_section(text: str, heading_breadcrumb: str, occurrence: int = 1) -> str | None:
    """Text of the `occurrence`-th section whose breadcrumb is `heading_breadcrumb`,
    including its subsections. None when there is no such section.

    A breadcrumb from the index (a passage's id) returns everything the index filed under
    it, as it always has: the text after a heading glued to a table included. Such a glued
    section can also be read by its own breadcrumb, and then ends where the next heading at
    its level begins. Exact breadcrumb matches win; only when there are none does it fall
    back to the old "breadcrumb ends with" match (so a short id like "Remedy" still finds
    "X > Remedy").
    """
    sections = split_into_sections(text)
    target = heading_breadcrumb.strip()
    if not [p for p in target.split(">") if p.strip()]:
        return None

    # Sections the index saw come first, numbered as the index numbers them; a glued section
    # answers to its own breadcrumb only when no section the index saw has it.
    matches = [
        i
        for i, s in enumerate(sections)
        if not s.glued and target in (_crumb(s.index_path), _crumb(s.heading_path))
    ]
    if not matches:
        matches = [
            i for i, s in enumerate(sections) if s.glued and _crumb(s.heading_path) == target
        ]
    if not matches:
        matches = [i for i, s in enumerate(sections) if _crumb(s.heading_path).endswith(target)]
    if not 1 <= occurrence <= len(matches):
        return None
    i = matches[occurrence - 1]
    section = sections[i]
    collected = [section.body]
    for later in sections[i + 1 :]:
        if section.glued:
            depth = len(section.heading_path)
            inside = (
                len(later.heading_path) > depth
                and later.heading_path[:depth] == section.heading_path
            )
            if not inside:
                break
            collected.append(later.body)
            continue
        # as the index walked it: a glued heading is text of the section it is in
        path = later.index_path or []
        depth = len(section.index_path or [])
        if path[:depth] != section.index_path or not (len(path) > depth or later.glued):
            break
        collected.append((later.heading_line if later.glued else "") + later.body)
    return "".join(collected).strip() + "\n"


def occurrence_of(text: str, heading_breadcrumb: str, offset: int) -> int:
    """Which occurrence (1-based) of `heading_breadcrumb` contains character `offset`.

    Chunk offsets come from this same section walk at index time, so the section that
    contains a chunk is the last one starting at or before its offset. Returns 1 when the
    breadcrumb is not repeated or cannot be located.
    """
    target = heading_breadcrumb.strip()
    count, result = 0, 1
    for section in split_into_sections(text):
        if section.byte_offset > offset:
            break
        if section.glued:
            continue  # not a section to the index: the passage is still in the one before
        if _crumb(section.index_path) == target:
            count += 1
            result = count
        else:
            result = 1  # the containing section so far is not a match
    return result


def headings(text: str) -> list[str]:
    """Every distinct section breadcrumb in the page, in order."""
    seen: list[str] = []
    for section in split_into_sections(text):
        path = " > ".join(section.heading_path)
        if path and path not in seen:
            seen.append(path)
    return seen


def strip_front_matter(text: str) -> str:
    """Drop a leading YAML front-matter block (---\\n...\\n---)."""
    return _FRONT_MATTER_RE.sub("", text, count=1).lstrip("\n")


# A backslash before a markdown punctuation character (CommonMark "backslash escapes").
_MD_ESCAPE_RE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")


def unescape_markdown(value: str) -> str:
    r"""Drop markdown backslash escapes: 'c\_GlideRecordAPI.html' -> 'c_GlideRecordAPI.html'."""
    return _MD_ESCAPE_RE.sub(r"\1", value)


def name_pattern(name: str) -> re.Pattern:
    """A code name as a whole word; case matters when it has a capital (JavaScript's does)."""
    flags = 0 if any(c.isupper() for c in name) else re.IGNORECASE
    return re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])", flags)


def plain_value(raw: str) -> str:
    """A front-matter value as text: surrounding whitespace and one matching pair of quotes
    removed (only a pair: "'Crawl' stage reports" keeps its quotes), escapes undone."""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return unescape_markdown(v)


def front_matter_value(text: str, key: str) -> str:
    r"""A top-level `key:` value from the front matter, or ''.

    The docs' front matter is written by a markdown converter, so values carry markdown
    escapes (canonical_url '.../c\_GlideRecordAPI.html' returns HTTP 400; title
    'GlideForm \(g\_form\)'). Values are returned unescaped."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return ""
    prefix = f"{key}:"
    for line in m.group(0).splitlines():
        if line.startswith(prefix):
            return plain_value(line[len(prefix) :])
    return ""


# Site release folders: www.servicenow.com/docs/r/<release>/<product>/<page>.html.
_SITE = "https://www.servicenow.com/docs/r/"
_SITE_RELEASES = frozenset(
    {"australia", "brazil", "zurich", "yokohama", "xanadu", "washingtondc", "vancouver"}
)
# Release-notes copies of older releases' notes shipped in the brazil docs with australia's
# addresses minus the release folder: those pages only exist under /r/australia/.
_AU_DELTA = re.compile(r"delta-(xanadu|yokohama|zurich)-australia")


def site_url(page: str, release: str) -> str:
    """The page's www.servicenow.com address, or '' when its front matter names none.

    The newest release's pages carry addresses without a release folder (/docs/r/<product>/
    ...); ServiceNow adds the folder once a newer release ships. Pinning the release keeps a
    brazil link on the brazil page afterwards (today /r/brazil/... redirects to the same
    page). `release` is the index's release, used when the page doesn't name its own."""
    url = front_matter_value(page, "canonical_url")
    if not url.startswith(_SITE):
        return url
    first = url[len(_SITE) :].split("/", 1)[0]
    if first in _SITE_RELEASES:
        return url
    page_release = front_matter_value(page, "release") or release
    if page_release == "brazil":
        return f"{_SITE}brazil/{url[len(_SITE) :]}"
    if page_release == "australia" and _AU_DELTA.fullmatch(first):
        return f"{_SITE}australia/{url[len(_SITE) :]}"
    return url


_MD_LINK = re.compile(r"\[([^\[\]\n]*)\]\(([^()\s]*(?:\([^()\s]*\)[^()\s]*)*)\)")


def unlink(text: str) -> str:
    """Markdown links reduced to their text (search snippets: shorter, and no dead links)."""
    return _MD_LINK.sub(r"\1", text)


# Links between docs pages point at the upstream repo's raw markdown, and most are dead: the
# release folder is repeated ('.../markdown/australia/<product>/...'), the page moved to a
# subfolder, or it isn't in this release at all.
_RAW_URL = re.compile(
    r"https://raw\.githubusercontent\.com/ServiceNow/ServiceNowDocs/(?P<branch>[\w.-]+)/markdown"
    r"(?:/(?:(?:australia|brazil)/)?(?P<path>[^\s)\]\[(#]+?\.md))?(?P<frag>#[^\s)\]\[(]*)?"
)
_RAW_LINK = re.compile(
    r"\[(?P<text>(?:\\.|[^\[\]\n\\])*)\]\((?P<url>https://raw\.githubusercontent\.com/ServiceNow/"
    r"ServiceNowDocs/[^)\s]*)\)"
)


def rewrite_doc_links(text: str, resolve) -> str:
    """Point links to other docs pages at those pages' real addresses.

    `resolve('markdown/<path>.md')` returns the page's address, or '' when the index has no
    such page; then a link keeps only its text, and a bare address becomes the page's name.
    Every other link is left alone."""
    if "raw.githubusercontent.com/ServiceNow/ServiceNowDocs/" not in text:
        return text

    def target(m: re.Match) -> str:
        path = m.group("path")
        return resolve("markdown/" + unescape_markdown(unquote(path))) if path else ""

    def bare(m: re.Match) -> str:
        url = target(m)
        if url:
            return url
        path = m.group("path")
        return path.rsplit("/", 1)[-1][: -len(".md")] if path else ""

    def link(m: re.Match) -> str:
        label = _RAW_URL.sub(bare, m.group("text"))
        um = _RAW_URL.fullmatch(m.group("url"))
        url = target(um) if um else ""
        return f"[{label}]({url})" if url else label

    return _RAW_URL.sub(bare, _RAW_LINK.sub(link, text))


# Some links in the docs repeat the release folder: '.../ServiceNowDocs/australia/markdown/
# australia/api-reference/...' (HTTP 404). The repo has no 'australia' or 'brazil' product
# folder, so the repeated segment is always wrong.
_DOUBLED_RELEASE_RE = re.compile(
    r"(ServiceNowDocs/[\w.-]+/markdown/)(?:australia|brazil)/", re.IGNORECASE
)


def fix_links(text: str) -> str:
    """Repair the known-broken link pattern in docs text (see _DOUBLED_RELEASE_RE)."""
    return _DOUBLED_RELEASE_RE.sub(r"\1", text)


def front_matter_title(text: str) -> str:
    return front_matter_value(text, "title")


def count_sections(text: str, heading_breadcrumb: str) -> int:
    """How many sections have exactly this breadcrumb."""
    target = heading_breadcrumb.strip()
    walked = split_into_sections(text)
    seen = sum(
        1
        for s in walked
        if not s.glued and target in (_crumb(s.index_path), _crumb(s.heading_path))
    )
    return seen or sum(1 for s in walked if s.glued and _crumb(s.heading_path) == target)
