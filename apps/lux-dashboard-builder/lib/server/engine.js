/*
 * Dashboard query engine.
 *
 * Shared by all widget server scripts. Rollup inlines this file into each
 * server script at build time. It runs on the instance as the current user.
 *
 * Rules:
 * - Every chart run checks access as the current user.
 * - Only tables on the admin allow list can be used.
 * - Every field in the filter, group by, aggregate, and list must be readable.
 * - The engine returns labels and numbers only, never full records
 *   (except the "list" chart, which uses GlideRecordSecure).
 */

export var ROLE_VIEWER = 'x_steas_dash.viewer';
export var ROLE_BUILDER = 'x_steas_dash.builder';
export var ROLE_ADMIN = 'x_steas_dash.admin';

var T_ALLOWED = 'x_steas_dash_allowed_table';

var MAX_GROUPS_LIMIT = 50;
var SECURE_ROW_CAP = 10000;
var LIST_ROW_LIMIT = 20;
var MAX_LIST_FIELDS = 6;

var CHART_TYPES = {
  score: true,
  column: true,
  bar: true,
  stacked: true,
  line: true,
  area: true,
  pie: true,
  donut: true,
  heatmap: true,
  list: true
};
var AGGREGATES = {COUNT: true, SUM: true, AVG: true, MIN: true, MAX: true};
var TRENDS = {none: true, Day: true, Week: true, Month: true, Quarter: true, Year: true};
var NUMERIC_TYPES = {
  integer: true,
  longint: true,
  decimal: true,
  float: true,
  currency: true,
  price: true
};
var DATE_TYPES = {glide_date: true, glide_date_time: true, due_date: true};
var BLOCKED_GROUP_TYPES = {
  journal: true,
  journal_input: true,
  journal_list: true,
  html: true,
  script: true,
  script_plain: true,
  script_server: true,
  conditions: true,
  password: true,
  password2: true,
  glide_list: true,
  translated_html: true
};

/* ---------------------------------------------------------------- helpers */

function str(v) {
  return v === null || v === undefined ? '' : String(v);
}

function isName(v) {
  return /^[a-z0-9_]+$/.test(str(v));
}

function isFieldPath(v) {
  return /^[a-z0-9_]+(\.[a-z0-9_]+){0,3}$/.test(str(v));
}

export function fail(data, message) {
  data.isError = true;
  data.errorMessage = message;
  return data;
}

export function userId() {
  return gs.getUserID();
}

export function isAdmin() {
  return gs.hasRole(ROLE_ADMIN);
}

export function isBuilder() {
  return gs.hasRole(ROLE_BUILDER);
}

export function isViewer() {
  return gs.hasRole(ROLE_VIEWER);
}

/* ------------------------------------------------------------ allow list */

/** Returns the allow-list row for a table, or null. */
export function allowedTable(table) {
  if (!isName(table)) return null;
  var gr = new GlideRecord(T_ALLOWED);
  gr.addQuery('source_table', table);
  gr.addQuery('active', true);
  gr.setLimit(1);
  gr.query();
  if (!gr.next()) return null;
  return {
    sys_id: gr.getUniqueValue(),
    table: table,
    secure: gr.getValue('secure_count') === '1'
  };
}

/** Allowed tables that the current user can read. */
export function listAllowedTables() {
  var out = [];
  var gr = new GlideRecord(T_ALLOWED);
  gr.addQuery('active', true);
  gr.orderBy('source_table');
  gr.setLimit(200);
  gr.query();
  while (gr.next()) {
    var t = gr.getValue('source_table');
    var info = tableInfo(t);
    if (info) out.push(info);
  }
  return out;
}

/** Table label, if the table exists and the user can read it. */
export function tableInfo(table) {
  if (!isName(table)) return null;
  var gr = new GlideRecord(table);
  if (!gr.isValid()) return null;
  if (!gr.canRead()) return null;
  return {name: table, label: gr.getClassDisplayValue() || table};
}

/* ------------------------------------------------------- field security */

/** The table a reference field points to, or '' (never throws). */
function refTable(el) {
  try {
    return str(el.getReferenceTable());
  } catch (e) {
    return '';
  }
}

