import {html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {
  AIUXWidgetElement,
  configProperty,
  decorators
} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import '../../components/x-dash-chart.js';

const {name, description, bestFor, chatCompatible, category, server, discoverable} =
  decorators;

const RUN_KEYS = [
  'sourceTable',
  'filter',
  'groupBy',
  'secondGroupBy',
  'aggregate',
  'aggregateField',
  'chartType',
  'dateTrend',
  'listFields',
  'maxGroups'
];

/**
 * One chart on the Lux canvas.
 * Set the chart in the canvas side panel. Each setting is a plain text field.
 * The server script checks every setting again as the current user.
 */
@customElement('x-dash-chart-widget')
@name('Chart')
@description(
  'Shows a chart of records from one table: a score, bar, line, area, pie, donut, heat map, or list.'
)
@bestFor('Dashboards that count or sum records by a field, such as incidents by priority.')
@chatCompatible(false)
@category('custom')
@server('./server-script.js')
@discoverable(true)
export default class DashChartWidget extends AIUXWidgetElement {
  @configProperty({type: String, label: i18n.getMessage('Chart title')})
  chartTitle = '';

  @configProperty({
    type: String,
    label: i18n.getMessage('Source table'),
    description: i18n.getMessage('Table name, for example incident')
  })
  sourceTable = 'incident';

  @configProperty({
    type: String,
    label: i18n.getMessage('Filter'),
    description: i18n.getMessage('Encoded query, for example active=true^priority=1')
  })
  filter = 'active=true';

  @configProperty({
    type: String,
    label: i18n.getMessage('Chart type'),
    description: i18n.getMessage(
      'score, column, bar, stacked, line, area, pie, donut, heatmap, or list'
    )
  })
  chartType = 'column';

  @configProperty({
    type: String,
    label: i18n.getMessage('Group by'),
    description: i18n.getMessage('Field name, for example priority')
  })
  groupBy = 'priority';

  @configProperty({
    type: String,
    label: i18n.getMessage('Second group by'),
    description: i18n.getMessage('Only for stacked and heatmap. Field name, for example state')
  })
  secondGroupBy = '';

  @configProperty({
    type: String,
    label: i18n.getMessage('Aggregate'),
    description: i18n.getMessage('COUNT, SUM, AVG, MIN, or MAX')
  })
  aggregate = 'COUNT';

  @configProperty({
    type: String,
    label: i18n.getMessage('Aggregate field'),
    description: i18n.getMessage('Number field for SUM, AVG, MIN, or MAX')
  })
  aggregateField = '';

  @configProperty({
    type: String,
    label: i18n.getMessage('Date trend'),
    description: i18n.getMessage(
      'none, day, week, month, quarter, or year. Group by must be a date field.'
    )
  })
  dateTrend = 'none';

  @configProperty({
    type: String,
    label: i18n.getMessage('List fields'),
    description: i18n.getMessage('Only for list. Comma-separated field names')
  })
  listFields = 'number,short_description,priority';

  @configProperty({
    type: Number,
    label: i18n.getMessage('Max groups'),
    description: i18n.getMessage('Largest groups to show. The rest is "Other".')
  })
  maxGroups = 10;

  static properties = {
    _run: {state: true},
    _loading: {state: true},
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
    this._run = null;
    this._loading = true;
    this._height = 240;
    this._timer = null;
    this._lastKey = '';
    this._seq = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this._resize = new ResizeObserver(entries => {
      const box = entries[0]?.contentRect;
      if (!box) return;
      // Leave room for the title and the note line.
      const h = Math.max(120, Math.floor(box.height) - 56);
      if (Math.abs(h - this._height) > 4) this._height = h;
    });
    this._resize.observe(this);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resize?.disconnect();
    clearTimeout(this._timer);
  }

  updated() {
    // Settings can change through properties or through the admin config.
    // Run the chart again only when a setting changed.
    const input = this._input();
    const key = JSON.stringify(input);
    if (key === this._lastKey) return;
    this._lastKey = key;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this._load(input), 400);
  }

  _input() {
    const input = {action: 'run', chartTitle: this.chartTitle};
    for (const k of RUN_KEYS) input[k] = this[k] ?? '';
    return input;
  }

  async _load(input) {
    const seq = ++this._seq;
    this._loading = true;
    let run;
    try {
      const res = await this.server.get(input);
      if (!res) run = {ok: false, reason: i18n.getMessage('No response from the server')};
      else if (res.isError) run = {ok: false, reason: res.errorMessage};
      else run = res.run || {ok: false, reason: i18n.getMessage('No response from the server')};
    } catch (e) {
      run = {ok: false, reason: e.message};
    }
    if (seq !== this._seq) return;
    this._run = run;
    this._loading = false;
  }

  render() {
    const type = String(this.chartType || 'column').toLowerCase();
    return html`
      <section
        class="flex h-full flex-col gap-2 overflow-hidden rounded-lg bg-base-100 p-3"
        aria-label=${this.chartTitle || i18n.getMessage('Chart')}
      >
        ${this.chartTitle
          ? html`<h2 class="truncate text-sm font-semibold text-text-primary">
              ${this.chartTitle}
            </h2>`
          : ''}
        <x-dash-chart
          .run=${this._run}
          chart-type=${type}
          .height=${this._height}
          ?loading=${this._loading}
        ></x-dash-chart>
      </section>
    `;
  }
}
