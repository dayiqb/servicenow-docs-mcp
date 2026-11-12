"""snow_docs_api through the MCP surface, against a fixture index with API reference pages."""

from __future__ import annotations

import anyio
import pytest
from conftest import DOCS, build_fixture_index, install_index, make_entry
from mcp import Client
from test_api_table import GLOBAL, GLOBAL_PATH, PAGE, PATH

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import mcp


@pytest.fixture
def api(monkeypatch, tmp_path, fake_models):
    """australia installed with two API pages; no search models on disk."""
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    docs = {**DOCS, PATH: PAGE, GLOBAL_PATH: GLOBAL}
    install_index(
        build_fixture_index(tmp_path / "au.db", docs=docs), config.BUILTIN_ENTRIES["australia"]
    )


def call(tool: str, **args):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_tool_is_listed_read_only(api):
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    tool = next(t for t in anyio.run(go).tools if t.name == "snow_docs_api")
    assert tool.annotations.model_dump(exclude_none=True).get("read_only_hint") is True
    assert set(tool.input_schema["properties"]) == {"name", "release"}


def test_a_class_lists_its_methods_per_variant(api):
    r = call("snow_docs_api", name="GlideRecord")
    assert r["ok"] and r["kind"] == "class" and r["release"] == "australia"
    assert [c["class_name"] for c in r["classes"]] == ["GlideRecord", "Scoped GlideRecord"]
    assert r["classes"][0]["members"] == [
        "addEncodedQuery(String query)",
        "getValue(String name)",
        "query()",
        "isActionAborted",
    ]
    assert r["classes"][0]["page_ids"] == [f"australia:{GLOBAL_PATH}::"]
    assert (
        "GlideRecord - Global"
        in call("snow_docs_read", id=r["classes"][0]["page_ids"][0])["content"]
    )
    assert "2 classes" in r["message"] and "8 members" in r["message"]


def test_a_method_gives_parameters_returns_example_and_a_readable_id(api):
    r = call("snow_docs_api", name="Scoped GlideRecord.addEncodedQuery")
    assert r["ok"] and r["kind"] == "method"
    (m,) = r["methods"]
    assert (
        m["class_name"] == "Scoped GlideRecord"
        and m["signature"] == "addEncodedQuery(String query)"
    )
    assert m["parameters"] == [
        {"name": "query", "type": "String", "description": "An encoded query string."}
    ]
    assert m["returns"] == "void" and "addEncodedQuery('active=true')" in m["example"]
    read = call("snow_docs_read", id=m["id"])
    assert read["ok"] and "Adds an encoded query" in read["content"]


def test_a_method_name_alone_finds_every_class_that_has_it(api):
    r = call("snow_docs_api", name="getValue")
    assert r["kind"] == "method"
    assert [m["class_name"] for m in r["methods"]] == ["GlideRecord", "Scoped GlideRecord"]


def test_an_unknown_method_is_a_clear_no_with_suggestions(api):
    r = call("snow_docs_api", name="GlideRecord.addEncodedQuerry")
    assert r["ok"] and r["kind"] == "not_found" and r["methods"] == []
    assert r["suggestions"] == ["GlideRecord.addEncodedQuery"]
    assert "not in the australia API reference" in r["message"]


def test_empty_name_unknown_release_and_missing_index(api):
    assert not call("snow_docs_api", name=" ")["ok"]
    assert (
        "Unknown release" in call("snow_docs_api", name="GlideRecord", release="zurich")["message"]
    )
    r = call("snow_docs_api", name="GlideRecord", release="brazil")
    assert not r["ok"] and r["kind"] == ""
