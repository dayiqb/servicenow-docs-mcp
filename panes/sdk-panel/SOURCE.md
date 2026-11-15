# Where this pane comes from

The ServiceNow SDK panel is developed in its own repository, `servicenow-sdk-panel`.
The files here are taken from it by `scripts/import_sdk_panel.py`, which says what it
changes and why. Change the panel there and run the script again; do not edit these
files here.

Taken from commit `c67f5460138982283cc829fc70f0989a7972034a` (The docs extension is found on Windows and Linux too).

| Here | There |
| --- | --- |
| `pane.tsx` | `hooks/register.tsx` |
| `pane.test.tsx` | `tests/pane.test.tsx` |
| `core/` (11 files) | `core/` |
| `test/` (9 test files, 22 fixtures) | `test/` |
| the panel's part of `types/index.d.ts` | `types/index.d.ts` |

Not taken, because they test parts that stay in the panel's repository:

- `test/cli.test.js (it also tests ../cli/host.js, ../cli/sdk-panel.mjs)`
- `test/docs.test.js (it also tests ../cli/docs.js)`
- `test/preview.test.js (it also tests ../scripts/build-preview.mjs)`
- `test/server.test.js (it also tests ../server/index.mjs, ../server/tools.mjs)`
- `test/tokens.test.js (it also tests ../app/tokens.css)`
- `test/versions.test.js (it also tests hooks/register.tsx, package.json)`
