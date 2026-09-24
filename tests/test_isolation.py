"""PKG-01 — this project is self-contained and its own uv workspace root.

Extraction is a directory copy and nothing else, so every property that makes the copy work
has to live inside this directory. These guards read the on-disk `pyproject.toml`, `uv.lock`
and `.gitignore` as text and state, in each failure message, both the rule and the consequence
of breaking it.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PYPROJECT_TEXT = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_pyproject_declares_an_empty_uv_workspace() -> None:
    """D-10 / PKG-01 — the nested project must be its own uv workspace root.

    Without this table a future `[tool.uv.workspace] members = ["servers/*"]` at the repo root
    silently absorbs this project: one lockfile at the root, one shared venv, one intersected
    `requires-python`. The isolation would be gone with no error to notice.
    """
    assert "[tool.uv.workspace]" in PYPROJECT_TEXT, (
        "pyproject.toml must declare [tool.uv.workspace] — without it a root workspace glob "
        "absorbs this project into the root lock and the extraction contract is broken"
    )
    assert "members = []" in PYPROJECT_TEXT, (
        "[tool.uv.workspace] members must be [] — a non-empty members list would make this "
        "project a workspace parent and re-entangle its resolution with other directories"
    )


def test_pyproject_pins_the_sdk_major_and_a_python_ceiling() -> None:
    """PKG-01 — the dependency contract is bounded on both sides.

    `mcp` 1.x and 2.x cannot share a process (1.x's `mcp.server.fastmcp` is gone in 2.x), so the
    range is what keeps this server and the surrounding research repo apart. The Python ceiling
    is load-bearing too: with a bare ">=3.11" uv resolves against CPython 3.14.
    """
    assert '"mcp>=2.0,<3"' in PYPROJECT_TEXT, (
        'the mcp dependency must be pinned to "mcp>=2.0,<3" — an unbounded floor lets a '
        "re-resolve cross a major boundary and break every import in this package"
    )
    assert 'requires-python = ">=3.11,<3.14"' in PYPROJECT_TEXT, (
        'requires-python must be ">=3.11,<3.14" — without the ceiling uv selects CPython 3.14, '
        "which is not the interpreter this server is developed or tested against"
    )


def test_pyproject_registers_one_console_script_that_exists() -> None:
    """D-08 — exactly one entry point, and its module is real.

    A dangling entry point installs a command that raises ModuleNotFoundError on first use.
    `snow-docs-build` is registered in Phase 19, together with the module it points at.
    """
    assert 'snow-docs-mcp = "snow_docs_mcp.server:main"' in PYPROJECT_TEXT, (
        "the snow-docs-mcp console script must point at snow_docs_mcp.server:main — it is the "
        "stdio entry point MCP clients launch as a subprocess"
    )
    assert "snow-docs-build" not in PYPROJECT_TEXT, (
        "snow-docs-build must not be registered before Phase 19 writes its module — a dangling "
        "entry point is a command that fails the moment a user runs it"
    )


def test_pyproject_carries_its_own_packaging_and_tooling_config() -> None:
    """D-10 — lint/test/build config travels with the directory copy.

    If these live only at the repo root, the extracted copy lints and tests differently from
    the way it was developed, and a built wheel silently omits the package.
    """
    for needle, consequence in (
        (
            'packages = ["src/snow_docs_mcp"]',
            "an unlisted package is silently omitted from the built wheel",
        ),
        ("line-length = 100", "the extracted copy would lint at a different width"),
        ('target-version = "py311"', "the extracted copy would lint against a different Python"),
        ('testpaths = ["tests"]', "a bare `pytest` in the copy would collect the wrong tree"),
    ):
        assert needle in PYPROJECT_TEXT, (
            f"pyproject.toml must contain {needle!r} — otherwise {consequence}"
        )


def test_the_lockfile_landed_in_this_directory() -> None:
    """PKG-01 — the lock is resolved HERE, not in a parent.

    A lock written to the parent means uv treated this project as a workspace member, so the
    copy would ship without a lockfile and `uv sync --frozen` in the extraction test would fail.
    """
    lock_path = PROJECT_ROOT / "uv.lock"
    assert lock_path.exists(), (
        f"{lock_path} must exist — if uv wrote the lock to a parent directory this project was "
        "absorbed into another workspace and is no longer independently resolvable"
    )
    lock_text = lock_path.read_text(encoding="utf-8")
    assert 'name = "servicenow-docs-mcp"' in lock_text, (
        "the lock must name this distribution — a lock that does not describe this project is "
        "a parent's lock that happens to sit here"
    )


def test_the_lock_closure_carries_no_spike_or_paid_api_packages() -> None:
    """PKG-01 / T-17-01 — the dependency closure is clean-room.

    Cheaper and stronger than widening the AST import guard: if a research-spike distribution or
    a paid-API SDK ever enters the resolved closure, it shows up here as a named package long
    before any code imports it.
    """
    lock_text = (PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8")
    assert "docs_rag" not in lock_text, (
        "the nested lock must name no docs_rag distribution — depending on the research spike "
        "would recouple this server to an 11-package monorepo and break extraction by copy"
    )
    assert 'name = "anthropic"' not in lock_text, (
        "the nested lock must not carry the anthropic SDK — this project is zero-paid-API by "
        "constraint, and a transitive pull would be the first way that silently changes"
    )


def test_gitignore_travels_with_the_copy() -> None:
    """D-10 / PKG-01 — ignore rules are part of the extractable directory.

    The repo root already ignores `.venv` at any depth, so this file changes nothing today; it
    exists so the extracted copy does not commit its virtualenv on first `git init`.
    """
    gitignore = PROJECT_ROOT / ".gitignore"
    assert gitignore.exists(), (
        f"{gitignore} must exist — without it the extracted copy has no ignore rules of its own"
    )
    assert ".venv/" in gitignore.read_text(encoding="utf-8"), (
        ".gitignore must ignore .venv/ — otherwise the extracted copy would track its own "
        "virtualenv, which is machine-specific and hundreds of megabytes"
    )
