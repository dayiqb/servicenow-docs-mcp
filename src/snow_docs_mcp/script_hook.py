"""PostToolUse hook body: after Claude writes or edits a file with ServiceNow script code,
tell it which calls the API reference does not document.

Reads the hook payload (JSON) on stdin and, when there is something to say, prints one JSON
object that adds a note to Claude's context. It never blocks, never fails the tool call and
never starts a download: any problem, or no installed docs index, means "stay silent, exit
0". Turn it off with SNOW_DOCS_SCRIPT_HOOK=off.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePath

from snow_docs_mcp.api_table import ApiTable
from snow_docs_mcp.script_check import check

# Files that can hold ServiceNow script: JavaScript and TypeScript, exported records (XML),
# widgets and UI pages (HTML), and files without an extension.
_CODE_SUFFIXES = {"", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".xml", ".html", ".htm"}
# Cheap first look: is this ServiceNow script at all? Only names that mean ServiceNow count.
# `current`, `previous` and `new Foo(` are ordinary JavaScript too, and reading a React
# component as a business rule gives false alarms.
_SERVICENOW = re.compile(
    r"\bGlide[A-Z]\w*"  # GlideRecord, GlideDateTime, GlideAjax, ...
    r"|\bgs\s*\.\s*\w+\s*\("  # gs.info(
    r"|\bg_[a-z]\w*\s*\."  # g_form., g_user., g_scratchpad.
    r"|\$sp\s*\."  # Service Portal
    r"|\bsn_\w+\s*\."  # scoped namespaces: sn_ws.RESTMessageV2
    r"|\bClass\.create\s*\("  # a script include
    r"|\bexecuteRule\s*\("  # a business rule
)
# Larger than hand-written code: the check would not end inside the hook's timeout.
MAX_CHARS = 300_000
_WRITERS = {"Write", "Edit", "MultiEdit"}
_FLUENT_SUFFIX = ".now.ts"  # ServiceNow SDK source files


def code_of(payload: dict) -> str:
    """The text a Write, Edit or MultiEdit call put into the file ("" for anything else)."""
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") not in _WRITERS or not isinstance(tool_input, dict):
        return ""
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        parts = [e.get("new_string") for e in edits if isinstance(e, dict)]
    else:
        parts = [tool_input.get("content"), tool_input.get("new_string")]
    return "\n".join(p for p in parts if isinstance(p, str) and p)


def _path_of(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    return str(tool_input.get("file_path") or "") if isinstance(tool_input, dict) else ""


def _lines_of(text: str, written: list[str]) -> list[range] | None:
    """The line ranges of `text` that hold the strings just written (None when one of them
    is not in the text: the file changed again, or is not the one that was edited)."""
    found: list[range] = []
    for new in written:
        at = text.find(new)
        if at < 0:
            return None
        while at >= 0:
            first = text.count("\n", 0, at) + 1
            found.append(range(first, first + new.count("\n") + 1))
            at = text.find(new, at + len(new))
    return found


def checked_text(payload: dict) -> tuple[str, list[range] | None]:
    """(the text to check, the line ranges of it that were just written; None = all of it).

    A Write holds the whole file. An Edit holds only the new text, which has no types on its
    own (`gr` is declared further up), so the file is read from disk, where the edit has
    already been made, and findings are kept for the edited lines only. When the file cannot
    be read, the new text is checked by itself.
    """
    code = code_of(payload)
    tool_input = payload.get("tool_input")
    if not code or not isinstance(tool_input, dict) or isinstance(tool_input.get("content"), str):
        return code, None
    edits = tool_input.get("edits")
    written = (
        [e.get("new_string") for e in edits if isinstance(e, dict)]
        if isinstance(edits, list)
        else [tool_input.get("new_string")]
    )
    written = [w for w in written if isinstance(w, str) and w.strip()]
    try:
        file = Path(_path_of(payload))
        if not file.is_file() or file.stat().st_size > MAX_CHARS * 4:
            return code, None
        text = file.read_bytes().decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return code, None
    lines = _lines_of(text, written)
    return (text, lines) if lines is not None else (code, None)


def _servicenow_script(text: str) -> bool:
    return len(text) <= MAX_CHARS and bool(_SERVICENOW.search(text))


def note(
    payload: dict, table: ApiTable, release: str, tables: frozenset[str] | None = None
) -> str | None:
    """What to tell Claude about the code it just wrote, if anything."""
    path = _path_of(payload)
    if PurePath(path).suffix.lower() not in _CODE_SUFFIXES:
        return None
    code, written = checked_text(payload)
    if not code:
        return None
    name = PurePath(path).name or "the file"
    parts: list[str] = []
    findings = check(code, table, tables) if _servicenow_script(code) else []
    if written is not None:
        findings = [f for f in findings if any(f.line in lines for lines in written)]
    if findings:
        lines = []
        for f in findings:
            close = f"; closest: {', '.join(f.suggestions)}" if f.suggestions else ""
            if f.kind == "table":
                lines.append(
                    f"- table '{f.call}' at line {f.line}: the docs never mention it{close}"
                )
            else:
                lines.append(f"- {f.call}() at line {f.line}: not in the API reference{close}")
        parts.append(
            f"ServiceNow script check ({release} docs) of the text just written to {name}:\n"
            + "\n".join(lines)
            + "\nLook each method up with snow_docs_api. If it is a mistake, fix the code. If the "
            "method or table really exists but is not in the docs (custom or undocumented), tell "
            "the user that it could not be verified."
        )
    if path.lower().endswith(_FLUENT_SUFFIX):
        parts.append(
            f"{name} is a ServiceNow SDK (Fluent) file. Check the Fluent APIs it uses with "
            "snow_docs_sdk_explain, and suggest running `now-sdk build`, which type-checks the "
            "project locally."
        )
    return "\n\n".join(parts) or None


def _worth_a_look(payload: dict) -> bool:
    """Cheap first look, before the slower imports: ServiceNow script, or a Fluent file."""
    path = _path_of(payload)
    if PurePath(path).suffix.lower() not in _CODE_SUFFIXES:
        return False
    code, _ = checked_text(payload)
    return bool(code) and (path.lower().endswith(_FLUENT_SUFFIX) or _servicenow_script(code))


def main() -> int:
    if os.environ.get("SNOW_DOCS_SCRIPT_HOOK", "").strip().lower() in ("off", "0", "false"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict) or not _worth_a_look(payload):
        return 0
    from snow_docs_mcp import api_table, config, setup, tables  # after the cheap checks

    release = config.default_release()
    db = setup.active_index(release)
    if db is None:  # not installed (yet): say nothing, and leave the download to the server
        return 0
    text = note(payload, api_table.load(db), release, tables.names(db))
    if text:
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}
        sys.stdout.write(json.dumps(out))
    return 0
