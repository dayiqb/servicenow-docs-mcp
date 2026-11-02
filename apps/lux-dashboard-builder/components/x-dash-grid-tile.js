import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import './x-dash-chart.js';

/**
 * One chart on the dashboard canvas. The layout renderer creates this element
 * and sets its properties once, so it reads the current chart, run, and edit
 * state from the board. The board fires "x-dash-board-state" when they change.
 * The grid hashes item properties as JSON, so they hold only the chart ID. The
 * tile gets its board by firing "x-dash-tile-connect".
 * Properties: chartId, board.
 */
@customElement('x-dash-grid-tile')
export class DashGridTile extends AIUXElement {
  static properties = {
    chartId: {type: String, attribute: false},
    board: {type: Object, attribute: false},
    _height: {state: true}
  };

  static styles = css`
    :host {
      display: block;
      height: 100%;
    }
  `;

  constructor() {
    super();
    this.chartId = '';
    this.board = null;
    this._height = 200;
    this._refresh = () => this.requestUpdate();
  }

  connectedCallback() {
    super.connectedCallback();
    this.dispatchEvent(new CustomEvent('x-dash-tile-connect', {bubbles: true, composed: true}));
    this.board?.addEventListener('x-dash-board-state', this._refresh);
  }

  willUpdate(changed) {
    if (changed.has('board')) {
      changed.get('board')?.removeEventListener('x-dash-board-state', this._refresh);
      this.board?.addEventListener('x-dash-board-state', this._refresh);
    }
  }

  firstUpdated() {
    const body = this.renderRoot.querySelector('[data-tile-body]');
    if (!body) return;
    this._observer = new ResizeObserver(entries => {
      const next = Math.max(80, Math.floor(entries[0].contentRect.height) - 4);
      if (next !== this._height) this._height = next;
    });
    this._observer.observe(body);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._observer?.disconnect();
    this.board?.removeEventListener('x-dash-board-state', this._refresh);
  }

  // "Apply as filter": clicking a bar or slice filters the other charts.
  _onChartClick(e, chart) {
    if (!chart.apply_as_filter) return;
    const clicked = e.detail?.values?.d1;
    if (clicked === null || clicked === undefined) return;
    // The chart reports the label of the clicked group. The filter needs its value.
    const run = this.board.runFor(this.chartId).run;
    const elements = run?.result?.data?.metadata?.columns?.d1?.elements || [];
    const element = elements.find(el => el.label === String(clicked) || el.id === String(clicked));
    if (element) this.board.toggleFilter(chart, element.id, element.label);
  }

  render() {
    const chart = this.board?.chartById(this.chartId);
    if (!chart) return nothing;
    const state = this.board.runFor(this.chartId);
    const title = chart.title || i18n.getMessage('Untitled chart');
    return html`<article
      class="flex h-full flex-col gap-2 overflow-hidden rounded-lg border border-base-300 bg-base-100 p-3 shadow-sm"
      aria-label=${title}
    >
      <header>
        <h2 class="break-words pr-8 text-base font-semibold text-text-primary">${title}</h2>
      </header>
      <div class="min-h-0 grow" data-tile-body>
        <x-dash-chart
          .filterValue=${this.board.filterValue(chart)}
          @x-dash-filter-change=${e => this.board.setFilter(chart, e.detail.value, e.detail.label)}
          @visualization:click=${e => this._onChartClick(e, chart)}
          .run=${state.run}
          .loading=${!!state.loading}
          chart-type=${chart.chart_type}
          height=${this._height}
        ></x-dash-chart>
      </div>
    </article>`;
  }
}
