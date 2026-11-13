"""snow_docs_compare through the MCP surface, against two fixture releases."""

from __future__ import annotations

import json

import anyio
import pytest
from conftest import (
    CHUNKS,
    DOCS,
    build_fixture_index,
    fake_models_on_disk,
    install_index,
    make_entry,
)
from mcp import Client

from snow_docs_mcp import config, setup
from snow_docs_mcp.server import mcp

NOTES_PAGE = "markdown/delta-australia-brazil/brazil-australia-incident-release-notes.md"
NEW_PRIORITY = (
    "Priority is now set by the priority lookup rules table, which administrators maintain "
    "per assignment group."
)


def _big(release: str) -> str:
    return "# Big\n\n" + "\n".join(
        f"## Section {i}\n\n" + " ".join(f"{release}{i}word{j}" for j in range(40)) + "\n"
        for i in range(60)
    )


AU_DOCS = {**DOCS, "markdown/itsm/big.md": _big("au")}
BR_DOCS = {
    "markdown/itsm/incident.md": DOCS["markdown/itsm/incident.md"]
    .replace("release: australia", "release: brazil")
    .replace("Priority is calculated from impact and urgency.", NEW_PRIORITY),
    "markdown/hr/case.md": DOCS["markdown/hr/case.md"].replace(
        "title: HR case", "title: HR case\nrelease: brazil"
    ),
    "markdown/itsm/problem.md": DOCS["markdown/itsm/problem.md"].replace(
        "the root cause", "the underlying root cause"
    ),
    "markdown/itsm/big.md": _big("br"),
    NOTES_PAGE: "# Incident release notes\n\n## New\n\nPriority lookup rules replace the fixed "
    "matrix.\n\n## Changes\n\nPriority lookup rules can be maintained per assignment group.\n",
}
WORKSPACE_NOTES = (
    "markdown/delta-australia-brazil/brazil-australia-incidentworkspace-release-notes.md"
)
FLOWS_NOTES = (
    "markdown/delta-australia-brazil/brazil-australia-flowssubflowsandactions-release-notes.md"
)
_DELTA = "markdown/delta-australia-brazil/brazil-australia-"
for _path, _app in (
    (WORKSPACE_NOTES, "Incident Workspace"),
    (FLOWS_NOTES, "Flows, subflows, and actions"),
    (_DELTA + "agentworkspaceforhr-release-notes.md", "Agent Workspace for HR Case Handling"),
    (_DELTA + "legaldelivery-release-notes.md", "Legal Service Delivery"),
    (_DELTA + "workplacedelivery-release-notes.md", "Workplace Service Delivery"),
    (_DELTA + "incidentmanagement-release-notes.md", "Incident Management"),
    (_DELTA + "documentservices-release-notes.md", "Document Services"),
    (_DELTA + "documentintelligence-release-notes.md", "Document Intelligence \\(DocIntel\\)"),
    (_DELTA + "nowassistdocintel-release-notes.md", "Now Assist in Document Intelligence"),
    (_DELTA + "playbooks-release-notes.md", "Playbooks"),
    (_DELTA + "workflowstudioinsights-release-notes.md", "Workflow Studio Insights"),
    (_DELTA + "workflowstudiotemplates-release-notes.md", "Workflow Studio Templates"),
    (_DELTA + "recommendedws-release-notes.md", "Recommended Actions for WS"),
    (_DELTA + "workflowstudioreports-release-notes.md", "Workflow Studio Reports"),
    (_DELTA + "predictiveintelligence-release-notes.md", "Predictive Intelligence"),
    (_DELTA + "threatintelligence-release-notes.md", "Threat Intelligence Center"),
    (_DELTA + "policycompliance-release-notes.md", "Policy and Compliance Management"),
    (_DELTA + "riskmanagement-release-notes.md", "Risk Management"),
    # a second page for the same application, named with its abbreviation
    (_DELTA + "riskmanagementrm-release-notes.md", "Risk Management \\(RM\\)"),
):
    BR_DOCS[_path] = (
        f"---\ntitle: Combined {_app} release notes for upgrades from Australia to Brazil\n---\n\n"
        f"# Combined {_app} release notes\n\n## New features\n\nNothing here.\n"
    )

# The per-application release notes carry the product family in their breadcrumb.
for _file, _title, _crumbs in (
    ("flows-rn", "Flows, subflows, and actions release notes", "Workflow Studio release notes, "),
    ("playbooks-rn", "Playbooks release notes", "Workflow Studio release notes, "),
    ("incident-rn-2026", "Brazil Early Availability", "Incident Management release notes, "),
    ("studio-rn", "Workflow Studio Insights release notes", "Platform Analytics release notes, "),
):
    BR_DOCS[f"markdown/release-notes/{_file}.md"] = (
        f"---\ntitle: {_title}\nbreadcrumb: [{_crumbs}App development, and low-code release "
        "notes, Features and changes by product, Brazil release notes]\n---\n\n# Notes\n\nText.\n"
    )

