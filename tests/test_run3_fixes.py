"""Fixes from the 2026-09-27 comparison run (tester run 3) that the tester's patch did not cover:
site addresses per release, links between docs pages, method-name ranking, product
abbreviations, missing docs areas per release, typo notes, and the fast rerank setting.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_tools_inmemory import _call, ready  # noqa: F401  (pytest fixture)

from snow_docs_mcp import config, identifiers, products, read, sections, setup, store
from snow_docs_mcp.config import CoverageGap
from snow_docs_mcp.search import snippet
from snow_docs_mcp.server import _did_you_mean

RAW = "https://raw.githubusercontent.com/ServiceNow/ServiceNowDocs"
SITE = "https://www.servicenow.com/docs/r/"


# --- front matter, snippets ---------------------------------------------------------------


def test_front_matter_quotes_are_removed_only_as_a_pair() -> None:
    assert sections.plain_value(" 'Crawl' stage reports ") == "'Crawl' stage reports"
    assert sections.plain_value("Setting a variable to 'NULL'") == "Setting a variable to 'NULL'"
    assert sections.plain_value('"Quoted title"') == "Quoted title"
    assert sections.plain_value(r"GlideForm \(g\_form\)") == "GlideForm (g_form)"


def test_snippet_header_is_unescaped_and_links_become_text() -> None:
    chunk = (
        "---\ntitle: GlideForm \\(g\\_form\\) - Client\ndescription: 'Crawl' stage\n---\n"
        f"See [Form fields]({RAW}/australia/markdown/australia/x/y.md) for more."
    )
    text = snippet(chunk)
    assert text.startswith("GlideForm (g_form) - Client: 'Crawl' stage")
    assert "See Form fields for more." in text and "http" not in text


# --- site addresses -------------------------------------------------------------------------


def _page(url: str, release: str = "") -> str:
    rel = f"release: {release}\n" if release else ""
    return f"---\ntitle: T\ncanonical_url: {url}\n{rel}---\n\nBody\n"


@pytest.mark.parametrize("url,page_release,index_release,expected", [
    # the newest release's pages carry no release folder: pin brazil
    (f"{SITE}it-service-management/incident.html", "brazil", "brazil",
     f"{SITE}brazil/it-service-management/incident.html"),
    (f"{SITE}delta-australia-brazil/rn.html", "brazil", "brazil",
     f"{SITE}brazil/delta-australia-brazil/rn.html"),
    # older releases' notes shipped in the brazil docs: those pages live under australia
    (f"{SITE}delta-zurich-australia/rn.html", "australia", "brazil",
     f"{SITE}australia/delta-zurich-australia/rn.html"),
    # left alone: already has a release folder, or a folder that works as it is
    (f"{SITE}australia/it-service-management/incident.html", "australia", "australia",
     f"{SITE}australia/it-service-management/incident.html"),
    (f"{SITE}delta-washingtondc-australia/rn.html", "australia", "australia",
     f"{SITE}delta-washingtondc-australia/rn.html"),
    # no release in the page: the index's release decides
    (f"{SITE}csm/cases.html", "", "brazil", f"{SITE}brazil/csm/cases.html"),
    ("https://example.com/other", "brazil", "brazil", "https://example.com/other"),
])
def test_site_url(url, page_release, index_release, expected) -> None:
    assert sections.site_url(_page(url, page_release), index_release) == expected


def test_site_url_is_empty_without_canonical_url() -> None:
    assert sections.site_url("---\ntitle: T\n---\nBody", "brazil") == ""


# --- links between docs pages -------------------------------------------------------------


def test_rewrite_doc_links() -> None:
    known = {
        "markdown/itsm/incident.md": f"{SITE}australia/itsm/incident.html",
    }
    text = (
        f"[Incidents]({RAW}/australia/markdown/australia/itsm/incident.md#anchor) and "
        f"[Gone]({RAW}/australia/markdown/itsm/gone.md), [Root]({RAW}/australia/markdown), "
        f"bare {RAW}/brazil/markdown/itsm/incident.md, bare dead {RAW}/brazil/markdown/x/old-page.md "
        "and [elsewhere](https://store.servicenow.com/app)."
    )
    out = sections.rewrite_doc_links(text, lambda fp: known.get(fp, ""))
    assert f"[Incidents]({SITE}australia/itsm/incident.html)" in out
    assert "Gone," in out and "gone.md" not in out
    assert "[Root]" not in out and "Root" in out
    assert f"bare {SITE}australia/itsm/incident.html," in out
    assert "bare dead old-page and" in out
    assert "[elsewhere](https://store.servicenow.com/app)" in out  # other links untouched
    assert "raw.githubusercontent.com" not in out


def test_read_resolves_links_through_the_index(ready, fixture_db) -> None:  # noqa: F811
    conn = sqlite3.connect(fixture_db)
    conn.execute(
        "UPDATE documents SET content = content || ? WHERE file_path = 'markdown/hr/case.md'",
        (
            (
                f"\nSee [Incidents]({RAW}/australia/markdown/australia/itsm/incident.md), "
                f"[Problems]({RAW}/australia/markdown/itsm/moved/problem.md) and "
                f"[Nothing]({RAW}/australia/markdown/itsm/nothing.md).\n"
            ),
        ),
    )
    conn.commit()
    conn.close()
    store.forget(fixture_db)
    r = read.read_section(fixture_db, "australia", "markdown/hr/case.md", "")
    assert r.ok, r.message
    assert "[Incidents](https://www.servicenow.com/docs/r/incident.html)" in r.content
    # the page moved: found by its file name, linked to its source (no canonical_url)
    assert "[Problems](https://github.com/" in r.content and "problem.md)" in r.content
    assert "Nothing" in r.content and "nothing.md" not in r.content
    assert "raw.githubusercontent.com" not in r.content


def test_store_mentions_and_page_paths(fixture_db) -> None:
    assert store.mentions(fixture_db, "zebrafish")
    assert store.mentions(fixture_db, "ZEBRAfish") is False  # a capital: case matters
    assert not store.mentions(fixture_db, "zebrafsh")
    assert not store.mentions(fixture_db, "...")
    paths, by_name = store.page_paths(fixture_db)
    assert "markdown/itsm/incident.md" in paths and by_name["case.md"] == ["markdown/hr/case.md"]


# --- method names --------------------------------------------------------------------------


def test_code_identifiers() -> None:
    assert identifiers.code_identifiers("GlideRecord addEncodedQuery") == [
        "GlideRecord", "addEncodedQuery"
    ]
    assert "setMandatory" in identifiers.code_identifiers("g_form.setMandatory()")
    assert "getParameter" in identifiers.code_identifiers("$sp.getParameter")
    assert identifiers.code_identifiers("ServiceNow incident priority, e.g. impact") == []


def _hit(heading: str, score: float):
    return SimpleNamespace(heading_path=heading, score=score)


def test_prefer_exact_puts_the_named_method_first() -> None:
    hits = [
        _hit("GlideRecord - Global > GlideRecord - addSystemEncodedQuery\\(String query\\)", 7.27),
        _hit("GlideRecord - Scoped > GlideRecord - addEncodedQuery\\(String query\\)", 6.89),
        _hit("GlideRecord - Global > GlideRecord - addEncodedQuery\\(String query\\)", 6.71),
    ]
    out = identifiers.prefer_exact("GlideRecord addEncodedQuery", hits)
    assert [h.score for h in out] == [6.89, 6.71, 7.27]
    assert [h.score for h in hits] == [7.27, 6.89, 6.71]  # input untouched, scores unchanged


def test_search_orders_hits_through_prefer_exact(ready, monkeypatch) -> None:  # noqa: F811
    plain = [h["id"] for h in _call("snow_docs_search", {"query": "incident", "limit": 3})["hits"]]
    monkeypatch.setattr(identifiers, "prefer_exact", lambda q, hits: list(reversed(hits)))
    flipped = [h["id"] for h in _call("snow_docs_search", {"query": "incident", "limit": 3})["hits"]]
    assert flipped != plain and len(flipped) == len(plain) == 3


def test_prefer_exact_ignores_class_names_alone_parent_headings_and_arguments() -> None:
    hits = [_hit("Intro", 5.0), _hit("GlideRecord - Global", 4.0)]
    assert identifiers.prefer_exact("GlideRecord overview", hits) == hits  # class name alone
    hits = [_hit("Intro", 5.0), _hit("addEncodedQuery > Example", 4.0)]
    assert identifiers.prefer_exact("addEncodedQuery example", hits) == hits  # parent heading
    hits = [_hit("Intro", 5.0), _hit("GlideSysAttachment - getContent(GlideRecord att)", 4.0)]
    assert identifiers.prefer_exact("GlideRecord", hits) == hits  # only in the argument list


# --- product filter ------------------------------------------------------------------------


KNOWN = ["employee-service-management", "hr", "it-service-management", "now-platform",
         "servicenow-platform"]


@pytest.mark.parametrize("value,expected", [
    ("itsm", ("it-service-management", "alias")),
    ("HRSD", ("employee-service-management", "alias")),
    ("IT Service Management", ("it-service-management", "exact")),
    ("it_service_management/", ("it-service-management", "exact")),
    ("hr", ("hr", "exact")),  # a real folder wins over an abbreviation
    ("now-platform", ("servicenow-platform", "alias")),  # 5 landing pages -> the real area
    ("api", ("api-reference", "alias-absent")),
    ("esm", ("", "unknown")),  # Enterprise or Employee Service Management: ambiguous
    ("xyz", ("", "unknown")),
])
def test_product_resolve(value, expected) -> None:
    assert products.resolve(value, KNOWN) == expected


def test_product_suggestions() -> None:
    paths = ["markdown/it-service-management/incident-management/a.md",
             "markdown/employee-service-management/hr-case/b.md"]
    assert products.suggestions("incident management", KNOWN, paths)[0] == "it-service-management"
    assert "it-service-management" in products.suggestions("itsn", KNOWN, paths)


def test_search_notes_an_abbreviation(ready, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setitem(products.ALIASES, "incidents", "itsm")
    res = _call("snow_docs_search", {"query": "priority", "product": "incidents"})
    assert res["ok"] and {h["product"] for h in res["hits"]} == {"itsm"}
    assert "searched the itsm docs for 'incidents'" in res["message"]


# --- missing docs areas --------------------------------------------------------------------


API_GAP = CoverageGap("api-reference", "API Reference", 0, 1227)


def test_coverage_gaps_parse_and_skip_malformed() -> None:
    raw = {
        "snapshot": "2026-09-24", "gz_sha256": "a" * 64, "url": "https://x/y.db.gz",
        "coverage_gaps": {"compared_with": "australia", "products": [
            {"product": "api-reference", "title": "API Reference", "pages": 0, "of": 1227},
            {"product": "Bad Name", "title": "x", "pages": 0, "of": 5},
            {"product": "esm", "pages": 9, "of": 9},  # not a gap
            {"product": "esm", "pages": "1", "of": 9},
            "junk",
        ]},
    }
    e = config.IndexEntry.from_json("brazil", raw)
    assert e.coverage_gaps == (API_GAP,) and e.gaps_compared_with == "australia"
    assert e == replace(e, coverage_gaps=(), gaps_compared_with="")  # metadata, not identity
    assert config.IndexEntry.from_json("brazil", {**raw, "coverage_gaps": "x"}).coverage_gaps == ()


def test_coverage_gaps_apply_only_to_the_snapshot_they_describe(ready) -> None:  # noqa: F811
    entry = config.BUILTIN_ENTRIES["australia"]
    with setup._state_lock:
        setup._latest["australia"] = replace(
            entry, coverage_gaps=(API_GAP,), gaps_compared_with="brazil"
        )
    try:
        assert setup.coverage_gaps("australia") == ((API_GAP,), "brazil")
        with setup._state_lock:
            setup._latest["australia"] = replace(
                entry, snapshot="2030-01-01", coverage_gaps=(API_GAP,), gaps_compared_with="brazil"
            )
        assert setup.coverage_gaps("australia") == ((), "")
    finally:
        with setup._state_lock:
            setup._latest.pop("australia", None)


def test_search_names_missing_areas_and_where_to_look(ready, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(setup, "coverage_gaps", lambda rel: ((API_GAP,), "brazil"))
    res = _call("snow_docs_search", {"query": "incident priority"})
    assert "lacks API Reference; for those, search release 'brazil'" in res["message"]
    res = _call("snow_docs_search", {"query": "addEncodedQuery", "product": "api"})
    assert res["ok"] is False
    assert "has no API Reference pages (1,227 in brazil)" in res["message"]
    filtered = _call("snow_docs_search", {"query": "priority", "product": "itsm"})
    assert "lacks" not in filtered["message"]  # itsm isn't one of the gaps


def test_filtered_search_on_a_partial_gap_says_so(ready, monkeypatch) -> None:  # noqa: F811
    partial = CoverageGap("itsm", "IT Service Management", 2, 500)
    monkeypatch.setattr(setup, "coverage_gaps", lambda rel: ((API_GAP, partial), "brazil"))
    res = _call("snow_docs_search", {"query": "priority", "product": "itsm"})
    assert res["ok"] and "lacks most of IT Service Management (2 of 500 pages); for those, " \
        "search release 'brazil'" in res["message"]
    assert "API Reference" not in res["message"]  # only the searched area's gap


def test_search_has_no_gaps_note_without_gaps(ready) -> None:  # noqa: F811
    assert "lacks" not in _call("snow_docs_search", {"query": "incident"})["message"]


# --- typo notes ----------------------------------------------------------------------------


def test_did_you_mean_suggests_the_closest_code_name() -> None:
    passages = [SimpleNamespace(content="Use g\\_form.setMandatory\\(String\\) and setValue.")]
    assert _did_you_mean(["setMandatroy"], passages) == {"setMandatroy": "setMandatory"}
    assert _did_you_mean(["totallyDifferent"], passages) == {}


def test_search_says_whether_a_missing_name_exists_elsewhere(ready) -> None:  # noqa: F811
    db = setup.active_index("australia")  # the installed copy the server searches
    conn = sqlite3.connect(db)  # a code name that exists in the docs, on an itsm page
    conn.execute(
        "UPDATE chunks SET content = content || ' Call setWorkflowSkip first.' "
        "WHERE file_path = 'markdown/itsm/change.md'"
    )
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    store.forget(db)
    # filtered to hr: the name is in the docs, just not in these passages
    elsewhere = _call("snow_docs_search", {"query": "setWorkflowSkip case", "product": "hr"})
    assert "'setWorkflowSkip' is in the australia docs but not in these passages; if the " \
        "question is about it, search for it by name." in elsewhere["message"]
    assert "appears nowhere" not in elsewhere["message"]
    # misspelt: nowhere in the docs, and the right name is in the candidates
    typo = _call("snow_docs_search", {"query": "setWorkflowSkp change approval"})
    assert "'setWorkflowSkp' (did you mean 'setWorkflowSkip'?) appears nowhere in the " \
        "australia docs" in typo["message"]
    # spelt right and in the candidates: no note
    right = _call("snow_docs_search", {"query": "setWorkflowSkip change approval"})
    assert "setWorkflowSkip" not in right["message"]


def test_did_you_mean_falls_back_to_heading_names() -> None:
    passages = [SimpleNamespace(content="Client script order and design.")]
    assert _did_you_mean(["setMandatroy"], passages) == {}
    def more():
        return frozenset({"setMandatory", "setDisplay"})

    assert _did_you_mean(["setMandatroy"], passages, more) == {"setMandatroy": "setMandatory"}


def test_typo_note_uses_heading_names_and_mentions_gaps(ready, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(store, "heading_code_names", lambda db: frozenset({"setWorkflowSkip"}))
    res = _call("snow_docs_search", {"query": "setWorkflowSkp case", "product": "hr"})
    assert "'setWorkflowSkp' (did you mean 'setWorkflowSkip'?) appears nowhere" in res["message"]
    assert "a typo, or a custom name?" in res["message"]
    hr_gap = CoverageGap("hr", "HR", 1, 600)
    monkeypatch.setattr(setup, "coverage_gaps", lambda rel: ((hr_gap,), "brazil"))
    res = _call("snow_docs_search", {"query": "setWorkflowSkp case", "product": "hr"})
    assert "or part of an area these docs lack (see the note)?" in res["message"]
    assert "lacks most of HR (1 of 600 pages)" in res["message"]
    monkeypatch.setattr(setup, "coverage_gaps", lambda rel: ((API_GAP,), "brazil"))
    res = _call("snow_docs_search", {"query": "setWorkflowSkp case", "product": "hr"})
    assert "(see the note)" not in res["message"]  # no note in this result to point at


def test_heading_code_names(ready) -> None:  # noqa: F811
    db = setup.active_index("australia")
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE chunks SET heading_path = 'GlideForm \\(g\\_form\\) > setMandatory\\(String\\)' "
        "WHERE file_path = 'markdown/itsm/problem.md'"
    )
    conn.commit()
    conn.close()
    store.forget(db)
    names = store.heading_code_names(db)
    assert {"setMandatory", "GlideForm", "g_form"} <= names
    assert "Incident" not in names and "String" not in names


# --- fast rerank setting -------------------------------------------------------------------


@pytest.mark.parametrize("value,expected", [
    ("", "standard"), ("fast", "fast"), (" FAST ", "fast"), ("turbo", "standard"),
])
def test_rerank_profile(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("SNOW_DOCS_RERANK", value)
    assert config.rerank_profile() == expected
    assert config.RERANK_PROFILES["standard"] == (25, 800)


# --- review fixes (2026-09-28) -------------------------------------------------------------


def test_member_names_count_only_in_api_heading_form() -> None:
    hits = [_hit("VMware credentials", 7.06),
            _hit("Discovery for VMware vCenter > vCenter Discovery on Windows host", 5.61)]
    assert identifiers.prefer_exact("vCenter discovery credentials", hits) == hits
    hits = [_hit("Procedure", 7.3), _hit("iOS push notifications", 5.6)]
    assert identifiers.prefer_exact("iOS mobile app push notifications", hits) == hits
    hits = [_hit("RESTAPIRequest - getHeaders", 7.0), _hit("RESTAPIRequest - getHeader", 6.5)]
    assert [h.score for h in identifiers.prefer_exact("RESTAPIRequest getHeader", hits)] == [6.5, 7.0]


def test_table_names_alone_never_reorder() -> None:
    hits = [_hit("Computer [cmdb_ci_computer] class > Attributes", 7.53),
            _hit("Service Graph Connector > Computer [cmdb_ci_computer]", 6.0)]
    assert identifiers.prefer_exact("cmdb_ci_computer attributes", hits) == hits


def test_mentions_needs_the_name_itself_not_its_words(ready) -> None:  # noqa: F811
    db = setup.active_index("australia")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE chunks SET content = content || ' Pick one, e.g. from the g form list.' "
                 "WHERE file_path = 'markdown/itsm/problem.md'")
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    store.forget(db)
    assert store.mentions(db, "g_form") is False  # words, not the name
    assert store.mentions(db, "g_from") is False


def test_missing_names_are_whole_words_case_aware_and_skip_customer_names() -> None:
    from snow_docs_mcp.server import _code_names, _missing_names

    passages = [SimpleNamespace(content="Call g\\_form.setMandatory\\(\\) here.")]
    assert _missing_names("setMandatory", passages) == []
    assert _missing_names("SetMandatory", passages) == ["SetMandatory"]  # JavaScript case
    assert _missing_names("setMandat", passages) == ["setMandat"]  # not a prefix match
    assert _code_names("u_category x_acme_app_table assignment_group") == ["assignment_group"]


def test_closest_needs_a_close_match_or_one_edit() -> None:
    from snow_docs_mcp.server import _closest, _one_edit

    assert _one_edit("g_from", "g_form") and _one_edit("setValue", "setValues")
    assert not _one_edit("g_from", "g_from") and not _one_edit("abcdef", "abcxyz")
    assert _closest("g_from", {"g_form", "g_list"}) == "g_form"
    assert _closest("setCallerDetails", {"getCartDetails"}) == ""  # 0.80: not close enough


def test_names_note_lists_at_most_three_and_agrees_in_number(ready) -> None:  # noqa: F811
    one = _call("snow_docs_search", {"query": "fooBarBaz incident"})["message"]
    assert "'fooBarBaz' appears nowhere" in one
    many = _call("snow_docs_search", {"query": "aaaBbb cccDdd eeeFff gggHhh incident"})["message"]
    assert "'aaaBbb', 'cccDdd', 'eeeFff' appear nowhere" in many and "gggHhh" not in many


def test_link_text_with_escaped_brackets_keeps_only_its_text() -> None:
    text = (f"[Script Debugger \\[Omitted image \"icon.png\"\\] Alt text]({RAW}/brazil/markdown/"
            f"x/script-debugger.md) and [T\\_x]({RAW}/brazil/markdown/y/t\\_Add.md)")
    known = {"markdown/y/t_Add.md": f"{SITE}brazil/y/t_Add.html"}
    out = sections.rewrite_doc_links(text, lambda fp: known.get(fp, ""))
    assert "(script-debugger)" not in out and "Script Debugger" in out
    assert f"({SITE}brazil/y/t_Add.html)" in out  # an escaped path still resolves


def test_retain_frees_caches_of_indexes_only_read(fixture_db, tmp_path) -> None:
    store.page_paths(fixture_db)
    store.heading_code_names(fixture_db)
    key = str(fixture_db.resolve())
    assert key in store._paths_cache and key not in store._matrix_cache
    store.retain(set())
    assert key not in store._paths_cache and key not in store._heading_words_cache


def test_suggestions_break_ties_by_name() -> None:
    paths = ["markdown/zeta/approvals/a.md", "markdown/alpha/approvals/b.md"]
    assert products.suggestions("approvals", ["alpha", "zeta"], paths) == ["alpha", "zeta"]
    # no area named exactly that: areas whose name contains the word decide, ties by name
    paths = ["markdown/zeta/legal-approvals/a.md", "markdown/alpha/hr-approvals/b.md"]
    assert products.suggestions("approvals", ["alpha", "zeta"], paths) == ["alpha", "zeta"]


def test_search_pool_leaves_room_for_duplicates(ready, monkeypatch) -> None:  # noqa: F811
    from snow_docs_mcp import models, server

    seen = []
    real = server.run_search
    monkeypatch.setattr(models, "RERANK_POOL", 20)  # the fast profile
    monkeypatch.setattr(server, "run_search", lambda *a, **k: seen.append(k["top_k"]) or real(*a, **k))
    _call("snow_docs_search", {"query": "incident", "limit": 20})
    _call("snow_docs_search", {"query": "incident", "limit": 5})
    assert seen == [25, 20]


@pytest.mark.parametrize("value,expected", [("true", "fast"), ("false", "standard"), ("1", "fast")])
def test_rerank_profile_accepts_the_desktop_checkbox(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("SNOW_DOCS_RERANK", value)
    assert config.rerank_profile() == expected


def test_manifest_offers_fast_search() -> None:
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[1] / "manifest.json").read_text())
    option = manifest["user_config"]["fast_search"]
    assert option["type"] == "boolean" and option["default"] is False
    env = manifest["server"]["mcp_config"]["env"]
    assert env["SNOW_DOCS_RERANK"] == "${user_config.fast_search}"
