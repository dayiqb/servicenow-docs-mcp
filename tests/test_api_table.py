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
