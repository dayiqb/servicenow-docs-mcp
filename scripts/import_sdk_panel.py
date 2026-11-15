"""Take the ServiceNow SDK panel into this plugin from its own repository.

    python3 scripts/import_sdk_panel.py <path to a servicenow-sdk-panel checkout>

The panel is developed in a repository of its own, where it also is a plugin by itself. Here
it is one of the panes of the ServiceNow Docs plugin, and a plugin has one hooks module, one
hook for an event, and one name for what it keeps. So the panel's files are taken as they are
at the checkout's last commit, with only what that needs changed:

- its state is kept under this plugin's name;
- what it sets up at the start of a session becomes `start($)`, which this plugin's one
  `session.start` hook calls (hooks/register.tsx);
- its types go into this plugin's contract (types/index.d.ts);
- its pane tests run with the panel's setting on.

Every change is checked: a file that no longer has the text a change expects stops the import
and names it, so nothing is half taken. Run it again to take a newer commit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "panes" / "sdk-panel"
CONTRACT = ROOT / "types" / "index.d.ts"
THEIRS = "servicenow-sdk-panel"
OURS = "servicenow-docs"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def swap(text: str, old: str, new: str, what: str, *, times: int | None = 1) -> str:
    found = text.count(old)
    if found == 0 or (times is not None and found != times):
        sys.exit(f"import stopped: {what}: expected {times or 'some'} of {old!r}, found {found}")
    return text.replace(old, new)


def pane(source: str) -> str:
    """The panel's hooks module as a pane of this plugin."""
    out = swap(source, "from '../core/", "from './core/", "imports of the core", times=None)
    out = swap(out, "from '../types'", "from '../../types'", "the import of its types")
    out = swap(
        out,
        f"{{ plugin: '{THEIRS}', key: ",
        f"{{ plugin: '{OURS}', key: ",
        "the names its state is kept under",
        times=None,
    )
    started = re.compile(
        r"export const register: Register = on => \{\n"
        r"  on\('session\.start', async \(\$, e, next\) => \{\n"
        r"(?P<body>(?:    .*\n)+?)"
        r"\n    return next\(e\)\n  \}\)\n\n"
    )
    found = started.findall(out)
    if len(found) != 1:
        sys.exit(f"import stopped: its session.start hook: expected 1, found {len(found)}")
    body = "".join(line[2:] for line in found[0].splitlines(keepends=True))
    out = started.sub(
        lambda _: (
            "/** What the panel sets up when a session starts. The plugin's one `session.start` "
            "hook calls it. */\n"
            "export async function start($: Engine): Promise<void> {\n"
            f"{body}"
            "}\n\n"
            "export const register: Register = on => {\n"
        ),
        out,
    )
    # The docs are not looked for in this plugin's folder: the plugin starts no docs server, so
    # the folder has no docs environment. The panel finds the Claude Desktop extension itself.
    if "Claude Extensions" not in out:
        sys.exit("import stopped: the pane no longer looks for the Claude Desktop extension")
    if "on('session.start'" in out or THEIRS in re.sub(r"//.*|/\*[\s\S]*?\*/", "", out):
        sys.exit("import stopped: the pane still names its own plugin or its own session.start")
    return out


def pane_tests(source: str) -> str:
    out = swap(source, f"plugin: '{THEIRS}'", f"plugin: '{OURS}'", "the plugin its tests mount")
    tests = len(re.findall(r"^test\(", out, flags=re.MULTILINE))
    out, changed = re.subn(
        r"^(test\((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`), )(async )",
        r"\1{ options: { sdk_panel: true } }, \2",
        out,
        flags=re.MULTILINE,
    )
    if tests == 0 or changed != tests:
        sys.exit(f"import stopped: its pane tests: {tests} tests, {changed} given the setting")
    return out


