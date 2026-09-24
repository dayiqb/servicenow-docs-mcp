"""The Claude Desktop bundle manifest must describe the server that actually ships."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import anyio
from mcp import Client

from snow_docs_mcp.server import ANSWER_RULES, __version__, mcp

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_versions_agree() -> None:
    assert MANIFEST["version"] == PYPROJECT["project"]["version"] == __version__


def test_manifest_lists_exactly_the_registered_tools_and_prompts() -> None:
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools(), await client.list_prompts()

    tools, prompts = anyio.run(go)
    assert sorted(t["name"] for t in MANIFEST["tools"]) == sorted(t.name for t in tools.tools)
    assert [p["name"] for p in MANIFEST["prompts"]] == [p.name for p in prompts.prompts]


def test_manifest_prompt_text_is_the_servers_answer_rules() -> None:
    (prompt,) = MANIFEST["prompts"]
    assert prompt["arguments"] == ["question"]
    assert prompt["text"] == f"{ANSWER_RULES}\n\nQuestion: ${{arguments.question}}"


def test_uv_server_config_is_runnable() -> None:
    server = MANIFEST["server"]
    assert MANIFEST["manifest_version"] == "0.4" and server["type"] == "uv"
    assert (ROOT / server["entry_point"]).is_file()
    args = server["mcp_config"]["args"]
    assert args[:4] == ["run", "--frozen", "--directory", "${__dirname}"]
    assert args[4] == server["entry_point"]
    assert server["mcp_config"]["env"]["SNOW_DOCS_HOME"] == "${user_config.data_folder}"
    assert MANIFEST["user_config"]["data_folder"]["type"] == "directory"
    assert (
        MANIFEST["compatibility"]["runtimes"]["python"] == PYPROJECT["project"]["requires-python"]
    )


PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
MARKET = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))


def test_plugin_and_marketplace_describe_this_version() -> None:
    assert PLUGIN["name"] == "servicenow-docs" and PLUGIN["version"] == __version__
    (entry,) = MARKET["plugins"]
    assert entry["name"] == PLUGIN["name"] and entry["version"] == __version__
    assert entry["source"] == "./", "the repo root is the plugin"


def test_plugin_launches_the_server_from_its_own_folder() -> None:
    server = PLUGIN["mcpServers"]["servicenow-docs"]
    assert server["command"] == "uv"
    args = server["args"]
    assert args[:2] == ["run", "--frozen"]
    assert "${CLAUDE_PLUGIN_ROOT}" in args
    assert (ROOT / args[-1]).is_file(), "the launcher script exists"


def test_plugin_skill_exists_and_names_the_tools() -> None:
    skill = (ROOT / "skills" / "servicenow-docs" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: servicenow-docs\ndescription: ")
    for tool in ("snow_docs_search", "snow_docs_read", "snow_docs_status"):
        assert tool in skill


def test_latest_json_seed_matches_the_builtin_entry() -> None:
    from snow_docs_mcp import config

    latest = json.loads((ROOT / "index" / "latest.json").read_text(encoding="utf-8"))
    assert latest["schema"] == 1
    au = config.IndexEntry.from_json("australia", latest["indexes"]["australia"])
    assert au == config.BUILTIN_ENTRIES["australia"]


def test_prompt_hook_is_wired_in_exec_form() -> None:
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    (group,) = hooks["hooks"]["UserPromptSubmit"]
    (hook,) = group["hooks"]
    assert hook["type"] == "command" and hook["command"] == "uv"
    assert "args" in hook, "exec form: no shell, so Windows quoting/profiles can't break it"
    assert "${CLAUDE_PLUGIN_ROOT}" in hook["args"]
    assert (ROOT / hook["args"][-1]).is_file()
