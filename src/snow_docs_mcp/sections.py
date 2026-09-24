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

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


@dataclass
class Section:
    heading_path: list[str]
    body: str
    byte_offset: int


def split_into_sections(text: str) -> list[Section]:
    """Walk the markdown line by line, opening a new section at each H2/H3."""
    lines = text.splitlines(keepends=True)
    heading_stack: list[str | None] = [None] * 6  # one slot per H1..H6 level
    sections: list[Section] = []
    current_lines: list[str] = []
    current_offset = 0
    section_start_offset = 0

    def _current_path() -> list[str]:
        return [h for h in heading_stack if h]

    for line in lines:
        m = HEADING_RE.match(line)
        if m and 2 <= len(m.group(1)) <= 3:
            if current_lines:
                sections.append(
                    Section(_current_path(), "".join(current_lines), section_start_offset)
                )
                current_lines = []
            level = len(m.group(1))
            heading_stack[level - 1] = m.group(2).strip()
            for deeper in range(level, 6):
                heading_stack[deeper] = None
            section_start_offset = current_offset + len(line)
        elif m and len(m.group(1)) == 1:
            if current_lines:
                sections.append(
                    Section(_current_path(), "".join(current_lines), section_start_offset)
                )
                current_lines = []
            heading_stack[0] = m.group(2).strip()
            for deeper in range(1, 6):
                heading_stack[deeper] = None
            section_start_offset = current_offset + len(line)
        else:
            current_lines.append(line)
        current_offset += len(line)

    if current_lines:
        sections.append(Section(_current_path(), "".join(current_lines), section_start_offset))
    return sections


def extract_section(text: str, heading_breadcrumb: str, occurrence: int = 1) -> str | None:
    """Text of the `occurrence`-th section whose breadcrumb is `heading_breadcrumb`,
    including its subsections. None when there is no such section.

    Exact breadcrumb matches win; only when there are none does it fall back to the old
    "breadcrumb ends with" match (so a short id like "Remedy" still finds "X > Remedy").
    """
    sections = split_into_sections(text)
    target = heading_breadcrumb.strip()
    if not [p for p in target.split(">") if p.strip()]:
        return None

    paths = [" > ".join(s.heading_path) for s in sections]
    matches = [i for i, p in enumerate(paths) if p == target]
    if not matches:
        matches = [i for i, p in enumerate(paths) if p.endswith(target)]
    if not 1 <= occurrence <= len(matches):
        return None
    i = matches[occurrence - 1]
    section = sections[i]
    collected = [section.body]
    depth = len(section.heading_path)
    for later in sections[i + 1 :]:
        if len(later.heading_path) > depth and later.heading_path[:depth] == section.heading_path:
            collected.append(later.body)
        else:
            break
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
        if " > ".join(section.heading_path) == target:
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


def front_matter_value(text: str, key: str) -> str:
    """A top-level `key:` value from the front matter, or ''."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return ""
    prefix = f"{key}:"
    for line in m.group(0).splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip("\"'")
    return ""


def front_matter_title(text: str) -> str:
    return front_matter_value(text, "title")


def count_sections(text: str, heading_breadcrumb: str) -> int:
    """How many sections have exactly this breadcrumb."""
    target = heading_breadcrumb.strip()
    return sum(1 for s in split_into_sections(text) if " > ".join(s.heading_path) == target)
