"""Table names the docs mention, collected once per index and cached in the data folder."""

from __future__ import annotations

from conftest import DOCS, build_fixture_index

from snow_docs_mcp import config, tables


def _db(tmp_path):
    docs = {
        **DOCS,
        "markdown/a.md": "The Incident [incident] and Group \\[sys\\_user\\_group\\] tables. See [the guide](x.md).",
        "markdown/b.md": "Task [task] extends nothing. [Optional] [2] [cmdb_ci_server]",
    }
    return build_fixture_index(tmp_path / "index-australia-2026-01-01-abc.db", docs=docs)


def test_names_in_brackets_are_collected_without_links_and_escapes(tmp_path):
    names = tables.names(_db(tmp_path))
    assert {"incident", "sys_user_group", "task", "cmdb_ci_server"} <= names
    assert "the guide" not in names and "Optional" not in names and "2" not in names


def test_the_list_is_cached_in_the_data_folder_per_index(tmp_path, monkeypatch):
    db = _db(tmp_path)
    first = tables.names(db)
    cache = config.data_home() / "tables-index-australia-2026-01-01-abc.json"
    assert cache.is_file()
    tables._memory.clear()
    monkeypatch.setattr(
        tables, "scan", lambda db: (_ for _ in ()).throw(AssertionError("rescanned"))
    )
    assert tables.names(db) == first


def test_a_broken_cache_file_is_rebuilt(tmp_path):
    db = _db(tmp_path)
    cache = config.data_home() / "tables-index-australia-2026-01-01-abc.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("not json")
    assert "incident" in tables.names(db)


def test_the_cache_file_goes_when_its_index_is_deleted(tmp_path):
    from snow_docs_mcp import setup

    home = config.data_home()
    home.mkdir(parents=True, exist_ok=True)
    db = build_fixture_index(home / "index-australia-2026-01-01-abc.db", docs=DOCS)
    tables.names(db)
    cache = home / "tables-index-australia-2026-01-01-abc.json"
    assert cache.is_file()
    assert setup._delete_index(db)
    assert not db.exists() and not cache.exists()
    assert str(db) not in tables._memory


def test_a_cache_file_left_without_its_index_is_swept(tmp_path):
    """Versions before this one never deleted the file, so data folders have orphans."""
    from snow_docs_mcp import setup

    home = config.data_home()
    home.mkdir(parents=True, exist_ok=True)
    orphan = home / "tables-index-australia-2025-12-01-000.json"
    orphan.write_text("[]")
    other_release = home / "tables-index-brazil-2025-12-01-000.json"
    other_release.write_text("[]")
    setup._sweep("australia", set())
    assert not orphan.exists()
    assert other_release.exists()  # each release sweeps its own files
