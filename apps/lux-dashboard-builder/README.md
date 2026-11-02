# Lux Dashboard Builder

A no-code dashboard builder for ServiceNow Lux (AIUX). Users pick a table, a filter, a group-by field, and a chart type. The app draws the chart with the official Lux visualization components.

Design: [Lit dashboard builder for Lux: design](https://claude.ai/artifact/BfbvDroQfkwRqSS1mZ3DZx)

## How it works

The app works like the Platform Analytics dashboard editor in Next Experience.

- `/home` lists your dashboards and the shared ones. Builders create new dashboards there.
- `/dashboard/<id>` shows one dashboard on a 12-column grid (GridStack, the grid library that the Lux canvas uses).
- **Edit** turns on edit mode: drag a visualization to move it, drag a corner to resize it, and use **Add visualization**, **Duplicate**, and **Remove**.
- **Configure** opens a side panel: title, visualization gallery, data source (table), filter (condition builder), metric (count, sum, average, minimum, maximum), group by, stack by, trend by date, and the maximum number of groups. The tile on the canvas shows a live preview.
- **Save** stores all changes at once for everyone who can see the dashboard. **Cancel** drops them.
- `/settings` (admins only) sets which tables can be used.

## What is in the app

| Part | Files |
| --- | --- |
| Roles: `x_steas_dash.viewer`, `x_steas_dash.builder`, `x_steas_dash.admin` | `src/fluent/roles.now.ts` |
| Tables: dashboards, charts (with grid position), allowed tables | `src/fluent/tables.now.ts` |
| Record ACLs | `src/fluent/acls.now.ts` |
| Allow list (incident, task) and a sample dashboard | `src/fluent/seed-data.now.ts` (first install only) |
| Query engine with the security checks | `lib/server/engine.js` |
| Dashboard editor | `widgets/x-dash-board/`, `components/x-dash-tile.js`, `components/x-dash-viz-panel.js` |
| Dashboard list | `widgets/x-dash-dashboards/` |
| Chart renderer (Lux visualization components) | `components/x-dash-chart.js` |
| Admin page for the allow list | `widgets/x-dash-settings/` |

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

The scope is `x_steas_dash`, because the target instance requires the company prefix `steas`. For an instance with another prefix, replace `x_steas_dash` in every file (tables, roles, ACLs, decorators) and in `now.config.json`. Delete `src/fluent/generated/keys.ts`, then build again.

## Not tested yet

The app builds without errors (`now-sdk build`, SDK 4.14.0) and lint passes. The editor is not tested on an instance yet. Check these first:

- Drag and resize with GridStack inside the widget's shadow DOM.
- Save in edit mode (new, changed, moved, and removed visualizations).

- The data format that the Lux chart components read (`toDataResponse` in `lib/server/engine.js`).
- `GlideAggregate.addTrend()` and the `timeref` value for date trends.
- The stacked bar setting (`axes.stacking`).
- Cross-scope access to `incident` and `task` from the `x_steas_dash` scope.