/**
 * Resolves a field path (dot-walk allowed, up to 4 levels) on a table.
 * Checks read access on every element in the path.
 * Returns {name, label, type} or null if the field is invalid or unreadable.
 */
export function fieldInfo(table, path) {
  if (!isFieldPath(path)) return null;
  var parts = path.split('.');
  var current = table;
  var labels = [];
  var type = '';
  for (var i = 0; i < parts.length; i++) {
    var gr = new GlideRecord(current);
    if (!gr.isValid() || !gr.canRead()) return null;
    if (!gr.isValidField(parts[i])) return null;
    gr.initialize();
    var el = gr.getElement(parts[i]);
    if (!el || !el.canRead()) return null;
    var ed = el.getED();
    type = ed ? str(ed.getInternalType()) : '';
    labels.push(str(el.getLabel()) || parts[i]);
    if (i < parts.length - 1) {
      var ref = refTable(el);
      if (!ref) return null;
      current = ref;
    }
  }
  return {name: path, label: labels.join(' > '), type: type};
}

/* ------------------------------------------------- encoded query checks */

// Only these server functions are allowed inside a filter value.
var SAFE_JS = /^javascript:gs\.(beginningOf|endOf|daysAgo|daysAgoStart|daysAgoEnd|monthsAgo|monthsAgoStart|monthsAgoEnd|quartersAgo|quartersAgoStart|quartersAgoEnd|yearsAgo|hoursAgo|hoursAgoStart|hoursAgoEnd|minutesAgo|minutesAgoStart|minutesAgoEnd|getUserID|dateGenerate)[A-Za-z]*\([^()]*\)$/;

/**
 * Finds every field that an encoded query reads.
 * Returns {ok, fields, reason}.
 */
export function queryFields(query) {
  var q = str(query);
  if (!q) return {ok: true, fields: []};
  if (q.length > 4000) return {ok: false, reason: 'Filter is too long'};

  // Check every javascript: value against the safe list.
  var jsParts = q.split('javascript:');
  for (var j = 1; j < jsParts.length; j++) {
    var token = 'javascript:' + jsParts[j].split('^')[0].split('@')[0];
    if (!SAFE_JS.test(token)) {
      return {ok: false, reason: 'Filter uses a script that is not allowed'};
    }
  }

  var fields = [];
  var parts = q.split(/\^NQ|\^OR(?!DERBY)|\^/);
  for (var i = 0; i < parts.length; i++) {
    var p = parts[i];
    if (!p || p === 'EQ') continue;
    var f = '';
    if (p.indexOf('ORDERBYDESC') === 0) f = p.substring(11);
    else if (p.indexOf('ORDERBY') === 0) f = p.substring(7);
    else if (p.indexOf('GROUPBY') === 0) f = p.substring(7);
    else if (/^[A-Z]/.test(p)) {
      // RLQUERY, SUBQUERY, GOTO, and other special tokens are not allowed.
      return {ok: false, reason: 'Filter uses a query type that is not allowed'};
    } else {
      var m = p.match(/^([a-z0-9_]+(\.[a-z0-9_]+)*)/);
      if (!m) return {ok: false, reason: 'Filter could not be read'};
      f = m[1];
    }
    if (f) fields.push(f);
  }
  return {ok: true, fields: fields};
}

/* ----------------------------------------------------- chart validation */

/**
 * Cleans a chart definition and checks every part of it as the current user.
 * Returns {ok, chart, allowed, fields, reason}.
 */
