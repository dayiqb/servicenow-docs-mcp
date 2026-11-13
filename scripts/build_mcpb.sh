#!/usr/bin/env bash
# Build dist/servicenow-docs.mcpb (the Claude Desktop extension) from this directory.
#
# The bundle carries only code + pyproject.toml + uv.lock (~220 KB): Claude Desktop installs
# Python and the dependencies with uv, and the server downloads the docs index on first run.
# Uses the official mcpb CLI through npx (no global install).
set -euo pipefail
cd "$(dirname "$0")/.."

MCPB="npx -y @anthropic-ai/mcpb@2.1.2"
OUT="dist/servicenow-docs.mcpb"

mkdir -p dist
rm -f "$OUT"
$MCPB validate manifest.json
$MCPB pack . "$OUT"

# The bundle carries only these top-level entries. Anything else (a virtualenv, tests, build
# output, or a local folder that git never sees) fails the build instead of being shipped.
ALLOWED="src server manifest.json pyproject.toml uv.lock README.md NOTICE LICENSE .python-version"
# shellcheck disable=SC2086  # the list is split into one name per line on purpose
extra=$(unzip -Z1 "$OUT" | cut -d/ -f1 | sort -u | grep -v -x -F -f <(printf '%s\n' $ALLOWED) || true)
if [ -n "$extra" ]; then
  echo "error: the bundle contains entries that are not on the list:" >&2
  echo "$extra" >&2
  mv "$OUT" "$OUT.rejected"
  exit 1
fi
echo "built $OUT ($(du -h "$OUT" | cut -f1)):"
unzip -Z1 "$OUT"
