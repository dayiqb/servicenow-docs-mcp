"""Docs indexes and search models: first-run install and daily updates, per release.

The server answers MCP `initialize` immediately; all downloading happens in one background
worker thread, so no client times out. Tools check the disk (`index_ready`, `search_ready`)
and, when something is missing, `request()` it and report progress instead of results.

Per release (australia, brazil):
    1. which index?  `index/latest.json` (checked at start and daily) names the newest
                     snapshot; each server version also has a built-in entry (config.py).
    2. download      <index>.db.gz.part, resumable (HTTP Range), size-checked
    3. verify        sha256 of the .gz (a resumed file that fails gets one fresh retry;
                     a fresh, full-size download that fails is fatal for that entry)
    4. unpack        into a private temp file while hashing it; must match the db sha256;
                     then a content-addressed name + .ok marker, so a file in use is never
                     replaced (Windows) and several snapshots can coexist
    5. switch        searches use the snapshot latest.json names (else the newest one);
                     snapshots nobody needs any more are deleted when possible (retried
                     at the next start)
Once per machine: the embedder + reranker (~1.2 GB) download on first run; afterwards the
models load on the first search, so an idle server stays small.

Several Claude apps, possibly different server versions, may share the data folder. One
OS-level file lock (filelock: fcntl/msvcrt) serialises downloads across processes; the OS
releases it if a process dies, so a crash or a closed laptop can never leave a lock that
blocks or gets stolen. The last latest.json read is saved in the folder, so every process
(even one that starts offline) follows the same view, and nothing is deleted without one.
A server only ever deletes indexes it can read itself; newer formats are left to newer
servers.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import http.client
import json
import logging
import os
import queue
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from snow_docs_mcp import config, models, store
from snow_docs_mcp.config import IndexEntry

logger = logging.getLogger(__name__)

CHUNK_BYTES = 1 << 20
DOWNLOAD_ATTEMPTS = 6
RETRY_BASE_SECONDS = 2.0
RETRY_AFTER_ERROR_SECONDS = 30.0
UPDATE_INTERVAL_SECONDS = 24 * 3600
LATEST_RETRY_SECONDS = 3600
LATEST_TIMEOUT_SECONDS = 10
MODELS_BYTES = 1_200_000_000
FALLBACK_GZ_BYTES = 700_000_000  # when a custom URL has no pinned size
FALLBACK_DB_BYTES = 1_700_000_000
HEADROOM_BYTES = 200_000_000
BAD_RETRY_SECONDS = 24 * 3600  # a published file that failed its checksum: retry daily
PART_MAX_AGE_SECONDS = 24 * 3600  # an unknown partial download older than this is dropped
LATEST_CACHE = ".latest.json"
USER_AGENT = f"servicenow-docs-mcp/{config.VERSION}"
MODEL_DIRS = ("models--qdrant--bge-small-en-v1.5-onnx-q", "models--BAAI--bge-reranker-base")
_INDEX_FILE = re.compile(
    r"index-(?P<release>[a-z]+)-(?P<snapshot>\d{4}-\d{2}-\d{2})-(?P<sha>[0-9a-f]{12})\.ok",
    re.ASCII,
)


class FatalSetupError(RuntimeError):
    """Retrying cannot help (the published file does not match what this version expects)."""


@dataclass(frozen=True)
class SetupStatus:
    # idle | waiting | downloading | verifying | unpacking | ready | unavailable | error
    state: str
    message: str
    progress: float = 0.0  # 0..1 within the current step


@dataclass(frozen=True)
class Installed:
    release: str
    snapshot: str
    key: str
    db_path: Path
    min_server_version: str = "0.1.0"
    installed_at: float = 0.0


# --- module state ---------------------------------------------------------------------------

_state_lock = threading.RLock()
_status: dict[str, SetupStatus] = {}
_models: SetupStatus = SetupStatus("idle", "")
_latest: dict[str, IndexEntry] = {}
_latest_checked_at: float | None = None
_latest_ok = False
_update_note = ""
_last_error_at: dict[str, float] = {}
_bad_memory: dict[tuple[str, str, str], float] = {}  # in case the .bad file can't be written
_cache_mtime: float | None = None  # the saved latest.json this process last read or wrote
_last_logged: dict[str, tuple[str, int]] = {}
_queue: queue.Queue[str] = queue.Queue()
_pending: set[str] = set()
_worker: threading.Thread | None = None
_updater: threading.Thread | None = None


def _set(release: str, state: str, message: str, progress: float = 0.0) -> None:
    global _models
    progress = max(0.0, min(1.0, progress))
    value = SetupStatus(state, message, progress)
    with _state_lock:
        if release == "models":
            _models = value
        else:
            _status[release] = value
        key = (state, int(progress * 10))
        if _last_logged.get(release) != key:  # state changes and every 10%, not every MiB
            _last_logged[release] = key
            logger.info("setup[%s]: %s — %s", release, state, message)


def status(release: str) -> SetupStatus:
    with _state_lock:
        return _status.get(release, SetupStatus("idle", "Not set up yet."))


def models_status() -> SetupStatus:
    with _state_lock:
        return _models


def update_note() -> str:
    with _state_lock:
        return _update_note


# --- what is on disk -----------------------------------------------------------------------


def _read_marker(marker: Path) -> dict | None:
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _scan(release: str) -> list[Installed]:
    """Every verified index of `release` on disk (any server version), newest first."""
    found: list[Installed] = []
    for marker in config.data_home().glob(f"index-{release}-*.ok"):
        m = _INDEX_FILE.fullmatch(marker.name)
        data = _read_marker(marker) if m and m.group("release") == release else None
        if data is None:
            continue
        db = marker.with_suffix(".db")
        try:
            if db.stat().st_size != data.get("db_bytes"):
                continue
        except OSError:
            continue
        found.append(
            Installed(
                release,
                m.group("snapshot"),
                marker.stem[len("index-") :],
                db,
                str(data.get("min_server_version", "0.1.0")),
                float(data.get("installed_at", 0.0) or 0.0),
            )
        )
    found.sort(key=lambda i: (i.snapshot, i.installed_at, i.key), reverse=True)
    return found


def installed(release: str) -> list[Installed]:
    """Verified indexes of `release` this server version can read, newest first."""
    return [i for i in _scan(release) if _compatible_version(i.min_server_version)]


def active_installed(release: str) -> Installed | None:
    """The index searches use: the one latest.json names if it is installed, else the
    newest compatible one (so same-date rebuilds and rollbacks follow latest.json)."""
    inst = installed(release)
    if not inst:
        return None
    wanted = _authoritative_entry(release)
    if wanted is not None:
        for i in inst:
            if i.key == wanted.key:
                return i
    return inst[0]


def active_index(release: str) -> Path | None:
    act = active_installed(release)
    return act.db_path if act else None


def index_ready(release: str) -> bool:
    return active_index(release) is not None


def models_on_disk() -> bool:
    base = config.models_dir()
    for name in MODEL_DIRS:
        snapshots = base / name / "snapshots"
        if not snapshots.is_dir() or not any(snapshots.rglob("*.onnx")):
            return False
    return True


def search_ready(release: str) -> bool:
    return index_ready(release) and models_on_disk()


# --- which index should be installed ----------------------------------------------------------


def _compatible_version(min_server_version: str) -> bool:
    return config.version_tuple(config.VERSION) >= config.version_tuple(min_server_version)


def _compatible(entry: IndexEntry) -> bool:
    return _compatible_version(entry.min_server_version)


def _authoritative_entry(release: str) -> IndexEntry | None:
    """latest.json's entry for `release`, if it was read and this version can use it."""
    with _state_lock:
        entry = _latest.get(release)
    return config.with_overrides(entry) if entry is not None and _compatible(entry) else None


