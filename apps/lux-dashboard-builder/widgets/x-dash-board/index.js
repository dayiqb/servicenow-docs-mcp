import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';
import {
  AIUXWidgetElement,
  decorators
} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {navigate} from '@servicenow/aiux/aiux-client';
import '@servicenow/aiux/aiux-components-condition-builder';
import '../../components/x-dash-chart.js';

const {name, description, bestFor, chatCompatible, category, server, discoverable} = decorators;

const CHART_TYPES = [
  {id: 'score', label: () => i18n.getMessage('Single score'), group: 0},
  {id: 'column', label: () => i18n.getMessage('Vertical bar'), group: 1},
  {id: 'bar', label: () => i18n.getMessage('Horizontal bar'), group: 1},
  {id: 'stacked', label: () => i18n.getMessage('Stacked bar'), group: 2},
  {id: 'line', label: () => i18n.getMessage('Line'), group: 1},
  {id: 'area', label: () => i18n.getMessage('Area'), group: 1},
  {id: 'pie', label: () => i18n.getMessage('Pie'), group: 1},
  {id: 'donut', label: () => i18n.getMessage('Donut'), group: 1},
  {id: 'heatmap', label: () => i18n.getMessage('Heat map'), group: 2},
  {id: 'list', label: () => i18n.getMessage('List'), group: 0}
];
const AGGREGATES = [
  {id: 'COUNT', label: () => i18n.getMessage('Count')},
  {id: 'SUM', label: () => i18n.getMessage('Sum')},
  {id: 'AVG', label: () => i18n.getMessage('Average')},
  {id: 'MIN', label: () => i18n.getMessage('Minimum')},
  {id: 'MAX', label: () => i18n.getMessage('Maximum')}
];
const TRENDS = [
  {id: 'none', label: () => i18n.getMessage('None')},
  {id: 'Day', label: () => i18n.getMessage('Day')},
  {id: 'Week', label: () => i18n.getMessage('Week')},
  {id: 'Month', label: () => i18n.getMessage('Month')},
  {id: 'Quarter', label: () => i18n.getMessage('Quarter')},
  {id: 'Year', label: () => i18n.getMessage('Year')}
];
const WIDTH_CLASS = {
  1: 'md:col-span-1 xl:col-span-1',
  2: 'md:col-span-2 xl:col-span-2',
  3: 'md:col-span-2 xl:col-span-3',
  4: 'md:col-span-2 xl:col-span-4'
};

function newChart(tables) {
  return {
    sys_id: '',
    title: '',
    source_table: tables?.[0]?.name || '',
    query: '',
    group_by: '',
    group_by_2: '',
    aggregate: 'COUNT',
    aggregate_field: '',
    chart_type: 'column',
    trend: 'none',
    list_fields: '',
    max_groups: 10,
    width: 2
  };
}

@customElement('x-dash-board')
@name('Dashboard')
@description('Shows one dashboard with its charts. Owners can add, change, move, and remove charts.')
@bestFor('Viewing and building a no-code dashboard of charts on ServiceNow tables.')
@chatCompatible(false)
@category('custom')
@server('./server-script.js')
@discoverable(true)
export default class DashBoard extends AIUXWidgetElement {
  static properties = {
    dashboardId: {type: String, attribute: 'dashboard-id'},
    _board: {state: true},
    _charts: {state: true},
    _runs: {state: true},
    _canEdit: {state: true},
    _tables: {state: true},
    _editMode: {state: true},
    _loading: {state: true},
    _error: {state: true},
    _editor: {state: true},
    _fields: {state: true},
    _preview: {state: true},
    _previewLoading: {state: true},
    _editorError: {state: true},
    _saving: {state: true},
    _boardForm: {state: true},
    _toast: {state: true}
  };

  static styles = css`
    :host {
      display: block;
      min-height: 100%;
      container-type: inline-size;
    }
  `;

