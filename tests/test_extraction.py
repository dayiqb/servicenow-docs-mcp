"""PKG-01 / D-04 — the extraction proof: this directory, copied out, installs and serves.

Extraction is a directory copy and nothing else. This test performs that copy for real — into
the system temp directory, outside the repo tree — runs a real `uv sync --frozen` there, and
then proves three things about the result: nothing from this repo is on the extracted
interpreter's `sys.path`, the spike is genuinely unimportable from it, and the extracted console
script completes an MCP `initialize` handshake.

Configuration (env vars):
    SNOW_DOCS_EXTRACTION_TEST   "1" enables this test. Default (unset) skips it, because the body
                                runs a real `uv sync` in a temp directory: it touches the network
                                on a cold uv cache and takes seconds rather than milliseconds.

D-04, fail-not-skip: once the variable is set there is NO `pytest.skip` anywhere in the body —
every problem is an assertion failure. The gate lives exclusively in the module-level `skipif`
marker. A skip inside an already-enabled live gate is the exact false-green shape that let a
repo guard sit red for about six weeks: the suite reported green while the assertion never ran.

Every child process here is spawned with a list argv and never `shell=True`, and every child env
is scrubbed of `VIRTUAL_ENV`, `PYTHONPATH` and `UV_PROJECT_ENVIRONMENT` (T-17-05). That scrub is
load-bearing, not cosmetic: with them set, the copy can still resolve back through this repo and
the test would pass while proving nothing.

This module is in `test_no_spike_imports.LITERAL_CHECK_EXEMPT` — it must name this repo's
directory to grep for leaks. The AST guard's import, `sys.path` and dynamic-import rules still
apply to it in full.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The repo that must NOT be reachable from the extracted copy. Derived from PROJECT_ROOT so a
# rename cannot silently make the leak check vacuous; the literal fragments below are a
# belt-and-braces second form for the case where a path reaches the copy by some other route.
REPO_ROOT = PROJECT_ROOT.parents[1]
REPO_PATH_FRAGMENTS = (REPO_ROOT.name, "docs-rag-frontier", "docs-rag-mcp")

ENV_FLAG = "SNOW_DOCS_EXTRACTION_TEST"

# Seconds to wait for the extracted server's handshake response before killing it. A blocking
# readline with no deadline turns a dead server into a gate that hangs forever.
HANDSHAKE_TIMEOUT_S = 60.0

SCRUBBED_VARS = ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT")


def _child_env() -> dict[str, str]:
    """The ambient environment minus everything that could re-open the boundary under test."""
    return {k: v for k, v in os.environ.items() if k not in SCRUBBED_VARS}


@pytest.mark.skipif(
    os.environ.get(ENV_FLAG) != "1",
    reason=(
        f"extraction proof is opt-in: set {ENV_FLAG}=1 to run it. Enabling it copies this "
        "project to a system temp directory and runs a REAL `uv sync --frozen` there, then "
        "spawns the extracted server — seconds, and network on a cold uv cache. Command: "
        f"{ENV_FLAG}=1 uv run --directory servers/servicenow-docs-mcp pytest -q -rs "
        "tests/test_extraction.py"
    ),
)
def test_extracted_copy_installs_and_starts() -> None:
    """D-04 / PKG-01 — a directory copy of this project installs and serves on its own.

    Failure mode prevented: "extractable" being an assumption rather than a measurement. Every
    other guard in this suite is static; this is the only one that proves the copy actually
    works, with nothing from this repo on its path.
    """
    env = _child_env()
    for var in SCRUBBED_VARS:
        assert var not in env, f"{var} must be scrubbed from every child env (T-17-05)"

    # System temp: mode 0700 and an unpredictable name (ASVS V12), and never inside the repo.
    tmp = tempfile.mkdtemp(prefix="snow-docs-extract-")
    try:
        dst = Path(tmp) / "servicenow-docs-mcp"
        shutil.copytree(
            PROJECT_ROOT,
            dst,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"
            ),
        )
        assert not (dst / ".venv").exists(), (
            "the copy must carry no virtualenv — a copied .venv would hide whether the lock "
            "alone is sufficient to install this project"
        )
        for candidate in (dst, dst.resolve()):
            assert not str(candidate).startswith(str(PROJECT_ROOT)), (
                f"the copy must live outside the repo tree, got {candidate}"
            )
            assert not str(candidate).startswith(str(REPO_ROOT)), (
                f"the copy must live outside the repo tree, got {candidate}"
            )

        # --frozen refuses to re-resolve, so this doubles as a lockfile-completeness assertion:
        # if uv.lock did not fully describe the project, this fails instead of quietly re-solving.
        sync = subprocess.run(
            ["uv", "sync", "--frozen"],
            check=False,
            cwd=dst,
            env=env,
            capture_output=True,
            text=True,
        )
        assert sync.returncode == 0, (
            "`uv sync --frozen` failed in the extracted copy — the committed uv.lock does not "
            f"install this project standalone:\n{sync.stderr}"
        )

        py = dst / ".venv" / "bin" / "python"
        script = dst / ".venv" / "bin" / "snow-docs-mcp"
        assert py.exists(), f"the extracted venv has no interpreter at {py}"
        assert script.exists(), (
            "the snow-docs-mcp console script is missing from the extracted venv — the entry "
            "point in pyproject.toml is what an MCP client launches"
        )

        # Negative proof 1: no path from this repo is reachable from the extracted interpreter.
        paths = subprocess.run(
            [str(py), "-c", "import sys, json; print(json.dumps(sys.path))"],
            cwd=dst,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        leaks = [
            entry
            for entry in json.loads(paths.stdout)
            if any(frag in entry for frag in REPO_PATH_FRAGMENTS)
        ]
        assert leaks == [], (
            f"repo paths leaked into the extracted venv's sys.path: {leaks} — the copy would be "
            "resolving through this repo, so every other assertion here would prove nothing"
        )

        # Negative proof 2: the spike is not merely unused, it is unimportable.
        spike = subprocess.run(
            [str(py), "-c", "import docs_rag_mcp"],
            check=False,
            cwd=dst,
            env=env,
            capture_output=True,
            text=True,
        )
        assert spike.returncode != 0, (
            "the extracted interpreter imported docs_rag_mcp — the clean room is not clean"
        )
        assert "ModuleNotFoundError" in spike.stderr, (
            "importing the spike must fail with ModuleNotFoundError, got:\n" + spike.stderr
        )

        # Positive proof: the copy actually serves MCP over stdio.
        proc = subprocess.Popen(
            [str(script)],
            cwd=tmp,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        watchdog = threading.Timer(HANDSHAKE_TIMEOUT_S, proc.kill)
        watchdog.start()
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "extract-test", "version": "0"},
                },
            }
            proc.stdin.write((json.dumps(request) + "\n").encode())
            proc.stdin.flush()
            line = proc.stdout.readline()
            assert line, (
                "the extracted server produced no handshake response within "
                f"{HANDSHAKE_TIMEOUT_S:.0f}s (stderr:\n{proc.stderr.read().decode(errors='replace')})"
            )
            obj = json.loads(line)
            # No protocolVersion assertion: the SDK negotiates down and that string is not a
            # stable contract (verified in Plan 17-01).
            assert obj["result"]["serverInfo"]["name"] == "servicenow-docs", (
                f"the extracted server identified itself as {obj['result']['serverInfo']!r}, "
                "not the servicenow-docs server this project builds"
            )
        finally:
            watchdog.cancel()
            proc.kill()
            proc.wait()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