export function validateChart(def) {
  var c = {
    title: str(def.title).substring(0, 100),
    source_table: str(def.source_table),
    query: str(def.query),
    group_by: str(def.group_by),
    group_by_2: str(def.group_by_2),
    aggregate: str(def.aggregate) || 'COUNT',
    aggregate_field: str(def.aggregate_field),
    chart_type: str(def.chart_type) || 'column',
    trend: str(def.trend) || 'none',
    list_fields: str(def.list_fields),
    max_groups: parseInt(def.max_groups, 10) || 10
  };

  if (!CHART_TYPES[c.chart_type]) return {ok: false, reason: 'Chart type must be one of: ' + Object.keys(CHART_TYPES).join(', ')};
  if (!AGGREGATES[c.aggregate]) return {ok: false, reason: 'Aggregate must be one of: COUNT, SUM, AVG, MIN, MAX'};
  if (!TRENDS[c.trend]) return {ok: false, reason: 'Date trend must be one of: none, day, week, month, quarter, year'};
  c.max_groups = Math.max(1, Math.min(MAX_GROUPS_LIMIT, c.max_groups));

  var allowed = allowedTable(c.source_table);
  if (!c.source_table) return {ok: false, reason: 'Set the source table (for example incident)'};
  if (!allowed) {
    return {ok: false, reason: 'This table is not on the allow list: ' + c.source_table};
  }
  if (!tableInfo(c.source_table)) {
    return {ok: false, reason: 'You cannot read this table: ' + c.source_table};
  }

  // Which fields does this chart type need?
  var needsGroup = {column: 1, bar: 1, stacked: 1, line: 1, area: 1, pie: 1, donut: 1, heatmap: 1};
  var needsTwo = {stacked: 1, heatmap: 1};
  if (c.chart_type === 'score' || c.chart_type === 'list') {
    c.group_by = '';
    c.group_by_2 = '';
  }
  if (!needsTwo[c.chart_type]) c.group_by_2 = '';
  if (needsGroup[c.chart_type] && !c.group_by) {
    return {ok: false, reason: 'Set the group by field (for example priority)'};
  }
  if (needsTwo[c.chart_type] && !c.group_by_2) {
    return {ok: false, reason: 'Set the second group by field for this chart type'};
  }
  if (c.aggregate === 'COUNT') c.aggregate_field = '';
  if (c.aggregate !== 'COUNT' && !c.aggregate_field) {
    return {ok: false, reason: 'Set the aggregate field (a number field) for SUM, AVG, MIN or MAX'};
  }
  if (c.chart_type === 'list') {
    c.aggregate = 'COUNT';
    c.aggregate_field = '';
    c.trend = 'none';
  }

  var fields = {};
  var toCheck = [];
  var qf = queryFields(c.query);
  if (!qf.ok) return {ok: false, reason: qf.reason};
  toCheck = toCheck.concat(qf.fields);
  if (c.group_by) toCheck.push(c.group_by);
  if (c.group_by_2) toCheck.push(c.group_by_2);
  if (c.aggregate_field) toCheck.push(c.aggregate_field);

  var listFieldNames = [];
  if (c.chart_type === 'list') {
    var raw = c.list_fields ? c.list_fields.split(',') : [];
    for (var r = 0; r < raw.length && listFieldNames.length < MAX_LIST_FIELDS; r++) {
      var lf = raw[r].replace(/\s/g, '');
      if (lf) listFieldNames.push(lf);
    }
    if (!listFieldNames.length) listFieldNames = ['sys_created_on'];
    c.list_fields = listFieldNames.join(',');
    toCheck = toCheck.concat(listFieldNames);
  }

  for (var i = 0; i < toCheck.length; i++) {
    var info = fieldInfo(c.source_table, toCheck[i]);
    if (!info) {
      return {ok: false, reason: 'Unknown field, or you cannot read it: ' + toCheck[i]};
    }
    fields[toCheck[i]] = info;
  }

  if (c.group_by && BLOCKED_GROUP_TYPES[fields[c.group_by].type]) {
    return {ok: false, reason: 'You cannot group by this field type'};
  }
  if (c.group_by_2 && BLOCKED_GROUP_TYPES[fields[c.group_by_2].type]) {
    return {ok: false, reason: 'You cannot group by this field type'};
  }
  if (c.aggregate_field && !NUMERIC_TYPES[fields[c.aggregate_field].type]) {
    return {ok: false, reason: 'The aggregate field must be a number field'};
  }
  if (c.trend !== 'none') {
    if (!c.group_by || !DATE_TYPES[fields[c.group_by].type] || c.group_by.indexOf('.') > -1) {
      c.trend = 'none';
    }
  }

  return {ok: true, chart: c, allowed: allowed, fields: fields, listFields: listFieldNames};
}

