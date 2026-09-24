"""PKG-03 / D-05 — the clean-room boundary, enforced statically on every nested-suite run.

Walks every `.py` under this project and fails on any route back into the research spike:
a direct import, a dynamic import, a `sys.path` mutation, or a string literal naming a path
inside this repo. The scan is AST-based rather than substring-based, so prose in a comment or
a docstring cannot trip it and a cleverly formatted import cannot hide from it.

The ban is a PREFIX (`docs_rag_`), never a list of package names. D-05 is explicit about why:
the spike currently ships 11 `docs_rag_*` distributions and will grow more, and a denylist is a
maintenance burden that silently stops covering the package added after it was written. The
complementary "no spike distribution in the resolved closure" check lives in `test_isolation.py`
as an assertion over `uv.lock`; together they cover both the source and the dependency route.

LITERAL_CHECK_EXEMPT — the self-trip trap, resolved narrowly. This module and `test_extraction.py`
must CONTAIN repo-path literals as fixture and assertion data: the mutation payload below carries
an absolute `docs-rag-frontier` path so the guard can be proven to bite, and the extraction test
greps the extracted `sys.path` for this repo's directory name. Exempting exactly those two files
from the `ast.Constant` repo-path rule — and from nothing else — is the narrowest correct scope.
The import, `sys.path` and dynamic-import rules still apply to them in full, and a test below
asserts the exemption set never grows beyond those two filenames.

This guard needs no eval.db, no index, no network and no model download: it is always on.
"""

from __future__ import annotations

import ast
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

# The whole denylist, and it has one entry. Covers all 11 current docs_rag_* packages plus any
# future one, exactly as D-05 requires.
BANNED_PREFIX = "docs_rag_"

# String literals that reach into this repo's tree. A path literal is how a `sys.path` hack or a
# hardcoded corpus path smuggles the spike back in without an import statement.
REPO_PATH_FRAGMENTS = ("src/docs_rag", "docs-rag-frontier", "docs-rag-mcp")

SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}

# Exactly two modules, frozen and asserted below. See the module docstring for the rationale.
LITERAL_CHECK_EXEMPT = frozenset({"test_no_spike_imports.py", "test_extraction.py"})

_RULE = (
    "nothing in this project may import from, path-hack into, or name a path inside the "
    "research spike"
)
_REASON = (
    "one convenience import recouples an extractable package to an 11-package monorepo "
    "carrying torch and anthropic, and extraction-by-directory-copy stops working"
)


def _violations(path: pathlib.Path) -> list[str]:
    """Every clean-room violation in `path`, as `file:lineno: description` strings.

    The `ast.Constant` repo-path-literal rule is suppressed for the two modules in
    `LITERAL_CHECK_EXEMPT`, which need such literals as their own fixture/assertion data. All
    other rules apply to every file without exception.
    """
    check_literals = path.name not in LITERAL_CHECK_EXEMPT
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0].startswith(BANNED_PREFIX):
                    out.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import — intra-package, cannot reach outside this distribution.
                continue
            mod = node.module or ""
            if mod.split(".")[0].startswith(BANNED_PREFIX):
                out.append(f"{path}:{node.lineno}: from {mod} import ...")
        elif isinstance(node, ast.Call):
            fn = node.func
            # Match the sys -> .path -> .append/.insert/.extend attribute chain, NOT the
            # substring "sys.path": a local variable named `path` with an `append` method is
            # commonplace and must not be flagged.
            if (
                isinstance(fn, ast.Attribute)
                and fn.attr in {"append", "insert", "extend"}
                and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "path"
                and isinstance(fn.value.value, ast.Name)
                and fn.value.value.id == "sys"
            ):
                out.append(f"{path}:{node.lineno}: sys.path.{fn.attr}(...)")
            dynamic = (isinstance(fn, ast.Attribute) and fn.attr == "import_module") or (
                isinstance(fn, ast.Name) and fn.id == "__import__"
            )
            if dynamic:
                for arg in node.args:
                    if (
                        isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and arg.value.split(".")[0].startswith(BANNED_PREFIX)
                    ):
                        out.append(f"{path}:{node.lineno}: dynamic import {arg.value!r}")
        elif check_literals and isinstance(node, ast.Constant) and isinstance(node.value, str):
            for frag in REPO_PATH_FRAGMENTS:
                if frag in node.value:
                    out.append(f"{path}:{node.lineno}: repo path literal {node.value!r}")
    return out


