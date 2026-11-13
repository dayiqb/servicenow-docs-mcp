"""Check the methods a ServiceNow script calls, and the tables it opens, against the docs.

Finds calls on receivers it can name a class for, and looks each `receiver.method(` up in the
API table. A receiver's class is known when:

- it is assigned `new GlideRecord(...)` or another documented class;
- it is assigned the result of a documented method whose return type is a class
  (`var user = gs.getUser()`), or the call is chained onto one (`gs.getUser().getName()`);
- a JSDoc `@param {GlideRecord} rec` or a TypeScript `rec: GlideRecord` says so;
- it is a variable the platform provides (`gs`, `current`, `g_form`, ...) or a class called
  directly;
- it has one of the usual names (`gr`, `now_GR`, `grIncident`, `gdt`) and the code does
  not assign it anything else.

A method the API reference does not document is reported with the closest documented names.
Table names in `new GlideRecord('name')` are checked against the names the docs mention.
Everything else (fields, plain JavaScript, objects of unknown type) is left alone, so a
report is rare and worth reading.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from snow_docs_mcp.api_table import ApiTable

# Comments, strings and template literals: not code. Blanked out, keeping the line breaks.
_NOT_CODE = re.compile(
    r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`""",
    re.DOTALL,
)
_NAME = r"[$A-Za-z_][\w$]*"
_ASSIGN = re.compile(
    rf"(?<![\w$.])({_NAME})\s*=(?!=)\s*"
    rf"(?:new\s+([$A-Za-z_][\w$.]*)\s*\(|({_NAME})\s*\.\s*({_NAME})\s*\()?"
)
_CALL = re.compile(rf"(?<![\w$.])({_NAME})\s*\.\s*({_NAME})\s*\(")
_CHAIN = re.compile(rf"(?<![\w$.])({_NAME})\s*\.\s*({_NAME})\s*\([^()]*\)\s*\.\s*({_NAME})\s*\(")
_JSDOC = re.compile(rf"@(?:param|type)\s*\{{\s*([\w$.]+)\s*\}}\s*\[?({_NAME})?")
_TS = re.compile(rf"(?<![\w$.])({_NAME})\s*\??:\s*([A-Z][\w$]*)\b(?=\s*[,)=;])")
_OPEN_TABLE = re.compile(
    r"""\bnew\s+(?:GlideRecord|GlideRecordSecure|GlideAggregate|GlideQuery)\s*\(\s*(['"])([A-Za-z0-9_]+)\1\s*[,)]"""
)
_CUSTOM_TABLE = re.compile(r"^(?:u_|x_)")  # customer tables and scoped apps: not in the docs
# The names scripts usually give these classes' objects.
_USUAL = (
    (re.compile(r"^(?:gr|now_GR|gr[A-Z_]\w*)$"), "GlideRecord"),
    (re.compile(r"^(?:gdt|gdt[A-Z_]\w*)$"), "GlideDateTime"),
)


@dataclass(frozen=True)
class Finding:
    call: str  # "GlideRecord.addEncodedQuerry", or a table name
    line: int  # 1-based, of the first use
    suggestions: list[str]
    kind: str = "method"  # "method" | "table"


@dataclass
class Review:
    findings: list[Finding] = field(default_factory=list)
    checked_calls: int = 0  # calls on receivers whose class is known
    checked_tables: int = 0


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def review(
    source: str, table: ApiTable, tables: frozenset[str] | None = None, limit: int = 10
) -> Review:
    """What the script calls that the API reference does not document (and, with `tables`,
    the tables it opens that the docs never mention), in order of first use."""
    code = _NOT_CODE.sub(_blank, source)
    out = Review()
    holds: dict[str, str] = {}  # variable -> its class
    untyped: set[str] = set()  # variables assigned something we cannot type

    def known(cls: str) -> bool:
        return table.member(cls, "") is not None

    for m in _JSDOC.finditer(source):
        cls = m.group(1).rsplit(".", 1)[-1]
        if m.group(2) and known(cls):
            holds[m.group(2)] = cls
    for m in _TS.finditer(code):
        if known(m.group(2)):
            holds[m.group(1)] = m.group(2)
    for m in _ASSIGN.finditer(code):
        name, made, receiver, method = m.groups()
        cls = ""
        if made:
            cls = made.rsplit(".", 1)[-1]  # sn_ws.RESTMessageV2 -> RESTMessageV2
        elif receiver:
            cls = table.returns(holds.get(receiver, receiver), method)
        if cls and known(cls):
            holds[name] = cls
            untyped.discard(name)
        elif name not in holds:
            untyped.add(name)

    def class_of(receiver: str) -> str:
        if receiver in holds:
            return holds[receiver]
        if receiver not in untyped:
            for pattern, cls in _USUAL:
                if pattern.match(receiver) and known(cls):
                    return cls
        return receiver

    hits: list[tuple[int, Finding]] = []

    def look_up(cls: str, method: str, at: int) -> None:
        answer = table.member(cls, method)
        if answer is None:  # not a class, nor a variable we know the class of
            return
        out.checked_calls += 1
        display, documented, close = answer
        if not documented:
            line = code.count("\n", 0, at) + 1
            hits.append((at, Finding(f"{display}.{method}", line, close)))

    for m in _CALL.finditer(code):
        look_up(class_of(m.group(1)), m.group(2), m.start())
    for m in _CHAIN.finditer(code):
        returned = table.returns(class_of(m.group(1)), m.group(2))
        if returned:
            look_up(returned, m.group(3), m.start(3))
    if tables is not None:
        for m in _OPEN_TABLE.finditer(source):
            name = m.group(2)
            if code[m.start() : m.start() + 3] != "new" or _CUSTOM_TABLE.match(name):
                continue
            out.checked_tables += 1
            if name.lower() not in tables:
                close = difflib.get_close_matches(name.lower(), tables, n=3, cutoff=0.8)
                line = source.count("\n", 0, m.start()) + 1
                hits.append((m.start(), Finding(name, line, close, "table")))
    seen: set[tuple[str, str]] = set()
    for _, finding in sorted(hits, key=lambda h: h[0]):
        if (finding.kind, finding.call) not in seen and len(out.findings) < limit:
            seen.add((finding.kind, finding.call))
            out.findings.append(finding)
    return out


def check(
    source: str, table: ApiTable, tables: frozenset[str] | None = None, limit: int = 10
) -> list[Finding]:
    return review(source, table, tables, limit).findings
