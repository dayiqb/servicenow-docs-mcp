"""What changed in one docs page between two releases.

The two releases' copies of a page almost always differ in ways that are not documentation
changes: the front matter names the release, links are rendered differently (often with the
link text missing in one release), and generated HTML tables get new ids. Those are removed
before comparing, and a section counts as changed only by its remaining words.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from snow_docs_mcp import sections

# A changed section with fewer changed words than this is a small rewording: counted, not
# listed. Most of them are link text that one release renders and the other drops.
MINOR_WORDS = 8
# Above this many words in a section, compare lines instead of words (API reference pages).
LINE_MODE_WORDS = 5000

_LINK = re.compile(r"!?\[[^\[\]\n]*\]\([^()\s]*(?:\([^()\s]*\)[^()\s]*)*\)")
_URL = re.compile(r"https?://\S+")
_GENERATED_ATTR = re.compile(r"""\s+(?:id|headers)=(?:"[^"]*"|'[^']*')""")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class SectionChange:
    heading_path: str  # breadcrumb joined with " > ", as ids use it
    occurrence: int  # 1-based, among sections with the same breadcrumb
    change: str  # "added" | "removed" | "changed"
    changed_words: int
    before: str  # excerpt; "" when the section is new
    after: str  # excerpt; "" when the section is gone


@dataclass(frozen=True)
class PageDiff:
    sections: list[SectionChange]
    minor: int  # changed sections below the threshold


def comparable(text: str, *, link_text: bool = False) -> str:
    """Text reduced to what counts as documentation: no front matter, links, URLs, generated
    table attributes or layout whitespace. `link_text` keeps each link's text.

    The releases render links two ways: one drops a link's text where the other has it, or
    one has plain text where the other has a link. Dropping links hides the first, keeping
    their text hides the second, so a section counts as changed only when it differs both ways.
    """
    text = sections.strip_front_matter(text)
    text = sections.unlink(text) if link_text else _LINK.sub("", text)
    text = _URL.sub("", text)
    text = _GENERATED_ATTR.sub("", text)
    return _WS.sub(" ", text).strip()


def _display(text: str) -> str:
    return _WS.sub(" ", sections.unlink(text)).strip()


def _keyed(page: str) -> dict[tuple[str, int], str]:
    """(breadcrumb, occurrence) -> section body, in page order."""
    out: dict[tuple[str, int], str] = {}
    seen: dict[str, int] = {}
    for s in sections.split_into_sections(sections.strip_front_matter(page)):
        crumb = " > ".join(s.heading_path)
        seen[crumb] = seen.get(crumb, 0) + 1
        out[(crumb, seen[crumb])] = s.body
    return out


def _changed_words(a: str, b: str) -> int:
    wa, wb = a.split(), b.split()
    if max(len(wa), len(wb)) > LINE_MODE_WORDS:
        return _changed_words_by_line(a, b)
    ops = difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes()
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in ops if tag != "equal")


def _changed_words_by_line(a: str, b: str) -> int:
    la, lb = a.splitlines(), b.splitlines()
    ops = difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes()
    total = 0
    for tag, i1, i2, j1, j2 in ops:
        if tag != "equal":
            total += max(
                sum(len(x.split()) for x in la[i1:i2]), sum(len(x.split()) for x in lb[j1:j2])
            )
    return total


def _line_comparable(body: str, link_text: bool) -> str:
    """Like `comparable`, but keeping line breaks (for the by-line comparison)."""
    lines = (comparable(line, link_text=link_text) for line in body.splitlines())
    return "\n".join(c for c in lines if c)


def _section_change(a: str, b: str, link_text: bool) -> int:
    """Changed words between two versions of a section body (0 = the same)."""
    ca, cb = comparable(a, link_text=link_text), comparable(b, link_text=link_text)
    if ca == cb:
        return 0
    if max(len(ca.split()), len(cb.split())) > LINE_MODE_WORDS:
        return _changed_words_by_line(
            _line_comparable(a, link_text), _line_comparable(b, link_text)
        )
    return _changed_words(ca, cb)


def _excerpt(words: list[str], start: int, max_chars: int) -> str:
    start = max(0, start - 5)
    text = " ".join(words[start:])
    cut = len(text) > max_chars
    if cut:
        text = text[:max_chars].rsplit(" ", 1)[0]
    return ("…" if start else "") + text + ("…" if cut else "")


def _first_difference(wa: list[str], wb: list[str]) -> int:
    n = min(len(wa), len(wb))
    for i in range(n):
        if wa[i] != wb[i]:
            return i
    return n


def compare_pages(
    before: str, after: str, *, minor_words: int = MINOR_WORDS, excerpt_chars: int = 300
) -> PageDiff:
    """Sections added, removed or reworded between two versions of a page: those of `after`
    in page order, then the removed ones."""
    old, new = _keyed(before), _keyed(after)
    listed: list[SectionChange] = []
    minor = 0
    for key, body in new.items():
        crumb, occ = key
        if key not in old:
            words = comparable(body).split()
            if words:
                shown = _excerpt(_display(body).split(), 0, excerpt_chars)
                listed.append(SectionChange(crumb, occ, "added", len(words), "", shown))
            continue
        n = min(_section_change(old[key], body, lt) for lt in (False, True))
        if n == 0:
            continue
        if n < minor_words:
            minor += 1
            continue
        wa, wb = _display(old[key]).split(), _display(body).split()
        at = _first_difference(wa, wb)
        listed.append(
            SectionChange(
                crumb,
                occ,
                "changed",
                n,
                _excerpt(wa, at, excerpt_chars),
                _excerpt(wb, at, excerpt_chars),
            )
        )
    for key, body in old.items():
        if key not in new:
            words = comparable(body).split()
            if words:
                shown = _excerpt(_display(body).split(), 0, excerpt_chars)
                listed.append(SectionChange(key[0], key[1], "removed", len(words), shown, ""))
    return PageDiff(listed, minor)
