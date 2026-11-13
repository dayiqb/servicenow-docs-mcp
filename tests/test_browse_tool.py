"""snow_docs_browse: the docs as a tree of product areas, folders and pages."""

from __future__ import annotations

import anyio
import pytest
from conftest import DOCS, build_fixture_index, fake_models_on_disk, install_index, make_entry
from mcp import Client

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import mcp

EXTRA = {
    "markdown/itsm/incident-management/create.md": "---\ntitle: Create an incident\n---\n\n# Create\n",
    "markdown/itsm/incident-management/close.md": "---\ntitle: Close an incident\n---\n\n# Close\n",
    "markdown/itsm/incident-management/setup/roles.md": "---\ntitle: Incident roles\n---\n\n# Roles\n",
    "markdown/itsm/change-management/overview.md": "# Change overview\n\nNo front matter here.\n",
}


@pytest.fixture
def docs(monkeypatch, tmp_path, fake_models):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    db = build_fixture_index(tmp_path / "au.db", docs={**DOCS, **EXTRA})
    install_index(db, config.BUILTIN_ENTRIES["australia"])
    fake_models_on_disk()


def call(tool: str, **args):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_without_arguments_it_lists_the_product_areas_with_page_counts(docs):
    r = call("snow_docs_browse")
    assert r["ok"] and r["path"] == "" and r["pages"] == []
    assert [(f["name"], f["pages"]) for f in r["folders"]] == [("hr", 1), ("itsm", 7)]
    assert "2 product areas" in r["message"]


def test_a_product_lists_its_folders_and_its_own_pages(docs):
    r = call("snow_docs_browse", product="itsm")
    assert r["path"] == "itsm"
    assert [(f["name"], f["path"], f["pages"]) for f in r["folders"]] == [
        ("change-management", "itsm/change-management", 1),
        ("incident-management", "itsm/incident-management", 3),
    ]
    assert [p["title"] for p in r["pages"]] == ["change.md", "Incident management", "problem.md"]
    assert r["pages"][1]["id"] == "australia:markdown/itsm/incident.md::"


def test_a_folder_goes_one_level_down_and_page_ids_read_back(docs):
    r = call("snow_docs_browse", product="itsm", folder="incident-management")
    assert r["path"] == "itsm/incident-management"
    assert [f["name"] for f in r["folders"]] == ["setup"]
    assert [p["title"] for p in r["pages"]] == ["Close an incident", "Create an incident"]
    assert call("snow_docs_read", id=r["pages"][0]["id"])["ok"]
    whole = call("snow_docs_browse", folder="itsm/incident-management/setup")
    assert [p["title"] for p in whole["pages"]] == ["Incident roles"]


def test_unknown_product_and_folder_are_explained(docs):
    r = call("snow_docs_browse", product="nonsense")
    s = call("snow_docs_search", query="x", product="nonsense")
    assert not r["ok"] and r["message"] == s["message"]
    f = call("snow_docs_browse", product="itsm", folder="incident-managment")
    assert not f["ok"] and "incident-management" in f["message"]


def test_a_long_folder_is_cut_and_says_so(docs, monkeypatch):
    from snow_docs_mcp import server

    monkeypatch.setattr(server, "BROWSE_PAGES_SHOWN", 2)
    r = call("snow_docs_browse", product="itsm")
    assert len(r["pages"]) == 2 and r["pages_left_out"] == 1 and "1 more page" in r["message"]
    more = call("snow_docs_browse", product="itsm", offset=2)
    assert [p["title"] for p in more["pages"]] == ["problem.md"] and more["pages_left_out"] == 0
    assert "offset=2" in r["message"]
