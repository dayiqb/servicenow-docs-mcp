# Lux Dashboard Builder

A no-code dashboard builder for ServiceNow Lux (AIUX). Users pick a table, a filter, a group-by field, and a chart type. The app draws the chart with the official Lux visualization components.

Design: [Lit dashboard builder for Lux: design](https://claude.ai/artifact/BfbvDroQfkwRqSS1mZ3DZx)

## How it works

The home page is a native Lux canvas (a page that extends `AIUXDashboard`). The canvas gives drag, resize, a widget library, user personalization, and the admin canvas editor.

Each chart is one **Chart** widget on the canvas. Set the chart in the canvas side panel. The side panel shows plain text fields:

| Setting | Example |
| --- | --- |
| Chart title | Open incidents by priority |
| Source table | incident |
| Filter (encoded query) | active=true^priority=1 |
| Chart type | score, column, bar, stacked, line, area, pie, donut, heatmap, list |
| Group by | priority |
| Second group by | state (only stacked and heatmap) |
| Aggregate | COUNT, SUM, AVG, MIN, MAX |
| Aggregate field | reassignment_count (only SUM, AVG, MIN, MAX) |
| Date trend | none, day, week, month, quarter, year (group by must be a date field) |
| List fields | number,short_description,priority (only list) |
| Max groups | 10 |

If a setting is wrong, the chart shows what to fix.

## What is in the app

| Part | Files |
| --- | --- |
| Roles: `x_steas_dash.viewer`, `x_steas_dash.builder`, `x_steas_dash.admin` | `src/fluent/roles.now.ts` |
| Allowed tables (table and ACLs) | `src/fluent/tables.now.ts`, `src/fluent/acls.now.ts` |
| Starting allow list (incident, task) | `src/fluent/seed-data.now.ts` (first install only) |
| Query engine with the security checks | `lib/server/engine.js` |
| Chart widget for the canvas | `widgets/x-dash-chart-widget/` |
| Chart renderer (Lux visualization components) | `components/x-dash-chart.js` |
| Canvas home page with sample charts | `pages/home/page.js` |
| Admin page for the allow list | `pages/settings/page.js`, `widgets/x-dash-settings/` |

## Chart types

Single score, vertical bar, horizontal bar, stacked bar, line, area, pie, donut, heat map, and list.
Aggregates: count, sum, average, minimum, maximum. Line and bar charts can group a date field by day, week, month, quarter, or year.

## Security

- Charts can use only tables on the allow list (`/settings`, admins only).
- Each chart runs as the person who looks at it.
- The engine checks read access on the table and on every field in the filter, group by, aggregate, and list columns. Dot-walked fields are checked on every table in the path.
- Filters can not use related-list queries or scripts. Only `javascript:gs.*` date and user functions are allowed.
- "Full record security" (default on) counts each record with GlideRecordSecure. It stops at 10,000 records. Turn it off only for tables without record-level ACLs. Then the app counts with GlideAggregate, which is faster.
- The list chart always uses GlideRecordSecure.

## Requirements

- Instance: Zurich Patch 12 or later, or Australia Patch 5 or later.
- Node 24.14.1 or later, pnpm 10 or later. pnpm settings are in `pnpm-workspace.yaml`. It also makes pnpm use only package versions that are at least 1 day old.

## Install

```bash
pnpm install
pnpm build
npx now-sdk auth --list            # find the alias of your instance
npx now-sdk install --auth <alias>
```

Then give users a role (`x_steas_dash.viewer`, `x_steas_dash.builder`, or `x_steas_dash.admin`) and open:
`https://<instance>.service-now.com/aiux/lux-dashboard-builder/home`

### Scope name

The scope is `x_steas_dash`, because the target instance requires the company prefix `steas`. For an instance with another prefix, replace `x_steas_dash` in every file (tables, roles, ACLs, decorators, the widget import in `pages/home/page.js`) and in `now.config.json`. Delete `src/fluent/generated/keys.ts`, then build again.

## Not tested yet

The app builds without errors (`now-sdk build`, SDK 4.14.0) and lint passes. The canvas version is not tested on an instance yet. Check these first:

- The Chart widget gets its settings from the canvas item (`widget_properties`).
- Who can open the canvas editor, and if users can personalize the canvas.

- The data format that the Lux chart components read (`toDataResponse` in `lib/server/engine.js`).
- `GlideAggregate.addTrend()` and the `timeref` value for date trends.
- The stacked bar setting (`axes.stacking`).
- Cross-scope access to `incident` and `task` from the `x_steas_dash` scope.
