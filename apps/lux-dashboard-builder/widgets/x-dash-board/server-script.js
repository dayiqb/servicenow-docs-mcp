import {
  fail,
  isBuilder,
  isAdmin,
  canView,
  canEdit,
  loadDashboard,
  loadChart,
  listCharts,
  listAllowedTables,
  listFields,
  allowedTable,
  tableInfo,
  runChart,
  validateChart,
  writeChartFields,
  TABLES
} from '../../lib/server/engine.js';

/**
 * Server script for the dashboard widget.
 * Every action checks access as the current user. Input is never trusted.
 */
export default function server(data, _options, input) {
  var action = (input && input.action) || '';
  var handlers = {
    getBoard: getBoard,
    runChart: runSavedChart,
    previewChart: previewChart,
    getFields: getFields,
    saveChart: saveChart,
    deleteChart: deleteChart,
    saveLayout: saveLayout,
    saveBoard: saveBoard,
    deleteBoard: deleteBoard
  };
  var handler = handlers[action];
  if (!handler) return;
  try {
    handler();
  } catch (e) {
    gs.error('x_dash board ' + action + ': ' + e.message);
    fail(data, gs.getMessage('Something went wrong') + ': ' + e.message);
  }

  function viewable() {
    var dash = loadDashboard(input.dashboardId);
    if (!dash || !canView(dash.d)) {
      fail(data, gs.getMessage('You cannot see this dashboard'));
      return null;
    }
    return dash;
  }

  function editable() {
    var dash = loadDashboard(input.dashboardId);
    if (!dash || !canEdit(dash.d)) {
      fail(data, gs.getMessage('You cannot change this dashboard'));
      return null;
    }
    return dash;
  }

  function getBoard() {
    var dash = viewable();
    if (!dash) return;
    data.dashboard = dash.d;
    data.canEdit = canEdit(dash.d);
    data.charts = listCharts(dash.d.sys_id);
    if (data.canEdit) data.tables = listAllowedTables();
  }

  function runSavedChart() {
    var row = loadChart(input.chartId);
    if (!row || !canView(row.dash.d)) {
      fail(data, gs.getMessage('You cannot see this data'));
      return;
    }
    data.run = runChart(row.c);
  }

  function previewChart() {
    if (!editable()) return;
    data.run = runChart(input.chart || {});
  }

  function getFields() {
    if (!isBuilder()) {
      fail(data, gs.getMessage('You cannot build charts'));
      return;
    }
    var table = String(input.table || '');
    if (!allowedTable(table) || !tableInfo(table)) {
      fail(data, gs.getMessage('This table is not on the allow list'));
      return;
    }
    data.table = table;
    data.fields = listFields(table);
  }

  function saveChart() {
    var dash = editable();
    if (!dash) return;
    var v = validateChart(input.chart || {});
    if (!v.ok) {
      fail(data, gs.getMessage(v.reason));
      return;
    }
    var gr = new GlideRecordSecure(TABLES.CHART);
    var id = String((input.chart && input.chart.sys_id) || '');
    if (id) {
      if (!gr.get(id) || gr.getValue('dashboard') !== dash.d.sys_id) {
        fail(data, gs.getMessage('Chart not found'));
        return;
      }
      writeChartFields(gr, v.chart);
      gr.update();
    } else {
      gr.initialize();
      gr.setValue('dashboard', dash.d.sys_id);
      writeChartFields(gr, v.chart);
      gr.setValue('order', nextOrder(dash.d.sys_id));
      id = gr.insert();
    }
    if (!id) {
      fail(data, gs.getMessage('The chart could not be saved'));
      return;
    }
    data.chartId = String(id);
  }

  function nextOrder(dashboardId) {
    var ga = new GlideAggregate(TABLES.CHART);
    ga.addQuery('dashboard', dashboardId);
    ga.addAggregate('MAX', 'order');
    ga.query();
    var max = 0;
    if (ga.next()) max = parseInt(ga.getAggregate('MAX', 'order'), 10) || 0;
    return max + 10;
  }

  function deleteChart() {
    var row = loadChart(input.chartId);
    if (!row || !canEdit(row.dash.d)) {
      fail(data, gs.getMessage('You cannot change this dashboard'));
      return;
    }
    row.gr.deleteRecord();
    data.deleted = true;
  }

  function saveLayout() {
    var dash = editable();
    if (!dash) return;
    var items = input.items || [];
    for (var i = 0; i < items.length && i < 24; i++) {
      var gr = new GlideRecordSecure(TABLES.CHART);
      if (!gr.get(String(items[i].id || ''))) continue;
      if (gr.getValue('dashboard') !== dash.d.sys_id) continue;
      var width = Math.max(1, Math.min(4, parseInt(items[i].width, 10) || 2));
      gr.setValue('order', (i + 1) * 10);
      gr.setValue('width', width);
      gr.update();
    }
    data.saved = true;
  }

  function saveBoard() {
    var dash = editable();
    if (!dash) return;
    var name = String(input.name || '').substring(0, 100);
    if (!name) {
      fail(data, gs.getMessage('Enter a name'));
      return;
    }
    dash.gr.setValue('name', name);
    dash.gr.setValue('description', String(input.description || '').substring(0, 1000));
    dash.gr.setValue('shared', input.shared === true);
    dash.gr.update();
    data.saved = true;
  }

  function deleteBoard() {
    var dash = editable();
    if (!dash) return;
    if (!isAdmin() && dash.d.owner !== gs.getUserID()) {
      fail(data, gs.getMessage('You cannot change this dashboard'));
      return;
    }
    dash.gr.deleteRecord();
    data.deleted = true;
  }
}
