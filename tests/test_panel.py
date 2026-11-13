"""The results panel (MCP Apps): wiring, and that the page stands on its own.

A host that supports MCP Apps renders `ui://servicenow-docs/panel.html` next to the result of
snow_docs_search and snow_docs_compare; every other client keeps getting the plain result.
"""

from __future__ import annotations

import re

import anyio
import pytest
from mcp import Client

from snow_docs_mcp import setup
from snow_docs_mcp.server import PANEL_URI, mcp, panel_html

APP_MIME = "text/html;profile=mcp-app"


@pytest.fixture(autouse=True)
def _no_setup(monkeypatch):
    monkeypatch.setattr(setup, "start", lambda: None)


def _run(coro_fn):
    async def go():
        async with Client(mcp) as client:
            return await coro_fn(client)

    return anyio.run(go)


def test_search_and_compare_point_at_the_panel_and_nothing_else_does():
    tools = _run(lambda c: c.list_tools()).tools
    with_ui = {t.name: (t.meta or {}).get("ui", {}).get("resourceUri") for t in tools}
    assert with_ui["snow_docs_search"] == PANEL_URI == "ui://servicenow-docs/panel.html"
    assert with_ui["snow_docs_compare"] == PANEL_URI
    assert [n for n, uri in with_ui.items() if uri] == [
        "snow_docs_search",
        "snow_docs_compare",
    ] or sorted(n for n, uri in with_ui.items() if uri) == ["snow_docs_compare", "snow_docs_search"]


def test_the_panel_is_served_as_an_app_resource():
    listed = _run(lambda c: c.list_resources()).resources
    assert [str(r.uri) for r in listed if str(r.uri).startswith("ui://")] == [PANEL_URI]
    read = _run(lambda c: c.read_resource(PANEL_URI))
    (content,) = read.contents
    assert content.mime_type == APP_MIME and content.text == panel_html()


def test_the_server_advertises_the_apps_extension():
    assert "io.modelcontextprotocol/ui" in mcp._lowlevel_server.extensions


def test_the_page_is_one_self_contained_document():
    html = panel_html()
    assert html.lstrip().lower().startswith("<!doctype html>") and len(html) < 120_000
    # the sandbox allows nothing external: no remote scripts, styles, fonts, images or fetches
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html)
    assert not re.search(r"@import|url\(\s*['\"]?https?:|fetch\(|XMLHttpRequest|<link\b", html)
    assert "<script src" not in html


def test_the_page_speaks_the_apps_protocol_and_only_calls_read_only_tools():
    html = panel_html()
    for method in (
        "ui/initialize",
        "ui/notifications/initialized",
        "ui/notifications/tool-input",
        "ui/notifications/tool-result",
        "ui/notifications/host-context-changed",
        "ui/notifications/size-changed",
        "ui/open-link",
        "tools/call",
    ):
        assert method in html, method
    called = set(re.findall(r"callTool\(\s*[\"'](\w+)[\"']", html))
    assert called == {"snow_docs_search", "snow_docs_read"}


def test_the_page_never_puts_tool_text_into_the_document_as_markup():
    html = panel_html()
    assert (
        "innerHTML" not in html
        and "insertAdjacentHTML" not in html
        and "document.write" not in html
    )
    assert "eval(" not in html and "new Function" not in html


def test_the_page_has_the_basics_of_an_accessible_document():
    html = panel_html()
    assert '<html lang="en"' in html and "<title>" in html
    assert "prefers-reduced-motion" in html and ":focus-visible" in html
    assert 'aria-live="polite"' in html and "color-scheme" in html
