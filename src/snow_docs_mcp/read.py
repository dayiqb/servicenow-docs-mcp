"""Resolve a search-hit id to the full section text, from the docs shipped in the index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from snow_docs_mcp import sections, store
from snow_docs_mcp.search import make_id

# A real id from the shipped index, used in error messages.
EXAMPLE_ID = (
    "australia:markdown/it-service-management/incident-management/overdue-state-dashboard.md"
    "::Legacy: Overdue by State dashboard > Indicators"
)


@dataclass
class ReadResult:
    ok: bool
    message: str
    id: str = ""
    title: str = ""
    url: str = ""
    heading_path: str = ""
    content: str = ""
    truncated: bool = False


def not_an_id(doc_id: str) -> ReadResult:
    return ReadResult(
        ok=False,
        message=(
            f"'{doc_id}' is not a docs id. Pass an `id` exactly as snow_docs_search "
            f"returned it, e.g. '{EXAMPLE_ID}'."
        ),
    )


def read_section(
    db_path: str | Path,
    release: str,
    file_path: str,
    heading_path: str,
    occurrence: int = 1,
    max_chars: int = 20000,
) -> ReadResult:
    """The section an id points at (the whole page when its heading part is empty)."""
    text = store.get_document(db_path, file_path)
    if text is None:
        return ReadResult(
            ok=False,
            message=(
                f"No page '{file_path}' in the {release} docs. Ids come from "
                "snow_docs_search; search again and pass one of its ids."
            ),
        )

    title = sections.front_matter_value(text, "title")
    url = sections.front_matter_value(text, "canonical_url") or store.source_url(db_path, file_path)
    if heading_path:
        body = sections.extract_section(text, heading_path, occurrence)
        if body is None:
            count = sections.count_sections(text, heading_path)
            if count and occurrence > count:
                hint = (
                    f"That page has {count} sections named '{heading_path}'; use the suffix "
                    f"::1 to ::{count}."
                )
            else:
                available = sections.headings(text)
                shown = "; ".join(available[:10]) + (" …" if len(available) > 10 else "")
                hint = f"Sections in that page: {shown or '(none)'}."
            return ReadResult(
                ok=False,
                message=(
                    f"Section '{heading_path}' not found in '{file_path}'. {hint} "
                    f"Pass '{release}:{file_path}::' to read the whole page."
                ),
            )
    else:
        body = sections.strip_front_matter(text)

    max_chars = max(500, min(int(max_chars), 100_000))
    truncated = len(body) > max_chars
    if truncated:
        body = body[:max_chars].rstrip() + "\n\n[… truncated — raise max_chars to see more]"
    where = f"section '{heading_path}'" if heading_path else "whole page"
    return ReadResult(
        ok=True,
        message=f"Returning the {where} of '{file_path}' ({release}, {len(body)} chars).",
        id=make_id(release, file_path, heading_path, occurrence),
        title=title,
        url=url,
        heading_path=heading_path,
        content=body,
        truncated=truncated,
    )
