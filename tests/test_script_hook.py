"""The PostToolUse hook: after Claude writes ServiceNow script code, name the calls that
the API reference does not document."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_script_check import TABLE

from snow_docs_mcp import script_hook

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hooks" / "servicenow_script_check.py"
BAD = "var gr = new GlideRecord('incident');\ngr.addEncodedQuerry('active=true');\n"


def payload(tool: str, **tool_input) -> dict:
    return {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": tool_input}


def test_written_edited_and_multi_edited_code_is_read():
    assert script_hook.code_of(payload("Write", file_path="a.js", content=BAD)) == BAD
    assert (
        script_hook.code_of(payload("Edit", file_path="a.js", old_string="x", new_string=BAD))
        == BAD
    )
    multi = payload(
        "MultiEdit", file_path="a.js", edits=[{"new_string": "a();"}, {"new_string": BAD}]
    )
    assert script_hook.code_of(multi) == "a();\n" + BAD
    assert script_hook.code_of(payload("Read", file_path="a.js")) == ""
    assert script_hook.code_of({"tool_name": "Write", "tool_input": "not a dict"}) == ""


def test_an_undocumented_call_becomes_a_note_for_claude():
    note = script_hook.note(payload("Write", file_path="br.js", content=BAD), TABLE, "australia")
    assert "GlideRecord.addEncodedQuerry" in note and "line 2" in note
    assert "GlideRecord.addEncodedQuery" in note and "snow_docs_api" in note
    assert "australia" in note


def test_documented_code_and_other_files_give_no_note():
    good = (
        "var gr = new GlideRecord('incident');\ngr.addEncodedQuery('active=true');\ngr.query();\n"
    )
    assert (
        script_hook.note(payload("Write", file_path="a.js", content=good), TABLE, "australia")
        is None
    )
    assert (
        script_hook.note(payload("Write", file_path="notes.md", content=BAD), TABLE, "australia")
        is None
    )
    assert (
        script_hook.note(payload("Write", file_path="a.py", content="x = 1"), TABLE, "australia")
        is None
    )


def test_a_script_include_in_xml_or_no_extension_is_still_checked():
    for name in ("sys_script_include_abc.xml", "business_rule", "widget.html", "a.ts"):
        assert script_hook.note(
            payload("Write", file_path=name, content=BAD), TABLE, "australia"
        ), name


def run_hook(stdin: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=60,
        check=False,
    )


def test_the_hook_is_silent_without_an_index_when_off_and_on_bad_input(tmp_path):
    body = json.dumps(payload("Write", file_path="a.js", content=BAD))
    home = {"SNOW_DOCS_HOME": str(tmp_path), "SNOW_DOCS_LATEST_URL": "off"}
    for stdin, env in (
        (body, home),
        (body, {**home, "SNOW_DOCS_SCRIPT_HOOK": "off"}),
        ("not json", home),
        ("", home),
    ):
        out = run_hook(stdin, **env)
        assert out.returncode == 0 and out.stdout == "", (stdin[:20], out.stdout, out.stderr[-300:])
    assert not any(tmp_path.iterdir()), "the hook must not start a download"


def test_the_hook_is_wired_after_write_and_edit():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    (entry,) = hooks["PostToolUse"]
    assert entry["matcher"] == "Write|Edit|MultiEdit"
    (hook,) = entry["hooks"]
    assert hook["type"] == "command" and hook["command"] == "uv"
    assert (
        hook["args"][-1] == "hooks/servicenow_script_check.py"
        and "${CLAUDE_PLUGIN_ROOT}" in hook["args"]
    )
    assert SCRIPT.is_file()


def test_readme_says_how_to_turn_it_off():
    assert "SNOW_DOCS_SCRIPT_HOOK=off" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_a_table_the_docs_never_mention_is_named_in_the_note():
    code = "var gr = new GlideRecord('incidnet');\ngr.query();\n"
    text = script_hook.note(
        payload("Write", file_path="a.js", content=code),
        TABLE,
        "australia",
        frozenset({"incident"}),
    )
    assert "table 'incidnet'" in text and "line 1" in text and "incident" in text


def test_a_fluent_file_gets_a_reminder_to_build_and_to_use_explain():
    code = "import { BusinessRule } from '@servicenow/sdk/core'\nBusinessRule({ name: 'x' })\n"
    text = script_hook.note(
        payload("Write", file_path="src/fluent/rule.now.ts", content=code), TABLE, "australia"
    )
    assert "now-sdk build" in text and "snow_docs_sdk_explain" in text
    both = script_hook.note(payload("Write", file_path="a.now.ts", content=BAD), TABLE, "australia")
    assert "GlideRecord.addEncodedQuerry" in both and "now-sdk build" in both


# --- review findings: other people's JavaScript, and edits ----------------------------------

REACT = """import React from "react";

