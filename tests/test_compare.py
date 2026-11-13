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


def test_small_rewording_is_listed_as_small_with_the_words_that_differ():
    d = compare_pages(BASE, BASE.replace("admin role", "administrator role"))
    (s,) = d.sections
    assert s.small and s.change == "changed" and d.minor == 1
    assert "admin role" in s.before and "administrator role" in s.after


def test_a_changed_number_or_a_not_is_never_hidden():
    """One word can change what an administrator must do when upgrading."""
    kept = BASE.replace("Open the form.", "Closed records are kept for 30 days.")
    d = compare_pages(kept, kept.replace("30 days", "90 days"))
    (s,) = d.sections
    assert s.small and "30 days" in s.before and "90 days" in s.after
    d = compare_pages(kept, kept.replace("are kept", "are not kept"))
    (s,) = d.sections
    assert s.small and "are kept" in s.before and "are not kept" in s.after


def test_a_long_rewording_is_not_small():
    b = BASE.replace(
        "Install the plugin and assign the admin role.",
        "Request the store application, wait for approval, then assign the new delegated "
        "developer role.",
    )
    d = compare_pages(BASE, b)
    assert [s.small for s in d.sections] == [False] and d.minor == 0


def test_an_unresolved_link_placeholder_is_no_change():
    """One release renders a link as `[bundle-area.topic]` where the other has its text."""
    a = BASE.replace("Open the form.", "Use the [SC Shopping Cart widget](https://x/y.md) here.")
    b = BASE.replace("Open the form.", "Use the [bundle-platux.sc-shopping-cart] here.")
    assert compare_pages(a, b) == PageDiff([], 0)
    assert compare_pages(b, a) == PageDiff([], 0)


def test_a_trademark_sign_is_no_change():
    a = BASE.replace("Open the form.", "Runs on the ServiceNow AI Platform\u00ae.")
    b = BASE.replace("Open the form.", "Runs on the ServiceNow AI Platform.")
    assert compare_pages(a, b) == PageDiff([], 0)


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
    (s,) = d.sections
    assert s.small and s.changed_words == 1 and d.minor == 1
    assert "different" in s.after and "different" not in s.before


def test_inserted_repeated_heading_is_reported_as_added():
    old = "# P\n\n## Procedure\n\nFirst steps here.\n\n## Procedure\n\nSecond steps here.\n"
    new = old.replace(
        "## Procedure\n\nFirst steps here.",
        "## Procedure\n\nA brand new procedure with more than eight words in it.\n\n"
        "## Procedure\n\nFirst steps here.",
    )
    d = compare_pages(old, new)
    assert [(s.change, s.occurrence) for s in d.sections] == [("added", 1)] and d.minor == 0


def test_changed_repeated_heading_keeps_each_releases_occurrence():
    old = "# P\n\n## Procedure\n\nFirst steps here.\n\n## Procedure\n\nSecond steps here.\n"
    new = (
        "# P\n\n## Procedure\n\nAn inserted procedure with more than eight words in it now.\n\n"
        "## Procedure\n\nFirst steps here.\n\n"
        "## Procedure\n\nSecond steps were rewritten completely with many new and different words.\n"
    )
    d = compare_pages(old, new)
    changed = next(s for s in d.sections if s.change == "changed")
    assert (changed.old_occurrence, changed.occurrence) == (2, 3)


def test_excerpt_shows_the_largest_change_not_the_first_small_one():
    filler = " ".join(f"same{i}" for i in range(80))
    a = f"# P\n\n## S\n\nSee  for details. {filler} The old ending."
    b = (
        f"# P\n\n## S\n\nSee the guide for details. {filler} A completely rewritten closing "
        "paragraph with many more words than before."
    )
    (s,) = compare_pages(a, b, excerpt_chars=120).sections
    assert "old ending" in s.before and "rewritten closing" in s.after
