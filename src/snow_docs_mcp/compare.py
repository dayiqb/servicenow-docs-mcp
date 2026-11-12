"""What changed in one docs page between two releases.

The two releases' copies of a page almost always differ in ways that are not documentation
changes: the front matter names the release, links are rendered differently (often with the
link text missing in one release), and generated HTML tables get new ids. Those are removed
before comparing, and a section counts as changed only by its remaining words.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass

from snow_docs_mcp import sections

# A changed section with fewer changed words than this is a small rewording: counted, not
# listed. Most of them are link text that one release renders and the other drops.
MINOR_WORDS = 8
# Word-by-word comparison is exact up to this many (words x words) after the shared start and
# end are set aside; above it, words are counted instead.
EXACT_CELLS = 250_000

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


def _first_difference(wa: list[str], wb: list[str]) -> int:
    n = min(len(wa), len(wb))
    for i in range(n):
        if wa[i] != wb[i]:
            return i
    return n


def _changed_words(a: str, b: str) -> int:
    """How many words differ between two texts. The shared start and end are set aside
    first; what is left is compared exactly when it is small, and otherwise counted as the
    words one side has and the other lacks (difflib takes minutes on long repetitive text
    such as tables and JSON schemas)."""
    wa, wb = a.split(), b.split()
    start = _first_difference(wa, wb)
    wa, wb = wa[start:], wb[start:]
    end = _first_difference(wa[::-1], wb[::-1])
    if end:
        wa, wb = wa[:-end], wb[:-end]
    if len(wa) * len(wb) <= EXACT_CELLS:
        ops = difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes()
        return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in ops if tag != "equal")
    ca, cb = Counter(wa), Counter(wb)
    return max(sum((ca - cb).values()), sum((cb - ca).values()))


def _section_change(a: str, b: str, link_text: bool) -> int:
    """Changed words between two versions of a section body (0 = the same)."""
    ca, cb = comparable(a, link_text=link_text), comparable(b, link_text=link_text)
    return 0 if ca == cb else max(1, _changed_words(ca, cb))


def _excerpt(words: list[str], start: int, max_chars: int) -> str:
    start = max(0, start - 5)
    text = " ".join(words[start:])
    cut = len(text) > max_chars
    if cut:
        text = text[:max_chars].rsplit(" ", 1)[0]
    return ("…" if start else "") + text + ("…" if cut else "")


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
