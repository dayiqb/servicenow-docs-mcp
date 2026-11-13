"""The docs as a Python library: the same calls as the MCP tools, without MCP.

    from snow_docs_mcp import api

    found = api.search("how are incident priorities calculated", limit=3)
    page = api.read(found.hits[0].id)
    method = api.lookup("GlideRecord.addEncodedQuery")

Every function returns the result model its tool returns (`ok`, `message`, and the data), and
never raises. The docs index and the search models must be installed: run
`snow-docs-mcp setup` once.
"""

from __future__ import annotations

from snow_docs_mcp.server import snow_docs_api as lookup
from snow_docs_mcp.server import snow_docs_browse as browse
from snow_docs_mcp.server import snow_docs_check_script as check_script
from snow_docs_mcp.server import snow_docs_compare as compare
from snow_docs_mcp.server import snow_docs_read as read
from snow_docs_mcp.server import snow_docs_search as search
from snow_docs_mcp.server import snow_docs_status as status

__all__ = ["browse", "check_script", "compare", "lookup", "read", "search", "status"]
