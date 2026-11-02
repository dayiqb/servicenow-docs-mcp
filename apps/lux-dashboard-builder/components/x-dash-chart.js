import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import '@servicenow/aiux/aiux-components-visualizations-axis';
import '@servicenow/aiux/aiux-components-visualizations-composition';
import '@servicenow/aiux/aiux-components-visualizations-score';
import '@servicenow/aiux/aiux-components-visualizations-matrix';

const AXIS_TYPES = {column: 'column', bar: 'bar', stacked: 'column', line: 'line', area: 'area'};

/**
 * Draws one chart result from the query engine.
 * Uses the official Lux visualization components.
 * Properties: run (engine result), chartType, height (px).
 */
@customElement('x-dash-chart')
export class DashChart extends AIUXElement {
  static properties = {
    run: {type: Object, attribute: false},
    chartType: {type: String, attribute: 'chart-type'},
    height: {type: Number},
    loading: {type: Boolean},
    filterValue: {type: String, attribute: false}
  };

  static styles = css`
    :host {
      display: block;
      width: 100%;
    }
  `;

  constructor() {
    super();
    this.run = null;
    this.chartType = 'column';
    this.height = 260;
    this.loading = false;
    this.filterValue = '';
  }

  _renderViz(result) {
    const t = this.chartType;
    const data = result.data;
    const style = 'display:block;width:100%;height:100%;';
    if (t === 'score') {
      return html`<aiux-visualizations-score style=${style} .data=${data}></aiux-visualizations-score>`;
    }
    if (t === 'pie' || t === 'donut') {
      return html`<aiux-visualizations-composition
        style=${style}
        type=${t}
        .data=${data}
        .legend=${{visible: true, position: 'bottom'}}
      ></aiux-visualizations-composition>`;
    }
    if (t === 'heatmap') {
      return html`<aiux-visualizations-matrix style=${style} type="heatmap" .data=${data}></aiux-visualizations-matrix>`;
    }
    const axes = {xAxis: {column: 'd1'}, yAxis: [{columns: ['value']}]};
    if (t === 'stacked') axes.stacking = {column: 'd2'};
    return html`<aiux-visualizations-axis
      style=${style}
      type=${AXIS_TYPES[t] || 'column'}
      .data=${data}
      .axes=${axes}
      .legend=${{visible: t === 'stacked', position: 'bottom'}}
      .tooltip=${{enabled: true}}
    ></aiux-visualizations-axis>`;
  }

  _renderList(result) {
    if (!result.rows.length) return this._renderEmpty();
    return html`
      <div class="h-full overflow-auto">
        <table class="aiux-table aiux-table-sm w-full">
          <thead>
            <tr>
              ${result.columns.map(c => html`<th scope="col">${c.label}</th>`)}
            </tr>
          </thead>
          <tbody>
            ${result.rows.map(
              r => html`<tr>
                ${r.cells.map(cell => html`<td class="break-words">${cell}</td>`)}
              </tr>`
            )}
          </tbody>
        </table>
      </div>
    `;
  }

  _renderFilter(result) {
    return html`<select
      class="aiux-select w-full"
      aria-label=${i18n.getMessage('Filter')}
      @change=${e => {
        const option = e.target.selectedOptions[0];
        this.dispatchEvent(
          new CustomEvent('x-dash-filter-change', {
            detail: {value: e.target.value, label: option ? option.textContent.trim() : ''}
          })
        );
      }}
    >
      <option value="" ?selected=${!this.filterValue}>${i18n.getMessage('All')}</option>
      ${result.options.map(o => html`<option value=${o.value} ?selected=${o.value === this.filterValue}>${o.label}</option>`)}
    </select>`;
  }

  _renderEmpty() {
    return html`<div class="flex h-full items-center justify-center text-sm text-text-secondary">
      ${i18n.getMessage('No data matches this filter')}
    </div>`;
  }

  _renderNotes(result) {
    const notes = [];
    if (result.truncated) {
      notes.push(i18n.getMessage('Counted the first 10,000 records only.'));
    }
    if (result.folded) {
      notes.push(i18n.getMessage('Shows the largest groups only.'));
    }
    if (!notes.length) return nothing;
    return html`<p class="mt-1 text-xs text-text-tertiary">${notes.join(' ')}</p>`;
  }

  render() {
    const h = `height:${this.height}px;`;
    if (this.loading) {
      return html`<div style=${h} role="status" aria-live="polite">
        <div class="aiux-skeleton h-full w-full rounded"></div>
        <span class="sr-only">${i18n.getMessage('Loading chart')}</span>
      </div>`;
    }
    const run = this.run;
    if (!run) return html`<div style=${h}></div>`;
    if (!run.ok) {
      return html`<div style=${h} class="flex items-center justify-center p-2">
        <div class="aiux-alert aiux-alert-warning aiux-alert-soft text-sm" role="alert">
          ${run.reason || i18n.getMessage('You cannot see this data')}
        </div>
      </div>`;
    }
    const result = run.result;
    if (result.kind === 'filter') return this._renderFilter(result);
    const body =
      result.kind === 'list'
        ? this._renderList(result)
        : result.empty
          ? this._renderEmpty()
          : this._renderViz(result);
    return html`<div style=${h}>${body}</div>
      ${result.kind === 'viz' ? this._renderNotes(result) : nothing}`;
  }
}
