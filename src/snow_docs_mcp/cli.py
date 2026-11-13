"""Command line for the docs tools: `snow-docs-mcp search "..."`, `read`, `compare`, `api`,
`check-script`, `browse`, `status`, `sdk-status`, `sdk-explain`.

Each command prints the tool's result as one JSON document on stdout and exits 0 when the
result is ok, 1 when it is not, 2 on bad usage. Anything else a tool or a model prints goes to
stderr, so the output can be piped. The docs index and the search models must be installed
(`snow-docs-mcp setup`); each call loads what it needs, so a search takes a few seconds.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

COMMANDS = (
    "search",
    "read",
    "compare",
    "api",
    "check-script",
    "browse",
    "status",
    "sdk-status",
    "sdk-explain",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snow-docs-mcp", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def release(p: argparse.ArgumentParser) -> None:
        p.add_argument("--release", help="australia or brazil (default: the configured one)")

    p = sub.add_parser("search", help="search the docs")
    p.add_argument("query")
    p.add_argument("--product", help="a product area, e.g. itsm")
    p.add_argument("--limit", type=int, default=5)
    release(p)
    p = sub.add_parser("read", help="read the section or page behind an id")
    p.add_argument("id")
    p.add_argument("--max-chars", type=int, default=20000)
    p = sub.add_parser("compare", help="what changed between australia and brazil")
    p.add_argument("query", nargs="?")
    p.add_argument("--page", help="compare one page: an id or a page path")
    p.add_argument("--product")
    p.add_argument("--limit", type=int, default=5)
    p = sub.add_parser("api", help="look up a class, method, REST API or endpoint")
    p.add_argument("name")
    release(p)
    p = sub.add_parser("check-script", help="check a script's method calls and table names")
    p.add_argument("file", help="a script file, or - for standard input")
    release(p)
    p = sub.add_parser("browse", help="list product areas, folders and pages")
    p.add_argument("product", nargs="?")
    p.add_argument("--folder")
    p.add_argument("--offset", type=int, default=0)
    release(p)
    sub.add_parser("status", help="what is installed, and which docs snapshot")
    sub.add_parser("sdk-status", help="is the ServiceNow SDK set up, and for which instances")
    p = sub.add_parser("sdk-explain", help="the ServiceNow SDK's own documentation")
    p.add_argument("topic", nargs="?")
    p.add_argument("--max-chars", type=int, default=20000)
    return parser


def _call(args: argparse.Namespace):
    from snow_docs_mcp import server  # late: loading it is the slow part

    if args.command == "search":
        return server.snow_docs_search(args.query, args.limit, args.product, args.release)
    if args.command == "read":
        return server.snow_docs_read(args.id, args.max_chars)
    if args.command == "compare":
        return server.snow_docs_compare(args.query, args.page, args.product, args.limit)
    if args.command == "api":
        return server.snow_docs_api(args.name, args.release)
    if args.command == "check-script":
        code = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        return server.snow_docs_check_script(code, args.release)
    if args.command == "browse":
        return server.snow_docs_browse(args.product, args.folder, args.release, args.offset)
    if args.command == "sdk-status":
        return server.snow_docs_sdk_status()
    if args.command == "sdk-explain":
        return server.snow_docs_sdk_explain(args.topic, args.max_chars)
    return server.snow_docs_status()


def run(argv: list[str]) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit:
        return 2
    if args.command == "check-script" and args.file != "-" and not Path(args.file).is_file():
        print(f"check-script: no file at {args.file}", file=sys.stderr)
        return 2
    with contextlib.redirect_stdout(sys.stderr):  # stdout is for the result alone
        result = _call(args)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    if not result.ok:
        print("If the docs are not installed yet, run: snow-docs-mcp setup all", file=sys.stderr)
    return 0 if result.ok else 1
