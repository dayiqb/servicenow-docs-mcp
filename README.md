# ServiceNow Docs for Claude

Ask Claude questions about ServiceNow and get answers taken from the **official ServiceNow product
documentation**, for the **Australia** and **Brazil** releases, each claim with a citation you can
open.

It adds three read-only tools to Claude:

| Tool | What it does |
|---|---|
| `snow_docs_search` | Finds the most relevant documentation passages for a question |
| `snow_docs_read` | Opens the full section behind a search result |
| `snow_docs_status` | Shows download/update progress and which docs snapshot is loaded |

Claude writes the answer from the passages and cites them. The server itself runs no AI model
that writes text, needs no API key, and sends nothing about your questions anywhere.

Works on **Windows 10/11 (x64)**, **macOS 14 or later on Apple silicon**, and **Linux (x64)**.

## Install

### 1. Install uv (once)

The plugin uses [uv](https://docs.astral.sh/uv/) to set up Python for the server.

- **Windows** (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **macOS / Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Then quit and reopen Claude so it picks up uv.

**Windows only:** the search models need the Microsoft Visual C++ Redistributable (x64), which
most PCs already have. If not, install it from https://aka.ms/vs/17/release/vc_redist.x64.exe.

### 2. Add it to Claude

**Claude Desktop (chat, Cowork and the Code tab): the extension.** Download
`servicenow-docs.mcpb` from the
[latest release](https://github.com/dayiqb/servicenow-docs-mcp/releases/latest) and double-click
it (or **Settings → Extensions → Advanced settings → Install Extension…**). It is unsigned, so
Claude Desktop shows a warning. Extensions run on your computer, and Claude Desktop makes them
available in chat, in Cowork and in the Code tab.

> Don't use **Customize → Plugins** for this one in Claude Desktop. Cowork runs plugins inside
> a sandboxed virtual machine that can't reach GitHub or Hugging Face, so the plugin's server
> can never download the docs there.

**Claude Code (terminal or IDE): the plugin.** It also adds the "docs first" hook (below).

```
/plugin marketplace add dayiqb/servicenow-docs-mcp
/plugin install servicenow-docs@servicenow-docs
```

Using both (the extension in Desktop, the plugin in the terminal) is fine: they share one data
folder, so nothing downloads twice.

The very first start takes a little longer (uv sets up Python, about 200 MB). If Claude says
the server failed to start the first time, restart Claude once.

## First run

The first time a release is used, the server downloads its docs index (about 550 MB, from this
repo's GitHub releases), and once per computer two search models (about 1.2 GB, from Hugging
Face). That takes a few minutes. Until it's done, the tools reply "still being set up" with a
percentage; ask Claude to run `snow_docs_status` to check progress.

Everything is stored in one folder, shared by all Claude apps on the computer:

- Windows: `%USERPROFILE%\.servicenow-docs-mcp`
- macOS / Linux: `~/.servicenow-docs-mcp`

About 2.6 GB per release plus the models. After the first run it works offline. Each running
copy of the server (Claude Desktop, plus one per open Claude Code session) uses under 100 MB of
memory until its first search, then about 3 GB.

## Releases and updates

- **Australia** is the default. For **Brazil**, just say so ("check the Brazil docs") and Claude
  passes `release: "brazil"`. To make Brazil the default, set the environment variable
  `SNOW_DOCS_RELEASE=brazil`.
- Only releases you actually use are downloaded.
- **Updates are automatic.** The server checks for a newer docs snapshot when it starts and once
  a day, downloads it in the background, verifies it, and switches over. Searches keep working
  on the current snapshot meanwhile. Older snapshots are deleted.

## Using it

Ask ServiceNow questions normally: "How is incident priority calculated?", "What roles do I need
to configure an email account?" Claude searches, reads the relevant sections, and answers with
citations like `[australia:markdown/it-service-management/…md::Incident management > Priority]`,
plus a link to the page on servicenow.com when the docs provide one.

To narrow a search, ask Claude to limit it to one area, e.g. *"search only in
platform-security"*. An unknown area name gets back the list of valid ones.

**Docs first, automatically.** The plugin includes a small hook: when a message is clearly
about ServiceNow, Claude is reminded to search the docs and cite them before answering. One
unmistakable term is enough (ServiceNow, GlideRecord, `g_form`, `sys_id`, Flow Designer, MID
Server, a transform map, …); words that also appear in everyday IT talk (business rule,
client script, update set, CMDB, ITSM, ACL, catalog item, …) count only when two come
together. Other messages are left alone. The hook never blocks a message; turn it off with
the environment variable `SNOW_DOCS_PROMPT_HOOK=off`. (The hook comes with the plugin, in
Claude Code; in Claude Desktop the extension's built-in instructions do the same job.)

## Troubleshooting

| Problem | Fix |
|---|---|
| The server fails to start | Check uv is installed (`uv --version` in a terminal), then quit and reopen Claude. |
| "HTTP 404" | The docs index release isn't published yet, or the link moved. Tell the maintainer. |
| "not enough free disk space" | Free about 3 GB, or set `SNOW_DOCS_HOME` to a folder on a bigger disk. |
| "DLL load failed" (Windows) | Install the Visual C++ Redistributable (link above), then restart Claude. |
| Certificate / SSL errors on a company network | The server and uv use the operating system's certificates. If your company's proxy certificate isn't installed in Windows, ask IT to install it. |
| "a proxy or Wi-Fi login page may be in the way" | Log in to the network (or try another network); it retries on the next question. |
| "does not match what this version of the server expects" | Update the plugin; if it persists, tell the maintainer. |
| "waiting for another Claude app" | Another app on your computer is doing the one-time download; this one continues when it finishes. |
| Anything else | Claude Desktop logs: `%APPDATA%\Claude\logs\` (Windows) or `~/Library/Logs/Claude/` (macOS), file `mcp-server-servicenow-docs.log`. |
| Start over | Quit Claude, delete the data folder above, and start Claude again. |

## What's inside

The search is the configuration that measured best when seven retrieval techniques were
compared on 67 real ServiceNow questions:

- **Contextual retrieval**: each passage is indexed together with a one-sentence context line
  written ahead of time by a language model (+.081 nDCG@10 over plain hybrid search).
- **Hybrid search**: semantic (`BAAI/bge-small-en-v1.5`) plus keyword (BM25), fused with
  reciprocal rank fusion.
- **Reranking**: a cross-encoder (`BAAI/bge-reranker-base`) reorders the top 25 candidates.

Every docs index is verified by SHA-256 on download. The list of current indexes is
[`index/latest.json`](index/latest.json).

## Development

```bash
uv sync
uv run pytest -q             # fast tests; no downloads
scripts/build_mcpb.sh        # builds dist/servicenow-docs.mcpb
```

CI runs the tests on Windows, macOS and Linux; the `e2e` job (manual, and for version tags)
downloads the real index and searches it over stdio on Windows and macOS.

## License

Code: MIT (see `LICENSE`). The documentation content in the indexes is ServiceNow's, under the
Apache License 2.0 (see `NOTICE`).
