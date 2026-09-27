"""Markdown escapes in front matter, doubled-release links, and misspelt code names.

Found in the 2026-09-27 comparison run against the 2026-09-24 Australia snapshot:
- canonical_url kept '\\_' ('.../c\\_GlideRecordAPI.html' returns HTTP 400), titles too;
- 7 of 9 read sections had links like '.../australia/markdown/australia/...' (HTTP 404);
- 'setMandatroy client script' scored above WEAK_SCORE, so no warning was given.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from test_read import read_section
from test_tools_inmemory import _call, ready  # noqa: F401  (pytest fixture)

from snow_docs_mcp import sections
from snow_docs_mcp.server import _code_names, _missing_names

RAW = "https://raw.githubusercontent.com/ServiceNow/ServiceNowDocs"

ESCAPED_DOC = f"""---
title: GlideForm \\(g\\_form\\) - Client
canonical_url: https://www.servicenow.com/docs/r/australia/api-reference/c\\_GlideFormAPI.html
---

# GlideForm \\(g\\_form\\) - Client

See [Form fields]({RAW}/australia/markdown/australia/platform-user-interface/c_FormFields.md)
and [UI policy]({RAW}/australia/markdown/platform-administration/ui-policy.md).
"""


def test_front_matter_values_are_unescaped() -> None:
    assert sections.front_matter_value(ESCAPED_DOC, "title") == "GlideForm (g_form) - Client"
    assert sections.front_matter_value(ESCAPED_DOC, "canonical_url") == (
        "https://www.servicenow.com/docs/r/australia/api-reference/c_GlideFormAPI.html"
    )


def test_unescape_keeps_plain_backslashes() -> None:
    assert sections.unescape_markdown(r"C:\temp \d+ a\_b") == r"C:\temp \d+ a_b"


def test_fix_links_drops_only_the_repeated_release_folder() -> None:
    fixed = sections.fix_links(ESCAPED_DOC)
    assert "markdown/australia/" not in fixed
    assert f"{RAW}/australia/markdown/platform-user-interface/c_FormFields.md" in fixed
    assert f"{RAW}/australia/markdown/platform-administration/ui-policy.md" in fixed  # untouched
    brazil = f"{RAW}/brazil/markdown/brazil/foo.md"
    assert sections.fix_links(brazil) == f"{RAW}/brazil/markdown/foo.md"


def test_read_returns_clean_url_title_and_links(fixture_db) -> None:
    conn = sqlite3.connect(fixture_db)
    conn.execute(
        "UPDATE documents SET content = ? WHERE file_path = 'markdown/hr/case.md'",
        (ESCAPED_DOC,),
    )
    conn.commit()
    conn.close()
    r = read_section(fixture_db, "markdown/hr/case.md::")
    assert r.ok, r.message
    assert r.title == "GlideForm (g_form) - Client"
    assert r.url.endswith("/c_GlideFormAPI.html")
    assert "markdown/australia/" not in r.content


def test_code_names_in_queries() -> None:
    assert _code_names("g_form.setMandatory") == ["g_form", "setMandatory"]
    assert _code_names("$sp.getParameter") == ["getParameter"]
    assert _code_names("sys_user_group table") == ["sys_user_group"]
    assert _code_names("how are incident priorities calculated") == []
    assert _code_names("record producer script producer.redirect") == []  # no code-like part


def test_missing_names_match_through_markdown_escapes() -> None:
    passages = [SimpleNamespace(content="GlideForm - g\\_form.setMandatory\\(String\\)")]
    assert _missing_names("g_form.setMandatory", passages) == []
    assert _missing_names("g_form.setMandatroy", passages) == ["setMandatroy"]


def test_search_flags_a_name_no_passage_contains(ready) -> None:  # noqa: F811
    res = _call("snow_docs_search", {"query": "setMandatroy client script"})
    assert res["ok"] is True and res["hits"]
    assert "'setMandatroy'" in res["message"] and "appears nowhere in the" in res["message"]


def test_search_does_not_flag_plain_queries(ready) -> None:  # noqa: F811
    res = _call("snow_docs_search", {"query": "incident priority"})
    assert "appears nowhere" not in res["message"] and "None of these passages" not in res["message"]
