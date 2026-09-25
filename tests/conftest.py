"""Shared fixtures: a tiny index with the real schema, and fake models.

The fixture index mirrors the shipped file exactly (chunks + external-content FTS5 +
documents + meta), but holds six chunks whose embeddings are one-hot vectors, so the
semantic ranking of any query is fully determined by the fake embedder below. Nothing
here downloads a model.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from snow_docs_mcp import config, models

DIM = 384

INCIDENT_DOC = """---
title: Incident management
release: australia
---

# Incident management

Overview of incident handling.

## States

An incident moves through New, In Progress, Resolved and Closed.

### Resolved state

Resolved incidents close automatically after 7 days.

## Priority

Priority is calculated from impact and urgency.
"""

CASE_DOC = """---
title: HR case
---

# HR case

## Create

Create an HR case from the employee center portal.

## Close

Close the case once the employee confirms.
"""

PROBLEM_DOC = "# Problem management\n\nFind the root cause of recurring incidents.\n"
CHANGE_DOC = "# Change\n\n## Approval\n\nThe change advisory board approves normal changes.\n"

# (file_path, heading_path, blurb, body) — row i gets the one-hot embedding e_i.
CHUNKS = [
    (
        "markdown/itsm/incident.md",
        "Incident management > States",
        "Describes the incident lifecycle.",
        "An incident moves through New, In Progress, Resolved and Closed.",
    ),
    (
        "markdown/itsm/incident.md",
        "Incident management > Priority",
        "Explains how incident priority is derived.",
        "Priority is calculated from impact and urgency.",
    ),
    (
        "markdown/itsm/problem.md",
        "Problem management",
        "Introduces problem management.",
        "Find the root cause of recurring incidents.",
    ),
    (
        "markdown/hr/case.md",
        "HR case > Create",
        "How employees open HR cases.",
        "Create an HR case from the employee center portal.",
    ),
    (
        "markdown/hr/case.md",
        "HR case > Close",
        "How HR cases are closed.",
        "Close the case once the employee confirms.",
    ),
    (
        "markdown/itsm/change.md",
        "Change > Approval",
        "Covers change approvals by the CAB.",
        "The change advisory board approves normal changes zebrafish.",
    ),
]
DOCS = {
    "markdown/itsm/incident.md": INCIDENT_DOC,
    "markdown/hr/case.md": CASE_DOC,
    "markdown/itsm/problem.md": PROBLEM_DOC,
    "markdown/itsm/change.md": CHANGE_DOC,
}


def one_hot(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


def build_fixture_index(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL, heading_path TEXT NOT NULL,
            content TEXT NOT NULL, byte_offset INTEGER NOT NULL, embedding BLOB NOT NULL
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            content, content='chunks', content_rowid='id', tokenize='unicode61'
        );
        CREATE TRIGGER chunks_fts_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TABLE documents (file_path TEXT PRIMARY KEY, content TEXT NOT NULL);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    for i, (fp, hp, blurb, body) in enumerate(CHUNKS):
        content = f"{blurb}\n\n{hp}\n\n{body}"
        conn.execute(
            "INSERT INTO chunks (file_path, heading_path, content, byte_offset, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            (fp, hp, content, 0, one_hot(i).tobytes()),
        )
    conn.executemany("INSERT INTO documents VALUES (?, ?)", list(DOCS.items()))
    conn.executemany(
        "INSERT INTO meta VALUES (?, ?)",
        [
            ("snapshot", "2026-05-15"),
            ("corpus_commit", "0ba98cdaf706821d72ff79e92b18adc057e60e29"),
            ("corpus_repo", "https://github.com/ServiceNow/ServiceNowDocs"),
            ("chunk_count", str(len(CHUNKS))),
        ],
    )
    conn.execute("PRAGMA journal_mode = delete")
    conn.commit()
    conn.close()
    return path


class FakeModels:
    """Deterministic stand-ins for the embedder and reranker.

    `query_vectors` maps a query string to a weight per chunk row; unknown queries embed
    to a vector that prefers row 0. `rerank_scores` maps a substring to a score; the
    reranker gives each document the score of the first matching key (0.0 otherwise) and
    records what it was asked to score.
    """

    def __init__(self) -> None:
        self.query_vectors: dict[str, dict[int, float]] = {}
        self.rerank_scores: dict[str, float] = {}
        self.reranked_docs: list[list[str]] = []

    def embed_one(self, text: str) -> np.ndarray:
        weights = self.query_vectors.get(text, {0: 1.0})
        v = np.zeros(DIM, dtype=np.float32)
        for i, w in weights.items():
            v[i] = w
        return v

    def rerank(self, query: str, documents) -> list[float]:
        docs = list(documents)
        self.reranked_docs.append(docs)
        out = []
        for d in docs:
            score = 0.0
            for key, s in self.rerank_scores.items():
                if key in d:
                    score = s
                    break
            out.append(score)
        return out


FIXTURE_SHA = "f1" * 32  # a well-formed sha256 for fixture entries


def make_entry(
    release: str = "australia",
    snapshot: str = "2026-05-15",
    gz_sha: str = FIXTURE_SHA,
    url: str = "http://127.0.0.1:9/unused.db.gz",
    **kw,
):
    from snow_docs_mcp.config import IndexEntry

    return IndexEntry(
        release=release,
        snapshot=snapshot,
        corpus_commit=kw.pop("corpus_commit", "c0ffee"),
        url=url,
        gz_sha256=gz_sha,
        gz_bytes=kw.pop("gz_bytes", None),
        db_sha256=kw.pop("db_sha256", ""),
        db_bytes=kw.pop("db_bytes", None),
        **kw,
    )


def install_index(db_file: Path, entry) -> Path:
    """Put `db_file` in place as an installed index for `entry`, as setup would."""
    import json
    import shutil

    target = config.index_file(entry)
    shutil.copyfile(db_file, target)
    config.marker_file(entry).write_text(
        json.dumps(
            {
                "release": entry.release,
                "snapshot": entry.snapshot,
                "gz_sha256": entry.gz_sha256,
                "db_sha256": "",
                "db_bytes": target.stat().st_size,
            }
        )
    )
    return target


def fake_models_on_disk() -> None:
    """Create the model files setup.models_on_disk() looks for (no real download)."""
    from snow_docs_mcp import setup

    for name in setup.MODEL_DIRS:
        d = config.models_dir() / name / "snapshots" / "abc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "model.onnx").write_bytes(b"onnx")
        for f in setup.MODEL_FILES:
            (d / f).write_text("{}")


@pytest.fixture(autouse=True)
def _isolated_data_folder(tmp_path_factory, monkeypatch):
    """Safety net for EVERY test: connecting a client starts setup, which must never
    download into (or leave a lock in) the real ~/.servicenow-docs-mcp, nor read the real
    latest.json. Tests that need a specific folder or URL override these."""
    import urllib.error
    import urllib.parse

    from snow_docs_mcp import setup

    monkeypatch.setenv("SNOW_DOCS_HOME", str(tmp_path_factory.mktemp("snow-docs-home")))
    monkeypatch.setenv("SNOW_DOCS_INDEX_URL", "http://127.0.0.1:9/unreachable.db.gz")
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", "off")
    monkeypatch.delenv("SNOW_DOCS_RELEASE", raising=False)
    monkeypatch.setattr(setup, "RETRY_BASE_SECONDS", 0.0)
    real_urlopen = setup.urllib.request.urlopen

    def local_only(req, *args, **kwargs):  # e.g. a fallback to the real built-in index
        url = req.full_url if hasattr(req, "full_url") else str(req)
        host = urllib.parse.urlsplit(url).hostname
        if host not in ("127.0.0.1", "localhost"):
            raise urllib.error.URLError(f"tests never reach {host}")
        return real_urlopen(req, *args, **kwargs)

    monkeypatch.setattr(setup.urllib.request, "urlopen", local_only)
    setup._reset_for_tests()
    yield
    setup._reset_for_tests()


@pytest.fixture
def fake_models(monkeypatch) -> FakeModels:
    fake = FakeModels()
    monkeypatch.setattr(models, "embed_one", fake.embed_one)
    monkeypatch.setattr(models, "rerank", fake.rerank)
    monkeypatch.setattr(models, "warm_up", lambda: None)
    return fake


@pytest.fixture
def fixture_db(tmp_path) -> Path:
    return build_fixture_index(tmp_path / "fixture.db")
