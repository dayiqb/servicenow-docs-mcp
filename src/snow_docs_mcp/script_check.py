"""Check the methods a ServiceNow script calls, and the tables it opens, against the docs.

Finds calls on receivers it can name a class for, and looks each `receiver.method(` up in the
API table. A receiver's class is known when:

- it is assigned `new GlideRecord(...)` or another documented class;
- it is assigned the result of a documented method whose return type is a class
  (`var user = gs.getUser()`), or the call is chained onto one (`gs.getUser().getName()`,
  `new GlideRecord('x').query()`);
- a JSDoc `@param {GlideRecord} rec` above its function, a `@type` above its declaration or a
  TypeScript `rec: GlideRecord` says so;
- it is a variable the platform provides (`gs`, `current`, `g_form`, ...) or a class called
  directly, and the script does not declare that name itself;
- it has one of the usual names (`gr`, `now_GR`, `grIncident`, `gdt`) and the code does
  not assign it anything else.

A variable has its class per function, at the place it is used: the same name may hold a
GlideRecord in one function and a GlideAggregate in the next, or be given another class
halfway. A name the script declares (`var logger = ...`, a parameter, an import) is the
script's own: it is never taken for a documented class of the same name. The one exception
is a function that takes its arguments as one object, `function handler({api, helpers})`, as
UI Builder client scripts do: those are handed in by name.

A method the API reference does not document is reported with the closest documented names.
Table names in `new GlideRecord('name')` are checked against the names the docs mention.
Everything else (fields, plain JavaScript, objects of unknown type) is left alone, so a
report is rare and worth reading.
"""

from __future__ import annotations

import bisect
import difflib
import re
from dataclasses import dataclass, field

from snow_docs_mcp.api_table import VARIABLES, ApiTable

