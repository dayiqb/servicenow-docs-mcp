"""The Claude Code plugin and its panes.

One plugin carries the docs server, the two hooks, the figures pane and the ServiceNow SDK
panel, so one install gives all of it. A plugin has one hooks module, and one hook for an event:
the module at hooks/register.tsx sets up both panes, and the SDK panel unless its setting is
turned off, because it can run SDK commands and the rest of the plugin only reads."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
MARKET = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
FIGURES = ROOT / "panes" / "figures"
SDK = ROOT / "panes" / "sdk-panel"
CLAUDE = shutil.which("claude")
NODE = shutil.which("node")
TSC = shutil.which("tsc")
# Claude Code writes its types here when it loads the plugin from this folder.
LAID = ROOT / ".claude-plugin" / "types" / "tsconfig.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_one_plugin_is_offered_and_it_loads_one_hooks_module() -> None:
    assert [p["name"] for p in MARKET["plugins"]] == ["servicenow-docs"]
    hooks = json.loads(_read(ROOT / "hooks" / "hooks.json"))
    assert hooks["modules"] == ["./register.tsx"]
    assert set(hooks["hooks"]) == {"UserPromptSubmit", "PostToolUse"}  # the two command hooks stay
    assert PLUGIN["types"] == "./types/index.d.ts"
    assert not (ROOT / "mods").exists()


def test_the_sdk_panel_is_a_setting_and_on_until_it_is_turned_off() -> None:
    """The panel runs now-sdk commands after a confirmation; everything else in the plugin only
    reads. So it is a setting: on as installed, and turned off for a plugin that only reads."""
    option = PLUGIN["userConfig"]["sdk_panel"]
    assert (option["type"], option["title"]) == ("boolean", "ServiceNow SDK panel")
    assert option["default"] is True
    assert "now-sdk" in option["description"] and "confirm" in option["description"]
    assert "Turn it off" in option["description"]
    assert "options.sdk_panel !== false" in _read(ROOT / "hooks" / "register.tsx")


def test_each_event_has_one_hook_in_the_plugin() -> None:
    """A second hook for the same event and matcher keeps the whole module from loading."""
    root = _read(ROOT / "hooks" / "register.tsx")
    panes = [_read(FIGURES / "pane.tsx"), _read(SDK / "pane.tsx")]
    assert root.count("on('session.start'") == 1
    for pane in panes:
        assert "on('session.start'" not in pane and "export async function start(" in pane
    commands = re.findall(r"on\('command\.run', \{ command: '([\w-]+)' \}", "".join(panes))
    assert sorted(commands) == ["docs-figures", "sdk-panel"]
    panes_drawn = re.findall(r"const PANE = '([\w-]+)'", "".join(panes))
    assert sorted(panes_drawn) == ["docs-figures", "sdk-panel"]


def test_the_state_contract_is_the_plugins_own() -> None:
    types = _read(ROOT / "types" / "index.d.ts")
    # the contract is one file that reaches nowhere else
    assert not re.search(r"^\s*(import\b|export .* from|/// <reference)", types, re.MULTILINE)
    block = re.search(r"'servicenow-docs': \{([^}]*)\}", types).group(1)
    assert sorted(re.findall(r"(\w+): Shaped<", block)) == ["book", "data", "view"]
    refs = re.findall(
        r"\{ plugin: '([\w-]+)', key: '(\w+)' \} as const",
        _read(FIGURES / "pane.tsx") + _read(SDK / "pane.tsx"),
    )
    assert sorted(refs) == [
        ("servicenow-docs", "book"),
        ("servicenow-docs", "data"),
        ("servicenow-docs", "view"),
    ]
    assert "mcp__servicenow-docs__show_figure" in _read(FIGURES / "pane.test.tsx")


def test_the_sdk_panel_says_where_it_is_taken_from() -> None:
    """The panel is developed in its own repository; this copy is taken from a named commit by a
    script, so taking a newer one is the same step again."""
    source = _read(SDK / "SOURCE.md")
    assert re.search(r"commit `[0-9a-f]{7,40}`", source) and "import_sdk_panel.py" in source
    assert (ROOT / "scripts" / "import_sdk_panel.py").is_file()
    assert json.loads(_read(SDK / "package.json"))["type"] == "module"


def test_the_panes_stay_out_of_the_desktop_extension() -> None:
    ignored = _read(ROOT / ".mcpbignore").split()
    assert "panes/" in ignored and "types/" in ignored and "mods/" not in ignored


def test_readme_tells_about_both_panes_and_the_setting() -> None:
    readme = _read(ROOT / "README.md")
    for said in ("/docs-figures", "/sdk-panel", "ServiceNow SDK panel"):
        assert said in readme, said
    assert "mods/" not in readme and "--plugin-dir" not in readme and "in preview" not in readme
    assert "on as installed" in readme and "turn it off" in readme.lower()
    assert "off until" not in readme and "off as installed" not in readme


def test_readme_gives_two_downloads() -> None:
    """The extension for the docs tools, the plugin for what only Claude Code has."""
    readme = _read(ROOT / "README.md")
    assert "Two downloads" in readme
    assert "starts no server of its own" in readme
    assert "One install gives all of it" not in readme
    assert "claude mcp add" in readme  # Claude Code without Claude Desktop


def test_the_sdk_panel_looks_for_the_docs_where_they_are_installed() -> None:
    """The plugin has no docs environment of its own: looked for in the plugin's folder, the
    docs would be found by their version file and then fail to run."""
    assert "$.plugin.root" not in _read(SDK / "pane.tsx")
    assert "Claude Extensions" in _read(SDK / "pane.tsx")


@pytest.mark.skipif(CLAUDE is None, reason="the claude command line is not installed")
def test_the_plugin_validates_and_its_pane_tests_pass() -> None:
    def run(*args: str) -> str:
        done = subprocess.run(
            [CLAUDE, "plugin", *args, str(ROOT)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return done.stdout + done.stderr

    assert "Validation passed" in run("validate")
    tested = run("test")
    assert re.search(r"\b0 fail\b", tested), tested[-2000:]
    assert int(re.search(r"\b(\d+) pass\b", tested).group(1)) >= 30


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_sdk_panels_core_passes_its_own_tests() -> None:
    tests = sorted(str(p) for p in (SDK / "test").glob("*.test.js"))
    assert len(tests) >= 8
    done = subprocess.run(
        [NODE, "--test", *tests], cwd=SDK, capture_output=True, text=True, timeout=300, check=False
    )
    assert done.returncode == 0, (done.stdout + done.stderr)[-2000:]


def test_the_type_check_of_the_panes_reads_the_sdk_panels_core() -> None:
    """The SDK panel's core is JavaScript with its types in JSDoc. A check that does not read it
    leaves every import from it untyped, and the pane then fails in dozens of places."""
    config = json.loads(_read(ROOT / "tsconfig.json"))
    assert config["extends"] == "./.claude-plugin/types/tsconfig.json"
    options = config["compilerOptions"]
    assert options["allowJs"] is True and options["checkJs"] is False
    assert options["allowImportingTsExtensions"] is True  # the module imports panes/*/pane.tsx
    # The pane files, not all of panes/: the core is read through their imports, and the
    # panel's Node tests ask for a check of their own that needs Node's types.
    assert config["include"] == [
        "hooks",
        "types",
        "panes/figures",
        "panes/sdk-panel/pane.tsx",
        "panes/sdk-panel/pane.test.tsx",
    ]
    assert ".claude-plugin/types/" in _read(ROOT / ".gitignore").split()
    assert "tsconfig.json" in _read(ROOT / ".mcpbignore").split()
    assert "tsc -p ." in _read(ROOT / "README.md")


@pytest.mark.skipif(
    TSC is None or not LAID.is_file(),
    reason="needs tsc, and the types Claude Code writes when it loads the plugin from here",
)
def test_the_strict_type_check_of_the_panes_is_clean() -> None:
    done = subprocess.run(
        [TSC, "-p", str(ROOT)], capture_output=True, text=True, timeout=300, check=False
    )
    assert done.returncode == 0, (done.stdout + done.stderr)[-2000:]
