"""now-sdk in the lookup tool: the setup status and the SDK's own `explain` documentation.

Both only read: the status lists what `now-sdk auth --list` prints (never a user name or a
secret), and explain returns a topic's documentation. A fake `now-sdk` stands in for the CLI.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time

import anyio
import pytest
from mcp import Client

from snow_docs_mcp import sdk
from snow_docs_mcp.server import mcp

WINDOWS = sys.platform == "win32"

# The fake SDK: a Python program that answers from a table, keyed by its arguments. Each answer
# has `out` (written as UTF-8, as Node writes it), `err`, `code`, and optionally `sleep` seconds
# and `stdin` (echo what it reads). It writes its process id to `pid` beside the table.
PROGRAM = r"""
import json, os, sys, time
table = sys.argv[1]
with open(os.path.join(os.path.dirname(table), "pid"), "w") as f:
    f.write(str(os.getpid()))
answers = json.load(open(table, encoding="utf-8"))
key = " ".join(sys.argv[2:])
a = answers.get(key, {"err": "unexpected: " + key, "code": 9})
if a.get("stdin"):
    sys.stdout.write(sys.stdin.read())
    sys.stdout.flush()
time.sleep(a.get("sleep", 0))
sys.stdout.buffer.write(a.get("out", "").encode("utf-8"))
sys.stdout.flush()
sys.stderr.write(a.get("err", ""))
sys.exit(a.get("code", 0))
"""

LISTING = """[now-sdk] Listing all credentials:
[dev1]
      host = https://dev1.service-now.com
      type = basic
      username = admin.secret.name
      default = No
*[prod]
      host = https://prod.service-now.com/
      type = oauth
      default = Yes
"""

TOPICS = """Available topics:

  acl-api  (Acl, acl, access control)
  business-rule-guide  (business rule, server script)
  businessrule-api  (BusinessRule, business rule, sys_script)