def contract(theirs: str) -> None:
    """The panel's types, and the names of what it keeps, in this plugin's one contract."""
    declared = re.search(r"\ndeclare module 'claude-code' \{[\s\S]*\}\s*$", theirs)
    kept = re.search(rf"'{THEIRS}': \{{([^}}]*)\}}", theirs)
    if not declared or not kept:
        sys.exit("import stopped: its contract no longer declares what it keeps")
    types = theirs[: declared.start()].strip() + "\n"
    if re.search(r"^\s*(import\b|export .* from|/// <reference)", types, re.MULTILINE):
        sys.exit("import stopped: its contract reaches into another file")
    keys = [entry.strip() for entry in kept.group(1).split(";") if entry.strip()]
    ours = CONTRACT.read_text(encoding="utf-8")
    block = re.compile(r"(// <sdk-panel>\n)[\s\S]*?(// </sdk-panel>\n)")
    state = re.compile(rf"('{OURS}': \{{ book: Shaped<Book>)[^}}]*( \}})")
    if len(block.findall(ours)) != 1 or len(state.findall(ours)) != 1:
        sys.exit("import stopped: types/index.d.ts has no place for the panel")
    names = {key.split(":")[0] for key in keys}
    if "book" in names or len(names) != len(keys):
        sys.exit(f"import stopped: the panel keeps a value under a name already taken: {keys}")
    ours = block.sub(lambda m: m.group(1) + types + m.group(2), ours)
    ours = state.sub(lambda m: m.group(1) + "".join(f"; {key}" for key in keys) + m.group(2), ours)
    CONTRACT.write_text(ours, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    repo = Path(sys.argv[1]).expanduser().resolve()
    commit = git(repo, "rev-parse", "HEAD").strip()
    subject = git(repo, "log", "-1", "--format=%s").strip()
    files = git(repo, "ls-tree", "-r", "--name-only", "HEAD").split("\n")

    def show(path: str) -> str:
        return git(repo, "show", f"HEAD:{path}")

    # Everything is read and changed before anything is written.
    module = pane(show("hooks/register.tsx"))
    tests = pane_tests(show("tests/pane.test.tsx"))
    core = {f: show(f) for f in files if re.fullmatch(r"core/[\w.-]+\.js", f)}
    fixtures = {f: show(f) for f in files if f.startswith("test/fixtures/")}
    taken, left = {}, []
    for f in files:
        if not re.fullmatch(r"test/[\w.-]+\.test\.js", f):
            continue
        text = show(f)
        outside = [
            m for m in re.findall(r"from '(\.\./[^']+)'", text) if not m.startswith("../core/")
        ]
        # A test can also read a file by its path: one outside core/ and test/ is not here.
        outside += re.findall(
            r"""['"`]((?:\.\./)?(?:(?:hooks|app|cli|server|scripts|preview|docs|types|tests)/[^'"`]*|package\.json))['"`]""",
            text,
        )
        if outside:
            left.append(f"{f} (it also tests {', '.join(sorted(set(outside)))})")
        else:
            taken[f] = text
    if not core or not taken:
        sys.exit("import stopped: no core or no core tests found")
    contract(show("types/index.d.ts"))

    for folder in ("core", "test"):
        shutil.rmtree(DEST / folder, ignore_errors=True)
    for path, text in {**core, **fixtures, **taken}.items():
        target = DEST / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (DEST / "pane.tsx").write_text(module, encoding="utf-8")
    (DEST / "pane.test.tsx").write_text(tests, encoding="utf-8")
    (DEST / "package.json").write_text(
        json.dumps({"private": True, "type": "module"}, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "SOURCE.md").write_text(
        "# Where this pane comes from\n\n"
        "The ServiceNow SDK panel is developed in its own repository, `servicenow-sdk-panel`.\n"
        "The files here are taken from it by `scripts/import_sdk_panel.py`, which says what it\n"
        "changes and why. Change the panel there and run the script again; do not edit these\n"
        "files here.\n\n"
        f"Taken from commit `{commit}` ({subject}).\n\n"
        "| Here | There |\n| --- | --- |\n"
        "| `pane.tsx` | `hooks/register.tsx` |\n"
        "| `pane.test.tsx` | `tests/pane.test.tsx` |\n"
        f"| `core/` ({len(core)} files) | `core/` |\n"
        f"| `test/` ({len(taken)} test files, {len(fixtures)} fixtures) | `test/` |\n"
        "| the panel's part of `types/index.d.ts` | `types/index.d.ts` |\n\n"
        + (
            "Not taken, because they test parts that stay in the panel's repository:\n\n"
            + "".join(f"- `{name}`\n" for name in left)
            if left
            else ""
        ),
        encoding="utf-8",
    )
    print(f"took the panel at {commit[:7]}: {len(core)} core files, {len(taken)} core tests")
    for name in left:
        print(f"  left: {name}")


if __name__ == "__main__":
    main()
