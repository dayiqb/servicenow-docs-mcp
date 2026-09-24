"""Claude Desktop (.mcpb) launcher: `uv run --directory <bundle> server/main.py`.

A separate folder on purpose: running `src/snow_docs_mcp/server.py` as a script would put
that package directory first on sys.path, where its `setup.py`, `config.py` and
`models.py` could shadow third-party modules of the same name.
"""

from snow_docs_mcp.server import main

if __name__ == "__main__":
    main()