/* ------------------------------------------------------------ run chart */

function round(n) {
  if (n === null || n === undefined || isNaN(n)) return 0;
  return Math.round(n * 100) / 100;
}

function aggLabel(c, fields) {
  var names = {COUNT: 'Count', SUM: 'Sum', AVG: 'Average', MIN: 'Minimum', MAX: 'Maximum'};
  var base = gs.getMessage(names[c.aggregate]);
  if (c.aggregate_field) return base + ' ' + fields[c.aggregate_field].label;
  return base;
}

/** Runs with GlideAggregate. Fast. Does not apply row-level ACLs. */
function runAggregate(c) {
  var ga = new GlideAggregate(c.source_table);
  if (c.query) ga.addEncodedQuery(c.query);
  if (c.aggregate === 'COUNT') ga.addAggregate('COUNT');
  else ga.addAggregate(c.aggregate, c.aggregate_field);
  var trendOn = c.trend !== 'none' && c.group_by;
  if (trendOn) ga.addTrend(c.group_by, c.trend);
  else if (c.group_by) ga.groupBy(c.group_by);
  if (c.group_by_2) ga.groupBy(c.group_by_2);
  ga.query();

  var rows = [];
  while (ga.next()) {
    var v =
      c.aggregate === 'COUNT'
        ? parseFloat(ga.getAggregate('COUNT'))
        : parseFloat(ga.getAggregate(c.aggregate, c.aggregate_field));
    var row = {value: round(v), weight: 1};
    if (trendOn) {
      row.k1 = str(ga.getValue('timeref'));
      row.l1 = row.k1;
    } else if (c.group_by) {
      row.k1 = str(ga.getValue(c.group_by));
      row.l1 = str(ga.getDisplayValue(c.group_by));
    }
    if (c.group_by_2) {
      row.k2 = str(ga.getValue(c.group_by_2));
      row.l2 = str(ga.getDisplayValue(c.group_by_2));
    }
    rows.push(row);
  }
  return {rows: rows, truncated: false};
}

/**
 * Runs with GlideRecordSecure. Applies row and field ACLs on every record.
 * Slower, so it stops at SECURE_ROW_CAP records.
 */
function runSecure(c) {
  var gr = new GlideRecordSecure(c.source_table);
  if (c.query) gr.addEncodedQuery(c.query);
  gr.setLimit(SECURE_ROW_CAP + 1);
  gr.query();

  var groups = {};
  var order = [];
  var seen = 0;
  var truncated = false;
  var restricted = gs.getMessage('(restricted)');

  function keyOf(field) {
    if (!field) return {k: '', l: ''};
    var el = gr.getElement(field);
    if (!el || !el.canRead()) return {k: '__restricted__', l: restricted};
    if (c.trend !== 'none' && field === c.group_by) {
      var raw = str(gr.getValue(field));
      var k = trendKey(raw, c.trend);
      return {k: k, l: k};
    }
    return {k: str(el.toString()), l: str(el.getDisplayValue())};
  }

  while (gr.next()) {
    seen++;
    if (seen > SECURE_ROW_CAP) {
      truncated = true;
      break;
    }
    var a = keyOf(c.group_by);
    var b = keyOf(c.group_by_2);
    var id = a.k + '\u0001' + b.k;
    var g = groups[id];
    if (!g) {
      g = {k1: a.k, l1: a.l, k2: b.k, l2: b.l, count: 0, sum: 0, min: null, max: null, n: 0};
      groups[id] = g;
      order.push(id);
    }
    g.count++;
    if (c.aggregate !== 'COUNT') {
      var el = gr.getElement(c.aggregate_field);
      if (el && el.canRead()) {
        var num = parseFloat(str(gr.getValue(c.aggregate_field)));
        if (!isNaN(num)) {
          g.sum += num;
          g.n++;
          g.min = g.min === null ? num : Math.min(g.min, num);
          g.max = g.max === null ? num : Math.max(g.max, num);
        }
      }
    }
  }

  var rows = [];
  for (var i = 0; i < order.length; i++) {
    var gg = groups[order[i]];
    var value = gg.count;
    if (c.aggregate === 'SUM') value = gg.sum;
    else if (c.aggregate === 'AVG') value = gg.n ? gg.sum / gg.n : 0;
    else if (c.aggregate === 'MIN') value = gg.min === null ? 0 : gg.min;
    else if (c.aggregate === 'MAX') value = gg.max === null ? 0 : gg.max;
    rows.push({k1: gg.k1, l1: gg.l1, k2: gg.k2, l2: gg.l2, value: round(value), weight: gg.count});
  }
  return {rows: rows, truncated: truncated};
}