def _iter_py(root: pathlib.Path):
    """Every `.py` under `root` in sorted order, skipping virtualenv and cache trees."""
    for p in sorted(root.rglob("*.py")):
        if not SKIP_DIRS.intersection(p.parts):
            yield p


def test_no_spike_imports() -> None:
    """D-05 / PKG-03 — no module in this project routes back into the research spike.

    Failure mode prevented: the clean room is only real while it is machine-enforced. A single
    `from docs_rag_eval import ...` added for convenience would make this directory unextractable
    while every other test stayed green, and nothing else in the suite would notice.
    """
    scanned = list(_iter_py(PROJECT_ROOT))
    assert scanned, (
        f"the guard scanned zero .py files under {PROJECT_ROOT} — a guard with nothing to scan "
        "passes vacuously; check PROJECT_ROOT and SKIP_DIRS"
    )
    found = [v for p in scanned for v in _violations(p)]
    assert not found, (
        "clean-room boundary violated:\n"
        + "\n".join(found)
        + f"\n\nRule: {_RULE}.\nReason: {_REASON}."
    )


def test_guard_is_not_vacuous(tmp_path) -> None:
    """D-05 / PKG-03 — mutation sanity: the guard bites on all six known evasion shapes.

    Failure mode prevented: a scanner that never fires. Phase 16's rule is "mutation-test guards
    or you have a guess" — without this control, `test_no_spike_imports` above would pass just as
    happily if `_violations` returned an empty list unconditionally.
    """
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import sys\n"
        'sys.path.insert(0, "/Users/x/projects/docs-rag-frontier/src")\n'
        "import docs_rag_ctx\n"
        "from docs_rag_eval.qrels import load\n"
        "import importlib\n"
        'importlib.import_module("docs_rag_synth")\n'
        '__import__("docs_rag_graph")\n',
        encoding="utf-8",
    )
    found = _violations(bad)
    assert len(found) >= 6, f"expected at least 6 findings from the mutation payload, got: {found}"
    assert any("sys.path.insert" in f for f in found), found
    assert any("docs_rag_ctx" in f for f in found), found
    assert any("repo path literal" in f for f in found), found


def test_guard_allows_relative_imports(tmp_path) -> None:
    """D-05 / PKG-03 — false-positive control: legitimate imports produce no findings.

    Failure mode prevented: a guard so broad it has to be switched off. `from . import sibling`
    is intra-package and can never reach the spike (hence the `node.level` skip), and
    `from mcp.server import ...` is this project's own SDK. If either were flagged, the first
    real module in Phase 18 would force someone to weaken the rule.
    """
    ok = tmp_path / "ok.py"
    ok.write_text(
        "from . import sibling\nfrom mcp.server import MCPServer\n",
        encoding="utf-8",
    )
    assert _violations(ok) == []


def test_literal_exemption_is_exactly_the_two_guard_modules() -> None:
    """D-05 / PKG-03 — the literal-rule exemption cannot grow into a general escape hatch.

    Failure mode prevented: someone hits the repo-path-literal rule in a real module and "fixes"
    it by adding that module's filename here. Only the two guard modules may carry repo-path
    literals, because carrying them is what they are for; every other module must not.
    """
    assert LITERAL_CHECK_EXEMPT == frozenset({"test_no_spike_imports.py", "test_extraction.py"}), (
        "LITERAL_CHECK_EXEMPT must stay exactly {test_no_spike_imports.py, test_extraction.py} — "
        "these two modules need repo-path literals as fixture and assertion data; any other "
        "module carrying one is a real boundary violation, not an exemption candidate"
    )
