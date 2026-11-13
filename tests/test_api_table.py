"""Parsing API reference pages into methods, and looking names up."""

from __future__ import annotations

from snow_docs_mcp.api_table import ApiTable, parse_page

PAGE = """---
title: GlideRecord - Scoped
---

# GlideRecord - Scoped

Scoped GlideRecord is used for database operations.

## Scoped GlideRecord - addEncodedQuery\\(String query\\)

Adds an encoded query to other queries that may have been set.

|Name|Type|Description|
|----|----|-----------|
|query|String|An [encoded query](https://x/y.md) string.|

|Type|Description|
|----|-----------|
|void| |

```
var now_GR = new GlideRecord('incident');
now_GR.addEncodedQuery('active=true');
```

Output:

```
ignored
```

## Scoped GlideRecord – getValue\\(String name\\)

Retrieves the string value of a field.

<table id="t1" class="parameters"><thead><tr><th>

Name

</th><th>

Type

</th><th>

Description

</th></tr></thead><tbody><tr><td>

name

</td><td>

String

</td><td>

Name of the field.

</td></tr></tbody>
</table><table id="t2" class="returns"><thead><tr><th>

Type

</th><th>

Description

</th></tr></thead><tbody><tr><td>

String

</td><td>

The value of the field.

</td></tr></tbody>
</table>

### Example

```
gs.info(now_GR.getValue('number'));
```

## Scoped GlideRecord - query\\(\\)

Runs the query.

## Scoped GlideRecord - isActionAborted

True when the action was aborted.

## Notes on performance

Not a method.
"""

GLOBAL = PAGE.replace("Scoped GlideRecord", "GlideRecord").replace("- Scoped", "- Global")
PATH = "markdown/api-reference/server-api-reference/c_GlideRecordScopedAPI.md"
GLOBAL_PATH = "markdown/api-reference/server-api-reference/c_GlideRecordAPI.md"


def test_parses_markdown_tables_description_returns_and_first_example():
    m = parse_page(PATH, PAGE)[0]
    assert (m.class_name, m.name, m.kind) == ("Scoped GlideRecord", "addEncodedQuery", "method")
    assert m.signature == "addEncodedQuery(String query)"
    assert [(p.name, p.type, p.description) for p in m.params] == [
        ("query", "String", "An encoded query string.")
    ]
    assert (m.returns, m.returns_description) == ("void", "")
    assert m.description == "Adds an encoded query to other queries that may have been set."
    assert "addEncodedQuery('active=true')" in m.example and "ignored" not in m.example


def test_parses_html_tables_dash_headings_and_an_example_under_a_subheading():
    m = parse_page(PATH, PAGE)[1]
    assert m.name == "getValue" and m.params[0].description == "Name of the field."
    assert (m.returns, m.returns_description) == ("String", "The value of the field.")
    assert "getValue('number')" in m.example


def test_methods_without_parameters_properties_and_non_methods():
    members = parse_page(PATH, PAGE)
    assert [(m.name, m.kind) for m in members] == [
        ("addEncodedQuery", "method"),
        ("getValue", "method"),
        ("query", "method"),
        ("isActionAborted", "property"),
    ]
    assert members[2].params == [] and members[2].signature == "query()"


def test_a_none_row_in_the_parameter_table_means_no_parameters():
    page = PAGE.replace(
        "Runs the query.",
        "Runs the query.\n\n|Name|Type|Description|\n|----|----|-----------|\n|None| | |\n",
    )
    assert parse_page(PATH, page)[2].params == []


def test_section_ids_are_the_headings_as_the_page_writes_them():
    m = parse_page(PATH, PAGE)[0]
    assert m.heading_path == (
        "GlideRecord - Scoped > Scoped GlideRecord - addEncodedQuery\\\\(String query\\\\)"
    ).replace("\\\\", "\\")
    assert m.occurrence == 1 and m.file_path == PATH


def _table() -> ApiTable:
    return ApiTable(parse_page(PATH, PAGE) + parse_page(GLOBAL_PATH, GLOBAL))


def test_class_lookup_keeps_global_and_scoped_apart_and_knows_variable_names():
    kind, classes = _table().find("glideRecord")
    assert kind == "class" and sorted(classes) == ["GlideRecord", "Scoped GlideRecord"]
    assert [m.name for m in classes["GlideRecord"]][:2] == ["addEncodedQuery", "getValue"]
    t = ApiTable(parse_page("p", PAGE.replace("Scoped GlideRecord", "GlideSystem")))
    assert t.find("gs")[0] == "class" and t.find("gs.query")[0] == "method"


