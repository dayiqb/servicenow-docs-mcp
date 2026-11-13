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


# --- scopes, declared names and what counts as code ------------------------------------------

from test_api_table import CLIENT, UIB_API, UIB_HELPERS, _page

AGGREGATE = PAGE.replace("Scoped GlideRecord", "GlideAggregate").replace(
    "addEncodedQuery", "addAggregate"
)
WIDE = ApiTable(
    parse_page(GLOBAL_PATH, GLOBAL)
    + parse_page("agg.md", AGGREGATE)
    + parse_page("u.md", USER)
    + parse_page("g.md", GETTERS)
    + parse_page("api.md", UIB_API)
    + parse_page("helpers.md", UIB_HELPERS)
    + parse_page("client.md", CLIENT)
    + [
        m
        for name in ("sb", "logger", "action", "Event", "Message")
        for m in parse_page(
            f"{name}.md", _page(f"{name} - Global", "A class.", f"{name} - run\\(\\)")
        )
    ]
    + parse_page(
        "table.md",
        _page(
            "Table - Scoped, Global",
            "It is provided within the `sn_pdfgeneratorutils` namespace.",
            "Table - addCell\\(String text\\)",
        ),
    )
)


def wide(code: str, **kw) -> list[str]:
    return [f.call for f in check(code, WIDE, **kw)]


def test_a_variable_has_the_class_its_own_function_gives_it():
    code = """
    var Util = Class.create();
    Util.prototype = {
        close: function(id) {
            var gr = new GlideRecord('incident');
            gr.addEncodedQuery('x'); gr.query(); gr.addAggregate('COUNT');
        },
        count: function() {
            var gr = new GlideAggregate('incident');
            gr.addAggregate('COUNT'); gr.query(); gr.addEncodedQuery('x');
        },
        type: 'Util'
    };
    """
    assert wide(code) == ["GlideRecord.addAggregate", "GlideAggregate.addEncodedQuery"]


def test_a_variable_given_another_class_is_checked_against_the_latest():
    code = (
        "var x = new GlideRecord('a'); x.addAggregate('COUNT');\n"
        "x = new GlideAggregate('a'); x.addAggregate('COUNT'); x.addEncodedQuery('q');\n"
        "x = other(); x.anything();"
    )
    assert wide(code) == ["GlideRecord.addAggregate", "GlideAggregate.addEncodedQuery"]


def test_a_function_sees_the_variables_around_it():
    code = (
        "function run() { gr.qurey(); inner(); function inner() { gr.query(); } }\n"
        "var gr = new GlideRecord('x');"
    )
    assert wide(code) == ["GlideRecord.qurey"]


def test_a_jsdoc_type_belongs_to_the_function_it_is_written_above():
    code = """
    var U = Class.create();
    U.prototype = {
        /** @param {GlideRecord} record */
        a: function(record) { return record.getValue('x') + record.getValeu('x'); },
        /** @param {Object} record a plain object */
        b: function(record) { return record.save(); },
        /**
         * @param {GlideDateTime} start
         * @param {GlideUser} [user] optional
         */
        c: function(start, user) { return user.getNmae(); },
        d: function() { var user = 5; return user.toFixed(2); },
        type: 'U'
    };"""
    assert wide(code) == ["GlideRecord.getValeu", "GlideUser.getNmae"]
    typed_var = "/** @type {GlideUser} */\nvar u = find();\nu.getNmae();"
    assert wide(typed_var) == ["GlideUser.getNmae"]


def test_a_declared_variable_is_never_taken_for_a_class_of_the_same_name():
    code = """
    var sb = []; sb.push('a');
    var logger = this.logger; logger.debug('x');
    var action = {}; action.go();
    var helpers = this._h(); helpers.doIt();
    var api = new x_acme.Api(); api.call();
    function Message() {} Message.send();
    let Event = require('events'); Event.emit('x');
    const { api: mine, gs } = tools; mine.emitt(); gs.nope();
    current = other; current.nope();
    """
    assert wide(code) == []
    # the same names, not declared: the platform's
    assert wide("action.go(); logger.debug('x'); Event.emit('x');") == [
        "action.go",
        "logger.debug",
        "Event.emit",
    ]
    assert wide("current.nope(); current = other;") == ["GlideRecord.nope"]


