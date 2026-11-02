import {fail, isAdmin, TABLES} from '../../lib/server/engine.js';

/** Admin settings: the table allow list. */
export default function server(data, _options, input) {
  var action = (input && input.action) || 'list';
  if (!isAdmin()) {
    fail(data, gs.getMessage('Only dashboard admins can change settings'));
    return;
  }
  try {
    if (action === 'add') add();
    else if (action === 'update') update();
    else if (action === 'remove') remove();
    list();
  } catch (e) {
    gs.error('x_steas_dash settings ' + action + ': ' + e.message);
    fail(data, gs.getMessage('Something went wrong') + ': ' + e.message);
  }

  function list() {
    var rows = [];
    var gr = new GlideRecordSecure(TABLES.ALLOWED);
    gr.orderBy('source_table');
    gr.setLimit(200);
    gr.query();
    while (gr.next()) {
      var t = gr.getValue('source_table');
      var tgr = new GlideRecord(t);
      rows.push({
        sys_id: gr.getUniqueValue(),
        table: t,
        label: tgr.isValid() ? tgr.getClassDisplayValue() : gs.getMessage('(table not found)'),
        secure: gr.getValue('secure_count') === '1',
        active: gr.getValue('active') === '1'
      });
    }
    data.rows = rows;
  }

  function add() {
    var table = String(input.table || '').trim().toLowerCase();
    if (!/^[a-z0-9_]+$/.test(table) || !new GlideRecord(table).isValid()) {
      fail(data, gs.getMessage('Table not found') + ': ' + table);
      return;
    }
    var dup = new GlideRecord(TABLES.ALLOWED);
    dup.addQuery('source_table', table);
    dup.query();
    if (dup.hasNext()) {
      fail(data, gs.getMessage('This table is already on the list'));
      return;
    }
    var gr = new GlideRecordSecure(TABLES.ALLOWED);
    gr.initialize();
    gr.setValue('source_table', table);
    gr.setValue('secure_count', input.secure !== false);
    gr.setValue('active', true);
    gr.insert();
  }

  function update() {
    var gr = new GlideRecordSecure(TABLES.ALLOWED);
    if (!gr.get(String(input.id || ''))) return;
    if (input.secure !== undefined) gr.setValue('secure_count', input.secure === true);
    if (input.active !== undefined) gr.setValue('active', input.active === true);
    gr.update();
  }

  function remove() {
    var gr = new GlideRecordSecure(TABLES.ALLOWED);
    if (gr.get(String(input.id || ''))) gr.deleteRecord();
  }
}
