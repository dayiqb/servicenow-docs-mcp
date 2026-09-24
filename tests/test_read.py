"""Reading a section (or a whole page) back by id."""

from __future__ import annotations

from snow_docs_mcp.read import read_section as _read_section
from snow_docs_mcp.search import parse_id


def read_section(db, doc_id: str, max_chars: int = 20000):
    """Test helper: parse an id the way the read tool does, then read it."""
    parsed = parse_id(doc_id)
    if parsed is None:
        from snow_docs_mcp.read import not_an_id

        return not_an_id(doc_id)
    release, file_path, heading, occurrence = parsed
    return _read_section(db, release or "australia", file_path, heading, occurrence, max_chars)


def test_section_includes_its_subsections(fixture_db) -> None:
    r = read_section(fixture_db, "markdown/itsm/incident.md::Incident management > States")
    assert r.ok, r.message
    assert "New, In Progress, Resolved and Closed" in r.content
    assert "close automatically after 7 days" in r.content  # the ### subsection
    assert "Priority is calculated" not in r.content  # the next ## sibling
    assert r.title == "Incident management"
    assert r.id == "australia:markdown/itsm/incident.md::Incident management > States"
    assert not r.truncated


def test_empty_heading_returns_the_page_without_front_matter(fixture_db) -> None:
    r = read_section(fixture_db, "markdown/hr/case.md::")
    assert r.ok
    assert r.content.startswith("# HR case")
    assert "title:" not in r.content
    assert "Close the case" in r.content


def test_truncation(fixture_db) -> None:
    r = read_section(fixture_db, "markdown/itsm/incident.md::", max_chars=500)
    assert r.ok  # 500 is the floor; the fixture page is shorter, so nothing is cut
    assert not r.truncated


def test_truncation_marks_long_output(fixture_db) -> None:
    import sqlite3

    db = fixture_db
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO documents VALUES (?, ?)",
        ("markdown/itsm/long.md", "# Long\n\n" + "word " * 2000),
    )
    conn.commit()
    conn.close()
    r = read_section(db, "markdown/itsm/long.md::", max_chars=800)
    assert r.ok and r.truncated
    assert r.content.endswith("raise max_chars to see more]")
    assert len(r.content) < 900


def test_malformed_id_explains_what_an_id_looks_like(fixture_db) -> None:
    r = read_section(fixture_db, "incident states")
    assert not r.ok
    assert "not a docs id" in r.message and "::" in r.message


def test_unknown_page(fixture_db) -> None:
    r = read_section(fixture_db, "markdown/itsm/nope.md::Anything")
    assert not r.ok
    assert "No page 'markdown/itsm/nope.md'" in r.message


def test_unknown_heading_lists_the_real_ones(fixture_db) -> None:
    r = read_section(fixture_db, "markdown/itsm/incident.md::Incident management > Nope")
    assert not r.ok
    assert "Incident management > States" in r.message
    assert "Incident management > Priority" in r.message
    assert "australia:markdown/itsm/incident.md::" in r.message


REPEATED = """# Troubleshooting

## Impacted service missing

### Remedy

Restart the discovery schedule.

### Remedy

Re-run service mapping.

### Remedy

Clear the cache.
"""


def test_repeated_headings_get_distinct_ids(fixture_db) -> None:
    import sqlite3

    from snow_docs_mcp.sections import occurrence_of

    conn = sqlite3.connect(fixture_db)
    conn.execute("INSERT INTO documents VALUES (?, ?)", ("markdown/itom/ts.md", REPEATED))
    conn.commit()
    conn.close()
    path = "Troubleshooting > Impacted service missing > Remedy"
    offset_of_second = REPEATED.index("Re-run")
    assert occurrence_of(REPEATED, path, offset_of_second) == 2
    assert occurrence_of(REPEATED, path, REPEATED.index("Restart")) == 1

    first = read_section(fixture_db, f"markdown/itom/ts.md::{path}")
    second = read_section(fixture_db, f"markdown/itom/ts.md::{path}::2")
    third = read_section(fixture_db, f"markdown/itom/ts.md::{path}::3")
    assert "Restart the discovery" in first.content and first.id.endswith("Remedy")
    assert "Re-run service mapping" in second.content and second.id.endswith("::2")
    assert "Clear the cache" in third.content
    fourth = read_section(fixture_db, f"markdown/itom/ts.md::{path}::4")
    assert (
        not fourth.ok
        and "has 3 sections named" in fourth.message
        and "::1 to ::3" in fourth.message
    )


def test_exact_breadcrumb_beats_suffix_match(fixture_db) -> None:
    import sqlite3

    # "Guide > Remedy" ends with "Remedy" and comes first; the id names the H1 "Remedy".
    text = "# Guide\n\n## Remedy\n\nwrong\n\n# Remedy\n\nright\n"
    conn = sqlite3.connect(fixture_db)
    conn.execute("INSERT INTO documents VALUES (?, ?)", ("markdown/x/y.md", text))
    conn.commit()
    conn.close()
    r = read_section(fixture_db, "markdown/x/y.md::Remedy")
    assert r.ok and "right" in r.content and "wrong" not in r.content