/** Bucket key for a date value, used by the secure path. Uses UTC dates. */
function trendKey(raw, trend) {
  if (!raw) return '';
  var d = raw.substring(0, 10); // yyyy-MM-dd
  var y = d.substring(0, 4);
  var m = parseInt(d.substring(5, 7), 10);
  if (trend === 'Year') return y;
  if (trend === 'Quarter') return y + ' Q' + (Math.floor((m - 1) / 3) + 1);
  if (trend === 'Month') return d.substring(0, 7);
  if (trend === 'Week') {
    var gdt = new GlideDateTime(raw.length > 10 ? raw : raw + ' 00:00:00');
    return y + ' W' + gdt.getWeekOfYearUTC();
  }
  return d;
}

/** Keeps the top N groups and folds the rest into "Other" (count and sum only). */
function limitGroups(rows, c) {
  if (c.trend !== 'none') {
    rows.sort(function (a, b) {
      return a.k1 < b.k1 ? -1 : a.k1 > b.k1 ? 1 : 0;
    });
    return {rows: rows.slice(-c.max_groups), folded: rows.length > c.max_groups};
  }
  if (c.group_by_2) {
    // Two dimensions: keep the top N values of each dimension.
    var t1 = {};
    var t2 = {};
    for (var i = 0; i < rows.length; i++) {
      t1[rows[i].k1] = (t1[rows[i].k1] || 0) + rows[i].value;
      t2[rows[i].k2] = (t2[rows[i].k2] || 0) + rows[i].value;
    }
    var top1 = topKeys(t1, c.max_groups);
    var top2 = topKeys(t2, c.max_groups);
    var kept = rows.filter(function (r) {
      return top1[r.k1] && top2[r.k2];
    });
    return {rows: kept, folded: kept.length < rows.length};
  }
  rows.sort(function (a, b) {
    return b.value - a.value;
  });
  if (rows.length <= c.max_groups) return {rows: rows, folded: false};
  var head = rows.slice(0, c.max_groups);
  if (c.aggregate === 'COUNT' || c.aggregate === 'SUM') {
    var rest = 0;
    for (var j = c.max_groups; j < rows.length; j++) rest += rows[j].value;
    head.push({k1: '__other__', l1: gs.getMessage('Other'), value: round(rest)});
  }
  return {rows: head, folded: true};
}

function topKeys(totals, n) {
  var keys = [];
  for (var k in totals) {
    if (Object.prototype.hasOwnProperty.call(totals, k)) keys.push(k);
  }
  keys.sort(function (a, b) {
    return totals[b] - totals[a];
  });
  var out = {};
  for (var i = 0; i < keys.length && i < n; i++) out[keys[i]] = true;
  return out;
}

