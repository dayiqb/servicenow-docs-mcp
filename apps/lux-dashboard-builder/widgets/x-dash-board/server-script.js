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
  writeGrid,
  cleanGrid,
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
    saveDashboard: saveDashboard,
    saveBoard: saveBoard,
    deleteBoard: deleteBoard
  };
  var handler = handlers[action];
  if (!handler) return;
  try {
    handler();
  } catch (e) {
    gs.error('x_steas_dash board ' + action + ': ' + e.message);
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

  /**
   * Saves the whole dashboard after Edit mode: changed and new charts,
   * grid positions, and removed charts. Checks every chart first, so a bad
   * chart saves nothing.
   */
  function saveDashboard() {
    var dash = editable();
    if (!dash) return;
    var items = input.items || [];
    var removed = input.removed || [];
    if (items.length > 48) {
      fail(data, gs.getMessage('A dashboard can have at most 48 charts'));
      return;
    }
    var checked = [];
    for (var i = 0; i < items.length; i++) {
      var v = validateChart(items[i].chart || {});
      if (!v.ok) {
        var name = (items[i].chart && items[i].chart.title) || gs.getMessage('Untitled chart');
        fail(data, name + ': ' + v.reason);
        return;
      }
      checked.push({id: String(items[i].id || ''), key: String(items[i].key || ''), c: v.chart, g: cleanGrid(items[i].grid)});
    }
    for (var r = 0; r < removed.length && r < 48; r++) {
      var dgr = new GlideRecordSecure(TABLES.CHART);
      if (dgr.get(String(removed[r])) && dgr.getValue('dashboard') === dash.d.sys_id) {
        dgr.deleteRecord();
      }
    }
    var ids = {};
    for (var j = 0; j < checked.length; j++) {
      var item = checked[j];
      var gr = new GlideRecordSecure(TABLES.CHART);
      var id = '';
      if (item.id && gr.get(item.id) && gr.getValue('dashboard') === dash.d.sys_id) {
        writeChartFields(gr, item.c);
        writeGrid(gr, item.g);
        gr.update();
        id = item.id;
      } else {
        gr.initialize();
        gr.setValue('dashboard', dash.d.sys_id);
        writeChartFields(gr, item.c);
        writeGrid(gr, item.g);
        id = String(gr.insert() || '');
      }
      if (!id) {
        fail(data, gs.getMessage('A chart could not be saved') + ': ' + item.c.title);
        return;
      }
      ids[item.key || id] = id;
    }
    data.ids = ids;
    data.charts = listCharts(dash.d.sys_id);
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
