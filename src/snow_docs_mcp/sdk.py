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
NOT_INSTALLED = (
    "The ServiceNow SDK is not installed (no `now-sdk` on the PATH). Install it with "
    "`npm install -g @servicenow/sdk`."
)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ALIAS = re.compile(r"^(\*?)\[(.+)\]\s*$")
_PAIR = re.compile(r"^\s+(\w+)\s*=\s*(.*?)\s*$")
_NO_TOPIC = "No matching topics"
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
    # Why the instance list is unknown ("" when it was read): not the same as no instances.
    error: str = ""


@dataclass(frozen=True)
class Topic:
    name: str
    keywords: str


class SdkError(Exception):
    """A read-only now-sdk command could not give an answer: missing, failed or timed out."""


def _allowed(args: list[str]) -> bool:
    """`--version`, `auth --list`, and `explain` with a topic or `--list`: reads only."""
    if args in (["--version"], ["auth", "--list"]):
        return True
    return args[:1] == ["explain"] and all(
        a in ("--list", "--format", "raw") or not a.startswith("-") for a in args[1:]
    )


def _call(args: list[str]) -> tuple[int, str]:
    """(exit code, output) of one of the read-only commands; SdkError when it cannot run."""
    if not _allowed(args):
        raise ValueError(f"not a read-only now-sdk command: {' '.join(args)}")
    exe = shutil.which(EXECUTABLE)
    if exe is None:
        raise SdkError(NOT_INSTALLED)
    command = f"`{EXECUTABLE} {' '.join(args)}`"
    try:
        done = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            # Never the server's own stdin: that is the MCP connection, and a child that
            # reads it would swallow a request.
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        raise SdkError(f"{command} timed out after {TIMEOUT_SECONDS:g} s") from e
    except (OSError, subprocess.SubprocessError) as e:
        raise SdkError(f"{command} could not be run: {e}") from e
    return done.returncode, _ANSI.sub("", done.stdout)


def _run(args: list[str]) -> str:
    """Output of one of the read-only commands; SdkError when it fails."""
    code, out = _call(args)
    if code != 0:
        raise SdkError(f"`{EXECUTABLE} {' '.join(args)}` failed (exit {code})")
    return out


def installed() -> bool:
    """Whether a `now-sdk` is on the PATH."""
    return shutil.which(EXECUTABLE) is not None


def version() -> str:
    """The installed SDK's version ("" when it is not installed or will not say)."""
    try:
        lines = _run(["--version"]).strip().splitlines()
    except SdkError:
        return ""
    return lines[-1].strip() if lines else ""


def status() -> Status:
    """Whether the SDK is installed, its version, and the instances it has credentials for."""
    exe = shutil.which(EXECUTABLE)
    if exe is None:
        return Status(installed=False, message=NOT_INSTALLED)
    out = Status(installed=True, path=exe, version=version())
    try:
        listing = _run(["auth", "--list"])
    except SdkError as e:
        out.error = str(e)
        return out
    alias, default, values = "", False, {}

    def close() -> None:
        if alias:
            out.instances.append(
                Instance(alias, values.get("host", "").rstrip("/"), values.get("type", ""), default)
            )

    for line in listing.splitlines():
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
    """The topics `now-sdk explain` has, optionally those matching a word; SdkError when the
    list cannot be read."""
    args = ["explain", "--list", *([filter_text] if filter_text.strip() else [])]
    found = []
    for line in _run(args).splitlines():
        m = _TOPIC.match(line)
        if m:
            found.append(Topic(m.group(1), m.group(2) or ""))
    return found


def explain(topic: str) -> str | None:
    """A topic's documentation as markdown; None when the SDK has no such topic."""
    code, text = _call(["explain", topic, "--format", "raw"])
    if _NO_TOPIC in text or (code == 0 and not text.strip()):
        return None
    if code != 0 or text.lstrip().startswith("[now-sdk] ERROR"):
        raise SdkError(f"`{EXECUTABLE} explain {topic}` failed (exit {code})")
    return text
