"""The API reference as a table: every documented method, by class.

API reference pages are regular: an H2 `Class - method(signature)` per method (hyphen or
dash), a description, a parameter table (Name, Type, Description), a return table (Type,
Description) and a code example. Tables come as markdown or as HTML. Parsing them gives exact
answers that text search cannot: whether a method exists, its parameters, a class's methods.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from snow_docs_mcp import sections

API_PREFIX = "markdown/api-reference/"

_SIGNATURE = re.compile(r"^(?P<cls>.+?)\s+[-–—]\s+(?P<name>[$\w][\w$.]*)\s*\((?P<args>.*)\)\s*$")
_PROPERTY = re.compile(r"^(?P<cls>.+?)\s+[-–—]\s+(?P<name>[$\w][\w$.]*)\s*$")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_HTML_TABLE = re.compile(r"<table\b.*?</table>", re.DOTALL | re.IGNORECASE)
_HTML_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_HTML_CELL = re.compile(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_PIPE = re.compile(r"(?<!\\)\|")
_SEPARATOR = re.compile(r"^[\s|:-]+$")
_WS = re.compile(r"\s+")
_VARIANT = re.compile(r"^scoped\s+|\s*\(.*\)\s*$", re.IGNORECASE)

# The variables scripts usually hold these classes in.
VARIABLES = {"gs": "glidesystem", "g_form": "glideform", "g_user": "glideuser"}


@dataclass(frozen=True)
class Param:
    name: str
    type: str
    description: str


@dataclass
class Member:
    class_name: str  # as the docs write it: "GlideRecord", "Scoped GlideRecord"
    name: str
    kind: str  # "method" | "property"
    signature: str
    file_path: str
    heading_path: str  # the section's breadcrumb, as ids use it
    occurrence: int
    description: str = ""
    params: list[Param] = field(default_factory=list)
    returns: str = ""
    returns_description: str = ""
    example: str = ""


def _text(cell: str) -> str:
    cell = sections.unescape_markdown(sections.unlink(_TAG.sub(" ", cell)))
    return _WS.sub(" ", cell).strip()


def _tables(body: str) -> list[list[list[str]]]:
    """Every table in a section, as rows of cell texts (header row first)."""
    found: list[tuple[int, list[list[str]]]] = []
    for m in _HTML_TABLE.finditer(body):
        rows = [[_text(c) for c in _HTML_CELL.findall(r)] for r in _HTML_ROW.findall(m.group(0))]
        found.append((m.start(), [r for r in rows if r]))
    block: list[list[str]] = []
    start = pos = 0
    for line in [*_HTML_TABLE.sub(lambda m: "\n" * m.group(0).count("\n"), body).split("\n"), ""]:
        if line.lstrip().startswith("|"):
            if not block:
                start = pos
            if not _SEPARATOR.match(line):
                block.append([_text(c) for c in _PIPE.split(line.strip().strip("|"))])
        elif block:
            found.append((start, block))
            block = []
        pos += len(line) + 1
    return [rows for _, rows in sorted(found, key=lambda x: x[0])]


def _fill(member: Member, body: str) -> None:
    """Add what a (further) part of the member's section says."""
    if not member.description:
        cut = min(
            (i for i in (body.find("\n|"), body.find("<table"), body.find("```")) if i >= 0),
            default=len(body),
        )
        member.description = _text(body[:cut])
    for rows in _tables(body):
        header = [h.lower() for h in rows[0]] if rows else []
        if header == ["name", "type", "description"] and not member.params:
            member.params = [
                Param(*r[:3]) for r in rows[1:] if len(r) >= 3 and r[0] and r[0].lower() != "none"
            ]
        elif header == ["type", "description"] and not member.returns and len(rows) > 1:
            member.returns = rows[1][0]
            member.returns_description = rows[1][1] if len(rows[1]) > 1 else ""
    if not member.example:
        code = _FENCE.search(body)
        if code:
            member.example = code.group(1).rstrip()


