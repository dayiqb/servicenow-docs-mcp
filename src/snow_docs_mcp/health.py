"""Index health check: does a (new) docs index still hold what the tools read out of it?

The tools parse the docs as ServiceNow writes them today: API reference headings and tables,
REST endpoint sections, the release notes' titles and breadcrumbs. If a docs update changes
that layout, the tools would quietly find less. This counts what they find in an index and
compares it with floors set well below today's numbers, so a drop is noticed before an index
is published. Run it with `snow-docs-mcp check-index --australia PATH --brazil PATH`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from snow_docs_mcp import notes, store, tables
from snow_docs_mcp.compare import compare_pages

# Floors, about 80 % of the 2026-11-06 indexes (4,560 methods in 520 classes, 94 % with a
# return type, 2,966 with described parameters, 3,848 with a code example; 681 REST endpoints
# in 136 APIs, 99 % with parameters, all with a default URL; 10,533 table and field names in
# brackets; every page with a title; 315 release-notes applications in 30 families).
FLOORS: dict[str, float] = {
    "api_methods": 3600,
    "api_classes": 400,
    "api_methods_with_return_type": 0.80,
    "api_methods_with_parameters": 2350,
    "api_methods_with_example": 3050,
    "rest_endpoints": 540,
    "rest_apis": 100,
    "rest_endpoints_with_parameters": 0.85,
    "rest_endpoints_with_default_url": 0.95,
    "table_names": 8000,
    "pages_with_title": 0.95,
    "release_notes_applications": 250,
    "release_notes_families": 20,
}
# Share of pages present in both releases that the comparison lists as changed. 0.04 % on the
# 2026-11-06 indexes; a jump means a rendering difference is being read as a change.
MAX_COMPARE_NOISE = 0.05
COMPARE_SAMPLE = 200


def counts(db: str | Path, release: str) -> dict[str, float]:
    """What the tools find in one index."""
    from snow_docs_mcp import server  # the tools' own readers; imported late (server imports us)

    table = server._api_table(db)
    methods = [m for found in table.by_method.values() for m in found if m.kind == "method"]
    endpoints = table.endpoints

    def share(part: int, whole: int) -> float:
        return round(part / whole, 3) if whole else 0.0

    out: dict[str, float] = {
        "api_methods": len(methods),
        "api_classes": len(table.by_class),
        "api_methods_with_return_type": share(sum(bool(m.returns) for m in methods), len(methods)),
        "api_methods_with_parameters": sum(any(p.description for p in m.params) for m in methods),
        "api_methods_with_example": sum(bool(m.example) for m in methods),
        "rest_endpoints": len(endpoints),
        "rest_apis": len(table.by_api),
        "rest_endpoints_with_parameters": share(
            sum(bool(e.path_params or e.query_params or e.body_params) for e in endpoints),
            len(endpoints),
        ),
        "rest_endpoints_with_default_url": share(
            sum(bool(e.default_url) for e in endpoints), len(endpoints)
        ),
    }
    out["table_names"] = len(tables.scan(db))
    titles = store.titles_by_path(db)
    out["pages_with_title"] = share(sum(bool(t) for t in titles.values()), len(titles))
    if release == notes.RELEASE:
        apps, families, _ = notes.index(db)
        out["release_notes_applications"] = len(apps)
        out["release_notes_families"] = len(families)
    return out


def problems(found: dict[str, float], floors: dict[str, float] | None = None) -> list[str]:
    """One line per count that is below its floor."""
    floors = FLOORS if floors is None else floors
    return [
        f"{key}: {found[key]:g} is below the floor of {floors[key]:g}"
        for key in found
        if key in floors and found[key] < floors[key]
    ]


def compare_noise(australia_db: str | Path, brazil_db: str | Path) -> tuple[float, int]:
    """(share of sampled pages with a change larger than a small rewording, pages sampled),
    over pages that both releases have."""
    shared = sorted(
        p
        for p in store.page_paths(australia_db)[0] & store.page_paths(brazil_db)[0]
        if not p.startswith("markdown/delta-")
    )
    sample = shared[:: max(1, len(shared) // COMPARE_SAMPLE)]
    changed = 0
    for path in sample:
        old, new = store.get_document(australia_db, path), store.get_document(brazil_db, path)
        changed += any(not s.small for s in compare_pages(old or "", new or "").sections)
    return (round(changed / len(sample), 3) if sample else 0.0), len(sample)


def run_cli(argv: list[str]) -> int:
    """`snow-docs-mcp check-index`: 0 = healthy, 1 = a count below its floor, 2 = bad usage
    (including a file that is not a docs index)."""
    parser = argparse.ArgumentParser(
        prog="snow-docs-mcp check-index",
        description="Count what the tools find in a docs index and compare it with the floors.",
    )
    parser.add_argument("--australia", type=Path, help="path to an australia index (.db)")
    parser.add_argument("--brazil", type=Path, help="path to a brazil index (.db)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # --help exits 0, bad usage 2
        return 0 if stop.code in (0, None) else 2
    given = {r: p for r, p in (("australia", args.australia), ("brazil", args.brazil)) if p}
    if not given:
        print("check-index: pass --australia PATH and/or --brazil PATH", file=sys.stderr)
        return 2
    for release, path in given.items():
        if not path.is_file():
            print(f"check-index: no index file at {path}", file=sys.stderr)
            return 2
    failed: list[str] = []
    for release, path in given.items():
        try:
            found = counts(path, release)
        except sqlite3.Error as e:
            print(f"check-index: {path} is not a docs index ({e})", file=sys.stderr)
            return 2
        for key, value in found.items():
            print(f"{release}  {key}: {value:g}  (floor {FLOORS.get(key, 0):g})")
        failed += [f"{release}  {line}" for line in problems(found, FLOORS)]
    if len(given) == 2:
        noise, sampled = compare_noise(given["australia"], given["brazil"])
        print(
            f"compare  changed pages: {noise:g} of {sampled} sampled  (ceiling {MAX_COMPARE_NOISE:g})"
        )
        if noise > MAX_COMPARE_NOISE:
            failed.append(
                f"compare  changed pages: {noise:g} is above the ceiling of {MAX_COMPARE_NOISE:g}"
            )
    for line in failed:
        print(f"PROBLEM  {line}")
    print("index health: FAILED" if failed else "index health: OK")
    return 1 if failed else 0