"""

# The SDK's documentation is not all ASCII: a dash and an ellipsis, as Fluent's docs have.
BUSINESS_RULE = "# BusinessRule\n\nCreates a Business Rule — on the server…\n"

FAKE = {
    "--version": {"out": "4.14.0\n"},
    "auth --list": {"out": LISTING},
    "explain --list": {"out": TOPICS},
    "explain --list flow": {"out": "Available topics:\n\n  flow-api  (Flow, flow designer)\n"},
    "explain businessrule-api --format raw": {"out": BUSINESS_RULE},
    "explain nope --format raw": {
        "out": '[now-sdk] ERROR: No matching topics for "nope"\n'
        "[now-sdk] Run `now-sdk explain --list` to see all available topics.\n"
    },
}

BROKEN = {
    "--version": {"out": "4.14.0\n"},
    "auth --list": {"err": "keychain is locked\n", "code": 3},
    "explain --list": {"err": "boom\n", "code": 3},
    "explain acl-api --format raw": {"err": "boom\n", "code": 3},
}


def _install(tmp_path, monkeypatch, answers: dict) -> None:
    """Put a fake `now-sdk` first on the PATH, shaped like the one npm installs.

    On Windows that is `now-sdk.cmd`, which starts the program as a child of cmd.exe; elsewhere
    a shell script that does the same, so the program is a grandchild there too.
    """
    table = tmp_path / "answers.json"
    table.write_text(json.dumps(answers), encoding="utf-8")
    program = tmp_path / "fake_sdk.py"
    program.write_text(PROGRAM, encoding="utf-8")
    if WINDOWS:
        (tmp_path / "now-sdk.cmd").write_text(
            f'@"{sys.executable}" "{program}" "{table}" %*\r\n', encoding="utf-8"
        )
    else:
        exe = tmp_path / "now-sdk"
        exe.write_text(f'#!/bin/sh\n"{sys.executable}" "{program}" "{table}" "$@"\n')
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")


def _running(pid: int) -> bool:
    if WINDOWS:
        found = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return str(pid) in found
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture(autouse=True)
def _no_setup(monkeypatch):
    from snow_docs_mcp import setup

    monkeypatch.setattr(setup, "start", lambda: None)


@pytest.fixture
def fake_sdk(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, FAKE)


def call(tool: str, **args):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_status_lists_the_version_and_instances_without_user_names(fake_sdk):
    s = sdk.status()
    assert s.installed and s.version == "4.14.0"
    assert [(i.alias, i.host, i.auth_type, i.default) for i in s.instances] == [
        ("dev1", "https://dev1.service-now.com", "basic", False),
        ("prod", "https://prod.service-now.com", "oauth", True),
    ]
    assert "admin.secret.name" not in repr(s)


def test_status_says_when_the_sdk_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    s = sdk.status()
    assert not s.installed and s.instances == [] and "npm" in s.message


def test_only_the_three_read_only_commands_are_ever_run(fake_sdk):
    with pytest.raises(ValueError):
        sdk._run(["auth", "--add", "x"])
    with pytest.raises(ValueError):
        sdk._run(["query", "incident"])
    with pytest.raises(ValueError):
        sdk._run(["auth", "--print"])


def test_explain_lists_topics_reads_one_and_reports_an_unknown_one(fake_sdk):
    topics = sdk.topics()
    assert [t.name for t in topics] == ["acl-api", "business-rule-guide", "businessrule-api"]
    assert topics[2].keywords == "BusinessRule, business rule, sys_script"
    assert [t.name for t in sdk.topics("flow")] == ["flow-api"]
    assert sdk.explain("businessrule-api") == BUSINESS_RULE
    assert sdk.explain("nope") is None


def test_the_status_tool_reports_the_setup(fake_sdk):
    r = call("snow_docs_sdk_status")
    assert r["ok"] and r["installed"] and r["version"] == "4.14.0"
    assert [i["alias"] for i in r["instances"]] == ["dev1", "prod"]
    assert "2 instances" in r["message"] and "prod" in r["message"]
    assert "admin.secret.name" not in str(r)


def test_the_explain_tool_reads_a_topic_lists_them_and_suggests(fake_sdk):
    r = call("snow_docs_sdk_explain", topic="businessrule-api")
    assert r["ok"] and r["topic"] == "businessrule-api" and r["content"] == BUSINESS_RULE
    listing = call("snow_docs_sdk_explain")
    assert listing["ok"] and len(listing["topics"]) == 3 and listing["content"] == ""
    miss = call("snow_docs_sdk_explain", topic="nope")
    assert miss["ok"] and miss["content"] == "" and "No topic" in miss["message"]
    name = call("snow_docs_sdk_explain", topic="BusinessRule")  # a keyword finds its topic
    assert name["topic"] == "businessrule-api" and name["content"]


def test_tools_explain_a_missing_sdk(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert not call("snow_docs_sdk_explain", topic="x")["ok"]
    r = call("snow_docs_sdk_status")
    assert r["ok"] and not r["installed"]


def test_the_command_line_and_the_library_have_them_too(fake_sdk, capsys):
    from snow_docs_mcp import api
    from snow_docs_mcp.server import main

    with pytest.raises(SystemExit) as done:
        main(["sdk-status"])
    assert done.value.code == 0 and json.loads(capsys.readouterr().out)["version"] == "4.14.0"
    with pytest.raises(SystemExit) as done:
        main(["sdk-explain", "businessrule-api"])
    assert (
        done.value.code == 0
        and "Creates a Business Rule" in json.loads(capsys.readouterr().out)["content"]
    )
    assert api.sdk_status().installed and api.sdk_explain("businessrule-api").content


# --- failures are reported as failures, not as facts ---------------------------------------


def test_a_failing_instance_list_is_not_reported_as_no_instances(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BROKEN)
    s = sdk.status()
    assert s.installed and s.version == "4.14.0" and "exit 3" in s.error
    r = call("snow_docs_sdk_status")
    assert not r["ok"] and r["installed"] and r["version"] == "4.14.0"
    assert "No instance is configured" not in r["message"]
    assert "auth --list" in r["message"] and "exit 3" in r["message"]


def test_a_timed_out_instance_list_is_not_reported_as_no_instances(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {**BROKEN, "auth --list": {"sleep": 30}})
    monkeypatch.setattr(sdk, "TIMEOUT_SECONDS", 2)
    r = call("snow_docs_sdk_status")
    assert not r["ok"] and "timed out" in r["message"]
    assert "No instance is configured" not in r["message"]


def test_a_command_that_hangs_is_stopped_with_what_it_started(tmp_path, monkeypatch):
    """npm's now-sdk is a wrapper that starts Node. Stopping only the wrapper leaves Node
    running, and on Windows the call then waits for Node instead of giving up."""
    _install(tmp_path, monkeypatch, {"auth --list": {"sleep": 30}})
    monkeypatch.setattr(sdk, "TIMEOUT_SECONDS", 2)
    started = time.monotonic()
    with pytest.raises(sdk.SdkError, match="timed out"):
        sdk._run(["auth", "--list"])
    assert time.monotonic() - started < 10
    pid = int((tmp_path / "pid").read_text())
    deadline = time.monotonic() + 5
    while _running(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _running(pid)


def test_a_failing_topic_list_is_not_reported_as_an_unknown_topic(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BROKEN)
    with pytest.raises(sdk.SdkError):
        sdk.topics()
    r = call("snow_docs_sdk_explain", topic="x")
    assert not r["ok"] and "No topic" not in r["message"]
    assert "explain --list" in r["message"] and "exit 3" in r["message"]


def test_a_failing_explain_is_not_reported_as_a_missing_topic(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BROKEN)
    with pytest.raises(sdk.SdkError):
        sdk.explain("acl-api")


def test_explain_does_not_need_the_instance_list(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {**FAKE, "auth --list": {"code": 7}})
    r = call("snow_docs_sdk_explain", topic="businessrule-api")
    assert r["ok"] and r["version"] == "4.14.0" and "Creates a Business Rule" in r["content"]


def test_the_sdk_never_reads_the_servers_standard_input(tmp_path, monkeypatch):
    """The MCP server talks JSON-RPC on stdin; a child that reads it would eat a request."""
    _install(tmp_path, monkeypatch, {"--version": {"stdin": True, "out": "4.14.0\n"}})
    read_end, write_end = os.pipe()
    os.write(write_end, b"REQUEST-LINE\n")
    os.close(write_end)
    saved = os.dup(0)
    try:
        os.dup2(read_end, 0)
        out = sdk._run(["--version"])
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(read_end)
    assert "REQUEST-LINE" not in out and "4.14.0" in out
