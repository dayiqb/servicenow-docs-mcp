"""now-sdk in the lookup tool: the setup status and the SDK's own `explain` documentation.

Both only read: the status lists what `now-sdk auth --list` prints (never a user name or a
secret), and explain returns a topic's documentation. A fake `now-sdk` stands in for the CLI.
"""

from __future__ import annotations

import os
import stat

import anyio
import pytest
from mcp import Client

from snow_docs_mcp import sdk
from snow_docs_mcp.server import mcp

FAKE = r"""#!/bin/sh
case "$*" in
  "--version") echo "4.14.0" ;;
  "auth --list")
    echo "[now-sdk] Listing all credentials: "
    echo "[dev1]"
    echo "      host = https://dev1.service-now.com"
    echo "      type = basic"
    echo "      username = admin.secret.name"
    echo "      default = No"
    echo "*[prod]"
    echo "      host = https://prod.service-now.com/"
    echo "      type = oauth"
    echo "      default = Yes" ;;
  "explain --list")
    echo "Available topics:"
    echo ""
    echo "  acl-api  (Acl, acl, access control)"
    echo "  business-rule-guide  (business rule, server script)"
    echo "  businessrule-api  (BusinessRule, business rule, sys_script)" ;;
  "explain --list flow") echo "Available topics:"; echo ""; echo "  flow-api  (Flow, flow designer)" ;;
  "explain businessrule-api --format raw") printf '# BusinessRule\n\nCreates a Business Rule.\n' ;;
  "explain nope --format raw")
    echo "[now-sdk] ERROR: No matching topics for \"nope\""
    echo "[now-sdk] Run \`now-sdk explain --list\` to see all available topics." ;;
  *) echo "unexpected: $*" >&2; exit 9 ;;
esac
"""


@pytest.fixture(autouse=True)
def _no_setup(monkeypatch):
    from snow_docs_mcp import setup

    monkeypatch.setattr(setup, "start", lambda: None)


@pytest.fixture
def fake_sdk(tmp_path, monkeypatch):
    exe = tmp_path / "now-sdk"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return exe


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
    assert sdk.explain("businessrule-api") == "# BusinessRule\n\nCreates a Business Rule.\n"
    assert sdk.explain("nope") is None


def test_the_status_tool_reports_the_setup(fake_sdk):
    r = call("snow_docs_sdk_status")
    assert r["ok"] and r["installed"] and r["version"] == "4.14.0"
    assert [i["alias"] for i in r["instances"]] == ["dev1", "prod"]
    assert "2 instances" in r["message"] and "prod" in r["message"]
    assert "admin.secret.name" not in str(r)


def test_the_explain_tool_reads_a_topic_lists_them_and_suggests(fake_sdk):
    r = call("snow_docs_sdk_explain", topic="businessrule-api")
    assert (
        r["ok"] and r["topic"] == "businessrule-api" and "Creates a Business Rule" in r["content"]
    )
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
    import json

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

BROKEN = r"""#!/bin/sh
case "$*" in
  "--version") echo "4.14.0" ;;
  "auth --list") echo "keychain is locked" >&2; exit 3 ;;
  "explain --list") echo "boom" >&2; exit 3 ;;
  "explain acl-api --format raw") echo "boom" >&2; exit 3 ;;
  *) echo "unexpected: $*" >&2; exit 9 ;;
esac
"""


def _install(tmp_path, monkeypatch, script: str):
    exe = tmp_path / "now-sdk"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return exe


def test_a_failing_instance_list_is_not_reported_as_no_instances(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BROKEN)
    s = sdk.status()
    assert s.installed and s.version == "4.14.0" and "exit 3" in s.error
    r = call("snow_docs_sdk_status")
    assert not r["ok"] and r["installed"] and r["version"] == "4.14.0"
    assert "No instance is configured" not in r["message"]
    assert "auth --list" in r["message"] and "exit 3" in r["message"]


def test_a_timed_out_instance_list_is_not_reported_as_no_instances(tmp_path, monkeypatch):
    slow = BROKEN.replace('echo "keychain is locked" >&2; exit 3', "sleep 5")
    _install(tmp_path, monkeypatch, slow)
    monkeypatch.setattr(sdk, "TIMEOUT_SECONDS", 0.3)
    r = call("snow_docs_sdk_status")
    assert not r["ok"] and "timed out" in r["message"]
    assert "No instance is configured" not in r["message"]


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
    works = FAKE.replace('"auth --list")', '"auth --list") exit 7 ;;\n  "never")')
    _install(tmp_path, monkeypatch, works)
    r = call("snow_docs_sdk_explain", topic="businessrule-api")
    assert r["ok"] and r["version"] == "4.14.0" and "Creates a Business Rule" in r["content"]


def test_the_sdk_never_reads_the_servers_standard_input(tmp_path, monkeypatch):
    """The MCP server talks JSON-RPC on stdin; a child that reads it would eat a request."""
    _install(tmp_path, monkeypatch, "#!/bin/sh\ncat\necho 4.14.0\n")
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