/** Builds the DataResponse that the Lux visualization components read. */
function toDataResponse(c, rows, fields) {
  var empty = gs.getMessage('(empty)');
  var metricLabel = aggLabel(c, fields);
  var columns = {};
  var rendering = {};
  var data = [];

  if (!c.group_by) {
    columns.value = {
      type: 'numerical',
      meaning: 'metric',
      order: 0,
      dataShape: 'single',
      groupedBy: [],
      label: metricLabel
    };
    rendering.value = {role: 'value'};
    data.push([String(rows.length ? rows[0].value : 0)]);
    return {metadata: {columns: columns}, data: data, rendering: {columns: rendering}, interactions: {}};
  }

  function elements(keyName, labelName) {
    var seen = {};
    var list = [];
    for (var i = 0; i < rows.length; i++) {
      var id = rows[i][keyName] || '__empty__';
      if (seen[id]) continue;
      seen[id] = true;
      list.push({id: id, label: rows[i][labelName] || empty});
    }
    return list;
  }

  var d1Label = c.trend !== 'none' ? fields[c.group_by].label + ' (' + c.trend + ')' : fields[c.group_by].label;
  columns.d1 = {type: 'categorical', meaning: 'dimension', order: 0, label: d1Label, elements: elements('k1', 'l1')};
  rendering.d1 = {role: 'grouping'};
  var groupedBy = ['d1'];
  if (c.group_by_2) {
    columns.d2 = {
      type: 'categorical',
      meaning: 'dimension',
      order: 1,
      label: fields[c.group_by_2].label,
      elements: elements('k2', 'l2')
    };
    rendering.d2 = {role: 'grouping'};
    groupedBy.push('d2');
  }
  columns.value = {
    type: 'numerical',
    meaning: 'metric',
    order: groupedBy.length,
    dataShape: 'single',
    groupedBy: groupedBy,
    label: metricLabel
  };
  rendering.value = {role: 'value'};

  for (var i = 0; i < rows.length; i++) {
    var row = [rows[i].k1 || '__empty__'];
    if (c.group_by_2) row.push(rows[i].k2 || '__empty__');
    row.push(String(rows[i].value));
    data.push(row);
  }
  return {metadata: {columns: columns}, data: data, rendering: {columns: rendering}, interactions: {}};
}

/** Top records for the "list" chart type. Always uses GlideRecordSecure. */
function runList(c, fields, listFieldNames) {
  var gr = new GlideRecordSecure(c.source_table);
  if (c.query) gr.addEncodedQuery(c.query);
  if (c.query.indexOf('ORDERBY') === -1) gr.orderByDesc('sys_created_on');
  gr.setLimit(LIST_ROW_LIMIT);
  gr.query();
  var cols = [];
  for (var i = 0; i < listFieldNames.length; i++) {
    cols.push({name: listFieldNames[i], label: fields[listFieldNames[i]].label});
  }
  var rows = [];
  while (gr.next()) {
    var cells = [];
    for (var j = 0; j < listFieldNames.length; j++) {
      var el = gr.getElement(listFieldNames[j]);
      cells.push(el && el.canRead() ? str(el.getDisplayValue()) : '');
    }
    rows.push({sys_id: gr.getUniqueValue(), cells: cells});
  }
  var displayName = new GlideRecord(c.source_table).getDisplayName() || 'number';
  return {kind: 'list', table: c.source_table, display: displayName, columns: cols, rows: rows};
}

/**
 * Runs a chart definition as the current user. Never throws.
 * Returns {ok, result, reason}.
 */
export function runChart(def) {
  try {
    var v = validateChart(def);
    if (!v.ok) return {ok: false, reason: v.reason};
    var c = v.chart;
    if (c.chart_type === 'list') {
      return {ok: true, chart: c, result: runList(c, v.fields, v.listFields)};
    }
    var raw = v.allowed.secure ? runSecure(c) : runAggregate(c);
    var limited = c.group_by ? limitGroups(raw.rows, c) : {rows: raw.rows, folded: false};
    return {
      ok: true,
      chart: c,
      result: {
        kind: 'viz',
        data: toDataResponse(c, limited.rows, v.fields),
        empty: limited.rows.length === 0,
        truncated: raw.truncated,
        folded: limited.folded,
        secure: v.allowed.secure
      }
    };
  } catch (e) {
    gs.error('x_steas_dash runChart: ' + e.message);
    return {ok: false, reason: gs.getMessage('The chart could not run') + ': ' + e.message};
  }
}

export var TABLES = {ALLOWED: T_ALLOWED};
export var LIMITS = {SECURE_ROW_CAP: SECURE_ROW_CAP, MAX_GROUPS: MAX_GROUPS_LIMIT};