def test_a_ui_builder_script_gets_api_and_helpers_as_one_object():
    code = """
    function handler({api, event, helpers, imports}) {
        api.emit('NAV', {}); api.emitt('NAV', {}); api.setState('a', 1);
        helpers.snHttp('/api/now/table/incident').then(function(r) { api.setState('rows', r); });
        helpers.navigate.to('home'); helpers.navigate.too('home');
        event.preventDefault(); imports.x.y();
    }"""
    found = check(code, WIDE)
    assert [f.call for f in found] == ["api.emitt", "helpers.navigate.too"]
    assert found[0].suggestions == ["api.emit"] and found[1].suggestions == ["helpers.navigate.to"]
    arrow = "export default ({ api, helpers: h }) => { api.emitt('x'); h.snHttp('/x'); };"
    assert wide(arrow) == ["api.emitt"]


def test_a_plain_parameter_is_not_taken_for_a_class():
    code = "function log(logger, sb, api, action) { logger.debug(); sb.push(); api.get(); action.go(); }"
    assert wide(code) == []
    # ... but the platform's variables and the usual names are, as before
    rule = "(function executeRule(current, previous, gr) { current.nope(); gr.qurey(); })(current, previous);"
    assert wide(rule) == ["GlideRecord.nope", "GlideRecord.qurey"]


def test_a_type_that_is_not_the_docs_class_types_nothing():
    ts = (
        "export function onClick(event: Event, table: Table, n: number): void "
        "{ event.preventDefault(); table.addRow(); }"
    )
    assert wide(ts) == []  # the browser's Event; the docs' Table is in a namespace
    assert wide("import { Message } from './types';\nfunction f(m: Message) { m.send(); }") == []
    jsdoc = (
        "/** @typedef {Object} Message */\n/** @param {Message} m */\nfunction f(m) { m.send(); }"
    )
    assert wide(jsdoc) == []
    assert wide("/** @param {Event} e */\nfunction f(e) { e.stopPropagation(); }") == []
    # with its namespace, or without one in the docs, the docs' class is meant
    named = "function f(t: sn_pdfgeneratorutils.Table, m: Message) { t.addRow(); m.send(); }"
    assert wide(named) == ["Table.addRow", "Message.send"]
    assert wide("const t = new sn_pdfgeneratorutils.Table(); t.addRow();") == ["Table.addRow"]


def test_a_typescript_declaration_names_the_class():
    code = (
        "let r: GlideRecord = make(); r.qurey();\n"
        "const u: GlideUser | null = find(); u.getNmae();\n"
        "const o = { rec: GlideUser }; rec.anything();"
    )
    assert wide(code) == ["GlideRecord.qurey", "GlideUser.getNmae"]


def test_code_inside_a_template_literal_is_checked():
    code = (
        "var gr = new GlideRecord('incident');\n"
        "gs.getProperty(`Number ${gr.getValeu('number')} by ${gs.getPropertee('x')}`);\n"
    )
    assert [(f.call, f.line) for f in check(code, WIDE)] == [
        ("GlideRecord.getValeu", 2),
        ("GlideSystem.getPropertee", 2),
    ]
    # the text of a template is not code, however deep it is
    nested = "var t = `gs.nope() ${cond ? `gs.fooBar() ${gs.getProperty('x')}` : ''} gs.bar()`;"
    assert wide(nested) == []
    assert wide("var t = `a ${ {b: gs.nope()}.b } c`; gs.nope2();") == [
        "GlideSystem.nope",
        "GlideSystem.nope2",
    ]


def test_a_regex_literal_with_a_quote_does_not_hide_the_rest_of_the_line():
    assert wide('var re = /"/g; var gr = new GlideRecord("incident"); gr.qurey("a");') == [
        "GlideRecord.qurey"
    ]
    assert wide("var re = /'/; gs.getPropertee('x'); var s = 'it';") == ["GlideSystem.getPropertee"]
    assert wide("if (/[/'\"]/.test(s)) { gs.getPropertee('x'); }") == ["GlideSystem.getPropertee"]
    # a division is not a regex, and what a regex holds is not code
    assert wide("var half = total / 2; var s = 'a' / gs.getPropertee('x') / 2;") == [
        "GlideSystem.getPropertee"
    ]
    assert wide("var re = /gs.nope()/; var n = a / b; gs.getProperty('x') / 2;") == []


