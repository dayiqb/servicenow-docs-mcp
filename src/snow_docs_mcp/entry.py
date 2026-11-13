"""What the process does around serving: logging, certificates, and `snow-docs-mcp setup`."""

from __future__ import annotations

import logging
import os
import sys
import threading

from snow_docs_mcp import config, setup

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Send all logging to stderr; stdout belongs to the MCP wire."""
    # force=True is REQUIRED: MCPServer() installs a root StreamHandler at construction
    # (import time here), and basicConfig is a no-op once the root logger has handlers.
    level = logging.getLevelName((os.environ.get("SNOW_DOCS_LOG_LEVEL") or "INFO").strip().upper())
    logging.basicConfig(
        level=level if isinstance(level, int) else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
        force=True,
    )


def noisy_startup_probe() -> None:
    """Emit the three stdout-noise shapes that corrupt stdio framing. Test-only."""
    print("stray-print-before-serve")
    sys.stdout.write("\rFetching model 10%")
    sys.stdout.flush()
    os.write(1, b"c-level-write-to-fd1\n")


def run_setup_cli(args: list[str]) -> int:
    """`snow-docs-mcp setup [RELEASE|all]`: download in the foreground, with progress."""
    target = (args[0].lower() if args else config.default_release()).strip()
    releases = list(config.RELEASES) if target == "all" else [target]
    if any(r not in config.RELEASES for r in releases):
        print(
            f"unknown release {target!r}; use one of: {', '.join(config.RELEASES)}, all",
            file=sys.stderr,
        )
        return 2
    logging.getLogger("snow_docs_mcp.setup").setLevel(logging.WARNING)
    print(
        f"ServiceNow docs MCP {config.VERSION}: setting up in {config.data_home()}", file=sys.stderr
    )
    worst = 0
    for rel in releases:
        done = threading.Event()
        result: dict = {}

        def run(rel: str = rel, result: dict = result, done: threading.Event = done) -> None:
            result["s"] = setup.ensure(rel)
            done.set()

        threading.Thread(target=run, daemon=True).start()
        last = ""
        while not done.wait(0.5):
            st = setup.status(rel)
            line = f"[{rel}] {st.state}: {st.message}"
            if line != last:
                print(line, file=sys.stderr)
                last = line
        st = result["s"]
        print(f"[{rel}] {st.state}: {st.message}", file=sys.stderr)
        if st.state != "ready":
            worst = 1
    return worst


def use_system_certificates() -> None:
    """Trust the OS certificate store for all HTTPS (index, latest.json, model downloads),
    so corporate proxies that re-sign TLS with their own root certificate work."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception as e:  # noqa: BLE001 - fall back to the bundled certificates
        logger.warning("could not use the system certificate store (%s)", e)
