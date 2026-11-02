import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import '@servicenow/aiux/aiux-components-condition-builder';

/**
 * Visualization types, in the order of the gallery.
 * groups: 0 = no group by, 1 = one group by, 2 = two group by fields.
 */
export const VIZ_TYPES = [
  {id: 'score', groups: 0, icon: '123', label: () => i18n.getMessage('Single score')},
  {id: 'column', groups: 1, icon: '▮▮▮', label: () => i18n.getMessage('Vertical bar')},
  {id: 'bar', groups: 1, icon: '☰', label: () => i18n.getMessage('Horizontal bar')},
  {id: 'stacked', groups: 2, icon: '▤', label: () => i18n.getMessage('Stacked bar')},
  {id: 'line', groups: 1, icon: '⟋', label: () => i18n.getMessage('Line')},
  {id: 'area', groups: 1, icon: '◭', label: () => i18n.getMessage('Area')},
  {id: 'pie', groups: 1, icon: '◔', label: () => i18n.getMessage('Pie')},
  {id: 'donut', groups: 1, icon: '◎', label: () => i18n.getMessage('Donut')},
  {id: 'heatmap', groups: 2, icon: '▦', label: () => i18n.getMessage('Heat map')},
  {id: 'list', groups: 0, icon: '≣', label: () => i18n.getMessage('List')}
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

/**
 * Side panel to configure one visualization, like the Platform Analytics
 * configuration panel: visualization type, data source, filter, metric,
 * group by, and display options.
 *
 * Properties: chart (definition), tables, fields, fieldsLoading.
 * Events: viz-change (detail: {key, value}), viz-close.
 */
@customElement('x-dash-viz-panel')
export class DashVizPanel extends AIUXElement {
  static properties = {
    chart: {type: Object, attribute: false},
    tables: {type: Array, attribute: false},
    fields: {type: Array, attribute: false},
    fieldsLoading: {type: Boolean, attribute: 'fields-loading'}
  };

  static styles = css`
    :host {
      display: block;
      height: 100%;
    }
  `;

  constructor() {
    super();
    this.chart = null;
    this.tables = [];
    this.fields = [];
    this.fieldsLoading = false;
  }

  _set(key, value) {
    this.dispatchEvent(new CustomEvent('viz-change', {detail: {key, value}, bubbles: true, composed: true}));
  }

  _close() {
    this.dispatchEvent(new CustomEvent('viz-close', {bubbles: true, composed: true}));
  }

  _options(filter, selected) {
    return (this.fields || [])
      .filter(filter)
      .map(f => html`<option value=${f.name} ?selected=${f.name === selected}>${f.label}</option>`);
  }

  _fieldSelect(id, label, key, filter) {
    const c = this.chart;
    return html`<div class="flex flex-col gap-1">
      <label class="aiux-label text-sm" for=${id}>${label}</label>
      <select
        id=${id}
        class="aiux-select aiux-select-sm w-full"
        ?disabled=${this.fieldsLoading}
        @change=${e => this._set(key, e.target.value)}
      >
        <option value="" ?selected=${!c[key]}>${i18n.getMessage('Select a field')}</option>
        ${this._options(filter, c[key])}
      </select>
    </div>`;
  }

  _section(title, body) {
    return html`<section class="flex flex-col gap-3 border-b border-base-300 px-4 py-4" aria-label=${title}>
      <h3 class="text-sm font-semibold text-text-primary">${title}</h3>
      ${body}
    </section>`;
  }

  _renderGallery() {
    const c = this.chart;
    return html`<div class="grid grid-cols-5 gap-2" role="group" aria-label=${i18n.getMessage('Visualization type')}>
      ${VIZ_TYPES.map(
        t => html`<button
          type="button"
          class="flex flex-col items-center gap-1 rounded-lg border p-2 text-xs ${t.id === c.chart_type
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-base-300 text-text-secondary hover:bg-base-200'}"
          aria-pressed=${t.id === c.chart_type ? 'true' : 'false'}
          title=${t.label()}
          @click=${() => this._set('chart_type', t.id)}
        >
          <span class="text-lg leading-none" aria-hidden="true">${t.icon}</span>
          <span class="w-full truncate text-center">${t.label()}</span>
        </button>`
      )}
    </div>`;
  }

  _renderData() {
    const c = this.chart;
    return html`
      <div class="flex flex-col gap-1">
        <label class="aiux-label text-sm" for="viz-table">${i18n.getMessage('Data source (table)')}</label>
        <select id="viz-table" class="aiux-select aiux-select-sm w-full" @change=${e => this._set('source_table', e.target.value)}>
          ${(this.tables || []).map(
            t => html`<option value=${t.name} ?selected=${t.name === c.source_table}>${t.label} (${t.name})</option>`
          )}
        </select>
      </div>
      <div
        class="flex flex-col gap-1"
        @cb-encoded-query-updated=${e => {
          e.stopPropagation();
          this._set('query', e.detail?.encodedQuery || '');
        }}
      >
        <span class="aiux-label text-sm">${i18n.getMessage('Filter')}</span>
        ${c.source_table
          ? html`<aiux-condition-builder .tableName=${c.source_table} .encodedQuery=${c.query || ''}></aiux-condition-builder>`
          : nothing}
      </div>
    `;
  }

  _renderMetric() {
    const c = this.chart;
    return html`
      <div class="flex flex-col gap-1">
        <label class="aiux-label text-sm" for="viz-agg">${i18n.getMessage('Aggregation')}</label>
        <select id="viz-agg" class="aiux-select aiux-select-sm w-full" @change=${e => this._set('aggregate', e.target.value)}>
          ${AGGREGATES.map(a => html`<option value=${a.id} ?selected=${a.id === c.aggregate}>${a.label()}</option>`)}
        </select>
      </div>
      ${c.aggregate !== 'COUNT'
        ? this._fieldSelect('viz-agg-field', i18n.getMessage('Number field'), 'aggregate_field', f => f.numeric)
        : nothing}
    `;
  }

  _renderGroups(type) {
    const c = this.chart;
    const groupField = (this.fields || []).find(f => f.name === c.group_by);
    return html`
      ${this._fieldSelect('viz-group', i18n.getMessage('Group by'), 'group_by', f => f.groupable)}
      ${type.groups === 2
        ? this._fieldSelect(
            'viz-group-2',
            c.chart_type === 'heatmap' ? i18n.getMessage('Second group by') : i18n.getMessage('Stack by'),
            'group_by_2',
            f => f.groupable
          )
        : nothing}
      ${groupField?.date && c.chart_type !== 'heatmap'
        ? html`<div class="flex flex-col gap-1">
            <label class="aiux-label text-sm" for="viz-trend">${i18n.getMessage('Trend by')}</label>
            <select id="viz-trend" class="aiux-select aiux-select-sm w-full" @change=${e => this._set('trend', e.target.value)}>
              ${TRENDS.map(t => html`<option value=${t.id} ?selected=${t.id === c.trend}>${t.label()}</option>`)}
            </select>
          </div>`
        : nothing}
      <div class="flex flex-col gap-1">
        <label class="aiux-label text-sm" for="viz-max">${i18n.getMessage('Maximum number of groups')}</label>
        <input
          id="viz-max"
          class="aiux-input aiux-input-sm w-full"
          type="number"
          min="1"
          max="50"
          .value=${String(c.max_groups || 10)}
          @change=${e => this._set('max_groups', parseInt(e.target.value, 10) || 10)}
        />
      </div>
    `;
  }

  _renderColumns() {
    const selected = this.chart.list_fields ? this.chart.list_fields.split(',') : [];
    return html`<div class="flex flex-col gap-1">
      <label class="aiux-label text-sm" for="viz-columns">${i18n.getMessage('Columns (up to 6)')}</label>
      <select
        id="viz-columns"
        class="aiux-select h-40 w-full"
        multiple
        ?disabled=${this.fieldsLoading}
        @change=${e =>
          this._set(
            'list_fields',
            [...e.target.selectedOptions]
              .slice(0, 6)
              .map(o => o.value)
              .join(',')
          )}
      >
        ${(this.fields || []).map(f => html`<option value=${f.name} ?selected=${selected.includes(f.name)}>${f.label}</option>`)}
      </select>
    </div>`;
  }

  render() {
    const c = this.chart;
    if (!c) return nothing;
    const type = VIZ_TYPES.find(t => t.id === c.chart_type) || VIZ_TYPES[1];
    return html`
      <aside class="flex h-full flex-col bg-base-100" aria-label=${i18n.getMessage('Configure visualization')}>
        <header class="flex items-center justify-between gap-2 border-b border-base-300 px-4 py-3">
          <h2 class="text-base font-semibold text-text-primary">${i18n.getMessage('Configure visualization')}</h2>
          <button type="button" class="aiux-btn aiux-btn-ghost aiux-btn-sm" @click=${this._close}>
            ${i18n.getMessage('Close')}
          </button>
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto">
          ${this._section(
            i18n.getMessage('Title'),
            html`<label class="sr-only" for="viz-title">${i18n.getMessage('Title')}</label>
              <input
                id="viz-title"
                class="aiux-input aiux-input-sm w-full"
                maxlength="100"
                .value=${c.title || ''}
                @input=${e => this._set('title', e.target.value)}
              />`
          )}
          ${this._section(i18n.getMessage('Visualization'), this._renderGallery())}
          ${this._section(i18n.getMessage('Data'), this._renderData())}
          ${c.chart_type === 'list'
            ? this._section(i18n.getMessage('Columns'), this._renderColumns())
            : this._section(i18n.getMessage('Metric'), this._renderMetric())}
          ${type.groups >= 1 ? this._section(i18n.getMessage('Group by'), this._renderGroups(type)) : nothing}
        </div>
      </aside>
    `;
  }
}
