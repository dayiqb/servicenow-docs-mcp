import {fail, isBuilder, isAdmin, readDashboard, canView, TABLES} from '../../lib/server/engine.js';

/** Lists the dashboards the user can see, and creates new ones. */
export default function server(data, _options, input) {
  var action = (input && input.action) || 'list';
  try {
    if (action === 'list') list();
    else if (action === 'create') create();
  } catch (e) {
    gs.error('x_dash dashboards ' + action + ': ' + e.message);
    fail(data, gs.getMessage('Something went wrong') + ': ' + e.message);
  }

  function list() {
    var me = gs.getUserID();
    var mine = [];
    var shared = [];
    var gr = new GlideRecordSecure(TABLES.DASHBOARD);
    gr.addActiveQuery();
    gr.orderBy('name');
    gr.setLimit(200);
    gr.query();
    while (gr.next()) {
      var d = readDashboard(gr);
      if (!canView(d)) continue;
      if (d.owner === me) mine.push(d);
      else shared.push(d);
    }
    data.mine = mine;
    data.shared = shared;
    data.canCreate = isBuilder();
    data.isAdmin = isAdmin();
  }

  function create() {
    if (!isBuilder()) {
      fail(data, gs.getMessage('You cannot create dashboards'));
      return;
    }
    var name = String(input.name || '').substring(0, 100);
    if (!name) {
      fail(data, gs.getMessage('Enter a name'));
      return;
    }
    var gr = new GlideRecordSecure(TABLES.DASHBOARD);
    gr.initialize();
    gr.setValue('name', name);
    gr.setValue('description', String(input.description || '').substring(0, 1000));
    gr.setValue('owner', gs.getUserID());
    gr.setValue('shared', false);
    gr.setValue('active', true);
    var id = gr.insert();
    if (!id) {
      fail(data, gs.getMessage('The dashboard could not be created'));
      return;
    }
    data.dashboardId = String(id);
  }
}
