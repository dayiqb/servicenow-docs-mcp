"""snow_docs_api through the MCP surface, against a fixture index with API reference pages."""

from __future__ import annotations

import anyio
import pytest
from conftest import DOCS, build_fixture_index, install_index, make_entry
from mcp import Client
from test_api_table import GLOBAL, GLOBAL_PATH, PAGE, PATH, REST, REST_PATH

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import mcp


@pytest.fixture
def api(monkeypatch, tmp_path, fake_models):
    """australia installed with two API pages; no search models on disk."""
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    docs = {**DOCS, PATH: PAGE, GLOBAL_PATH: GLOBAL, REST_PATH: REST}
    docs["markdown/itsm/tables.md"] = "# Tables\n\nThe Incident [incident] table.\n"
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


def test_a_rest_endpoint_gives_its_parameters_by_place(api):
    r = call("snow_docs_api", name="POST /api/now/table/incident")
    assert r["ok"] and r["kind"] == "endpoint"
    (e,) = r["endpoints"]
    assert (e["api"], e["verb"], e["path"]) == ("Table", "POST", "/now/table/{tableName}")
    assert e["default_url"] == "/api/now/table/{tableName}"
    assert [p["name"] for p in e["path_parameters"]] == ["tableName"]
    assert [p["name"] for p in e["query_parameters"]] == ["sysparm_fields"]
    assert [p["name"] for p in e["body_parameters"]] == ["name-value pairs"]
    assert "Inserts one record" in call("snow_docs_read", id=e["id"])["content"]


def test_a_rest_api_name_lists_its_endpoints(api):
    r = call("snow_docs_api", name="Table API")
    assert r["kind"] == "rest_api"
    assert r["classes"] == [
        {
            "class_name": "Table",
            "members": ["POST /now/table/{tableName}", "GET /now/table/{tableName}/{sys_id}"],
            "page_ids": [f"australia:{REST_PATH}::"],
        }
    ]


def test_an_unknown_endpoint_is_a_clear_no(api):
    r = call("snow_docs_api", name="DELETE /now/table/incident")
    assert r["ok"] and r["kind"] == "not_found"
    assert r["suggestions"] == ["POST /now/table/{tableName}"]


def test_check_script_reports_undocumented_calls_and_unknown_tables(api):
    code = "var gr = new GlideRecord('incidnet');\ngr.addEncodedQuerry('a');\ngr.query();\n"
    r = call("snow_docs_check_script", code=code)
    assert r["ok"] and r["release"] == "australia"
    assert (r["checked_calls"], r["checked_tables"]) == (2, 1)
    assert r["findings"] == [
        {"kind": "table", "name": "incidnet", "line": 1, "suggestions": ["incident"]},
        {
            "kind": "method",
            "name": "GlideRecord.addEncodedQuerry",
            "line": 2,
            "suggestions": ["GlideRecord.addEncodedQuery"],
        },
    ]
    assert "2 of them are not in the australia docs" in r["message"]


def test_check_script_says_so_when_everything_checks_out_or_nothing_can_be_checked(api):
    good = call("snow_docs_check_script", code="var gr = new GlideRecord('incident'); gr.query();")
    assert good["ok"] and good["findings"] == [] and "all documented" in good["message"]
    none = call("snow_docs_check_script", code="function add(a, b) { return a + b; }")
    assert none["ok"] and none["checked_calls"] == 0 and "Nothing to check" in none["message"]
    assert not call("snow_docs_check_script", code="  ")["ok"]


def test_both_releases_stay_loaded_when_calls_alternate(tmp_path, monkeypatch):
    """A comparison of releases looks things up in one, then the other, then the first again;
    each index is parsed once, not on every switch."""
    from snow_docs_mcp import api_table, server, store

    docs = {**DOCS, PATH: PAGE, GLOBAL_PATH: GLOBAL}
    au = build_fixture_index(tmp_path / "au.db", docs=docs)
    br = build_fixture_index(tmp_path / "br.db", docs=docs)
    newer = build_fixture_index(tmp_path / "au-newer.db", docs=docs)
    loads: list[str] = []
    real_load, real_titles = api_table.load, store.titles_by_path
    monkeypatch.setattr(api_table, "load", lambda db: loads.append(str(db)) or real_load(db))
    monkeypatch.setattr(
        store, "titles_by_path", lambda db: loads.append(f"titles {db}") or real_titles(db)
    )
    for db in (au, br, au, br, au):
        assert server._api_table(db).names
        assert server._page_titles(db)
    assert loads == [str(au), f"titles {au}", str(br), f"titles {br}"]
    # a new snapshot takes the place of the oldest one: never more than one per release
    assert server._api_table(newer).names and server._page_titles(newer)
    assert len(server._api_tables) == 2 and len(server._titles) == 2
    assert str(au) not in server._api_tables and str(br) in server._api_tables
