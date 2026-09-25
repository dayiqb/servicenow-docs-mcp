"""Hybrid search, reranking, and the display helpers."""

from __future__ import annotations

import numpy as np
import pytest

from snow_docs_mcp import search as S
from snow_docs_mcp import store


def test_rrf_fuse_matches_hand_computation() -> None:
    # a: 1/61 + 1/62 ; b: 1/62 + 1/61 ; c: 1/63 ; d: 1/63 -> ties keep first-seen order
    fused = store._rrf_fuse([10, 20, 30], [20, 10, 40])
    assert fused[:2] == [10, 20]
    assert set(fused[2:]) == {30, 40}
    assert store._rrf_fuse([], []) == []


def test_semantic_only_orders_by_cosine(fixture_db) -> None:
    q = np.zeros(store.EMBED_DIM, dtype=np.float32)
    q[3], q[4], q[0] = 0.9, 0.5, 0.1
    hits = store.search(fixture_db, q, top_k=3, query_text=None)
    assert [h.heading_path for h in hits] == [
        "HR case > Create",
        "HR case > Close",
        "Incident management > States",
    ]
    assert hits[0].score > hits[1].score > hits[2].score


def test_keyword_half_promotes_an_exact_term(fixture_db) -> None:
    # Semantically the query points at row 0; only row 5 contains "zebrafish".
    q = np.zeros(store.EMBED_DIM, dtype=np.float32)
    q[0] = 1.0
    semantic = store.search(fixture_db, q, top_k=6, query_text=None)
    hybrid = store.search(fixture_db, q, top_k=6, query_text="zebrafish")

    def rank(hits):
        return [h.heading_path for h in hits].index("Change > Approval")

    assert rank(hybrid) < rank(semantic)


def test_prefix_filter_keeps_only_that_product(fixture_db) -> None:
    q = np.ones(store.EMBED_DIM, dtype=np.float32)
    hits = store.search(fixture_db, q, top_k=10, file_path_prefix="markdown/hr/", query_text="case")
    assert hits and all(h.file_path.startswith("markdown/hr/") for h in hits)
    assert store.search(fixture_db, q, top_k=10, file_path_prefix="markdown/nope/") == []


def test_reranker_sees_blurbed_content_and_reorders(fixture_db, fake_models) -> None:
    fake_models.query_vectors["incident states"] = {0: 1.0, 1: 0.8, 2: 0.6}
    fake_models.rerank_scores = {"root cause": 9.0, "lifecycle": 5.0}
    hits = S.run_search(fixture_db, "incident states", top_k=2, query_text="incident states")
    assert [h.heading_path for h in hits] == ["Problem management", "Incident management > States"]
    assert hits[0].score == 9.0
    # the measured config reranks the stored content INCLUDING the context line
    assert any(
        d.startswith("Describes the incident lifecycle.") for d in fake_models.reranked_docs[-1]
    )


def test_strip_blurb_and_snippet() -> None:
    content = "A context line.\n\nIncident > States\n\nBody   text\nhere."
    assert S.strip_blurb(content) == "Incident > States\n\nBody   text\nhere."
    assert S.strip_blurb("no blank line") == "no blank line"
    assert S.snippet(content) == "Incident > States Body text here."
    long = "ctx\n\n" + "word " * 400
    s = S.snippet(long, max_chars=100)
    assert len(s) <= 102 and s.endswith("…") and "ctx" not in s


def test_ids_round_trip_and_reject_garbage() -> None:
    doc_id = S.make_id("australia", "markdown/itsm/incident.md", "Incident management > States")
    assert doc_id == "australia:markdown/itsm/incident.md::Incident management > States"
    assert S.parse_id(doc_id) == (
        "australia",
        "markdown/itsm/incident.md",
        "Incident management > States",
        1,
    )
    third = S.make_id("brazil", "markdown/a.md", "A > Remedy", 3)
    assert third == "brazil:markdown/a.md::A > Remedy::3"
    assert S.parse_id(third) == ("brazil", "markdown/a.md", "A > Remedy", 3)
    assert S.parse_id("markdown/a.md::") == (None, "markdown/a.md", "", 1), "old ids still parse"
    assert S.parse_id("incident states") is None
    assert S.parse_id("notes.txt::x") is None


def test_context_prefix_is_removed_by_length_when_known() -> None:
    content = "A context line.\n\nHeading\n\nBody"
    assert S.strip_blurb(content, len("A context line.\n\n")) == "Heading\n\nBody"
    assert S.strip_blurb("Heading\n\nBody", 0) == "Heading\n\nBody", "no context line: keep all"
    assert S.strip_blurb(content) == "Heading\n\nBody", "old indexes: split on the first gap"
    assert S.snippet("Body only, no context", 0) == "Body only, no context"


def test_products(fixture_db) -> None:
    assert store.products(fixture_db) == ["hr", "itsm"]
    assert store.product_of("markdown/itsm/a/b.md") == "itsm"
    assert store.product_of("README.md") == ""


def test_index_connections_are_read_only(fixture_db) -> None:
    import sqlite3

    conn = store._connect(fixture_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE t (a)")
    finally:
        conn.close()


def test_a_missing_index_file_is_not_created(tmp_path) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(FileNotFoundError):
        store._connect(missing)
    assert not missing.exists()


def test_a_unc_index_path_is_opened_without_a_uri(fixture_db, monkeypatch) -> None:
    # Windows maps network drives to \\server\share paths, which SQLite rejects as URIs.
    import sqlite3
    from pathlib import PureWindowsPath

    unc = PureWindowsPath(r"\\fileserver\home\me\.servicenow-docs-mcp\index.db")
    real_connect = sqlite3.connect
    seen = []

    def spy(target, *a, uri=False, **kw):
        seen.append((str(target), uri))
        return real_connect(str(fixture_db), check_same_thread=False)

    monkeypatch.setattr(type(fixture_db), "resolve", lambda self: unc)
    monkeypatch.setattr(store.sqlite3, "connect", spy)
    store._connect(fixture_db).close()
    assert seen == [(str(unc), False)]


def test_matrices_of_deleted_snapshots_are_dropped(tmp_path) -> None:
    import shutil

    from conftest import build_fixture_index

    a = build_fixture_index(tmp_path / "a.db")
    b = tmp_path / "b.db"
    shutil.copyfile(a, b)
    q = np.zeros(store.EMBED_DIM, dtype=np.float32)
    q[0] = 1.0
    store.search(a, q, top_k=1)
    a.unlink()  # another app switched snapshots and deleted this one
    store.search(b, q, top_k=1)
    assert str(a.resolve()) not in store._matrix_cache


def test_a_page_header_reads_as_title_and_description() -> None:
    content = (
        "A context line.\n\n---\ntitle: Classic Business rules\ndescription: A business rule "
        "is a server-side script.\nbreadcrumb: [Build workflows]\n---\n\nBusiness rules run "
        "when records change."
    )
    assert S.snippet(content, len("A context line.\n\n")) == (
        "Classic Business rules: A business rule is a server-side script. "
        "Business rules run when records change."
    )
    cut_off = (  # long headers span two passages: the first has no closing ---
        "A context line.\n\n---\ntitle: Very long header\ndescription: Covers it all."
    )
    assert S.snippet(cut_off, len("A context line.\n\n")) == "Very long header: Covers it all."
    assert S.snippet("---\nno fields here", 0) == "--- no fields here"
