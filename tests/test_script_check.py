"""Checking the methods a script calls against the API table."""

from __future__ import annotations

from test_api_table import GLOBAL, GLOBAL_PATH, PAGE, PATH

from snow_docs_mcp.api_table import ApiTable, parse_page
from snow_docs_mcp.script_check import check

SYSTEM = PAGE.replace("Scoped GlideRecord", "GlideSystem").replace("getValue", "getProperty")
FORM = PAGE.replace("Scoped GlideRecord", "GlideForm").replace("addEncodedQuery", "setMandatory")
TABLE_MEMBERS = (
    parse_page(PATH, PAGE)
    + parse_page(GLOBAL_PATH, GLOBAL)
    + parse_page("markdown/api-reference/gs.md", SYSTEM)
    + parse_page("markdown/api-reference/form.md", FORM)
)
TABLE = ApiTable(TABLE_MEMBERS)


def names(code: str) -> list[str]:
    return [f.call for f in check(code, TABLE)]


def test_documented_calls_pass():
    code = """
    var gr = new GlideRecord('incident');
    gr.addEncodedQuery('active=true');
    gr.query();
    while (gr.next()) { gs.getProperty('x'); current.getValue('number'); }
    """
    assert names(code) == ["GlideRecord.next"]  # not in this small table: reported


def test_an_invented_method_is_reported_once_with_the_closest_names():
    code = (
        "var gr = new GlideRecord('task');\ngr.addEncodedQuerry('a');\ngr.addEncodedQuerry('b');\n"
    )
    (f,) = check(code, TABLE)
    assert f.call == "GlideRecord.addEncodedQuerry" and f.line == 2
    assert f.suggestions == ["GlideRecord.addEncodedQuery"]


def test_variables_from_let_const_and_plain_assignment_are_followed():
    code = "const a = new GlideRecord('x'); let b = new GlideRecord('y');\nc = new GlideRecord('z');\na.foo(); b.bar(); c.baz();"
    assert names(code) == ["GlideRecord.foo", "GlideRecord.bar", "GlideRecord.baz"]


def test_known_variables_and_static_class_calls_are_checked():
    assert names("g_form.setMandatroy('x', true); gs.getProperty('a'); gs.getPropertee('a');") == [
        "GlideForm.setMandatroy",
        "GlideSystem.getPropertee",
    ]
    assert names("GlideSystem.nope();") == ["GlideSystem.nope"]


def test_unknown_receivers_fields_and_plain_javascript_are_left_alone():
    code = """
    var list = [1, 2]; list.push(3); JSON.stringify(list); console.log('x');
    current.state.changes(); current.assigned_to.getDisplayValue();
    var other = new SomethingElse(); other.whatever();
    """
    assert names(code) == []


def test_comments_and_strings_are_not_code():
    code = """
    // gs.notAMethod()
    /* g_form.alsoNot() */
    var s = "gs.stillNot()"; var t = 'gs.nope()';
    gs.getProperty('gs.inside()');
    """
    assert names(code) == []


def test_code_without_servicenow_calls_gives_nothing_and_is_fast():
    assert check("function add(a, b) { return a + b; }\n" * 2000, TABLE) == []


def test_findings_are_capped():
    code = "\n".join(f"gs.madeUp{i}();" for i in range(40))
    found = check(code, TABLE, limit=10)
    assert len(found) == 10 and found[0].call == "GlideSystem.madeUp0"


def test_class_names_are_matched_with_their_exact_case():
    table = ApiTable(
        TABLE_MEMBERS + parse_page("d.md", PAGE.replace("Scoped GlideRecord", "Document"))
    )
    assert [f.call for f in check("document.querySelector('a'); Document.nope();", table)] == [
        "Document.nope"
    ]
    assert [f.call for f in check("var d = new document(); d.x(); gliderecord.y();", table)] == []
