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
    kind, found = t.find("getvalue")
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