_NAME = r"[$A-Za-z_][\w$]*"
_ASSIGN = re.compile(rf"(?<![\w$.])({_NAME})\s*=(?![=>])")
_CALL = re.compile(rf"(?<![\w$.])({_NAME})\s*\.\s*({_NAME})\s*\(")
_DEEP = re.compile(rf"(?<![\w$.])({_NAME})((?:\s*\.\s*{_NAME}){{2,}})\s*\(")
_NEXT_CALL = re.compile(rf"\s*\.\s*({_NAME})\s*\(")
_NEW = re.compile(r"\bnew\s+([$A-Za-z_][\w$.]*)\s*\(")
_VALUE_NEW = re.compile(r"\s*new\s+([$A-Za-z_][\w$.]*)\s*\(")
_VALUE_CALL = re.compile(rf"\s*({_NAME})\s*\.\s*({_NAME})\s*\(")
_NAMESPACE = re.compile(r"^(?:sn_\w+|global)$")
_FUNCTION = re.compile(rf"\bfunction\b\s*\*?\s*({_NAME})?\s*(?:<[^<>()]*>\s*)?\(")
_METHOD = re.compile(rf"(?<![\w$.])({_NAME})\s*(?:<[^<>()]*>\s*)?\(")
_RETURNS = r"(?::\s*[\w$.<>\[\]|][\w$.<>\[\]|, ]*?)?"  # a TypeScript return type
_BODY = re.compile(rf"\s*{_RETURNS}\s*\{{")
_ARROW_PARENS = re.compile(rf"\)\s*{_RETURNS}\s*$")
_NAME_AT = re.compile(_NAME)
_EQUALS = re.compile(r"\s*=(?![=>])")
_ARROW_NAME = re.compile(rf"({_NAME})\s*$")
_DECLARE = re.compile(r"(?<![\w$.])(var|let|const)\b")
_DECLARED = re.compile(
    rf"(?<![\w$.])(?:var|let|const|function\s*\*?|class|interface|type|enum)\s+({_NAME})"
)
_IMPORT = re.compile(r"(?<![\w$.])import\b\s*(?:type\b\s*)?([^;'\"`()]*?)\bfrom\b")
_TYPE = r"([$A-Za-z_][\w$.]*)(?:\s*\|\s*(?:null|undefined))*"
_PARAM = re.compile(
    rf"\s*(?:\.\.\.)?\s*(?:(?:public|private|protected|readonly|override)\s+)*({_NAME})"
    rf"\s*\??\s*(?::\s*{_TYPE}\s*(?==|$))?"
)
_ANNOTATION = re.compile(rf"\s*:\s*{_TYPE}(?=\s*(?:[=;,\n]|$))")
_JSDOC = re.compile(r"/\*\*.*?\*/", re.DOTALL)
_JSDOC_PARAM = re.compile(rf"@param\s*\{{\s*([\w$.]+)\s*\}}\s*\[?\s*({_NAME})")
_JSDOC_TYPE = re.compile(r"@type\s*\{\s*([\w$.]+)\s*\}")
_JSDOC_NAMES = re.compile(rf"@(?:typedef\s*(?:\{{[^}}]*\}})?|callback)\s*({_NAME})")
_AFTER_JSDOC = re.compile(rf"\s*(?:export\s+)?(?:var|let|const)\s+({_NAME})")
_OPEN_TABLE = re.compile(
    r"""\bnew\s+(?:GlideRecord|GlideRecordSecure|GlideAggregate|GlideQuery)\s*\(\s*(['"])([A-Za-z0-9_]+)\1\s*[,)]"""
)
_CUSTOM_TABLE = re.compile(r"^(?:u_|x_)")  # customer tables and scoped apps: not in the docs
# The names scripts usually give these classes' objects.
_USUAL = (
    (re.compile(r"^(?:gr|now_GR|gr[A-Z_]\w*)$"), "GlideRecord"),
    (re.compile(r"^(?:gdt|gdt[A-Z_]\w*)$"), "GlideDateTime"),
)
# A `/` after one of these starts a regular expression; after anything else it divides.
_REGEX_AFTER = frozenset("(,=:[!&|?{};+-*%~^")
_REGEX_AFTER_WORDS = frozenset(
    [
        "return",
        "typeof",
        "case",
        "in",
        "of",
        "delete",
        "void",
        "throw",
        "new",
        "else",
        "do",
        "instanceof",
        "yield",
        "await",
    ]
)
# A line that ends, or a next line that starts, with one of these is not finished.
_GOES_ON = frozenset("=+-*/%&|?:(<[{,.")
# `name(...) {` after one of these is a statement, not a method being defined.
_NOT_A_METHOD = frozenset(
    ["if", "for", "while", "switch", "with", "function", "return", "typeof", "await"]
)
# What every JavaScript object has: never a class's own, so never in its documentation.
_OBJECT_METHODS = frozenset(
    [
        "toString",
        "toLocaleString",
        "valueOf",
        "hasOwnProperty",
        "isPrototypeOf",
        "propertyIsEnumerable",
    ]
)
# JavaScript's and the browser's own types: a type annotation with one of these names means
# that type, not a ServiceNow class that happens to share the name.
_JS_TYPES = frozenset(
    [
        "Array",
        "Audio",
        "Blob",
        "Boolean",
        "Date",
        "Document",
        "Element",
        "Error",
        "Event",
        "File",
        "FormData",
        "Function",
        "Headers",
        "History",
        "Image",
        "Location",
        "Map",
        "Math",
        "Navigator",
        "Node",
        "Notification",
        "Number",
        "Object",
        "Option",
        "Promise",
        "Proxy",
        "Range",
        "Reflect",
        "RegExp",
        "Request",
        "Response",
        "Selection",
        "Set",
        "Storage",
        "String",
        "Symbol",
        "Text",
        "URL",
        "Window",
        "Worker",
    ]
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


@dataclass
class _Var:
    """A name the script declares, and what it holds from where."""

    kind: str  # "var" | "param" | "object-param" | "name" (a function, class or import) | "global"
    cls: str = ""  # the class a type annotation gives it
    at: list[int] = field(default_factory=list)  # where it is given a value, in order
    holds: list[str] = field(default_factory=list)  # the class of each value, "" when unknown


@dataclass
class _Scope:
    """A function's body (the whole script for the outermost one)."""

    start: int
    end: int
    block: bool = False  # a catch block: `var` inside it belongs to the function around it
    parent: _Scope | None = None
    names: dict[str, _Var] = field(default_factory=dict)


@dataclass
class _Function:
    header: int  # where its definition starts
    scope: _Scope
    params: tuple[int, int] | None  # the text between its parentheses, or None for `x => ...`
    single: str = ""  # the parameter of `x => ...`


def _code(source: str) -> str:
    """The script with everything that is not code blanked out, every character in its place:
    comments, strings, regular expressions and the text of template literals. What a
    template holds in `${...}` is code and stays."""
    out = list(source)
    n = len(source)
    open_braces: list[int] = []  # for each `${` we are inside: the braces open within it
    last = ""  # the last piece of code: one character, or a whole word
    i = 0

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    def template(start: int) -> tuple[int, str]:
        """Blank a template's text from `start`; (where code goes on, what came last)."""
        k = start
        while k < n:
            ch = source[k]
            if ch == "\\":
                k += 2
            elif ch == "`":
                blank(start, k + 1)
                return k + 1, '"'
            elif ch == "$" and source.startswith("${", k):
                blank(start, k + 2)
                open_braces.append(0)
                return k + 2, "("
            else:
                k += 1
        blank(start, n)
        return n, '"'

    def regex_end(start: int) -> int:
        """Where the regular expression starting at `start` ends; 0 when it is not one."""
        k, in_class = start + 1, False
        while k < n and source[k] != "\n":
            ch = source[k]
            if ch == "\\":
                k += 2
                continue
            if ch == "[":
                in_class = True
            elif ch == "]":
                in_class = False
            elif ch == "/" and not in_class:
                k += 1
                while k < n and source[k].isalpha():
                    k += 1
                return k
            k += 1
        return 0

    while i < n:
        c = source[i]
        if c == "/" and source.startswith("//", i):
            end = source.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif c == "/" and source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif c in "\"'":
            end = i + 1
            while end < n and source[end] != c and source[end] != "\n":
                end += 2 if source[end] == "\\" else 1
            end = min(end + 1, n) if end < n and source[end] == c else min(end, n)
            blank(i, end)
            i, last = end, '"'
        elif c == "`":
            out[i] = " "
            i, last = template(i + 1)
        elif (
            c == "/"
            and (not last or last in _REGEX_AFTER or last in _REGEX_AFTER_WORDS)
            and (end := regex_end(i))
        ):
            blank(i, end)
            i, last = end, '"'
        elif c == "}" and open_braces and open_braces[-1] == 0:
            open_braces.pop()
            out[i] = " "
            i, last = template(i + 1)
        elif c.isalnum() or c in "_$":
            end = i + 1
            while end < n and (source[end].isalnum() or source[end] in "_$"):
                end += 1
            i, last = end, source[i:end]
        else:
            if open_braces and c in "{}":
                open_braces[-1] += 1 if c == "{" else -1
            if not c.isspace():
                last = c
            i += 1
    return "".join(out)


def _pairs(code: str) -> dict[int, int]:
    """Every opening bracket's place -> the place of the bracket that closes it."""
    closes = {")": "(", "]": "[", "}": "{"}
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for i, c in enumerate(code):
        if c in "([{":
            stack.append(i)
        elif c in closes and stack and code[stack[-1]] == closes[c]:
            pairs[stack.pop()] = i
    return pairs


def _split(text: str) -> list[tuple[int, str]]:
    """The pieces of a comma-separated list (parameters, the names in a pattern), each with
    where it starts; commas inside brackets or a generic type do not separate."""
    pieces: list[tuple[int, str]] = []
    depth = start = 0
    for i, c in enumerate(text):
        if c in "([{" or (c == "<" and i and (text[i - 1].isalnum() or text[i - 1] in "_$")):
            depth += 1
        elif c in ")]}" or (c == ">" and depth and text[i - 1] != "="):
            depth = max(0, depth - 1)
        elif c == "," and not depth:
            pieces.append((start, text[start:i]))
            start = i + 1
    pieces.append((start, text[start:]))
    return pieces


def _pattern_names(inner: str) -> list[str]:
    """The variables an object pattern declares: `{a, b: c, d = 1, ...rest}` -> a, c, d, rest."""
    names: list[str] = []
    for _, piece in _split(inner):
        target = piece.split("=", 1)[0]
        target = target.rsplit(":", 1)[-1] if ":" in target else target
        m = re.fullmatch(rf"\s*(?:\.\.\.)?\s*({_NAME})\s*", target)
        if m:
            names.append(m.group(1))
    return names


def review(
    source: str, table: ApiTable, tables: frozenset[str] | None = None, limit: int = 10
) -> Review:
    """What the script calls that the API reference does not document (and, with `tables`,
    the tables it opens that the docs never mention), in order of first use."""
    code = _code(source)
    n = len(code)
    pairs = _pairs(code)
    out = Review()

    def known(cls: str) -> bool:
        return table.member(cls, "") is not None

    def after(pos: int) -> str:
        """The first character of code after `pos` ("" at the end)."""
        while pos < n and code[pos].isspace():
            pos += 1
        return code[pos] if pos < n else ""

    # --- the names the script declares anywhere: a type with one of them is the script's own
    own_types = {m.group(1) for m in _DECLARED.finditer(code)}
    own_types |= {
        m.group(1) for block in _JSDOC.findall(source) for m in _JSDOC_NAMES.finditer(block)
    }
    root = _Scope(0, n)
    for m in _IMPORT.finditer(code):
        at = m.end() + len(source[m.end() :]) - len(source[m.end() :].lstrip())
        quote = source[at : at + 1]
        module = source[at + 1 : source.find(quote, at + 1)] if quote and quote in "'\"" else ""
        if module.startswith("@servicenow/glide"):
            continue  # the platform's own classes and variables, by their own names
        clause = m.group(1)
        inner = clause[clause.find("{") + 1 : clause.rfind("}")] if "{" in clause else ""
        outside = clause.replace("{" + inner + "}", " ") if inner else clause
        for piece in [*inner.split(","), *outside.split(",")]:
            name = re.search(rf"({_NAME})\s*$", piece)
            if name:
                own_types.add(name.group(1))
                root.names[name.group(1)] = _Var("name")

    def named(dotted: str) -> str:
        """The documented class a dotted name means: sn_ws.RESTMessageV2 -> RESTMessageV2.
        "" when it is not one, or is another namespace's class of the same name."""
        namespace, _, cls = dotted.rpartition(".")
        if not known(cls):
            return ""
        home = table.namespace(cls)
        return "" if namespace and home and namespace != home else cls

    def annotated(type_name: str) -> str:
        """The documented class a type annotation means ("" when it means something else:
        JavaScript's own type, one the script declares, or a bare name for a class the docs
        put in a namespace)."""
        cls = named(type_name)
        if not cls or "." in type_name:
            return cls
        return "" if cls in _JS_TYPES or cls in own_types or table.namespace(cls) else cls

    # --- functions: each body is a scope, with its parameters
    functions: list[_Function] = []

    def body_after(close: int) -> tuple[int, int] | None:
        m = _BODY.match(code, close + 1)
        brace = m.end() - 1 if m else -1
        return (brace, pairs[brace] + 1) if brace in pairs else None

    bodies: set[int] = set()
    for m in _FUNCTION.finditer(code):
        close = pairs.get(m.end() - 1)
        body = body_after(close) if close is not None else None
        if body:
            bodies.add(body[0])
            functions.append(_Function(m.start(), _Scope(*body), (m.end(), close)))
    for m in _METHOD.finditer(code):  # a method of a class or an object, and `catch (e) {`
        name = m.group(1)
        close = pairs.get(m.end() - 1)
        if name in _NOT_A_METHOD or close is None:
            continue
        body = body_after(close)
        if body and body[0] not in bodies:
            scope = _Scope(*body, block=name == "catch")
            functions.append(_Function(m.start(), scope, (m.end(), close)))
    opens = {close: open_ for open_, close in pairs.items()}
    arrows: list[int] = []
    arrow = code.find("=>")
    while arrow >= 0:
        arrows.append(arrow)
        arrow = code.find("=>", arrow + 2)
    # Where each arrow's body starts and ends. Worked out from the last arrow to the first: an
    # expression body runs to the comma, bracket or semicolon that ends it, and when it meets
    # the body of a later arrow (`a => b => c => ...`) it ends where that one does, instead of
    # reading the rest of the file again for every arrow.
    body_of: dict[int, tuple[int, int]] = {}
    ends: dict[int, int] = {}  # body start -> body end
    for arrow in reversed(arrows):
        start = arrow + 2
        while start < n and code[start].isspace():
            start += 1
        if start < n and code[start] == "{" and start in pairs:
            end = pairs[start] + 1
        else:
            end = start
            while end < n and code[end] not in ",;)]}":
                if ends.get(end, end) > end:
                    end = ends[end]
                elif code[end] in "([{":
                    end = pairs.get(end, n - 1) + 1
                else:
                    end += 1
        body_of[arrow] = (start, end)
        ends[start] = end
    for arrow in arrows:
        before = code[max(0, arrow - 400) : arrow]
        params: tuple[int, int] | None = None
        single = ""
        header = arrow
        m = _ARROW_PARENS.search(before)
        if m:
            close = arrow - len(before) + m.start()
            if close in opens:
                params, header = (opens[close] + 1, close), opens[close]
        else:
            m = _ARROW_NAME.search(before)
            if m:
                single, header = m.group(1), arrow - len(before) + m.start(1)
        if params or single:
            functions.append(_Function(header, _Scope(*body_of[arrow]), params, single))

    scopes = sorted((f.scope for f in functions), key=lambda s: (s.start, -s.end))
    open_scopes = [root]
    for scope in scopes:
        while len(open_scopes) > 1 and open_scopes[-1].end <= scope.start:
            open_scopes.pop()
        scope.parent = open_scopes[-1]
        scope.end = min(scope.end, scope.parent.end)
        open_scopes.append(scope)
    starts = [s.start for s in scopes]

    def scope_at(pos: int) -> _Scope:
        i = bisect.bisect_right(starts, pos) - 1
        scope = scopes[i] if i >= 0 else root
        while scope.parent is not None and not scope.start <= pos < scope.end:
            scope = scope.parent
        return scope

    def variable(name: str, pos: int) -> _Var | None:
        scope: _Scope | None = scope_at(pos)
        while scope is not None:
            if name in scope.names:
                return scope.names[name]
            scope = scope.parent
        return None

    # (where, the variable, where its value starts or -1, the class a type gives it)
    given: list[tuple[int, _Var, int, str]] = []
    in_params: list[tuple[int, int]] = []
    for f in functions:
        if f.single:
            f.scope.names.setdefault(f.single, _Var("param"))
        if not f.params:
            continue
        in_params.append(f.params)
        for offset, piece in _split(code[f.params[0] : f.params[1]]):
            at = f.params[0] + offset
            if piece.lstrip().startswith("{"):  # handed in by name, as one object
                brace = at + len(piece) - len(piece.lstrip())
                inner = code[brace + 1 : pairs.get(brace, brace)]
                for name in _pattern_names(inner):
                    f.scope.names.setdefault(name, _Var("object-param"))
                continue
            if piece.lstrip().startswith("["):
                for name in re.findall(_NAME, piece):
                    f.scope.names.setdefault(name, _Var("param"))
                continue
            m = _PARAM.match(piece)
            if not m or m.group(1) == "this":
                continue
            var = f.scope.names.setdefault(m.group(1), _Var("param"))
            var.cls = annotated(m.group(2)) if m.group(2) else var.cls
            equals = piece.find("=", m.end())
            if equals >= 0 and not piece.startswith("=>", equals):  # a default value
                given.append((at, var, at + equals + 1, ""))
    in_params.sort()

    by_header = sorted(functions, key=lambda f: f.header)
    headers = [f.header for f in by_header]

    def function_after(pos: int) -> _Function | None:
        """The function a comment ending at `pos` is written above."""
        i = bisect.bisect_left(headers, pos)
        f = by_header[i] if i < len(by_header) else None
        return f if f and not re.search(r"[;{}]", code[pos : f.header]) else None

    typed_declarations: dict[int, str] = {}  # where a declared name starts -> its @type
    for m in _JSDOC.finditer(source):
        if code[m.start()] != " ":  # not a comment: the same text inside a template
            continue
        f = function_after(m.end())
        for p in _JSDOC_PARAM.finditer(m.group(0)):
            var = f.scope.names.get(p.group(2)) if f else None
            if var is not None and not var.cls:
                var.cls = annotated(p.group(1))
        kind = _JSDOC_TYPE.search(m.group(0))
        declared = _AFTER_JSDOC.match(code, m.end()) if kind else None
        if declared:
            typed_declarations[declared.start(1)] = kind.group(1)

    # --- var, let and const: each name, where it is, and the value it starts with
    declared_at: set[int] = set()
    for f in functions:  # a function's own name is declared around it
        m = _FUNCTION.match(code, f.header)
        if m and m.group(1):
            scope_at(f.header).names.setdefault(m.group(1), _Var("name"))
    for m in re.finditer(rf"(?<![\w$.])class\s+({_NAME})", code):
        scope_at(m.start()).names.setdefault(m.group(1), _Var("name"))
    for m in _DECLARE.finditer(code):
        pos = m.end()
        scope = scope_at(m.start())
        while m.group(1) == "var" and scope.block and scope.parent is not None:
            scope = scope.parent
        while True:
            while pos < n and code[pos].isspace():
                pos += 1
            if pos >= n:
                break
            if code[pos] in "{[":  # a pattern: its names, whatever they are given
                end = pairs.get(pos)
                if end is None:
                    break
                inner = code[pos + 1 : end]
                names = _pattern_names(inner) if code[pos] == "{" else re.findall(_NAME, inner)
                for name in names:
                    var = scope.names.setdefault(name, _Var("var"))
                    given.append((pos, var, -1, ""))
                pos = end + 1
            else:
                name = _NAME_AT.match(code, pos)
                if not name:
                    break
                var = scope.names.setdefault(name.group(0), _Var("var"))
                declared_at.add(pos)
                kind = typed_declarations.get(pos, "")
                pos = name.end()
                annotation = _ANNOTATION.match(code, pos)
                if annotation:
                    declared_at.add(annotation.start(1))  # `x: Type = ...` assigns x, not Type
                    kind, pos = annotation.group(1), annotation.end()
                equals = _EQUALS.match(code, pos)
                if equals:
                    cls = annotated(kind) if kind else ""
                    given.append((name.start(), var, equals.end(), cls))
                elif kind and annotated(kind):
                    given.append((name.start(), var, -1, annotated(kind)))
            # on to the next name of this declaration, if a comma says there is one
            more = False
            while pos < n:
                c = code[pos]
                if c in "([{":
                    pos = pairs.get(pos, n - 1) + 1
                    continue
                if c == ",":
                    more, pos = True, pos + 1
                    break
                if c in ";)]}":
                    break
                if c == "\n":
                    # a line that ends in an operator, or a next one that starts with one,
                    # goes on; anything else ends the declaration
                    back = pos - 1
                    while back >= 0 and code[back].isspace():
                        back -= 1
                    if code[back] not in _GOES_ON and after(pos) not in _GOES_ON:
                        break
                pos += 1
            if not more:
                break

    def inside_parameters(pos: int) -> bool:
        i = bisect.bisect_right(in_params, (pos, n)) - 1
        return i >= 0 and in_params[i][0] <= pos < in_params[i][1]

    for m in _ASSIGN.finditer(code):
        if m.start(1) in declared_at or inside_parameters(m.start(1)):
            continue
        var = variable(m.group(1), m.start())
        if var is None:
            var = root.names.setdefault(m.group(1), _Var("global"))
        given.append((m.start(), var, m.end(), ""))

    def by_name(name: str, classes: bool) -> str:
        """What a name means when nothing in the script says: a variable of the platform, a
        class called directly (when `classes`), or one of the usual names."""
        if name in VARIABLES or (classes and known(name)):
            return name
        return next((cls for p, cls in _USUAL if p.match(name) and known(cls)), "")

    def class_of(name: str, pos: int) -> str:
        var = variable(name, pos)
        if var is None:
            return by_name(name, True)
        i = bisect.bisect_right(var.at, pos) - 1
        if i >= 0:
            return var.holds[i]
        if var.kind == "global":  # not given anything yet: still the platform's
            return by_name(name, True)
        if var.kind in ("param", "object-param"):
            return var.cls or by_name(name, var.kind == "object-param")
        if var.kind == "name":
            return ""
        if var.holds:  # used in a function written above the place it gets its value
            return var.holds[0]
        return next((cls for p, cls in _USUAL if p.match(name) and known(cls)), "")

    def value_class(pos: int) -> str:
        """The class of the value that starts at `pos`: `new Class(...)` or a documented
        method that returns one, and nothing more after it."""
        made = _VALUE_NEW.match(code, pos)
        called = None if made else _VALUE_CALL.match(code, pos)
        m = made or called
        close = pairs.get(m.end() - 1) if m else None
        if close is None or after(close + 1) in (".", "[", "("):
            return ""
        if made:
            return named(made.group(1))
        cls = table.returns(class_of(called.group(1), called.start(1)), called.group(2))
        return cls if cls and known(cls) else ""

    for at, var, value, kind in sorted(given, key=lambda g: g[0]):
        cls = kind or (value_class(value) if value >= 0 else "")  # may read the variable itself
        var.at.append(at)
        var.holds.append(cls)

    # --- the calls
    hits: list[tuple[int, Finding]] = []

    def look_up(cls: str, method: str, at: int) -> None:
        answer = table.member(cls, method) if method not in _OBJECT_METHODS else None
        if answer is None:  # not a class, nor a variable we know the class of
            return
        out.checked_calls += 1
        display, documented, close = answer
        if not documented:
            line = code.count("\n", 0, at) + 1
            hits.append((at, Finding(f"{display}.{method}", line, close)))

    def chain(cls: str, method: str, open_: int) -> None:
        """Check what is called on the result of `cls.method(`, and on that call's result."""
        while cls:
            close = pairs.get(open_)
            following = _NEXT_CALL.match(code, close + 1) if close is not None else None
            cls = table.returns(cls, method) if following else ""
            if not cls:
                return
            method, open_ = following.group(1), following.end() - 1
            look_up(cls, method, following.start(1))

    for m in _CALL.finditer(code):
        cls = class_of(m.group(1), m.start())
        if cls:
            look_up(cls, m.group(2), m.start())
            chain(cls, m.group(2), m.end() - 1)
    for m in _NEW.finditer(code):
        cls = named(m.group(1))
        close = pairs.get(m.end() - 1)
        following = _NEXT_CALL.match(code, close + 1) if close is not None and cls else None
        if following:
            look_up(cls, following.group(1), following.start(1))
            chain(cls, following.group(1), following.end() - 1)
    for m in _DEEP.finditer(code):
        path = re.sub(r"\s+", "", m.group(2))[1:]
        first, _, rest = path.partition(".")
        if _NAMESPACE.match(m.group(1)) and "." not in rest and named(f"{m.group(1)}.{first}"):
            if variable(m.group(1), m.start()) is None:  # sn_fd.FlowAPI.getRunner(
                look_up(first, rest, m.start())
                chain(first, rest, m.end() - 1)
            continue
        cls = class_of(m.group(1), m.start())
        names = table.member_names(cls) if cls else None
        # helpers.navigate.to(: only when the class documents something under "navigate."
        if names and (path in names or any(name.startswith(first + ".") for name in names)):
            look_up(cls, path, m.start())

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
