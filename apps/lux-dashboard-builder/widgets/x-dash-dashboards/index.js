import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXWidgetElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {navigate} from '@servicenow/aiux/aiux-client';

const {name, description, bestFor, chatCompatible, category, server, discoverable} = decorators;

@customElement('x-dash-dashboards')
@name('Dashboard list')
@description('Lists the dashboards that the user owns or that are shared, and creates new dashboards.')
@bestFor('Picking or creating a no-code dashboard.')
@chatCompatible(false)
@category('custom')
@server('./server-script.js')
@discoverable(true)
export default class DashDashboards extends AIUXWidgetElement {
  static properties = {
    _mine: {state: true},
    _shared: {state: true},
    _canCreate: {state: true},
    _loading: {state: true},
    _error: {state: true},
    _newName: {state: true},
    _creating: {state: true}
  };

  static styles = css`
    :host {
      display: block;
    }
  `;

  constructor() {
    super();
    this._mine = [];
    this._shared = [];
    this._canCreate = false;
    this._loading = true;
    this._error = '';
    this._newName = '';
    this._creating = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this._load();
  }

  async _load() {
    this._loading = true;
    this._error = '';
    try {
      const res = await this.server.get({action: 'list'});
      if (!res || res.isError) throw new Error(res?.errorMessage || i18n.getMessage('Failed to load data'));
      this._mine = res.mine || [];
      this._shared = res.shared || [];
      this._canCreate = !!res.canCreate;
    } catch (e) {
      this._error = e.message;
    } finally {
      this._loading = false;
    }
  }

  async _create(e) {
    e.preventDefault();
    const nameValue = this._newName.trim();
    if (!nameValue || this._creating) return;
    this._creating = true;
    try {
      const res = await this.server.get({action: 'create', name: nameValue});
      if (!res || res.isError) throw new Error(res?.errorMessage || i18n.getMessage('Failed to create'));
      navigate(`/dashboard/${res.dashboardId}`);
    } catch (err) {
      this._error = err.message;
    } finally {
      this._creating = false;
    }
  }

  _renderList(items, emptyText) {
    if (!items.length) return html`<p class="text-sm text-text-secondary">${emptyText}</p>`;
    return html`<ul class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      ${items.map(
        d => html`<li>
          <a
            class="aiux-card block h-full border border-base-300 bg-base-100 shadow-sm hover:border-primary focus-visible:outline-2"
            href="./dashboard/${d.sys_id}"
            @click=${ev => {
              ev.preventDefault();
              navigate(`/dashboard/${d.sys_id}`);
            }}
          >
            <span class="aiux-card-body gap-1 p-4">
              <span class="aiux-card-title break-words text-base">${d.name}</span>
              ${d.description ? html`<span class="break-words text-sm text-text-secondary">${d.description}</span>` : nothing}
              <span class="text-xs text-text-tertiary">
                ${d.shared ? i18n.getMessage('Shared') : i18n.getMessage('Private')}
                ${d.owner_name ? html` · ${d.owner_name}` : nothing}
              </span>
            </span>
          </a>
        </li>`
      )}
    </ul>`;
  }

  render() {
    if (this._loading) {
      return html`<div role="status" class="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div class="aiux-skeleton h-24 rounded"></div>
        <div class="aiux-skeleton h-24 rounded"></div>
        <div class="aiux-skeleton h-24 rounded"></div>
        <span class="sr-only">${i18n.getMessage('Loading dashboards')}</span>
      </div>`;
    }
    return html`
      ${this._error
        ? html`<div class="aiux-alert aiux-alert-error aiux-alert-soft mb-4" role="alert">
            <span>${this._error}</span>
            <button class="aiux-btn aiux-btn-sm aiux-btn-ghost" @click=${this._load}>${i18n.getMessage('Retry')}</button>
          </div>`
        : nothing}
      ${this._canCreate
        ? html`<form class="mb-6 flex flex-wrap items-end gap-2" aria-label=${i18n.getMessage('Create dashboard')} @submit=${this._create}>
            <label class="aiux-fieldset min-w-64 grow md:grow-0">
              <span class="aiux-label">${i18n.getMessage('New dashboard name')}</span>
              <input
                class="aiux-input w-full"
                maxlength="100"
                required
                .value=${this._newName}
                @input=${e => (this._newName = e.target.value)}
              />
            </label>
            <button class="aiux-btn aiux-btn-primary" type="submit" ?disabled=${this._creating}>
              ${i18n.getMessage('Create dashboard')}
            </button>
          </form>`
        : nothing}
      ${this._canCreate
        ? html`<section class="mb-6" aria-labelledby="mine-title">
            <h2 id="mine-title" class="mb-2 text-lg font-semibold">${i18n.getMessage('My dashboards')}</h2>
            ${this._renderList(this._mine, i18n.getMessage('You have no dashboards yet.'))}
          </section>`
        : nothing}
      <section aria-labelledby="shared-title">
        <h2 id="shared-title" class="mb-2 text-lg font-semibold">${i18n.getMessage('Shared dashboards')}</h2>
        ${this._renderList(this._shared, i18n.getMessage('No dashboards are shared with you.'))}
      </section>
    `;
  }
}
