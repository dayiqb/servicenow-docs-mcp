import {fail, isViewer, runChart} from '../../lib/server/engine.js';

/**
 * Server script for the chart widget on the canvas.
 * The chart settings come from the client, so the engine checks all of them
 * again as the current user: allow list, table access and field access.
 */
export default function server(data, _options, input) {
  if (!input || input.action !== 'run') return;
  if (!isViewer()) {
    fail(data, gs.getMessage('You need the dashboard viewer role to see this chart'));
    return;
  }
  var run = runChart({
    title: input.chartTitle,
    source_table: input.sourceTable,
    query: input.filter,
    group_by: input.groupBy,
    group_by_2: input.secondGroupBy,
    aggregate: String(input.aggregate || 'COUNT').toUpperCase(),
    aggregate_field: input.aggregateField,
    chart_type: String(input.chartType || 'column').toLowerCase(),
    trend: normalizeTrend(input.dateTrend),
    list_fields: input.listFields,
    max_groups: input.maxGroups
  });
  data.run = run;

  function normalizeTrend(v) {
    var t = String(v || 'none').toLowerCase();
    if (t === 'none' || t === '') return 'none';
    return t.charAt(0).toUpperCase() + t.substring(1);
  }
}