def test_method_lookup_with_and_without_class():
    t = _table()
    kind, found = t.find("GlideRecord.addEncodedQuery()")
    assert kind == "method" and {m.class_name for m in found} == {
        "GlideRecord",
        "Scoped GlideRecord",
    }
    kind, found = t.find("Scoped GlideRecord.getValue")
    assert kind == "method" and [m.class_name for m in found] == ["Scoped GlideRecord"]
    kind, found = t.find("getValue")
    assert kind == "method" and len(found) == 2


def test_unknown_names_give_the_closest_ones():
    t = _table()
    assert t.find("GlideRecord.addEncodedQuerry") == ("not_found", ["GlideRecord.addEncodedQuery"])
    assert t.find("GlideRecrod") == ("not_found", ["GlideRecord"])
    assert t.find("zzzz") == ("not_found", [])
    # an unknown class is not answered with other classes' methods, only pointed at them
    assert t.find("$sp.getValue") == ("not_found", ["GlideRecord.getValue"])
    assert t.find("  ") == ("not_found", [])


def test_parameters_come_from_the_signature_when_the_docs_have_no_table():
    page = (
        "# GlideForm\n\n## GlideForm - clearChoices\\(String fieldName\\)\n\nRemoves all choices.\n\n"
        "## GlideForm - open\\(type: TokenType, token: String\\)\n\nOpens it.\n"
    )
    a, b = parse_page("p", page)
    assert [(p.name, p.type, p.description) for p in a.params] == [("fieldName", "String", "")]
    assert [(p.name, p.type) for p in b.params] == [("type", "TokenType"), ("token", "String")]


def test_variables_the_docs_name_resolve_to_their_classes():
    page = PAGE.replace("Scoped GlideRecord", "GlideSPScriptable")
    t = ApiTable(
        parse_page("p", page) + parse_page("q", PAGE.replace("Scoped GlideRecord", "GlideListV3"))
    )
    assert t.find("$sp.getValue")[0] == "method"
    assert sorted(t.find("g_list")[1]) == ["GlideListV3"]
    assert t.find("current.getValue")[0] == "not_found"  # GlideRecord is not in this table


REST = """# Table API

The Table API allows CRUD operations on tables.

## Table - POST /now/table/\\{tableName\\}

Inserts one record in the specified table.

### URL format

Versioned URL: `/api/now/{api_version}/table/{tableName}`

Default URL: `/api/now/table/{tableName}`

### Supported request parameters

<table class="rest_api_path_parameters"><thead><tr><th>

Name

</th><th>

Description

</th></tr></thead><tbody><tr><td>

tableName

</td><td>

Name of the table in which to save the record.Data type: String

</td></tr></tbody>
</table><table class="rest_api_query_parameters"><thead><tr><th>

Name

</th><th>

Description

</th></tr></thead><tbody><tr><td>

sysparm\\_fields

</td><td>

Comma-separated list of fields to return.Data type: String

</td></tr></tbody>
</table><table class="rest_api_request_body"><thead><tr><th>

Name

</th><th>

Description

</th></tr></thead><tbody><tr><td>

name-value pairs

</td><td>

Field name and the associated value for each field.

</td></tr></tbody>
</table>

### Status codes

|Status code|Description|
|-----------|-----------|
|201|Created.|

## Table - GET /now/table/\\{tableName\\}/\\{sys\\_id\\}

Retrieves the record identified by the specified sys_id.

### Supported request parameters

|Name|Description|
|----|-----------|
|sys\\_id|Sys_id of the record. Data type: String|

|Name|Description|
|----|-----------|
|None| |

|Name|Description|
|----|-----------|
|None| |
"""
REST_PATH = "markdown/api-reference/rest-apis/c_TableAPI.md"


