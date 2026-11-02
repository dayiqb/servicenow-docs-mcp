import {html, css, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXWidgetElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';

const {name, description, bestFor, chatCompatible, category, server, discoverable} = decorators;

@customElement('x-dash-settings')
@name('Dashboard settings')
@description('Lets dashboard admins manage which tables builders can use, and how each table is counted.')
@bestFor('Admin page for the table allow list of the dashboard builder.')
@chatCompatible(false)
@category('custom')
@server('./server-script.js')
@discoverable(true)
export default class DashSettings extends AIUXWidgetElement {
  static properties = {
    _rows: {state: true},
    _loading: {state: true},
    _error: {state: true},
    _table: {state: true},
    _secure: {state: true}
  };

  static styles = css`
    :host {
      display: block;
    }
  `;

  constructor() {
    super();
    this._rows = [];
    this._loading = true;
    this._error = '';
    this._table = '';
    this._secure = true;
  }

  connectedCallback() {
    super.connectedCallback();
    this._call({action: 'list'});
  }

  async _call(input) {
    this._error = '';
    try {
      const res = await this.server.get(input);
      if (!res) throw new Error(i18n.getMessage('No response from the server'));
      if (res.isError) this._error = res.errorMessage;
      if (res.rows) this._rows = res.rows;
      return !res.isError;
    } catch (e) {
      this._error = e.message;
      return false;
    } finally {
      this._loading = false;
    }
  }

  async _add(e) {
    e.preventDefault();
    const ok = await this._call({action: 'add', table: this._table, secure: this._secure});
    if (ok) this._table = '';
  }

  render() {
    if (this._loading) {
      return html`<div role="status" class="aiux-skeleton h-40 rounded">
        <span class="sr-only">${i18n.getMessage('Loading')}</span>
      </div>`;
    }
    return html`
      <p class="mb-4 max-w-3xl text-sm text-text-secondary">
        ${i18n.getMessage(
          'Builders can only use tables on this list. "Full record security" counts each record with record and field rules applied. It is slower and stops at 10,000 records. Turn it off only for tables that have no record-level rules.'
        )}
      </p>
      ${this._error
        ? html`<div class="aiux-alert aiux-alert-error aiux-alert-soft mb-4" role="alert">${this._error}</div>`
        : nothing}
      <form class="mb-6 flex flex-wrap items-end gap-3" aria-label=${i18n.getMessage('Add table')} @submit=${this._add}>
        <label class="aiux-fieldset">
          <span class="aiux-label">${i18n.getMessage('Table name')}</span>
          <input
            class="aiux-input"
            required
            .value=${this._table}
            @input=${e => (this._table = e.target.value)}
          />
        </label>
        <label class="flex items-center gap-2 pb-2">
          <input
            type="checkbox"
            class="aiux-toggle"
            .checked=${this._secure}
            @change=${e => (this._secure = e.target.checked)}
          />
          <span>${i18n.getMessage('Full record security')}</span>
        </label>
        <button class="aiux-btn aiux-btn-primary" type="submit">${i18n.getMessage('Add table')}</button>
      </form>
      <div class="overflow-x-auto">
        <table class="aiux-table w-full">
          <thead>
            <tr>
              <th scope="col">${i18n.getMessage('Table')}</th>
              <th scope="col">${i18n.getMessage('Full record security')}</th>
              <th scope="col">${i18n.getMessage('Active')}</th>
              <th scope="col"><span class="sr-only">${i18n.getMessage('Actions')}</span></th>
            </tr>
          </thead>
          <tbody>
            ${this._rows.map(
              r => html`<tr>
                <td class="break-words">${r.label} <span class="text-xs text-text-tertiary">(${r.table})</span></td>
                <td>
                  <input
                    type="checkbox"
                    class="aiux-toggle aiux-toggle-sm"
                    aria-label=${i18n.getMessage('Full record security for {0}', [r.table])}
                    .checked=${r.secure}
                    @change=${e => this._call({action: 'update', id: r.sys_id, secure: e.target.checked})}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    class="aiux-toggle aiux-toggle-sm"
                    aria-label=${i18n.getMessage('{0} is active', [r.table])}
                    .checked=${r.active}
                    @change=${e => this._call({action: 'update', id: r.sys_id, active: e.target.checked})}
                  />
                </td>
                <td>
                  <button
                    class="aiux-btn aiux-btn-ghost aiux-btn-xs text-error"
                    @click=${() => this._call({action: 'remove', id: r.sys_id})}
                  >
                    ${i18n.getMessage('Remove')}
                  </button>
                </td>
              </tr>`
            )}
          </tbody>
        </table>
      </div>
    `;
  }
}