def _incompatible_entry(release: str) -> IndexEntry | None:
    with _state_lock:
        entry = _latest.get(release)
    return entry if entry is not None and not _compatible(entry) else None


def target_entry(release: str) -> IndexEntry | None:
    entry = _authoritative_entry(release)
    if entry is None:
        builtin = config.BUILTIN_ENTRIES.get(release)
        entry = config.with_overrides(builtin) if builtin else None
    return entry


def _apply_latest(doc: object) -> None:
    """Make a parsed latest.json this process's view. Raises ValueError if unusable."""
    global _update_note
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise ValueError("unsupported latest.json schema")
    entries: dict[str, IndexEntry] = {}
    notes = []
    for release, raw in (doc.get("indexes") or {}).items():
        if release not in config.RELEASES:
            continue
        try:
            entry = IndexEntry.from_json(release, raw)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("latest.json: ignoring %s entry (%s)", release, e)
            continue
        if not _compatible(entry):
            notes.append(
                f"a newer {release} docs index needs server {entry.min_server_version}+; "
                "update the plugin/extension to get it"
            )
        entries[release] = entry
    with _state_lock:
        _latest.clear()
        _latest.update(entries)
        _update_note = "; ".join(notes)


def _save_latest(url: str, doc: dict) -> None:
    """Share this latest.json with the other processes using the folder (atomic write)."""
    global _cache_mtime
    home = config.data_home()
    cache = home / LATEST_CACHE
    try:
        fd, tmp = tempfile.mkstemp(prefix=".latest-", suffix=".tmp", dir=home)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"schema": 1, "url": url, "doc": doc}, f)
        os.replace(tmp, cache)
        with _state_lock:
            _cache_mtime = cache.stat().st_mtime
    except OSError as e:
        logger.warning("could not save %s (%s)", cache, e)


