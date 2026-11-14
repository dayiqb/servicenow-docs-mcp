"""The results panel (MCP Apps): wiring, and that the page stands on its own.

A host that supports MCP Apps renders the panel (`ui://servicenow-docs/panel-<digest>.html`) next
to the result of snow_docs_search and snow_docs_compare; every other client keeps getting the plain result.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import anyio
import pytest
from mcp import Client

from snow_docs_mcp import setup
from snow_docs_mcp.server import PANEL_URI, mcp, panel_html, panel_uri

APP_MIME = "text/html;profile=mcp-app"


@pytest.fixture(autouse=True)
def _no_setup(monkeypatch):
    monkeypatch.setattr(setup, "start", lambda: None)


def _run(coro_fn):
    async def go():
        async with Client(mcp) as client:
            return await coro_fn(client)

    return anyio.run(go)


def test_only_the_tools_that_show_something_point_at_the_panel():
    """Searching and browsing are how Claude finds its way; it does them many times for one
    answer. A panel for each of them fills the conversation with lists nobody asked to see, so
    the panel is drawn only for what is meant to be looked at."""
    tools = _run(lambda c: c.list_tools()).tools
    with_ui = {
        t.name for t in tools if (t.meta or {}).get("ui", {}).get("resourceUri") == PANEL_URI
    }
    assert with_ui == {"snow_docs_compare", "snow_docs_open"}


def test_the_panel_address_follows_what_the_panel_holds():
    """A host keeps the page it fetched under its address and does not ask again: after an
    upgrade Claude Desktop went on showing the previous panel, because the address was the same.
    So the address is made from the page, and another page has another address."""
    assert PANEL_URI == panel_uri(panel_html())
    assert re.fullmatch(r"ui://servicenow-docs/panel-[0-9a-f]{12}\.html", PANEL_URI)
    assert panel_uri(panel_html() + " ") != PANEL_URI


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
    assert called == {"snow_docs_search", "snow_docs_read", "snow_docs_browse"}


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


def test_readme_describes_the_panel_and_the_stand_in_host_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert "## The panel in Claude Desktop" in (root / "README.md").read_text(encoding="utf-8")
    host = (root / "scripts" / "panel_host.html").read_text(encoding="utf-8")
    assert "ui/initialize" in host and "/src/snow_docs_mcp/ui/panel.html" in host


def test_the_page_draws_no_diagrams():
    """Figures are Claude's to draw, where the client has a place for them (in Claude Code, the
    figures pane). The page had a drawing engine of its own, with a step list under every figure:
    long, and no match for a figure drawn for the concept. It is gone, and so is \"Show as flow\"."""
    html = panel_html()
    for gone in ("snow_docs_diagram", "showDiagram", "flowToggle", "chart-wrap", "<svg"):
        assert gone not in html


