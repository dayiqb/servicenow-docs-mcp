"""PostToolUse hook: check the ServiceNow script code Claude just wrote against the API
reference (see snow_docs_mcp.script_hook). Never blocks: any problem means exit 0, silent."""

from __future__ import annotations

import sys

if __name__ == "__main__":
    try:
        from snow_docs_mcp.script_hook import main

        sys.exit(main())
    except Exception:  # noqa: BLE001 - a hook must never fail the tool call it follows
        sys.exit(0)