def _load_saved_latest(url: str) -> None:
    """Adopt the latest.json another process saved, if it is new to this process."""
    global _cache_mtime
    cache = config.data_home() / LATEST_CACHE
    try:
        mtime = cache.stat().st_mtime
        with _state_lock:
            if mtime == _cache_mtime:
                return
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if not isinstance(saved, dict) or saved.get("schema") != 1 or saved.get("url") != url:
            return
        _apply_latest(saved.get("doc"))
        with _state_lock:
            _cache_mtime = mtime
    except (OSError, ValueError) as e:
        if not isinstance(e, FileNotFoundError):
            logger.warning("ignoring the saved %s (%s)", cache, e)


def refresh_latest(*, force: bool = False) -> None:
    """Read latest.json (at most daily; hourly after a failure). In between, or when it
    can't be reached, use the one saved in the data folder. Never raises."""
    global _latest_checked_at, _latest_ok
    url = config.latest_url()
    if url is None:
        return
    now = time.monotonic()
    with _state_lock:
        due = force or _latest_checked_at is None
        if not due:
            wait = UPDATE_INTERVAL_SECONDS if _latest_ok else LATEST_RETRY_SECONDS
            due = now - _latest_checked_at >= wait
        if due:
            _latest_checked_at = now
    if not due:
        _load_saved_latest(url)  # another process may have read a newer one meanwhile
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=LATEST_TIMEOUT_SECONDS) as resp:
            doc = json.loads(resp.read(1_000_000))
        _apply_latest(doc)
        with _state_lock:
            _latest_ok = True
        _save_latest(url, doc)
    except Exception as e:  # noqa: BLE001 - offline or GitHub down: keep what we have
        with _state_lock:
            _latest_ok = False
        logger.warning("could not read %s (%s); keeping the current indexes", url, e)
        _load_saved_latest(url)


# --- cross-process lock --------------------------------------------------------------------