export function List({ list, value, previous }) {
  let current = list.head;
  while (current) {
    current.visit();
    current = current.next;
  }
  const node = new TreeNode(value);
  return previous.equals(node) ? null : <ul />;
}
"""


def test_javascript_that_is_not_servicenow_is_left_alone():
    """`current`, `previous` and `new Foo(` are ordinary JavaScript; they are not a reason to
    read a React component as a business rule (or to load the API table for it)."""
    react = payload("Write", file_path="List.tsx", content=REACT)
    assert not script_hook._worth_a_look(react)
    assert script_hook.note(react, TABLE, "australia") is None
    rule = "(function executeRule(current, previous) {\n    current.addEncodedQuerry('x');\n})();"
    assert script_hook._worth_a_look(payload("Write", file_path="br.js", content=rule))


def test_an_edit_is_checked_in_the_file_it_was_made_in(tmp_path):
    """The edited text alone has no types: `gr` is declared further up in the file."""
    script = tmp_path / "br.js"
    script.write_text(
        "// rule\n\nvar gr = new GlideRecord('incident');\ngr.query();\n"
        "gr.addEncodedQuerry('active=true');\n",
        encoding="utf-8",
    )
    edit = payload(
        "Edit",
        file_path=str(script),
        old_string="gr.addEncodedQuery('active=true');",
        new_string="gr.addEncodedQuerry('active=true');",
    )
    assert script_hook._worth_a_look(edit)
    note = script_hook.note(edit, TABLE, "australia")
    assert note and "GlideRecord.addEncodedQuerry" in note and "line 5" in note


def test_an_edit_does_not_report_what_was_already_in_the_file(tmp_path):
    script = tmp_path / "br.js"
    script.write_text(
        "var gr = new GlideRecord('incident');\ngr.oldMistake();\ngr.query();\n", encoding="utf-8"
    )
    edit = payload("Edit", file_path=str(script), old_string="gr.next();", new_string="gr.query();")
    assert script_hook.note(edit, TABLE, "australia") is None


def test_a_multi_edit_reports_each_edited_place_by_its_line_in_the_file(tmp_path):
    script = tmp_path / "br.js"
    script.write_text(
        "var gr = new GlideRecord('incident');\ngr.frist();\ngr.query();\n\n\ngr.secnd();\n",
        encoding="utf-8",
    )
    multi = payload(
        "MultiEdit",
        file_path=str(script),
        edits=[{"new_string": "gr.frist();"}, {"new_string": "gr.secnd();"}],
    )
    note = script_hook.note(multi, TABLE, "australia")
    assert "GlideRecord.frist() at line 2" in note and "GlideRecord.secnd() at line 6" in note


def test_an_edit_whose_file_cannot_be_read_is_checked_by_its_new_text(tmp_path):
    edit = payload("Edit", file_path=str(tmp_path / "gone.js"), old_string="x", new_string=BAD)
    note = script_hook.note(edit, TABLE, "australia")
    assert note and "GlideRecord.addEncodedQuerry" in note and "line 2" in note


def test_a_very_large_file_is_not_checked():
    """The check must end well inside the hook's timeout; a bundle is not hand-written code."""
    huge = BAD + "gs.info('x');\n" * (script_hook.MAX_CHARS // 14 + 1)
    big = payload("Write", file_path="bundle.js", content=huge)
    assert not script_hook._worth_a_look(big)
    assert script_hook.note(big, TABLE, "australia") is None


def test_the_hooks_never_install_anything():
    """Without --no-sync, the first hook after an install or update makes `uv run` build the
    environment (a large download) inside the hook's 15 to 20 second timeout. The server
    builds it; until then the hooks say nothing."""
    events = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    commands = [hook for groups in events.values() for group in groups for hook in group["hooks"]]
    assert len(commands) == 2
    for hook in commands:
        assert (
            hook["command"] == "uv" and "--no-sync" in hook["args"] and "--frozen" in hook["args"]
        )


def test_the_hook_is_silent_when_the_package_is_not_installed():
    """What --no-sync leaves on a fresh install: a Python without the package."""
    out = subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT)],
        input=json.dumps(payload("Write", file_path="a.js", content=BAD)),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0 and out.stdout == "" and out.stderr == ""
