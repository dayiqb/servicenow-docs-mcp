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
# "Scoped GlideRecord", "GlideForm (Next Experience)", "GlideNavigation [Next Experience]"
_VARIANT = re.compile(r"^scoped\s+|\s*(?:\(.*\)|\[.*\])\s*$", re.IGNORECASE)

_REST_HEADING = re.compile(
    r"^(?P<api>.+?)\s+[-–—]\s+(?P<verb>GET|POST|PUT|PATCH|DELETE)\s+(?P<path>/\S*)\s*$"
)
# A path as people paste it: with a verb, an instance address or neither.
_ENDPOINT_QUERY = re.compile(
    r"^(?:(GET|POST|PUT|PATCH|DELETE)\s+)?"
    r"(?:https?://[^/\s?#]+|[\w-]+(?:\.[\w-]+)+(?::\d+)?(?=/api/))?(/\S*)$",
    re.IGNORECASE,
)
_URL_VERB = re.compile(r"^(?:GET|POST|PUT|PATCH|DELETE)\s+", re.IGNORECASE)
_NEW = re.compile(r"^new\s+")
_ARGUMENTS = re.compile(r"(?<=[\w$])\([^()]*\)")  # of a call: not "GlideForm (Next Experience)"
# The namespace a script writes before a class: sn_ws.RESTMessageV2, global.GlideQuery.
_NAMESPACE_PREFIX = re.compile(r"^(?:sn_\w+|global)\.(?=.)", re.IGNORECASE)
_NAMESPACE = re.compile(
    r"`?\b(sn\\?_[a-z0-9_\\]+)`?\s+namespace|namespace[^.\n]{0,30}?`?\b(sn\\?_[a-z0-9_\\]+)"
)
_DEFAULT_URL = re.compile(r"Default URL:\s*`([^`]+)`")
_CODE_URL = re.compile(r"`(/?api/[^`\s]+)`")
_DATA_TYPE = re.compile(r"Data type:\s*([A-Za-z]\w*)")
_VERSION = re.compile(r"^(v\d+|\{api_version\})$", re.IGNORECASE)
_REST_DESCRIPTION_CHARS = 300

# The variables scripts hold these classes in, as the API reference names them.
VARIABLES: dict[str, tuple[str, ...]] = {
    "gs": ("glidesystem",),
    "current": ("gliderecord",),
    "previous": ("gliderecord",),
    "g_form": ("glideform", "mobileglideform"),
    "g_user": ("glideuser",),
    "g_list": ("glidelist2", "glidelistv3", "glidelist"),
    "g_modal": ("glidemodal",),
    "g_aw": ("glideagentworkspace",),
    "g_document": ("glidedocument",),
    "g_guid": ("glideguid",),
    "g_i18n": ("i18n",),
    "g_menu": ("glidemenu",),
    "g_item": ("glidemenu",),
    "g_navigation": ("glidenavigation",),
    "g_notification": ("glidenotification",),
    "g_processor": ("glidescriptedprocessor",),
    "g_request": ("glideservletrequest",),
    "g_response": ("glideservletresponse",),
    "g_ui_scripts": ("glideuiscripts",),
    "$sp": ("glidespscriptable",),
    # Service Portal's client services: a widget's controller is handed them by these names
    "spUtil": ("sputil",),
    "spModal": ("spmodal",),
    "spAriaUtil": ("spariautil",),
    "spContextManager": ("spcontextmanager",),
}


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
    namespace: str = ""  # "sn_ws" when the page says the class is in that namespace
    short: str = ""  # the name as a script writes it after the class: "emit" for "api.emit"

    def __post_init__(self) -> None:
        if not self.short:
            self.short = self.name.removeprefix(_plain(self.class_name) + ".")


@dataclass
class Endpoint:
    api: str  # "Table"
    verb: str
    path: str  # "/now/table/{tableName}"
    file_path: str
    heading_path: str
    occurrence: int
    description: str = ""
    default_url: str = ""
    path_params: list[Param] = field(default_factory=list)
    query_params: list[Param] = field(default_factory=list)
    body_params: list[Param] = field(default_factory=list)


def _plain(class_name: str) -> str:
    """'Scoped GlideRecord' and 'GlideForm (Next Experience)' -> 'GlideRecord', 'GlideForm'."""
    name = class_name.strip()
    while True:
        shorter = _VARIANT.sub("", name).strip()
        if shorter == name:
            return name
        name = shorter


