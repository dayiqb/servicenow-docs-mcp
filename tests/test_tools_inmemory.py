"""The MCP surface, driven through the SDK's in-memory client against fixture indexes.

Exercises the same server object the stdio entry point serves, without a process: tool
registration + annotations, the prompt, server instructions, both releases, and each tool
while setup is still going. Real transport is covered by test_stdio_noise.py.

Driven from sync tests via anyio.run on purpose: pytest-asyncio would fight the anyio
plugin the mcp SDK already brings.
"""

from __future__ import annotations

import sqlite3

import anyio
import pytest
from conftest import fake_models_on_disk, install_index, make_entry
from mcp import Client

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import ANSWER_RULES, mcp


@pytest.fixture
def ready(monkeypatch, fixture_db, fake_models):
    """australia installed + models on disk; nothing downloads."""
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    conn = sqlite3.connect(fixture_db)  # give one page a canonical_url, as newer docs have
    conn.execute(
        "UPDATE documents SET content = replace(content, 'title: Incident management', "
        "'title: Incident management' || char(10) || "
        "'canonical_url: https://www.servicenow.com/docs/r/incident.html') "
        "WHERE file_path = 'markdown/itsm/incident.md'"
    )
    conn.commit()
    conn.close()
    install_index(fixture_db, config.BUILTIN_ENTRIES["australia"])
    fake_models_on_disk()
    return fake_models


@pytest.fixture
def nothing_installed(monkeypatch, fake_models):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)


def _call(name: str, args: dict | None = None):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, args or {})

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_surface_tools_annotations_prompt_and_instructions(ready) -> None:
    async def go():
        async with Client(mcp) as client:
            return (
                await client.list_tools(),
                await client.list_prompts(),
                await client.get_prompt("answer", {"question": "How do SLAs pause?"}),
            )

    tools, prompts, prompt = anyio.run(go)
    assert sorted(t.name for t in tools.tools) == [
        "snow_docs_read",
        "snow_docs_search",
        "snow_docs_status",
    ]
    for tool in tools.tools:
        hints = tool.annotations.model_dump(exclude_none=True)
        assert hints.get("read_only_hint") is True, (tool.name, hints)
        assert hints.get("open_world_hint") is False, (tool.name, hints)
        assert tool.description and len(tool.description) > 60, tool.name
    search = next(t for t in tools.tools if t.name == "snow_docs_search")
    assert "release" in search.input_schema["properties"]
    assert [p.name for p in prompts.prompts] == ["answer"]
    text = prompt.messages[0].content.text
    assert "How do SLAs pause?" in text and "Cite every factual claim" in text
    assert "australia" in ANSWER_RULES and "brazil" in ANSWER_RULES


def test_search_then_read_round_trip(ready) -> None:
    ready.query_vectors["incident lifecycle"] = {0: 1.0, 1: 0.5}
    ready.rerank_scores = {"lifecycle": 3.0, "priority": 1.0}
    res = _call("snow_docs_search", {"query": "incident lifecycle", "limit": 2})
    assert res["ok"] is True, res
    assert res["release"] == "australia" and res["snapshot"] == "2026-05-15"
    hit = res["hits"][0]
    assert hit["id"] == "australia:markdown/itsm/incident.md::Incident management > States"
    assert hit["page_title"] == "Incident management" and hit["product"] == "itsm"
    assert hit["url"] == "https://www.servicenow.com/docs/r/incident.html"
    assert "Describes the incident lifecycle" not in hit["snippet"], "context line leaked"
    assert "New, In Progress" in hit["snippet"]

    read = _call("snow_docs_read", {"id": hit["id"]})
    assert read["ok"] is True, read
    assert "close automatically after 7 days" in read["content"]
    assert read["url"] == hit["url"]
    # ids without the release prefix (older citations) still read from the default release
    old_style = _call("snow_docs_read", {"id": "markdown/itsm/incident.md::"})
    assert old_style["ok"] is True and old_style["id"].startswith("australia:")


def test_product_filter_and_unknown_product(ready) -> None:
    res = _call("snow_docs_search", {"query": "case", "product": "hr", "limit": 5})
    assert res["ok"] and {h["product"] for h in res["hits"]} == {"hr"}
    bad = _call("snow_docs_search", {"query": "case", "product": "itsn"})
    assert bad["ok"] is False and "Did you mean: itsm" in bad["message"]
    assert "hr, itsm" in bad["message"]


def test_limit_is_clamped_and_said(ready) -> None:
    res = _call("snow_docs_search", {"query": "incident", "limit": 99})
    assert res["ok"] and len(res["hits"]) == 6
    assert "limit adjusted to 20" in res["message"]


def test_empty_query_and_unknown_release(ready) -> None:
    assert _call("snow_docs_search", {"query": "   "})["ok"] is False
    res = _call("snow_docs_search", {"query": "x", "release": "tokyo"})
    assert res["ok"] is False and "australia, brazil" in res["message"]
    bad_id = _call("snow_docs_read", {"id": "tokyo:markdown/a.md::B"})
    assert bad_id["ok"] is False and "Unknown release" in bad_id["message"]
    garbage = _call("snow_docs_read", {"id": "incident states"})
    assert garbage["ok"] is False and "not a docs id" in garbage["message"]


def test_brazil_not_published_yet_is_explained(ready, monkeypatch) -> None:
    monkeypatch.setattr(setup, "request", lambda release: None)
    setup._set("brazil", "unavailable", "No brazil docs index has been published yet.")
    res = _call("snow_docs_search", {"query": "incident", "release": "brazil"})
    assert res["ok"] is False and "No brazil docs index" in res["message"]


