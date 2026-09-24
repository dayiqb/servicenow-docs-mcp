"""End-to-end smoke check: start the real server over stdio and search + read.

Uses whatever data folder the server uses (run `snow-docs-mcp setup` first so the index
and models are already downloaded). Exits non-zero on any failure. Cross-platform.

    uv run --frozen python scripts/smoke_e2e.py
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT = Path(sys.executable).parent / ("snow-docs-mcp.exe" if os.name == "nt" else "snow-docs-mcp")
QUESTIONS = [
    ("how is incident priority calculated from impact and urgency", "priority"),
    ("create an email account for inbound email", "email"),
]


def main() -> int:
    proc = subprocess.Popen([str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
    lines: queue.Queue[bytes] = queue.Queue()
    threading.Thread(
        target=lambda: [lines.put(line) for line in iter(proc.stdout.readline, b"")],
        daemon=True,
    ).start()
    ids = iter(range(1, 10_000))

    def rpc(method: str, params: dict | None = None) -> dict:
        msg_id = next(ids)
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        proc.stdin.flush()
        while True:
            reply = json.loads(lines.get(timeout=600))
            if reply.get("id") == msg_id:
                return reply

    def tool(name: str, args: dict) -> dict:
        return rpc("tools/call", {"name": name, "arguments": args})["result"]["structuredContent"]

    try:
        rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        )
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        deadline = time.time() + 1200
        while not (st := tool("snow_docs_status", {}))["ok"]:
            if time.time() > deadline:
                print("not ready in time:", json.dumps(st, indent=2))
                return 1
            time.sleep(5)
        print("status:", json.dumps(st["releases"]))
        for question, expect in QUESTIONS:
            t = time.time()
            res = tool("snow_docs_search", {"query": question, "limit": 5})
            assert res["ok"] and res["hits"], res
            top = res["hits"][0]
            print(f"{time.time() - t:5.1f}s  {question!r} -> {top['id']}")
            assert expect in json.dumps(res["hits"]).lower(), res
            read = tool("snow_docs_read", {"id": top["id"]})
            assert read["ok"] and len(read["content"]) > 50, read
        print("smoke test passed")
        return 0
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)


if __name__ == "__main__":
    sys.exit(main())
