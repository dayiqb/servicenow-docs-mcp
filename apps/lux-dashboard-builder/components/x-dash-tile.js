import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import './x-dash-chart.js';

/**
 * One visualization tile on the dashboard grid.
 * Properties: chart, run, loading, editMode, selected.
 * Events (edit mode): tile-configure, tile-duplicate, tile-remove (detail: {key}).
 */
@customElement('x-dash-tile')
export class DashTile extends AIUXElement {
  static properties = {
    key: {type: String},
    chart: {type: Object, attribute: false},
    run: {type: Object, attribute: false},
    loading: {type: Boolean},
    editMode: {type: Boolean, attribute: 'edit-mode'},
    selected: {type: Boolean},
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
    this.key = '';
    this.chart = null;
    this.run = null;
    this.loading = false;
    this.editMode = false;
    this.selected = false;
    this._height = 200;
  }

  connectedCallback() {
    super.connectedCallback();
    this._resize = new ResizeObserver(entries => {
      const box = entries[0]?.contentRect;
      if (!box) return;
      const h = Math.max(80, Math.floor(box.height) - 64);
      if (Math.abs(h - this._height) > 4) this._height = h;
    });
    this._resize.observe(this);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resize?.disconnect();
  }

  _emit(name) {
    this.dispatchEvent(new CustomEvent(name, {detail: {key: this.key}, bubbles: true, composed: true}));
  }

  render() {
    const c = this.chart || {};
    const title = c.title || i18n.getMessage('Untitled visualization');
    const ring = this.selected ? 'ring-2 ring-primary' : this.editMode ? 'ring-1 ring-base-300' : '';
    return html`
      <article
        class="flex h-full flex-col gap-2 overflow-hidden rounded-lg border border-base-300 bg-base-100 p-3 shadow-sm ${ring}"
        aria-label=${title}
      >
        <header class="flex min-h-7 items-center justify-between gap-2">
          <h2 class="min-w-0 truncate text-sm font-semibold text-text-primary" title=${title}>${title}</h2>
          ${this.editMode
            ? html`<div class="flex shrink-0 gap-1">
                <button
                  type="button"
                  class="aiux-btn aiux-btn-ghost aiux-btn-xs"
                  aria-label=${i18n.getMessage('Configure {0}', [title])}
                  @click=${() => this._emit('tile-configure')}
                >
                  ${i18n.getMessage('Configure')}
                </button>
                <button
                  type="button"
                  class="aiux-btn aiux-btn-ghost aiux-btn-xs"
                  aria-label=${i18n.getMessage('Duplicate {0}', [title])}
                  @click=${() => this._emit('tile-duplicate')}
                >
                  ${i18n.getMessage('Duplicate')}
                </button>
                <button
                  type="button"
                  class="aiux-btn aiux-btn-ghost aiux-btn-xs text-error"
                  aria-label=${i18n.getMessage('Remove {0}', [title])}
                  @click=${() => this._emit('tile-remove')}
                >
                  ${i18n.getMessage('Remove')}
                </button>
              </div>`
            : nothing}
        </header>
        <x-dash-chart
          .run=${this.run}
          .loading=${this.loading}
          chart-type=${c.chart_type || 'column'}
          .height=${this._height}
        ></x-dash-chart>
      </article>
    `;
  }
}