def _text(cell: str) -> str:
    cell = sections.unescape_markdown(sections.unlink(_TAG.sub(" ", cell)))
    return _WS.sub(" ", cell).strip()


_TABLE_CLASS = re.compile(r'^<table\b[^>]*\bclass="([^"]*)"', re.IGNORECASE)


def _tables(body: str) -> list[tuple[str, list[list[str]]]]:
    """Every table in a section, in order: (its HTML class or "", rows of cell texts with the
    header row first)."""
    found: list[tuple[int, str, list[list[str]]]] = []
    for m in _HTML_TABLE.finditer(body):
        rows = [[_text(c) for c in _HTML_CELL.findall(r)] for r in _HTML_ROW.findall(m.group(0))]
        cls = _TABLE_CLASS.match(m.group(0))
        found.append((m.start(), cls.group(1) if cls else "", [r for r in rows if r]))
    block: list[list[str]] = []
    start = pos = 0
    for line in [*_HTML_TABLE.sub(lambda m: "\n" * m.group(0).count("\n"), body).split("\n"), ""]:
        if line.lstrip().startswith("|"):
            if not block:
                start = pos
            if not _SEPARATOR.match(line):
                block.append([_text(c) for c in _PIPE.split(line.strip().strip("|"))])
        elif block:
            found.append((start, "", block))
            block = []
        pos += len(line) + 1
    return [(cls, rows) for _, cls, rows in sorted(found, key=lambda x: x[0])]


def _fill(member: Member, body: str) -> None:
    """Add what a (further) part of the member's section says."""
    if not member.description:
        cut = min(
            (i for i in (body.find("\n|"), body.find("<table"), body.find("```")) if i >= 0),
            default=len(body),
        )
        member.description = _text(body[:cut])
    for _, rows in _tables(body):
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


def _signature_params(signature: str) -> list[Param]:
    """Parameters as a signature names them: "String name" or "name: String"."""
    args = signature[signature.index("(") + 1 : signature.rindex(")")]
    out: list[Param] = []
    for piece in (a.strip() for a in args.split(",")):
        if not piece:
            continue
        if ":" in piece:
            name, _, kind = piece.partition(":")
        else:
            kind, _, name = piece.rpartition(" ")
        out.append(Param(name.strip(), kind.strip(), ""))
    return out


