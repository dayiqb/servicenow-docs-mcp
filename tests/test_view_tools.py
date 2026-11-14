"""The tool that exists to show something to the user in the panel: snow_docs_open (a page as
a document)."""

from __future__ import annotations

import anyio
import pytest
from conftest import DOCS, build_fixture_index, install_index, make_entry
from mcp import Client

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import PANEL_URI, mcp

INCIDENT = "australia:markdown/itsm/incident.md::"
STATES = "australia:markdown/itsm/incident.md::Incident management > States"


@pytest.fixture
def docs(monkeypatch, tmp_path, fake_models):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    install_index(
        build_fixture_index(tmp_path / "au.db", docs=DOCS), config.BUILTIN_ENTRIES["australia"]
    )


def call(tool: str, **args):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_the_view_tools_point_at_the_panel_and_the_finding_tools_do_not(docs):
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    ui = {t.name: (t.meta or {}).get("ui", {}).get("resourceUri") for t in anyio.run(go).tools}
    assert {n for n, uri in ui.items() if uri == PANEL_URI} == {
        "snow_docs_compare",
        "snow_docs_open",
    }
    assert "snow_docs_diagram" not in ui  # figures are Claude's to draw, not this server's
    # Claude's own finding and reading: many calls for one answer, and no panel for any of them
    for name in ("snow_docs_search", "snow_docs_browse", "snow_docs_read", "snow_docs_api"):
        assert ui[name] is None


def test_open_names_the_page_and_its_sections_without_returning_the_text(docs):
    r = call("snow_docs_open", id=STATES)
    assert r["ok"] and r["id"] == INCIDENT and r["title"] == "Incident management"
    assert r["focus"] == "Incident management > States" and r["release"] == "australia"
    assert r["headings"] == [
        "Incident management",
        "Incident management > States",
        "Incident management > States > Resolved state",
        "Incident management > Priority",
    ]
    assert "content" not in r and "An incident moves through" not in str(r)
    whole = call("snow_docs_open", id=INCIDENT)
    assert whole["ok"] and whole["focus"] == ""


def test_open_explains_a_bad_id_like_read_does(docs):
    bad = call("snow_docs_open", id="australia:markdown/itsm/nope.md::")
    assert (
        not bad["ok"]
        and bad["message"]
        == call("snow_docs_read", id="australia:markdown/itsm/nope.md::")["message"]
    )
    assert not call("snow_docs_open", id="not an id")["ok"]