def test_rest_endpoints_are_parsed_with_their_three_parameter_tables():
    from snow_docs_mcp.api_table import parse_rest_page

    post, get = parse_rest_page(REST_PATH, REST)
    assert (post.api, post.verb, post.path) == ("Table", "POST", "/now/table/{tableName}")
    assert post.default_url == "/api/now/table/{tableName}"
    assert post.description == "Inserts one record in the specified table."
    assert [(p.name, p.type) for p in post.path_params] == [("tableName", "String")]
    assert [(p.name, p.type) for p in post.query_params] == [("sysparm_fields", "String")]
    assert [p.name for p in post.body_params] == ["name-value pairs"]
    assert get.path == "/now/table/{tableName}/{sys_id}"
    assert [p.name for p in get.path_params] == ["sys_id"] and get.query_params == []
    assert parse_rest_page(PATH, PAGE) == []  # a scripting page has no endpoints


def test_rest_lookup_by_api_name_path_and_verb():
    from snow_docs_mcp.api_table import parse_rest_page

    t = ApiTable(parse_page(PATH, PAGE), parse_rest_page(REST_PATH, REST))
    kind, found = t.find("Table API")
    assert kind == "rest_api" and [e.verb for e in found["Table"]] == ["POST", "GET"]
    assert t.find("table")[0] == "rest_api"
    for q in (
        "POST /now/table/{tableName}",
        "post /api/now/table/incident",
        "POST /api/now/v2/table/incident",
    ):
        kind, found = t.find(q)
        assert kind == "endpoint" and [(e.verb, e.path) for e in found] == [
            ("POST", "/now/table/{tableName}")
        ], q
    kind, found = t.find("/now/table")  # a path prefix lists what is under it
    assert kind == "endpoint" and len(found) == 2
    assert t.find("GET /api/now/table/incident/abc123")[1][0].path.endswith("{sys_id}")
    assert t.find("DELETE /now/table/incident") == ("not_found", ["POST /now/table/{tableName}"])
    assert t.find("/now/nothing/here") == ("not_found", [])


def test_rest_tables_without_a_telling_class_count_by_position_and_urls_without_a_label():
    from snow_docs_mcp.api_table import parse_rest_page

    page = (
        "# Change API\n\n## Change - GET /sn\\_chg/change/\\{sys\\_id\\}\n\nGets it.\n\n"
        "### URL format\n\nVersioned URL: `/api/sn_chg/{api_version}/change/{sys_id}`\n\n"
        "`api/sn_chg/change/{sys_id}`\n\n### Supported request parameters\n\n"
        '<table class="rest_api_request_parameters"><thead><tr><th>Name</th><th>Description</th>'
        "</tr></thead><tbody><tr><td>sys\\_id</td><td>The record.Data type: String</td></tr></tbody>\n"
        "</table>|Parameter|Description|\n|----|-----------|\n|sysparm\\_x|A flag. Data type: Boolean|\n\n"
        "|Name|Description|\n|----|-----------|\n|None| |\n"
    )
    (e,) = parse_rest_page("p", page)
    assert [p.name for p in e.path_params] == ["sys_id"]
    assert [(p.name, p.type) for p in e.query_params] == [("sysparm_x", "Boolean")]
    assert e.body_params == [] and e.default_url == "/api/sn_chg/change/{sys_id}"


def test_default_url_is_derived_when_the_docs_only_give_other_forms():
    from snow_docs_mcp.api_table import parse_rest_page

    def url(heading_path: str, url_block: str) -> str:
        page = f"# X API\n\n## X - GET {heading_path}\n\nGets.\n\n### URL format\n\n{url_block}\n"
        return parse_rest_page("p", page)[0].default_url

    # only a versioned URL: the version part is taken out
    assert (
        url("/now/clotho/put", "Versioned URL: `/api/now/{api_version}/clotho/put`")
        == "/api/now/clotho/put"
    )
    # nothing usable in the block, but the heading's path has its namespace
    assert url("/now/batch", "See the note.") == "/api/now/batch"
    assert url("/sn\\_uxa/data\\_export", "") == "/api/sn_uxa/data_export"
    assert url("/api/sn\\_csm/\\{api\\_version\\}/price", "") == "/api/sn_csm/price"
    # a path without a namespace cannot be completed
    assert url("/agents/list", "See the note.") == ""


# --- names as scripts write them ------------------------------------------------------------


def _page(title: str, intro: str, *headings: str) -> str:
    """A small API page: a title, an intro and one documented member per heading."""
    parts = [f"# {title}\n\n{intro}\n"]
    parts += [f"## {h}\n\nDoes it.\n" for h in headings]
    return "\n".join(parts)