def _rest_params(rows: list[list[str]]) -> list[Param]:
    out = []
    for row in rows[1:]:
        if len(row) < 2 or not row[0] or row[0].lower() == "none":
            continue
        kind = _DATA_TYPE.search(row[1])
        text = row[1]
        if len(text) > _REST_DESCRIPTION_CHARS:
            text = text[:_REST_DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"
        out.append(Param(row[0], kind.group(1) if kind else "", text))
    return out


def parse_rest_page(file_path: str, text: str) -> list[Endpoint]:
    """The REST endpoints a page documents: H2 `API - VERB /path`, with the tables under
    "Supported request parameters" (path, query, request body, in that order)."""
    endpoints: list[Endpoint] = []
    current: Endpoint | None = None
    seen: dict[str, int] = {}
    for sec in sections.split_into_sections(sections.strip_front_matter(text)):
        crumb = " > ".join(sec.heading_path)
        seen[crumb] = seen.get(crumb, 0) + 1
        if len(sec.heading_path) == 2:
            m = _REST_HEADING.match(sections.unescape_markdown(sec.heading_path[-1]))
            current = None
            if m:
                current = Endpoint(
                    m.group("api").strip(),
                    m.group("verb"),
                    m.group("path"),
                    file_path,
                    crumb,
                    seen[crumb],
                )
                cut = min(
                    (
                        i
                        for i in (
                            sec.body.find("\n|"),
                            sec.body.find("<table"),
                            sec.body.find("```"),
                        )
                        if i >= 0
                    ),
                    default=len(sec.body),
                )
                current.description = _text(sec.body[:cut])
                current.default_url = _url_from_path(current.path)  # until "URL format" says
                endpoints.append(current)
        elif len(sec.heading_path) < 2:
            current = None
        elif current is not None:
            part = sections.unescape_markdown(sec.heading_path[2]).strip().lower()
            if part == "url format":
                current.default_url = _default_url(sec.body) or current.default_url
            elif part == "supported request parameters":
                tables = [
                    (cls, rows)
                    for cls, rows in _tables(sec.body)
                    if rows
                    and [h.lower() for h in rows[0]]
                    in (["name", "description"], ["parameter", "description"])
                ]
                # path, query, request body, in that order; an HTML class may say which
                for place, (cls, rows) in enumerate(tables[:3]):
                    by_class = next((k for k in ("path", "query", "body") if k in cls), "")
                    target = f"{by_class or ('path', 'query', 'body')[place]}_params"
                    if not getattr(current, target):
                        setattr(current, target, _rest_params(rows))
    return endpoints


def _without_version(url: str) -> str:
    """A URL as the docs give it, as a default URL: no verb in front, no version part, no
    space inside, and starting with '/api' when it starts with a namespace (now, sn_...)."""
    url = _WS.sub("", _URL_VERB.sub("", url.strip()))  # the docs break a few with a space
    parts = [p for p in url.strip("/").split("/") if p]
    parts = [p for p in parts if p != "{api_version}"]
    if parts and (parts[0] == "now" or parts[0].startswith("sn_")):
        parts.insert(0, "api")
    return "/" + "/".join(parts)


def _default_url(block: str) -> str:
    """The default URL a "URL format" part gives: labelled, or the only one without a
    version, or the versioned one with the version taken out."""
    labelled = _DEFAULT_URL.search(block)
    if labelled:
        return _without_version(labelled.group(1))
    urls = _CODE_URL.findall(block)
    plain = [u for u in urls if "{api_version}" not in u]
    return _without_version((plain or urls)[0]) if urls else ""


def _url_from_path(path: str) -> str:
    """'/api' + the heading's path when that path starts with its namespace (now, sn_...)."""
    parts = [p for p in path.strip("/").split("/") if p]
    if parts and parts[0].lower() == "api":
        parts = parts[1:]
    if parts and (parts[0] == "now" or parts[0].startswith("sn_")):
        return _without_version("/api/" + "/".join(parts))
    return ""


def _segments(path: str) -> list[str]:
    """A REST path's parts, without the '/api' start and the version."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts = [p for p in path.strip().strip("/").split("/") if p]
    if parts and parts[0].lower() == "api":
        parts = parts[1:]
    return [p for i, p in enumerate(parts) if not (i <= 2 and _VERSION.match(p))]


def parse_page(file_path: str, text: str) -> list[Member]:
    """The methods and properties an API reference page documents, in page order."""
    members: list[Member] = []
    current: Member | None = None
    seen: dict[str, int] = {}
    text = sections.strip_front_matter(text)
    named = _NAMESPACE.search(text.split("\n## ", 1)[0])  # the page's introduction
    namespace = (named.group(1) or named.group(2)).replace("\\", "") if named else ""
    for sec in sections.split_into_sections(text):
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
            current.namespace = namespace
            _fill(current, sec.body)
            members.append(current)
    for member in members:  # a few methods have no parameter table: read the signature
        if member.kind == "method" and not member.params:
            member.params = _signature_params(member.signature)
    classes = {m.class_name for m in members if m.kind == "method"}
    return [m for m in members if m.kind == "method" or m.class_name in classes]


def load(db_path) -> ApiTable:
    """The API reference of one index as a table (parsing takes about half a second)."""
    from snow_docs_mcp import store

    pages = store.documents(db_path, API_PREFIX)
    members = [m for path, text in pages for m in parse_page(path, text)]
    endpoints = [e for path, text in pages for e in parse_rest_page(path, text)]
    return ApiTable(members, endpoints)


def _base(class_name: str) -> str:
    """'Scoped GlideRecord' and 'GlideForm (Next Experience)' -> 'gliderecord', 'glideform'."""
    return _plain(class_name).lower()


class ApiTable:
    def __init__(self, members: list[Member], endpoints: list[Endpoint] | None = None):
        self.endpoints = list(endpoints or [])
        self.by_api: dict[str, list[Endpoint]] = {}  # lowercase API name -> its endpoints
        # every endpoint by the parts of its path, and of its default URL when that differs
        self._paths: list[tuple[Endpoint, list[str]]] = []
        for e in self.endpoints:
            self.by_api.setdefault(e.api.lower(), []).append(e)
            ways = [_segments(e.path)]
            if e.default_url and _segments(e.default_url) not in ways:
                ways.append(_segments(e.default_url))
            self._paths += [(e, way) for way in ways]
        self.by_class: dict[
            str, dict[str, list[Member]]
        ] = {}  # base -> class as written -> members
        self.by_method: dict[str, list[Member]] = {}  # lowercase method name -> members
        self.by_name: dict[str, list[Member]] = {}  # name, exact, as the docs or a script write it
        self.display: dict[str, str] = {}  # base -> the class name without its variant
        self.names: set[str] = set()  # class names as the docs write them, exact case
        for m in members:
            base = _base(m.class_name)
            self.by_class.setdefault(base, {}).setdefault(m.class_name, []).append(m)
            self.by_method.setdefault(m.name.lower(), []).append(m)
            for name in dict.fromkeys((m.name, m.short)):
                self.by_name.setdefault(name, []).append(m)
            plain = _plain(m.class_name)
            if base not in self.display or len(plain) < len(self.display[base]):
                self.display[base] = plain
            self.names.update((plain, m.class_name))

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_method.values())

    def _endpoints(self, verb: str, path: str) -> tuple[str, object]:
        """Endpoints a (verb and) path means: the documented path it fits, or everything
        under it when it is only the start of one. A documented path fits by its fixed parts:
        one made of placeholders only fits nothing."""
        given = _segments(path)

        def fits(doc: list[str], n: int) -> bool:
            return len(doc) >= n and all(
                d.startswith("{") or d.lower() == g.lower()
                for d, g in zip(doc[:n], given, strict=False)
            )

        def literal(doc: list[str]) -> int:
            return sum(not d.startswith("{") for d in doc[: len(given)])

        docs = [(e, d) for e, d in self._paths if literal(d) and fits(d, len(given))]
        same = [(e, d) for e, d in docs if len(d) == len(given)]
        for group in (same, docs):
            if not group:
                continue
            best = max(literal(d) for _, d in group)
            hits = list({id(e): e for e, d in group if literal(d) == best}.values())
            wanted = [e for e in hits if not verb or e.verb == verb.upper()]
            if wanted:
                return "endpoint", wanted
            return "not_found", [f"{e.verb} {e.path}" for e in hits][:5]
        return "not_found", []

    def _class(self, name: str) -> tuple[str, dict[str, list[Member]]] | None:
        """(the class as the docs name it, the variants a class name means). "Scoped
        GlideRecord" means that one variant, a plain name every variant; classes that differ
        only in case ("API", "api") are different classes when the name is one of them."""
        asked = name.strip()
        wanted = asked.lower()
        base = _base(wanted)
        bases = [b for b in (*VARIABLES.get(wanted, ()), base) if b in self.by_class]
        if not bases:
            return None
        variants = {c: ms for b in dict.fromkeys(bases) for c, ms in self.by_class[b].items()}
        exact = {c: ms for c, ms in variants.items() if c.lower() == wanted and wanted != base}
        same_case = {c: ms for c, ms in variants.items() if _plain(c) == asked}
        variants = exact or same_case or variants
        return min((_plain(c) for c in variants), key=len), variants

    def _client_side(self, variants: dict[str, list[Member]]) -> list[Member]:
        """What the docs have for the same class in a client script ("Client side
        GlideRecord"): a script may be one, and the class is written the same there."""
        bases = dict.fromkeys(f"client side {_base(c)}" for c in variants)
        return [m for b in bases for ms in self.by_class.get(b, {}).values() for m in ms]

    def _members(self, class_name: str) -> tuple[str, list[Member]] | None:
        """(the class as the docs name it, everything it documents) for a class name or a
        variable that holds one, exact in case; None for anything else."""
        if class_name not in VARIABLES and class_name not in self.names:
            return None
        hit = self._class(class_name)
        if not hit:
            return None
        display, variants = hit
        return display, [m for ms in variants.values() for m in ms] + self._client_side(variants)

    def member(self, class_name: str, method: str) -> tuple[str, bool, list[str]] | None:
        """(the class as the docs name it, whether it documents `method`, the closest
        names when it does not); None when `class_name` is neither a class nor a variable
        that holds one. Class and method names are matched exactly, as JavaScript does."""
        hit = self._members(class_name)
        if not hit:
            return None
        display, members = hit
        names = sorted({m.short for m in members})
        if method in names:
            return display, True, []
        close = difflib.get_close_matches(method, names, n=3, cutoff=0.6)
        return display, False, [f"{display}.{c}" for c in close]

    def member_names(self, class_name: str) -> set[str] | None:
        """The names a class documents, as a script writes them after the class or the
        variable ("navigate.to" for helpers); None when it is not a class."""
        hit = self._members(class_name)
        return {m.short for m in hit[1]} if hit else None

    def namespace(self, class_name: str) -> str:
        """The namespace the docs put a class in ("sn_ws"), or "" when they name none."""
        hit = self._class(class_name) if class_name in self.names else None
        spaces = {m.namespace for ms in hit[1].values() for m in ms} if hit else set()
        return spaces.pop() if len(spaces) == 1 else ""

    def returns(self, class_name: str, method: str) -> str:
        """The class a documented method returns ("" when it is not a documented class, or
        the method or class is unknown)."""
        hit = self._members(class_name)
        for m in hit[1] if hit else ():
            if m.short == method and m.returns.strip() in self.names:
                return m.returns.strip()
        return ""

    def find(self, name: str) -> tuple[str, object]:
        """("class", {class as written: members}), ("method", [members]), ("rest_api",
        {API: endpoints}), ("endpoint", [endpoints]) or ("not_found", [closest names]).

        A class is found whatever its case, with or without its namespace (sn_ws.RESTMessageV2).
        A chain of calls is followed by what each returns (gs.getUser().getName).
        A method is found by its exact name, as JavaScript calls it: a name that differs only
        in case is not found, and the right spelling is the closest name."""
        raw = name.strip()
        if raw.endswith(")"):  # a variant as the docs write it: "GlideForm (Next Experience)"
            for variants in self.by_class.values():
                for written, members in variants.items():
                    if written.lower() == raw.lower() and _plain(written) != written:
                        return "class", {written: members}
        # a call's arguments say nothing; what follows a call is called on what it returns
        calls = _NEW.sub("", raw)
        while (fewer := _ARGUMENTS.sub("\0", calls)) != calls:
            calls = fewer
        links = [link for link in (part.strip().strip(".") for part in calls.split("\0")) if link]
        q = links[0] if links else ""
        for following in links[1:]:  # gs.getUser().getName -> GlideUser.getName
            kind, found = self._named(q)
            if kind == "class":  # new GlideRecord('x').query: the class itself
                q = f"{q}.{following}"
                continue
            returned = {m.returns.strip() for m in found} & self.names if kind == "method" else ()
            if len(returned) != 1:
                return "not_found", []
            q = f"{next(iter(returned))}.{following}"
        q = re.sub(r"\(.*\)\s*$", "", q).strip().strip(".")
        if not q:
            return "not_found", []
        endpoint = _ENDPOINT_QUERY.match(q)
        if endpoint:
            return self._endpoints(endpoint.group(1) or "", endpoint.group(2))
        return self._named(q)

    def _named(self, q: str) -> tuple[str, object]:
        """A class or member by name, with or without a namespace before it."""
        answer = self._lookup(q)
        plain = _NAMESPACE_PREFIX.sub("", q)
        if answer[0] == "not_found" and plain != q:
            return self._lookup(plain)
        return answer

    def _lookup(self, q: str) -> tuple[str, object]:
        whole = self._class(q)
        if whole:
            return "class", whole[1]
        api = self.by_api.get(re.sub(r"\s+api$", "", q.lower()))
        if api:
            return "rest_api", {api[0].api: api}
        parts = q.split(".")
        # Class.member: the class may have a dot (cabrillo.camera), and so may the member
        # (helpers.navigate.to); the longest class that exists is the one meant
        for cut in range(len(parts) - 1, 0, -1):
            hit = self._class(".".join(parts[:cut]))
            if not hit:
                continue
            display, variants = hit
            rest = ".".join(parts[cut:])
            own = [m for ms in variants.values() for m in ms]
            for members in (own, self._client_side(variants)):
                found = [m for m in members if rest in (m.short, m.name)]
                if found:
                    return "method", found
            names = sorted({m.short for m in own + self._client_side(variants)})
            close = [n for n in names if n.lower() == rest.lower()]
            close = close or difflib.get_close_matches(rest, names, n=3, cutoff=0.6)
            return "not_found", [f"{display}.{c}" for c in close]
        found = self.by_name.get(q, [])
        if found:
            return "method", found
        if len(parts) > 1:
            # an unknown class: point at the classes that have the method, never answer with them
            method = parts[-1]
            owners = self.by_name.get(method) or self.by_method.get(method.lower(), [])
            return "not_found", sorted({f"{_plain(m.class_name)}.{m.short}" for m in owners})[:5]
        same = sorted(n for n in self.by_name if n.lower() == q.lower())
        if same:  # right but for its case
            return "not_found", same[:5]
        bases = difflib.get_close_matches(_base(q), list(self.by_class), n=3, cutoff=0.75)
        methods = difflib.get_close_matches(q.lower(), list(self.by_method), n=3, cutoff=0.8)
        close = [self.display[b] for b in bases]
        close += sorted({m.name for k in methods for m in self.by_method[k]})
        return "not_found", list(dict.fromkeys(close))[:5]
