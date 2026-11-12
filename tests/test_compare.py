"""Comparing two versions of one page: only real text changes count."""

from __future__ import annotations

import time

from snow_docs_mcp.compare import PageDiff, compare_pages

BASE = (
    "---\ntitle: T\nrelease: australia\ncanonical_url: https://x/r/australia/t.html\n---\n\n"
    "# T\n\nIntro.\n\n## Setup\n\nInstall the plugin and assign the admin role.\n\n"
    "## Use\n\nOpen the form.\n"
)


def test_front_matter_only_difference_is_no_change():
    other = BASE.replace("release: australia", "release: brazil").replace("/australia/", "/")
    assert compare_pages(BASE, other) == PageDiff([], 0)


def test_link_table_id_and_whitespace_differences_are_no_change():
    a = BASE.replace("Open the form.", 'See  for details.\n<th id="d1e61" headers="d1e60">X</th>')
    b = BASE.replace(
        "Open the form.",
        "See [the guide](https://raw.githubusercontent.com/a/b.md) for details.\n"
        '<th id="d9e99"  headers="d9e98">X</th>',
    )
    assert compare_pages(a, b) == PageDiff([], 0)


def test_added_and_removed_sections():
    b = BASE.replace(
        "## Use\n\nOpen the form.\n", "## Roles\n\nThe new approver role is required here.\n"
    )
    d = compare_pages(BASE, b)
    assert [(s.heading_path, s.change) for s in d.sections] == [
        ("T > Roles", "added"),
        ("T > Use", "removed"),
    ]
    assert d.sections[0].before == "" and "approver role" in d.sections[0].after
    assert d.sections[1].after == "" and "Open the form" in d.sections[1].before


def test_reworded_section_above_threshold_is_listed_with_excerpts():
    b = BASE.replace(
        "Install the plugin and assign the admin role.",
        "Request the store application, wait for approval, then assign the new delegated "
        "developer role.",
    )
    (s,) = compare_pages(BASE, b).sections
    assert s.change == "changed" and s.changed_words >= 8
    assert "Install the plugin" in s.before and "store application" in s.after


def test_small_rewording_is_counted_as_minor():
    d = compare_pages(BASE, BASE.replace("admin role", "administrator role"))
    assert d.sections == [] and d.minor == 1


def test_repeated_headings_are_matched_by_occurrence():
    page = "# P\n\n## Procedure\n\nFirst steps here.\n\n## Procedure\n\nSecond steps here.\n"
    b = page.replace(
        "Second steps here.",
        "Completely different instructions for the second procedure, nine words long.",
    )
    (s,) = compare_pages(page, b).sections
    assert (s.heading_path, s.occurrence) == ("P > Procedure", 2)


def test_page_without_headings_is_one_section():
    (s,) = compare_pages(
        "Old text about one thing only.",
        "A fully rewritten body with many new words in this page now.",
    ).sections
    assert s.heading_path == "" and s.change == "changed"


def test_windows_line_endings_do_not_count_as_changes():
    assert compare_pages(BASE, BASE.replace("\n", "\r\n")) == PageDiff([], 0)


def test_large_section_is_fast():
    a = "# P\n\n## Big\n\n" + "\n".join(f"line {i} of the reference text" for i in range(20000))
    b = a.replace("line 777 of", "line 777 was rewritten with quite a few more words of")
    t = time.monotonic()
    d = compare_pages(a, b)
    assert time.monotonic() - t < 1.0
    assert len(d.sections) + d.minor == 1


def test_excerpt_starts_near_the_first_difference_and_is_cut():
    long = " ".join(f"word{i}" for i in range(200))
    a = f"# P\n\n## S\n\n{long} old ending here.\n"
    b = f"# P\n\n## S\n\n{long} a new and much longer ending with several more words here.\n"
    (s,) = compare_pages(a, b, excerpt_chars=120).sections
    assert s.after.startswith("…") and "new and much longer" in s.after
    assert len(s.before) <= 122 and len(s.after) <= 122


def test_link_in_one_release_and_plain_text_in_the_other_is_no_change():
    words = "Parent topic for integrating the two applications across every product area"
    a = BASE.replace("Open the form.", f"See [{words}](https://x/a.md).")
    b = BASE.replace("Open the form.", f"See {words}.")
    assert compare_pages(a, b) == PageDiff([], 0)


def test_repetitive_lines_with_scattered_changes_are_fast():
    def obj(i: int, changed: bool) -> str:
        kind = "integer" if changed else "string"
        return f'{{\n  "name": "field",\n  "type": "{kind}",\n  "required": true\n}},'

    a = "# P\n\n## Schema\n\n" + "\n".join(obj(i, False) for i in range(1500))
    b = "# P\n\n## Schema\n\n" + "\n".join(obj(i, i % 5 == 0) for i in range(1500))
    t = time.monotonic()
    (s,) = compare_pages(a, b).sections
    assert time.monotonic() - t < 1.0
    assert s.changed_words == 300


def test_big_table_with_scattered_changes_is_fast():
    a = "# P\n\n## T\n\n" + " ".join(f"| cell{i % 40} " for i in range(2400))
    b = "# P\n\n## T\n\n" + " ".join(
        f"| {'new' if i % 7 == 0 else 'cell'}{i % 40} " for i in range(2400)
    )
    t = time.monotonic()
    (s,) = compare_pages(a, b).sections
    assert time.monotonic() - t < 1.0 and s.changed_words >= 300


def test_one_changed_word_in_a_huge_single_line_counts_as_one():
    words = [f"w{i % 50}" for i in range(8000)]
    a = "# P\n\n## S\n\n" + " ".join(words)
    words[4000] = "different"
    d = compare_pages(a, "# P\n\n## S\n\n" + " ".join(words))
    assert d.sections == [] and d.minor == 1
