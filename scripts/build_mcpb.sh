#!/usr/bin/env bash
# Build dist/servicenow-docs.mcpb (the Claude Desktop extension) from this directory.
#
# The bundle carries only code + pyproject.toml + uv.lock (~100 KB): Claude Desktop installs
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

# The bundle must never carry a virtualenv, tests or build output.
if unzip -Z1 "$OUT" | grep -E '^(\.venv|tests|dist|scripts)/' >/dev/null; then
  echo "error: bundle contains excluded paths:" >&2
  unzip -Z1 "$OUT" | grep -E '^(\.venv|tests|dist|scripts)/' >&2
  exit 1
fi
echo "built $OUT ($(du -h "$OUT" | cut -f1)):"
unzip -Z1 "$OUT"