REST_MESSAGE = _page(
    "RESTMessageV2 - Scoped, Global",
    "The RESTMessageV2 API sends outbound REST messages. It is in the `sn_ws` namespace.",
    "RESTMessageV2 - execute\\(\\)",
    "RESTMessageV2 - setEndpoint\\(String endpoint\\)",
)
FLOW_API = _page(
    "FlowAPI - Scoped, Global",
    "Use these methods in the sn\\_fd namespace to run flows.",
    "FlowAPI - getRunner\\(\\)",
)
UIB_API = _page(
    "api - UI Builder",
    "The api object is passed to client scripts.",
    "api - api.emit\\(String eventName, Object payload\\)",
    "api - setState\\(String stateParam, Any value\\)",
)
UIB_HELPERS = _page(
    "helpers - UI Builder",
    "The helpers object is passed to client scripts.",
    "helpers - helpers.navigate.to\\(String route\\)",
    "helpers - helpers.snHttp\\(String url, Object options\\)",
)
ML = _page(
    "MLPredictor - Global",
    "Predicts with a solution.",
    "MLPredictor - solution.predict\\(Object input\\)",
    "MLPredictor - findActiveSolution\\(String name\\)",
)
ERP = _page(
    "sn\\_erp\\_integration API - Scoped, Global",
    "Reads data from an ERP system.",
    "API - execute\\(\\)",
    "API - limit\\(Number n\\)",
)


def _scripts_table() -> ApiTable:
    pages = (PAGE, GLOBAL, REST_MESSAGE, FLOW_API, UIB_API, UIB_HELPERS, ML, ERP)
    return ApiTable([m for i, p in enumerate(pages) for m in parse_page(f"p{i}.md", p)])


def test_a_namespace_before_a_class_is_ignored():
    t = _scripts_table()
    kind, found = t.find("sn_ws.RESTMessageV2")
    assert kind == "class" and list(found) == ["RESTMessageV2"]
    kind, found = t.find("sn_ws.RESTMessageV2.execute()")
    assert kind == "method" and [m.name for m in found] == ["execute"]
    kind, found = t.find("sn_fd.FlowAPI.getRunner")
    assert kind == "method" and [m.class_name for m in found] == ["FlowAPI"]
    assert t.find("global.GlideRecord")[0] == "class"
    assert t.find("global.GlideRecord.getValue")[0] == "method"
    # a customer's own scope is not ServiceNow's namespace
    assert t.find("x_acme.GlideRecord.getValue")[0] == "not_found"


def test_the_namespace_a_page_names_is_kept():
    t = _scripts_table()
    assert parse_page("p.md", REST_MESSAGE)[0].namespace == "sn_ws"
    assert t.namespace("RESTMessageV2") == "sn_ws" and t.namespace("FlowAPI") == "sn_fd"
    assert t.namespace("GlideRecord") == "" and t.namespace("Nothing") == ""


def test_members_the_docs_name_with_a_dot_are_found():
    t = _scripts_table()
    for q, cls, name in (
        ("api.emit", "api", "api.emit"),
        ("api.emit('X', {})", "api", "api.emit"),
        ("helpers.snHttp", "helpers", "helpers.snHttp"),
        ("helpers.navigate.to", "helpers", "helpers.navigate.to"),
        ("MLPredictor.solution.predict", "MLPredictor", "solution.predict"),
        ("emit", "api", "api.emit"),
        ("solution.predict", "MLPredictor", "solution.predict"),
        ("navigate.to", "helpers", "helpers.navigate.to"),
    ):
        kind, found = t.find(q)
        assert kind == "method" and [(m.class_name, m.name) for m in found] == [(cls, name)], q
    # the closest names are written as a script calls them
    assert t.find("api.emitt") == ("not_found", ["api.emit"])
    assert t.find("helpers.snHtp") == ("not_found", ["helpers.snHttp"])
    assert t.member("api", "emit") == ("api", True, [])
    assert t.member("helpers", "navigate.to") == ("helpers", True, [])
    assert t.member("helpers", "snHtp") == ("helpers", False, ["helpers.snHttp"])
    assert t.member_names("helpers") == {"navigate.to", "snHttp"}


def test_classes_that_differ_only_in_case_are_kept_apart():
    t = _scripts_table()
    assert list(t.find("api")[1]) == ["api"] and list(t.find("API")[1]) == ["API"]
    assert sorted(t.find("Api")[1]) == ["API", "api"]  # neither spelling: both are offered
    assert t.member("api", "execute") == ("api", False, [])
    assert t.member("API", "execute") == ("API", True, [])
    assert t.find("api.limit")[0] == "not_found" and t.find("API.limit")[0] == "method"