# A family whose docs folder is not named like it: "GRC" is an alias of the folder
# governance-risk-compliance, and the family is "Governance, Risk, and Compliance".
for _file, _title in (
    ("policy-rn", "Policy and Compliance Management release notes"),
    ("risk-rn", "Risk Management release notes"),
):
    BR_DOCS[f"markdown/release-notes/{_file}.md"] = (
        f"---\ntitle: {_title}\nbreadcrumb: [Governance, Risk, and Compliance release notes, "
        "Features and changes by product, Brazil release notes]\n---\n\n# Notes\n\nText.\n"
    )

# Each application's own docs: the product area (top folder) they are in.
for _docs_path, _title in (
    ("markdown/build-workflows/flows/flows.md", "Flows, subflows, and actions"),
    ("markdown/build-workflows/templates/templates.md", "Workflow Studio Templates"),
    ("markdown/analytics/reports/reports.md", "Workflow Studio Reports"),
    ("markdown/governance-risk-compliance/policy/policy.md", "Policy and Compliance Management"),
    ("markdown/governance-risk-compliance/risk/risk.md", "Risk Management"),
):
    BR_DOCS[_docs_path] = f"---\ntitle: {_title}\n---\n\n# {_title}\n\nAbout it.\n"

BR_CHUNKS = [
    CHUNKS[0],
    (CHUNKS[1][0], CHUNKS[1][1], CHUNKS[1][2], NEW_PRIORITY),
    *CHUNKS[2:5],
    (
        NOTES_PAGE,
        "Incident release notes > New",
        "Release notes for incident.",
        "Priority lookup rules replace the fixed matrix.",
    ),
    (
        NOTES_PAGE,
        "Incident release notes > Changes",
        "Release notes for incident.",
        "Priority lookup rules can be maintained per assignment group.",
    ),
    # last, so the passages above keep their numbers: makes governance-risk-compliance a
    # product folder of the index
    (
        "markdown/governance-risk-compliance/risk/risk.md",
        "Risk Management",
        "Risk docs.",
        "About it.",
    ),
]


def _install(monkeypatch, tmp_path, releases):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    entries = {
        "australia": make_entry(),
        "brazil": make_entry(release="brazil", snapshot="2026-05-16", gz_sha="b2" * 32),
    }
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {r: entries[r] for r in releases})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    built = {
        "australia": lambda: build_fixture_index(tmp_path / "au.db", docs=AU_DOCS),
        "brazil": lambda: build_fixture_index(tmp_path / "br.db", docs=BR_DOCS, chunks=BR_CHUNKS),
    }
    for r in releases:
        install_index(built[r](), entries[r])
    fake_models_on_disk()


@pytest.fixture
def both(monkeypatch, tmp_path, fake_models):
    _install(monkeypatch, tmp_path, ["australia", "brazil"])
    return fake_models


@pytest.fixture
def australia_only(monkeypatch, tmp_path, fake_models):
    _install(monkeypatch, tmp_path, ["australia"])
    return fake_models


def call(name: str, **args):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, args)

    result = anyio.run(go)
    assert not result.is_error, result
    return result.structured_content


def test_tool_is_listed_read_only(both):
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    tool = next(t for t in anyio.run(go).tools if t.name == "snow_docs_compare")
    assert tool.annotations.model_dump(exclude_none=True).get("read_only_hint") is True
    assert set(tool.input_schema["properties"]) == {"query", "page", "product", "limit"}


def test_query_returns_release_notes_and_changed_pages(both):
    r = call("snow_docs_compare", query="incident priority")
    assert r["ok"], r
    assert r["australia_snapshot"] == "2026-05-15" and r["brazil_snapshot"] == "2026-05-16"
    assert r["release_notes"][0]["id"].startswith("brazil:markdown/delta-australia-brazil/")
    # the page that changed most first; problem.md has one small rewording
    assert [x["page"] for x in r["changed_pages"]] == [
        "markdown/itsm/incident.md",
        "markdown/itsm/problem.md",
    ]
    p = r["changed_pages"][0]
    assert p["page_title"] == "Incident management"
    (s,) = p["sections"]
    assert s["heading_path"] == "Incident management > Priority" and s["change"] == "changed"
    assert s["australia_id"].startswith("australia:") and s["brazil_id"].startswith("brazil:")
    assert "impact and urgency" in s["australia_excerpt"]
    assert "lookup rules" in s["brazil_excerpt"] and not s["small"]
    assert "2 changed pages" in r["message"]


