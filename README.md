# ServiceNow Docs for Claude

Ask Claude questions about ServiceNow and get answers taken from the **official ServiceNow product
documentation**, for the **Australia** and **Brazil** releases, each claim with a citation you can
open.

It adds eleven read-only tools to Claude:

| Tool | What it does |
|---|---|
| `snow_docs_search` | Finds the most relevant documentation passages for a question |
| `snow_docs_read` | Opens the full section behind a search result |
| `snow_docs_compare` | Shows what changed between the Australia and Brazil docs for a topic or page |
| `snow_docs_api` | Looks up a scripting class or method exactly: its methods, parameters and return type |
| `snow_docs_check_script` | Checks a script: which method calls and table names the docs do not have |
| `snow_docs_browse` | Lists the docs as a tree: product areas, folders and pages by title |
| `snow_docs_sdk_status` | Shows whether the ServiceNow SDK is installed, its version and the instances it is set up for |
| `snow_docs_sdk_explain` | Reads the ServiceNow SDK's own documentation (Fluent) for the installed version |
| `snow_docs_open` | Shows a page to you as a readable document, in a panel |
| `snow_docs_diagram` | Shows a process from the docs as a flow diagram or swimlanes, in a panel |
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
/plugin install servicenow-docs@servicenow-docs-mcp
```

Using both (the extension in Desktop, the plugin in the terminal) is fine: they share one data
folder, so nothing downloads twice.

The very first start takes a little longer (uv sets up Python, about 200 MB). If Claude says
the server failed to start the first time, restart Claude once.

## First run

The first time a release is used, the server downloads its docs index (about 600-660 MB, from
this repo's GitHub releases), and once per computer two search models (about 1.2 GB, from Hugging
Face). That takes a few minutes. Until it's done, the tools reply "still being set up" with a
percentage; ask Claude to run `snow_docs_status` to check progress.

Everything is stored in one folder, shared by all Claude apps on the computer:

- Windows: `%USERPROFILE%\.servicenow-docs-mcp`
- macOS / Linux: `~/.servicenow-docs-mcp`

About 1.7 GB per release once unpacked (2.4 GB free space needed while it unpacks), plus the
models. After the first run it works offline. Each running
copy of the server (Claude Desktop, plus one per open Claude Code session) uses under 100 MB of
memory until its first search, then about 3 GB.

## Releases and updates

- **Australia** is the default. For **Brazil**, just say so ("check the Brazil docs") and Claude
  passes `release: "brazil"`. To make Brazil the default, set the environment variable
  `SNOW_DOCS_RELEASE=brazil`.
- Only releases you actually use are downloaded.
- The Brazil docs don't yet cover every area: the current snapshot has no API reference and no
  Finance and Supply Chain pages, and only part of Employee Service Management. Brazil search
  results say so, and Claude searches the Australia docs for questions in those areas.
- **Updates are automatic.** The server checks for a newer docs snapshot when it starts and once
  a day, downloads it in the background, verifies it, and switches over. Searches keep working
  on the current snapshot meanwhile. Older snapshots are deleted.

## Using it

Ask ServiceNow questions normally: "How is incident priority calculated?", "What roles do I need
to configure an email account?" Claude searches, reads the relevant sections, and answers with
citations like `[australia:markdown/it-service-management/…md::Incident management > Priority]`,
plus a link to each page on www.servicenow.com (for the release you searched), or its source
page on GitHub when the docs name no site page. Links between docs pages inside a section point
at those pages too.

To narrow a search, ask Claude to limit it to one area, e.g. *"search only in
platform-security"*. Common abbreviations work too (ITSM, CSM, HRSD, CMDB, UI Builder, Service
Portal, ...); an unknown area name gets back suggestions and the list of valid ones.

When a question names a method or other code name (`addEncodedQuery`, `g_form.setMandatory`),
the section with exactly that name comes first. A misspelt name gets a note, with the closest
name the docs have (*"did you mean 'setMandatory'?"*).

**Docs first, automatically.** The plugin includes a small hook: when a message is clearly
about ServiceNow, Claude is reminded to search the docs and cite them before answering. One
unmistakable term is enough (ServiceNow, GlideRecord, `g_form`, `sys_id`, Flow Designer, MID
Server, a transform map, …); words that also appear in everyday IT talk (business rule,
client script, update set, CMDB, ITSM, ACL, catalog item, …) count only when two come
together. Other messages are left alone. The hook never blocks a message; turn it off with
the environment variable `SNOW_DOCS_PROMPT_HOOK=off`. (The hook comes with the plugin, in
Claude Code; in Claude Desktop the extension's built-in instructions do the same job.)

**Script check, automatically.** A second hook runs after Claude writes or edits a file with
ServiceNow script code (JavaScript, TypeScript, exported XML, widget HTML). It looks up every
method call on an object whose class it can tell, and every table opened by name, and tells
Claude what the docs do not have, with the closest documented names. Claude then fixes the
code or tells you what could not be verified. It tells an object's class from:

- `new GlideRecord(...)` and other documented classes;
- what a documented method returns (`var user = gs.getUser()`), also in a chain
  (`gs.getUser().getName()`);
- a JSDoc `@param {GlideRecord} rec` or a TypeScript `rec: GlideRecord`;
- the platform's variables (`gs`, `current`, `g_form`, `$sp`, ...) and the usual names (`gr`,
  `now_GR`, `gdt`).

Table names are compared with the names the docs mention; customer tables (`u_`, `x_`) are
skipped. Field names are not checked: they depend on your instance. The hook takes about a
second, never blocks a write and stays silent for code that checks out; turn it off with
`SNOW_DOCS_SCRIPT_HOOK=off`. Hooks exist in Claude Code only: in Claude Desktop, Claude runs
the same check itself with the `snow_docs_check_script` tool.

## The panel in Claude Desktop

In Claude Desktop, results can appear in a panel next to Claude's answer, so you can read the
source yourself. It follows Claude's light or dark theme and your language (English or
Norwegian), works with the keyboard, and needs no network: it is one page inside the extension.

- **Search results.** A ranked list with the page, the section and the passage. *Read section*
  opens the full section in place; *Open docs* opens the page on servicenow.com; the switch at
  the top runs the same search in the other release.
- **A page as a document.** Ask *"show me that page"*: the page is laid out for reading, with
  its sections listed beside it, notes set apart, and tables and code as they should be. A
  numbered procedure can also be shown as a flow, one box per step. The switch shows the same
  page in the other release.
- **Browse.** Product areas, folders and pages as lists you click through; a page opens as a
  document.
- **Diagrams.** Ask *"draw the major incident process as swimlanes"*: Claude takes the steps
  from the docs and the panel draws a flow, or swimlanes when several roles take part. Every
  step lists the passage it comes from, and you can open it.
- **What changed.** A comparison of Australia and Brazil, side by side, with the words that
  differ marked.

Claude Code and other clients without panels get the same results as text; a diagram comes as
Mermaid text there.

## Compare releases

Ask what changes between the two releases, for example *"What changes for Document Intelligence
when we upgrade from Australia to Brazil?"* Claude calls `snow_docs_compare` and gets back:

- **Release notes.** The matching passages from ServiceNow's own combined release notes for
  upgrades from Australia to Brazil.
- **Changed pages.** The documentation pages on that topic whose text differs between the
  releases, section by section (added, removed or changed), with an excerpt from each release.

To compare one page, give Claude its path or a citation from an earlier answer. Differences in
page metadata and links are ignored, and small rewordings are counted but not listed. Both
releases' docs must be downloaded; the first comparison starts the download of the one that is
missing.

## Upgrade review

Ask for an upgrade checklist, for example *"What do we need to check for Document Intelligence
before we upgrade from Australia to Brazil?"* Claude finds the product's page in ServiceNow's
combined release notes, reads all of it, and writes a checklist with a citation on every item:
before and after the upgrade, new features, changed behavior, removed and deprecated, and
activation and requirements. Where the release notes say there are no updates, the checklist says
so.

In Claude Code this is the `servicenow-upgrade-review` skill, used automatically. In Claude
Desktop, pick the `upgrade_review` prompt and enter the product name, or just ask.

## API lookup

Ask what a class offers or what a method takes, for example *"Which parameters does
GlideRecord.addEncodedQuery take?"* or *"List the methods of GlideAggregate."* Claude calls
`snow_docs_api`, which answers from a table of everything in the API reference instead of
searching text:

- **Scripting APIs.** About 4,500 methods in 520 classes: the signature, each parameter with
  its type, the return type, a short description and the first code example. A class name lists
  its methods, with the global and scoped variants apart. The variables scripts use work as
  class names too (`gs`, `current`, `g_form`, `g_list`, `$sp` and others).
- **REST APIs.** About 680 endpoints in 136 APIs: an API name ("Table API") lists its endpoints,
  and an endpoint ("POST /api/now/table/incident") gives its default URL and its path, query
  and request body parameters.

A name the API reference does not have gets a clear "not found" with the closest names, so
Claude checks its methods before it writes script code instead of guessing.

## Setup checklist

Ask how to set something up, for example *"How do I set up Document Intelligence?"* Claude
finds the setup pages, reads them in full and writes an ordered checklist with a citation on
every item: what must be in place first (plugins, licenses, roles, dependencies), the steps in
the docs' order, how to check that it works, and what to configure next. Where the docs lack a
step, the checklist says so.

In Claude Code this is the `servicenow-setup-checklist` skill, used automatically. In Claude
Desktop, pick the `setup_checklist` prompt and enter the feature, or just ask.

## Browse

Ask what the docs have on something instead of searching for words you may not know, for
example *"What is documented under Incident Management?"* Claude calls `snow_docs_browse`:
without arguments it lists the 54 product areas with their page counts; with a product it
lists that area's folders and pages by title; with a folder it goes further down. Every page
can be opened in full.

## ServiceNow SDK

If the ServiceNow SDK (`now-sdk`) is installed on your computer, two more lookups work:

- **SDK documentation.** Ask about Fluent or the SDK, for example *"How do I define a business
  rule in Fluent?"* Claude reads the SDK's own documentation with `snow_docs_sdk_explain`
  (about 270 topics), which matches the SDK version you have installed.
- **Setup status.** Ask *"Is my ServiceNow SDK set up?"* and `snow_docs_sdk_status` shows the
  version and the instances the SDK has credentials for: alias, address, kind of sign-in and
  which one is the default. User names and secrets are never shown.

Both only read. This extension never signs in, never changes the SDK's configuration and never
contacts an instance: adding an instance is something you do yourself in a terminal
(`now-sdk auth --add <instance> --type oauth`). In Claude Code, the script check also reminds
Claude to run `now-sdk build`, which type-checks locally, after it changes a Fluent file
(`*.now.ts`).

## Command line and library

The same tools work without Claude, from a terminal, a script or another agent. Each command
prints one JSON result and exits 0 when it is ok:

```bash
snow-docs-mcp search "how is incident priority calculated" --limit 3
snow-docs-mcp read "australia:markdown/it-service-management/incident-management/def-prio-lookup-rules.md::"
snow-docs-mcp api GlideRecord.addEncodedQuery
snow-docs-mcp api "POST /api/now/table/incident"
snow-docs-mcp check-script my_business_rule.js
snow-docs-mcp browse itsm --folder incident-management
snow-docs-mcp compare "document intelligence"
snow-docs-mcp status
snow-docs-mcp sdk-status
snow-docs-mcp sdk-explain BusinessRule
```

From a checkout, put `uv run` in front. A search loads the search models each time, so it
takes about 5 seconds; the lookups take 1 to 2 seconds. Run `snow-docs-mcp setup all` once
first if the docs are not installed.

In Python, `snow_docs_mcp.api` has the same calls and returns the same results:

```python
from snow_docs_mcp import api

found = api.search("how is incident priority calculated", limit=3)
method = api.lookup("GlideRecord.addEncodedQuery")
```

## Troubleshooting

| Problem | Fix |
|---|---|
| The server fails to start | Check uv is installed (`uv --version` in a terminal), then quit and reopen Claude. |
| Searches are slow (6+ seconds, e.g. a 2-CPU computer or container) | Claude Desktop: Settings → Extensions → ServiceNow Docs → turn on "Faster search on slow computers". Claude Code: set the environment variable `SNOW_DOCS_RERANK=fast`. The ranking step then reads less of each candidate: about 45% less work per search, slightly different results, same measured quality (nDCG@10 −.007, not significant). |
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
