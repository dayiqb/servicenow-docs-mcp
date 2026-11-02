import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXWidgetElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {navigate} from '@servicenow/aiux/aiux-client';
import {gridstackStyles} from '../../components/gridstack-styles.js';
import '../../components/x-dash-tile.js';
import '../../components/x-dash-viz-panel.js';

const {name, description, bestFor, chatCompatible, category, server, discoverable} = decorators;

// GridStack touches the browser DOM, so load it in the browser only (not during SSR).
let gridStackModule = null;
async function loadGridStack() {
  if (!gridStackModule) {
    gridStackModule = await import('gridstack');
    // GridStack writes `content` as text into each item. The tiles render the content instead.
    gridStackModule.GridStack.renderCB = () => {};
  }
  return gridStackModule.GridStack;
}

const GRID_OPTIONS = {
  column: 12,
  cellHeight: 80,
  margin: 6,
  float: false,
  animate: true,
  resizable: {handles: 'se, sw'},
  columnOpts: {breakpoints: [{w: 768, c: 1}], layout: 'list'}
};

let keySeq = 0;
const newKey = () => `new-${Date.now()}-${++keySeq}`;

function clone(v) {
  return JSON.parse(JSON.stringify(v));
}

function blankChart(tables) {
  return {
    title: i18n.getMessage('New visualization'),
    source_table: tables?.[0]?.name || '',
    query: '',
    group_by: '',
    group_by_2: '',
    aggregate: 'COUNT',
    aggregate_field: '',
    chart_type: 'column',
    trend: 'none',
    list_fields: '',
    max_groups: 10
  };
}

/**
 * One dashboard, built like the Platform Analytics dashboard editor.
 * View mode shows the visualizations on a grid. Edit mode lets owners drag,
 * resize, add, duplicate, remove, and configure visualizations in a side
 * panel with a live preview on the canvas. Save stores everything at once.
 */
@customElement('x-dash-board')
@name('Dashboard')
@description('Shows one dashboard. Owners edit it like a Platform Analytics dashboard: drag, resize, and configure visualizations.')
@bestFor('Viewing and building a no-code dashboard of charts on ServiceNow tables.')
@chatCompatible(false)
@category('custom')
@server('./server-script.js')
@discoverable(true)
export default class DashBoard extends AIUXWidgetElement {
  static properties = {
    dashboardId: {type: String, attribute: 'dashboard-id'},
    _board: {state: true},
    _canEdit: {state: true},
    _tables: {state: true},
    _items: {state: true},
    _runs: {state: true},
    _edit: {state: true},
    _selectedKey: {state: true},
    _fields: {state: true},
    _fieldsLoading: {state: true},
    _loading: {state: true},
    _saving: {state: true},
    _error: {state: true},
    _saveError: {state: true},
    _boardForm: {state: true},
    _toast: {state: true}
  };

  static styles = [
    gridstackStyles,
    css`
      :host {
        display: block;
        min-height: 100%;
      }
      .grid-stack {
        min-height: 160px;
      }
      .editing .grid-stack {
        background-image: radial-gradient(var(--color-base-300, #e5e7eb) 1px, transparent 1px);
        background-size: 16px 16px;
        border-radius: 0.5rem;
      }
      .grid-stack-item-content {
        overflow: visible !important;
      }
    `
  ];

  constructor() {
    super();
    this.dashboardId = '';
    this._board = null;
    this._canEdit = false;
    this._tables = [];
    this._items = [];
    this._runs = {};
    this._edit = false;
    this._selectedKey = '';
    this._fields = {};
    this._fieldsLoading = false;
    this._loading = true;
    this._saving = false;
    this._error = '';
    this._saveError = '';
    this._boardForm = null;
    this._toast = '';
    this._grid = null;
    this._tiles = new Map();
    this._snapshot = null;
    this._removed = [];
    this._previewTimers = new Map();
    this._runSeq = new Map();
  }

  updated(changed) {
    if (changed.has('dashboardId') && this.dashboardId) this._load();
    this._syncTiles();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._grid?.destroy(false);
    this._grid = null;
    this._previewTimers.forEach(t => clearTimeout(t));
    clearTimeout(this._toastTimer);
  }

  async _call(input) {
    const res = await this.server.get({dashboardId: this.dashboardId, ...input});
    if (!res) throw new Error(i18n.getMessage('No response from the server'));
    if (res.isError) throw new Error(res.errorMessage);
    return res;
  }