def test_status_reports_each_release(ready) -> None:
    st = _call("snow_docs_status")
    assert st["ok"] is True and st["default_release"] == "australia" and st["models"] == "ready"
    by = {r["release"]: r for r in st["releases"]}
    assert by["australia"]["state"] == "ready" and by["australia"]["snapshot"] == "2026-05-15"
    assert by["australia"]["chunks"] == 6
    assert by["brazil"]["state"] == "not_installed"
    assert st["data_folder"] == str(config.data_home())


def test_tools_explain_setup_in_progress(nothing_installed) -> None:
    setup._set("australia", "downloading", "Downloading the australia docs index (22%).", 0.22)
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is False and "still being set up" in res["message"] and "22%" in res["message"]
    read = _call("snow_docs_read", {"id": "australia:markdown/itsm/incident.md::"})
    assert read["ok"] is False and "still being set up" in read["message"]
    st = _call("snow_docs_status")
    assert st["ok"] is False
    assert {r["release"]: r["state"] for r in st["releases"]}["australia"] == "downloading"


def test_models_missing_is_explained(ready, monkeypatch) -> None:
    import shutil

    monkeypatch.setattr(setup, "request", lambda release: None)
    shutil.rmtree(config.models_dir())
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is False and "search models" in res["message"]


def test_setup_errors_are_shown_verbatim(nothing_installed) -> None:
    setup._set("australia", "error", "Setup failed: not enough free disk space in /x.")
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is False and res["message"].startswith("Setup failed: not enough")


def test_lifespan_starts_setup(monkeypatch, fake_models) -> None:
    started = []
    monkeypatch.setattr(setup, "start", lambda: started.append(True))
    monkeypatch.setattr(setup, "request", lambda release: None)
    _call("snow_docs_status")
    assert started, "connecting a client must kick off setup"


# --- review round 4 ---------------------------------------------------------------------


def _drop(entry) -> None:
    config.index_file(entry).unlink()
    config.marker_file(entry).unlink()


def test_a_search_survives_a_snapshot_switch_mid_search(ready, fixture_db, monkeypatch) -> None:
    from snow_docs_mcp import server

    old = config.BUILTIN_ENTRIES["australia"]
    new = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32)
    real, calls = server.run_search, []

    def switching(db, *args, **kwargs):
        if not calls:  # another Claude app installs a newer snapshot and deletes this one
            install_index(fixture_db, new)
            _drop(old)
        calls.append(db)
        return real(db, *args, **kwargs)

    monkeypatch.setattr(server, "run_search", switching)
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is True and res["hits"] and res["snapshot"] == "2026-10-01"
    assert calls == [config.index_file(old), config.index_file(new)]


def test_an_index_that_disappears_mid_search_is_reported_plainly(ready, monkeypatch) -> None:
    from snow_docs_mcp import server

    monkeypatch.setattr(setup, "request", lambda release: None)
    setup._set("australia", "ready", "Ready.", 1.0)
    real = server.run_search

    def vanishing(db, *args, **kwargs):
        _drop(config.BUILTIN_ENTRIES["australia"])
        return real(db, *args, **kwargs)

    monkeypatch.setattr(server, "run_search", vanishing)
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is False and "missing" in res["message"]
    assert "Ready." not in res["message"] and "first use" not in res["message"]


def test_search_and_status_report_the_index_actually_used(ready, fixture_db, tmp_path) -> None:
    # latest.json rolled back to the 2026-05-15 build; a newer one is still on disk
    newer_db = tmp_path / "newer.db"
    newer_db.write_bytes(fixture_db.read_bytes())
    conn = sqlite3.connect(newer_db)
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'chunk_count'")
    conn.commit()
    conn.close()
    install_index(newer_db, make_entry(snapshot="2026-10-01", gz_sha="bb" * 32))
    old = config.BUILTIN_ENTRIES["australia"]
    setup._apply_latest(
        {
            "schema": 1,
            "indexes": {
                "australia": {
                    "snapshot": old.snapshot,
                    "url": "http://127.0.0.1:9/x.db.gz",
                    "gz_sha256": old.gz_sha256,
                }
            },
        }
    )
    assert _call("snow_docs_search", {"query": "incident"})["snapshot"] == "2026-05-15"
    au = {r["release"]: r for r in _call("snow_docs_status")["releases"]}["australia"]
    assert au["snapshot"] == "2026-05-15" and au["chunks"] == 6


def test_a_failed_model_download_is_named_in_search(ready, monkeypatch) -> None:
    import shutil

    monkeypatch.setattr(setup, "request", lambda release: None)
    shutil.rmtree(config.models_dir())
    setup._set("models", "error", "The search models could not be downloaded: proxy said no")
    setup._set("australia", "error", "Setup failed: proxy said no. It retries...")
    res = _call("snow_docs_search", {"query": "incident"})
    assert res["ok"] is False and "search models could not be downloaded" in res["message"]


def test_the_old_snapshots_memory_is_freed_after_a_switch(ready, fixture_db) -> None:
    from snow_docs_mcp import store

    old = config.BUILTIN_ENTRIES["australia"]
    assert _call("snow_docs_search", {"query": "incident"})["ok"]
    assert str(config.index_file(old).resolve()) in store._matrix_cache
    new = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32)
    install_index(fixture_db, new)  # the old file stays (e.g. Windows refused the delete)
    assert _call("snow_docs_search", {"query": "incident"})["snapshot"] == "2026-10-01"
    assert list(store._matrix_cache) == [str(config.index_file(new).resolve())]


def test_status_mentions_a_first_version_index_left_behind(ready) -> None:
    (config.data_home() / "index-2026-05-15.db").write_bytes(b"x")
    assert "index-2026-05-15.db" in _call("snow_docs_status")["update_note"]