def test_ids_round_trip_through_read(both):
    r = call("snow_docs_compare", page="markdown/itsm/incident.md")
    s = r["changed_pages"][0]["sections"][0]
    assert "lookup rules" in call("snow_docs_read", id=s["brazil_id"])["content"]
    assert "impact and urgency" in call("snow_docs_read", id=s["australia_id"])["content"]


def test_page_mode_accepts_id_and_bare_path(both):
    for page in (
        "australia:markdown/itsm/incident.md::Incident management > States",
        "markdown/itsm/incident.md",
        "itsm/incident",
    ):
        r = call("snow_docs_compare", page=page)
        assert r["changed_pages"][0]["page"] == "markdown/itsm/incident.md", page


def test_page_in_one_release_only(both):
    r = call("snow_docs_compare", page="markdown/itsm/change.md")
    assert r["ok"] and r["only_in_australia"] == ["markdown/itsm/change.md"]
    assert not r["changed_pages"] and "only in the australia docs" in r["message"]


def test_front_matter_only_page_reports_no_changes(both):
    r = call("snow_docs_compare", page="markdown/hr/case.md")
    assert r["ok"] and r["changed_pages"] == [] and "No documentation changes" in r["message"]


def test_unknown_page_suggests_close_paths(both):
    r = call("snow_docs_compare", page="markdown/itsm/incidnet.md")
    assert not r["ok"] and "markdown/itsm/incident.md" in r["message"]


def test_needs_exactly_one_of_query_and_page(both):
    assert not call("snow_docs_compare")["ok"]
    r = call("snow_docs_compare", query="x", page="markdown/itsm/incident.md")
    assert not r["ok"] and "query" in r["message"] and "page" in r["message"]


def test_unknown_product_gives_the_search_message(both):
    r = call("snow_docs_compare", query="priority", product="nonsense")
    s = call("snow_docs_search", query="priority", product="nonsense")
    assert not r["ok"] and r["message"] == s["message"]


def test_missing_brazil_index_is_explained(australia_only):
    r = call("snow_docs_compare", page="markdown/itsm/incident.md")
    assert not r["ok"]
    assert r["message"].startswith("Comparing needs both the australia and brazil docs.")
    assert r["changed_pages"] == [] and r["release_notes"] == []


def test_delta_pages_are_never_compared_as_documentation(both):
    r = call("snow_docs_compare", query="priority lookup rules release notes")
    assert r["ok"], r
    assert all(not p["page"].startswith("markdown/delta-") for p in r["changed_pages"])
    assert all(not p.startswith("markdown/delta-") for p in r["only_in_brazil"])


def test_limit_is_clamped_and_said(both):
    r = call("snow_docs_compare", query="incident priority", limit=99)
    assert r["ok"] and "limit adjusted to 20" in r["message"]


def test_result_stays_under_the_size_limit(both):
    r = call("snow_docs_compare", page="markdown/itsm/big.md")
    assert r["ok"], r
    assert len(json.dumps(r)) <= 12000
    assert r["changed_pages"][0]["sections_left_out"] > 0 and "left out" in r["message"]


def test_many_one_section_pages_still_fit_the_size_limit():
    from snow_docs_mcp import server

    def page(i: int) -> server.ChangedPage:
        path = f"markdown/it-service-management/a-rather-long-folder-name/page-number-{i}.md"
        sec = server.SectionDiff(
            heading_path="A long page title > A long section heading " * 2,
            change="changed",
            changed_words=20,
            australia_id=f"australia:{path}::" + "A long page title > A long section heading " * 2,
            brazil_id=f"brazil:{path}::" + "A long page title > A long section heading " * 2,
            australia_excerpt="old " * 75,
            brazil_excerpt="new " * 75,
        )
        return server.ChangedPage(
            page=path,
            page_title="A long page title",
            product="it-service-management",
            australia_url="https://www.servicenow.com/docs/r/australia/" + path,
            brazil_url="https://www.servicenow.com/docs/r/" + path,
            sections=[sec],
        )

    result = server.CompareResult(ok=True, message="", changed_pages=[page(i) for i in range(20)])
    _, pages_dropped = server._fit(result)
    assert pages_dropped > 0 and len(result.changed_pages) == 20 - pages_dropped
    assert len(json.dumps(result.model_dump())) + 800 <= 12000


