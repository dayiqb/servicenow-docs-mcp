import {html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {setDocumentTitle} from '../../utils/document-title.js';
import '../../widgets/x-dash-settings/index.js';

const {acl} = decorators;

@customElement('x-dash-settings-page')
@acl([{decision: 'allow_if', roles: ['x_dash.admin']}])
export default class SettingsPage extends AIUXElement {
  static styles = css`
    :host {
      display: block;
    }
  `;

  firstUpdated() {
    setDocumentTitle(i18n.getMessage('Dashboard settings'));
  }

  render() {
    return html`
      <div class="mx-auto flex max-w-screen-xl flex-col gap-4 p-4 lg:p-6">
        <h1 class="text-2xl font-bold text-text-primary">${i18n.getMessage('Allowed tables')}</h1>
        <x-dash-settings></x-dash-settings>
      </div>
    `;
  }
}