def test_method_names_are_matched_with_their_exact_case():
    t = _table()
    assert t.find("GlideRecord.getvalue") == ("not_found", ["GlideRecord.getValue"])
    assert t.find("getvalue") == ("not_found", ["getValue"])
    assert t.find("gliderecord.getValue")[0] == "method"  # the class is found in any case


def test_a_variant_named_exactly_is_answered_alone():
    form = PAGE.replace("Scoped GlideRecord", "GlideForm")
    t = ApiTable(
        parse_page("a.md", form)
        + parse_page("b.md", form.replace("GlideForm - ", "GlideForm \\(Next Experience\\) - "))
    )
    assert sorted(t.find("GlideForm")[1]) == ["GlideForm", "GlideForm (Next Experience)"]
    assert list(t.find("GlideForm (Next Experience)")[1]) == ["GlideForm (Next Experience)"]
    kind, found = t.find("GlideForm (Next Experience).addEncodedQuery")
    assert kind == "method" and [m.class_name for m in found] == ["GlideForm (Next Experience)"]
    assert len(t.find("g_form.getValue('x')")[1]) == 2


def test_suggestions_are_not_repeated():
    page = PAGE.replace(
        "Scoped GlideRecord - query\\(\\)", "Scoped GlideRecord - GlideRecord\\(\\)"
    )
    t = ApiTable(parse_page(PATH, page.replace("Scoped GlideRecord", "GlideRecord")))
    assert t.find("GlideRecod") == ("not_found", ["GlideRecord"])
    # an unknown class is pointed at the classes that really have the method
    other = PAGE.replace("Scoped GlideRecord", "GlideElement").replace("getValue", "GetValue")
    t = ApiTable(parse_page(PATH, PAGE) + parse_page("e.md", other))
    assert t.find("Nope.getValue") == ("not_found", ["GlideRecord.getValue"])


CLIENT = _page(
    "GlideRecord - Client",
    "Client side GlideRecord queries from a client script.",
    "Client side GlideRecord - addOrderBy\\(String column\\)",
    "Client side GlideRecord - query\\(Function responseFunction\\)",
)


def test_client_side_methods_count_for_the_class():
    t = ApiTable(parse_page(GLOBAL_PATH, GLOBAL) + parse_page("c.md", CLIENT))
    assert t.member("GlideRecord", "addOrderBy") == ("GlideRecord", True, [])
    kind, found = t.find("GlideRecord.addOrderBy")
    assert kind == "method" and [m.class_name for m in found] == ["Client side GlideRecord"]
    assert list(t.find("GlideRecord")[1]) == ["GlideRecord"]  # the class itself is listed alone
    assert t.find("GlideRecord.query")[1][0].class_name == "GlideRecord"


# --- REST paths as people paste them ---------------------------------------------------------

ATTACHMENT = (
    "# Attachment API\n\n## Attachment - POST /now/attachment/file\n\nUploads a file.\n\n"
    "## Attachment - GET /now/attachment/\\{sys\\_id\\}\n\nReturns the metadata.\n"
)
REASSIGN = (
    "# Reassign Assessment API\n\n## Reassign Assessment - PATCH /\\{userId\\}\n\nReassigns it.\n\n"
    "### URL format\n\nDefault URL: `PATCH /api/sn_smart_asmt/instance/asmt/{asmtInstanceId}/user/{userId}`\n"
)


def _rest_table() -> ApiTable:
    from snow_docs_mcp.api_table import parse_rest_page

    pages = (REST, ATTACHMENT, REASSIGN)
    return ApiTable([], [e for i, p in enumerate(pages) for e in parse_rest_page(f"r{i}.md", p)])