@pytest.fixture
def nothing(monkeypatch, fake_models):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)


def test_a_small_rewording_is_shown_and_marked_small(both):
    """It used to be counted and hidden; "30 days" becoming "90 days" is a small rewording."""
    r = call("snow_docs_compare", page="markdown/itsm/problem.md")
    assert r["ok"] and len(r["changed_pages"]) == 1
    page = r["changed_pages"][0]
    (sec,) = page["sections"]
    assert sec["small"] and sec["australia_excerpt"] != sec["brazil_excerpt"]
    assert page["minor_changes"] == 1
    assert "1 small rewording" in r["message"] and "marked `small`" in r["message"]
    assert "not listed" not in r["message"] and "No documentation changes" not in r["message"]


def test_the_rules_no_longer_say_small_rewordings_are_hidden():
    from pathlib import Path

    from snow_docs_mcp import server

    root = Path(__file__).parent.parent
    texts = {
        "ANSWER_RULES": server.ANSWER_RULES,
        "UPGRADE_REVIEW_RULES": server.UPGRADE_REVIEW_RULES,
        **{
            name: (root / name).read_text(encoding="utf-8")
            for name in (
                "manifest.json",
                "README.md",
                "skills/servicenow-docs/SKILL.md",
                "skills/servicenow-upgrade-review/SKILL.md",
                "commands/upgrade-review.md",
            )
        },
    }
    for name, text in texts.items():
        assert "not listed" not in text, name
        assert "`small`" in text, name


def test_release_notes_lead_is_only_said_when_there_are_release_notes(both):
    r = call("snow_docs_compare", page="markdown/itsm/incident.md")
    assert "release notes" not in r["message"] and "cite ids as [id]" in r["message"].lower()
    q = call("snow_docs_compare", query="incident priority")
    assert "Lead with the release notes" in q["message"]


def test_page_accepts_urls_backslashes_and_other_case(both):
    for page in (
        "Australia:markdown/itsm/incident.md::",
        "markdown\\itsm\\incident.MD",
        "https://www.servicenow.com/docs/r/australia/itsm/incident.html",
        "https://www.servicenow.com/docs/r/some-other-folder/incident.html",
    ):
        r = call("snow_docs_compare", page=page)
        assert r["ok"] and r["changed_pages"][0]["page"] == "markdown/itsm/incident.md", page
    assert not call("snow_docs_compare", page="::")["ok"]


def test_both_indexes_missing_message_does_not_repeat_itself(nothing):
    r = call("snow_docs_compare", query="incident")
    assert not r["ok"] and r["message"].startswith("Comparing needs both")
    sentences = [x.strip() for x in r["message"].split(". ") if x.strip()]
    assert len(sentences) == len(set(sentences)), r["message"]


def test_index_replaced_twice_mid_call_says_not_ready(both, monkeypatch):
    from snow_docs_mcp import server

    def gone(*a, **k):
        raise FileNotFoundError("index-brazil.db")

    monkeypatch.setattr(server, "_compare", gone)
    r = call("snow_docs_compare", page="markdown/itsm/incident.md")
    assert not r["ok"] and r["message"].startswith("Comparing needs both")
    assert "Compare failed" not in r["message"]


def test_product_found_only_in_brazil_is_accepted(both):
    r = call("snow_docs_compare", query="priority", product="delta-australia-brazil")
    assert r["ok"], r


def test_product_gap_message_does_not_tell_you_to_search(both, monkeypatch):
    from snow_docs_mcp import server

    monkeypatch.setattr(
        server,
        "_product_problem",
        lambda *a: (
            "The australia docs snapshot has no X pages (5 in brazil). "
            "Search with release 'brazil' for these."
        ),
    )
    r = call("snow_docs_compare", query="priority", product="nonsense")
    assert not r["ok"] and "Search with release" not in r["message"]
    assert "can't be compared" in r["message"]


def test_sections_dropped_for_size_are_the_least_changed():
    from snow_docs_mcp import server

    secs = [
        server.SectionDiff(
            heading_path=f"Page > Section {i}",
            change="changed",
            changed_words=i + 8,
            australia_id=f"australia:markdown/a/p.md::Page > Section {i}",
            brazil_id=f"brazil:markdown/a/p.md::Page > Section {i}",
            australia_excerpt="old " * 70,
            brazil_excerpt="new " * 70,
        )
        for i in range(80)
    ]
    page = server.ChangedPage(page="markdown/a/p.md", page_title="Page", product="a", sections=secs)
    result = server.CompareResult(ok=True, message="", changed_pages=[page])
    server._fit(result)
    kept = [s.changed_words for s in result.changed_pages[0].sections]
    assert 0 < len(kept) < 80 and min(kept) == 88 - len(kept)
    assert kept == sorted(kept), "page order is kept"