@contextlib.contextmanager
def _file_lock(release: str) -> Iterator[None]:
    lock = FileLock(str(config.data_home() / ".setup.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        _set(
            release,
            "waiting",
            "Another Claude app on this computer is downloading docs data; waiting for it.",
        )
        lock.acquire()
    try:
        yield
    finally:
        lock.release()


@contextlib.contextmanager
def _lock_if_free() -> Iterator[bool]:
    """For best-effort housekeeping: never wait behind another app's long download."""
    lock = FileLock(str(config.data_home() / ".setup.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()


# --- download / verify / unpack ------------------------------------------------------------


def _mb(n: float) -> str:
    return f"{n / 1_000_000:,.0f} MB"


def _require_free(home: Path, needed: int, what: str) -> None:
    free = shutil.disk_usage(home).free
    if free < needed + HEADROOM_BYTES:
        raise RuntimeError(
            f"not enough free disk space in {home} to {what}: {_mb(free)} free, about "
            f"{_mb(needed + HEADROOM_BYTES)} needed. Free some space, or choose another data "
            "folder (SNOW_DOCS_HOME)"
        )


def _download(
    url: str,
    part: Path,
    on_progress: Callable[[int, int | None], None],
    max_bytes: int | None = None,
) -> None:
    """Download `url` into `part`, resuming from its current size. Retries on drops."""
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        have = part.stat().st_size if part.exists() else 0
        if max_bytes is not None and have > max_bytes:
            part.unlink()
            have = 0
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if have and resp.status != 206:
                    have = 0  # server ignored the Range: start over
                length = resp.headers.get("Content-Length")
                total = have + int(length) if length and length.isdigit() else max_bytes
                with part.open("ab" if have else "wb") as f:
                    while True:
                        block = resp.read(CHUNK_BYTES)
                        if not block:
                            break
                        f.write(block)
                        have += len(block)
                        if max_bytes is not None and have > max_bytes:
                            raise RuntimeError(
                                "the download is larger than the docs index should be; a "
                                "proxy or Wi-Fi login page may be in the way"
                            )
                        on_progress(have, total)
                if total is not None and have < total:
                    raise ConnectionError(f"connection closed at {have} of {total} bytes")
                return
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:
                return  # nothing left to fetch; the checks decide if it is whole
            if 400 <= e.code < 500:
                raise RuntimeError(
                    f"download refused by the server (HTTP {e.code}) for {url}"
                ) from e
            last_error = e
        except (OSError, http.client.HTTPException) as e:  # URLError, timeouts, resets,
            # and IncompleteRead when the connection drops mid-body
            last_error = e
        wait = min(30.0, RETRY_BASE_SECONDS * 2 ** (attempt - 1))
        logger.warning(
            "setup: download attempt %d failed (%s); retrying in %.0fs", attempt, last_error, wait
        )
        if attempt < DOWNLOAD_ATTEMPTS:
            time.sleep(wait)
    raise RuntimeError(f"download kept failing ({last_error})")


def _sha256(path: Path, on_progress: Callable[[float], None]) -> str:
    size = max(1, path.stat().st_size)
    h, done = hashlib.sha256(), 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * CHUNK_BYTES), b""):
            h.update(block)
            done += len(block)
            on_progress(done / size)
    return h.hexdigest()


def _install(entry: IndexEntry) -> None:
    """Download, verify and unpack `entry`. The caller holds the file lock."""
    home = config.data_home()
    release = entry.release
    # Leftovers of an unpack that was killed (e.g. Claude quit mid-unpack). Safe to delete:
    # we hold the lock, so no other process is unpacking right now.
    for stale in home.glob(".index-*.part"):
        with contextlib.suppress(OSError):
            stale.unlink()

    part = config.gz_part_file(entry)
    have = part.stat().st_size if part.exists() else 0
    _require_free(
        home,
        max(0, (entry.gz_bytes or FALLBACK_GZ_BYTES) - have)
        + (entry.db_bytes or FALLBACK_DB_BYTES),
        f"download the {release} docs index",
    )
    label = f"{release} docs index ({entry.snapshot})"

    def dl_progress(got: int, total: int | None) -> None:
        if total:
            _set(
                release,
                "downloading",
                f"Downloading the {label}: {_mb(got)} of {_mb(total)} ({got / total:.0%}).",
                got / total,
            )
        else:
            _set(release, "downloading", f"Downloading the {label}: {_mb(got)} so far.")

    for _round in range(2):
        resumed = part.exists() and part.stat().st_size > 0
        _set(release, "downloading", f"Downloading the {label}.")
        _download(entry.url, part, dl_progress, max_bytes=entry.gz_bytes)
        size = part.stat().st_size
        if entry.gz_bytes is not None and size != entry.gz_bytes:
            part.unlink(missing_ok=True)
            raise RuntimeError(
                f"the download was not the docs index ({_mb(size)} instead of "
                f"{_mb(entry.gz_bytes)}); a proxy or Wi-Fi login page may be in the way"
            )
        _set(release, "verifying", f"Checking the downloaded {label}.")
        gz_sha = _sha256(part, lambda p: _set(release, "verifying", f"Checking the {label}.", p))
        if gz_sha == entry.gz_sha256:
            break
        part.unlink(missing_ok=True)
        if not resumed:
            raise FatalSetupError(
                f"the published {release} docs index does not match what this version of the "
                "server expects (checksum mismatch). Update the plugin/extension, or tell "
                "whoever shared it"
            )
        # A resumed file can be corrupt from an earlier interruption: retry once from scratch.

    _set(release, "unpacking", f"Unpacking the {label}.")
    _require_free(home, entry.db_bytes or FALLBACK_DB_BYTES, f"unpack the {release} docs index")
    db = config.index_file(entry)
    fd, tmp_name = tempfile.mkstemp(prefix=f".index-{release}-", suffix=".part", dir=home)
    tmp = Path(tmp_name)
    try:
        h, written = hashlib.sha256(), 0
        total = max(1, part.stat().st_size)
        with os.fdopen(fd, "wb") as dst, part.open("rb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="rb") as src:
                for block in iter(lambda: src.read(8 * CHUNK_BYTES), b""):
                    dst.write(block)
                    h.update(block)
                    written += len(block)
                    _set(release, "unpacking", f"Unpacking the {label}.", raw.tell() / total)
            dst.flush()
            os.fsync(dst.fileno())
        db_sha = h.hexdigest()
        if entry.db_sha256 and db_sha != entry.db_sha256:
            part.unlink(missing_ok=True)  # its checksum matched, so re-unpacking cannot help
            raise FatalSetupError(
                f"the unpacked {release} docs index does not match what this version of the "
                "server expects (checksum mismatch). Update the plugin/extension"
            )
        os.replace(tmp, db)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _write_marker(entry, gz_sha, db_sha, written)
    part.unlink(missing_ok=True)


def _write_marker(entry: IndexEntry, gz_sha: str, db_sha: str, db_bytes: int) -> None:
    marker = config.marker_file(entry)
    tmp = marker.with_suffix(".ok.tmp")
    tmp.write_text(
        json.dumps(
            {
                "release": entry.release,
                "snapshot": entry.snapshot,
                "gz_sha256": gz_sha,
                "db_sha256": db_sha,
                "db_bytes": db_bytes,
                "min_server_version": entry.min_server_version,
                "installed_at": time.time(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, marker)


# --- housekeeping (only under the file lock; skipped when another app holds it) ---------------

_LEGACY_INDEX = re.compile(r"index-\d{4}-\d{2}-\d{2}\.db", re.ASCII)
_PART_FILE = re.compile(
    r"index-(?P<key>[a-z]+-\d{4}-\d{2}-\d{2}-[0-9a-f]{12})\.db\.gz\.part", re.ASCII
)


def _delete_index(path: Path) -> bool:
    """Delete an index file, then its marker. If the file is in use (Windows), keep the
    marker so the next start sees it and tries again."""
    store.forget(path)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False
    with contextlib.suppress(OSError):
        path.with_suffix(".ok").unlink(missing_ok=True)
    return True


def legacy_files() -> list[Path]:
    """Index files of the first version (`index-<date>.db`), which this version never
    deletes: that version may still be installed and using them."""
    return sorted(p for p in config.data_home().glob("index-*.db") if _LEGACY_INDEX.fullmatch(p.name))


def _migrate_legacy(home: Path) -> None:
    """Adopt a first-version `index-<date>.db` under its content-addressed name with a hard
    link: no re-download, no extra disk space, and the old version keeps its file. Any
    problem (a file in use, a disk without hard links) just means a normal download."""
    known = [e for e in config.BUILTIN_ENTRIES.values()]
    with _state_lock:
        known += list(_latest.values())
    for db in legacy_files():
        try:
            try:
                raw = db.with_suffix(".ok").read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                continue
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"gz_sha256": raw}
            gz_sha = str(data.get("gz_sha256", "")) if isinstance(data, dict) else ""
            match = next((e for e in known if gz_sha and e.gz_sha256 == gz_sha), None)
            if match is None or config.marker_file(match).exists():
                continue
            size = db.stat().st_size
            if match.db_bytes is not None and match.db_bytes != size:
                continue
            target = config.index_file(match)
            target.unlink(missing_ok=True)  # an orphan without a marker
            os.link(db, target)
            _write_marker(match, gz_sha, match.db_sha256, size)
            logger.info("setup: adopted the existing %s index (no download)", match.key)
        except OSError as e:
            logger.warning("setup: could not adopt %s (%s); downloading instead", db.name, e)


def _sweep(release: str, keep_part_keys: set[str]) -> None:
    """Remove leftovers: unpack temps, orphaned index files without a valid marker, marker
    and latest.json temps, and partial downloads nobody is known to want."""
    home = config.data_home()
    for stale in [*home.glob(".index-*.part"), *home.glob("index-*.ok.tmp")]:
        with contextlib.suppress(OSError):
            stale.unlink()
    now = time.time()
    for stale in home.glob(".latest-*.tmp"):  # another process may be writing one right now
        with contextlib.suppress(OSError):
            if now - stale.stat().st_mtime > 3600:
                stale.unlink()
    valid = {i.db_path.name for i in _scan(release)}
    for db in home.glob(f"index-{release}-*.db"):
        if db.name not in valid and _INDEX_FILE.fullmatch(db.with_suffix(".ok").name):
            _delete_index(db)
    for part in home.glob(f"index-{release}-*.db.gz.part"):
        m = _PART_FILE.fullmatch(part.name)
        if not m or m.group("key") in keep_part_keys:
            continue
        with contextlib.suppress(OSError):  # e.g. another server version's paused download
            if now - part.stat().st_mtime > PART_MAX_AGE_SECONDS:
                part.unlink()


def _wanted_keys(release: str) -> set[str]:
    """Every index key a server sharing this folder may be installing: latest.json's
    (whatever its format) and the built-in one, with and without testing overrides."""
    entries = [config.BUILTIN_ENTRIES.get(release)]
    with _state_lock:
        entries.append(_latest.get(release))
    keys = set()
    for e in entries:
        if e is not None:
            keys |= {e.key, config.with_overrides(e).key}
    return keys


def _cleanup(release: str) -> None:
    """Delete this release's indexes that no server sharing the folder needs any more.

    Only with a latest.json view (live or saved): without one this process can't tell a
    rollback from an outdated index. Only indexes this server can read: newer formats are
    the newer server's business. Kept: the active one, the one latest.json names, anything
    newer, and the newest index of every other min_server_version (an older server's).
    """
    with _state_lock:
        named = _latest.get(release)
    act = active_installed(release)
    if named is None or act is None:
        return
    everything = _scan(release)
    keep = {act.key, named.key, config.with_overrides(named).key}
    keep |= {i.key for i in everything if i.snapshot > act.snapshot}
    seen_versions = {act.min_server_version}
    for i in everything:  # newest first
        if i.min_server_version not in seen_versions:
            keep.add(i.key)
            seen_versions.add(i.min_server_version)
    for i in everything:
        if i.key not in keep and _compatible_version(i.min_server_version):
            _delete_index(i.db_path)


# --- remembered failures ----------------------------------------------------------------------


def _bad_file(entry: IndexEntry) -> Path:
    return config.data_home() / f"index-{entry.key}.bad"


def _identity(entry: IndexEntry) -> tuple[str, str, str]:
    return (entry.url, entry.gz_sha256, entry.db_sha256)


def _is_bad(entry: IndexEntry) -> bool:
    """A fatal checksum failure is remembered on disk for a day, so new server processes
    (one per Claude Code session) don't download it again meanwhile. A corrected entry
    (different url or checksums) is tried at once; the same one again after a day (the
    maintainer may have re-uploaded the file)."""
    now = time.time()
    with _state_lock:
        at = _bad_memory.get(_identity(entry))
    if at is not None and now - at < BAD_RETRY_SECONDS:
        return True
    bad = _bad_file(entry)
    data = _read_marker(bad)
    if not data or tuple(data.get(k) for k in ("url", "gz_sha256", "db_sha256")) != _identity(
        entry
    ):
        return False
    try:
        return now - bad.stat().st_mtime < BAD_RETRY_SECONDS
    except OSError:
        return False


def _remember_bad(entry: IndexEntry, reason: str) -> None:
    with _state_lock:
        _bad_memory[_identity(entry)] = time.time()
    url, gz_sha, db_sha = _identity(entry)
    with contextlib.suppress(OSError):
        _bad_file(entry).write_text(
            json.dumps({"url": url, "gz_sha256": gz_sha, "db_sha256": db_sha, "reason": reason}),
            encoding="utf-8",
        )


def _forget_bad(entry: IndexEntry) -> None:
    with _state_lock:
        _bad_memory.pop(_identity(entry), None)
    with contextlib.suppress(OSError):
        _bad_file(entry).unlink(missing_ok=True)


def _ensure_models(release: str) -> None:
    if models_on_disk():
        _set("models", "ready", "Search models are on disk.", 1.0)
        return
    _set("models", "downloading", "Downloading the search models (one-time, about 1.2 GB).")
    _set(release, "downloading", "Downloading the search models (one-time, about 1.2 GB).")
    try:
        with _file_lock(release):
            if not models_on_disk():
                _require_free(config.data_home(), MODELS_BYTES, "download the search models")
                models.warm_up()
        if not models_on_disk():
            raise RuntimeError("the search models did not download completely")
    except Exception as e:
        _set("models", "error", f"The search models could not be downloaded: {e}")
        raise
    _set("models", "ready", "Search models are on disk.", 1.0)


# --- orchestration ---------------------------------------------------------------------------


def _needs_install(release: str, entry: IndexEntry) -> bool:
    inst = installed(release)
    if any(i.key == entry.key for i in inst):
        return False
    if _authoritative_entry(release) is not None:
        return True  # latest.json decides (it may also roll back)
    # The built-in entry only fills in when nothing at least as new is installed (a
    # same-date rebuild from latest.json counts: never replace it with the older build).
    return not any(i.snapshot >= entry.snapshot for i in inst)


def _fallback_entry(release: str, failed: IndexEntry) -> IndexEntry | None:
    """The built-in index, when latest.json's failed and nothing else is installed."""
    builtin = config.BUILTIN_ENTRIES.get(release)
    if builtin is None:
        return None
    builtin = config.with_overrides(builtin)
    if builtin.key == failed.key or _is_bad(builtin) or installed(release):
        return None
    return builtin


def _install_remembering_failure(release: str, entry: IndexEntry) -> FatalSetupError | None:
    """Install `entry` under the lock; a fatal checksum failure is returned (and
    remembered), anything else raises."""
    with _file_lock(release):
        if any(i.key == entry.key for i in installed(release)):
            return None
        try:
            _install(entry)
        except FatalSetupError as e:
            _remember_bad(entry, str(e))
            return e
    _forget_bad(entry)
    return None


def ensure(release: str, *, with_models: bool = True) -> SetupStatus:
    """Bring `release` up to date (index + models) in the calling thread. Never raises."""
    try:
        refresh_latest()
        entry = target_entry(release)
        with _lock_if_free() as locked:
            if locked:
                _migrate_legacy(config.data_home())
                _sweep(release, _wanted_keys(release))
        if entry is None:
            newer = _incompatible_entry(release)
            if index_ready(release):
                _set(release, "ready", "Ready.", 1.0)
            elif newer is not None:
                _set(
                    release,
                    "unavailable",
                    f"The {release} docs index needs server {newer.min_server_version} or "
                    "newer. Update the plugin/extension to get it.",
                )
            else:
                _set(
                    release,
                    "unavailable",
                    f"No {release} docs index has been published yet. It will be picked up "
                    "automatically once it is (checked daily).",
                )
            return status(release)
        failure: FatalSetupError | None = None
        if _needs_install(release, entry):
            if _is_bad(entry):
                failure = FatalSetupError(
                    f"the published {release} docs index failed its checksum before; update "
                    "the plugin/extension, or tell whoever shared it"
                )
            else:
                failure = _install_remembering_failure(release, entry)
            fallback = _fallback_entry(release, entry) if failure else None
            if fallback is not None:
                _install_remembering_failure(release, fallback)
        # A failure above still leaves the installed index usable: tidy up and make sure
        # the models are there, then report it.
        with _lock_if_free() as locked:
            if locked:
                _cleanup(release)
        if with_models:
            _ensure_models(release)
        if failure is not None:
            raise failure
        _set(release, "ready", "Ready.", 1.0)
    except Exception as e:  # setup reports, never crashes the server
        fatal = isinstance(e, FatalSetupError)
        with _state_lock:
            _last_error_at[release] = time.monotonic()
        logger.exception("setup[%s] failed", release)
        retry = (
            "It won't try that download again for a day."
            if fatal
            else "It retries the next time it's used."
        )
        if search_ready(release):
            retry += " Searches keep using the docs index already installed."
        if "DLL load failed" in str(e):
            retry += (
                " On Windows this usually means the Microsoft Visual C++ Redistributable is "
                "missing: https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
        _set(release, "error", f"Setup failed: {e}. {retry} Help: {config.README_URL}")
    return status(release)


def request(release: str) -> None:
    """Queue `release` for the background worker (install, update, models). Non-blocking;
    rate-limited after errors; a download that failed its checksum waits a day (a
    corrected entry in latest.json is tried at once)."""
    global _worker
    with _state_lock:
        st = _status.get(release)
        if st and st.state == "error":
            entry = target_entry(release)
            if entry and _needs_install(release, entry) and _is_bad(entry):
                return
            if time.monotonic() - _last_error_at.get(release, 0.0) < RETRY_AFTER_ERROR_SECONDS:
                return
        if release in _pending:
            return
        if (st is None or st.state == "idle") and not index_ready(release):
            if _pending:  # the worker is busy with another release
                _set(release, "queued", "Queued; starts as soon as the current download finishes.")
            else:
                _set(release, "queued", "Starting.")
        _pending.add(release)
        _queue.put(release)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name="snow-docs-setup", daemon=True)
            _worker.start()


def _work() -> None:
    q = _queue
    while True:
        release = q.get()
        try:
            ensure(release)
        finally:
            with _state_lock:
                _pending.discard(release)


def start() -> None:
    """Called when a client connects: set up the default release, keep installed ones
    fresh, and check for updates daily while the server runs."""
    global _updater
    releases = {config.default_release()} | {r for r in config.RELEASES if index_ready(r)}
    for release in sorted(releases):
        request(release)
    with _state_lock:
        if _updater is None or not _updater.is_alive():
            _updater = threading.Thread(target=_update_loop, name="snow-docs-updates", daemon=True)
            _updater.start()


def _update_loop() -> None:
    while True:
        time.sleep(UPDATE_INTERVAL_SECONDS)
        refresh_latest(force=True)
        for release in config.RELEASES:
            if index_ready(release) or status(release).state == "error":
                request(release)


def _reset_for_tests() -> None:
    global _worker, _updater, _latest_checked_at, _latest_ok, _update_note, _queue, _models
    global _cache_mtime
    with _state_lock:
        _status.clear()
        _models = SetupStatus("idle", "")
        _latest.clear()
        _latest_checked_at = None
        _latest_ok = False
        _update_note = ""
        _cache_mtime = None
        _last_error_at.clear()
        _bad_memory.clear()
        _last_logged.clear()
        _pending.clear()
        _queue = queue.Queue()
        _worker = None
        _updater = None
