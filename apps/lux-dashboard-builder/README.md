# Lux Dashboard Builder

A no-code dashboard builder for ServiceNow Lux (AIUX). Users pick a table, a filter, a group-by field, and a chart type. The app draws the chart with the official Lux visualization components.

Design: [Lit dashboard builder for Lux: design](https://claude.ai/artifact/BfbvDroQfkwRqSS1mZ3DZx)

## What is in the app

| Part | Files |
| --- | --- |
| Roles: `x_dash.viewer`, `x_dash.builder`, `x_dash.admin` | `src/fluent/roles.now.ts` |
| Tables: dashboards, charts, allowed tables | `src/fluent/tables.now.ts` |
| Record ACLs for the three tables | `src/fluent/acls.now.ts` |
| Allow list (incident, task) and a sample dashboard | `src/fluent/seed-data.now.ts` (first install only) |
| Query engine with the security checks | `lib/server/engine.js` |
| Widgets: dashboard list, dashboard, settings | `widgets/` |
| Chart renderer (Lux visualization components) | `components/x-dash-chart.js` |
| Pages: `/home`, `/dashboard/:id`, `/settings` | `pages/` |

## Chart types

Single score, vertical bar, horizontal bar, stacked bar, line, area, pie, donut, heat map, and list.
Aggregates: count, sum, average, minimum, maximum. Line and bar charts can group a date field by day, week, month, quarter, or year.

## Security

- Builders can use only tables on the allow list (`/settings`, admins only).
- Each chart runs as the person who looks at it.
- The engine checks read access on the table and on every field in the filter, group by, aggregate, and list columns. Dot-walked fields are checked on every table in the path.
- Filters can not use related-list queries or scripts. Only `javascript:gs.*` date and user functions are allowed.
- "Full record security" (default on) counts each record with GlideRecordSecure. It stops at 10,000 records. Turn it off only for tables without record-level ACLs. Then the app counts with GlideAggregate, which is faster.
- The list chart always uses GlideRecordSecure.

## Requirements

- Instance: Zurich Patch 12 or later, or Australia Patch 5 or later.
- Node 24.14.1 or later, pnpm 10 or later.

## Install

```bash
pnpm install
pnpm build
npx now-sdk auth --list            # find the alias of your instance
npx now-sdk install --auth <alias>
```

Then give users a role (`x_dash.viewer`, `x_dash.builder`, or `x_dash.admin`) and open:
`https://<instance>.service-now.com/aiux/lux-dashboard-builder/home`

### If the install fails on the scope name

Some instances require the company prefix in the scope, for example `x_12345_dash`. Then replace `x_dash` with the new scope in every file (tables, roles, ACLs, decorators), and set the new scope in `now.config.json`. Delete `src/fluent/generated/keys.ts`, then build again.

## Not tested yet

The app builds without errors (`now-sdk build`, SDK 4.14.0) and lint passes. It is not tested on an instance yet. Check these first:

- The data format that the Lux chart components read (`toDataResponse` in `lib/server/engine.js`).
- `GlideAggregate.addTrend()` and the `timeref` value for date trends.
- The stacked bar setting (`axes.stacking`).
- Cross-scope access to `incident` and `task` from the `x_dash` scope.
