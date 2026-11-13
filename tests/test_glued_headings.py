"""A heading written on the same line as a table's end (`</table>## Heading`) opens a section.

About 3,000 pages in each release have this. Without it, the text after the table hides under
the previous heading: it cannot be read by its own id and is missing from the page's sections.
"""

from __future__ import annotations

from snow_docs_mcp import sections

PAGE = (
    "# Release notes\n\nIntro.\n\n## Important information\n\nBefore you upgrade.\n\n"
    "<table><tbody><tr><td>\n\nBrazil\n\n</td><td>\n\nNo updates.\n\n</td></tr></tbody>\n"
    "</table>## New features\n\nNew things.\n\n<table><tbody><tr><td>x</td></tr></tbody>\n"
    "</table>### Details\n\nFine print.\n\n## Changes\n\nChanged things.\n\n"
    "<table><tbody><tr><td>y</td></tr></tbody>\n</table>**Parent Topic:** Home\n"
)


def test_a_glued_heading_is_a_section_that_can_be_read_by_its_own_heading():
    assert sections.headings(PAGE) == [
        "Release notes",
        "Release notes > Important information",
        "Release notes > New features",
        "Release notes > New features > Details",
        "Release notes > Changes",
    ]
    new = sections.extract_section(PAGE, "Release notes > New features")
    assert new.lstrip().startswith("New things.")
    assert (
        "Fine print." in new and "Changed things." not in new and "Before you upgrade." not in new
    )
    assert (
        sections.extract_section(PAGE, "Release notes > New features > Details").strip()
        == "Fine print."
    )


def test_an_id_from_the_index_still_returns_all_the_text_the_index_filed_under_it():
    # the index did not see the glued headings: it filed "New things." and "Fine print." under
    # "Important information", so that id must keep returning them, headings included
    important = sections.extract_section(PAGE, "Release notes > Important information")
    for text in (
        "Before you upgrade.",
        "## New features",
        "New things.",
        "### Details",
        "Fine print.",
    ):
        assert text in important, text
    assert "Changed things." not in important  # "Changes" is a heading the index saw


def test_text_glued_to_a_table_that_is_not_a_heading_is_left_alone():
    changes = sections.extract_section(PAGE, "Release notes > Changes")
    assert "</table>**Parent Topic:** Home" in changes


def test_a_repeated_heading_keeps_its_count_across_a_glued_section():
    page = "# P\n\n## Steps\n\nOne.\n\n<table></table>\n</table>## Notes\n\nNote.\n\n## Steps\n\nTwo.\n"
    assert sections.occurrence_of(page, "P > Steps", page.index("Note.")) == 1
    assert sections.occurrence_of(page, "P > Steps", page.index("Two.")) == 2


def test_offsets_still_count_the_page_as_written():
    offset = PAGE.index("Changed things.")
    walked = sections.split_into_sections(PAGE)
    changes = next(s for s in walked if s.heading_path[-1] == "Changes")
    assert (
        PAGE[changes.byte_offset :].lstrip().startswith("Changed things.")
        and changes.byte_offset <= offset
    )


def test_a_section_under_a_glued_heading_answers_to_the_index_breadcrumb_too():
    # the index nested "Detail" under "First" because it did not see the glued "Second"
    page = "# P\n\n## First\n\nOne.\n\n<table></table>\n</table>## Second\n\nTwo.\n\n### Detail\n\nThree.\n"
    assert sections.headings(page) == ["P", "P > First", "P > Second", "P > Second > Detail"]
    assert sections.extract_section(page, "P > First > Detail").strip() == "Three."
    assert sections.extract_section(page, "P > Second > Detail").strip() == "Three."
    first = sections.extract_section(page, "P > First")
    assert "One." in first and "Two." in first and "Three." in first
    assert sections.count_sections(page, "P > First > Detail") == 1


def test_a_deep_heading_glued_to_a_table_stays_text():
    page = "# P\n\n## A\n\n<table></table>\n</table>#### Small\n\nText.\n"
    assert sections.headings(page) == ["P", "P > A"]
    assert sections.extract_section(page, "P > A").count("</table>") == 2


def test_a_repeated_heading_is_numbered_as_the_index_numbers_it():
    # two "Example" sections the index saw, and a glued one in between that it did not
    page = (
        "# P\n\n## Example\n\nFirst.\n\n<table></table>\n</table>## Example\n\nGlued.\n\n"
        "## Other\n\nx\n\n## Example\n\nSecond.\n"
    )
    assert "First." in sections.extract_section(page, "P > Example", 1)
    assert sections.extract_section(page, "P > Example", 2).strip() == "Second."
    assert sections.count_sections(page, "P > Example") == 2
