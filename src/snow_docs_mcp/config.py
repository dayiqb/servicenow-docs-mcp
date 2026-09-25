"""Where the server keeps its data, and which docs indexes exist.

Everything heavy lives in one data folder, shared by every Claude app on the machine that
runs this server (the plugin, the Claude Desktop extension and any Claude Code install all
use the same files, so each index downloads once):

    <data folder>/
        index-<release>-<snapshot>-<sha12>.db    one docs index (read-only SQLite)
        index-<release>-<snapshot>-<sha12>.ok    marker: fully downloaded and verified
        models/                                  embedder + reranker cache
        .setup.lock                              OS-level lock held while downloading

There is one index per ServiceNow release (australia, brazil). New snapshots are listed in
`index/latest.json` on the project's GitHub repo; the server checks it daily and installs
newer ones in the background (see setup.py). Each server version also carries a built-in
entry, so a first run works even if latest.json cannot be reached.

Configuration (env vars):
    SNOW_DOCS_HOME          Data folder. Default: ~/.servicenow-docs-mcp
    SNOW_DOCS_RELEASE       Default release for searches: australia (default) or brazil.
    SNOW_DOCS_LATEST_URL    Where to read latest.json. "off" disables update checks.
    SNOW_DOCS_INDEX_URL     Testing / pre-release: download every index from this URL instead.
    SNOW_DOCS_INDEX_SHA256  ... and expect this sha256 of the gzipped download.
    SNOW_DOCS_INDEX_DB_SHA256
                            ... and (optionally) this sha256 of the unpacked index.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)

VERSION = "0.1.2"
RELEASES = ("australia", "brazil")
DEFAULT_RELEASE = "australia"

REPO = "dayiqb/servicenow-docs-mcp"
LATEST_URL = f"https://raw.githubusercontent.com/{REPO}/main/index/latest.json"
README_URL = f"https://github.com/{REPO}#troubleshooting"


@dataclass(frozen=True)
class IndexEntry:
    """One downloadable docs index, as listed in latest.json."""

    release: str
    snapshot: str  # YYYY-MM-DD of the docs commit
    corpus_commit: str
    url: str
    gz_sha256: str
    gz_bytes: int | None
    db_sha256: str
    db_bytes: int | None
    chunks: int | None = None
    context_lines: int | None = None
    min_server_version: str = "0.1.0"

    @property
    def key(self) -> str:
        return f"{self.release}-{self.snapshot}-{self.gz_sha256[:12]}"

    @classmethod
    def from_json(cls, release: str, raw: object) -> IndexEntry:
        if not isinstance(raw, dict):
            raise TypeError("entry is not an object")
        snapshot = str(raw["snapshot"])
        gz_sha = str(raw["gz_sha256"]).lower()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot, re.ASCII):
            raise ValueError(f"bad snapshot {snapshot!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", gz_sha, re.ASCII):
            raise ValueError("bad gz_sha256")
        url = str(raw["url"])
        if not (
            url.startswith("https://") or re.match(r"http://(127\.0\.0\.1|localhost)[:/]", url)
        ):
            raise ValueError("url must be https (plain http only for localhost, for tests)")

        def opt_int(name: str) -> int | None:
            value = raw.get(name)
            return value if isinstance(value, int) and value > 0 else None

        return cls(
            release=release,
            snapshot=snapshot,
            corpus_commit=str(raw.get("corpus_commit", "")),
            url=url,
            gz_sha256=gz_sha,
            gz_bytes=opt_int("gz_bytes"),
            db_sha256=str(raw.get("db_sha256", "")).lower(),
            db_bytes=opt_int("db_bytes"),
            chunks=opt_int("chunks"),
            context_lines=opt_int("context_lines"),
            min_server_version=str(raw.get("min_server_version", "0.1.0")),
        )


# The index this version ships with: the measured contextual-retrieval index (ServiceNowDocs
# "australia" as of 2026-05-15; +.0811 nDCG@10 over plain hybrid search). latest.json
# supersedes it with fresher snapshots.
BUILTIN_ENTRIES: dict[str, IndexEntry] = {
    "australia": IndexEntry(
        release="australia",
        snapshot="2026-05-15",
        corpus_commit="0ba98cdaf706821d72ff79e92b18adc057e60e29",
        url=(
            f"https://github.com/{REPO}/releases/download/index-australia-2026-05-15/"
            "servicenow-docs-index-australia-2026-05-15-04e38491fd4b.db.gz"
        ),
        gz_sha256="04e38491fd4be3d1ee8d05766e330d498f12bc252ff27afa47cc016c61e80774",
        gz_bytes=545_850_628,
        db_sha256="0a310a2f54e8b47bb5e8297e77a53887185632431171a37325da7e61c4134386",
        db_bytes=1_348_288_512,
        chunks=253_589,
        context_lines=253_589,
    ),
}

DEFAULT_HOME = Path.home() / ".servicenow-docs-mcp"


def data_home() -> Path:
    """The data folder, created on first use.

    SNOW_DOCS_HOME may arrive with unexpanded variables: Claude Desktop passes a manifest
    default like "${HOME}/.servicenow-docs-mcp" through verbatim, and an unset setting can
    arrive as the literal "${user_config.data_folder}". `$VAR`/`${VAR}`/`~` are expanded
    here; anything still unresolved, blank or relative falls back to the default (a relative
    path would land in whatever folder the host happened to start the server in).
    """
    raw = os.environ.get("SNOW_DOCS_HOME", "").strip()
    home = DEFAULT_HOME
    if raw:
        expanded = Path(os.path.expanduser(os.path.expandvars(raw)))
        if "$" not in str(expanded) and expanded.is_absolute():
            home = expanded
        else:
            logger.warning(
                "SNOW_DOCS_HOME=%r is not a usable absolute folder; using %s", raw, DEFAULT_HOME
            )
    home.mkdir(parents=True, exist_ok=True)
    return home


def default_release() -> str:
    raw = os.environ.get("SNOW_DOCS_RELEASE", "").strip().lower()
    return raw if raw in RELEASES else DEFAULT_RELEASE


def normalize_release(value: str | None) -> str | None:
    """A valid release name, the default for None/blank, or None for an unknown name."""
    if value is None or not str(value).strip():
        return default_release()
    v = str(value).strip().lower()
    return v if v in RELEASES else None


def latest_url() -> str | None:
    raw = os.environ.get("SNOW_DOCS_LATEST_URL", "").strip()
    if raw.lower() in ("off", "none", "0", "false"):
        return None
    return raw or LATEST_URL


def with_overrides(entry: IndexEntry) -> IndexEntry:
    """Apply the SNOW_DOCS_INDEX_* testing overrides, if set."""
    url = os.environ.get("SNOW_DOCS_INDEX_URL", "").strip()
    if not url:
        return entry
    gz = os.environ.get("SNOW_DOCS_INDEX_SHA256", "").strip().lower() or entry.gz_sha256
    db = os.environ.get("SNOW_DOCS_INDEX_DB_SHA256", "").strip().lower()
    return replace(entry, url=url, gz_sha256=gz, db_sha256=db, gz_bytes=None, db_bytes=None)


def index_file(entry: IndexEntry) -> Path:
    return data_home() / f"index-{entry.key}.db"


def marker_file(entry: IndexEntry) -> Path:
    return data_home() / f"index-{entry.key}.ok"


def gz_part_file(entry: IndexEntry) -> Path:
    return data_home() / f"index-{entry.key}.db.gz.part"


def models_dir() -> Path:
    path = data_home() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def version_tuple(v: str) -> tuple[int, ...]:
    parts = []
    for p in v.split("."):
        m = re.match(r"\d+", p)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts)
