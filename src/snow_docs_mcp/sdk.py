"""The ServiceNow SDK (`now-sdk`) as something to look up: is it set up, and what does its
own documentation say?

Only three commands are ever run, and all three only read: `now-sdk --version`,
`now-sdk auth --list` (which instances are configured) and `now-sdk explain` (the SDK's
documentation for the installed version). Nothing here contacts an instance, changes the
SDK's configuration or sees a secret; user names are left out of the status on purpose.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

EXECUTABLE = "now-sdk"
TIMEOUT_SECONDS = 30
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ALIAS = re.compile(r"^(\*?)\[(.+)\]\s*$")
_PAIR = re.compile(r"^\s+(\w+)\s*=\s*(.*?)\s*$")
_TOPIC = re.compile(r"^\s{2}(\S+)\s*(?:\((.*)\))?\s*$")


@dataclass(frozen=True)
class Instance:
    alias: str
    host: str
    auth_type: str
    default: bool


@dataclass
class Status:
    installed: bool
    version: str = ""
    path: str = ""
    instances: list[Instance] = field(default_factory=list)
    message: str = ""


@dataclass(frozen=True)
class Topic:
    name: str
    keywords: str


def _allowed(args: list[str]) -> bool:
    """`--version`, `auth --list`, and `explain` with a topic or `--list`: reads only."""
    if args in (["--version"], ["auth", "--list"]):
        return True
    return args[:1] == ["explain"] and all(
        a in ("--list", "--format", "raw") or not a.startswith("-") for a in args[1:]
    )


def _run(args: list[str]) -> str:
    """Output of one of the read-only commands ("" when the SDK is missing or it fails)."""
    if not _allowed(args):
        raise ValueError(f"not a read-only now-sdk command: {' '.join(args)}")
    exe = shutil.which(EXECUTABLE)
    if exe is None:
        return ""
    try:
        done = subprocess.run(
            [exe, *args], capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return _ANSI.sub("", done.stdout)


def status() -> Status:
    """Whether the SDK is installed, its version, and the instances it has credentials for."""
    exe = shutil.which(EXECUTABLE)
    if exe is None:
        return Status(
            installed=False,
            message="The ServiceNow SDK is not installed (no `now-sdk` on the PATH). Install it "
            "with `npm install -g @servicenow/sdk`.",
        )
    version = _run(["--version"]).strip().splitlines()
    out = Status(installed=True, path=exe, version=version[-1].strip() if version else "")
    alias, default, values = "", False, {}

    def close() -> None:
        if alias:
            out.instances.append(
                Instance(alias, values.get("host", "").rstrip("/"), values.get("type", ""), default)
            )

    for line in _run(["auth", "--list"]).splitlines():
        head = _ALIAS.match(line)
        pair = _PAIR.match(line)
        if head:
            close()
            alias, default, values = head.group(2), bool(head.group(1)), {}
        elif pair and alias and pair.group(1) in ("host", "type"):  # never the user name
            values[pair.group(1)] = pair.group(2)
    close()
    return out


def topics(filter_text: str = "") -> list[Topic]:
    """The topics `now-sdk explain` has, optionally those matching a word."""
    args = ["explain", "--list", *([filter_text] if filter_text.strip() else [])]
    found = []
    for line in _run(args).splitlines():
        m = _TOPIC.match(line)
        if m:
            found.append(Topic(m.group(1), m.group(2) or ""))
    return found


def explain(topic: str) -> str | None:
    """A topic's documentation as markdown; None when the SDK has no such topic."""
    text = _run(["explain", topic, "--format", "raw"])
    if not text.strip() or text.lstrip().startswith("[now-sdk] ERROR"):
        return None
    return text