  _say(message) {
    this._toast = message;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (this._toast = ''), 4000);
  }

  /* ------------------------------------------------------------ loading */

  async _load() {
    this._loading = true;
    this._error = '';
    try {
      const res = await this._call({action: 'getBoard'});
      this._board = res.dashboard;
      this._canEdit = !!res.canEdit;
      this._tables = res.tables || [];
      this._items = (res.charts || []).map(c => this._fromServer(c));
      this._runs = {};
      this._loading = false;
      await this.updateComplete;
      await this._buildGrid();
      this._items.forEach(item => this._runSaved(item));
    } catch (e) {
      this._error = e.message;
      this._loading = false;
    }
  }

  _fromServer(c) {
    const {grid, sys_id: id, ...chart} = c;
    return {key: id, id, chart, grid: grid || {x: 0, y: 0, w: 6, h: 4}};
  }

  _setRun(key, value) {
    this._runs = {...this._runs, [key]: value};
  }

  async _runSaved(item) {
    const seq = (this._runSeq.get(item.key) || 0) + 1;
    this._runSeq.set(item.key, seq);
    this._setRun(item.key, {loading: true, run: this._runs[item.key]?.run});
    let run;
    try {
      run = (await this._call({action: 'runChart', chartId: item.id})).run;
    } catch (e) {
      run = {ok: false, reason: e.message};
    }
    if (this._runSeq.get(item.key) === seq) this._setRun(item.key, {loading: false, run});
  }

  async _runPreview(key) {
    const item = this._items.find(i => i.key === key);
    if (!item) return;
    const seq = (this._runSeq.get(key) || 0) + 1;
    this._runSeq.set(key, seq);
    this._setRun(key, {loading: true, run: this._runs[key]?.run});
    let run;
    try {
      run = (await this._call({action: 'previewChart', chart: item.chart})).run;
    } catch (e) {
      run = {ok: false, reason: e.message};
    }
    if (this._runSeq.get(key) === seq) this._setRun(key, {loading: false, run});
  }

  _queuePreview(key, delay = 500) {
    clearTimeout(this._previewTimers.get(key));
    this._previewTimers.set(
      key,
      setTimeout(() => this._runPreview(key), delay)
    );
  }

  /* --------------------------------------------------------------- grid */

  async _buildGrid() {
    const el = this.renderRoot.querySelector('.grid-stack');
    if (!el) return;
    const GridStack = await loadGridStack();
    if (!this._grid) {
      this._grid = GridStack.init(GRID_OPTIONS, el);
      this._grid.on('change', (_e, nodes) => this._onGridChange(nodes));
    } else {
      this._grid.removeAll(true);
    }
    this._tiles.clear();
    this._grid.batchUpdate();
    this._items.forEach(item => this._addTile(item, false));
    this._grid.batchUpdate(false);
    this._setGridEditable(this._edit);
    this._syncTiles();
  }

  _addTile(item, autoPosition) {
    const g = item.grid || {};
    const widget = autoPosition
      ? {id: item.key, w: g.w || 6, h: g.h || 4, autoPosition: true}
      : {id: item.key, x: g.x, y: g.y, w: g.w || 6, h: g.h || 4};
    const el = this._grid.addWidget(widget);
    const content = el.querySelector('.grid-stack-item-content') || el;
    const tile = document.createElement('x-dash-tile');
    tile.key = item.key;
    content.appendChild(tile);
    this._tiles.set(item.key, tile);
    if (autoPosition && el.gridstackNode) {
      const n = el.gridstackNode;
      item.grid = {x: n.x, y: n.y, w: n.w, h: n.h};
    }
    return el;
  }

  _setGridEditable(on) {
    if (!this._grid) return;
    this._grid.enableMove(on);
    this._grid.enableResize(on);
  }

  _onGridChange(nodes) {
    if (!this._edit || !nodes?.length) return;
    const byKey = new Map(nodes.map(n => [String(n.id), n]));
    this._items = this._items.map(item => {
      const n = byKey.get(item.key);
      return n ? {...item, grid: {x: n.x, y: n.y, w: n.w, h: n.h}} : item;
    });
  }

  _syncTiles() {
    for (const item of this._items) {
      const tile = this._tiles.get(item.key);
      if (!tile) continue;
      const state = this._runs[item.key] || {loading: true};
      tile.chart = item.chart;
      tile.run = state.run || null;
      tile.loading = !!state.loading;
      tile.editMode = this._edit;
      tile.selected = this._edit && item.key === this._selectedKey;
    }
  }

  /* ---------------------------------------------------------- edit mode */

  _startEdit() {
    this._snapshot = {items: clone(this._items), runs: {...this._runs}};
    this._removed = [];
    this._saveError = '';
    this._edit = true;
    this._setGridEditable(true);
  }

  async _cancelEdit() {
    this._edit = false;
    this._selectedKey = '';
    this._saveError = '';
    if (this._snapshot) {
      this._items = this._snapshot.items;
      this._runs = this._snapshot.runs;
    }
    this._snapshot = null;
    this._removed = [];
    await this.updateComplete;
    await this._buildGrid();
  }

  async _save() {
    if (this._saving) return;
    this._saving = true;
    this._saveError = '';
    try {
      const res = await this._call({
        action: 'saveDashboard',
        items: this._items.map(i => ({key: i.key, id: i.id || '', chart: i.chart, grid: i.grid})),
        removed: this._removed
      });
      const ids = res.ids || {};
      const runs = {};
      this._items = this._items.map(item => {
        const id = ids[item.key] || item.id;
        runs[id] = this._runs[item.key];
        return {...item, id, key: id};
      });
      this._runs = runs;
      this._edit = false;
      this._selectedKey = '';
      this._snapshot = null;
      this._removed = [];
      await this.updateComplete;
      await this._buildGrid();
      this._say(i18n.getMessage('Dashboard saved'));
    } catch (e) {
      this._saveError = e.message;
    } finally {
      this._saving = false;
    }
  }

  async _addViz() {
    const item = {key: newKey(), id: '', chart: blankChart(this._tables), grid: {w: 6, h: 4}};
    this._items = [...this._items, item];
    this._addTile(item, true);
    this._items = [...this._items];
    await this._select(item.key);
    this._queuePreview(item.key, 0);
  }

  _duplicate(key) {
    const src = this._items.find(i => i.key === key);
    if (!src) return;
    const chart = clone(src.chart);
    chart.title = i18n.getMessage('{0} (copy)', [chart.title || i18n.getMessage('Untitled visualization')]).substring(0, 100);
    const item = {key: newKey(), id: '', chart, grid: {w: src.grid.w, h: src.grid.h}};
    this._items = [...this._items, item];
    this._addTile(item, true);
    this._items = [...this._items];
    this._setRun(item.key, this._runs[key] || {loading: true});
    this._queuePreview(item.key, 0);
    this._say(i18n.getMessage('Visualization duplicated'));
  }

  _remove(key) {
    const item = this._items.find(i => i.key === key);
    if (!item) return;
    const el = this._tiles.get(key)?.closest('.grid-stack-item');
    if (el) this._grid.removeWidget(el, true);
    this._tiles.delete(key);
    if (item.id) this._removed = [...this._removed, item.id];
    this._items = this._items.filter(i => i.key !== key);
    if (this._selectedKey === key) this._selectedKey = '';
    this._say(i18n.getMessage('Visualization removed. Save to keep the change.'));
  }

  async _select(key) {
    this._selectedKey = key;
    const item = this._items.find(i => i.key === key);
    if (item?.chart.source_table) await this._loadFields(item.chart.source_table);
  }

  async _loadFields(table) {
    if (this._fields[table]) return;
    this._fieldsLoading = true;
    try {
      const res = await this._call({action: 'getFields', table});
      this._fields = {...this._fields, [table]: res.fields || []};
    } catch (e) {
      this._say(e.message);
    } finally {
      this._fieldsLoading = false;
    }
  }

  _onVizChange(e) {
    const {key, value} = e.detail;
    const target = this._selectedKey;
    this._items = this._items.map(item => {
      if (item.key !== target) return item;
      const chart = {...item.chart, [key]: value};
      if (key === 'source_table') {
        chart.query = '';
        chart.group_by = '';
        chart.group_by_2 = '';
        chart.aggregate_field = '';
        chart.list_fields = '';
        chart.trend = 'none';
        this._loadFields(value);
      }
      if (key === 'aggregate' && value === 'COUNT') chart.aggregate_field = '';
      if (key === 'group_by') chart.trend = 'none';
      return {...item, chart};
    });
    if (key !== 'title') this._queuePreview(target);
  }

  /* ------------------------------------------------------ board settings */

  async _openBoardForm() {
    this._boardForm = {name: this._board.name, description: this._board.description, shared: this._board.shared};
    await this.updateComplete;
    this.renderRoot.querySelector('#board-form')?.showModal();
  }

  _closeBoardForm() {
    this.renderRoot.querySelector('#board-form')?.close();
    this._boardForm = null;
  }

  async _saveBoardForm(e) {
    e.preventDefault();
    try {
      await this._call({action: 'saveBoard', ...this._boardForm});
      this._board = {...this._board, ...this._boardForm};
      this._closeBoardForm();
      this._say(i18n.getMessage('Dashboard settings saved'));
    } catch (err) {
      this._say(err.message);
    }
  }

  async _deleteBoard() {
    if (!globalThis.confirm?.(i18n.getMessage('Delete this dashboard and all its visualizations?'))) return;
    try {
      await this._call({action: 'deleteBoard'});
      navigate('/home');
    } catch (err) {
      this._say(err.message);
    }
  }

  /* ------------------------------------------------------------- render */

  _renderBoardForm() {
    const f = this._boardForm;
    if (!f) return nothing;
    return html`<form class="flex flex-col gap-3" aria-label=${i18n.getMessage('Dashboard settings')} @submit=${this._saveBoardForm}>
      <label class="flex flex-col gap-1">
        <span class="aiux-label">${i18n.getMessage('Name')}</span>
        <input
          class="aiux-input w-full"
          required
          maxlength="100"
          .value=${f.name}
          @input=${e => (this._boardForm = {...f, name: e.target.value})}
        />
      </label>
      <label class="flex flex-col gap-1">
        <span class="aiux-label">${i18n.getMessage('Description')}</span>
        <textarea
          class="aiux-textarea w-full"
          maxlength="1000"
          .value=${f.description}
          @input=${e => (this._boardForm = {...f, description: e.target.value})}
        ></textarea>
      </label>
      <label class="flex items-center gap-2">
        <input
          type="checkbox"
          class="aiux-toggle"
          .checked=${f.shared}
          @change=${e => (this._boardForm = {...f, shared: e.target.checked})}
        />
        <span>${i18n.getMessage('Share with everyone who has the dashboard viewer role')}</span>
      </label>
      <div class="flex justify-between gap-2">
        <button type="button" class="aiux-btn aiux-btn-error aiux-btn-outline" @click=${this._deleteBoard}>
          ${i18n.getMessage('Delete dashboard')}
        </button>
        <div class="flex gap-2">
          <button type="button" class="aiux-btn aiux-btn-ghost" @click=${this._closeBoardForm}>${i18n.getMessage('Cancel')}</button>
          <button type="submit" class="aiux-btn aiux-btn-primary">${i18n.getMessage('Save')}</button>
        </div>
      </div>
    </form>`;
  }

  _renderToolbar() {
    if (!this._canEdit) {
      return html`<button class="aiux-btn aiux-btn-ghost aiux-btn-sm" @click=${this._load}>${i18n.getMessage('Refresh')}</button>`;
    }
    if (!this._edit) {
      return html`
        <button class="aiux-btn aiux-btn-ghost aiux-btn-sm" @click=${this._load}>${i18n.getMessage('Refresh')}</button>
        <button class="aiux-btn aiux-btn-primary aiux-btn-sm" @click=${this._startEdit}>${i18n.getMessage('Edit')}</button>
      `;
    }
    return html`
      <button class="aiux-btn aiux-btn-outline aiux-btn-sm" @click=${this._addViz}>+ ${i18n.getMessage('Add visualization')}</button>
      <button class="aiux-btn aiux-btn-ghost aiux-btn-sm" @click=${this._openBoardForm}>${i18n.getMessage('Dashboard settings')}</button>
      <button class="aiux-btn aiux-btn-ghost aiux-btn-sm" ?disabled=${this._saving} @click=${this._cancelEdit}>
        ${i18n.getMessage('Cancel')}
      </button>
      <button class="aiux-btn aiux-btn-primary aiux-btn-sm" ?disabled=${this._saving} @click=${this._save}>
        ${this._saving ? i18n.getMessage('Saving') : i18n.getMessage('Save')}
      </button>
    `;
  }

  _renderPanel() {
    if (!this._edit || !this._selectedKey) return nothing;
    const item = this._items.find(i => i.key === this._selectedKey);
    if (!item) return nothing;
    return html`<div
      class="fixed inset-0 z-40 border-base-300 bg-base-100 shadow-xl lg:static lg:inset-auto lg:z-auto lg:w-96 lg:shrink-0 lg:rounded-lg lg:border lg:shadow-sm"
    >
      <x-dash-viz-panel
        class="lg:sticky lg:top-4 lg:max-h-[calc(100vh-6rem)]"
        .chart=${item.chart}
        .tables=${this._tables}
        .fields=${this._fields[item.chart.source_table] || []}
        ?fields-loading=${this._fieldsLoading}
        @viz-change=${this._onVizChange}
        @viz-close=${() => (this._selectedKey = '')}
      ></x-dash-viz-panel>
    </div>`;
  }

  render() {
    if (this._loading && !this._board) {
      return html`<div class="p-6" role="status">
        <div class="aiux-skeleton mb-4 h-8 w-64 rounded"></div>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div class="aiux-skeleton h-64 rounded"></div>
          <div class="aiux-skeleton h-64 rounded"></div>
        </div>
        <span class="sr-only">${i18n.getMessage('Loading dashboard')}</span>
      </div>`;
    }
    if (this._error) {
      return html`<div class="p-6">
        <div class="aiux-alert aiux-alert-error aiux-alert-soft" role="alert">
          <span>${this._error}</span>
          <button class="aiux-btn aiux-btn-sm aiux-btn-ghost" @click=${this._load}>${i18n.getMessage('Try again')}</button>
        </div>
      </div>`;
    }
    const b = this._board;
    return html`
      <div class="flex flex-col gap-4 p-4 lg:p-6 ${this._edit ? 'editing' : ''}">
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <button class="aiux-btn aiux-btn-ghost aiux-btn-xs mb-1" @click=${() => navigate('/home')}>
              ← ${i18n.getMessage('All dashboards')}
            </button>
            <h1 class="break-words text-2xl font-bold text-text-primary">${b.name}</h1>
            ${b.description ? html`<p class="break-words text-sm text-text-secondary">${b.description}</p>` : nothing}
          </div>
          <div class="flex flex-wrap items-center gap-2">${this._renderToolbar()}</div>
        </header>

        ${this._edit
          ? html`<div class="aiux-alert aiux-alert-info aiux-alert-soft text-sm">
              ${i18n.getMessage('Edit mode: drag a visualization to move it, drag a corner to resize it, and select Configure to change it. Select Save to keep your changes.')}
            </div>`
          : nothing}
        ${this._saveError
          ? html`<div class="aiux-alert aiux-alert-error aiux-alert-soft text-sm" role="alert">${this._saveError}</div>`
          : nothing}

        <div class="flex items-start gap-4">
          <div
            class="min-w-0 flex-1"
            @tile-configure=${e => this._select(e.detail.key)}
            @tile-duplicate=${e => this._duplicate(e.detail.key)}
            @tile-remove=${e => this._remove(e.detail.key)}
          >
            ${!this._items.length
              ? html`<div class="mb-2 rounded-lg border border-dashed border-base-300 bg-base-100 p-6 text-center">
                  <p class="text-text-secondary">${i18n.getMessage('This dashboard has no visualizations yet.')}</p>
                  ${this._canEdit
                    ? html`<button
                        class="aiux-btn aiux-btn-primary aiux-btn-sm mt-3"
                        @click=${() => {
                          if (!this._edit) this._startEdit();
                          this._addViz();
                        }}
                      >
                        + ${i18n.getMessage('Add visualization')}
                      </button>`
                    : nothing}
                </div>`
              : nothing}
            <div class="grid-stack"></div>
          </div>
          ${this._renderPanel()}
        </div>
      </div>

      <dialog id="board-form" class="aiux-modal" aria-labelledby="board-form-title" @close=${() => (this._boardForm = null)}>
        <div class="aiux-modal-box">
          <h2 id="board-form-title" class="mb-4 text-lg font-bold">${i18n.getMessage('Dashboard settings')}</h2>
          ${this._renderBoardForm()}
        </div>
      </dialog>

      <div class="sr-only" role="status" aria-live="polite">${this._toast}</div>
      ${this._toast
        ? html`<div class="aiux-toast aiux-toast-bottom aiux-toast-center z-50" aria-hidden="true">
            <div class="aiux-alert aiux-alert-info aiux-alert-soft">${this._toast}</div>
          </div>`
        : nothing}
    `;
  }
}
