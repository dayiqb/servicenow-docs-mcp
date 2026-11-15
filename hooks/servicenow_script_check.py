"""PostToolUse hook: check the ServiceNow script code Claude just wrote against the API
reference (see snow_docs_mcp.script_hook). Never blocks: any problem means exit 0, silent.

The check needs the docs code and the Python environment it runs in. The plugin starts no docs
server, so its own folder has neither, unless it is a checkout someone set up. The check then
runs where the docs are installed: the ServiceNow Docs extension of Claude Desktop.

Standard library only, and no import of the docs code at the top: this file must load in a
Python that has nothing installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

EXTENSION = "servicenow-docs"  # the name in the extension's manifest
RUN = "import sys; from snow_docs_mcp.script_hook import main; sys.exit(main())"


def extensions_dir(platform: str = sys.platform) -> Path:
    """Where Claude Desktop keeps the extensions it has installed."""
    if platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Claude" / "Claude Extensions"


def docs_extension(folder: Path) -> Path | None:
    """The installed ServiceNow Docs extension that has been started (so it has its
    environment), or None."""
    try:
        found = sorted(entry for entry in folder.iterdir() if entry.is_dir())
    except OSError:
        return None
    for entry in found:
        try:
            manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        named = isinstance(manifest, dict) and manifest.get("name") == EXTENSION
        if named and (entry / ".venv").is_dir():
            return entry
    return None


def command(folder: Path) -> list[str]:
    """The check, run in the docs' own folder with the environment it already has."""
    return [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "--quiet",
        "--directory",
        str(folder),
        "python",
        "-c",
        RUN,
    ]


def in_the_extension() -> int:
    folder = docs_extension(extensions_dir())
    if folder is None:
        return 0
    # uv names this folder's environment to what it starts; the extension has its own.
    env = {name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}
    done = subprocess.run(
        command(folder),
        input=sys.stdin.read(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=15,
        check=False,
    )
    if done.returncode == 0:
        sys.stdout.write(done.stdout)
    return 0


def main() -> int:
    try:
        from snow_docs_mcp.script_hook import main as check  # a checkout with its environment
    except ImportError:
        return in_the_extension()
    return check()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a hook must never fail the tool call it follows
        sys.exit(0)
