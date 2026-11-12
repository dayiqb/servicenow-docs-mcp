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
from pathlib import PurePath

from snow_docs_mcp.api_table import ApiTable
from snow_docs_mcp.script_check import check

# Files that can hold ServiceNow script: JavaScript and TypeScript, exported records (XML),
# widgets and UI pages (HTML), and files without an extension.
_CODE_SUFFIXES = {"", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".xml", ".html", ".htm"}
# Cheap first look: is there anything the check could resolve at all?
_LOOKS_LIKE_SCRIPT = re.compile(
    r"\bnew\s+[A-Z]\w*\s*\(|\b(?:gs|current|previous|g_\w+)\s*\.|\$sp\s*\.|\bGlide\w+\s*\."
)
_WRITERS = {"Write", "Edit", "MultiEdit"}


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


def note(payload: dict, table: ApiTable, release: str) -> str | None:
    """What to tell Claude about the code it just wrote, if anything."""
    tool_input = payload.get("tool_input")
    path = str(tool_input.get("file_path", "")) if isinstance(tool_input, dict) else ""
    if PurePath(path).suffix.lower() not in _CODE_SUFFIXES:
        return None
    code = code_of(payload)
    if not code or not _LOOKS_LIKE_SCRIPT.search(code):
        return None
    findings = check(code, table)
    if not findings:
        return None
    lines = []
    for f in findings:
        close = f"; closest documented: {', '.join(f.suggestions)}" if f.suggestions else ""
        lines.append(f"- {f.call}() at line {f.line} of the new text{close}")
    return (
        f"ServiceNow script check: the {release} API reference does not document these calls "
        f"in {PurePath(path).name or 'the file'}:\n" + "\n".join(lines) + "\n"
        "Look each one up with snow_docs_api. If it is a mistake, fix the code. If the method "
        "really exists but is undocumented, tell the user that it is not in the API reference."
    )


def main() -> int:
    if os.environ.get("SNOW_DOCS_SCRIPT_HOOK", "").strip().lower() in ("off", "0", "false"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict) or not _LOOKS_LIKE_SCRIPT.search(code_of(payload)):
        return 0
    from snow_docs_mcp import api_table, config, setup  # after the cheap checks: slower imports

    release = config.default_release()
    db = setup.active_index(release)
    if db is None:  # not installed (yet): say nothing, and leave the download to the server
        return 0
    text = note(payload, api_table.load(db), release)
    if text:
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}
        sys.stdout.write(json.dumps(out))
    return 0