def test_release_notes_give_one_passage_per_page(both):
    r = call("snow_docs_compare", query="priority lookup rules")
    pages = [h["id"].split("::")[0] for h in r["release_notes"]]
    assert pages == [f"brazil:{NOTES_PAGE}"], pages
    assert "1 release-notes page" in r["message"]


def test_release_notes_pages_are_also_found_by_application_name(both):
    r = call("snow_docs_compare", query="incident priority")
    more = r["more_release_notes"]
    assert [m["application"] for m in more] == ["Incident Management", "Incident Workspace"]
    assert more[1]["id"] == f"brazil:{WORKSPACE_NOTES}::"
    assert "2 more release-notes pages by name" in r["message"]
    assert "Nothing here" in call("snow_docs_read", id=more[1]["id"])["content"]


def test_a_name_that_search_misses_still_finds_its_release_notes_page(both):
    both.rerank_scores = {"": -5.0}  # search finds nothing relevant
    r = call("snow_docs_compare", query="Flow Designer")
    assert [m["application"] for m in r["more_release_notes"]] == ["Flows, subflows, and actions"]
    assert r["message"].startswith("1 release-notes page found by name (more_release_notes)")


def test_generic_words_do_not_match_every_release_notes_page(both):
    r = call("snow_docs_compare", query="service management for the release")
    assert r["more_release_notes"] == []


def test_by_name_matches_must_contain_the_rarest_query_word(both):
    both.rerank_scores = {"": -5.0}
    r = call("snow_docs_compare", query="HR Service Delivery")
    assert [m["application"] for m in r["more_release_notes"]] == [
        "Agent Workspace for HR Case Handling"
    ]


def test_a_query_that_names_one_application_only_lists_pages_with_that_whole_name(both):
    both.rerank_scores = {"": -5.0}
    r = call("snow_docs_compare", query="Document Intelligence")
    assert [m["application"] for m in r["more_release_notes"]] == [
        "Document Intelligence (DocIntel)",
        "Now Assist in Document Intelligence",
    ]
    r = call("snow_docs_compare", query="docintel")  # the abbreviation names it too
    assert [m["application"] for m in r["more_release_notes"]] == [
        "Document Intelligence (DocIntel)"
    ]


def test_a_query_that_names_a_product_family_lists_its_applications(both):
    both.rerank_scores = {"": -5.0}
    r = call("snow_docs_compare", query="Workflow Studio")
    # its applications and a page with the family's name that no breadcrumb lists; not the
    # page of another family (Insights), nor the one documented in another product area (Reports)
    assert [m["application"] for m in r["more_release_notes"]] == [
        "Workflow Studio Templates",
        "Flows, subflows, and actions",
        "Playbooks",
    ]
    r = call("snow_docs_compare", query="app development and low-code")  # a family with a comma
    assert sorted(m["application"] for m in r["more_release_notes"]) == [
        "Flows, subflows, and actions",
        "Playbooks",
        "Workflow Studio Insights",
    ]


def test_an_abbreviation_finds_its_family_when_the_folder_is_named_differently(both):
    """GRC -> the folder governance-risk-compliance; the family is "Governance, Risk, and
    Compliance". The family is the one whose applications are documented in that folder."""
    both.rerank_scores = {"": -5.0}
    r = call("snow_docs_compare", query="GRC")
    assert sorted(m["application"] for m in r["more_release_notes"]) == [
        "Policy and Compliance Management",
        "Risk Management",
        "Risk Management (RM)",
    ]


def test_two_pages_with_one_application_name_are_both_listed(both):
    both.rerank_scores = {"": -5.0}
    r = call("snow_docs_compare", query="Risk Management")
    assert [m["application"] for m in r["more_release_notes"]] == [
        "Risk Management",
        "Risk Management (RM)",
    ]
    assert len({m["id"] for m in r["more_release_notes"]}) == 2


def test_a_folder_that_only_the_other_release_has_says_which_release(both):
    """The combined upgrade notes (delta-australia-brazil) are in the brazil docs only."""
    r = call("snow_docs_browse", product="delta-australia-brazil")
    assert not r["ok"] and "release 'brazil'" in r["message"]
    assert "Valid products" not in r["message"]
    assert call("snow_docs_browse", product="delta-australia-brazil", release="brazil")["ok"]
    s = call("snow_docs_search", query="x", product="delta-australia-brazil")
    assert not s["ok"] and "release 'brazil'" in s["message"]
