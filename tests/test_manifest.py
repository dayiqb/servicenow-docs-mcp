"""The Claude Desktop bundle manifest must describe the server that actually ships."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import anyio
from mcp import Client

from snow_docs_mcp import config
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
    prompt = next(p for p in MANIFEST["prompts"] if p["name"] == "answer")
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
    # the marketplace is named like its repo: Claude Desktop names a marketplace added by repo
    # after the repo, and its Update button then asks for that name (0.1.4's differed:
    # "Couldn't check for updates", MARKETPLACE_ERROR:NOT_REGISTERED)
    assert MARKET["name"] == "servicenow-docs-mcp" == config.REPO.split("/")[1]
    (entry,) = MARKET["plugins"]
    assert entry["name"] == PLUGIN["name"] and entry["version"] == __version__
    assert entry["source"] == "./", "the repo root is the plugin"


def test_plugin_launches_the_server_from_its_own_folder() -> None:
    server = PLUGIN["mcpServers"]["servicenow-docs"]
    assert server["command"] == "uv"
    args = server["args"]
    assert args[0] == "run" and "--frozen" in args  # the locked dependencies, never re-resolved
    assert "${CLAUDE_PLUGIN_ROOT}" in args
    assert (ROOT / args[-1]).is_file(), "the launcher script exists"


def test_plugin_skill_exists_and_names_the_tools() -> None:
    skill = (ROOT / "skills" / "servicenow-docs" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: servicenow-docs\ndescription: ")
    for tool in (
        "snow_docs_search",
        "snow_docs_read",
        "snow_docs_compare",
        "snow_docs_api",
        "snow_docs_browse",
        "snow_docs_open",
        "snow_docs_sdk_status",
        "snow_docs_sdk_explain",
        "snow_docs_check_script",
        "snow_docs_status",
    ):
        assert tool in skill


def test_latest_json_is_well_formed_and_never_behind_the_builtin_entry() -> None:
    """A new docs index is published by editing latest.json alone, so it moves ahead of the
    server's built-in entry (which stays as the known-good fallback); it must never point
    behind it, and every entry must be usable by this server version."""
    from snow_docs_mcp import config, setup

    latest = json.loads((ROOT / "index" / "latest.json").read_text(encoding="utf-8"))
    assert latest["schema"] == 1
    assert set(config.BUILTIN_ENTRIES) <= set(latest["indexes"])
    for release, raw in latest["indexes"].items():
        entry = config.IndexEntry.from_json(release, raw)
        builtin = config.BUILTIN_ENTRIES.get(release)
        if builtin is not None:
            assert entry.snapshot >= builtin.snapshot
            if entry.snapshot == builtin.snapshot:
                assert entry == builtin
        assert entry.url.startswith(f"https://github.com/{config.REPO}/releases/download/")
        assert entry.url.endswith(f"-{entry.gz_sha256[:12]}.db.gz"), "content-addressed name"
        assert len(entry.gz_sha256) == 64 and len(entry.db_sha256) == 64
        assert entry.gz_bytes and entry.db_bytes and entry.chunks
        assert setup._compatible(entry)


def test_prompt_hook_is_wired_in_exec_form() -> None:
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    (group,) = hooks["hooks"]["UserPromptSubmit"]
    (hook,) = group["hooks"]
    assert hook["type"] == "command" and hook["command"] == "uv"
    assert "args" in hook, "exec form: no shell, so Windows quoting/profiles can't break it"
    assert "${CLAUDE_PLUGIN_ROOT}" in hook["args"]
    assert (ROOT / hook["args"][-1]).is_file()


# Claude Desktop runs plugin servers on the host (and bridges them into Cowork) only if their
# `env` avoids the names it reserves; one reserved name and the server never starts (2026-09-28:
# 'env declares reserved variable name "UV_SYSTEM_CERTS"'). Desktop's rule, as shipped then:
DESKTOP_RESERVED_PREFIXES = (
    "CLAUDE_",
    "ANTHROPIC_",
    "OTEL_",
    "LD_",
    "DYLD_",
    "BASH_FUNC_",
    "GIT_",
    "NPM_CONFIG_",
    "UV_",
)
DESKTOP_RESERVED_NAMES = {
    "PATH",
    "HOME",
    "PYTHONPATH",
    "PYTHONHOME",
    "SSL_CERT_FILE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "TMPDIR",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "NODE_EXTRA_CA_CERTS",
}


def test_plugin_server_and_hooks_avoid_desktop_reserved_env_names() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    envs = [srv.get("env", {}) for srv in plugin["mcpServers"].values()]
    envs += [h.get("env", {}) for g in hooks["hooks"].values() for e in g for h in e["hooks"]]
    for env in envs:
        for name in env:
            upper = name.upper()
            assert upper not in DESKTOP_RESERVED_NAMES, name
            assert not upper.startswith(DESKTOP_RESERVED_PREFIXES), name
    # system certificates for uv's own downloads, as a flag instead (any uv version)
    assert plugin["mcpServers"]["servicenow-docs"]["args"][:2] == ["run", "--native-tls"]


def test_version_is_2_1_1_everywhere() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    versions = {__version__, MANIFEST["version"], plugin["version"]}
    versions |= {p["version"] for p in market["plugins"]}
    assert versions == {"2.1.1"}


def test_instructions_and_readme_name_the_compare_tool() -> None:
    assert "snow_docs_compare" in ANSWER_RULES
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "snow_docs_compare" in readme and "## Compare releases" in readme


def test_upgrade_review_text_is_the_same_in_prompt_manifest_and_skill() -> None:
    from snow_docs_mcp.server import UPGRADE_REVIEW_RULES

    prompt = next(p for p in MANIFEST["prompts"] if p["name"] == "upgrade_review")
    assert prompt["arguments"] == ["product"]
    assert prompt["text"] == f"{UPGRADE_REVIEW_RULES}\n\nProduct: ${{arguments.product}}"
    skill = (ROOT / "skills" / "servicenow-upgrade-review" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: servicenow-upgrade-review\ndescription: ")
    assert UPGRADE_REVIEW_RULES in skill
    for needed in ("snow_docs_compare", "snow_docs_read", "No updates for this release", "[id]"):
        assert needed in UPGRADE_REVIEW_RULES
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "upgrade_review" in readme and "servicenow-upgrade-review" in readme


def test_instructions_and_readme_name_the_api_tool() -> None:
    assert "snow_docs_api" in ANSWER_RULES
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "snow_docs_api" in readme and "## API lookup" in readme


def test_setup_checklist_text_is_the_same_in_prompt_manifest_and_skill() -> None:
    from snow_docs_mcp.server import SETUP_CHECKLIST_RULES

    prompt = next(p for p in MANIFEST["prompts"] if p["name"] == "setup_checklist")
    assert prompt["arguments"] == ["feature"]
    assert prompt["text"] == f"{SETUP_CHECKLIST_RULES}\n\nFeature: ${{arguments.feature}}"
    skill = (ROOT / "skills" / "servicenow-setup-checklist" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: servicenow-setup-checklist\ndescription: ")
    assert SETUP_CHECKLIST_RULES in skill
    for needed in ("snow_docs_search", "snow_docs_browse", "snow_docs_read", "[id]", "Before you start"):
        assert needed in SETUP_CHECKLIST_RULES
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "setup_checklist" in readme and "servicenow-setup-checklist" in readme


def test_plugin_commands_carry_the_recipes_word_for_word() -> None:
    from snow_docs_mcp.server import SETUP_CHECKLIST_RULES, UPGRADE_REVIEW_RULES

    for name, rules, argument in (
        ("upgrade-review", UPGRADE_REVIEW_RULES, "Product: $ARGUMENTS"),
        ("setup-checklist", SETUP_CHECKLIST_RULES, "Feature: $ARGUMENTS"),
    ):
        text = (ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith("---\ndescription: ") and "argument-hint: " in text.split("---")[1]
        assert rules in text and text.rstrip().endswith(argument)


def test_plugin_agent_names_the_tools_it_should_use() -> None:
    text = (ROOT / "agents" / "servicenow-docs-researcher.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: servicenow-docs-researcher\ndescription: ")
    for tool in ("snow_docs_search", "snow_docs_read", "snow_docs_api", "snow_docs_check_script", "snow_docs_compare"):
        assert tool in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "servicenow-docs-researcher" in readme and "/servicenow-docs:upgrade-review" in readme


def test_the_desktop_extension_leaves_out_the_claude_code_only_folders() -> None:
    ignored = (ROOT / ".mcpbignore").read_text(encoding="utf-8").split()
    for folder in ("skills/", "hooks/", "agents/", "commands/", "mods/"):
        assert folder in ignored


def test_the_figures_pane_mod_is_complete_and_not_yet_offered_for_install() -> None:
    mod = ROOT / "mods" / "servicenow-docs-figures"
    manifest = json.loads((mod / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "servicenow-docs-figures" and manifest["version"] == __version__
    # Not in the marketplace until it has been seen working in Claude Code: the marketplace
    # file is what Claude Desktop reads, and it has exactly one plugin today.
    assert [p["name"] for p in MARKET["plugins"]] == ["servicenow-docs"]
    assert json.loads((mod / "hooks" / "hooks.json").read_text(encoding="utf-8")) == {"modules": ["./register.tsx"]}
    module = (mod / "hooks" / "register.tsx").read_text(encoding="utf-8")
    # Claude draws; the pane shows. Nothing is drawn for a search or a read.
    assert "show_figure" in module and "snow_docs_" not in module
    assert (mod / "hooks" / "register.test.tsx").is_file()
    assert (mod / "types" / "index.d.ts").is_file() and (mod / "README.md").is_file()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "servicenow-docs-figures" in readme and "/docs-figures" in readme
    assert "servicenow-docs-sources" not in readme and "/docs-sources" not in readme


def test_the_bundle_holds_only_what_the_extension_needs() -> None:
    """Local folders that git never sees (.claude with other sessions' worktrees, .superpowers
    with scratch files) were packed into the bundle: 524 KB instead of 220. They are ignored
    by name, and the build fails on anything that is not on its list."""
    ignored = (ROOT / ".mcpbignore").read_text(encoding="utf-8").split()
    for folder in (".claude/", ".superpowers/"):
        assert folder in ignored
    build = (ROOT / "scripts" / "build_mcpb.sh").read_text(encoding="utf-8")
    assert "ALLOWED=" in build and "not on the list" in build
    allowed = build.split('ALLOWED="', 1)[1].split('"', 1)[0].split()
    assert sorted(allowed) == sorted(
        [
            "src",
            "server",
            "manifest.json",
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "NOTICE",
            "LICENSE",
            ".python-version",
        ]
    )