def test_a_chain_is_followed_through_nested_parentheses():
    assert typed("gs.getUser(gs.getProperty('a')).getNmae();") == ["GlideUser.getNmae"]
    assert typed("var u = gs.getUser(f(1, g(2)))\n    .getNmae();\nu.anything();") == [
        "GlideUser.getNmae"
    ]
    assert typed("new GlideRecord(name()).qurey(); new GlideRecord('x').query();") == [
        "GlideRecord.qurey"
    ]
    assert typed("global.GlideSystem.getUser().getNmae(); sn_x.GlideUser.nope();") == [
        "GlideUser.getNmae",
        "GlideUser.nope",
    ]


def test_methods_the_docs_have_for_the_client_side_class_pass():
    code = "var gr = new GlideRecord('sys_user'); gr.addOrderBy('name'); gr.addOrderBi('name');"
    assert wide(code) == ["GlideRecord.addOrderBi"]


def test_methods_every_object_has_are_not_reported():
    code = "var gr = new GlideRecord('x'); gr.toString(); gr.hasOwnProperty('a'); gr.valueOf(); gs.toString();"
    assert wide(code) == []


def test_arrow_functions_and_imports():
    arrows = (
        "const f = (rec: GlideRecord, n) => rec.qurey(); list.forEach(gr => gr.qurey2()); "
        "list.map(logger => logger.x());"
    )
    assert wide(arrows) == ["GlideRecord.qurey", "GlideRecord.qurey2"]
    glide = (
        "import { gs, GlideRecord } from '@servicenow/glide';\n"
        "gs.getPropertee('x'); new GlideRecord('x').qurey();"
    )
    assert wide(glide) == ["GlideSystem.getPropertee", "GlideRecord.qurey"]
    fluent = (
        "import { Table, Event as E } from '@servicenow/sdk/core';\nTable.nope(); Event.emit();"
    )
    assert wide(fluent) == ["Event.emit"]


def test_a_variable_given_a_value_made_from_itself_is_followed():
    code = (
        "var u = gs.getUser(); u.getNmae(); u = u.getName(); u.anything();\nvar n = n.toFixed(2);"
    )
    assert typed(code) == ["GlideUser.getNmae"]


def test_a_class_of_the_same_name_in_another_namespace_is_not_the_docs_class():
    code = (
        "var a = new SNC.Notify.Table(cfg); a.init();\n"
        "var b = new x_acme.Table(); b.init(); new x_acme.Table().init();\n"
        "function f(t: x_acme.Table) { t.init(); }\nx_acme.Table.init();"
    )
    assert wide(code) == []
    assert wide("sn_pdfgeneratorutils.Table.init(); new sn_pdfgeneratorutils.Table().init();") == [
        "Table.init"
    ]


def test_unfinished_code_is_read_without_failing():
    for code in (
        "x => ",
        "(a, b) =>",
        "function f(a",
        "gs.getUser(",
        "var t = `a ${gs.getPropertee(",
        "var s = 'open",
        "}}} ) ]",
        "/* open",
        "var a = 1,",
        "import { a } from",
        "function f({a: {b}}) { b.c(); }",
    ):
        assert isinstance(check(code, WIDE), list), code
    assert wide("gs.getPropertee('x'); (a) =>") == ["GlideSystem.getPropertee"]


def test_service_portal_services_are_handed_to_a_controller_by_name():
    sp = _page(
        "spUtil - Client", "Utility methods for widgets.", "spUtil - recordWatch\\(Object scope\\)"
    )
    table = ApiTable(TABLE_MEMBERS + parse_page("sp.md", sp))
    code = "api.controller = function($scope, spUtil, $http) { spUtil.recordWatch($scope); spUtil.recordWach($scope); $http.get('/x'); };"
    assert [f.call for f in check(code, table)] == ["spUtil.recordWach"]


def test_many_arrow_functions_in_a_row_are_fast():
    """A minified file is thousands of arrows; each one's body used to be scanned to the end
    of the file (90,000 characters took 34 seconds, past the hook's timeout)."""
    import time

    from snow_docs_mcp.script_check import review

    curried = "var gr = new GlideRecord('incident');\n" + "a=>" * 30000 + "gr.qurey()"
    started = time.monotonic()
    found = review(curried, TABLE)
    assert time.monotonic() - started < 2.0
    assert [f.call for f in found.findings] == ["GlideRecord.qurey"]
