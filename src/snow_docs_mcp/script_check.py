"""Check the methods a ServiceNow script calls against the API table.

Finds calls on receivers it can name a class for: variables assigned `new GlideRecord(...)`
and the like, the variables the platform provides (`gs`, `current`, `g_form`, ...), and
classes called directly. Each such `receiver.method(` is looked up; a method the API
reference does not document is reported with the closest documented names. Everything else
(fields, plain JavaScript, objects of unknown type) is left alone, so a report is rare and
worth reading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from snow_docs_mcp.api_table import ApiTable

# Comments, strings and template literals: not code. Blanked out, keeping the line breaks.
_NOT_CODE = re.compile(
    r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`""",
    re.DOTALL,
)
_NEW = re.compile(r"(?<![\w$.])([$A-Za-z_][\w$]*)\s*=\s*new\s+([$A-Za-z_][\w$.]*)\s*\(")
_CALL = re.compile(r"(?<![\w$.])([$A-Za-z_][\w$]*)\s*\.\s*([$A-Za-z_][\w$]*)\s*\(")


@dataclass(frozen=True)
class Finding:
    call: str  # "GlideRecord.addEncodedQuerry"
    line: int  # 1-based, of the first use
    suggestions: list[str]


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def check(code: str, table: ApiTable, limit: int = 10) -> list[Finding]:
    """Calls to methods the API reference does not document, in order of first use."""
    code = _NOT_CODE.sub(_blank, code)
    holds: dict[str, str] = {}  # variable -> the class it was assigned
    for m in _NEW.finditer(code):
        cls = m.group(2).rsplit(".", 1)[-1]  # sn_ws.RESTMessageV2 -> RESTMessageV2
        if table.member(cls, "") is not None:
            holds[m.group(1)] = cls
    found: dict[str, Finding] = {}
    for m in _CALL.finditer(code):
        receiver, method = m.group(1), m.group(2)
        answer = table.member(holds.get(receiver, receiver), method)
        if answer is None:  # not a class, nor a variable we know the class of
            continue
        display, documented, close = answer
        call = f"{display}.{method}"
        if not documented and call not in found:
            found[call] = Finding(call, code.count("\n", 0, m.start()) + 1, close)
            if len(found) >= limit:
                break
    return list(found.values())
