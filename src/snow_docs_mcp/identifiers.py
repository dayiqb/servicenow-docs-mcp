"""Code names in a query, and ranking a section named after one first.

The reranker scores near-misses close to the exact method: for "GlideRecord addEncodedQuery"
it put addSystemEncodedQuery (7.27) above both addEncodedQuery sections (6.89, 6.71). A small
bonus for a section whose own heading names the query's method fixes that: on 150 "Class
method" lookups from the API reference, the exact section came first for 149 instead of 130,
and none of the 67 gold questions' top 10 changed (measured 2026-09-27).
"""

from __future__ import annotations

import html
import re

_STRIP = "\"'`,;:?!()[]{}<>*"
_MD_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_NOT_CODE = {"ServiceNow"}  # the product name: in many queries and headings, never a method
_CODE_CHARS = re.compile(r"[$\w]+")
_ARGS = re.compile(r"(?<=\w)\([^()]*\)")  # a call's argument list: name(String a, ...)
BONUS = 2.0  # reranker logits per matched name; the near-misses were within ~1.5


def _looks_like_code(token: str, classes: bool = True) -> bool:
    """camelCase / snake_case / $name; PascalCase with an inner capital only if `classes`."""
    if not _CODE_CHARS.fullmatch(token) or not re.search(r"[A-Za-z]", token):
        return False
    if token in _NOT_CODE:
        return False
    if "_" in token.strip("_") or token.startswith("$"):
        return True
    if re.search(r"[a-z0-9][A-Z]", token):
        return classes or token[0].islower()
    return False


def code_identifiers(query: str) -> list[str]:
    """Distinct code names in `query`, in order: addEncodedQuery, GlideRecord, sys_user,
    $sp, g_form.setMandatory (a dotted name also adds its code-like parts)."""
    out: list[str] = []
    for raw in query.split():
        t = raw.strip(_STRIP + ".")
        t = re.sub(r"\(.*$", "", t).strip(_STRIP + ".")  # getValue() / getValue(a) -> getValue
        if len(t) < 3:
            continue
        parts = [p for p in t.split(".") if p]
        found: list[str] = []
        if len(parts) > 1:
            if (
                all(_CODE_CHARS.fullmatch(p) for p in parts)
                and re.search(r"[A-Za-z]", t)
                and max(map(len, parts)) >= 2  # not "e.g" / "i.e"
            ):
                found.append(t)
                found += [p for p in parts if len(p) >= 2 and _looks_like_code(p)]
        elif _looks_like_code(t):
            found.append(t)
        for name in found:
            if name not in out:
                out.append(name)
    return out


def plain_heading(heading_path: str) -> str:
    """A heading as text: markdown escapes ('g\\_form') and HTML entities undone."""
    return html.unescape(_MD_ESCAPE.sub(r"\1", heading_path or ""))


def _kind(name: str) -> str:
    """"member" (addEncodedQuery), "anchor" (a class, GlideRecord, or a table/field name,
    cmdb_ci_computer: counts only next to a member), or "other" (dotted, $sp)."""
    if "." in name or name.startswith("$"):
        return "other"
    if re.search(r"[a-z0-9][A-Z]", name) and name[0].islower():
        return "member"
    return "anchor"


def _pattern(name: str, kind: str) -> re.Pattern:
    word = re.escape(name)
    if kind == "member":  # as API headings write members: name(...) or "Class - name"
        return re.compile(rf"(?<![\w$]){word}\(|\s-\s{word}(?![\w$])")
    return re.compile(rf"(?<![\w$]){word}(?![\w$])")


def prefer_exact(query: str, hits: list) -> list:
    """`hits` (reranked, best first) re-sorted by score + BONUS for each query code name the
    section's own heading contains, argument lists ignored. A method counts only as API
    headings write one ("addEncodedQuery(...)", "Class - addEncodedQuery"), so product names
    like vCenter or iOS don't; a class or table name (GlideRecord, cmdb_ci_computer) counts
    only together with a method, so it alone never reorders. Scores are unchanged."""
    names = code_identifiers(query)
    if not names:
        return list(hits)
    kinds = [_kind(n) for n in names]
    patterns = [_pattern(n, k) for n, k in zip(names, kinds)]

    def matched(h) -> int:
        own = _ARGS.sub("()", plain_heading(h.heading_path).split(" > ")[-1])
        found = [bool(p.search(own)) for p in patterns]
        if not any(f and k != "anchor" for f, k in zip(found, kinds)):
            return 0
        return sum(found)

    return sorted(hits, key=lambda h: h.score + BONUS * matched(h), reverse=True)
