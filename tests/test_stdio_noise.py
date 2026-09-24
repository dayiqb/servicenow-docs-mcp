"""PKG-04 / D-06 — the stdio wire survives stdout noise, proven by spawning the real server.

This module drives the installed console script as a subprocess over real pipes, because that
is what an MCP client does. An in-process shim would exercise the SDK's transport but not the
process startup window, and the startup window is exactly where the corruption lives: anything
written to fd 1 before `mcp.run()` enters `stdio_server()` lands on the protocol stream.

Per D-06 this guard stays whether or not the SDK protects stdout for the serving window. The
requirement says the behaviour is *verified*, not *assumed* — an SDK that happens to be safe
today is not a contract, and the pre-serve window is the application's responsibility either
way. `test_guard_removal_corrupts_the_wire` is what keeps that claim honest.

Two mechanics are load-bearing and must not be "simplified":
  * bytes mode everywhere — `text=True` translates a lone `\\r` into `\\n`, so a carriage-return
    progress bar would look like a harmless blank line instead of the concatenation onto the
    front of the `initialize` frame that a real client actually sees;
  * a deadline on every read — a bare `readline()` against a wedged server hangs the phase gate
    forever instead of failing it.

No `protocolVersion` string is asserted anywhere: the installed SDK negotiates down to an older
version than its own latest constant, and that string is not a stable contract.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The real console script, not `python -m` and not an in-process object: the entry point an MCP
# client launches is the thing under test.
# The console script next to the running interpreter (bin/ on macOS/Linux, Scripts\ on
# Windows, where it is an .exe).
SCRIPT = Path(sys.executable).parent / ("snow-docs-mcp.exe" if os.name == "nt" else "snow-docs-mcp")

# Scrubbed from every child environment: the parent test process runs inside a venv, and letting
# these through would let the caller's environment decide which interpreter and which import
# paths the spawned server sees (T-17-05).
_SCRUBBED_ENV_KEYS = ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT")

_READ_DEADLINE_S = 10.0


def _child_env(**extra: str) -> dict[str, str]:
    """Inherit the environment minus the venv-bleed keys, plus any explicit test switches.

    The server starts first-run setup when a client connects, so every child gets a
    throwaway data folder and an unreachable index URL: the test must never download into
    (or read from) the real ~/.servicenow-docs-mcp.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED_ENV_KEYS}
    env["SNOW_DOCS_HOME"] = tempfile.mkdtemp(prefix="snow-docs-stdio-")
    env["SNOW_DOCS_INDEX_URL"] = "http://127.0.0.1:9/unreachable.db.gz"
    env["SNOW_DOCS_LATEST_URL"] = "off"
    env.update(extra)
    return env


class _Reader:
    """Reads the child's stdout byte by byte on a thread, so every read can have a deadline
    on every OS (selectors cannot poll pipes on Windows). Bytes mode on purpose: text mode
    would turn a lone carriage return into a newline and hide the corruption under test."""

    def __init__(self, stream) -> None:
        self.q: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._pump, args=(stream,), daemon=True).start()

    def _pump(self, stream) -> None:
        while True:
            b = stream.read(1)
            self.q.put(b)
            if not b:
                return

    def line(self, deadline_s: float = _READ_DEADLINE_S) -> bytes:
        """One newline-terminated frame, or whatever arrived before the deadline/EOF."""
        import time

        buf = b""
        end = time.monotonic() + deadline_s
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return buf
            try:
                b = self.q.get(timeout=remaining)
            except queue.Empty:
                return buf
            if not b:
                return buf
            buf += b
            if b == b"\n":
                return buf