# ---- what the page puts on the screen ---------------------------------------------------------
#
# The page's own script is run by node against a small stand-in for the DOM (panel_harness.mjs),
# on real docs sections (tests/fixtures/panel, as snow_docs_read returns them).


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src" / "snow_docs_mcp" / "ui" / "panel.html"
FIXTURES = ROOT / "tests" / "fixtures" / "panel"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _render(*cases):
    done = subprocess.run(
        [NODE, str(ROOT / "tests" / "panel_harness.mjs"), str(PANEL)],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    results = json.loads(done.stdout)
    for result in results:
        assert not (isinstance(result, dict) and "error" in result), result["error"]
    return results


def _page(name: str) -> str:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["content"]


def _dom(markup: str) -> ET.Element:
    return ET.fromstring(f"<root>{markup}</root>")


def _markdown(text: str) -> ET.Element:
    (markup,) = _render({"op": "markdown", "text": text})
    return _dom(markup)


def _text(node: ET.Element) -> str:
    return " ".join("".join(node.itertext()).split())


@needs_node
def test_sub_steps_stay_inside_their_step():
    # "You can trigger this workflow in two ways": step 1 has three sub-steps.
    root = _markdown(_page("steps-nested"))
    (steps,) = root.findall("./ol")
    assert steps.get("start") is None and len(steps.findall("./li")) == 2
    first, second = steps.findall("./li")
    assert _text(first.find("./p")) == "Recommend solutions button"
    assert len(first.findall("./ol/li")) == 3
    assert _text(second).startswith("Navigate to the ServiceNow Otto panel")


@needs_node
def test_a_procedure_keeps_its_numbers_and_what_belongs_to_each_step():
    source = _page("steps-substeps")
    top_level = [line for line in source.split("\n") if re.match(r"\d+\.\s", line)]
    assert len(top_level) == 3
    root = _markdown(source)
    (steps,) = root.findall("./ol")
    items = steps.findall("./li")
    assert steps.get("start") is None and len(items) == len(top_level)
    # step 1: its bullets and the paragraph after them belong to it
    assert len(items[0].findall("./ul/li")) == 2
    assert _text(items[0].findall("./p")[-1]).startswith("For details on installing")
    # step 3: numbered sub-steps, with their code block inside the sub-step
    assert len(items[2].findall("./ol/li")) >= 3
    assert items[2].find("./ol/li/pre") is not None
    # the list is the procedure: there is no second drawing of it as boxes
    assert root.findall(".//div[@class='flow-of']") == []


@needs_node
def test_a_list_that_restarts_after_a_paragraph_keeps_its_number():
    root = _markdown("1. One\n2. Two\n\nA word in between.\n\n3. Three\n4. Four\n")
    first, second = root.findall("./ol")
    assert first.get("start") is None and second.get("start") == "3"


@needs_node
def test_a_table_at_the_margin_after_a_step_belongs_to_that_step():
    # "3. Fill in the fields, as appropriate." <table> ... </table>4.  Click **Submit**.
    root = _markdown(_page("table-colspan"))
    (steps,) = root.findall("./ol")
    items = steps.findall("./li")
    assert len(items) == 4 and items[2].find("./div/table") is not None
    assert _text(items[3]) == "Click Submit."


@needs_node
def test_a_list_glued_to_the_end_of_a_line_is_a_list():
    root = _markdown(
        "This can be:-   Draft\n-   Published\n-   Closed\n\nOptions:1.  Low\n2.  High\n"
    )
    assert [_text(p) for p in root.findall("./p")] == ["This can be:", "Options:"]
    assert [_text(li) for li in root.findall("./ul/li")] == ["Draft", "Published", "Closed"]
    assert [_text(li) for li in root.findall("./ol/li")] == ["Low", "High"]
    plain = _markdown("A well-known - if rare - case, and version 1.  Two spaces.")
    assert (
        len(plain.findall("./p")) == 1 and plain.find("./ul") is None and plain.find("./ol") is None
    )


@needs_node
def test_bold_links_bold_code_and_italics_are_not_shown_as_markup():
    links = _markdown(_page("links-bold"))
    bold = [a for a in links.iter("a") if a.text == "Create a customer success definition record"]
    assert bold and bold[0].get("href", "").startswith("https://www.servicenow.com/docs/")
    assert any(strong.find("a") is not None for strong in links.iter("strong"))
    assert "](" not in _text(links) and "**" not in _text(links)

    code = _markdown(_page("code-bold"))
    names = [_text(c) for strong in code.iter("strong") for c in strong.findall("code")]
    assert "ReferenceError: X is not defined" in names
    assert "`" not in "".join(_text(s) for s in code.iter("strong"))

    italic = _markdown(_page("italic"))
    assert "additionally" in [_text(em) for em in italic.iter("em")]


@needs_node
def test_inline_text():
    cases = {
        "a __bold__ word": "<p>a <strong>bold</strong> word</p>",
        "***both***": "<p><strong><em>both</em></strong></p>",
        "the sys_user_has_role table and my_var_name": (
            "<p>the sys_user_has_role table and my_var_name</p>"
        ),
        r"a \*literal\* star and 5 * 3 * 2": "<p>a *literal* star and 5 * 3 * 2</p>",
        "See [Flow](https://en.wikipedia.org/wiki/Flow_(psychology)) now": (
            '<p>See <a href="https://en.wikipedia.org/wiki/Flow_(psychology)">Flow</a> now</p>'
        ),
        "``a `tick` b`` here": "<p><code>a `tick` b</code> here</p>",
        "**All** &gt; **System Definition** &amp; more": (
            "<p><strong>All</strong> &gt; <strong>System Definition</strong> &amp; more</p>"
        ),
        "[local](../other.md) and [bad](javascript:alert(1))": "<p>local and bad</p>",
        r"Plugin \[com.sn\_x\]. See [Plugins](https://example.com/p)": (
            '<p>Plugin [com.sn_x]. See <a href="https://example.com/p">Plugins</a></p>'
        ),
        "use `sys_select.<table name>.<field name>` here": (
            "<p>use <code>sys_select.&lt;table name&gt;.&lt;field name&gt;</code> here</p>"
        ),
    }
    results = _render(*({"op": "inline", "text": text} for text in cases))
    assert dict(zip(cases, results, strict=True)) == cases
    (plain,) = _render(
        {"op": "plain", "text": r"**Cost** types and [sub-vendor](https://x.example) \(new\)"}
    )
    assert plain == "Cost types and sub-vendor (new)"
    # the docs sometimes have bold around nothing, where a name was left out
    (empty,) = _render({"op": "plain", "text": "…Enterprise Architecture&gt;. - **** Set a rate"})
    assert empty == "…Enterprise Architecture>. - Set a rate"


@needs_node
def test_a_table_keeps_placeholders_lists_spans_and_code():
    placeholder = _markdown(_page("table-placeholder"))
    cells = [_text(td) for td in placeholder.iter("td")]
    assert 'Field to highlight in the following format: "<table-name>.<field-name>".' in cells
    values = [td for td in placeholder.iter("td") if _text(td).startswith("How long the label")]
    assert [_text(li) for li in values[0].findall("./ul/li")][:2] == [
        "2: Flashes for 1 second",
        "0: Flashes for 2 seconds",
    ]

    icons = _markdown(_page("table-list"))
    longest = max(len(td.findall("./ul/li")) for td in icons.iter("td"))
    assert longest >= 40

    assert any(td.get("colspan") == "2" for td in _markdown(_page("table-colspan")).iter("td"))
    assert any(td.get("rowspan") == "3" for td in _markdown(_page("table-rowspan")).iter("td"))
    assert any(td.find("./pre") is not None for td in _markdown(_page("table-code")).iter("td"))


@needs_node
def test_a_table_inside_a_table_is_a_table_and_what_follows_it_is_kept():
    root = _markdown(_page("table-nested"))
    outer = [t for t in root.iter("table") if t.find(".//table") is not None]
    assert len(outer) == 1
    inner = outer[0].find(".//td/div/table")
    assert inner is not None and len(inner.findall("./tr")) == 6
    assert [len(tr) for tr in outer[0].findall("./tr")] == [2, 2]
    assert not re.search(r"</?(?:td|tr|tbody|table)\b", _text(root))
    # the example that follows the table on the same line
    assert "nn.getStatus()" in _text(root.findall("./pre")[-1])


@needs_node
def test_text_that_looks_like_a_table_tag_is_text():
    root = _markdown("Before.\n\n<table-name> is a placeholder.\n\nUse `<table>` here.\n\nEnd.")
    assert [_text(p) for p in root.findall("./p")] == [
        "Before.",
        "<table-name> is a placeholder.",
        "Use <table> here.",
        "End.",
    ]


@needs_node
def test_the_servers_own_note_about_a_cut_section_is_not_shown():
    root = _markdown("Some text.\n\n[… truncated — raise max_chars to see more]")
    assert _text(root) == "Some text."


def _show(result: dict, args: dict | None = None, open: list[int] | None = None) -> ET.Element:
    (markup,) = _render({"op": "show", "result": result, "args": args or {}, "open": open or []})
    return _dom(markup)


@needs_node
def test_a_small_rewording_is_shown_with_its_words_marked():
    section = {
        "heading_path": "Retention > Closed cases", "change": "changed", "changed_words": 2,
        "small": True, "australia_id": "australia:markdown/x.md::A", "brazil_id": "brazil:markdown/x.md::A",
        "australia_excerpt": "…closed cases are kept for 30 days before they…",
        "brazil_excerpt": "…closed cases are kept for 90 days before they…",
    }  # fmt: skip
    page = {"page": "markdown/x.md", "page_title": "Retention", "product": "customer-service-management",
            "sections": [section, {**section, "small": False, "heading_path": "Retention > Overview"}],
            "minor_changes": 1, "sections_left_out": 0}  # fmt: skip
    root = _show({"ok": True, "message": "", "release_notes": [], "more_release_notes": [],
                  "changed_pages": [page], "only_in_australia": [], "only_in_brazil": []},
                 {"query": "retention"})  # fmt: skip
    kinds = [_text(k) for k in root.iter("span") if (k.get("class") or "").startswith("kind")]
    assert kinds == ["Small rewording", "Changed"]
    assert [_text(d) for d in root.iter("del")] == ["30", "30"]
    assert [_text(i) for i in root.iter("ins")] == ["90", "90"]
    assert "not listed" not in _text(root)


@needs_node
def test_each_reader_in_a_comparison_names_its_release():
    section = {"heading_path": "A > B", "change": "changed", "changed_words": 9, "small": False,
               "australia_id": "australia:markdown/x.md::A", "brazil_id": "brazil:markdown/x.md::A",
               "australia_excerpt": "one two", "brazil_excerpt": "one three"}  # fmt: skip
    page = {"page": "markdown/x.md", "page_title": "A", "product": "x", "sections": [section]}
    root = _show({"ok": True, "message": "", "release_notes": [], "more_release_notes": [],
                  "changed_pages": [page], "only_in_australia": [], "only_in_brazil": []})  # fmt: skip
    buttons = [_text(b) for b in root.iter("button") if b.get("class") == "act"]
    assert buttons == ["Read in Australia", "Read in Brazil"]


# ---- the page as text: rules that hold for every line of it -------------------------------------


def _style() -> str:
    return re.search(r"<style>(.*?)</style>", panel_html(), re.DOTALL).group(1)


@needs_node
def test_every_string_exists_in_english_and_norwegian():
    html = panel_html()
    (words,) = _render({"op": "words"})
    assert set(words["en"]) == set(words["nb"]) and len(words["en"]) > 40
    used = set(re.findall(r"""\bt\(\s*["'](\w+)["']\s*[,)]""", html))
    assert used <= set(words["en"]), used - set(words["en"])
    assert "sectionOf" not in html and "Ingen avsnitt passet" not in html
    assert "not listed" not in html and "ikke listet" not in html


def test_type_sizes_and_spacing_stay_on_the_scale():
    css = _style()
    # sizes come from the four variables; nothing sets a size of its own
    assert set(re.findall(r"--(?:meta|secondary|body|title): ([\d.]+rem)", css)) == {
        "0.75rem", "0.875rem", "1rem", "1.25rem",
    }  # fmt: skip
    assert re.findall(r"font-size:\s*(?!\s|var\(--(?:meta|secondary|body|title)\))[^;]+;", css) == [
        "font-size: 16px;"
    ]
    for shorthand in re.findall(r"font:\s*([^;]+);", css):
        assert re.match(
            r"(?:inherit|(?:400|500|600) var\(--(?:meta|secondary|body|title)\))", shorthand
        ), shorthand
    assert set(re.findall(r"font-weight:\s*(\d+)", css)) <= {"400", "500", "600"}
    for name, value in re.findall(r"(?<![\w-])(padding|margin|gap)(?:-[a-z]+)?:\s*([^;]+);", css):
        for size in re.findall(r"(?<![\w.-])(\d+(?:\.\d+)?)px", value):
            assert float(size) % 4 == 0, (name, value)


def test_marked_words_and_the_way_to_the_other_release_do_not_rely_on_colour():
    css = _style()
    assert re.search(r"\bdel\s*\{[^}]*text-decoration:\s*line-through", css)
    assert re.search(r"\bins\s*\{[^}]*text-decoration:\s*underline", css)
    # the release shown is said in words; the button to the other one is underlined text
    assert re.search(r"\.switch\s*\{[^}]*text-decoration:\s*underline", css)
    assert "radiogroup" not in panel_html() and 'type: "radio"' not in panel_html()


def test_focus_is_not_dropped_and_the_size_report_can_shrink():
    html = panel_html()
    # a focused control that is disabled loses the focus: the page marks it busy instead
    assert ".disabled = true" not in html and "aria-busy" in html
    assert "scrollHeight" not in html
    assert "DOMParser" not in html


def test_only_web_addresses_go_to_the_host():
    html = panel_html()
    assert "const WEB = /^https?:\\/\\//i;" in html
    assert html.count('request("ui/open-link"') == 1
    opener = html[html.index("function openLink") :][:200]
    assert "if (!WEB.test(String(url))) return;" in opener


# ---- accessibility audit of the rendered page (accesslint, 2026-11-13) ------------------------


@needs_node
def test_a_document_has_no_gap_in_its_heading_levels():
    """The page title is the h1, so the page's own headings start at h2; in a reader under a
    search hit (whose title is an h2) they start at h3."""
    text = "## Before you begin\n\nRole required: admin\n\n### Procedure\n\nDo it.\n"
    (document,) = _render({"op": "markdown", "text": text, "anchors": True})
    assert [n.tag for n in _dom(document) if n.tag.startswith("h")] == ["h2", "h3"]
    (reader,) = _render({"op": "markdown", "text": text})
    assert [n.tag for n in _dom(reader) if n.tag.startswith("h")] == ["h3", "h4"]


@needs_node
def test_a_note_is_a_note_not_a_page_landmark():
    """`aside` is a landmark that must be at the top of the page; a note sits in the text, in a
    step or in a table cell."""
    root = _markdown("Text.\n\n> **Note:** Activate the plugin first.\n")
    assert root.find(".//aside") is None
    (note,) = root.findall(".//div[@role='note']")
    assert "Activate the plugin first" in _text(note)


def test_the_status_for_screen_readers_is_inside_the_main_landmark():
    html = panel_html()
    main = html[html.index("<main>") : html.index("</main>")]
    assert 'id="app"' in main and 'id="live"' in main and 'role="status"' in main


@needs_node
def test_a_bold_label_is_not_glued_to_what_follows():
    """31,569 pages end with `**Parent Topic:**[Page](url)`, written without a space."""
    (markup,) = _render(
        {"op": "inline", "text": "**Parent Topic:**[Risk and issues page](https://x.test/y)"}
    )
    assert _text(_dom(markup)) == "Parent Topic: Risk and issues page"
    (spaced,) = _render({"op": "inline", "text": "**Role:** admin, **Time:**5 min. **Bold**text"})
    assert _text(_dom(spaced)) == "Role: admin, Time: 5 min. Boldtext"
    (after,) = _render({"op": "inline", "text": "the rule runs on.**Note:** The list is short."})
    assert _text(_dom(after)) == "the rule runs on. Note: The list is short."


@needs_node
def test_a_first_heading_that_repeats_the_title_is_not_shown_twice():
    text = "# Define priority lookup rules\n\nIntro.\n\n## Procedure\n\nDo it.\n"
    (shown,) = _render({"op": "document", "text": text, "title": "Define priority lookup rules"})
    (body,) = _dom(shown["html"])
    assert [n.tag for n in body] == ["p", "h2", "p"]
    assert shown["anchors"] == ["Procedure"]
    (other,) = _render({"op": "document", "text": text, "title": "Another title"})
    (body,) = _dom(other["html"])
    assert next(n.tag for n in body) == "h2" and len(other["anchors"]) == 2


# ---- results as a tree: closed rows that open in place (2026-11-13) -----------------------------


def _hit(n: int, product: str, title: str, section: str = "") -> dict:
    path = title + (" > " + section if section else "")
    return {"id": f"australia:markdown/{product}/p{n}.md::{section or title}", "page_title": title,
            "full_title": title, "heading_path": path, "product": product,
            "snippet": f"{path} Passage number {n} says something.",
            "url": f"https://docs.test/p{n}"}  # fmt: skip


def _search(*hits: dict) -> dict:
    return {"ok": True, "message": "", "release": "australia", "snapshot": "2026-11-06",
            "hits": list(hits)}  # fmt: skip


def _has(node: ET.Element, name: str) -> bool:
    return name in (node.get("class") or "").split()


def _part(node: ET.Element, name: str) -> str:
    return " ".join(_text(s) for s in node.iter("span") if _has(s, name))


def _folds(root: ET.Element, heading: str) -> list[ET.Element]:
    return [h.find("button") for h in root.iter(heading) if h.find("button") is not None]


def _bodies(root: ET.Element) -> list[ET.Element]:
    return [d for d in root.iter("div") if _has(d, "fold-body")]


@needs_node
def test_search_hits_are_grouped_by_product_area_and_start_closed():
    root = _show(
        _search(
            _hit(1, "it-service-management", "Create an SLA definition"),
            _hit(2, "employee-service-management", "Create an SLA Definition", "Procedure"),
            _hit(3, "it-service-management", "SLA definition", "Schedule"),
        ),
        {"query": "sla"},
    )
    areas = _folds(root, "h2")
    assert [(_part(a, "fold-name"), _part(a, "fold-count"), a.get("aria-expanded")) for a in areas] == [
        ("IT Service Management", "2 passages", "true"),
        ("Employee Service Management", "1 passage", "true"),
    ]  # fmt: skip
    hits = _folds(root, "h3")
    # an area stands where its best hit is, and every hit keeps the rank the search gave it
    assert [(_part(h, "rank"), _part(h, "fold-name"), _part(h, "fold-more")) for h in hits] == [
        ("1", "Create an SLA definition", ""),
        ("3", "SLA definition", "Schedule"),
        ("2", "Create an SLA Definition", "Procedure"),
    ]
    assert [h.get("aria-expanded") for h in hits] == ["false"] * 3
    bodies = _bodies(root)
    assert len(bodies) == 3 and all(b.get("hidden") is not None for b in bodies)
    assert [h.get("aria-controls") for h in hits] == [b.get("id") for b in bodies]


@needs_node
def test_opening_a_hit_shows_its_passage_and_what_can_be_done_with_it():
    result = _search(_hit(1, "it-service-management", "Create an SLA definition"))
    root = _show(result, {"query": "sla"}, open=[1])  # fold 0 is the area, fold 1 the hit
    (hit,) = _folds(root, "h3")
    (body,) = _bodies(root)
    assert hit.get("aria-expanded") == "true" and body.get("hidden") is None
    assert _text(body.find("blockquote")) == "Passage number 1 says something."
    assert [_text(b) for b in body.iter("button")] == ["Read section", "Open docs"]
    (again,) = _bodies(_show(result, {"query": "sla"}, open=[1, 1]))
    assert again.get("hidden") is not None


@needs_node
def test_an_area_can_be_closed():
    result = _search(_hit(1, "it-service-management", "A"), _hit(2, "it-service-management", "B"))
    root = _show(result, {"query": "x"}, open=[0])
    (area,) = _folds(root, "h2")
    (leaves,) = [u for u in root.iter("ul") if _has(u, "leaves")]
    assert area.get("aria-expanded") == "false" and leaves.get("hidden") is not None
    assert area.get("aria-controls") == leaves.get("id")


def _change(heading: str, change: str = "changed", small: bool = False) -> dict:
    return {"heading_path": heading, "change": change, "changed_words": 2, "small": small,
            "australia_id": "australia:markdown/x.md::A", "brazil_id": "brazil:markdown/x.md::A",
            "australia_excerpt": "kept for 30 days", "brazil_excerpt": "kept for 90 days"}  # fmt: skip


def _compare(pages: list[dict], notes: list[dict] | None = None) -> dict:
    return {"ok": True, "message": "", "release_notes": notes or [], "more_release_notes": [],
            "changed_pages": pages, "only_in_australia": [], "only_in_brazil": []}  # fmt: skip


@needs_node
def test_changed_pages_are_closed_rows_that_open_into_their_sections():
    pages = [
        {"page": "markdown/x.md", "page_title": "Retention", "product": "customer-service-management",
         "sections": [_change("Retention > Closed cases", small=True), _change("Retention > Overview", "added")]},
        {"page": "markdown/y.md", "page_title": "Archiving", "product": "it-service-management",
         "sections": [_change("Archiving > Rules")]},
    ]  # fmt: skip
    root = _show(_compare(pages), {"query": "retention"})
    rows = _folds(root, "h3")
    assert [(_part(r, "fold-name"), _part(r, "fold-more"), _part(r, "fold-count"), r.get("aria-expanded")) for r in rows] == [
        ("Retention", "Customer Service Management", "2 sections", "false"),
        ("Archiving", "IT Service Management", "1 section", "false"),
    ]  # fmt: skip
    sections = _folds(root, "h4")
    assert [
        (_part(s, "fold-name"), _part(s, "kind"), s.get("aria-expanded")) for s in sections
    ] == [
        ("Closed cases", "Small rewording", "false"),
        ("Overview", "Added", "false"),
        ("Rules", "Changed", "false"),
    ]
    assert all(b.get("hidden") is not None for b in _bodies(root))
    opened = _show(
        _compare(pages), {"query": "retention"}, open=[0, 1]
    )  # the page, then its first section
    shown = [b for b in _bodies(opened) if b.get("hidden") is None]
    assert len(shown) == 1 and [_text(d) for d in shown[0].iter("del")] == ["30"]


@needs_node
def test_one_page_asked_for_lists_its_sections_without_a_row_for_the_page():
    page = {"page": "markdown/x.md", "page_title": "Retention", "product": "customer-service-management",
            "sections": [_change("Retention > Closed cases"), _change("Retention > Overview")]}  # fmt: skip
    root = _show(_compare([page]), {"page": "australia:markdown/x.md::"})
    assert _text(root.find(".//h1")) == "Retention"
    sections = _folds(root, "h3")
    # the page's title is the heading of the panel, so a row does not say it again
    assert [_part(s, "fold-name") for s in sections] == ["Closed cases", "Overview"]
    assert [s.get("aria-expanded") for s in sections] == ["false", "false"] and not _folds(
        root, "h4"
    )
    assert "null" not in _text(root) and "undefined" not in _text(root)


@needs_node
def test_release_notes_are_closed_rows_too():
    note = {**_hit(1, "delta-brazil", "Combined Now Assist release notes for upgrades from Australia", "Changed"),
            "page_title": "Combined Now Assist release notes for upgrades from Australia"}  # fmt: skip
    root = _show(_compare([], [note]), {"query": "now assist"})
    (row,) = _folds(root, "h3")
    assert (_part(row, "fold-name"), _part(row, "fold-more"), row.get("aria-expanded")) == (
        "Now Assist",
        "Changed",
        "false",
    )
    (body,) = _bodies(root)
    assert body.get("hidden") is not None and [_text(b) for b in body.iter("button")] == [
        "Read section",
        "Open docs",
    ]


def test_what_is_hidden_is_not_drawn_and_long_text_scrolls_inside_the_panel():
    css = _style()
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", css)
    for box in (".reader-body", ".doc-body", ".rows"):
        rule = re.escape(box) + r"\s*\{[^}]*max-height:\s*\d+rem[^}]*overflow:\s*auto"
        assert re.search(rule, css), box
    # the frame is as tall as its content, so a height taken from the frame feeds on itself
    assert "100vh" not in css


@needs_node
def test_a_document_that_scrolls_can_be_reached_with_the_keyboard():
    (shown,) = _render({"op": "document", "text": "Intro.\n", "title": "A page"})
    (body,) = _dom(shown["html"])
    assert (body.get("tabindex"), body.get("role"), body.get("aria-label")) == (
        "0",
        "region",
        "A page",
    )


# ---- the other release: one quiet button where the release is named (2026-11-13) ---------------


def _switch(root: ET.Element) -> ET.Element:
    (count,) = [p for p in root.iter("p") if _has(p, "count")]
    (button,) = [b for b in count.iter("button") if _has(b, "switch")]
    return button


@needs_node
def test_the_other_release_is_one_button_on_the_line_that_names_the_release():
    result = _search(_hit(1, "it-service-management", "Create an SLA definition"))
    root = _show(result, {"query": "sla"})
    assert _text(_switch(root)) == "Switch to Brazil" and not list(root.iter("input"))
    (count,) = [s for s in root.iter("span") if _has(s, "count-text")]
    assert _text(count) == "1 passage, from the Australia docs, snapshot 6 Nov 2026"
    brazil = _show({**result, "release": "brazil"}, {"query": "sla"})
    assert _text(_switch(brazil)) == "Switch to Australia"


@needs_node
def test_a_document_has_the_same_button_to_the_other_release():
    page = {"ok": True, "message": "", "id": "australia:markdown/x.md::", "focus": "", "title": "A page",
            "url": "", "release": "australia", "product": "it-service-management", "headings": []}  # fmt: skip
    assert _text(_switch(_show(page))) == "Switch to Brazil"