def parse_page(file_path: str, text: str) -> list[Member]:
    """The methods and properties an API reference page documents, in page order."""
    members: list[Member] = []
    current: Member | None = None
    seen: dict[str, int] = {}
    for sec in sections.split_into_sections(sections.strip_front_matter(text)):
        crumb = " > ".join(sec.heading_path)
        seen[crumb] = seen.get(crumb, 0) + 1
        if len(sec.heading_path) > 2:  # a subheading inside a member's section
            if current is not None:
                _fill(current, sec.body)
            continue
        current = None
        if len(sec.heading_path) < 2:
            continue
        heading = sections.unescape_markdown(sec.heading_path[-1])
        m = _SIGNATURE.match(heading)
        prop = None if m else _PROPERTY.match(heading)
        if m:
            signature = f"{m.group('name')}({m.group('args').strip()})"
            current = Member(
                m.group("cls").strip(),
                m.group("name"),
                "method",
                signature,
                file_path,
                crumb,
                seen[crumb],
            )
        elif prop:
            current = Member(
                prop.group("cls").strip(),
                prop.group("name"),
                "property",
                prop.group("name"),
                file_path,
                crumb,
                seen[crumb],
            )
        if current is not None:
            _fill(current, sec.body)
            members.append(current)
    classes = {m.class_name for m in members if m.kind == "method"}
    return [m for m in members if m.kind == "method" or m.class_name in classes]


def _base(class_name: str) -> str:
    """'Scoped GlideRecord' and 'GlideForm (Next Experience)' -> 'gliderecord', 'glideform'."""
    name = class_name.strip()
    while True:
        shorter = _VARIANT.sub("", name).strip()
        if shorter == name:
            return name.lower()
        name = shorter


class ApiTable:
    def __init__(self, members: list[Member]):
        self.by_class: dict[
            str, dict[str, list[Member]]
        ] = {}  # base -> class as written -> members
        self.by_method: dict[str, list[Member]] = {}  # lowercase method name -> members
        self.display: dict[str, str] = {}  # base -> the class name without its variant
        for m in members:
            base = _base(m.class_name)
            self.by_class.setdefault(base, {}).setdefault(m.class_name, []).append(m)
            self.by_method.setdefault(m.name.lower(), []).append(m)
            plain = _VARIANT.sub("", m.class_name).strip()
            if base not in self.display or len(plain) < len(self.display[base]):
                self.display[base] = plain

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_method.values())

    def _class(self, name: str) -> tuple[str, dict[str, list[Member]]] | None:
        """(base, the variants a class name means): one variant when it names it exactly."""
        wanted = name.strip().lower()
        base = VARIABLES.get(wanted) or _base(wanted)
        variants = self.by_class.get(base)
        if not variants:
            return None
        # a plain name means every variant; "Scoped GlideRecord" means that one
        exact = {c: ms for c, ms in variants.items() if c.lower() == wanted and wanted != base}
        return base, exact or variants

    def find(self, name: str) -> tuple[str, object]:
        """("class", {class as written: members}), ("method", [members]) or
        ("not_found", [closest names])."""
        q = re.sub(r"\(.*\)\s*$", "", name.strip()).strip().strip(".")
        if not q:
            return "not_found", []
        whole = self._class(q)
        if whole:
            return "class", whole[1]
        cls_part, _, method = q.rpartition(".")
        if cls_part:
            hit = self._class(cls_part)
            if hit:
                base, variants = hit
                found = [
                    m for ms in variants.values() for m in ms if m.name.lower() == method.lower()
                ]
                if found:
                    return "method", found
                names = sorted({m.name for ms in variants.values() for m in ms})
                close = difflib.get_close_matches(method, names, n=3, cutoff=0.6)
                return "not_found", [f"{self.display[base]}.{c}" for c in close]
            # an unknown class: point at the classes that have the method, never answer with them
            owners = sorted(
                {self.display[_base(m.class_name)] for m in self.by_method.get(method.lower(), [])}
            )
            names = {m.name for m in self.by_method.get(method.lower(), [])}
            return "not_found", [f"{c}.{n}" for c in owners for n in sorted(names)][:5]
        found = self.by_method.get(q.lower(), [])
        if found:
            return "method", found
        bases = difflib.get_close_matches(_base(q), list(self.by_class), n=3, cutoff=0.75)
        methods = difflib.get_close_matches(q.lower(), list(self.by_method), n=3, cutoff=0.8)
        close = [self.display[b] for b in bases]
        close += sorted({m.name for k in methods for m in self.by_method[k]})
        return "not_found", close[:5]