  constructor() {
    super();
    this.dashboardId = '';
    this._board = null;
    this._charts = [];
    this._runs = {};
    this._canEdit = false;
    this._tables = [];
    this._editMode = false;
    this._loading = true;
    this._error = '';
    this._editor = null;
    this._fields = [];
    this._preview = null;
    this._previewLoading = false;
    this._editorError = '';
    this._saving = false;
    this._boardForm = null;
    this._toast = '';
    this._previewTimer = null;
    this._layoutTimer = null;
    this._toastTimer = null;
    this._fetching = false;
  }

  updated(changed) {
    if (changed.has('dashboardId') && this.dashboardId) this._load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._previewTimer);
    clearTimeout(this._layoutTimer);
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
    this._toastTimer = setTimeout(() => {
      this._toast = '';
    }, 4000);
  }

  /* ------------------------------------------------------------ loading */

  async _load() {
    if (this._fetching) return;
    this._fetching = true;
    this._loading = true;
    this._error = '';
    try {
      const res = await this._call({action: 'getBoard'});
      this._board = res.dashboard;
      this._charts = res.charts || [];
      this._canEdit = !!res.canEdit;
      this._tables = res.tables || [];
      this._runs = {};
      this._charts.forEach(c => this._runChart(c.sys_id));
    } catch (e) {
      this._error = e.message;
    } finally {
      this._loading = false;
      this._fetching = false;
    }
  }

  async _runChart(id) {
    this._runs = {...this._runs, [id]: {loading: true}};
    try {
      const res = await this._call({action: 'runChart', chartId: id});
      this._runs = {...this._runs, [id]: {run: res.run}};
    } catch (e) {
      this._runs = {...this._runs, [id]: {run: {ok: false, reason: e.message}}};
    }
  }

  /* ------------------------------------------------------------- layout */

  _move(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= this._charts.length) return;
    const list = [...this._charts];
    const [item] = list.splice(index, 1);
    list.splice(target, 0, item);
    this._charts = list;
    this._queueLayout();
    this._say(i18n.getMessage('Chart moved'));
  }

  _setWidth(index, width) {
    const list = [...this._charts];
    list[index] = {...list[index], width};
    this._charts = list;
    this._queueLayout();
  }

  _queueLayout() {
    clearTimeout(this._layoutTimer);
    this._layoutTimer = setTimeout(async () => {
      try {
        await this._call({
          action: 'saveLayout',
          items: this._charts.map(c => ({id: c.sys_id, width: c.width}))
        });
      } catch (e) {
        this._say(e.message);
      }
    }, 600);
  }

  async _deleteChart(chart) {
    if (!globalThis.confirm?.(i18n.getMessage('Remove this chart?'))) return;
    try {
      await this._call({action: 'deleteChart', chartId: chart.sys_id});
      this._charts = this._charts.filter(c => c.sys_id !== chart.sys_id);
      this._say(i18n.getMessage('Chart removed'));
    } catch (e) {
      this._say(e.message);
    }
  }

  /* ------------------------------------------------------------- editor */

  async _openEditor(chart) {
    this._editor = chart ? {...chart} : newChart(this._tables);
    this._preview = null;
    this._editorError = '';
    this._fields = [];
    await this.updateComplete;
    this.renderRoot.querySelector('#chart-editor')?.showModal();
    if (this._editor.source_table) await this._loadFields(this._editor.source_table);
    this._queuePreview();
  }

  _closeEditor() {
    this.renderRoot.querySelector('#chart-editor')?.close();
    this._editor = null;
    this._preview = null;
  }

  async _loadFields(table) {
    try {
      const res = await this._call({action: 'getFields', table});
      this._fields = res.fields || [];
    } catch (e) {
      this._fields = [];
      this._editorError = e.message;
    }
  }

  _set(key, value) {
    const next = {...this._editor, [key]: value};
    if (key === 'source_table') {
      next.query = '';
      next.group_by = '';
      next.group_by_2 = '';
      next.aggregate_field = '';
      next.list_fields = '';
      this._loadFields(value).then(() => this._queuePreview());
    }
    if (key === 'aggregate' && value === 'COUNT') next.aggregate_field = '';
    this._editor = next;
    this._editorError = '';
    if (key !== 'source_table' && key !== 'title' && key !== 'width') this._queuePreview();
  }

  _queuePreview() {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(() => this._runPreview(), 500);
  }

  async _runPreview() {
    if (!this._editor) return;
    this._previewLoading = true;
    try {
      const res = await this._call({action: 'previewChart', chart: this._editor});
      this._preview = res.run;
    } catch (e) {
      this._preview = {ok: false, reason: e.message};
    } finally {
      this._previewLoading = false;
    }
  }

  async _saveEditor(e) {
    e.preventDefault();
    if (this._saving) return;
    this._saving = true;
    this._editorError = '';
    try {
      const res = await this._call({action: 'saveChart', chart: this._editor});
      const isNew = !this._editor.sys_id;
      this._closeEditor();
      await this._load();
      this._say(isNew ? i18n.getMessage('Chart added') : i18n.getMessage('Chart saved'));
      return res;
    } catch (err) {
      this._editorError = err.message;
    } finally {
      this._saving = false;
    }
    return null;
  }

  /* ------------------------------------------------------ board settings */

  async _openBoardForm() {
    this._boardForm = {
      name: this._board.name,
      description: this._board.description,
      shared: this._board.shared
    };
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
      this._say(i18n.getMessage('Dashboard saved'));
    } catch (err) {
      this._say(err.message);
    }
  }

  async _deleteBoard() {
    if (!globalThis.confirm?.(i18n.getMessage('Delete this dashboard and all its charts?'))) return;
    try {
      await this._call({action: 'deleteBoard'});
      navigate('/home');
    } catch (err) {
      this._say(err.message);
    }
  }

  /* ------------------------------------------------------------- render */

  _fieldOptions(filter, selected) {
    return this._fields
      .filter(filter)
      .map(
        f => html`<option value=${f.name} ?selected=${f.name === selected}>${f.label} (${f.name})</option>`
      );
  }

  _renderEditor() {
    const c = this._editor;
    if (!c) return nothing;
    const type = CHART_TYPES.find(t => t.id === c.chart_type) || CHART_TYPES[1];
    const groupField = this._fields.find(f => f.name === c.group_by);
    const listSelected = c.list_fields ? c.list_fields.split(',') : [];
    return html`
      <form class="flex flex-col gap-4 lg:flex-row" aria-label=${i18n.getMessage('Chart settings')} @submit=${this._saveEditor}>
        <div class="flex min-w-0 flex-col gap-3 lg:w-1/2">
          <label class="aiux-fieldset">
            <span class="aiux-label">${i18n.getMessage('Title')}</span>
            <input
              class="aiux-input w-full"
              .value=${c.title}
              maxlength="100"
              @input=${e => this._set('title', e.target.value)}
            />
          </label>
          <label class="aiux-fieldset">
            <span class="aiux-label">${i18n.getMessage('Table')}</span>
            <select class="aiux-select w-full" @change=${e => this._set('source_table', e.target.value)}>
              ${this._tables.map(
                t => html`<option value=${t.name} ?selected=${t.name === c.source_table}>${t.label} (${t.name})</option>`
              )}
            </select>
          </label>
          <label class="aiux-fieldset">
            <span class="aiux-label">${i18n.getMessage('Chart type')}</span>
            <select class="aiux-select w-full" @change=${e => this._set('chart_type', e.target.value)}>
              ${CHART_TYPES.map(
                t => html`<option value=${t.id} ?selected=${t.id === c.chart_type}>${t.label()}</option>`
              )}
            </select>
          </label>
          ${type.group >= 1
            ? html`<label class="aiux-fieldset">
                <span class="aiux-label">${i18n.getMessage('Group by')}</span>
                <select class="aiux-select w-full" @change=${e => this._set('group_by', e.target.value)}>
                  <option value="" ?selected=${!c.group_by}>${i18n.getMessage('Pick a field')}</option>
                  ${this._fieldOptions(f => f.groupable, c.group_by)}
                </select>
              </label>`
            : nothing}
          ${type.group >= 1 && groupField?.date
            ? html`<label class="aiux-fieldset">
                <span class="aiux-label">${i18n.getMessage('Date trend')}</span>
                <select class="aiux-select w-full" @change=${e => this._set('trend', e.target.value)}>
                  ${TRENDS.map(
                    t => html`<option value=${t.id} ?selected=${t.id === c.trend}>${t.label()}</option>`
                  )}
                </select>
              </label>`
            : nothing}
          ${type.group === 2
            ? html`<label class="aiux-fieldset">
                <span class="aiux-label">${i18n.getMessage('Second group by')}</span>
                <select class="aiux-select w-full" @change=${e => this._set('group_by_2', e.target.value)}>
                  <option value="" ?selected=${!c.group_by_2}>${i18n.getMessage('Pick a field')}</option>
                  ${this._fieldOptions(f => f.groupable, c.group_by_2)}
                </select>
              </label>`
            : nothing}
          ${c.chart_type !== 'list'
            ? html`<div class="flex gap-2">
                <label class="aiux-fieldset w-1/2">
                  <span class="aiux-label">${i18n.getMessage('Aggregate')}</span>
                  <select class="aiux-select w-full" @change=${e => this._set('aggregate', e.target.value)}>
                    ${AGGREGATES.map(
                      a => html`<option value=${a.id} ?selected=${a.id === c.aggregate}>${a.label()}</option>`
                    )}
                  </select>
                </label>
                ${c.aggregate !== 'COUNT'
                  ? html`<label class="aiux-fieldset w-1/2">
                      <span class="aiux-label">${i18n.getMessage('Number field')}</span>
                      <select class="aiux-select w-full" @change=${e => this._set('aggregate_field', e.target.value)}>
                        <option value="" ?selected=${!c.aggregate_field}>${i18n.getMessage('Pick a field')}</option>
                        ${this._fieldOptions(f => f.numeric, c.aggregate_field)}
                      </select>
                    </label>`
                  : nothing}
              </div>`
            : html`<fieldset class="aiux-fieldset">
                <legend class="aiux-label">${i18n.getMessage('Columns (up to 6)')}</legend>
                <select
                  class="aiux-select h-32 w-full"
                  multiple
                  aria-label=${i18n.getMessage('Columns')}
                  @change=${e =>
                    this._set(
                      'list_fields',
                      [...e.target.selectedOptions].slice(0, 6).map(o => o.value).join(',')
                    )}
                >
                  ${this._fields.map(
                    f => html`<option value=${f.name} ?selected=${listSelected.includes(f.name)}>${f.label}</option>`
                  )}
                </select>
              </fieldset>`}
          ${type.group >= 1
            ? html`<label class="aiux-fieldset">
                <span class="aiux-label">${i18n.getMessage('Max number of groups')}</span>
                <input
                  class="aiux-input w-full"
                  type="number"
                  min="1"
                  max="50"
                  .value=${String(c.max_groups)}
                  @change=${e => this._set('max_groups', parseInt(e.target.value, 10) || 10)}
                />
              </label>`
            : nothing}
          <label class="aiux-fieldset">
            <span class="aiux-label">${i18n.getMessage('Width')}</span>
            <select class="aiux-select w-full" @change=${e => this._set('width', parseInt(e.target.value, 10))}>
              ${[1, 2, 3, 4].map(
                w => html`<option value=${w} ?selected=${w === c.width}>${i18n.getMessage('{0} of 4 columns', [w])}</option>`
              )}
            </select>
          </label>
        </div>
        <div class="flex min-w-0 flex-col gap-3 lg:w-1/2">
          <div
            class="rounded-lg border border-base-300 p-3"
            @cb-encoded-query-updated=${e => {
              e.preventDefault?.();
              this._set('query', e.detail?.encodedQuery || '');
            }}
          >
            <p class="aiux-label mb-2">${i18n.getMessage('Filter')}</p>
            ${c.source_table
              ? html`<aiux-condition-builder
                  .tableName=${c.source_table}
                  .encodedQuery=${c.query}
                ></aiux-condition-builder>`
              : nothing}
          </div>
          <section class="rounded-lg border border-base-300 p-3" aria-label=${i18n.getMessage('Preview')}>
            <p class="aiux-label mb-2">${i18n.getMessage('Preview')}</p>
            <x-dash-chart
              .run=${this._preview}
              chart-type=${c.chart_type}
              .loading=${this._previewLoading}
              height="240"
            ></x-dash-chart>
          </section>
          ${this._editorError
            ? html`<div class="aiux-alert aiux-alert-error aiux-alert-soft text-sm" role="alert">${this._editorError}</div>`
            : nothing}
          <div class="flex justify-end gap-2">
            <button type="button" class="aiux-btn aiux-btn-ghost" @click=${this._closeEditor}>
              ${i18n.getMessage('Cancel')}
            </button>
            <button type="submit" class="aiux-btn aiux-btn-primary" ?disabled=${this._saving}>
              ${this._saving ? html`<span class="aiux-loading aiux-loading-spinner aiux-loading-xs"></span>` : nothing}
              ${i18n.getMessage('Save chart')}
            </button>
          </div>
        </div>
      </form>
    `;
  }

  _renderBoardForm() {
    const f = this._boardForm;
    if (!f) return nothing;
    return html`<form class="flex flex-col gap-3" aria-label=${i18n.getMessage('Dashboard settings')} @submit=${this._saveBoardForm}>
      <label class="aiux-fieldset">
        <span class="aiux-label">${i18n.getMessage('Name')}</span>
        <input
          class="aiux-input w-full"
          required
          maxlength="100"
          .value=${f.name}
          @input=${e => (this._boardForm = {...f, name: e.target.value})}
        />
      </label>
      <label class="aiux-fieldset">
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
          <button type="button" class="aiux-btn aiux-btn-ghost" @click=${this._closeBoardForm}>
            ${i18n.getMessage('Cancel')}
          </button>
          <button type="submit" class="aiux-btn aiux-btn-primary">${i18n.getMessage('Save')}</button>
        </div>
      </div>
    </form>`;
  }

  _renderCard(chart, index) {
    const state = this._runs[chart.sys_id] || {loading: true};
    const title = chart.title || i18n.getMessage('Untitled chart');
    return html`
      <article
        class="aiux-card col-span-1 border border-base-300 bg-base-100 shadow-sm ${WIDTH_CLASS[chart.width] || WIDTH_CLASS[2]}"
        aria-label=${title}
      >
        <div class="aiux-card-body gap-2 p-4">
          <div class="flex items-start justify-between gap-2">
            <h2 class="aiux-card-title min-w-0 break-words text-base">${title}</h2>
            ${this._editMode
              ? html`<div class="flex flex-wrap justify-end gap-1">
                  <button
                    class="aiux-btn aiux-btn-ghost aiux-btn-xs"
                    aria-label=${i18n.getMessage('Move {0} earlier', [title])}
                    ?disabled=${index === 0}
                    @click=${() => this._move(index, -1)}
                  >
                    ←
                  </button>
                  <button
                    class="aiux-btn aiux-btn-ghost aiux-btn-xs"
                    aria-label=${i18n.getMessage('Move {0} later', [title])}
                    ?disabled=${index === this._charts.length - 1}
                    @click=${() => this._move(index, 1)}
                  >
                    →
                  </button>
                  <select
                    class="aiux-select aiux-select-xs w-auto"
                    aria-label=${i18n.getMessage('Width of {0}', [title])}
                    @change=${e => this._setWidth(index, parseInt(e.target.value, 10))}
                  >
                    ${[1, 2, 3, 4].map(w => html`<option value=${w} ?selected=${w === chart.width}>${w}/4</option>`)}
                  </select>
                  <button class="aiux-btn aiux-btn-ghost aiux-btn-xs" @click=${() => this._openEditor(chart)}>
                    ${i18n.getMessage('Edit')}
                  </button>
                  <button class="aiux-btn aiux-btn-ghost aiux-btn-xs text-error" @click=${() => this._deleteChart(chart)}>
                    ${i18n.getMessage('Remove')}
                  </button>
                </div>`
              : nothing}
          </div>
          <x-dash-chart
            .run=${state.run}
            .loading=${!!state.loading}
            chart-type=${chart.chart_type}
            height=${chart.chart_type === 'score' ? 140 : 260}
          ></x-dash-chart>
        </div>
      </article>
    `;
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
          <button class="aiux-btn aiux-btn-sm aiux-btn-ghost" @click=${this._load}>${i18n.getMessage('Retry')}</button>
        </div>
      </div>`;
    }
    const b = this._board;
    return html`
      <div class="mx-auto flex max-w-screen-2xl flex-col gap-4 p-4 lg:p-6">
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <button class="aiux-btn aiux-btn-ghost aiux-btn-xs mb-1" @click=${() => navigate('/home')}>
              ← ${i18n.getMessage('All dashboards')}
            </button>
            <h1 class="break-words text-2xl font-bold text-text-primary">${b.name}</h1>
            ${b.description ? html`<p class="break-words text-sm text-text-secondary">${b.description}</p>` : nothing}
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="aiux-btn aiux-btn-ghost aiux-btn-sm" @click=${this._load}>${i18n.getMessage('Refresh')}</button>
            ${this._canEdit
              ? this._editMode
                ? html`
                    <button class="aiux-btn aiux-btn-outline aiux-btn-sm" @click=${() => this._openEditor(null)}>
                      ${i18n.getMessage('Add chart')}
                    </button>
                    <button class="aiux-btn aiux-btn-outline aiux-btn-sm" @click=${this._openBoardForm}>
                      ${i18n.getMessage('Dashboard settings')}
                    </button>
                    <button class="aiux-btn aiux-btn-primary aiux-btn-sm" @click=${() => (this._editMode = false)}>
                      ${i18n.getMessage('Done')}
                    </button>
                  `
                : html`<button class="aiux-btn aiux-btn-primary aiux-btn-sm" @click=${() => (this._editMode = true)}>
                    ${i18n.getMessage('Edit')}
                  </button>`
              : nothing}
          </div>
        </header>

        ${this._charts.length
          ? html`<div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              ${repeat(
                this._charts,
                c => c.sys_id,
                (c, i) => this._renderCard(c, i)
              )}
            </div>`
          : html`<div class="aiux-card border border-dashed border-base-300 bg-base-100">
              <div class="aiux-card-body items-center text-center">
                <p class="text-text-secondary">${i18n.getMessage('This dashboard has no charts yet.')}</p>
                ${this._canEdit
                  ? html`<button class="aiux-btn aiux-btn-primary" @click=${() => {
                      this._editMode = true;
                      this._openEditor(null);
                    }}>
                      ${i18n.getMessage('Add chart')}
                    </button>`
                  : nothing}
              </div>
            </div>`}
      </div>

      <dialog
        id="chart-editor"
        class="aiux-modal"
        aria-labelledby="chart-editor-title"
        @close=${() => (this._editor = null)}
      >
        <div class="aiux-modal-box w-11/12 max-w-6xl">
          <h2 id="chart-editor-title" class="mb-4 text-lg font-bold">
            ${this._editor?.sys_id ? i18n.getMessage('Edit chart') : i18n.getMessage('Add chart')}
          </h2>
          ${this._renderEditor()}
        </div>
      </dialog>

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
