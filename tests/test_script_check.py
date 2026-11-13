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


USER = PAGE.replace("Scoped GlideRecord", "GlideUser").replace("getValue", "getName")
GETTERS = (
    "# GlideSystem\n\n## GlideSystem - getUser\\(\\)\n\nReturns the user.\n\n"
    "|Type|Description|\n|----|-----------|\n|GlideUser|The current user.|\n\n"
    "## GlideSystem - getProperty\\(String key\\)\n\nReturns a property.\n\n"
    "|Type|Description|\n|----|-----------|\n|String|The value.|\n"
)
TYPED = ApiTable(
    parse_page(GLOBAL_PATH, GLOBAL) + parse_page("u.md", USER) + parse_page("g.md", GETTERS)
)


def typed(code: str, **kw) -> list[str]:
    return [f.call for f in check(code, TYPED, **kw)]


def test_a_variable_gets_the_class_a_documented_method_returns():
    assert typed("var u = gs.getUser(); u.getName(); u.getNmae();") == ["GlideUser.getNmae"]
    # a method that returns a plain value gives no class to check against
    assert typed("var p = gs.getProperty('x'); p.anything();") == []


def test_a_chained_call_is_checked_against_the_returned_class():
    assert typed("gs.getUser().getName(); gs.getUser().getNmae();") == ["GlideUser.getNmae"]


def test_type_annotations_name_the_class():
    jsdoc = "/** @param {GlideRecord} rec */\nfunction f(rec) { rec.qurey(); }"
    ts = "function f(rec: GlideRecord, n: number) { rec.qurey(); n.toFixed(); }"
    assert typed(jsdoc) == ["GlideRecord.qurey"] and typed(ts) == ["GlideRecord.qurey"]


def test_the_usual_variable_names_are_taken_for_their_classes():
    assert typed(
        "function f(gr, grTask, now_GR) { gr.qurey(); grTask.qurey(); now_GR.qurey(); }"
    ) == ["GlideRecord.qurey"]
    # ... unless the code assigns the name something we cannot type
    assert typed("var gr = somethingElse(); gr.qurey();") == []


def test_table_names_the_docs_never_mention_are_reported():
    tables = frozenset({"incident", "sys_user", "change_request"})
    code = "var a = new GlideRecord('incidnet');\nvar b = new GlideRecord(\"sys_user\");\nvar c = new GlideRecord('u_my_table'); var d = new GlideRecord('x_acme_app_thing'); var e = new GlideRecord(name);"
    found = check(code, TYPED, tables=tables)
    assert [(f.kind, f.call, f.line, f.suggestions) for f in found] == [
        ("table", "incidnet", 1, ["incident"])
    ]
    assert check(code, TYPED) == []  # no table list: tables are not checked


def test_review_counts_what_it_could_check():
    from snow_docs_mcp.script_check import review

    r = review(
        "var gr = new GlideRecord('incident'); gr.query(); gr.qurey(); list.push(1);",
        TYPED,
        tables=frozenset({"incident"}),
    )
    assert (r.checked_calls, r.checked_tables, len(r.findings)) == (2, 1, 1)
