# Panel fixtures

Input for `tests/test_panel.py` and for the stand-in host (`scripts/panel_host.html`).

- `steps-*.json`, `links-bold.json`, `code-bold.json`, `italic.json`, `table-*.json`: sections
  of the ServiceNow documentation exactly as `snow_docs_read` returns them (Australia release,
  snapshot 2026-11-06). The text is ServiceNow's, under the Apache License 2.0 (see `NOTICE`
  in the repository root). Each one holds a construct the panel once showed wrongly: sub-steps,
  links in bold, lists and placeholders in table cells, a table inside a table.

Show one in the browser: `scripts/panel_host.html?view=open&page=steps-nested`.