def test_rest_lookup_takes_a_query_string_and_a_whole_url():
    t = _rest_table()
    for q, verb, path in (
        (
            "POST /api/now/attachment/file?table_name=incident&table_sys_id=abc&file_name=x.txt",
            "POST",
            "/now/attachment/file",
        ),
        ("/api/now/attachment/file#upload", "POST", "/now/attachment/file"),
        (
            "POST https://dev12345.service-now.com/api/now/table/incident",
            "POST",
            "/now/table/{tableName}",
        ),
        (
            "https://dev12345.service-now.com/api/now/table/incident?sysparm_limit=1",
            "POST",
            "/now/table/{tableName}",
        ),
        (
            "dev12345.service-now.com/api/now/table/incident/abc",
            "GET",
            "/now/table/{tableName}/{sys_id}",
        ),
        (
            "GET http://localhost:8080/api/now/v2/table/incident/abc?x=1",
            "GET",
            "/now/table/{tableName}/{sys_id}",
        ),
    ):
        kind, found = t.find(q)
        assert kind == "endpoint" and [(e.verb, e.path) for e in found] == [(verb, path)], q


def test_a_path_of_placeholders_only_never_answers_a_short_query():
    t = _rest_table()
    assert t.find("/table") == ("not_found", [])
    kind, found = t.find("/api/now")  # the start of a path: what is under it
    assert kind == "endpoint" and {e.api for e in found} == {"Table", "Attachment"}
    # its real path is in its default URL: found by that
    kind, found = t.find("PATCH /api/sn_smart_asmt/instance/asmt/abc/user/def")
    assert kind == "endpoint" and [e.api for e in found] == ["Reassign Assessment"]


def test_default_url_drops_a_verb_and_gets_its_api_start():
    from snow_docs_mcp.api_table import parse_rest_page

    assert parse_rest_page("r.md", REASSIGN)[0].default_url == (
        "/api/sn_smart_asmt/instance/asmt/{asmtInstanceId}/user/{userId}"
    )

    def url(url_block: str) -> str:
        page = f"# X API\n\n## X - POST /x/y\n\nDoes.\n\n### URL format\n\n{url_block}\n"
        return parse_rest_page("p", page)[0].default_url

    assert (
        url("Default URL: `POST api/sn_wsd_rsv/v2/reservable/list`")
        == "/api/sn_wsd_rsv/v2/reservable/list"
    )
    assert url("Default URL: `/now/agent_intelligence/solution/prediction`") == (
        "/api/now/agent_intelligence/solution/prediction"
    )
    assert url("Default URL: `/sn_tmf_api/catalog/{id}`") == "/api/sn_tmf_api/catalog/{id}"
    assert url("Default URL: `/api/sn_sc/ servicecatalog/items/{sys_id}`") == (
        "/api/sn_sc/servicecatalog/items/{sys_id}"
    )


def test_a_chain_of_calls_is_followed_by_what_each_returns():
    getters = (
        "# GlideSystem\n\n## GlideSystem - getUser\\(\\)\n\nReturns the user.\n\n"
        "|Type|Description|\n|----|-----------|\n|GlideUser|The current user.|\n\n"
        "## GlideSystem - getProperty\\(String key\\)\n\nReturns a property.\n\n"
        "|Type|Description|\n|----|-----------|\n|String|The value.|\n"
    )
    user = PAGE.replace("Scoped GlideRecord", "GlideUser").replace("getValue", "getName")
    t = ApiTable(parse_page("g.md", getters) + parse_page("u.md", user))
    kind, found = t.find("gs.getUser().getName()")
    assert kind == "method" and [(m.class_name, m.name) for m in found] == [
        ("GlideUser", "getName")
    ]
    assert t.find("gs.getUser().getNmae") == ("not_found", ["GlideUser.getName"])
    assert t.find("new GlideUser(id).getName()")[0] == "method"  # a new object: its class
    # a method that returns no documented class cannot be followed
    assert t.find("gs.getProperty('x').getName")[0] == "not_found"


def test_a_variant_written_in_square_brackets_is_a_variant_too():
    """The docs write one class as `GlideNavigation [Next Experience]`."""
    nav = PAGE.replace("Scoped GlideRecord", "GlideNavigation")
    bracketed = nav.replace("GlideNavigation - ", "GlideNavigation \\[Next Experience\\] - ")
    t = ApiTable(parse_page("a.md", nav) + parse_page("b.md", bracketed))
    assert sorted(t.find("GlideNavigation")[1]) == [
        "GlideNavigation",
        "GlideNavigation [Next Experience]",
    ]
    assert list(t.find("GlideNavigation [Next Experience]")[1]) == [
        "GlideNavigation [Next Experience]"
    ]
    kind, found = t.find("GlideNavigation.addEncodedQuery")
    assert kind == "method" and len(found) == 2
