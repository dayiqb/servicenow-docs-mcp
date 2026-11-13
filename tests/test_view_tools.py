"""The tools that exist to show something to the user in the panel: snow_docs_open (a page as
a document) and snow_docs_diagram (a flow or swimlanes built from steps the docs give)."""

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
        "snow_docs_diagram",
    }
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


STEPS = [
    {"id": "new", "label": "Incident is created", "kind": "start", "lane": "caller"},
    {"id": "triage", "label": "Set impact and urgency", "lane": "desk", "source_id": STATES},
    {
        "id": "major",
        "label": "Major incident?",
        "kind": "decision",
        "lane": "desk",
        "source_id": STATES,
    },
    {"id": "resolve", "label": "Resolve the incident", "lane": "desk", "source_id": STATES},
    {"id": "closed", "label": "Closed after 7 days", "kind": "end", "lane": "caller"},
]
LINKS = [
    {"source": "new", "target": "triage"},
    {"source": "triage", "target": "major"},
    {"source": "major", "target": "resolve", "label": "No"},
    {"source": "resolve", "target": "closed"},
]
LANES = [{"id": "caller", "label": "Caller"}, {"id": "desk", "label": "Service desk"}]


def test_a_swimlane_diagram_comes_back_checked_with_a_text_form(docs):
    r = call("snow_docs_diagram", title="Incident lifecycle", steps=STEPS, links=LINKS, lanes=LANES)
    assert r["ok"] and r["kind"] == "swimlane" and r["title"] == "Incident lifecycle"
    assert [s["id"] for s in r["steps"]] == ["new", "triage", "major", "resolve", "closed"]
    assert r["links"][2] == {"source": "major", "target": "resolve", "label": "No"}
    m = r["mermaid"]
    # the text form names steps s1, s2, ... and lanes lane1, ...: the caller's ids stay in
    # `steps`, and no id the caller picks can break the Mermaid syntax
    assert m.startswith("flowchart TD") and 'subgraph lane1["Caller"]' in m
    assert (
        's3{"Major incident?"}' in m
        and 's3 -- "No" --> s4' in m
        and 's1(["Incident is created"])' in m
    )
    assert "5 steps" in r["message"] and "2 lanes" in r["message"]


def test_without_links_the_steps_follow_each_other_and_without_lanes_it_is_a_flow(docs):
    plain = [{k: v for k, v in s.items() if k != "lane"} for s in STEPS]
    r = call("snow_docs_diagram", title="Lifecycle", steps=plain)
    assert r["ok"] and r["kind"] == "flow" and r["lanes"] == []
    assert [(link["source"], link["target"]) for link in r["links"]] == [
        ("new", "triage"),
        ("triage", "major"),
        ("major", "resolve"),
        ("resolve", "closed"),
    ]


def test_a_diagram_that_does_not_hold_together_is_refused_with_every_problem(docs):
    broken = [
        {"id": "a", "label": "One"},
        {"id": "a", "label": "Two", "lane": "nobody"},
        {"id": "c", "label": "Three", "source_id": "australia:markdown/itsm/missing.md::"},
    ]
    r = call(
        "snow_docs_diagram",
        title="x",
        steps=broken,
        links=[{"source": "a", "target": "zzz"}],
        lanes=LANES,
    )
    assert not r["ok"] and r["steps"] == []
    for problem in ("'a' is used by more than one step", "lane 'nobody'", "'zzz'", "missing.md"):
        assert problem in r["message"], problem
    assert not call("snow_docs_diagram", title="x", steps=[{"id": "a", "label": "Only one"}])["ok"]


def test_steps_without_a_source_are_counted_in_the_message(docs):
    plain = [{"id": "a", "label": "First"}, {"id": "b", "label": "Second", "source_id": STATES}]
    r = call("snow_docs_diagram", title="x", steps=plain)
    assert r["ok"] and "1 step has no source" in r["message"]


def test_no_step_or_lane_id_can_break_the_text_form(docs):
    """`end` is the natural id of an end step and a Mermaid keyword; `a--` reads as an arrow."""
    steps = [
        {"id": "end", "label": "Start here", "kind": "start", "lane": "desk"},
        {"id": "a--", "label": 'Say "hello"', "lane": "desk"},
        {"id": "desk", "label": "Done", "kind": "end", "lane": "subgraph"},
    ]
    lanes = [{"id": "desk", "label": "Service desk"}, {"id": "subgraph", "label": "Caller"}]
    r = call("snow_docs_diagram", title="x", steps=steps, lanes=lanes)
    assert r["ok"], r["message"]
    assert [s["id"] for s in r["steps"]] == ["end", "a--", "desk"]
    lines = [line.strip() for line in r["mermaid"].splitlines()]
    assert lines == [
        "flowchart TD",
        'subgraph lane1["Service desk"]',
        's1(["Start here"])',
        "s2[\"Say 'hello'\"]",
        "end",
        'subgraph lane2["Caller"]',
        's3(["Done"])',
        "end",
        "s1 --> s2",
        "s2 --> s3",
    ]


def test_lanes_are_checked_like_steps(docs):
    steps = [
        {"id": "a", "label": "One", "lane": "desk"},
        {"id": "b", "label": "Two", "lane": "desk"},
    ]
    for lanes, problem in (
        ([{"id": "desk", "label": "A"}, {"id": "desk", "label": "B"}], "more than one lane"),
        ([{"id": "desk", "label": "A"}, {"id": "the desk", "label": "B"}], "lane id 'the desk'"),
        ([{"id": "desk", "label": "  "}], "lane 'desk' has no label"),
    ):
        r = call("snow_docs_diagram", title="x", steps=steps, lanes=lanes)
        assert not r["ok"] and problem in r["message"], (lanes, r["message"])
