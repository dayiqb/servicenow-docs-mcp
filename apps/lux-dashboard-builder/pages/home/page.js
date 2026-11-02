import {html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {setDocumentTitle} from '../../utils/document-title.js';
import '../../widgets/x-dash-dashboards/index.js';

const {acl} = decorators;

@customElement('x-dash-home-page')
@acl([{decision: 'allow_if', roles: ['x_steas_dash.viewer']}])
export default class HomePage extends AIUXElement {
  static styles = css`
    :host {
      display: block;
    }
  `;

  firstUpdated() {
    setDocumentTitle(i18n.getMessage('Dashboards'));
  }

  render() {
    return html`
      <div class="mx-auto flex max-w-screen-2xl flex-col gap-4 p-4 lg:p-6">
        <h1 class="text-2xl font-bold text-text-primary">${i18n.getMessage('Dashboards')}</h1>
        <x-dash-dashboards></x-dash-dashboards>
      </div>
    `;
  }
}