def _handshake(env: dict[str, str]) -> tuple[list[bytes], bytes, int]:
    """Spawn the console script and drive initialize -> tools/list -> tools/call over stdio.

    Returns the three raw stdout frames (undecoded — the bytes are the evidence), the child's
    full stderr, and its return code.

    `stderr` is its own pipe and is never merged into stdout: the whole measurement is "the
    noise went to stderr while the wire stayed clean", and `stderr=subprocess.STDOUT` would
    destroy the distinction being measured.
    """
    proc = subprocess.Popen(
        [str(SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # NOT subprocess.STDOUT — see docstring
        env=env,
        bufsize=0,  # unbuffered bytes; line buffering is meaningless in binary mode
    )

    reader = _Reader(proc.stdout)

    def send(message: dict) -> None:
        proc.stdin.write((json.dumps(message) + "\n").encode())
        proc.stdin.flush()

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "phase17-stdio-noise-test", "version": "0"},
                },
            }
        )
        lines = [reader.line()]

        # A notification: no id, and no response is expected — reading for one here would
        # burn the whole deadline and then mis-attribute the next frame.
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        lines.append(reader.line())

        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "snow_docs_status", "arguments": {}},
            }
        )
        lines.append(reader.line())

        proc.stdin.close()
        try:
            returncode = proc.wait(timeout=_READ_DEADLINE_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait()
        return lines, proc.stderr.read(), returncode
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_clean_stdio_handshake() -> None:
    """The real console script completes a full JSON-RPC exchange over real pipes."""
    assert SCRIPT.exists(), (
        f"console script not found at {SCRIPT} — the nested venv must be synced "
        "(`uv sync --directory` on this project) before the transport can be measured"
    )

    lines, stderr, returncode = _handshake(_child_env())

    init, tools, call = (json.loads(raw) for raw in lines)

    assert init["id"] == 1, f"initialize response carried the wrong id: {init!r}"
    # Presence only. mcp 2.0.0 negotiates DOWN from its own LATEST_PROTOCOL_VERSION, so pinning
    # the string would fail on an SDK bump that broke nothing.
    assert "protocolVersion" in init["result"], (
        f"initialize result must carry a negotiated protocolVersion key, got {init['result']!r}"
    )

    assert sorted(tool["name"] for tool in tools["result"]["tools"]) == [
        "snow_docs_read",
        "snow_docs_search",
        "snow_docs_status",
    ], f"the three tools must be advertised over the wire, got {tools['result']['tools']!r}"

    assert call["result"]["isError"] is False, f"tools/call reported an error: {call!r}"
    status = call["result"]["structuredContent"]
    assert status["ok"] is False, f"a fresh data folder cannot be ready: {status!r}"
    assert {r["release"] for r in status["releases"]} == {"australia", "brazil"}, status

    assert returncode == 0, (
        f"the server must exit cleanly when its stdin closes, got {returncode} — "
        f"stderr was: {stderr[-2000:]!r}"
    )


def test_stdio_survives_noise_with_guard() -> None:
    """PKG-04 proper — noise before AND during serving, and every stdout frame is still JSON-RPC.

    The server is asked (via SNOW_DOCS_TEST_STDOUT_NOISE) to emit the three shapes that a real
    dependency emits at import/startup: a plain print, a carriage-return progress bar with no
    newline, and a raw `os.write(1, ...)` from C-level code that no `sys.stdout` shim can catch.
    """
    lines, stderr, returncode = _handshake(_child_env(SNOW_DOCS_TEST_STDOUT_NOISE="1"))

    # THE assertion. A carriage-return bar has no newline, so it concatenates onto the FRONT of
    # the initialize frame — "find a parseable line somewhere in the output" would silently drop
    # the corrupted frame and pass. The first byte on the wire must be the start of JSON.
    assert lines[0].startswith(b"{"), (
        f"the first byte on the protocol wire was not JSON: {lines[0][:120]!r} — a client reads "
        "this stream strictly, so one stray byte before the first frame makes the server unusable"
    )

    for raw in lines:
        json.loads(raw)  # every collected frame parses; no leniency, no skipping

    # The noise is not suppressed, it is redirected. Losing a model-download progress bar
    # entirely would be its own bug; it belongs on stderr, and this proves it arrived there.
    assert b"stray-print-before-serve" in stderr, (
        f"the pre-serve Python print did not reach stderr: {stderr[-2000:]!r}"
    )
    assert b"c-level-write-to-fd1" in stderr, (
        "the raw fd-1 write did not reach stderr — this is the shape a sys.stdout shim cannot "
        f"catch, and the reason the guard is fd-level: {stderr[-2000:]!r}"
    )
    assert b"stray-print-during-call" in stderr, (
        f"the during-serving noise did not reach stderr: {stderr[-2000:]!r}"
    )

    assert returncode == 0, (
        f"the server must still exit cleanly with noise on, got {returncode} — "
        f"stderr was: {stderr[-2000:]!r}"
    )


def test_guard_removal_corrupts_the_wire() -> None:
    """MUTATION CONTROL — with the guard disabled the wire MUST corrupt.

    Without this case the test above can pass for the wrong reason (an SDK that happens to
    absorb the noise, a harness that never sees it), and PKG-04 would be a guess rather than a
    measurement. This is the same "a guard must be able to fail" discipline the AST clean-room
    guard carries.
    """
    lines, stderr, _returncode = _handshake(
        _child_env(SNOW_DOCS_TEST_STDOUT_NOISE="1", SNOW_DOCS_TEST_DISABLE_STDOUT_GUARD="1")
    )

    assert not lines[0].startswith(b"{"), (
        f"the guard-disabled run produced a clean first frame ({lines[0][:120]!r}), so "
        "test_stdio_survives_noise_with_guard proves nothing — something absorbed the noise "
        "other than the guard under test. Investigate the SDK or this harness; do NOT delete "
        f"this case to make the suite green. Child stderr: {stderr[-2000:]!r}"
    )
