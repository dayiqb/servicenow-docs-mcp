"""Data folder, releases, latest.json entries and the testing overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from snow_docs_mcp import config
from snow_docs_mcp.config import IndexEntry


def test_env_overrides_the_data_folder(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom"
    monkeypatch.setenv("SNOW_DOCS_HOME", str(target))
    assert config.data_home() == target
    assert target.is_dir(), "the data folder is created on first use"
    assert config.models_dir() == target / "models"


def test_unexpanded_variables_from_the_host_are_resolved(monkeypatch, tmp_path) -> None:
    # Claude Desktop passed the manifest default "${HOME}/.servicenow-docs-mcp" through
    # verbatim; the server then created a folder literally named "${HOME}" in its cwd.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SNOW_DOCS_HOME", "${HOME}/.servicenow-docs-mcp")
    assert config.data_home() == tmp_path / ".servicenow-docs-mcp"


@pytest.mark.parametrize(
    "raw", ["${user_config.data_folder}", "relative/folder", "   ", "${NOT_A_REAL_VAR}/x"]
)
def test_unusable_values_fall_back_to_the_default(monkeypatch, tmp_path, raw) -> None:
    monkeypatch.delenv("NOT_A_REAL_VAR", raising=False)
    monkeypatch.setenv("SNOW_DOCS_HOME", raw)
    monkeypatch.setattr(config, "DEFAULT_HOME", tmp_path / "default")
    assert config.data_home() == tmp_path / "default"


def test_default_data_folder_is_under_home() -> None:
    assert config.DEFAULT_HOME == Path.home() / ".servicenow-docs-mcp"


def test_releases_and_default(monkeypatch) -> None:
    assert config.RELEASES == ("australia", "brazil")
    monkeypatch.delenv("SNOW_DOCS_RELEASE", raising=False)
    assert config.default_release() == "australia"
    monkeypatch.setenv("SNOW_DOCS_RELEASE", " Brazil ")
    assert config.default_release() == "brazil"
    assert config.normalize_release(None) == "brazil"
    assert config.normalize_release("AUSTRALIA") == "australia"
    assert config.normalize_release("tokyo") is None
    monkeypatch.setenv("SNOW_DOCS_RELEASE", "${user_config.release}")
    assert config.default_release() == "australia"


def test_latest_url_can_be_turned_off(monkeypatch) -> None:
    monkeypatch.delenv("SNOW_DOCS_LATEST_URL", raising=False)
    assert config.latest_url() == config.LATEST_URL
    assert config.LATEST_URL.startswith("https://raw.githubusercontent.com/")
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", "off")
    assert config.latest_url() is None


def test_builtin_entry_is_content_addressed() -> None:
    entry = config.BUILTIN_ENTRIES["australia"]
    assert entry.gz_sha256[:12] in entry.url and entry.snapshot in entry.url
    assert entry.url.startswith(f"https://github.com/{config.REPO}/releases/download/")
    assert entry.key == f"australia-2026-05-15-{entry.gz_sha256[:12]}"
    assert config.index_file(entry).name == f"index-{entry.key}.db"


def test_overrides_replace_url_and_checksums(monkeypatch) -> None:
    entry = config.BUILTIN_ENTRIES["australia"]
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    assert config.with_overrides(entry) == entry
    monkeypatch.setenv("SNOW_DOCS_INDEX_URL", "http://127.0.0.1:1/x.gz")
    monkeypatch.setenv("SNOW_DOCS_INDEX_SHA256", "AB" * 32)
    over = config.with_overrides(entry)
    assert over.url == "http://127.0.0.1:1/x.gz" and over.gz_sha256 == "ab" * 32
    assert over.gz_bytes is None and over.db_bytes is None and over.db_sha256 == ""


def _raw(**kw) -> dict:
    base = {
        "snapshot": "2026-09-24",
        "url": "https://github.com/x/y/releases/download/t/a.db.gz",
        "gz_sha256": "ab" * 32,
        "gz_bytes": 10,
        "db_bytes": 20,
        "min_server_version": "0.1.0",
    }
    base.update(kw)
    return base


def test_latest_entries_are_validated() -> None:
    e = IndexEntry.from_json("brazil", _raw())
    assert (e.release, e.snapshot, e.gz_bytes, e.db_bytes) == ("brazil", "2026-09-24", 10, 20)
    assert IndexEntry.from_json("brazil", _raw(url="http://127.0.0.1:8/a.gz")).url.startswith(
        "http://127.0.0.1"
    )
    for bad in (
        _raw(snapshot="yesterday"),
        _raw(gz_sha256="nothex"),
        _raw(url="http://evil.example/a.gz"),
        _raw(url="file:///etc/passwd"),
    ):
        with pytest.raises(ValueError):
            IndexEntry.from_json("brazil", bad)
    with pytest.raises((ValueError, KeyError)):
        IndexEntry.from_json("brazil", {"snapshot": "2026-09-24"})
    with pytest.raises(TypeError):
        IndexEntry.from_json("brazil", ["not", "an", "object"])


def test_version_comparison() -> None:
    assert config.version_tuple("0.10.0") > config.version_tuple("0.9.3")
    assert config.version_tuple("1.0") >= config.version_tuple("0.1.0")
