"""Index install/update per release, against a real local HTTP server (Range support,
cut-offs, bad files, latest.json)."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import build_fixture_index, fake_models_on_disk, install_index, make_entry

from snow_docs_mcp import config, setup, store


class _Server:
    """Serves files by path with Range support, and records every request.

    `files` maps a URL path (e.g. "/index.db.gz") to bytes. cut_first_after: on the FIRST
    plain GET of a .gz file, send only that many bytes (with the full Content-Length) and
    drop the connection — a network cut.
    """

    def __init__(self, files: dict[str, bytes], cut_first_after: int | None = None) -> None:
        self.files = files
        self.cut_first_after = cut_first_after
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a) -> None:
                pass

            def do_GET(self) -> None:
                rng = self.headers.get("Range")
                outer.requests.append({"path": self.path, "range": rng})
                body = outer.files.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if rng:
                    start = int(rng.split("=")[1].split("-")[0])
                    if start >= len(body):
                        self.send_response(416)
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
                    self.send_header("Content-Length", str(len(body) - start))
                    self.end_headers()
                    self.wfile.write(body[start:])
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if outer.cut_first_after is not None and self.path.endswith(".gz"):
                    cut, outer.cut_first_after = outer.cut_first_after, None
                    self.wfile.write(body[:cut])
                    self.wfile.flush()
                    self.close_connection = True
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def gz_requests(self) -> list[dict]:
        return [r for r in self.requests if r["path"].endswith(".gz")]

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def payload(tmp_path) -> tuple[bytes, str, bytes]:
    """(gz payload, gz sha256, raw db bytes) of the fixture index."""
    raw = build_fixture_index(tmp_path / "src.db").read_bytes()
    gz = gzip.compress(raw)
    return gz, hashlib.sha256(gz).hexdigest(), raw


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("SNOW_DOCS_HOME", str(h))
    return h


@pytest.fixture
def srv():
    servers: list[_Server] = []

    def make(files, **kw) -> _Server:
        s = _Server(files, **kw)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def _override(monkeypatch, s: _Server, sha: str, path: str = "/index.db.gz") -> None:
    """Point the built-in australia entry at the local server (the testing override)."""
    monkeypatch.setenv("SNOW_DOCS_INDEX_URL", s.base + path)
    monkeypatch.setenv("SNOW_DOCS_INDEX_SHA256", sha)


def _files(home) -> list[str]:
    return sorted(p.name for p in home.iterdir() if p.name not in (".setup.lock", "models"))


def _wait(pred, timeout=10.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


# --- install ---------------------------------------------------------------------------------


def test_fresh_download_installs_a_working_index(home, payload, srv, monkeypatch) -> None:
    gz, sha, raw = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    monkeypatch.setenv("SNOW_DOCS_INDEX_DB_SHA256", hashlib.sha256(raw).hexdigest())
    st = setup.ensure("australia", with_models=False)
    assert st.state == "ready", st.message
    (inst,) = setup.installed("australia")
    assert inst.snapshot == "2026-05-15" and inst.key.endswith(sha[:12])
    assert setup.index_ready("australia") and setup.active_index("australia") == inst.db_path
    marker = json.loads(inst.db_path.with_suffix(".ok").read_text())
    assert marker["gz_sha256"] == sha and marker["db_bytes"] == len(raw)
    assert marker["db_sha256"] == hashlib.sha256(raw).hexdigest()
    assert store.chunk_count(inst.db_path) == 6
    assert _files(home) == sorted([inst.db_path.name, inst.db_path.with_suffix(".ok").name])


def test_a_cut_download_resumes_with_a_range_request(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    cut = len(gz) // 3
    s = srv({"/index.db.gz": gz}, cut_first_after=cut)
    _override(monkeypatch, s, sha)
    assert setup.ensure("australia", with_models=False).state == "ready"
    ranges = [r["range"] for r in s.gz_requests()]
    assert ranges[0] is None and ranges[1] and ranges[1].startswith("bytes=")
    assert 0 < int(ranges[1].split("=")[1].rstrip("-")) <= cut


def test_a_fresh_download_with_the_wrong_checksum_is_fatal(home, payload, srv, monkeypatch) -> None:
    gz, _, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, "0" * 64)
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "does not match" in st.message and "for a day" in st.message
    n = len(s.gz_requests())
    monkeypatch.setattr(setup, "RETRY_AFTER_ERROR_SECONDS", 0.0)
    setup.request("australia")  # a later tool call
    time.sleep(0.4)
    assert len(s.gz_requests()) == n, "a checksum mismatch must not re-download on its own"
    assert [n for n in _files(home) if not n.endswith(".bad")] == []
    # a new server process (another Claude Code session) must not download it again either
    setup._reset_for_tests()
    st2 = setup.ensure("australia", with_models=False)
    assert st2.state == "error" and "failed its checksum before" in st2.message
    assert len(s.gz_requests()) == n
    # a day later (the maintainer may have re-uploaded the file) it is tried again
    (bad,) = home.glob("*.bad")
    a_day_ago = time.time() - setup.BAD_RETRY_SECONDS - 60
    os.utime(bad, (a_day_ago, a_day_ago))
    setup._reset_for_tests()
    setup.ensure("australia", with_models=False)
    assert len(s.gz_requests()) == n + 1


def test_a_corrupt_resumed_file_gets_one_fresh_retry(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    entry = setup.target_entry("australia")
    config.gz_part_file(entry).write_bytes(b"\0" * (len(gz) // 2))  # garbage from an old run
    st = setup.ensure("australia", with_models=False)
    assert st.state == "ready", st.message
    ranges = [r["range"] for r in s.gz_requests()]
    assert ranges[0] and ranges[-1] is None, "resumed first, then one fresh download"


def test_a_login_page_instead_of_the_index_is_retried(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": b"<html>Please log in to the Wi-Fi</html>"})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    monkeypatch.setattr(
        config,
        "BUILTIN_ENTRIES",
        {"australia": make_entry(url=s.base + "/index.db.gz", gz_sha=sha, gz_bytes=len(gz))},
    )
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "login page" in st.message and "retries" in st.message
    s.files["/index.db.gz"] = gz  # the user logs in to the Wi-Fi
    assert setup.ensure("australia", with_models=False).state == "ready"


def test_an_unpacked_index_with_the_wrong_hash_is_rejected(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    monkeypatch.setenv("SNOW_DOCS_INDEX_DB_SHA256", "f" * 64)
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "unpacked" in st.message
    assert not setup.index_ready("australia")
    assert not [n for n in _files(home) if n.startswith(".index-")], "no unpack temp left"


def test_leftovers_of_a_killed_unpack_are_cleaned(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    home.mkdir(parents=True, exist_ok=True)
    (home / ".index-australia-x1y2.part").write_bytes(b"\0" * 1000)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert not (home / ".index-australia-x1y2.part").exists()


def test_a_missing_release_asset_says_so_without_retrying(home, payload, srv, monkeypatch) -> None:
    _, sha, _ = payload
    s = srv({})
    _override(monkeypatch, s, sha, path="/missing.db.gz")
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "HTTP 404" in st.message and config.README_URL in st.message
    assert len(s.requests) == 1


def test_an_unreachable_server_reports_an_error(home, payload, monkeypatch) -> None:
    # the autouse fixture already points downloads at an unreachable port
    monkeypatch.setenv("SNOW_DOCS_INDEX_SHA256", payload[1])
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "download kept failing" in st.message
    assert not setup.index_ready("australia")


def test_installed_index_needs_no_network(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    assert setup.ensure("australia", with_models=False).state == "ready"
    n = len(s.requests)
    setup._reset_for_tests()
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert len(s.requests) == n


def test_a_truncated_index_is_not_trusted(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    setup.ensure("australia", with_models=False)
    db = setup.active_index("australia")
    with db.open("r+b") as f:
        f.truncate(4096)
    assert not setup.index_ready("australia"), "the marker records the size"


def test_a_marker_that_is_not_an_object_is_ignored(home, fixture_db) -> None:
    entry = make_entry()
    install_index(fixture_db, entry)
    config.marker_file(entry).write_text("[]")
    assert setup.installed("australia") == []


def test_a_deleted_index_is_reinstalled_in_the_background(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    fake_models_on_disk()
    assert setup.ensure("australia").state == "ready"
    setup.active_index("australia").unlink()
    assert not setup.search_ready("australia")
    setup.request("australia")
    assert _wait(lambda: setup.search_ready("australia"))
    assert len(s.gz_requests()) == 2


# --- snapshots and updates -----------------------------------------------------------------


def _latest(entries: dict) -> bytes:
    return json.dumps({"schema": 1, "indexes": entries}).encode()


def _entry_json(s: _Server, gz: bytes, sha: str, snapshot: str, path: str, **kw) -> dict:
    s.files[path] = gz
    return {
        "snapshot": snapshot,
        "url": s.base + path,
        "gz_sha256": sha,
        "gz_bytes": len(gz),
        "min_server_version": kw.pop("min_server_version", "0.1.0"),
        **kw,
    }


def _name_in_latest(s: _Server, monkeypatch, *entries) -> None:
    """Publish a latest.json naming these (already installed) entries."""
    s.files["/latest.json"] = _latest(
        {
            e.release: {
                "snapshot": e.snapshot,
                "url": s.base + f"/{e.key}.db.gz",
                "gz_sha256": e.gz_sha256,
                "min_server_version": e.min_server_version,
            }
            for e in entries
        }
    )
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)


def test_latest_json_installs_a_newer_snapshot_and_retires_the_old(
    home, payload, srv, fixture_db, monkeypatch
) -> None:
    gz, sha, _ = payload
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    old = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    install_index(fixture_db, old)
    s = srv({})
    s.files["/latest.json"] = _latest(
        {"australia": _entry_json(s, gz, sha, "2026-09-24", "/au-0924.db.gz")}
    )
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    assert setup.ensure("australia", with_models=False).state == "ready"
    (inst,) = setup.installed("australia")
    assert inst.snapshot == "2026-09-24", "searches switch to the new snapshot"
    assert not config.index_file(old).exists(), "the older snapshot is removed"


def test_latest_json_entries_needing_a_newer_server_are_skipped(
    home, payload, srv, fixture_db, monkeypatch
) -> None:
    gz, sha, _ = payload
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry(gz_sha="aa" * 32)})
    install_index(fixture_db, config.BUILTIN_ENTRIES["australia"])
    s = srv({})
    s.files["/latest.json"] = _latest(
        {
            "australia": _entry_json(
                s, gz, sha, "2026-09-24", "/new.db.gz", min_server_version="9.0.0"
            )
        }
    )
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.installed("australia")[0].snapshot == "2026-05-15"
    assert s.gz_requests() == [] and "9.0.0" in setup.update_note()


def test_a_broken_latest_json_keeps_the_current_index(home, fixture_db, srv, monkeypatch) -> None:
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    install_index(fixture_db, config.BUILTIN_ENTRIES["australia"])
    s = srv({"/latest.json": b"{not json"})
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    assert setup.ensure("australia", with_models=False).state == "ready"


def test_brazil_is_unavailable_until_published_then_installs(
    home, payload, srv, monkeypatch
) -> None:
    gz, sha, _ = payload
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    s = srv({"/latest.json": _latest({})})
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    st = setup.ensure("brazil", with_models=False)
    assert st.state == "unavailable" and "No brazil docs index" in st.message
    s.files["/latest.json"] = _latest(
        {"brazil": _entry_json(s, gz, sha, "2026-09-24", "/br.db.gz")}
    )
    setup.refresh_latest(force=True)
    assert setup.ensure("brazil", with_models=False).state == "ready"
    assert setup.installed("brazil")[0].snapshot == "2026-09-24"
    assert setup.installed("australia") == [], "other releases are not downloaded"


def test_a_newer_installed_snapshot_is_never_downgraded_or_deleted(
    home, fixture_db, monkeypatch
) -> None:
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    newer = make_entry(snapshot="2099-01-01", gz_sha="bb" * 32)
    install_index(fixture_db, newer)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.installed("australia")[0].snapshot == "2099-01-01"


def test_only_this_servers_older_snapshots_are_removed(home, fixture_db, srv, monkeypatch):
    current = make_entry(snapshot="2026-05-15")
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    _name_in_latest(srv({}), monkeypatch, current)
    install_index(fixture_db, current)
    older = make_entry(snapshot="2020-01-01", gz_sha="cc" * 32)
    other_release = make_entry(release="brazil", snapshot="2020-01-01", gz_sha="dd" * 32)
    install_index(fixture_db, older)
    install_index(fixture_db, other_release)
    unrelated = [
        home / "index-customers.db",
        home / "notes.txt",
        home / "index-australia-2020-01-01-cccccccccccc.db.bak",  # near miss, legal on Windows
    ]
    for p in unrelated:
        p.write_text("x")
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert not config.index_file(older).exists()
    assert config.index_file(other_release).exists(), "another release is left alone"
    assert all(p.exists() for p in unrelated)


# --- disk space ------------------------------------------------------------------------------


def _fake_free(monkeypatch, *frees: int) -> None:
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    seq = list(frees)
    monkeypatch.setattr(
        setup.shutil, "disk_usage", lambda p: usage(10, 10, seq.pop(0) if len(seq) > 1 else seq[0])
    )


def test_low_disk_space_is_reported_before_downloading(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    _fake_free(monkeypatch, 1_000_000)
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "not enough free disk space" in st.message
    assert s.requests == []


def test_disk_space_is_rechecked_before_unpacking(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    _fake_free(monkeypatch, 10**12, 1_000_000)
    st = setup.ensure("australia", with_models=False)
    assert st.state == "error" and "to unpack" in st.message
    assert [n for n in _files(home) if n.endswith(".gz.part")], "the download is kept"
    assert not [n for n in _files(home) if n.startswith(".index-")]


# --- models --------------------------------------------------------------------------------


def test_models_download_once_and_only_when_missing(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    calls = []

    def fake_warm_up() -> None:
        calls.append(setup.index_ready("australia"))
        fake_models_on_disk()

    monkeypatch.setattr(setup.models, "warm_up", fake_warm_up)
    assert setup.ensure("australia").state == "ready"
    assert calls == [True], "first run: models download after the index is in place"
    setup._reset_for_tests()
    assert setup.ensure("australia").state == "ready"
    assert calls == [True], "later starts leave model loading to the first search"


def test_missing_model_files_are_downloaded_again(home, payload, srv, monkeypatch) -> None:
    import shutil

    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    fake_models_on_disk()
    assert setup.ensure("australia").state == "ready"
    shutil.rmtree(config.models_dir())
    assert not setup.search_ready("australia")
    monkeypatch.setattr(setup.models, "warm_up", fake_models_on_disk)
    assert setup.ensure("australia").state == "ready" and setup.search_ready("australia")


# --- the cross-process lock -------------------------------------------------------------------


def _hold_lock_in_subprocess(lock_file) -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import time; from filelock import FileLock; "
                f"l = FileLock({str(lock_file)!r}); l.acquire(); print('held', flush=True); "
                "time.sleep(120)"
            ),
        ],
        stdout=subprocess.PIPE,
    )
    assert proc.stdout.readline().strip() == b"held"
    return proc


def test_waits_for_another_process_then_continues_when_it_dies(
    home, payload, srv, monkeypatch
) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    home.mkdir(parents=True, exist_ok=True)
    holder = _hold_lock_in_subprocess(home / ".setup.lock")
    result = {}
    t = threading.Thread(
        target=lambda: result.update(s=setup.ensure("australia", with_models=False))
    )
    try:
        t.start()
        assert _wait(lambda: setup.status("australia").state == "waiting", 5)
        assert s.gz_requests() == []
        holder.kill()  # a crash, not a clean release: the OS frees the lock
        holder.wait()
        t.join(timeout=15)
    finally:
        if holder.poll() is None:
            holder.kill()
    assert result["s"].state == "ready", result["s"].message
    assert len(s.gz_requests()) == 1


def test_a_leftover_lock_file_does_not_block(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    home.mkdir(parents=True, exist_ok=True)
    (home / ".setup.lock").write_text("left behind by a crashed process\n")
    assert setup.ensure("australia", with_models=False).state == "ready"


def test_requests_are_queued_once(home, payload, srv, monkeypatch) -> None:
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    fake_models_on_disk()
    setup.request("australia")
    setup.request("australia")
    assert _wait(lambda: setup.search_ready("australia"))
    assert len(s.gz_requests()) == 1


# --- review round 3: shared folders, versions, rebuilds, leftovers ---------------------------


def _published(s: _Server, monkeypatch, entries: dict) -> None:
    s.files["/latest.json"] = _latest(entries)
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/latest.json")
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)


def test_a_same_date_rebuild_named_in_latest_json_is_used(
    home, payload, srv, fixture_db, monkeypatch
):
    gz, sha, _ = payload
    first = make_entry(snapshot="2026-10-01", gz_sha="ff" * 32)  # hex sorts after the rebuild
    install_index(fixture_db, first)
    s = srv({})
    _published(s, monkeypatch, {"australia": _entry_json(s, gz, sha, "2026-10-01", "/re.db.gz")})
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia").name.endswith(f"{sha[:12]}.db")
    assert not config.index_file(first).exists(), "the superseded same-date build is removed"


def test_an_older_server_keeps_a_compatible_index(home, payload, srv, fixture_db, monkeypatch):
    gz, sha, _ = payload
    mine = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": mine})
    install_index(fixture_db, mine)
    newer_fmt = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32, min_server_version="0.2.0")
    install_index(fixture_db, newer_fmt)
    marker = config.marker_file(newer_fmt)
    data = json.loads(marker.read_text())
    data["min_server_version"] = "0.2.0"
    marker.write_text(json.dumps(data))
    s = srv({})
    _published(
        s,
        monkeypatch,
        {
            "australia": _entry_json(
                s, gz, sha, "2026-10-01", "/v2.db.gz", min_server_version="0.2.0"
            )
        },
    )
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(mine), "never a too-new format"
    assert config.index_file(newer_fmt).exists(), "the newer server's index is left alone"


def test_a_newer_server_does_not_delete_the_last_old_format_index(home, fixture_db, monkeypatch):
    old_fmt = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    install_index(fixture_db, old_fmt)
    monkeypatch.setattr(config, "VERSION", "0.2.0")
    new = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32, min_server_version="0.2.0")
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": new})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    install_index(fixture_db, new)
    marker = config.marker_file(new)
    data = json.loads(marker.read_text())
    data["min_server_version"] = "0.2.0"
    marker.write_text(json.dumps(data))
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert config.index_file(old_fmt).exists(), "an older server sharing the folder needs it"


def test_a_blocked_delete_is_retried_later(home, fixture_db, srv, monkeypatch):
    current = make_entry(snapshot="2026-05-15")
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    s = srv({})
    _name_in_latest(s, monkeypatch, current)
    install_index(fixture_db, current)
    old = make_entry(snapshot="2020-01-01", gz_sha="cc" * 32)
    install_index(fixture_db, old)
    real_unlink = type(config.index_file(old)).unlink

    def windows_in_use(self, missing_ok=False):
        if self.name == config.index_file(old).name:
            raise PermissionError("[WinError 32] in use by another process")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(type(config.index_file(old)), "unlink", windows_in_use)
    setup.ensure("australia", with_models=False)
    assert config.marker_file(old).exists(), "marker kept so the next start retries"
    monkeypatch.undo()
    monkeypatch.setenv("SNOW_DOCS_HOME", str(home))
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    _name_in_latest(s, monkeypatch, current)
    setup._reset_for_tests()
    setup.ensure("australia", with_models=False)
    assert not config.index_file(old).exists() and not config.marker_file(old).exists()


def test_leftovers_are_swept(home, fixture_db, monkeypatch):
    current = make_entry()
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    install_index(fixture_db, current)
    orphan = home / "index-australia-2026-01-01-eeeeeeeeeeee.db"  # no marker
    orphan.write_bytes(b"x" * 100)
    stale_part = home / "index-australia-2026-02-02-dddddddddddd.db.gz.part"
    stale_part.write_bytes(b"x")
    a_day_ago = time.time() - setup.PART_MAX_AGE_SECONDS - 60
    os.utime(stale_part, (a_day_ago, a_day_ago))
    recent_part = home / "index-australia-2026-10-01-cccccccccccc.db.gz.part"
    recent_part.write_bytes(b"x")  # e.g. another server version's paused download
    (home / "index-australia-2026-03-03-aaaaaaaaaaaa.ok.tmp").write_text("{}")
    setup.ensure("australia", with_models=False)
    assert not orphan.exists() and not stale_part.exists()
    assert recent_part.exists(), "an unknown but recent partial download is kept for a day"
    assert not list(home.glob("*.ok.tmp"))
    assert setup.active_index("australia") == config.index_file(current)


def _legacy_install(home, fixture_db, sha: str) -> None:
    import shutil

    home.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture_db, home / "index-2026-05-15.db")
    size = fixture_db.stat().st_size
    (home / "index-2026-05-15.ok").write_text(json.dumps({"gz_sha256": sha, "db_bytes": size}))
    (home / "models.ok").write_text("{}")


def test_a_legacy_install_is_adopted_not_redownloaded(home, fixture_db, payload, monkeypatch):
    _, sha, _ = payload
    entry = make_entry(gz_sha=sha, db_bytes=fixture_db.stat().st_size)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": entry})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    _legacy_install(home, fixture_db, sha)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(entry)
    legacy = home / "index-2026-05-15.db"
    assert legacy.exists() and (home / "models.ok").exists(), "the first version keeps its files"
    assert os.path.samefile(legacy, config.index_file(entry)), "a hard link: no extra disk"
    assert setup.legacy_files() == [legacy]
    # the first version, still installed, may delete or replace its own file: no effect here
    legacy.unlink()
    setup._reset_for_tests()
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(entry)


def test_a_legacy_file_in_use_never_stops_setup(home, fixture_db, payload, srv, monkeypatch):
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    entry = make_entry(url=s.base + "/index.db.gz", gz_sha=sha, gz_bytes=len(gz))
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": entry})
    _legacy_install(home, fixture_db, sha)
    tried = []

    def in_use(src, dst):
        tried.append(src)
        raise PermissionError("[WinError 32] in use by another process")

    monkeypatch.setattr(setup.os, "link", in_use)
    st = setup.ensure("australia", with_models=False)
    assert tried, "the legacy file matched, so adopting it was tried"
    assert st.state == "ready", st.message
    assert len(s.gz_requests()) == 1, "it downloads instead"
    assert (home / "index-2026-05-15.db").exists()


def test_an_unmatched_legacy_index_is_left_alone(home, fixture_db, monkeypatch):
    # e.g. a later server with a different built-in index, started offline
    _legacy_install(home, fixture_db, "ab" * 32)
    setup.ensure("australia", with_models=False)
    assert (home / "index-2026-05-15.db").exists() and (home / "index-2026-05-15.ok").exists()


def test_a_complete_download_left_behind_is_unpacked_later(home, payload, srv, monkeypatch):
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)
    _fake_free(monkeypatch, 10**12, 1_000_000)
    assert setup.ensure("australia", with_models=False).state == "error"
    _fake_free(monkeypatch, 10**12)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert s.gz_requests()[-1]["range"] == f"bytes={len(gz)}-", "416 means: already complete"


def test_a_server_that_ignores_range_restarts_cleanly(home, payload, monkeypatch):
    gz, sha, _ = payload
    calls = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            calls.append(self.headers.get("Range"))
            self.send_response(200)
            self.send_header("Content-Length", str(len(gz)))
            self.end_headers()
            self.wfile.write(gz[: len(gz) // 3] if len(calls) == 1 else gz)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/x.db.gz"
        monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
        monkeypatch.setattr(
            config,
            "BUILTIN_ENTRIES",
            {"australia": make_entry(url=url, gz_sha=sha, gz_bytes=len(gz))},
        )
        assert setup.ensure("australia", with_models=False).state == "ready"
        assert calls[0] is None and calls[1] is not None, "resumed, got a full 200, restarted"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_start_sets_up_only_the_default_and_installed_releases(home, fixture_db, monkeypatch):
    asked = []
    monkeypatch.setattr(setup, "request", asked.append)
    monkeypatch.setattr(setup, "_update_loop", lambda: None)
    setup.start()
    assert asked == ["australia"], "Brazil must not download for everyone"
    install_index(fixture_db, make_entry(release="brazil", gz_sha="dd" * 32))
    asked.clear()
    setup._reset_for_tests()
    monkeypatch.setattr(setup, "request", asked.append)
    monkeypatch.setattr(setup, "_update_loop", lambda: None)
    setup.start()
    assert asked == ["australia", "brazil"]


def test_a_brazil_index_needing_a_newer_server_says_update(home, payload, srv, monkeypatch):
    gz, sha, _ = payload
    s = srv({})
    _published(
        s,
        monkeypatch,
        {"brazil": _entry_json(s, gz, sha, "2026-09-24", "/br.db.gz", min_server_version="9.0.0")},
    )
    st = setup.ensure("brazil", with_models=False)
    assert st.state == "unavailable" and "needs server 9.0.0" in st.message
    assert "Update the plugin" in st.message


def test_a_failed_model_download_is_reported_as_such(home, payload, srv, monkeypatch):
    gz, sha, _ = payload
    s = srv({"/index.db.gz": gz})
    _override(monkeypatch, s, sha)

    def blocked():
        raise OSError("huggingface.co blocked by proxy")

    monkeypatch.setattr(setup.models, "warm_up", blocked)
    st = setup.ensure("australia")
    assert st.state == "error" and "Searches keep using" not in st.message
    assert setup.models_status().state == "error"
    assert "could not be downloaded" in setup.models_status().message


def test_a_queued_release_says_so(home, monkeypatch):
    monkeypatch.setattr(setup, "_work", lambda: time.sleep(5))  # a busy worker
    setup.request("australia")
    assert setup.status("australia").message == "Starting.", "nothing else is downloading"
    setup.request("brazil")
    assert setup.status("brazil").state == "queued"
    assert "current download" in setup.status("brazil").message


# --- review round 4: shared views, formats, fallbacks, the lock -------------------------------


def _min_version(entry, version: str) -> None:
    marker = config.marker_file(entry)
    data = json.loads(marker.read_text())
    data["min_server_version"] = version
    marker.write_text(json.dumps(data))


def test_without_latest_json_nothing_is_deleted(home, fixture_db, monkeypatch):
    # offline, or SNOW_DOCS_LATEST_URL=off: an older snapshot may be what latest.json rolled
    # back to, so nothing is deleted
    current = make_entry(snapshot="2026-05-15")
    older = make_entry(snapshot="2020-01-01", gz_sha="cc" * 32)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    install_index(fixture_db, current)
    install_index(fixture_db, older)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert config.index_file(older).exists()
    assert setup.active_index("australia") == config.index_file(current)


def test_an_offline_start_follows_the_saved_latest_json(home, fixture_db, srv, monkeypatch):
    rolled_back_to = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    withdrawn = make_entry(snapshot="2026-10-15", gz_sha="bb" * 32)
    for e in (rolled_back_to, withdrawn):
        install_index(fixture_db, e)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": withdrawn})
    s = srv({})
    _name_in_latest(s, monkeypatch, rolled_back_to)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(rolled_back_to)
    del s.files["/latest.json"]  # GitHub unreachable for the next process
    setup._reset_for_tests()
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(rolled_back_to)
    assert config.index_file(rolled_back_to).exists() and config.index_file(withdrawn).exists()


def test_a_newer_view_saved_by_another_app_is_picked_up(home, fixture_db, srv, monkeypatch):
    a = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    b = make_entry(snapshot="2026-10-15", gz_sha="bb" * 32)
    for e in (a, b):
        install_index(fixture_db, e)
    s = srv({})
    _name_in_latest(s, monkeypatch, a)
    setup.refresh_latest()
    assert setup.active_index("australia") == config.index_file(a)
    saved = json.loads((home / setup.LATEST_CACHE).read_text())
    saved["doc"]["indexes"]["australia"]["snapshot"] = b.snapshot
    saved["doc"]["indexes"]["australia"]["gz_sha256"] = b.gz_sha256
    (home / setup.LATEST_CACHE).write_text(json.dumps(saved))  # another process read it
    n = len(s.requests)
    setup.refresh_latest()  # not due yet: no network, but the saved view is newer
    assert len(s.requests) == n
    assert setup.active_index("australia") == config.index_file(b)


def test_a_saved_latest_json_for_another_url_is_ignored(home, fixture_db, srv, monkeypatch):
    a = make_entry(snapshot="2026-05-15", gz_sha="aa" * 32)
    b = make_entry(snapshot="2026-10-15", gz_sha="bb" * 32)
    for e in (a, b):
        install_index(fixture_db, e)
    s = srv({})
    _name_in_latest(s, monkeypatch, a)
    setup.refresh_latest()
    setup._reset_for_tests()
    monkeypatch.setenv("SNOW_DOCS_LATEST_URL", s.base + "/elsewhere.json")  # 404
    setup.refresh_latest()
    assert setup.active_index("australia") == config.index_file(b), "no view: the newest"


def test_an_older_server_never_deletes_what_it_cannot_read(home, fixture_db, srv, monkeypatch):
    mine = make_entry(snapshot="2026-10-01", gz_sha="aa" * 32)
    same_date_new_format = make_entry(
        snapshot="2026-10-01", gz_sha="bb" * 32, min_server_version="0.2.0"
    )
    later = make_entry(snapshot="2026-10-15", gz_sha="cc" * 32, min_server_version="0.2.0")
    for e in (mine, same_date_new_format, later):
        install_index(fixture_db, e)
        _min_version(e, e.min_server_version)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": mine})
    _name_in_latest(srv({}), monkeypatch, same_date_new_format)  # rolled back to it
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert setup.active_index("australia") == config.index_file(mine)
    assert config.index_file(same_date_new_format).exists(), "the newer server's active index"
    assert config.index_file(later).exists()


def test_the_built_in_build_never_replaces_a_same_date_rebuild(home, fixture_db, srv, monkeypatch):
    s = srv({})
    built_in = make_entry(snapshot="2026-10-01", gz_sha="aa" * 32, url=s.base + "/r1.db.gz")
    rebuild = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32)  # from latest.json, earlier
    install_index(fixture_db, rebuild)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": built_in})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert s.gz_requests() == [] and setup.active_index("australia") == config.index_file(rebuild)


def test_a_newer_servers_partial_download_is_kept(home, fixture_db, srv, monkeypatch):
    current = make_entry()
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    install_index(fixture_db, current)
    newer = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32, min_server_version="0.2.0")
    _name_in_latest(srv({}), monkeypatch, newer)
    part = config.gz_part_file(newer)
    part.write_bytes(b"x" * 10)
    two_days_ago = time.time() - 2 * setup.PART_MAX_AGE_SECONDS
    os.utime(part, (two_days_ago, two_days_ago))
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert part.exists(), "latest.json names it: the newer server resumes it"


def test_a_broken_published_index_falls_back_to_the_built_in(home, payload, srv, monkeypatch):
    gz, sha, _ = payload
    s = srv({"/builtin.db.gz": gz})
    built_in = make_entry(url=s.base + "/builtin.db.gz", gz_sha=sha, gz_bytes=len(gz))
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": built_in})
    _published(
        s, monkeypatch, {"australia": _entry_json(s, gz, "0" * 64, "2026-09-24", "/broken.db.gz")}
    )
    warmed = []

    def warm_up():
        warmed.append(True)
        fake_models_on_disk()

    monkeypatch.setattr(setup.models, "warm_up", warm_up)
    st = setup.ensure("australia")
    assert st.state == "error" and "does not match" in st.message
    assert "Searches keep using" in st.message
    assert setup.active_index("australia") == config.index_file(built_in)
    assert warmed and setup.search_ready("australia"), "the models still download"


def test_a_corrected_entry_is_retried_by_the_running_server(home, payload, srv, monkeypatch):
    gz, sha, raw = payload
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {})
    s = srv({})
    wrong = _entry_json(s, gz, sha, "2026-09-24", "/x.db.gz", db_sha256="f" * 64)
    _published(s, monkeypatch, {"australia": wrong})
    assert "unpacked" in setup.ensure("australia", with_models=False).message
    right = {**wrong, "db_sha256": hashlib.sha256(raw).hexdigest()}  # same url and gz sha
    s.files["/latest.json"] = _latest({"australia": right})
    setup.refresh_latest(force=True)
    monkeypatch.setattr(setup, "RETRY_AFTER_ERROR_SECONDS", 0.0)
    fake_models_on_disk()
    setup.request("australia")  # e.g. the next search, or the daily update
    assert _wait(lambda: setup.search_ready("australia"))
    assert not list(home.glob("*.bad")), "a successful install forgets the failure"


def test_an_installed_release_does_not_wait_for_another_apps_download(home, fixture_db, monkeypatch):
    current = make_entry()
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": current})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    install_index(fixture_db, current)
    fake_models_on_disk()
    holder = _hold_lock_in_subprocess(home / ".setup.lock")  # e.g. a long Brazil download
    try:
        t0 = time.monotonic()
        st = setup.ensure("australia")
        elapsed = time.monotonic() - t0
    finally:
        holder.kill()
        holder.wait()
    assert st.state == "ready" and elapsed < 5, (st, elapsed)


def test_an_older_server_leaves_every_newer_format_index_alone(home, fixture_db, srv, monkeypatch):
    # not named, not newer, not the newest of its format: still the newer server's business
    mine = make_entry(snapshot="2026-10-15", gz_sha="aa" * 32)
    their_old = make_entry(snapshot="2026-10-01", gz_sha="bb" * 32, min_server_version="0.2.0")
    their_current = make_entry(snapshot="2026-10-05", gz_sha="cc" * 32, min_server_version="0.2.0")
    for e in (mine, their_old, their_current):
        install_index(fixture_db, e)
        _min_version(e, e.min_server_version)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": mine})
    _name_in_latest(srv({}), monkeypatch, their_current)
    assert setup.ensure("australia", with_models=False).state == "ready"
    assert config.index_file(their_old).exists()
